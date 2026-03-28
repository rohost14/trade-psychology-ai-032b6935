"""Admin audit log — paginated read-only view of all admin actions."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from typing import Optional

from app.core.database import get_db
from app.api.admin.deps import get_current_admin
from app.models.admin_audit_log import AdminAuditLog

router = APIRouter()


@router.get("/audit-log")
async def get_audit_log(
    page:       int            = Query(1, ge=1),
    limit:      int            = Query(50, ge=1, le=200),
    admin_email: Optional[str] = Query(None),
    action:     Optional[str]  = Query(None),
    db:         AsyncSession   = Depends(get_db),
    _:          dict           = Depends(get_current_admin),
):
    offset = (page - 1) * limit
    q = select(AdminAuditLog)
    if admin_email:
        q = q.where(AdminAuditLog.admin_email == admin_email)
    if action:
        q = q.where(AdminAuditLog.action == action)

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
