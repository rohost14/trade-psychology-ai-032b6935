"""
Admin authentication — email + password → OTP → JWT.
Completely independent of Zerodha OAuth.
"""
import random
import string
import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from passlib.context import CryptContext
from jose import jwt

from app.core.database import get_db
from app.core.config import settings
from app.models.admin_user import AdminUser
from app.api.admin.deps import get_current_admin
from app.core.rate_limiter import admin_login_limiter, admin_otp_limiter

router = APIRouter()
logger = logging.getLogger(__name__)
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

OTP_TTL    = 300   # 5 minutes
OTP_PREFIX = "admin_otp:"

# Per-email failed-attempt tracking (catches distributed IP attacks)
LOGIN_FAIL_PREFIX  = "admin_fail:"
LOGIN_FAIL_MAX     = 5      # lock after 5 consecutive failures
LOGIN_FAIL_TTL     = 900    # 15-minute lockout window


def _redis():
    import redis as redis_lib
    return redis_lib.from_url(settings.REDIS_URL, decode_responses=True)


def _make_otp() -> str:
    return "".join(random.choices(string.digits, k=6))


def _make_admin_jwt(admin: AdminUser) -> str:
    secret = settings.ADMIN_JWT_SECRET
    if not secret:
        raise RuntimeError("ADMIN_JWT_SECRET not configured")
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.ADMIN_JWT_EXPIRE_HOURS)
    return jwt.encode(
        {"sub": str(admin.id), "email": admin.email, "name": admin.name, "exp": expire},
        secret,
        algorithm="HS256",
    )


# ── Request/Response models ────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class OTPRequest(BaseModel):
    email: EmailStr
    otp: str

class TokenResponse(BaseModel):
    token: str
    admin: dict


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/login")
async def admin_login(
    request: Request,
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
    _rl: None = Depends(admin_login_limiter),
):
    """
    Step 1: verify email + password.
    On success, generate OTP and send to admin's email.
    Returns generic message regardless of whether email exists (no enumeration).
    """
    r = _redis()
    fail_key = f"{LOGIN_FAIL_PREFIX}{body.email}"

    # Check per-email lockout (catches attackers rotating IPs)
    fail_count = int(r.get(fail_key) or 0)
    if fail_count >= LOGIN_FAIL_MAX:
        ttl = r.ttl(fail_key)
        raise HTTPException(
            status_code=429,
            detail=f"Account temporarily locked. Try again in {ttl}s.",
            headers={"Retry-After": str(ttl)},
        )

    result = await db.execute(
        select(AdminUser).where(AdminUser.email == body.email, AdminUser.is_active == True)
    )
    admin = result.scalar_one_or_none()

    # Always verify password to prevent timing attacks that reveal account existence
    dummy_hash = "$2b$12$dummy.hash.to.prevent.timing.attack.padding.xxxxxxxxxxx"
    check_hash = admin.password_hash if admin else dummy_hash
    valid = pwd_ctx.verify(body.password, check_hash)

    if not admin or not valid:
        # Increment per-email failure counter
        pipe = r.pipeline()
        pipe.incr(fail_key)
        pipe.expire(fail_key, LOGIN_FAIL_TTL)
        pipe.execute()
        logger.warning(f"Admin login failed for {body.email} (attempt {fail_count + 1})")
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Success — clear failure counter
    r.delete(fail_key)

    # Generate and store OTP
    otp = _make_otp()
    r.setex(f"{OTP_PREFIX}{body.email}", OTP_TTL, otp)

    # Send OTP via email
    try:
        from app.services.email_service import email_service
        subject = "TradeMentor Admin — Your login code"
        html = f"""
        <div style="font-family: monospace; max-width: 480px; margin: 0 auto; padding: 32px; background: #0a0a0f; color: #e2e8f0; border-radius: 12px;">
            <h2 style="color: #f59e0b; margin-bottom: 8px;">TradeMentor Admin</h2>
            <p style="color: #94a3b8; margin-bottom: 24px;">Your one-time login code:</p>
            <div style="font-size: 2.5rem; font-weight: 800; letter-spacing: 0.3em; color: #fff; background: #1a1a2e; padding: 20px; border-radius: 8px; text-align: center; border: 1px solid #f59e0b33;">
                {otp}
            </div>
            <p style="color: #64748b; font-size: 0.8rem; margin-top: 20px;">
                Expires in 5 minutes. Do not share this code.
            </p>
        </div>
        """
        await email_service.send_email(body.email, subject, html)
        logger.info(f"Admin OTP sent to {body.email}")
    except Exception as e:
        logger.error(f"Failed to send admin OTP email to {body.email}: {e}. "
                     "Configure SMTP_HOST/SMTP_USER/SMTP_PASS to enable email delivery. "
                     "OTP is stored in Redis under key admin_otp:{email} — use redis-cli GET to retrieve in dev.")

    return {"status": "otp_sent", "message": "Check your email for the login code"}


@router.post("/verify", response_model=TokenResponse)
async def admin_verify_otp(
    request: Request,
    body: OTPRequest,
    db: AsyncSession = Depends(get_db),
    _rl: None = Depends(admin_otp_limiter),
):
    """
    Step 2: verify OTP. On success, return admin JWT.
    """
    r = _redis()
    stored_otp = r.get(f"{OTP_PREFIX}{body.email}")

    if not stored_otp or stored_otp != body.otp.strip():
        raise HTTPException(status_code=401, detail="Invalid or expired code")

    # OTP is one-time — delete immediately
    r.delete(f"{OTP_PREFIX}{body.email}")

    result = await db.execute(
        select(AdminUser).where(AdminUser.email == body.email, AdminUser.is_active == True)
    )
    admin = result.scalar_one_or_none()
    if not admin:
        raise HTTPException(status_code=401, detail="Account not found")

    # Update last login
    await db.execute(
        update(AdminUser)
        .where(AdminUser.id == admin.id)
        .values(last_login_at=datetime.now(timezone.utc))
    )
    await db.commit()

    token = _make_admin_jwt(admin)
    logger.info(f"Admin login: {admin.email}")
    # Write to DB audit log — admin logins are high-value security events
    try:
        from app.api.admin.audit_writer import audit
        await audit(db, admin.email, "admin_login",
                    target_type="admin", target_id=str(admin.id),
                    details={"name": admin.name})
    except Exception as _audit_err:
        logger.warning(f"Admin login audit log failed (non-fatal): {_audit_err}")
    return TokenResponse(
        token=token,
        admin={"id": str(admin.id), "email": admin.email, "name": admin.name},
    )


@router.get("/me")
async def admin_me(payload: dict = Depends(get_current_admin)):
    """Return current admin info from JWT."""
    return {"email": payload["email"], "name": payload["name"]}


@router.post("/logout")
async def admin_logout():
    """Client-side logout — just acknowledge. Token is stateless (JWT)."""
    return {"status": "ok"}
