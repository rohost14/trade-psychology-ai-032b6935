"""
Thin helper — write one row to admin_audit_log.
Call from every admin endpoint that mutates state.
Fire-and-forget: errors are logged but never surface to the caller.
"""
import logging
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.admin_audit_log import AdminAuditLog

logger = logging.getLogger(__name__)


async def audit(
    db: AsyncSession,
    admin_email: str,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Insert one audit row. Never raises — swallows exceptions so callers are unaffected."""
    try:
        row = AdminAuditLog(
            admin_email=admin_email,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=details,
        )
        db.add(row)
        await db.commit()
    except Exception as e:
        logger.error(f"audit_writer failed (action={action}): {e}")
