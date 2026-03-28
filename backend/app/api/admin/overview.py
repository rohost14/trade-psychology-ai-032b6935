"""Admin overview — key metrics dashboard."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from datetime import datetime, timezone, timedelta

from app.core.database import get_db
from app.api.admin.deps import get_current_admin
from app.models.broker_account import BrokerAccount
from app.models.risk_alert import RiskAlert
from app.models.trade import Trade

router = APIRouter()


@router.get("/overview")
async def get_overview(
    db: AsyncSession = Depends(get_db),
    _:  dict         = Depends(get_current_admin),
):
    now        = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start  = today_start - timedelta(days=7)

    # ── User counts ───────────────────────────────────────────────────────
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

    active_7d = (await db.execute(
        select(func.count(func.distinct(Trade.broker_account_id)))
        .where(Trade.created_at >= week_start)
    )).scalar() or 0

    # ── Activity ─────────────────────────────────────────────────────────
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

    # ── User growth — signups per day for last 14 days ───────────────────
    since_14d = today_start - timedelta(days=13)
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

    # ── Online users (in-memory WS manager) ──────────────────────────────
    online_now = 0
    try:
        from app.api.websocket import manager
        online_now = len(manager.active_connections)
    except Exception:
        pass

    # ── Infrastructure health ────────────────────────────────────────────
    health = {"db": "ok", "redis": "unknown"}
    try:
        import redis as redis_lib
        r = redis_lib.from_url(settings.REDIS_URL, decode_responses=True, socket_timeout=2)
        r.ping()
        health["redis"] = "ok"
    except Exception:
        health["redis"] = "error"

    from app.core.config import settings

    return {
        "users": {
            "total":       total_accounts,
            "connected":   connected,
            "new_today":   new_today,
            "active_7d":   active_7d,
            "online_now":  online_now,
        },
        "activity": {
            "total_trades": total_trades,
            "total_alerts": total_alerts,
            "alerts_today": alerts_today,
        },
        "health": health,
        "daily_signups": daily_signups,
    }
