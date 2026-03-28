"""
Position Monitor (M-05) — Event-Driven (Phase 6 upgrade)

Tasks are triggered by trade fills, not a recurring beat:

  check_position_overexposure(account_id, symbol)
      Called immediately after every COMPLETE fill via trade_tasks.py.
      Checks if the filled position now exceeds the account's capital limit.
      Zero REST API calls — uses Redis LTP cache from KiteTicker.

  check_holding_loser_scheduled(account_id, check_number)
      Scheduled 30 min after a BUY fill that opens/increases a position.
      Self-reschedules up to MAX_HOLDING_LOSER_CHECKS (= 4 hours of coverage).
      Stops automatically when the position closes (no open positions found).

The legacy monitor_open_positions beat task is kept in this file for
reference but is no longer registered in celery_app.py beat schedule.
"""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional
from uuid import UUID
from zoneinfo import ZoneInfo

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.market_hours import is_market_open, MarketSegment

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")


def _get_redis():
    import redis as redis_lib
    return redis_lib.from_url(settings.REDIS_URL, decode_responses=True)

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
    return asyncio.run(_monitor_all_accounts())


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

    async def _monitor_safe(account):
        async with SessionLocal() as db:
            return await _monitor_account(account.id, db)

    batch_size = 20
    events_fired = 0
    for i in range(0, len(accounts), batch_size):
        batch = accounts[i:i + batch_size]
        results = await asyncio.gather(*[_monitor_safe(a) for a in batch], return_exceptions=True)
        for r in results:
            if isinstance(r, Exception):
                logger.error(f"[position_monitor] Batch account failed: {r}")
            elif isinstance(r, int):
                events_fired += r

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


# ---------------------------------------------------------------------------
# Event-driven tasks (triggered by trade fills, not a beat schedule)
# ---------------------------------------------------------------------------

# How many 30-min cycles to reschedule after a BUY fill (= 4 hours coverage)
MAX_HOLDING_LOSER_CHECKS = 8


@celery_app.task(name="app.tasks.position_monitor_tasks.check_holding_loser_scheduled")
def check_holding_loser_scheduled(broker_account_id: str, check_number: int = 0):
    """
    Deferred holding-loser check.  Scheduled 30 min after a BUY fill
    (open or increase).  Self-reschedules up to MAX_HOLDING_LOSER_CHECKS
    if the position is still open.  Stops automatically on position close.
    """
    import asyncio
    return asyncio.run(
        _holding_loser_task(broker_account_id, check_number)
    )


async def _holding_loser_task(broker_account_id: str, check_number: int) -> dict:
    now_ist = datetime.now(IST)
    from datetime import time as dtime
    if now_ist.weekday() >= 5 or not (dtime(9, 15) <= now_ist.time() <= dtime(15, 25)):
        return {"skipped": "outside_market_hours"}

    from app.models.position import Position
    from app.models.user_profile import UserProfile
    from app.core.trading_defaults import get_thresholds
    from app.services.price_stream_service import get_cached_ltp
    from sqlalchemy import select, and_

    async with SessionLocal() as db:
        pos_result = await db.execute(
            select(Position).where(
                and_(
                    Position.broker_account_id == UUID(broker_account_id),
                    Position.total_quantity != 0,
                )
            )
        )
        open_positions = pos_result.scalars().all()

        if not open_positions:
            # Chain ends — no open positions, release the chain key
            _get_redis().delete(f"holding_loser_chain:{broker_account_id}")
            return {"skipped": "no_open_positions", "check_number": check_number}

        profile_result = await db.execute(
            select(UserProfile).where(UserProfile.broker_account_id == UUID(broker_account_id))
        )
        profile = profile_result.scalar_one_or_none()
        thresholds = get_thresholds(profile)

    alerts_fired = 0
    for pos in open_positions:
        current_price = get_cached_ltp(pos.instrument_token) if pos.instrument_token else None
        if current_price is None:
            continue
        avg_entry = float(pos.average_entry_price or 0)
        qty = pos.total_quantity or 0
        if avg_entry <= 0 or qty == 0:
            continue

        is_long = qty > 0
        pnl_pct = ((current_price - avg_entry) / avg_entry * 100) if is_long \
            else ((avg_entry - current_price) / avg_entry * 100)
        unrealized_pnl = ((current_price - avg_entry) * abs(qty)) if is_long \
            else ((avg_entry - current_price) * abs(qty))

        if unrealized_pnl < 0 and abs(pnl_pct) >= HOLDING_LOSER_MIN_LOSS_PCT and pos.last_entry_time:
            hold_min = (
                datetime.now(timezone.utc) - pos.last_entry_time
            ).total_seconds() / 60
            if hold_min >= HOLDING_LOSER_MIN_DURATION:
                async with SessionLocal() as alert_db:
                    fired = await _fire_position_alert(
                        broker_account_id=broker_account_id,
                        pattern_type="holding_loser",
                        severity="caution",
                        message=(
                            f"{pos.tradingsymbol}: down {abs(pnl_pct):.1f}% "
                            f"for {hold_min:.0f}min. "
                            f"Unrealized loss: ₹{abs(unrealized_pnl):,.0f}"
                        ),
                        details={
                            "symbol": pos.tradingsymbol,
                            "pnl_pct": round(pnl_pct, 2),
                            "hold_minutes": round(hold_min),
                            "unrealized_pnl": round(unrealized_pnl),
                        },
                        db=alert_db,
                    )
                    if fired:
                        alerts_fired += 1

    # Reschedule if still under the cap; renew the chain key TTL
    if check_number < MAX_HOLDING_LOSER_CHECKS:
        _get_redis().set(
            f"holding_loser_chain:{broker_account_id}", check_number + 1, ex=1900
        )
        check_holding_loser_scheduled.apply_async(
            args=[broker_account_id, check_number + 1],
            countdown=1800,  # 30 minutes
        )
    else:
        # Hit the cap — release chain key so a new fill can start a fresh chain
        _get_redis().delete(f"holding_loser_chain:{broker_account_id}")

    return {
        "check_number": check_number,
        "positions_checked": len(open_positions),
        "alerts_fired": alerts_fired,
    }


