"""Admin IAM — manage admin accounts (superadmin only).

Replaces the shell-only `scripts/create_admin.py` bottleneck: create/list admins,
change role, activate/deactivate, force-logout, reset TOTP, reset password — all from
the panel, all audited.

Security model:
  - Every route requires role `superadmin` (require_role).
  - A new admin gets a one-time temp password (returned ONCE) with must_change_password
    + totp_required set, so first login forces a password change and TOTP enrolment.
  - Deactivate / role-change / reset / force-logout bump session_epoch, which
    deps.get_current_admin checks against the token's `sv` → the target's existing
    sessions die immediately.
  - Self-mutation is blocked here (manage yourself via /auth/*), and the LAST active
    superadmin cannot be demoted or deactivated (no lockout).
"""
import logging
import secrets
from datetime import datetime, timezone

import bcrypt as _bcrypt
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.admin.deps import require_role
from app.api.admin.audit_writer import audit
from app.models.admin_user import AdminUser

router = APIRouter()
logger = logging.getLogger(__name__)

VALID_ROLES = ("superadmin", "ops", "support")


def _hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode("utf-8"), _bcrypt.gensalt(rounds=12)).decode("utf-8")


def _temp_password() -> str:
    # url-safe, ~16 chars → comfortably above the 12-char minimum
    return secrets.token_urlsafe(12)


def _serialize(a: AdminUser) -> dict:
    return {
        "id":                   str(a.id),
        "email":                a.email,
        "name":                 a.name,
        "role":                 a.role,
        "is_active":            a.is_active,
        "has_totp":             a.totp_secret_enc is not None,
        "must_change_password": bool(a.must_change_password),
        "totp_required":        bool(a.totp_required),
        "last_login_at":        a.last_login_at.isoformat() if a.last_login_at else None,
        "created_at":           a.created_at.isoformat() if a.created_at else None,
        "created_by":           a.created_by,
    }


async def _get_or_404(db: AsyncSession, admin_id: str) -> AdminUser:
    a = (await db.execute(select(AdminUser).where(AdminUser.id == admin_id))).scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="Admin not found")
    return a


async def _active_superadmin_count(db: AsyncSession, exclude_id: str | None = None) -> int:
    q = select(func.count()).select_from(AdminUser).where(
        AdminUser.role == "superadmin", AdminUser.is_active == True
    )
    if exclude_id:
        q = q.where(AdminUser.id != exclude_id)
    return (await db.execute(q)).scalar() or 0


def _bump(a: AdminUser) -> None:
    a.session_epoch = (a.session_epoch or 0) + 1


# ── Schemas ──────────────────────────────────────────────────────────────────
class CreateAdminRequest(BaseModel):
    email: EmailStr
    name: str
    role: str


class PatchAdminRequest(BaseModel):
    role: str | None = None
    is_active: bool | None = None


# ── Routes ───────────────────────────────────────────────────────────────────
@router.get("/admins")
async def list_admins(
    _: dict = Depends(require_role("superadmin")),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(select(AdminUser).order_by(AdminUser.created_at.desc().nullslast()))).scalars().all()
    return {"admins": [_serialize(a) for a in rows]}


@router.post("/admins")
async def create_admin(
    body: CreateAdminRequest,
    admin: dict = Depends(require_role("superadmin")),
    db: AsyncSession = Depends(get_db),
):
    if body.role not in VALID_ROLES:
        raise HTTPException(status_code=422, detail=f"role must be one of {list(VALID_ROLES)}")
    email = str(body.email).strip().lower()
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="name is required")

    existing = (await db.execute(select(AdminUser).where(AdminUser.email == email))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="An admin with this email already exists")

    temp_pw = _temp_password()
    new = AdminUser(
        email=email,
        name=name,
        role=body.role,
        password_hash=_hash_password(temp_pw),
        is_active=True,
        must_change_password=True,
        totp_required=True,
        session_epoch=0,
        created_at=datetime.now(timezone.utc),
        created_by=admin["email"],
    )
    db.add(new)
    await db.commit()
    await db.refresh(new)

    await audit(db, admin["email"], "create_admin",
                target_type="admin", target_id=str(new.id),
                details={"email": email, "role": body.role})
    logger.warning(f"Admin {admin['email']} created new admin {email} (role={body.role})")

    # temp_password returned ONCE — never stored in plaintext, never re-fetchable.
    return {"admin": _serialize(new), "temp_password": temp_pw}


