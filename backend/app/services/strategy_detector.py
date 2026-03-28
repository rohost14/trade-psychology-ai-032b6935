"""
Strategy Detector — Multi-Leg Strategy Classification

Runs AFTER FIFO creates a CompletedTrade. Looks at other recent CompletedTrades
on the same account to detect if the current trade is part of a multi-leg strategy
(straddle, strangle, spread, iron condor, futures hedge, etc.).

Detection window: trades whose entry_time is within ENTRY_WINDOW_MINUTES of the
current trade's entry_time.  We use entry_time (not exit_time) because strategy
legs are typically entered together — they may close at different times.

Detection timing
----------------
When the SECOND (or last) leg of a strategy closes, this detector:
  1. Finds the sibling CompletedTrades by entry_time proximity
  2. Classifies the strategy type
  3. Creates a StrategyGroup + StrategyGroupLeg rows in the DB
  4. Returns the StrategyGroup so BehaviorEngine can use it immediately

The FIRST leg of a strategy may still fire some alerts (we don't know it's a
strategy leg until the second leg closes).  Full entry-time detection (using open
Positions before any leg closes) is a Phase 2 improvement.

Supported strategy types (12)
------------------------------
  straddle_buy / straddle_sell
  strangle_buy / strangle_sell
  bull_call_spread / bear_put_spread / bull_put_spread / bear_call_spread
  iron_condor / iron_butterfly
  futures_hedge_bullish / futures_hedge_bearish
  calendar_spread
  synthetic_long / synthetic_short
  multi_leg_unknown  (2+ legs detected but don't match a named pattern)
"""
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.completed_trade import CompletedTrade
from app.models.strategy_group import StrategyGroup, StrategyGroupLeg, StrategyType
from app.services.instrument_parser import parse_symbol, same_expiry, ParsedSymbol

logger = logging.getLogger(__name__)

ENTRY_WINDOW_MINUTES = 15   # legs entered within this window are candidate siblings


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def detect_and_save(
    completed_trade: CompletedTrade,
    db: AsyncSession,
) -> Optional[StrategyGroup]:
    """
    Detect if `completed_trade` belongs to a multi-leg strategy.

    If a strategy is detected, creates StrategyGroup + StrategyGroupLeg rows,
    commits them to the DB, and returns the StrategyGroup.

    Returns None if no strategy is detected (single-leg trade) or if the trade
    already belongs to an existing StrategyGroup.
    """
    # Guard: skip EQ (delivery) trades — no multi-leg strategies apply
    if completed_trade.instrument_type == "EQ":
        return None

    # Guard: already in a strategy group?
    existing = await _get_group_for_trade(completed_trade.id, db)
    if existing:
        return existing

    parsed = parse_symbol(completed_trade.tradingsymbol or "")
    if parsed.instrument_type == "EQ":
        return None

    # Find candidate sibling trades (same account, session, similar entry time)
    siblings = await _find_siblings(completed_trade, parsed, db)
    if not siblings:
        return None

    # Classify strategy
    strategy_type = _classify(completed_trade, parsed, siblings)

    # Build StrategyGroup
    all_trades = [completed_trade] + siblings
    net_pnl = sum(Decimal(str(t.realized_pnl or 0)) for t in all_trades)
    opened_at = min(t.entry_time for t in all_trades if t.entry_time)
    closed_at = max(t.exit_time for t in all_trades if t.exit_time)

    group = StrategyGroup(
        broker_account_id=completed_trade.broker_account_id,
        strategy_type=strategy_type,
        underlying=parsed.underlying,
        expiry_key=parsed.expiry_key,
        status="closed",
        net_pnl=net_pnl,
        opened_at=opened_at,
        closed_at=closed_at,
    )
    db.add(group)
    await db.flush()  # get group.id

    # Link all legs
    for trade in all_trades:
        p = parse_symbol(trade.tradingsymbol or "")
        leg_role = _leg_role(trade, p)
        db.add(StrategyGroupLeg(
            strategy_group_id=group.id,
            completed_trade_id=trade.id,
            leg_role=leg_role,
            leg_pnl=Decimal(str(trade.realized_pnl or 0)),
        ))

    await db.commit()

    logger.info(
        f"[strategy_detector] {strategy_type} detected — "
        f"{parsed.underlying} {parsed.expiry_key} | "
        f"legs={len(all_trades)} | net_pnl={float(net_pnl):+,.0f}"
    )
    return group