@celery_app.task(name="app.tasks.position_monitor_tasks.check_position_overexposure")
def check_position_overexposure(broker_account_id: str, tradingsymbol: str):
    """
    Immediate overexposure check after a fill.
    Uses Redis LTP cache — zero REST API calls.
    """
    import asyncio
    return asyncio.run(
        _overexposure_task(broker_account_id, tradingsymbol)
    )


async def _overexposure_task(broker_account_id: str, tradingsymbol: str) -> dict:
    from app.models.position import Position
    from app.models.user_profile import UserProfile
    from app.core.trading_defaults import get_thresholds
    from app.services.price_stream_service import get_cached_ltp
    from sqlalchemy import select, and_

    async with SessionLocal() as db:
        pos_result = await db.execute(
            select(Position).where(
                and_(
                    Position.broker_account_id == UUID(broker_account_id),
                    Position.tradingsymbol == tradingsymbol,
                    Position.total_quantity != 0,
                )
            )
        )
        pos = pos_result.scalar_one_or_none()
        if not pos:
            return {"skipped": "no_open_position"}

        profile_result = await db.execute(
            select(UserProfile).where(UserProfile.broker_account_id == UUID(broker_account_id))
        )
        profile = profile_result.scalar_one_or_none()
        thresholds = get_thresholds(profile)

    current_price = get_cached_ltp(pos.instrument_token) if pos.instrument_token else None
    if current_price is None:
        return {"skipped": "no_ltp"}

    capital = thresholds.get("trading_capital")
    qty = pos.total_quantity or 0
    if not capital or capital <= 0 or qty == 0:
        return {"skipped": "no_capital"}

    position_value = current_price * abs(qty)
    exposure_pct = position_value / capital * 100
    max_size = thresholds.get("max_position_size") or 10.0

    if exposure_pct > max_size * 1.5:
        # danger if >2x limit (critical overexposure), caution if 1.5-2x
        severity = "danger" if exposure_pct > max_size * 2 else "caution"
        async with SessionLocal() as alert_db:
            await _fire_position_alert(
                broker_account_id=broker_account_id,
                pattern_type="overexposure",
                severity=severity,
                message=(
                    f"{tradingsymbol}: ₹{position_value:,.0f} exposure "
                    f"({exposure_pct:.1f}% of capital, limit {max_size:.0f}%)"
                ),
                details={
                    "symbol": tradingsymbol,
                    "position_value": round(position_value),
                    "exposure_pct": round(exposure_pct, 1),
                    "limit_pct": max_size,
                },
                db=alert_db,
            )
        return {"symbol": tradingsymbol, "exposure_pct": round(exposure_pct, 1), "alerted": True}

    return {"symbol": tradingsymbol, "exposure_pct": round(exposure_pct, 1), "alerted": False}


async def _fire_position_alert(
    broker_account_id: str,
    pattern_type: str,
    severity: str,
    message: str,
    details: dict,
    db,
) -> bool:
    """
    Create a RiskAlert for a position-based pattern and push to frontend.

    Deduplicates against the last 30 minutes so the same pattern doesn't
    spam the user every time the holding-loser check runs.

    Returns True if a new alert was created, False if suppressed by dedup.
    """
    from app.models.risk_alert import RiskAlert
    from app.core.event_bus import publish_event
    from sqlalchemy import select, and_

    # 30-min dedup window (matches the check_holding_loser_scheduled interval)
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)
    existing = await db.execute(
        select(RiskAlert).where(
            and_(
                RiskAlert.broker_account_id == UUID(broker_account_id),
                RiskAlert.pattern_type == pattern_type,
                RiskAlert.detected_at >= cutoff,
            )
        )
    )
    if existing.scalar_one_or_none():
        logger.debug(
            f"[position_monitor] {pattern_type} for {broker_account_id[:8]} "
            f"suppressed — already alerted in last 30 min"
        )
        return False

    alert = RiskAlert(
        broker_account_id=UUID(broker_account_id),
        pattern_type=pattern_type,
        severity=severity,
        message=message,
        details=details,
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)

    # Push to frontend immediately via WebSocket
    publish_event(broker_account_id, "alert_update", {
        "count": 1,
        "has_danger": severity == "danger",
        "behavior_state": None,
    })

    logger.info(
        f"[position_monitor] {pattern_type} alert fired | "
        f"{broker_account_id[:8]} | severity={severity} | {message[:80]}"
    )

    # WhatsApp + push for danger-level alerts (e.g. critical overexposure)
    if severity == "danger":
        from app.tasks.trade_tasks import send_danger_alert
        send_danger_alert.delay(broker_account_id, str(alert.id))

    return True
