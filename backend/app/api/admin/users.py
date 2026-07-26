"""Admin user management — list, detail, timeline, limits override, push status, force sync."""
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin.audit_writer import audit
from app.api.admin.deps import get_current_admin, require_role
from app.core.config import settings
from app.core.database import get_db
from app.models.admin_audit_log import AdminAuditLog
from app.models.broker_account import BrokerAccount
from app.models.push_subscription import PushSubscription
from app.models.risk_alert import RiskAlert
from app.models.trade import Trade
from app.models.user import User
from app.models.user_profile import UserProfile

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _compute_lifecycle(
    status: str,
    created_at: Optional[datetime],
    last_trade_at: Optional[datetime],
) -> str:
    if status in ("suspended", "erased", "deleted"):
        return status
    if status == "disconnected":
        return "disconnected"

    now = datetime.now(timezone.utc)

    if last_trade_at is None:
        # Never traded: new if < 7 days old, otherwise stalled/inactive
        if created_at and (now - created_at).days <= 7:
            return "new"
        return "inactive"

    # Has trades — classification based on recency of last trade only
    lt = last_trade_at if last_trade_at.tzinfo else last_trade_at.replace(tzinfo=timezone.utc)
    days_since = (now - lt).days

    if days_since > 30:
        return "churned"
    if days_since > 14:
        return "at_risk"
    return "active"


# ─────────────────────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────────────────────

class LimitsUpdate(BaseModel):
    daily_trade_limit:  Optional[int]   = Field(None, ge=1, le=500)
    daily_loss_limit:   Optional[float] = Field(None, ge=0)
    cooldown_after_loss: Optional[int]  = Field(None, ge=0, le=1440)
    max_position_size:  Optional[float] = Field(None, ge=0.1, le=100)


