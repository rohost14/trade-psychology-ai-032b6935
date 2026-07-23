"""
Admin authentication — email + password → OTP/TOTP → JWT.
Completely independent of Zerodha OAuth.

Login flows:
  A. TOTP configured:  password → totp_required → POST /totp/verify → JWT
  B. TOTP not set up:  password → email OTP    → POST /verify      → JWT

TOTP setup (requires active session):
  GET  /totp/setup   → secret + QR URI (pending, stored in Redis 5 min)
  POST /totp/confirm → verify code, store encrypted secret in DB
  DELETE /totp       → disable TOTP (superadmin only)
"""
import secrets
import string
import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException, Depends, Request, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
import bcrypt as _bcrypt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from jose import jwt

from app.core.database import get_db
from app.core.config import settings
from app.models.admin_user import AdminUser
from app.api.admin.deps import get_current_admin, require_role
from app.api.admin import session_registry
from app.core.rate_limiter import admin_login_limiter, admin_otp_limiter

_bearer_logout = HTTPBearer(auto_error=False)

router = APIRouter()
logger = logging.getLogger(__name__)

def _hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode("utf-8"), _bcrypt.gensalt(rounds=12)).decode("utf-8")

def _verify_password(password: str, hashed: str) -> bool:
    try:
        return _bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False

OTP_TTL    = 300   # 5 minutes
OTP_PREFIX = "admin_otp:"
TOTP_PENDING_PREFIX = "admin_totp_pending:"

LOGIN_FAIL_PREFIX  = "admin_fail:"
LOGIN_FAIL_MAX     = 5
LOGIN_FAIL_TTL     = 900

# Per-ACCOUNT lockout on the 2nd factor (email OTP / TOTP). The per-IP admin_otp_limiter
# alone lets a 6-digit code be brute-forced from many IPs; this caps attempts per email.
VERIFY_FAIL_PREFIX = "admin_vfail:"
VERIFY_FAIL_MAX    = 5
VERIFY_FAIL_TTL    = 900

# TOTP replay guard — a code stays valid ~90s (valid_window=1). Once accepted it is marked
# consumed for this TTL so the same code cannot be replayed (screen-share / phishing proxy).
TOTP_USED_PREFIX   = "admin_totp_used:"
TOTP_USED_TTL      = 120

BLOCKLIST_PREFIX = "admin_jti_block:"


def _redis():
    import redis as redis_lib
    return redis_lib.from_url(settings.REDIS_URL, decode_responses=True)


ADMIN_COOKIE = "tm_admin"


def _set_admin_cookie(response: Response, token: str) -> None:
    """Store the admin JWT in an httpOnly cookie (not readable by JS → XSS-safe).
    dev: SameSite=Lax over http. prod: SameSite=None + Secure (cross-site https)."""
    secure = settings.ENVIRONMENT != "development"
    response.set_cookie(
        key=ADMIN_COOKIE, value=token, httponly=True, secure=secure,
        samesite="none" if secure else "lax",
        max_age=settings.ADMIN_JWT_EXPIRE_HOURS * 3600, path="/api/admin",
    )


def _clear_admin_cookie(response: Response) -> None:
    response.delete_cookie(ADMIN_COOKIE, path="/api/admin")


def _assert_verify_unlocked(r, email: str) -> None:
    """Raise 429 if this account has hit VERIFY_FAIL_MAX failed 2nd-factor attempts."""
    key = f"{VERIFY_FAIL_PREFIX}{email}"
    if int(r.get(key) or 0) >= VERIFY_FAIL_MAX:
        ttl = r.ttl(key)
        raise HTTPException(
            status_code=429,
            detail=f"Too many attempts. Try again in {ttl}s.",
            headers={"Retry-After": str(ttl)},
        )


def _record_verify_fail(r, email: str) -> None:
    key = f"{VERIFY_FAIL_PREFIX}{email}"
    pipe = r.pipeline()
    pipe.incr(key)
    pipe.expire(key, VERIFY_FAIL_TTL)
    pipe.execute()


def _clear_verify_fail(r, email: str) -> None:
    r.delete(f"{VERIFY_FAIL_PREFIX}{email}")


def _make_otp() -> str:
    return "".join(secrets.choice(string.digits) for _ in range(6))


def _make_admin_jwt(admin: AdminUser) -> str:
    secret = settings.ADMIN_JWT_SECRET
    if not secret:
        raise RuntimeError("ADMIN_JWT_SECRET not configured")
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.ADMIN_JWT_EXPIRE_HOURS)
    return jwt.encode(
        {
            "sub":   str(admin.id),
            "email": admin.email,
            "name":  admin.name,
            "role":  admin.role,
            "sv":    int(admin.session_epoch or 0),  # session epoch — see deps.get_current_admin
            "exp":   expire,
            "jti":   secrets.token_hex(16),
        },
        secret,
        algorithm="HS256",
    )


