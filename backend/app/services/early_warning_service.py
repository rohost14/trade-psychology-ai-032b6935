"""
Early Warning Service

Plan-based push warnings — fires when session approaches user's configured limits.
Covers gaps the behavior engine doesn't: P&L limit proximity and trade count limit.

- P&L at 70% of daily loss limit → "₹X remaining in your plan"
- Trade count at 80% of daily limit → "N trades left in your plan"

NOT included (removed to prevent spam):
- 2 consecutive losses: behavior engine fires consecutive_loss_streak at 3 anyway.
  Having both causes 2 pushes within seconds for the same situation.

These do NOT create RiskAlert records (keeps alerts list clean).
Redis dedup: once per day per warning type.
"""

import logging
from datetime import datetime, date, time, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.completed_trade import CompletedTrade
from app.models.user_profile import UserProfile

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")


async def check_early_warnings(
    broker_account_id: UUID,
    db: AsyncSession,
    redis_client=None,
) -> list[dict]:
    """
    Returns list of push notification payloads to send as early warnings.
    Caller is responsible for actually pushing them via push_service.
    """
    try:
        return await _check(broker_account_id, db, redis_client)
    except Exception as e:
        logger.warning(f"[EarlyWarning] check failed for {broker_account_id}: {e}")
        return []


async def _check(
    broker_account_id: UUID,
    db: AsyncSession,
    redis_client,
) -> list[dict]:
    today_ist = datetime.now(IST).date()
    # Correct IST→UTC: midnight IST = previous day 18:30 UTC
    today_start_utc = datetime.combine(today_ist, time.min, tzinfo=IST).astimezone(timezone.utc)

    # Fetch profile limits
    profile_result = await db.execute(
        select(UserProfile).where(UserProfile.broker_account_id == broker_account_id)
    )
    profile = profile_result.scalar_one_or_none()

    # Fetch today's completed trades — no limit so P&L sum is always accurate
    trades_result = await db.execute(
        select(CompletedTrade)
        .where(
            and_(
                CompletedTrade.broker_account_id == broker_account_id,
                CompletedTrade.exit_time >= today_start_utc,
            )
        )
    )
    trades_today = trades_result.scalars().all()

    if not trades_today:
        return []

    warnings = []
    dedup_prefix = f"ew:{broker_account_id}:{today_ist.isoformat()}"

    # ── 1. P&L at 70% of daily loss limit ────────────────────────────────────
    if profile and profile.daily_loss_limit:
        session_pnl = sum(float(t.realized_pnl or 0) for t in trades_today)
        limit = float(profile.daily_loss_limit)
        used_pct = abs(session_pnl) / limit if session_pnl < 0 and limit > 0 else 0.0

        if used_pct >= 0.70:
            key = f"{dedup_prefix}:pnl70"
            if _not_deduped(redis_client, key, ttl=86400):  # once per day
                remaining = max(0.0, limit - abs(session_pnl))
                warnings.append({
                    "title": "TradeMentor — Loss Limit Warning",
                    "body": f"70% of your daily limit used. ₹{remaining:,.0f} remaining — each trade now costs more than money.",
                    "data": {"action": "open_dashboard", "type": "early_warning"},
                    "severity": "caution",
                    "tag": "ew-pnl70",
                })

    # ── 2. Trade count at 80% of daily limit ─────────────────────────────────
    if profile and profile.daily_trade_limit:
        count = len(trades_today)
        limit = profile.daily_trade_limit
        if limit >= 5 and count >= int(0.80 * limit) and count < limit:
            key = f"{dedup_prefix}:cnt80"
            if _not_deduped(redis_client, key, ttl=86400):  # once per day
                remaining = limit - count
                warnings.append({
                    "title": "TradeMentor — Trade Count",
                    "body": f"{count}/{limit} trades today. {remaining} left in your plan — make them deliberate.",
                    "data": {"action": "open_dashboard", "type": "early_warning"},
                    "severity": "info",
                    "tag": "ew-cnt80",
                })

    return warnings


def _not_deduped(redis_client, key: str, ttl: int) -> bool:
    """Returns True (and sets key) if this warning hasn't fired yet."""
    if redis_client is None:
        return True  # No Redis — always fire (better than silent miss)
    try:
        return bool(redis_client.set(key, "1", nx=True, ex=ttl))
    except Exception:
        return True  # Redis error — fire warning rather than suppress