# ─────────────────────────────────────────────────────────────────────────────
# User List
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/users")
async def list_users(
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    lifecycle: Optional[str] = Query(None),   # new|active|at_risk|churned|inactive
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
    rows  = (await db.execute(
        q.order_by(desc(BrokerAccount.created_at)).offset(offset).limit(limit)
    )).all()

    # Batch fetch last trade times — single query regardless of page size
    account_ids = [a.id for a, _ in rows]
    last_trade_map: dict = {}
    if account_ids:
        lt_rows = (await db.execute(
            select(
                Trade.broker_account_id,
                func.max(
                    func.coalesce(Trade.order_timestamp, Trade.created_at)
                ).label("last_at"),
            )
            .where(Trade.broker_account_id.in_(account_ids))
            .group_by(Trade.broker_account_id)
        )).all()
        last_trade_map = {str(r.broker_account_id): r.last_at for r in lt_rows}

    items = []
    for account, user in rows:
        last_at = last_trade_map.get(str(account.id))
        lc = _compute_lifecycle(account.status, account.created_at, last_at)

        # Post-filter by lifecycle if requested (done in Python since lifecycle is computed)
        if lifecycle and lc != lifecycle:
            continue

        items.append({
            "account_id":     str(account.id),
            "broker_user_id": account.broker_user_id,
            "status":         account.status,
            "broker_email":   account.broker_email,
            "created_at":     account.created_at.isoformat() if account.created_at else None,
            "last_trade_at":  last_at.isoformat() if last_at else None,
            "lifecycle":      lc,
            "user": {
                "id":             str(user.id) if user else None,
                "email":          user.email if user else None,
                "guardian_phone": user.guardian_phone if user else None,
            } if user else None,
        })

    return {"total": total, "page": page, "limit": limit, "items": items}


# ─────────────────────────────────────────────────────────────────────────────
# User Detail
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/users/{account_id}")
async def get_user_detail(
    account_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    account = await db.get(BrokerAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    user = await db.get(User, account.user_id) if account.user_id else None

    profile_r = await db.execute(
        select(UserProfile).where(UserProfile.broker_account_id == account_id)
    )
    profile = profile_r.scalar_one_or_none()

    # Counts
    trade_count = (await db.execute(
        select(func.count()).select_from(Trade).where(Trade.broker_account_id == account_id)
    )).scalar() or 0

    alert_count = (await db.execute(
        select(func.count()).select_from(RiskAlert).where(RiskAlert.broker_account_id == account_id)
    )).scalar() or 0

    push_count = (await db.execute(
        select(func.count()).select_from(PushSubscription)
        .where(PushSubscription.broker_account_id == account_id)
    )).scalar() or 0

    # Last trade timestamp
    last_trade_at_r = (await db.execute(
        select(func.max(func.coalesce(Trade.order_timestamp, Trade.created_at)))
        .where(Trade.broker_account_id == account_id)
    )).scalar()

    lifecycle = _compute_lifecycle(account.status, account.created_at, last_trade_at_r)

    recent_alerts = (await db.execute(
        select(RiskAlert)
        .where(RiskAlert.broker_account_id == account_id)
        .order_by(desc(RiskAlert.detected_at))
        .limit(10)
    )).scalars().all()

    return {
        "account": {
            "id":             str(account.id),
            "broker_user_id": account.broker_user_id,
            "broker_email":   account.broker_email,
            "status":         account.status,
            "sync_status":    account.sync_status,
            "last_sync_at":   account.last_sync_at.isoformat() if account.last_sync_at else None,
            "connected_at":   account.connected_at.isoformat() if account.connected_at else None,
            "created_at":     account.created_at.isoformat() if account.created_at else None,
        },
        "user": {
            "id":               str(user.id) if user else None,
            "email":            user.email if user else None,
            "display_name":     user.display_name if user else None,
            "guardian_phone":   user.guardian_phone if user else None,
            "guardian_name":    user.guardian_name if user else None,
            "guardian_confirmed": user.guardian_confirmed if user else False,
        } if user else None,
        "profile": {
            "trading_style":      profile.trading_style if profile else None,
            "experience_level":   profile.experience_level if profile else None,
            "risk_tolerance":     profile.risk_tolerance if profile else None,
            "trading_capital":    profile.trading_capital if profile else None,
            "daily_trade_limit":  profile.daily_trade_limit if profile else None,
            "daily_loss_limit":   profile.daily_loss_limit if profile else None,
            "max_position_size":  profile.max_position_size if profile else None,
            "cooldown_after_loss": profile.cooldown_after_loss if profile else None,
            "push_enabled":       profile.push_enabled if profile else False,
            "whatsapp_enabled":   profile.whatsapp_enabled if profile else False,
            "email_enabled":      profile.email_enabled if profile else False,
            "alert_sensitivity":  profile.alert_sensitivity if profile else None,
            "onboarding_completed": profile.onboarding_completed if profile else False,
        } if profile else None,
        "stats": {
            "total_trades":          trade_count,
            "total_alerts":          alert_count,
            "push_subscription_count": push_count,
            "last_trade_at":         last_trade_at_r.isoformat() if last_trade_at_r else None,
        },
        "lifecycle": lifecycle,
        "recent_alerts": [
            {
                "id":           str(a.id),
                "pattern_type": a.pattern_type,
                "severity":     a.severity,
                "message":      a.message,
                "detected_at":  a.detected_at.isoformat() if a.detected_at else None,
                "acknowledged": a.acknowledged_at is not None,
            }
            for a in recent_alerts
        ],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Messaging
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/users/{account_id}/send-message")
async def send_admin_message(
    account_id: UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_role("superadmin", "ops", "support")),
):
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
    success = await whatsapp_service.send_message(user.guardian_phone, message)

    await audit(db, admin["email"], "send_message",
                target_type="user", target_id=str(account_id),
                details={"preview": message[:120], "to": user.guardian_phone, "success": success})
    return {"success": success, "to": user.guardian_phone}


@router.get("/users/{account_id}/messages")
async def get_message_history(
    account_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
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


# ─────────────────────────────────────────────────────────────────────────────
# Account State Changes
# ─────────────────────────────────────────────────────────────────────────────

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
    """DPDP right-to-erasure: permanently wipe all PII. Irreversible."""
    account = await db.get(BrokerAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    if account.status == "erased":
        raise HTTPException(status_code=409, detail="Account already erased")

    user = await db.get(User, account.user_id) if account.user_id else None

    erased_at     = datetime.now(timezone.utc)
    erased_fields = []

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


# ─────────────────────────────────────────────────────────────────────────────
# Timeline
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/users/{account_id}/timeline")
async def get_user_timeline(
    account_id: UUID,
    limit: int = Query(80, ge=20, le=200),
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    """Merged chronological event feed: trades + alerts, sorted newest-first."""
    account = await db.get(BrokerAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    trades = (await db.execute(
        select(Trade)
        .where(Trade.broker_account_id == account_id)
        .order_by(desc(func.coalesce(Trade.order_timestamp, Trade.created_at)))
        .limit(60)
    )).scalars().all()

    alerts = (await db.execute(
        select(RiskAlert)
        .where(RiskAlert.broker_account_id == account_id)
        .order_by(desc(func.coalesce(RiskAlert.detected_at, RiskAlert.created_at)))
        .limit(60)
    )).scalars().all()

    events = []

    for t in trades:
        ts = t.order_timestamp or t.created_at
        events.append({
            "type":       "trade",
            "time":       ts.isoformat() if ts else None,
            "id":         str(t.id),
            "symbol":     t.tradingsymbol,
            "direction":  t.transaction_type,   # BUY / SELL
            "product":    t.product,
            "status":     t.status,
            "quantity":   t.quantity,
            "price":      float(t.average_price) if t.average_price else None,
            "exchange":   t.exchange,
        })

    for a in alerts:
        ts = a.detected_at or a.created_at
        events.append({
            "type":         "alert",
            "time":         ts.isoformat() if ts else None,
            "id":           str(a.id),
            "pattern":      a.pattern_type,
            "severity":     a.severity,
            "message":      a.message,
            "acknowledged": a.acknowledged_at is not None,
        })

    # Merge sort by time descending; events without a time sink to bottom
    events.sort(key=lambda e: e["time"] or "0000", reverse=True)

    return {"events": events[:limit], "total": len(events)}


# ─────────────────────────────────────────────────────────────────────────────
# Force Sync
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/users/{account_id}/force-sync")
async def force_sync_user(
    account_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_role("superadmin", "ops")),
):
    """Trigger an immediate Zerodha trade sync for one account. Runs inline — may take 5–15s."""
    account = await db.get(BrokerAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    if account.status not in ("connected",):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot sync account in '{account.status}' state. Only 'connected' accounts can sync.",
        )
    if not account.access_token:
        raise HTTPException(
            status_code=400,
            detail="Account has no access token — user must reconnect Zerodha.",
        )

    from app.services.trade_sync_service import TradeSyncService
    try:
        result = await TradeSyncService.sync_trades_for_broker_account(account_id, db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)[:300]}")

    await audit(db, admin["email"], "force_sync",
                target_type="user", target_id=str(account_id),
                details={
                    "trades_synced":    result.get("trades_synced", 0),
                    "positions_synced": result.get("positions_synced", 0),
                    "errors":           result.get("errors", [])[:5],
                })

    return {
        "success":          result.get("success", True),
        "trades_synced":    result.get("trades_synced", 0),
        "positions_synced": result.get("positions_synced", 0),
        "orders_synced":    result.get("orders_synced", 0),
        "errors":           result.get("errors", []),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Limits Override
# ─────────────────────────────────────────────────────────────────────────────

@router.patch("/users/{account_id}/limits")
async def update_user_limits(
    account_id: UUID,
    body: LimitsUpdate,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_role("superadmin", "ops")),
):
    """Override user's trading plan limits. Takes effect on the next trade detection cycle."""
    account = await db.get(BrokerAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    profile_r = await db.execute(
        select(UserProfile).where(UserProfile.broker_account_id == account_id)
    )
    profile = profile_r.scalar_one_or_none()

    if not profile:
        profile = UserProfile(broker_account_id=account_id)
        db.add(profile)

    changed: dict = {}
    if body.daily_trade_limit is not None:
        changed["daily_trade_limit"] = (profile.daily_trade_limit, body.daily_trade_limit)
        profile.daily_trade_limit = body.daily_trade_limit
    if body.daily_loss_limit is not None:
        changed["daily_loss_limit"] = (profile.daily_loss_limit, body.daily_loss_limit)
        profile.daily_loss_limit = body.daily_loss_limit
    if body.cooldown_after_loss is not None:
        changed["cooldown_after_loss"] = (profile.cooldown_after_loss, body.cooldown_after_loss)
        profile.cooldown_after_loss = body.cooldown_after_loss
    if body.max_position_size is not None:
        changed["max_position_size"] = (profile.max_position_size, body.max_position_size)
        profile.max_position_size = body.max_position_size

    if not changed:
        raise HTTPException(status_code=400, detail="No limits provided to update")

    await db.commit()
    await db.refresh(profile)

    await audit(db, admin["email"], "update_limits",
                target_type="user", target_id=str(account_id),
                details={"changes": {k: {"from": v[0], "to": v[1]} for k, v in changed.items()}})

    return {
        "daily_trade_limit":  profile.daily_trade_limit,
        "daily_loss_limit":   profile.daily_loss_limit,
        "cooldown_after_loss": profile.cooldown_after_loss,
        "max_position_size":  profile.max_position_size,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Push Notifications
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/users/{account_id}/push-status")
async def get_push_status(
    account_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    """Return push subscription details and delivery stats for a user."""
    account = await db.get(BrokerAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    subs = (await db.execute(
        select(PushSubscription)
        .where(PushSubscription.broker_account_id == account_id)
        .order_by(desc(PushSubscription.created_at))
    )).scalars().all()

    # Last successful push delivery
    last_push_r = (await db.execute(
        select(RiskAlert.delivered_push_at, RiskAlert.pattern_type, RiskAlert.severity)
        .where(
            RiskAlert.broker_account_id == account_id,
            RiskAlert.delivered_push_at.is_not(None),
        )
        .order_by(desc(RiskAlert.delivered_push_at))
        .limit(1)
    )).first()

    # Total pushes ever sent
    total_pushed = (await db.execute(
        select(func.count())
        .select_from(RiskAlert)
        .where(
            RiskAlert.broker_account_id == account_id,
            RiskAlert.delivered_push_at.is_not(None),
        )
    )).scalar() or 0

    return {
        "subscription_count": len(subs),
        "subscriptions": [
            {
                "id":          str(s.id),
                "device_type": s.device_type or "unknown",
                "user_agent":  (s.user_agent or "")[:80],
                "created_at":  s.created_at.isoformat() if s.created_at else None,
                # Show only last 20 chars of endpoint to avoid leaking full FCM URL
                "endpoint_tail": s.endpoint[-24:] if s.endpoint else None,
            }
            for s in subs
        ],
        "last_push_at":      last_push_r.delivered_push_at.isoformat() if last_push_r else None,
        "last_push_pattern": last_push_r.pattern_type if last_push_r else None,
        "total_pushes_sent": total_pushed,
    }


@router.post("/users/{account_id}/test-push")
async def send_test_push(
    account_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_role("superadmin", "ops")),
):
    """Send a test push notification to verify the subscription is live."""
    account = await db.get(BrokerAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    # Confirm at least one subscription exists
    sub_count = (await db.execute(
        select(func.count()).select_from(PushSubscription)
        .where(PushSubscription.broker_account_id == account_id)
    )).scalar() or 0

    if sub_count == 0:
        raise HTTPException(status_code=400, detail="No push subscriptions on file for this user")

    from app.services.push_notification_service import push_service
    result = await push_service.send_notification(
        broker_account_id=account_id,
        title="Admin Test Push",
        body="This is a test notification from TradeMentor admin. If you see this, push is working.",
        db=db,
        data={"type": "admin_test", "sent_by": admin["email"]},
        severity="info",
        tag="admin_test",
    )

    await audit(db, admin["email"], "send_test_push",
                target_type="user", target_id=str(account_id),
                details={"subscriptions_targeted": sub_count, "result": str(result)[:200]})

    return {"success": True, "subscriptions_targeted": sub_count, "result": result}


# ─────────────────────────────────────────────────────────────────────────────
# Rate Limit Reset
# ─────────────────────────────────────────────────────────────────────────────

@router.delete("/users/{account_id}/rate-limit")
async def clear_rate_limits(
    account_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_role("superadmin", "ops")),
):
    """Clear all Redis rate-limit keys for this account (format: rl:{account_id}:*)."""
    try:
        import redis as redis_lib
        r = redis_lib.from_url(settings.REDIS_URL, decode_responses=True, socket_timeout=3)
        r.ping()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Redis unavailable: {str(e)[:80]}")

    pattern  = f"rl:{account_id}:*"
    keys     = list(r.scan_iter(pattern, count=200))
    cleared  = r.delete(*keys) if keys else 0

    await audit(db, admin["email"], "clear_rate_limit",
                target_type="user", target_id=str(account_id),
                details={"pattern": pattern, "keys_cleared": cleared})

    return {"keys_cleared": cleared, "pattern": pattern}


# ─────────────────────────────────────────────────────────────────────────────
# Read-only impersonation ("view as user")
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/users/{account_id}/impersonate")
async def impersonate_user(
    account_id: UUID,
    admin: dict = Depends(require_role("superadmin", "ops")),
    db: AsyncSession = Depends(get_db),
):
    """Mint a short-lived, READ-ONLY user token so an admin can see exactly what a user
    sees. The token is signed with the normal user SECRET_KEY and carries `imp=True`;
    a middleware in main.py rejects every non-GET request bearing an impersonation token,
    so it can never mutate the account. Superadmin/ops only. Audited."""
    from datetime import timedelta
    from jose import jwt

    account = (await db.execute(
        select(BrokerAccount).where(BrokerAccount.id == account_id)
    )).scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    user = (await db.execute(
        select(User).where(User.id == account.user_id)
    )).scalar_one_or_none()

    ttl_seconds = 30 * 60
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub":    str(account.user_id),
            "bid":    str(account.id),
            "imp":    True,
            "imp_by": admin["email"],
            "iat":    now,
            "exp":    now + timedelta(seconds=ttl_seconds),
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )

    display = (user.email if user else None) or account.broker_email or account.broker_user_id or "user"
    await audit(db, admin["email"], "impersonate_user",
                target_type="user", target_id=str(account_id),
                details={"display": display, "ttl_seconds": ttl_seconds})

    return {
        "token":       token,
        "expires_in":  ttl_seconds,
        "display":     display,
        "account_id":  str(account_id),
    }
