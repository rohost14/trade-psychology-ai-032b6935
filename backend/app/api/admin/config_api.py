"""Admin config — maintenance mode, announcement banner."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.admin.deps import get_current_admin
from app.core.config import settings
from app.core.database import get_db
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# In-memory announcement (resets on server restart — good enough for now)
_announcement: Optional[str] = None


class MaintenanceRequest(BaseModel):
    enabled: bool
    message: Optional[str] = None


class AnnouncementRequest(BaseModel):
    message: Optional[str] = None   # None/empty = clear announcement


@router.get("/config")
async def get_config(_: dict = Depends(get_current_admin)):
    return {
        "maintenance_mode":    settings.MAINTENANCE_MODE,
        "maintenance_message": settings.MAINTENANCE_MESSAGE,
        "announcement":        _announcement,
    }


@router.post("/config/maintenance")
async def set_maintenance(
    body: MaintenanceRequest,
    admin: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Toggle maintenance mode. NOTE: This only affects the running process.
    For persistent maintenance mode, set MAINTENANCE_MODE=true in .env and redeploy."""
    from app.api.admin.audit_writer import audit
    settings.MAINTENANCE_MODE = body.enabled
    if body.message:
        settings.MAINTENANCE_MESSAGE = body.message
    logger.warning(f"Admin {admin['email']} set maintenance_mode={body.enabled}")
    await audit(db, admin["email"], "set_maintenance",
                target_type="config", target_id="global",
                details={"enabled": body.enabled, "message": body.message})
    return {"maintenance_mode": settings.MAINTENANCE_MODE}


@router.post("/config/announcement")
async def set_announcement(
    body: AnnouncementRequest,
    admin: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Set or clear a system-wide announcement banner (shown in the app)."""
    from app.api.admin.audit_writer import audit
    global _announcement
    _announcement = body.message or None
    logger.info(f"Admin {admin['email']} set announcement: {_announcement!r}")
    await audit(db, admin["email"], "set_announcement",
                target_type="config", target_id="global",
                details={"announcement": _announcement})
    return {"announcement": _announcement}


@router.get("/config/announcement/public")
async def get_announcement_public():
    """Public endpoint — no auth. Frontend polls this to show announcement banner."""
    return {"announcement": _announcement}