async def get_group_for_trade(
    completed_trade_id: UUID,
    db: AsyncSession,
) -> Optional[StrategyGroup]:
    """Return the StrategyGroup this trade belongs to, or None."""
    return await _get_group_for_trade(completed_trade_id, db)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _get_group_for_trade(
    completed_trade_id: UUID,
    db: AsyncSession,
) -> Optional[StrategyGroup]:
    leg_result = await db.execute(
        select(StrategyGroupLeg).where(
            StrategyGroupLeg.completed_trade_id == completed_trade_id
        )
    )
    leg = leg_result.scalar_one_or_none()
    if not leg:
        return None

    group_result = await db.execute(
        select(StrategyGroup).where(StrategyGroup.id == leg.strategy_group_id)
    )
    return group_result.scalar_one_or_none()


async def _find_siblings(
    ct: CompletedTrade,
    parsed: ParsedSymbol,
    db: AsyncSession,
) -> List[CompletedTrade]:
    """
    Find CompletedTrades that were entered within ENTRY_WINDOW_MINUTES of ct,
    on the same underlying + same expiry, but a different symbol.
    """
    if not ct.entry_time:
        return []

    window_start = ct.entry_time - timedelta(minutes=ENTRY_WINDOW_MINUTES)
    window_end   = ct.entry_time + timedelta(minutes=ENTRY_WINDOW_MINUTES)

    result = await db.execute(
        select(CompletedTrade).where(and_(
            CompletedTrade.broker_account_id == ct.broker_account_id,
            CompletedTrade.id != ct.id,
            CompletedTrade.entry_time >= window_start,
            CompletedTrade.entry_time <= window_end,
            CompletedTrade.tradingsymbol != ct.tradingsymbol,
        ))
    )
    candidates = list(result.scalars().all())

    # Filter to same underlying + same or compatible expiry
    siblings = []
    for c in candidates:
        p = parse_symbol(c.tradingsymbol or "")
        if p.underlying != parsed.underlying:
            continue
        # Same expiry (strict for straddle/strangle) OR different expiry (calendar spread)
        # — we accept both here; _classify() will tell them apart
        if not p.expiry_key:
            continue
        # Skip EQ siblings — not relevant for F&O strategy grouping
        if p.instrument_type == "EQ":
            continue
        siblings.append(c)

    return siblings


