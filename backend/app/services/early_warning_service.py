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
from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core import session_facts
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

    # Fetch profile limits
    profile_result = await db.execute(
        select(UserProfile).where(UserProfile.broker_account_id == broker_account_id)
    )
    profile = profile_result.scalar_one_or_none()

    # This session's trades and facts, from the one canonical definition. These
    # warnings are PUSHED to the trader and compared against their declared daily
    # limit, so the P&L quoted here has to be the same number the dashboard and
    # the alerts are working from - it used to be summed here from its own query.
    trades_today = await session_facts.load_session_trades(
        db, broker_account_id, today_ist
    )
    facts = session_facts.derive(trades_today)

    if not trades_today:
        return []

    warnings = []
    dedup_prefix = f"ew:{broker_account_id}:{today_ist.isoformat()}"

    # ── 1. P&L at 70% of daily loss limit ────────────────────────────────────
    if profile and profile.daily_loss_limit:
        session_pnl = float(facts.pnl)
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
        count = facts.trades
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