async def _issue_login(admin, request, db, method: str) -> str:
    """Mint a JWT, register the live session in Redis, and record login history.
    Registry/history are best-effort and never block issuing the token."""
    token = _make_admin_jwt(admin)
    try:
        p = jwt.decode(token, settings.ADMIN_JWT_SECRET, algorithms=["HS256"])
        session_registry.register(
            str(admin.id), p["jti"], int(p["exp"]),
            session_registry.client_ip(request), session_registry.user_agent(request),
            int(admin.session_epoch or 0),
        )
    except Exception as _e:
        logger.warning(f"session register skipped: {_e}")
    await session_registry.record_login(db, admin, request, method)
    return token


def _decrypt_totp_secret(enc: str) -> str:
    from cryptography.fernet import Fernet
    return Fernet(settings.ENCRYPTION_KEY.encode()).decrypt(enc.encode()).decode()


def _encrypt_totp_secret(secret: str) -> str:
    from cryptography.fernet import Fernet
    return Fernet(settings.ENCRYPTION_KEY.encode()).encrypt(secret.encode()).decode()


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


# ── Step 1: Password verification ─────────────────────────────────────────────

@router.post("/login")
async def admin_login(
    request: Request,
    response: Response,
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
    _rl: None = Depends(admin_login_limiter),
):
    """
    Step 1: verify email + password.
    If admin has TOTP configured: returns {status: "totp_required"} — no email OTP sent.
    Otherwise: sends email OTP and returns {status: "otp_sent"}.
    """
    r = _redis()
    fail_key = f"{LOGIN_FAIL_PREFIX}{body.email}"

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

    dummy_hash = "$2b$12$dummy.hash.to.prevent.timing.attack.padding.xxxxxxxxxxx"
    check_hash = admin.password_hash if admin else dummy_hash
    valid = _verify_password(body.password, check_hash)

    if not admin or not valid:
        pipe = r.pipeline()
        pipe.incr(fail_key)
        pipe.expire(fail_key, LOGIN_FAIL_TTL)
        pipe.execute()
        logger.warning(f"Admin login failed for {body.email} (attempt {fail_count + 1})")
        raise HTTPException(status_code=401, detail="Invalid credentials")

    r.delete(fail_key)

    # Dev bypass — skip all 2FA, return JWT immediately (only in development)
    if settings.ADMIN_DEV_BYPASS and settings.ENVIRONMENT == "development":
        logger.warning(f"ADMIN_DEV_BYPASS active — issuing JWT for {admin.email} without 2FA")
        await db.execute(
            update(AdminUser).where(AdminUser.id == admin.id)
            .values(last_login_at=datetime.now(timezone.utc))
        )
        await db.commit()
        token = await _issue_login(admin, request, db, "dev_bypass")
        _set_admin_cookie(response, token)
        return {"status": "ok", "token": token, "admin": {"email": admin.email, "name": admin.name, "role": admin.role}}

    # TOTP path — skip email OTP entirely
    if admin.totp_secret_enc:
        return {"status": "totp_required", "message": "Enter your authenticator code"}

    # Email OTP path
    otp = _make_otp()
    r.setex(f"{OTP_PREFIX}{body.email}", OTP_TTL, otp)

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
        logger.error(
            f"Failed to send admin OTP email to {body.email}: {e}. "
            "OTP stored in Redis under key admin_otp:{email} — use redis-cli GET in dev."
        )

    return {"status": "otp_sent", "message": "Check your email for the login code"}


# ── Step 2A: Email OTP verification ───────────────────────────────────────────

