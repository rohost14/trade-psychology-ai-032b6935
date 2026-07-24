"""Admin overview — business health dashboard with funnel, lifecycle, and adoption metrics."""
from collections import Counter
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin.deps import get_current_admin
from app.api.admin.users import _compute_lifecycle
from app.core.config import settings
from app.core.database import get_db
from app.models.broker_account import BrokerAccount
from app.models.risk_alert import RiskAlert
from app.models.trade import Trade
from app.models.user import User
from app.models.user_profile import UserProfile

router = APIRouter()
_IST = ZoneInfo("Asia/Kolkata")


_OVERVIEW_CACHE_KEY = "admin:cache:overview"
_OVERVIEW_TTL = 60  # seconds — admin dashboard tolerates minor staleness


@router.get("/overview")
async def get_overview(
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    from app.api.admin.cache_util import cache_get, cache_set
    cached = await cache_get(_OVERVIEW_CACHE_KEY)
    if cached is not None:
        return cached

    now = datetime.now(timezone.utc)

    # IST midnight so "today" aligns with trading day, not UTC rollover
    ist_today   = datetime.now(_IST).date()
    today_start = datetime.combine(ist_today, time.min, tzinfo=_IST).astimezone(timezone.utc)
    week_start  = today_start - timedelta(days=7)
    dau_since   = now - timedelta(hours=24)
    mau_since   = now - timedelta(days=30)
    since_14d   = today_start - timedelta(days=13)

    # ── User base ──────────────────────────────────────────────────────────
    total_accounts = (await db.execute(
        select(func.count()).select_from(BrokerAccount)
    )).scalar() or 0

    connected = (await db.execute(
        select(func.count()).select_from(BrokerAccount)
        .where(BrokerAccount.status == "connected")
    )).scalar() or 0

    new_today = (await db.execute(
        select(func.count()).select_from(BrokerAccount)
        .where(BrokerAccount.created_at >= today_start)
    )).scalar() or 0

    # WAU: distinct traders in last 7 days by trade execution time
    wau = (await db.execute(
        select(func.count(func.distinct(Trade.broker_account_id)))
        .where(func.coalesce(Trade.order_timestamp, Trade.created_at) >= week_start)
    )).scalar() or 0

    # ── Engagement: DAU / WAU / MAU ────────────────────────────────────────
    # All three use trade execution time (order_timestamp fallback to created_at)
    dau = (await db.execute(
        select(func.count(func.distinct(Trade.broker_account_id)))
        .where(func.coalesce(Trade.order_timestamp, Trade.created_at) >= dau_since)
    )).scalar() or 0

    mau = (await db.execute(
        select(func.count(func.distinct(Trade.broker_account_id)))
        .where(func.coalesce(Trade.order_timestamp, Trade.created_at) >= mau_since)
    )).scalar() or 0

    # Stickiness: DAU/MAU × 100. 0 if no monthly actives.
    dau_mau_ratio = round(dau / mau * 100, 1) if mau > 0 else 0.0

    # ── Activity ───────────────────────────────────────────────────────────
    total_trades = (await db.execute(
        select(func.count()).select_from(Trade)
    )).scalar() or 0

    total_alerts = (await db.execute(
        select(func.count()).select_from(RiskAlert)
    )).scalar() or 0

    alerts_today = (await db.execute(
        select(func.count()).select_from(RiskAlert)
        .where(RiskAlert.created_at >= today_start)
    )).scalar() or 0

    # ── Conversion funnel ─────────────────────────────────────────────────
    # Each stage = distinct accounts that reached that milestone
    has_trades = (await db.execute(
        select(func.count(func.distinct(Trade.broker_account_id)))
    )).scalar() or 0

    has_alerts = (await db.execute(
        select(func.count(func.distinct(RiskAlert.broker_account_id)))
    )).scalar() or 0

    has_acknowledged = (await db.execute(
        select(func.count(func.distinct(RiskAlert.broker_account_id)))
        .where(RiskAlert.acknowledged_at.is_not(None))
    )).scalar() or 0

    # ── Lifecycle distribution ────────────────────────────────────────────
    # Fetch all accounts (id, status, created_at) — two targeted queries,
    # compute in Python. Acceptable for admin-only, on-demand refresh.
    all_acc_rows = (await db.execute(
        select(BrokerAccount.id, BrokerAccount.status, BrokerAccount.created_at)
    )).all()

    lt_rows = (await db.execute(
        select(
            Trade.broker_account_id,
            func.max(func.coalesce(Trade.order_timestamp, Trade.created_at)).label("last_at"),
        ).group_by(Trade.broker_account_id)
    )).all()
    last_trade_map: dict = {str(r.broker_account_id): r.last_at for r in lt_rows}

    dist: Counter = Counter()
    for acc_id, status, created_at in all_acc_rows:
        lc = _compute_lifecycle(status, created_at, last_trade_map.get(str(acc_id)))
        dist[lc] += 1

    lifecycle_dist = {
        "active":       dist["active"],
        "new":          dist["new"],
        "at_risk":      dist["at_risk"],
        "churned":      dist["churned"],
        "inactive":     dist["inactive"],
        "suspended":    dist["suspended"],
        "disconnected": dist["disconnected"],
    }

    # ── Feature adoption ──────────────────────────────────────────────────
    push_enabled_n = (await db.execute(
        select(func.count()).select_from(UserProfile)
        .where(UserProfile.push_enabled.is_(True))
    )).scalar() or 0

    limits_configured_n = (await db.execute(
        select(func.count()).select_from(UserProfile)
        .where(
            UserProfile.daily_trade_limit.is_not(None) |
            UserProfile.daily_loss_limit.is_not(None)
        )
    )).scalar() or 0

    whatsapp_n = (await db.execute(
        select(func.count()).select_from(UserProfile)
        .where(UserProfile.whatsapp_enabled.is_(True))
    )).scalar() or 0

    # guardian_phone IS NOT NULL and non-empty string
    guardian_n = (await db.execute(
        select(func.count()).select_from(User)
        .where(User.guardian_phone.is_not(None), User.guardian_phone != "")
    )).scalar() or 0

    # ── User growth — signups per day for last 14 days ────────────────────
    daily_signups_rows = (await db.execute(
        select(
            func.date_trunc("day", BrokerAccount.created_at).label("day"),
            func.count().label("count"),
        )
        .where(BrokerAccount.created_at >= since_14d)
        .group_by("day")
        .order_by("day")
    )).all()

    daily_signups = [
        {"date": r.day.strftime("%m/%d"), "count": r.count}
        for r in daily_signups_rows
    ]

    # ── Online users ──────────────────────────────────────────────────────
    online_now = 0
    try:
        from app.api.websocket import manager
        online_now = len(manager.active_connections)
    except Exception:
        pass

    # ── Infrastructure health ─────────────────────────────────────────────
    health = {"db": "ok", "redis": "unknown"}
    try:
        import redis as redis_lib
        r = redis_lib.from_url(settings.REDIS_URL, decode_responses=True, socket_timeout=2)
        r.ping()
        health["redis"] = "ok"
    except Exception:
        health["redis"] = "error"

    result = {
        "users": {
            "total":      total_accounts,
            "connected":  connected,
            "new_today":  new_today,
            "online_now": online_now,
        },
        "engagement": {
            "dau":           dau,
            "wau":           wau,
            "mau":           mau,
            "dau_mau_ratio": dau_mau_ratio,
        },
        "activity": {
            "total_trades": total_trades,
            "total_alerts": total_alerts,
            "alerts_today": alerts_today,
        },
        "funnel": {
            "total":           total_accounts,
            "connected":       connected,
            "has_trades":      has_trades,
            "has_alerts":      has_alerts,
            "has_acknowledged": has_acknowledged,
        },
        "lifecycle_dist": lifecycle_dist,
        "adoption": {
            "push_enabled":      push_enabled_n,
            "limits_configured": limits_configured_n,
            "guardian_set":      guardian_n,
            "whatsapp_enabled":  whatsapp_n,
            "total":             total_accounts,
        },
        "health":        health,
        "daily_signups": daily_signups,
    }
    await cache_set(_OVERVIEW_CACHE_KEY, result, _OVERVIEW_TTL)
    return result