@router.patch("/admins/{admin_id}")
async def patch_admin(
    admin_id: str,
    body: PatchAdminRequest,
    admin: dict = Depends(require_role("superadmin")),
    db: AsyncSession = Depends(get_db),
):
    if admin_id == admin["sub"]:
        raise HTTPException(status_code=400, detail="Manage your own account from account settings, not here.")

    target = await _get_or_404(db, admin_id)
    changed = {}

    if body.role is not None and body.role != target.role:
        if body.role not in VALID_ROLES:
            raise HTTPException(status_code=422, detail=f"role must be one of {list(VALID_ROLES)}")
        # Guard: never demote the last active superadmin.
        if target.role == "superadmin" and target.is_active and await _active_superadmin_count(db, exclude_id=admin_id) == 0:
            raise HTTPException(status_code=400, detail="Cannot demote the last active superadmin.")
        changed["role"] = {"from": target.role, "to": body.role}
        target.role = body.role

    if body.is_active is not None and body.is_active != target.is_active:
        # Guard: never deactivate the last active superadmin.
        if not body.is_active and target.role == "superadmin" and await _active_superadmin_count(db, exclude_id=admin_id) == 0:
            raise HTTPException(status_code=400, detail="Cannot deactivate the last active superadmin.")
        changed["is_active"] = body.is_active
        target.is_active = body.is_active

    if not changed:
        return {"admin": _serialize(target), "changed": False}

    _bump(target)  # role change / deactivation takes effect on the target immediately
    await db.commit()
    await db.refresh(target)

    await audit(db, admin["email"], "update_admin",
                target_type="admin", target_id=admin_id, details=changed)
    return {"admin": _serialize(target), "changed": True}


@router.post("/admins/{admin_id}/force-logout")
async def force_logout_admin(
    admin_id: str,
    admin: dict = Depends(require_role("superadmin")),
    db: AsyncSession = Depends(get_db),
):
    if admin_id == admin["sub"]:
        raise HTTPException(status_code=400, detail="Use Sign out for your own session.")
    target = await _get_or_404(db, admin_id)
    _bump(target)
    await db.commit()
    await audit(db, admin["email"], "force_logout_admin", target_type="admin", target_id=admin_id)
    return {"status": "ok"}


@router.post("/admins/{admin_id}/reset-totp")
async def reset_admin_totp(
    admin_id: str,
    admin: dict = Depends(require_role("superadmin")),
    db: AsyncSession = Depends(get_db),
):
    """Clear the target's TOTP and force re-enrolment on next login (e.g. lost device)."""
    if admin_id == admin["sub"]:
        raise HTTPException(status_code=400, detail="Manage your own TOTP from Config.")
    target = await _get_or_404(db, admin_id)
    target.totp_secret_enc = None
    target.totp_required = True
    _bump(target)
    await db.commit()
    await audit(db, admin["email"], "reset_admin_totp", target_type="admin", target_id=admin_id)
    return {"status": "ok"}


@router.post("/admins/{admin_id}/reset-password")
async def reset_admin_password(
    admin_id: str,
    admin: dict = Depends(require_role("superadmin")),
    db: AsyncSession = Depends(get_db),
):
    """Issue a new one-time temp password; forces a change on next login. Returned ONCE."""
    if admin_id == admin["sub"]:
        raise HTTPException(status_code=400, detail="Change your own password from account settings.")
    target = await _get_or_404(db, admin_id)
    temp_pw = _temp_password()
    target.password_hash = _hash_password(temp_pw)
    target.must_change_password = True
    _bump(target)  # kills the target's current sessions
    await db.commit()
    await audit(db, admin["email"], "reset_admin_password", target_type="admin", target_id=admin_id)
    logger.warning(f"Admin {admin['email']} reset password for {target.email}")
    return {"status": "ok", "temp_password": temp_pw}