def _classify(
    ct: CompletedTrade,
    parsed: ParsedSymbol,
    siblings: List[CompletedTrade],
) -> str:
    """
    Classify the strategy type from the current trade + its siblings.
    All trades have the same underlying.
    """
    all_trades = [ct] + siblings
    all_parsed = [parsed] + [parse_symbol(t.tradingsymbol or "") for t in siblings]

    n = len(all_trades)
    instrument_types = {p.instrument_type for p in all_parsed}
    directions = {t.direction for t in all_trades}
    same_expiry_all = all(same_expiry(all_parsed[0], p) for p in all_parsed[1:])

    # Helper: for options legs only
    opt_types = {p.instrument_type for p in all_parsed if p.instrument_type in ("CE", "PE")}
    strikes = {p.strike for p in all_parsed if p.strike is not None}

    # ── Calendar spread (same type, different expiry) ────────────────────────
    if not same_expiry_all and n == 2:
        if len(instrument_types) == 1 and list(instrument_types)[0] in ("CE", "PE"):
            return StrategyType.CALENDAR_SPREAD

    # All remaining strategies require same expiry
    if not same_expiry_all:
        return StrategyType.MULTI_LEG_UNKNOWN

    # ── Futures hedge ────────────────────────────────────────────────────────
    if "FUT" in instrument_types and n == 2:
        other_type = (instrument_types - {"FUT"}).pop() if len(instrument_types) > 1 else None
        fut_trade = next(t for t, p in zip(all_trades, all_parsed) if p.instrument_type == "FUT")
        if other_type == "PE" and fut_trade.direction == "LONG":
            return StrategyType.FUTURES_HEDGE_BULLISH   # Long FUT + Buy PE hedge
        if other_type == "CE" and fut_trade.direction == "SHORT":
            return StrategyType.FUTURES_HEDGE_BEARISH   # Short FUT + Buy CE hedge
        return StrategyType.MULTI_LEG_UNKNOWN

    # From here all legs are options (CE/PE)
    if instrument_types - {"CE", "PE"}:
        return StrategyType.MULTI_LEG_UNKNOWN

    # ── Synthetic (same strike, CE + PE, opposite sides) ────────────────────
    if opt_types == {"CE", "PE"} and len(strikes) == 1 and n == 2:
        if directions == {"LONG", "SHORT"}:
            ce_trade = next(t for t, p in zip(all_trades, all_parsed) if p.instrument_type == "CE")
            if ce_trade.direction == "LONG":
                return StrategyType.SYNTHETIC_LONG    # Buy CE + Sell PE
            return StrategyType.SYNTHETIC_SHORT       # Sell CE + Buy PE

    # ── Straddle (CE + PE, same strike, same direction) ─────────────────────
    if opt_types == {"CE", "PE"} and len(strikes) == 1 and n == 2:
        if directions == {"LONG"}:  return StrategyType.STRADDLE_BUY
        if directions == {"SHORT"}: return StrategyType.STRADDLE_SELL

    # ── Strangle (CE + PE, different strikes, same direction) ───────────────
    if opt_types == {"CE", "PE"} and len(strikes) == 2 and n == 2:
        if directions == {"LONG"}:  return StrategyType.STRANGLE_BUY
        if directions == {"SHORT"}: return StrategyType.STRANGLE_SELL

    # ── Vertical spreads (2 legs, same type, different strikes, mixed sides) ─
    if len(opt_types) == 1 and len(strikes) == 2 and n == 2 and directions == {"LONG", "SHORT"}:
        opt = list(opt_types)[0]
        strike_list = sorted(s for s in strikes if s is not None)
        if len(strike_list) < 2:
            return StrategyType.MULTI_LEG_UNKNOWN
        lo_strike, hi_strike = strike_list
        # Find which leg is LONG
        long_parsed = next(p for t, p in zip(all_trades, all_parsed) if t.direction == "LONG")
        long_strike = long_parsed.strike

        if opt == "CE":
            # Bull call spread: buy lower CE, sell higher CE
            if long_strike == lo_strike: return StrategyType.BULL_CALL_SPREAD
            # Bear call spread: sell lower CE, buy higher CE
            return StrategyType.BEAR_CALL_SPREAD
        else:  # PE
            # Bear put spread: buy higher PE, sell lower PE
            if long_strike == hi_strike: return StrategyType.BEAR_PUT_SPREAD
            # Bull put spread: sell higher PE, buy lower PE
            return StrategyType.BULL_PUT_SPREAD

    # ── Iron condor (4 legs: short strangle + long strangle, wider) ──────────
    if opt_types == {"CE", "PE"} and n == 4 and directions == {"LONG", "SHORT"}:
        return StrategyType.IRON_CONDOR

    # ── Iron butterfly (4 legs at 3 strikes: short ATM straddle + long OTM) ──
    if opt_types == {"CE", "PE"} and n == 4 and len(strikes) == 3:
        return StrategyType.IRON_BUTTERFLY

    return StrategyType.MULTI_LEG_UNKNOWN


def _leg_role(trade: CompletedTrade, parsed: ParsedSymbol) -> str:
    """Return a human-readable role label for a strategy leg."""
    direction = (trade.direction or "").upper()
    itype = parsed.instrument_type

    if itype == "CE":
        return "long_call" if direction == "LONG" else "short_call"
    if itype == "PE":
        return "long_put" if direction == "LONG" else "short_put"
    if itype == "FUT":
        return "long_futures" if direction == "LONG" else "short_futures"
    return "unknown"
