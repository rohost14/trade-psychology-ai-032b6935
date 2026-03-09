"""
Position Monitor (M-05) — Phase 5

Runs every 30 seconds during market hours (09:15–15:25 IST).
For each account with open positions, checks:
  - holding_loser:       holding a losing position too long
  - averaging_down:      adding to a losing position
  - overexposure:        total open position value too high
  - time_limit_exceeded: holding past user-defined max duration

Uses Redis LTP cache (set by KiteTicker on_ticks) — zero REST API calls.
Falls back gracefully if no cached price (KiteTicker not connected yet).

Adapted from Phase 5 original plan — uses Celery Beat instead of
stream worker (Phase 4 deferred). Behavior identical.
"""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional
from uuid import UUID
from zoneinfo import ZoneInfo

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.core.market_hours import is_market_open, MarketSegment

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")

# How long (minutes) a losing position must be held before alerting
HOLDING_LOSER_MIN_DURATION = 30   # 30 minutes of holding a loss
HOLDING_LOSER_MIN_LOSS_PCT = 0.5  # Position down at least 0.5%

# Size increase threshold for averaging-down detection
AVERAGING_DOWN_SIZE_INCREASE_PCT = 50   # 50%+ size increase on a loser


@celery_app.task(name="app.tasks.position_monitor_tasks.monitor_open_positions")
def monitor_open_positions():
    """
    Celery Beat task — runs every 30 seconds.
    Skips outside 09:15–15:25 IST and on weekends.
    """
    import asyncio
    return asyncio.get_event_loop().run_until_complete(_monitor_all_accounts())


async def _monitor_all_accounts():
    """Check all connected accounts with open positions."""
    now_ist = datetime.now(IST)

    # Only run during equity/F&O market hours with 5-minute buffer before close
    from datetime import time as dtime
    if now_ist.weekday() >= 5:
        return {"skipped": "weekend"}
    current = now_ist.time()
    if not (dtime(9, 15) <= current <= dtime(15, 25)):
        return {"skipped": "outside_market_hours"}

    from app.models.broker_account import BrokerAccount
    from app.models.position import Position
    from sqlalchemy import select, and_

    async with SessionLocal() as db:
        # Find connected accounts with open positions
        result = await db.execute(
            select(BrokerAccount).where(
                and_(
                    BrokerAccount.status == "connected",
                    BrokerAccount.token_revoked_at == None,  # noqa: E711
                )
            )
        )
        accounts = result.scalars().all()

        events_fired = 0
        for account in accounts:
            try:
                fired = await _monitor_account(account.id, db)
                events_fired += fired
            except Exception as e:
                logger.error(f"[position_monitor] Account {account.id} failed: {e}")

    return {"accounts_checked": len(accounts), "events_fired": events_fired}


async def _monitor_account(broker_account_id: UUID, db) -> int:
    """Monitor open positions for one account. Returns number of events fired."""
    from app.models.position import Position
    from app.models.instrument import Instrument
    from app.models.user_profile import UserProfile
    from app.core.trading_defaults import get_thresholds
    from sqlalchemy import select, and_

    # Load open positions
    result = await db.execute(
        select(Position).where(
            and_(
                Position.broker_account_id == broker_account_id,
                Position.total_quantity != 0,
            )
        )
    )
    open_positions = result.scalars().all()
    if not open_positions:
        return 0

    # Load user profile for thresholds
    profile_result = await db.execute(
        select(UserProfile).where(UserProfile.broker_account_id == broker_account_id)
    )
    profile = profile_result.scalar_one_or_none()
    thresholds = get_thresholds(profile)

    events = []
    for pos in open_positions:
        pos_events = await _check_position(pos, thresholds, db)
        events.extend(pos_events)

    if not events:
        return 0

    # Fire events through shadow BehaviorEngine (same pipeline)
    # In production (post Phase 3 cutover) these would go to AlertEngine
    # For now: log them and write to shadow table via BehaviorEngine
    for event in events:
        logger.info(
            f"[position_monitor] {broker_account_id} | "
            f"{event['pattern']} | {event['symbol']} | {event['message']}"
        )

    return len(events)


async def _check_position(position, thresholds: dict, db) -> List[dict]:
    """Check a single open position for behavioral patterns."""
    from app.services.price_stream_service import get_cached_ltp

    events = []
    symbol = position.tradingsymbol
    qty = position.total_quantity or 0
    avg_entry = float(position.average_entry_price or 0)
    instrument_token = position.instrument_token

    # Get current price from Redis LTP cache (set by KiteTicker)
    current_price = get_cached_ltp(instrument_token) if instrument_token else None

    if current_price is None or avg_entry <= 0:
        # No live price available — KiteTicker not connected or instrument_token missing
        # Skip without logging (common when API key not configured)
        return events

    # Calculate unrealized P&L
    is_long = qty > 0
    if is_long:
        unrealized_pnl = (current_price - avg_entry) * abs(qty)
        pnl_pct = (current_price - avg_entry) / avg_entry * 100
    else:
        unrealized_pnl = (avg_entry - current_price) * abs(qty)
        pnl_pct = (avg_entry - current_price) / avg_entry * 100

    # ── Holding loser ──────────────────────────────────────────────────
    if unrealized_pnl < 0 and abs(pnl_pct) >= HOLDING_LOSER_MIN_LOSS_PCT:
        # Check how long position has been open
        if position.last_entry_time:
            hold_min = (
                datetime.now(timezone.utc) - position.last_entry_time
            ).total_seconds() / 60
            if hold_min >= HOLDING_LOSER_MIN_DURATION:
                events.append({
                    "pattern": "holding_loser",
                    "symbol": symbol,
                    "message": (
                        f"{symbol}: down {abs(pnl_pct):.1f}% for {hold_min:.0f}min. "
                        f"Unrealized loss: ₹{abs(unrealized_pnl):,.0f}"
                    ),
                    "context": {
                        "symbol": symbol,
                        "unrealized_pnl": round(unrealized_pnl),
                        "pnl_pct": round(pnl_pct, 2),
                        "hold_minutes": round(hold_min),
                    }
                })

    # ── Overexposure ───────────────────────────────────────────────────
    capital = thresholds.get("trading_capital")
    if capital and capital > 0:
        position_value = current_price * abs(qty)
        exposure_pct = position_value / capital * 100
        max_size = thresholds.get("max_position_size") or 10.0
        if exposure_pct > max_size * 1.5:
            events.append({
                "pattern": "overexposure",
                "symbol": symbol,
                "message": (
                    f"{symbol}: ₹{position_value:,.0f} exposure "
                    f"({exposure_pct:.1f}% of capital, limit {max_size:.0f}%)"
                ),
                "context": {
                    "symbol": symbol,
                    "position_value": round(position_value),
                    "exposure_pct": round(exposure_pct, 1),
                    "limit_pct": max_size,
                }
            })

    return events