@router.post("/verify", response_model=TokenResponse)
async def admin_verify_otp(
    request: Request,
    response: Response,
    body: OTPRequest,
    db: AsyncSession = Depends(get_db),
    _rl: None = Depends(admin_otp_limiter),
):
    """Step 2 (email OTP path): verify OTP. Returns admin JWT."""
    r = _redis()
    _assert_verify_unlocked(r, body.email)
    stored_otp = r.get(f"{OTP_PREFIX}{body.email}")

    submitted = body.otp.strip()
    if not stored_otp or not secrets.compare_digest(stored_otp, submitted):
        _record_verify_fail(r, body.email)
        raise HTTPException(status_code=401, detail="Invalid or expired code")

    r.delete(f"{OTP_PREFIX}{body.email}")

    result = await db.execute(
        select(AdminUser).where(AdminUser.email == body.email, AdminUser.is_active == True)
    )
    admin = result.scalar_one_or_none()
    if not admin:
        raise HTTPException(status_code=401, detail="Account not found")

    _clear_verify_fail(r, body.email)

    await db.execute(
        update(AdminUser).where(AdminUser.id == admin.id)
        .values(last_login_at=datetime.now(timezone.utc))
    )
    await db.commit()

    token = await _issue_login(admin, request, db, "email_otp")
    _set_admin_cookie(response, token)
    logger.info(f"Admin login (OTP): {admin.email} role={admin.role}")
    try:
        from app.api.admin.audit_writer import audit
        await audit(db, admin.email, "admin_login",
                    target_type="admin", target_id=str(admin.id),
                    details={"name": admin.name, "method": "email_otp"})
    except Exception as _e:
        logger.warning(f"Admin login audit log failed: {_e}")

    return TokenResponse(
        token=token,
        admin={"id": str(admin.id), "email": admin.email, "name": admin.name, "role": admin.role},
    )


# ── Step 2B: TOTP verification ────────────────────────────────────────────────

@router.post("/totp/verify", response_model=TokenResponse)
async def admin_verify_totp(
    request: Request,
    response: Response,
    body: OTPRequest,
    db: AsyncSession = Depends(get_db),
    _rl: None = Depends(admin_otp_limiter),
):
    """Step 2 (TOTP path): verify 6-digit authenticator code. Returns admin JWT."""
    r = _redis()
    _assert_verify_unlocked(r, body.email)

    result = await db.execute(
        select(AdminUser).where(AdminUser.email == body.email, AdminUser.is_active == True)
    )
    admin = result.scalar_one_or_none()
    if not admin or not admin.totp_secret_enc:
        _record_verify_fail(r, body.email)
        raise HTTPException(status_code=401, detail="TOTP not configured for this account")

    import pyotp
    code   = body.otp.strip()
    secret = _decrypt_totp_secret(admin.totp_secret_enc)
    totp   = pyotp.TOTP(secret)
    if not totp.verify(code, valid_window=1):
        _record_verify_fail(r, body.email)
        raise HTTPException(status_code=401, detail="Invalid authenticator code")

    # Replay guard — atomically claim this code; if already claimed, reject the replay.
    if not r.set(f"{TOTP_USED_PREFIX}{admin.id}:{code}", "1", nx=True, ex=TOTP_USED_TTL):
        _record_verify_fail(r, body.email)
        raise HTTPException(status_code=401, detail="Authenticator code already used")

    _clear_verify_fail(r, body.email)

    await db.execute(
        update(AdminUser).where(AdminUser.id == admin.id)
        .values(last_login_at=datetime.now(timezone.utc))
    )
    await db.commit()

    token = await _issue_login(admin, request, db, "totp")
    _set_admin_cookie(response, token)
    logger.info(f"Admin login (TOTP): {admin.email} role={admin.role}")
    try:
        from app.api.admin.audit_writer import audit
        await audit(db, admin.email, "admin_login",
                    target_type="admin", target_id=str(admin.id),
                    details={"name": admin.name, "method": "totp"})
    except Exception as _e:
        logger.warning(f"Admin login audit log failed: {_e}")

    return TokenResponse(
        token=token,
        admin={"id": str(admin.id), "email": admin.email, "name": admin.name, "role": admin.role},
    )


# ── TOTP Management (requires active session) ─────────────────────────────────

@router.get("/totp/setup")
async def totp_setup_init(
    admin_payload: dict = Depends(get_current_admin),
):
    """
    Generate a new TOTP secret + QR code URI.
    Secret is stored in Redis for 5 minutes pending confirmation.
    Scan the QR URI with Google Authenticator / Authy, then call POST /totp/confirm.
    """
    import pyotp
    secret  = pyotp.random_base32()
    r       = _redis()
    r.setex(f"{TOTP_PENDING_PREFIX}{admin_payload['email']}", 300, secret)

    totp    = pyotp.TOTP(secret)
    qr_uri  = totp.provisioning_uri(
        name=admin_payload["email"],
        issuer_name=settings.ADMIN_TOTP_ISSUER,
    )
    return {"secret": secret, "qr_uri": qr_uri}


