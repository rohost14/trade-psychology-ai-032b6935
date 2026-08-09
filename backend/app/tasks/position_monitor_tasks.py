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

import asyncio
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
from app.services.price_stream_service import get_cached_ltp

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")


def _get_redis():
    from app.core.redis_pool import get_sync_redis
    return get_sync_redis()

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
        # Phase 6 All-In ladder (master 1D.8 - one detector, presentation tier):
        #   caution  1.5-2x limit
        #   danger   >2x limit
        #   critical >=30% of capital - and >=50% presents as ALL-IN BET
        all_in = exposure_pct >= 50.0
        if exposure_pct >= 30.0:
            severity = "critical"
        elif exposure_pct > max_size * 2:
            severity = "danger"
        else:
            severity = "caution"

        # Emotional multiplier (doc 4 P32): recent emotional danger events
        # (recovery bet / martingale / revenge) bump severity one level -
        # oversized AFTER losses is the "make it back" bet.
        emotional_bump = False
        async with SessionLocal() as ev_db:
            from app.models.behavior_event import BehaviorEvent
            from sqlalchemy import select as _sel, and_ as _and
            ist_now = datetime.now(timezone.utc)
            day_start = ist_now - timedelta(hours=12)
            ev_res = await ev_db.execute(_sel(BehaviorEvent).where(_and(
                BehaviorEvent.broker_account_id == UUID(broker_account_id),
                BehaviorEvent.detected_at >= day_start,
                BehaviorEvent.detector.in_(
                    ("post_loss_recovery_bet", "martingale_behaviour", "revenge_trade")),
                BehaviorEvent.severity.in_(("danger", "critical")),
            )))
            if ev_res.scalars().first():
                emotional_bump = True
        if emotional_bump and severity == "caution":
            severity = "danger"
        elif emotional_bump and severity == "danger":
            severity = "critical"

        label = "ALL-IN BET" if all_in else "Overexposure"
        async with SessionLocal() as alert_db:
            await _fire_position_alert(
                broker_account_id=broker_account_id,
                pattern_type="overexposure",
                severity=severity,
                message=(
                    f"{label}: {tradingsymbol} ₹{position_value:,.0f} exposure "
                    f"({exposure_pct:.1f}% of capital, your limit {max_size:.0f}%)"
                    + (" after recent loss-chasing behavior." if emotional_bump else ".")
                ),
                details={
                    "symbol": tradingsymbol,
                    "position_value": round(position_value),
                    "exposure_pct": round(exposure_pct, 1),
                    "limit_pct": max_size,
                    "all_in": all_in,
                    "emotional_bump": emotional_bump,
                    "_confidence": 95.0,
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
    from app.models.behavior_event import BehaviorEvent
    from app.core.event_bus import publish_event
    from sqlalchemy import select, and_
    from uuid import uuid4 as _uuid4

    # 30-min dedup window; rule-aware for constitution (Q15) and
    # escalation-aware (Phase 6): a higher severity always passes.
    _RANK = {"info": 0, "caution": 1, "danger": 2, "critical": 3}
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
    rule = (details or {}).get("rule")
    recent = [a for a in existing.scalars().all()
              if rule is None or (a.details or {}).get("rule") == rule]
    max_recent = max((_RANK.get(a.severity, 0) for a in recent), default=-1)
    if recent and _RANK.get(severity, 0) <= max_recent:
        logger.debug(
            f"[position_monitor] {pattern_type} for {broker_account_id[:8]} "
            f"suppressed — already alerted at this level in last 30 min"
        )
        return False

    from app.services.behavior_engine import ENGINE_VERSION
    from app.services.detector_registry import BY_NAME as _SPECS, ALIASES as _ALIASES
    _spec = _SPECS.get(pattern_type)
    version = _spec.version if _spec else _ALIASES.get(pattern_type, ENGINE_VERSION)
    confidence = (details or {}).pop("_confidence", 90.0)
    data_quality = (details or {}).pop("_data_quality", "GOOD")
    now_utc = datetime.now(timezone.utc)

    alert = RiskAlert(
        id=_uuid4(),
        broker_account_id=UUID(broker_account_id),
        pattern_type=pattern_type,
        severity=severity,
        message=message,
        details=details,
        detector_version=version,
        confidence=confidence,
        detected_at=now_utc,
        # Every alert from this module is raised while the position is still
        # open — that is the whole point of the position monitor, and the copy
        # already says "position is OPEN". Migration 076 added `lifecycle` to
        # record exactly that distinction and it was never set, so these were
        # stored as 'post' alongside genuinely post-hoc findings. Nothing can
        # tell live alerts from post-hoc ones until this is right, which is the
        # foundation the entry-time work builds on.
        lifecycle="live",
    )
    db.add(alert)
    await db.flush()
    # Evidence record (1C.8) — entry-time detections feed state/scores too
    db.add(BehaviorEvent(
        broker_account_id=UUID(broker_account_id),
        detector=pattern_type,
        detector_version=version,
        severity=severity,
        confidence=confidence,
        data_quality=data_quality,
        message=message,
        evidence=dict(details or {}),
        input_snapshot={"source": "position_monitor"},
        risk_alert_id=alert.id,
        detected_at=now_utc,
    ))
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

    # WhatsApp + push for danger/critical alerts (guardian gating + monthly
    # budget enforced inside send_danger_alert - Phase 5)
    if severity in ("danger", "critical"):
        from app.tasks.trade_tasks import send_danger_alert
        send_danger_alert.delay(broker_account_id, str(alert.id))

    return True


# ─────────────────────────────────────────────────────────────────────────────
# Phase 6: portfolio concentration + entry-time constitution rules
# ─────────────────────────────────────────────────────────────────────────────

async def _open_structures(broker_account_id: str) -> list:
    """
    Recognised multi-leg structures among the account's currently open positions.

    Non-fatal by design: this is context that improves a decision, never a
    precondition for making one. If it fails the entry checks still run, they
    just run without knowing the legs belong together.
    """
    from sqlalchemy import and_, select

    from app.models.position import Position
    from app.services.strategy_detector import classify_open_positions

    try:
        async with SessionLocal() as db:
            result = await db.execute(
                select(Position).where(and_(
                    Position.broker_account_id == UUID(broker_account_id),
                    Position.total_quantity != 0,
                ))
            )
            return classify_open_positions(list(result.scalars().all()))
    except Exception as e:
        logger.warning(f"[entry_batch] open-structure classification failed: {e}")
        return []


@celery_app.task(name="app.tasks.position_monitor_tasks.flush_entry_batch")
def flush_entry_batch(broker_account_id: str):
    """
    Run the entry-time checks once for everything that landed in the window.

    Scheduled by the fill pipeline when an opening fill starts a window (E1).
    Whatever arrived inside it — partial fills of one order, the four legs of a
    condor, a sliced entry — is evaluated as a single event instead of N.
    """
    return asyncio.run(_flush_entry_batch(broker_account_id))


async def _flush_entry_batch(broker_account_id: str) -> dict:
    from app.services import entry_batch_service as batch

    try:
        redis = _get_redis()
        fills = batch.drain(redis, broker_account_id)
    except Exception as e:
        # Nothing to fall back to here: the fills are gone with the window.
        # Loud, because it means entry checks silently did not run.
        logger.error(f"[entry_batch] drain failed for {broker_account_id[:8]}: {e}")
        return {"error": "drain_failed"}

    if not fills:
        return {"skipped": "empty_batch"}

    summary = batch.summarise(fills)
    symbols = summary["symbols"]

    # E2: what structures do the account's OPEN positions form right now?
    # The exit-time detector cannot answer this — it waits for a second leg to
    # close. Knowing at entry that these legs are an iron condor rather than
    # four impulsive trades is the difference between one alert and four wrong
    # ones, and it is the input the inferred detectors will need.
    structures = await _open_structures(broker_account_id)
    if structures:
        summary["structures"] = structures
        logger.info(
            f"[entry_batch] {broker_account_id[:8]}: open structures — "
            + ", ".join(f"{s['strategy_type']} ({s['leg_count']} legs)" for s in structures)
        )

    logger.info(
        f"[entry_batch] {broker_account_id[:8]}: {summary['fill_count']} fill(s), "
        f"{summary['distinct_symbols']} instrument(s) — evaluating once"
    )

    # Account-level: one check per window regardless of how many legs landed.
    try:
        await _concentration_task(broker_account_id)
    except Exception as e:
        logger.warning(f"concentration check failed: {e}")

    # Position-level: genuinely per instrument — each leg is its own position
    # and its own exposure. The 30-minute dedup in _fire_position_alert keeps
    # this from becoming one alert per leg.
    for symbol in symbols:
        try:
            await _overexposure_task(broker_account_id, symbol)
        except Exception as e:
            logger.warning(f"overexposure check failed for {symbol}: {e}")

    # Account-level rules, but the copy names what was entered — which is the
    # point of coalescing: "4 positions (NIFTY… +3 more)", not one arbitrary leg.
    try:
        await _entry_rules_task(broker_account_id, symbols)
    except Exception as e:
        logger.warning(f"entry rules check failed: {e}")

    return {"fills": summary["fill_count"], "symbols": summary["distinct_symbols"]}


@celery_app.task(name="app.tasks.position_monitor_tasks.check_portfolio_concentration")
def check_portfolio_concentration(broker_account_id: str):
    """
    Entry-time concentration check (master 10b / doc 4 P31):
    largest underlying exposure / total exposure, levels 40/60/80%.
    Requires 2+ open underlyings — a single position is overexposure's job.
    LTP from Redis cache; falls back to entry price (data quality PARTIAL).
    """
    import asyncio
    return asyncio.run(_concentration_task(broker_account_id))


async def _concentration_task(broker_account_id: str) -> dict:
    from app.models.position import Position
    from app.services.instrument_parser import parse_symbol
    from sqlalchemy import select, and_

    async with SessionLocal() as db:
        result = await db.execute(
            select(Position).where(and_(
                Position.broker_account_id == UUID(broker_account_id),
                Position.total_quantity != 0,
            ))
        )
        positions = list(result.scalars().all())

    if len(positions) < 2:
        return {"skipped": "single_position"}

    by_underlying: dict = {}
    partial = False
    for pos in positions:
        try:
            u = parse_symbol(pos.tradingsymbol or "").underlying or pos.tradingsymbol
        except Exception:
            u = pos.tradingsymbol
        ltp = get_cached_ltp(pos.instrument_token) if pos.instrument_token else None
        if ltp is None:
            ltp = float(pos.average_entry_price or 0)
            partial = True
        by_underlying[u] = by_underlying.get(u, 0.0) + ltp * abs(pos.total_quantity or 0)

    if len(by_underlying) < 2:
        return {"skipped": "single_underlying"}
    total = sum(by_underlying.values())
    if total <= 0:
        return {"skipped": "zero_exposure"}

    top_u, top_v = max(by_underlying.items(), key=lambda kv: kv[1])
    pct = top_v / total * 100

    if pct >= 80:
        severity = "critical"
    elif pct >= 60:
        severity = "danger"
    elif pct >= 40:
        severity = "caution"
    else:
        return {"underlying": top_u, "pct": round(pct, 1), "alerted": False}

    async with SessionLocal() as alert_db:
        fired = await _fire_position_alert(
            broker_account_id=broker_account_id,
            pattern_type="portfolio_concentration",
            severity=severity,
            message=(
                f"{top_u} is {pct:.0f}% of your open exposure "
                f"(₹{top_v:,.0f} of ₹{total:,.0f} across "
                f"{len(by_underlying)} underlyings). Looks diversified, is not."
            ),
            details={
                "top_underlying": top_u,
                "top_pct": round(pct, 1),
                "total_exposure": round(total),
                "by_underlying": {k: round(v) for k, v in by_underlying.items()},
                "_confidence": 75.0 if partial else 95.0,
                "_data_quality": "PARTIAL" if partial else "GOOD",
            },
            db=alert_db,
        )
    return {"underlying": top_u, "pct": round(pct, 1), "alerted": fired}


@celery_app.task(name="app.tasks.position_monitor_tasks.check_entry_rules")
def check_entry_rules(broker_account_id: str, tradingsymbol: str):
    """
    Entry-time constitution checks (Phase 6): cooldown + restricted windows,
    evaluated AT THE FILL - while intervention still matters - instead of
    waiting for the position to close.
    """
    import asyncio
    return asyncio.run(_entry_rules_task(broker_account_id, tradingsymbol))


from app.services.entry_checks import squareoff_window as _squareoff_window  # noqa: E402
from app.services.fill_classification import POSITION_OPENING_FILLS as _OPENING_FILLS  # noqa: E402


async def _entry_rules_task(broker_account_id: str, tradingsymbol) -> dict:
    """
    Entry-time constitution rules.

    `tradingsymbol` accepts a single symbol or a list of them: E1 coalesces the
    fills that land inside one window, so a four-leg structure arrives here once
    with four symbols rather than four times with one each. The rules themselves
    are account-level facts (is it a no-trade window, are we inside a cooldown),
    so the symbols only shape the copy.
    """
    from app.services.entry_batch_service import describe as _describe

    symbols = [tradingsymbol] if isinstance(tradingsymbol, str) else list(tradingsymbol or [])
    symbols = [s for s in symbols if s]
    entered = _describe(symbols)
    return await __entry_rules_impl(broker_account_id, entered, symbols)


async def __entry_rules_impl(broker_account_id: str, entered: str, symbols: list) -> dict:
    from zoneinfo import ZoneInfo as _ZI
    from app.models.user_profile import UserProfile
    from app.models.completed_trade import CompletedTrade
    from app.core.trading_defaults import get_thresholds
    from sqlalchemy import select, and_, desc

    IST = _ZI("Asia/Kolkata")
    now_utc = datetime.now(timezone.utc)
    fired = []

    async with SessionLocal() as db:
        prof_res = await db.execute(
            select(UserProfile).where(UserProfile.broker_account_id == UUID(broker_account_id))
        )
        profile = prof_res.scalar_one_or_none()
        if not profile:
            return {"skipped": "no_profile"}
        th = get_thresholds(profile)

        # Rule: restricted window (binary)
        windows = th.get("restricted_windows") or []
        now_ist = now_utc.astimezone(IST)
        now_min = now_ist.hour * 60 + now_ist.minute
        for w in windows:
            try:
                start_s, end_s = w.split("-")
                sh, sm = map(int, start_s.split(":"))
                eh, em = map(int, end_s.split(":"))
            except (ValueError, AttributeError):
                continue
            if sh * 60 + sm <= now_min <= eh * 60 + em:
                await _fire_position_alert(
                    broker_account_id=broker_account_id,
                    pattern_type="constitution_violation",
                    severity="danger",
                    message=(
                        f"Your no-trade window ({w} IST) violated: entered "
                        f"{entered} at {now_ist.strftime('%H:%M')} - position is OPEN."
                    ),
                    details={"rule": "restricted_window", "window": w,
                             "entry_time_ist": now_ist.strftime("%H:%M"),
                             "symbol": symbols[0] if symbols else None,
                             "symbols": symbols, "at_entry": True,
                             "_confidence": 100.0},
                    db=db,
                )
                fired.append("restricted_window")
                break

        # Rule: cooldown after loss (binary)
        cooldown_min = th.get("user_cooldown_min")
        if cooldown_min:
            loss_res = await db.execute(
                select(CompletedTrade).where(and_(
                    CompletedTrade.broker_account_id == UUID(broker_account_id),
                    CompletedTrade.realized_pnl < 0,
                    CompletedTrade.exit_time >= now_utc - timedelta(minutes=int(cooldown_min)),
                )).order_by(desc(CompletedTrade.exit_time)).limit(1)
            )
            last_loss = loss_res.scalar_one_or_none()
            if last_loss and last_loss.exit_time:
                gap = (now_utc - last_loss.exit_time).total_seconds() / 60
                await _fire_position_alert(
                    broker_account_id=broker_account_id,
                    pattern_type="constitution_violation",
                    severity="danger",
                    message=(
                        f"Your {int(cooldown_min)}-minute cooldown violated: entered "
                        f"{entered} {gap:.0f} min after a "
                        f"₹{abs(float(last_loss.realized_pnl or 0)):,.0f} loss - "
                        f"position is OPEN."
                    ),
                    details={"rule": "cooldown", "gap_min": round(gap, 1),
                             "limit_min": int(cooldown_min),
                             "prior_loss": float(last_loss.realized_pnl or 0),
                             "prior_symbol": last_loss.tradingsymbol,
                             "symbol": symbols[0] if symbols else None,
                             "symbols": symbols, "at_entry": True,
                             "_confidence": 100.0},
                    db=db,
                )
                fired.append("cooldown")

        # ── E3: rules that are pure arithmetic at entry ───────────────────
        # Trade limit, loss limit and the MIS square-off run-up. All three are
        # fully decidable the moment the position opens, and all three lose most
        # of their value once it has closed — "you have 20 minutes before this
        # is squared off for you" is not a useful thing to learn afterwards.
        from app.models.position_ledger import PositionLedger
        from app.models.trading_session import TradingSession
        from app.services.entry_checks import (
            count_entries_today, evaluate_loss_limit, evaluate_mis_panic,
            evaluate_trade_limit,
        )

        day_start_utc = now_ist.replace(
            hour=0, minute=0, second=0, microsecond=0
        ).astimezone(timezone.utc)

        ledger_res = await db.execute(
            select(PositionLedger).where(and_(
                PositionLedger.broker_account_id == UUID(broker_account_id),
                PositionLedger.occurred_at >= day_start_utc,
            ))
        )
        ledger_rows = list(ledger_res.scalars().all())
        entries_today = count_entries_today(ledger_rows)

        approaching = float(th.get("constitution_approaching_pct", 0.80))
        severe = float(th.get("constitution_severe_pct", 1.20))

        trade_limit_hit = evaluate_trade_limit(
            entries_today, th.get("user_daily_trade_limit"), approaching, severe
        )
        if trade_limit_hit:
            await _fire_position_alert(
                broker_account_id=broker_account_id,
                pattern_type="constitution_violation",
                severity=trade_limit_hit["severity"],
                message=trade_limit_hit["message"],
                details={**{k: v for k, v in trade_limit_hit.items()
                            if k not in ("severity", "message")},
                         "symbols": symbols, "at_entry": True, "_confidence": 100.0},
                db=db,
            )
            fired.append("daily_trade_limit")

        session_res = await db.execute(
            select(TradingSession).where(and_(
                TradingSession.broker_account_id == UUID(broker_account_id),
                TradingSession.session_date == now_ist.date(),
            ))
        )
        session_row = session_res.scalar_one_or_none()
        session_pnl = float(getattr(session_row, "session_pnl", 0) or 0)

        loss_limit_hit = evaluate_loss_limit(
            session_pnl, th.get("daily_loss_limit"), approaching, severe
        )
        if loss_limit_hit:
            await _fire_position_alert(
                broker_account_id=broker_account_id,
                pattern_type="constitution_violation",
                severity=loss_limit_hit["severity"],
                message=loss_limit_hit["message"],
                details={**{k: v for k, v in loss_limit_hit.items()
                            if k not in ("severity", "message")},
                         "symbols": symbols, "at_entry": True, "_confidence": 100.0},
                db=db,
            )
            fired.append("daily_loss_limit")

        # MIS square-off run-up. Product and exchange come from the fills that
        # opened the window, so this only fires for genuinely intraday entries.
        mis_rows = [
            r for r in ledger_rows
            if (getattr(r, "product", "") or "").upper() in ("MIS", "INTRADAY")
            and getattr(r, "entry_type", None) in _OPENING_FILLS
        ]
        if mis_rows:
            exchange = next((r.exchange for r in mis_rows if r.exchange), None)
            panic_start, _ = _squareoff_window(exchange, now_ist)
            late_count = sum(
                1 for r in mis_rows
                if r.occurred_at and r.occurred_at.astimezone(IST) >= panic_start
            )
            mis_hit = evaluate_mis_panic(
                now_ist, exchange, "MIS", late_count,
                caution_count=th.get("end_session_mis_caution_count", 2),
                danger_count=th.get("end_session_mis_danger_count", 3),
            )
            if mis_hit:
                await _fire_position_alert(
                    broker_account_id=broker_account_id,
                    pattern_type="end_of_session_mis_panic",
                    severity=mis_hit["severity"],
                    message=mis_hit["message"],
                    details={**{k: v for k, v in mis_hit.items()
                                if k not in ("severity", "message")},
                             "symbols": symbols, "at_entry": True, "_confidence": 100.0},
                    db=db,
                )
                fired.append("end_of_session_mis_panic")

    return {"fired": fired}
