"""Admin user management."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, or_
from typing import Optional
from uuid import UUID

from app.core.database import get_db
from app.api.admin.deps import get_current_admin, require_role
from app.api.admin.audit_writer import audit
from app.models.broker_account import BrokerAccount
from app.models.user import User
from app.models.user_profile import UserProfile
from app.models.trade import Trade
from app.models.risk_alert import RiskAlert
from app.models.admin_audit_log import AdminAuditLog

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
    admin: dict = Depends(require_role("superadmin", "ops", "support")),
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
    success = await whatsapp_service.send_alert(user.guardian_phone, message)

    await audit(db, admin["email"], "send_message",
                target_type="user", target_id=str(account_id),
                details={"preview": message[:120], "to": user.guardian_phone, "success": success})
    return {"success": success, "to": user.guardian_phone}


@router.patch("/users/{account_id}/suspend")
async def toggle_suspend(
    account_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_role("superadmin", "ops")),
):
    account = await db.get(BrokerAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    new_status = "suspended" if account.status == "connected" else "connected"
    action     = "suspend_user" if new_status == "suspended" else "unsuspend_user"
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
    admin: dict = Depends(require_role("superadmin")),
):
    """Soft-delete: revoke token, mark deleted. Does not wipe PII — use /erase for DPDP."""
    account = await db.get(BrokerAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    if account.status in ("deleted", "erased"):
        raise HTTPException(status_code=409, detail="Account already deleted/erased")

    account.status           = "deleted"
    account.token_revoked_at = datetime.now(timezone.utc)
    account.access_token     = None
    await db.commit()

    await audit(db, admin["email"], "delete_user",
                target_type="user", target_id=str(account_id),
                details={"note": "soft-delete: token revoked, status=deleted"})
    return {"status": "deleted", "account_id": str(account_id)}


@router.delete("/users/{account_id}/erase")
async def erase_user_data(
    account_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_role("superadmin")),
):
    """
    DPDP right-to-erasure: permanently wipe all PII from the account.

    Wipes: email, phone, access_token, broker_email, api_key fields.
    Sets status to 'erased'. Writes audit entry with timestamp.
    Irreversible — cannot be undone. Requires superadmin role.
    """
    account = await db.get(BrokerAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    if account.status == "erased":
        raise HTTPException(status_code=409, detail="Account already erased")

    user = await db.get(User, account.user_id) if account.user_id else None

    erased_at = datetime.now(timezone.utc)
    erased_fields = []

    # Wipe broker account PII
    if account.access_token:
        account.access_token = None
        erased_fields.append("access_token")
    if account.broker_email:
        account.broker_email = f"erased_{account_id}@deleted"
        erased_fields.append("broker_email")
    if hasattr(account, "api_secret_enc") and account.api_secret_enc:
        account.api_secret_enc = None
        erased_fields.append("api_secret_enc")
    account.status           = "erased"
    account.token_revoked_at = erased_at

    # Wipe user PII
    if user:
        if user.email:
            user.email = f"erased_{user.id}@deleted"
            erased_fields.append("user.email")
        if user.guardian_phone:
            user.guardian_phone = None
            erased_fields.append("user.guardian_phone")

    await db.commit()

    await audit(db, admin["email"], "erase_user",
                target_type="user", target_id=str(account_id),
                details={"note": "DPDP erasure", "erased_fields": erased_fields,
                         "erased_at": erased_at.isoformat()})
    return {"status": "erased", "account_id": str(account_id), "erased_fields": erased_fields}


@router.get("/users/{account_id}/messages")
async def get_message_history(
    account_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    """Admin→user message history from audit log (last 50 messages)."""
    rows = (await db.execute(
        select(AdminAuditLog)
        .where(
            AdminAuditLog.action == "send_message",
            AdminAuditLog.target_id == str(account_id),
        )
        .order_by(desc(AdminAuditLog.created_at))
        .limit(50)
    )).scalars().all()

    return [
        {
            "id":          str(r.id),
            "admin_email": r.admin_email,
            "preview":     r.details.get("preview") if r.details else None,
            "to":          r.details.get("to") if r.details else None,
            "success":     r.details.get("success") if r.details else None,
            "created_at":  r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