@router.post("/totp/confirm")
async def totp_setup_confirm(
    body: dict,
    admin_payload: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Confirm TOTP setup with a valid code from the authenticator app.
    Stores the Fernet-encrypted secret in the DB. From next login, TOTP replaces email OTP.
    """
    r = _redis()
    pending = r.get(f"{TOTP_PENDING_PREFIX}{admin_payload['email']}")
    if not pending:
        raise HTTPException(status_code=400, detail="No pending TOTP setup. Call GET /totp/setup first.")

    import pyotp
    totp = pyotp.TOTP(pending)
    if not totp.verify((body.get("code") or "").strip(), valid_window=1):
        raise HTTPException(status_code=401, detail="Invalid code. Scan the QR and try again.")

    encrypted = _encrypt_totp_secret(pending)
    result = await db.execute(select(AdminUser).where(AdminUser.id == admin_payload["sub"]))
    admin  = result.scalar_one_or_none()
    if not admin:
        raise HTTPException(status_code=404)
    admin.totp_secret_enc = encrypted
    admin.totp_required = False   # forced-enrolment (if any) satisfied
    await db.commit()

    r.delete(f"{TOTP_PENDING_PREFIX}{admin_payload['email']}")
    logger.info(f"Admin TOTP enabled: {admin.email}")
    return {"status": "totp_enabled", "message": "TOTP is now active for your account"}


@router.delete("/totp")
async def totp_disable(
    admin_payload: dict = Depends(require_role("superadmin")),
    db: AsyncSession = Depends(get_db),
):
    """Disable TOTP for the current admin account. Superadmin only."""
    result = await db.execute(select(AdminUser).where(AdminUser.id == admin_payload["sub"]))
    admin  = result.scalar_one_or_none()
    if not admin:
        raise HTTPException(status_code=404)
    admin.totp_secret_enc = None
    await db.commit()
    logger.info(f"Admin TOTP disabled: {admin.email}")
    return {"status": "totp_disabled"}


# ── Session info + logout ─────────────────────────────────────────────────────

@router.get("/me")
async def admin_me(payload: dict = Depends(get_current_admin)):
    return {
        "email": payload["email"],
        "name":  payload["name"],
        "role":  payload.get("role", "superadmin"),
        "must_change_password": payload.get("must_change_password", False),
        "totp_required":        payload.get("totp_required", False),
        "has_totp":             payload.get("has_totp", False),
    }


class ChangePasswordRequest(BaseModel):
    new_password: str


@router.post("/change-password")
async def admin_change_password(
    request: Request,
    response: Response,
    body: ChangePasswordRequest,
    payload: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Change the current admin's password. Clears the must_change_password flag and
    bumps session_epoch (invalidating all OTHER sessions), then returns a FRESH token so
    the caller stays signed in. Used both for the forced first-login change and voluntary
    rotation."""
    new_pw = (body.new_password or "").strip()
    if len(new_pw) < 12:
        raise HTTPException(status_code=422, detail="Password must be at least 12 characters.")

    result = await db.execute(select(AdminUser).where(AdminUser.id == payload["sub"]))
    admin = result.scalar_one_or_none()
    if not admin:
        raise HTTPException(status_code=404)

    admin.password_hash = _hash_password(new_pw)
    admin.must_change_password = False
    admin.session_epoch = (admin.session_epoch or 0) + 1  # invalidate other sessions
    await db.commit()
    await db.refresh(admin)

    # Old sessions are already dead (epoch bumped); drop them from the registry and
    # register the fresh token that this response hands back.
    session_registry.clear(str(admin.id))
    token = _make_admin_jwt(admin)  # new token carries the bumped sv so THIS session survives
    try:
        p = jwt.decode(token, settings.ADMIN_JWT_SECRET, algorithms=["HS256"])
        session_registry.register(
            str(admin.id), p["jti"], int(p["exp"]),
            session_registry.client_ip(request), session_registry.user_agent(request),
            int(admin.session_epoch or 0),
        )
    except Exception:
        pass
    _set_admin_cookie(response, token)
    logger.info(f"Admin changed password: {admin.email}")
    try:
        from app.api.admin.audit_writer import audit
        await audit(db, admin.email, "change_password", target_type="admin", target_id=str(admin.id))
    except Exception as _e:
        logger.warning(f"change_password audit failed: {_e}")

    return {"status": "ok", "token": token}


@router.post("/logout")
async def admin_logout(
    response: Response,
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_logout),
    payload: dict = Depends(get_current_admin),
):
    """Invalidate current admin JWT server-side via JTI blocklist + clear the cookie."""
    _clear_admin_cookie(response)
    jti = payload.get("jti")
    exp = payload.get("exp")
    if jti and exp:
        try:
            ttl = int(exp - datetime.now(timezone.utc).timestamp())
            if ttl > 0:
                r = _redis()
                r.setex(f"{BLOCKLIST_PREFIX}{jti}", ttl, "1")
        except Exception as _e:
            logger.warning(f"Logout blocklist write failed (non-fatal): {_e}")
        session_registry.unregister(payload.get("sub", ""), jti)
    return {"status": "ok"}
