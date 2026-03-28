"""Admin user management."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, or_
from typing import Optional
from uuid import UUID

from app.core.database import get_db
from app.api.admin.deps import get_current_admin
from app.models.broker_account import BrokerAccount
from app.models.user import User
from app.models.user_profile import UserProfile
from app.models.trade import Trade
from app.models.risk_alert import RiskAlert

router = APIRouter()


@router.get("/users")
async def list_users(
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),   # connected | disconnected
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    offset = (page - 1) * limit
    q = select(BrokerAccount, User).outerjoin(User, BrokerAccount.user_id == User.id)

    if status:
        q = q.where(BrokerAccount.status == status)
    if search:
        q = q.where(
            or_(
                BrokerAccount.broker_user_id.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%"),
                User.guardian_phone.ilike(f"%{search}%"),
            )
        )

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
    rows  = (await db.execute(q.order_by(desc(BrokerAccount.created_at)).offset(offset).limit(limit))).all()

    items = []
    for account, user in rows:
        items.append({
            "account_id":     str(account.id),
            "broker_user_id": account.broker_user_id,
            "status":         account.status,
            "broker_email":   account.broker_email,
            "created_at":     account.created_at.isoformat() if account.created_at else None,
            "user": {
                "id":            str(user.id) if user else None,
                "email":         user.email if user else None,
                "guardian_phone": user.guardian_phone if user else None,
            } if user else None,
        })

    return {"total": total, "page": page, "limit": limit, "items": items}


@router.get("/users/{account_id}")
async def get_user_detail(
    account_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    account = await db.get(BrokerAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    user    = await db.get(User, account.user_id) if account.user_id else None
    profile_r = await db.execute(select(UserProfile).where(UserProfile.broker_account_id == account_id))
    profile = profile_r.scalar_one_or_none()

    trade_count = (await db.execute(
        select(func.count()).select_from(Trade).where(Trade.broker_account_id == account_id)
    )).scalar() or 0

    alert_count = (await db.execute(
        select(func.count()).select_from(RiskAlert).where(RiskAlert.broker_account_id == account_id)
    )).scalar() or 0

    recent_alerts = (await db.execute(
        select(RiskAlert)
        .where(RiskAlert.broker_account_id == account_id)
        .order_by(desc(RiskAlert.created_at))
        .limit(10)
    )).scalars().all()

    return {
        "account": {
            "id":             str(account.id),
            "broker_user_id": account.broker_user_id,
            "broker_email":   account.broker_email,
            "status":         account.status,
            "created_at":     account.created_at.isoformat() if account.created_at else None,
        },
        "user": {
            "id":             str(user.id) if user else None,
            "email":          user.email if user else None,
            "guardian_phone": user.guardian_phone if user else None,
        } if user else None,
        "profile": {
            "risk_tolerance":  profile.risk_tolerance if profile else None,
            "email_enabled":   profile.email_enabled if profile else False,
            "trading_style":   profile.trading_style if profile else None,
        } if profile else None,
        "stats": {
            "total_trades": trade_count,
            "total_alerts": alert_count,
        },
        "recent_alerts": [
            {
                "id":           str(a.id),
                "pattern_type": a.pattern_type,
                "severity":     a.severity,
                "created_at":   a.created_at.isoformat() if a.created_at else None,
                "message":      a.message,
            }
            for a in recent_alerts
        ],
    }


@router.post("/users/{account_id}/send-message")
async def send_admin_message(
    account_id: UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(get_current_admin),
):
    """Send a WhatsApp message to a user from admin. Logged with sender info."""
    message = body.get("message", "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="message is required")
    if len(message) > 700:
        raise HTTPException(status_code=400, detail="Message too long (max 700 chars)")

    account = await db.get(BrokerAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    user = await db.get(User, account.user_id) if account.user_id else None
    if not user or not user.guardian_phone:
        raise HTTPException(status_code=400, detail="User has no phone number set")

    from app.services.whatsapp_service import whatsapp_service
    from app.api.admin.audit_writer import audit
    success = await whatsapp_service.send_alert(user.guardian_phone, message)

    await audit(db, admin["email"], "send_message",
                target_type="user", target_id=str(account_id),
                details={"preview": message[:120], "to": user.guardian_phone, "success": success})
    return {"success": success, "to": user.guardian_phone}


@router.patch("/users/{account_id}/suspend")
async def toggle_suspend(
    account_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(get_current_admin),
):
    from app.api.admin.audit_writer import audit
    account = await db.get(BrokerAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    new_status = "suspended" if account.status == "connected" else "connected"
    action = "suspend_user" if new_status == "suspended" else "unsuspend_user"
    account.status = new_status
    await db.commit()
    await audit(db, admin["email"], action,
                target_type="user", target_id=str(account_id),
                details={"new_status": new_status})
    return {"status": new_status}


@router.delete("/users/{account_id}")
async def delete_user(
    account_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(get_current_admin),
):
    """
    Soft-delete a user account (DPDP right-to-erasure).

    Revokes the Zerodha access token, marks account as 'deleted', and
    writes an audit log entry. Does NOT hard-delete DB rows — use a
    scheduled DB job or manual SQL for GDPR/DPDP hard erasure.
    The account will no longer be accessible via any API endpoint.
    """
    from datetime import datetime, timezone
    from app.api.admin.audit_writer import audit

    account = await db.get(BrokerAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    if account.status == "deleted":
        raise HTTPException(status_code=409, detail="Account already deleted")

    account.status = "deleted"
    account.token_revoked_at = datetime.now(timezone.utc)
    account.access_token = None  # Remove stored token immediately
    await db.commit()

    await audit(db, admin["email"], "delete_user",
                target_type="user", target_id=str(account_id),
                details={"note": "soft-delete: token revoked, status=deleted"})
    return {"status": "deleted", "account_id": str(account_id)}
