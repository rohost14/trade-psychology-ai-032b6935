"""Admin audit log — paginated read-only view of all admin actions."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from typing import Optional

from app.core.database import get_db
from app.api.admin.deps import get_current_admin
from app.models.admin_audit_log import AdminAuditLog

router = APIRouter()


def _parse_dt(s: Optional[str], end: bool = False) -> Optional[datetime]:
    """Parse an ISO date or datetime. A bare date as `end` becomes end-of-day."""
    if not s:
        return None
    try:
        if len(s) == 10:  # YYYY-MM-DD
            dt = datetime.fromisoformat(s)
            if end:
                dt = dt.replace(hour=23, minute=59, second=59)
            return dt.replace(tzinfo=timezone.utc)
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _apply_filters(q, admin_email, action, target_type, target_id, date_from, date_to):
    if admin_email:
        q = q.where(AdminAuditLog.admin_email == admin_email)
    if action:
        q = q.where(AdminAuditLog.action == action)
    if target_type:
        q = q.where(AdminAuditLog.target_type == target_type)
    if target_id:
        q = q.where(AdminAuditLog.target_id == target_id)
    df = _parse_dt(date_from)
    dt = _parse_dt(date_to, end=True)
    if df:
        q = q.where(AdminAuditLog.created_at >= df)
    if dt:
        q = q.where(AdminAuditLog.created_at <= dt)
    return q


@router.get("/audit-log")
async def get_audit_log(
    page:        int           = Query(1, ge=1),
    limit:       int           = Query(50, ge=1, le=5000),
    admin_email: Optional[str] = Query(None),
    action:      Optional[str] = Query(None),
    target_type: Optional[str] = Query(None),
    target_id:   Optional[str] = Query(None),
    date_from:   Optional[str] = Query(None, description="ISO date/datetime — inclusive lower bound"),
    date_to:     Optional[str] = Query(None, description="ISO date/datetime — inclusive upper bound"),
    db:          AsyncSession  = Depends(get_db),
    _:           dict          = Depends(get_current_admin),
):
    offset = (page - 1) * limit
    q = _apply_filters(select(AdminAuditLog), admin_email, action, target_type, target_id, date_from, date_to)

    total = (await db.execute(
        select(func.count()).select_from(q.subquery())
    )).scalar() or 0

    rows = (await db.execute(
        q.order_by(desc(AdminAuditLog.created_at)).offset(offset).limit(limit)
    )).scalars().all()

    return {
        "total": total,
        "page": page,
        "items": [
            {
                "id":           str(r.id),
                "admin_email":  r.admin_email,
                "action":       r.action,
                "target_type":  r.target_type,
                "target_id":    r.target_id,
                "details":      r.details,
                "created_at":   r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }
