"""Admin config — maintenance mode, announcement banner.

Maintenance mode and the announcement are stored in Redis via `app.core.admin_state`
so they apply across ALL uvicorn workers, not just the one that served the toggle.
Writes are superadmin-only — the frontend hides the Config page from non-superadmins
(`AdminLayout.tsx`), and the backend now enforces that same policy.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.admin.deps import get_current_admin, require_role
from app.core.config import settings
from app.core.database import get_db
from app.core import admin_state
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


class MaintenanceRequest(BaseModel):
    enabled: bool
    message: Optional[str] = None


class AnnouncementRequest(BaseModel):
    message: Optional[str] = None   # None/empty = clear announcement


@router.get("/config")
async def get_config(_: dict = Depends(get_current_admin)):
    enabled, message = await admin_state.get_maintenance()
    return {
        "maintenance_mode":    enabled,
        "maintenance_message": message,
        "announcement":        await admin_state.get_announcement(),
    }


@router.post("/config/maintenance")
async def set_maintenance(
    body: MaintenanceRequest,
    admin: dict = Depends(require_role("superadmin")),
    db: AsyncSession = Depends(get_db),
):
    """Toggle maintenance mode for every worker (Redis-backed). Superadmin only."""
    from app.api.admin.audit_writer import audit
    await admin_state.set_maintenance(body.enabled, body.message)
    # Keep this worker's settings mirror consistent for any code still reading settings.*
    settings.MAINTENANCE_MODE = body.enabled
    if body.message:
        settings.MAINTENANCE_MESSAGE = body.message
    logger.warning(f"Admin {admin['email']} set maintenance_mode={body.enabled}")
    await audit(db, admin["email"], "set_maintenance",
                target_type="config", target_id="global",
                details={"enabled": body.enabled, "message": body.message})
    return {"maintenance_mode": body.enabled}


@router.post("/config/announcement")
async def set_announcement(
    body: AnnouncementRequest,
    admin: dict = Depends(require_role("superadmin")),
    db: AsyncSession = Depends(get_db),
):
    """Set or clear a system-wide announcement banner (shown in the app). Superadmin only."""
    from app.api.admin.audit_writer import audit
    message = body.message or None
    await admin_state.set_announcement(message)
    logger.info(f"Admin {admin['email']} set announcement: {message!r}")
    await audit(db, admin["email"], "set_announcement",
                target_type="config", target_id="global",
                details={"announcement": message})
    return {"announcement": message}


@router.get("/config/announcement/public")
async def get_announcement_public():
    """Public endpoint — no auth. Frontend polls this to show announcement banner."""
    return {"announcement": await admin_state.get_announcement()}


# ── Global settings — feature kill-switches / signup gate / AI models ───────────
class GlobalSettingsRequest(BaseModel):
    updates: dict


@router.get("/config/global")
async def get_global_settings(
    _: dict = Depends(require_role("superadmin")),
    db: AsyncSession = Depends(get_db),
):
    from app.services import admin_settings_service as ss
    return {
        "settings":       await ss.get_effective(db),
        "signup_modes":   list(ss.SIGNUP_MODES),
        "model_allowlist": list(ss.MODEL_ALLOWLIST),
    }


@router.post("/config/global")
async def set_global_settings(
    body: GlobalSettingsRequest,
    admin: dict = Depends(require_role("superadmin")),
    db: AsyncSession = Depends(get_db),
):
    from app.services import admin_settings_service as ss
    from app.api.admin.audit_writer import audit
    if not body.updates:
        raise HTTPException(status_code=422, detail="No settings provided")
    try:
        settings = await ss.save(db, body.updates, admin["email"])
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    await audit(db, admin["email"], "set_global_settings",
                target_type="config", target_id="global",
                details={"keys": sorted(body.updates.keys())})
    logger.warning(f"Admin {admin['email']} updated global settings: {sorted(body.updates.keys())}")
    return {"settings": settings}
