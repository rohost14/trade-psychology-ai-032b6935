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
from typing import Any, Dict, List, NamedTuple, Optional, Sequence
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
    siblings = await _drop_already_grouped(siblings, db)
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
# Counting structures instead of legs (E2)
# ---------------------------------------------------------------------------
# A CompletedTrade is per tradingsymbol, so one four-leg iron condor is four
# rows. Detectors that count trades were therefore counting legs: two condors
# read as eight trades against a burst threshold of five, and a spread trader
# got a danger-severity overtrading alert for two positions.
#
# This does not use StrategyGroup rows, deliberately. Those are only written
# when the second leg CLOSES, so mid-session the earlier legs of an open
# structure are not yet grouped — the counting has to work from the trades in
# hand, and identically at entry time and exit time.

#: Legs of one structure are placed together. Beyond this gap it is a new
#: decision, not another leg of the same one.
#:
#: 30s, not 120s. A real structure goes in as a basket or a rapid sequence —
#: seconds apart. Two minutes was wide enough to swallow a panic entry: buying
#: a call and then a put a minute later classifies as a straddle and collapsed
#: to one "disciplined decision", which is the opposite of what that behaviour
#: is. Deliberate legging-in over minutes is not covered by any sane window and
#: is handled by classify_open_positions instead, which reads the positions
#: themselves rather than guessing from timing.
STRUCTURE_GAP_SECONDS = 30


def _entry_ts(trade) -> Optional[datetime]:
    return getattr(trade, "entry_time", None)


def cluster_legs(trades: Sequence[Any], gap_seconds: int = STRUCTURE_GAP_SECONDS) -> List[List[Any]]:
    """
    Group trades that were plausibly entered as one structure.

    Two rules, both conservative:

      * Same underlying and expiry, entered within `gap_seconds` of each other.
      * **Distinct symbols.** A repeat of a symbol already in the cluster is a
        re-entry, not another leg — otherwise a scalper taking the same strike
        twice in a minute would be counted as one "structure" and their
        overtrading would disappear.

    Trades with no entry time or no parseable expiry are returned as singletons
    rather than guessed at.
    """
    buckets: Dict[tuple, List[Any]] = {}
    singletons: List[List[Any]] = []

    for t in trades:
        ts = _entry_ts(t)
        parsed = parse_symbol(getattr(t, "tradingsymbol", "") or "")
        if ts is None or not parsed.underlying or not parsed.expiry_key:
            singletons.append([t])
            continue
        buckets.setdefault((parsed.underlying, parsed.expiry_key), []).append(t)

    clusters: List[List[Any]] = []
    for bucket in buckets.values():
        bucket.sort(key=_entry_ts)
        current: List[Any] = []
        current_symbols: set = set()
        prev_ts: Optional[datetime] = None
        for t in bucket:
            ts = _entry_ts(t)
            symbol = getattr(t, "tradingsymbol", "") or ""
            too_far = prev_ts is not None and (ts - prev_ts).total_seconds() > gap_seconds
            repeat = symbol in current_symbols
            if current and (too_far or repeat):
                clusters.append(current)
                current, current_symbols = [], set()
            current.append(t)
            current_symbols.add(symbol)
            prev_ts = ts
        if current:
            clusters.append(current)

    return clusters + singletons


def count_structures(trades: Sequence[Any], gap_seconds: int = STRUCTURE_GAP_SECONDS) -> int:
    """
    How many trading decisions are in this list, counting a structure as one.

    A cluster collapses to 1 only when it classifies as a *recognised* strategy.
    An unrecognised cluster stays as its individual legs — two directional
    trades on the same underlying a minute apart are two decisions, not a
    mystery spread. For a trader who never trades multi-leg, this returns
    len(trades) exactly and nothing about their alerts changes.

    **The invariant is `count <= len(trades)`, and that is the only one.** It
    holds permanently, because a cluster contributes either 1 or its own leg
    count and never more.

    This docstring used to say something stronger and wrong — that "the count
    can only fall, never rise, so thresholds can only fire less often". That is
    true against a raw leg count. It is NOT true across a change to the
    classifier, and B1 (2026-09-02) is the counter-example: FUT LONG + PE SHORT
    was named `futures_hedge_bullish` and counted 1; it is a risk-adding
    structure, not a hedge, so it now falls to MULTI_LEG_UNKNOWN and counts 2.
    The count ROSE, correctly, and the overtrading detectors can fire more
    often for a trader who does this. Any future classification change must be
    measured against the previous behaviour rather than assumed conservative.
    """
    total = 0
    for cluster in cluster_legs(trades, gap_seconds):
        if len(cluster) > 1 and classify_legs(
            [LegView(getattr(t, "tradingsymbol", "") or "",
                     getattr(t, "direction", "") or "") for t in cluster]
        ) != StrategyType.MULTI_LEG_UNKNOWN:
            total += 1
        else:
            total += len(cluster)
    return total


#: How each structure is named to a trader. Lives here, beside the values it
#: describes, for the same reason the pattern copy does: a label map on the
#: frontend keyed on backend strings is the drift that produced the empty alert
#: panel. The frontend renders what this returns.
STRATEGY_LABELS: Dict[str, str] = {
    StrategyType.STRADDLE_BUY:          "Long straddle",
    StrategyType.STRADDLE_SELL:         "Short straddle",
    StrategyType.STRANGLE_BUY:          "Long strangle",
    StrategyType.STRANGLE_SELL:         "Short strangle",
    StrategyType.BULL_CALL_SPREAD:      "Bull call spread",
    StrategyType.BEAR_PUT_SPREAD:       "Bear put spread",
    StrategyType.BULL_PUT_SPREAD:       "Bull put spread",
    StrategyType.BEAR_CALL_SPREAD:      "Bear call spread",
    StrategyType.IRON_CONDOR:           "Iron condor",
    StrategyType.IRON_BUTTERFLY:        "Iron butterfly",
    StrategyType.FUTURES_HEDGE_BULLISH: "Hedged long future",
    StrategyType.FUTURES_HEDGE_BEARISH: "Hedged short future",
    StrategyType.CALENDAR_SPREAD:       "Calendar spread",
    StrategyType.SYNTHETIC_LONG:        "Synthetic long",
    StrategyType.SYNTHETIC_SHORT:       "Synthetic short",
    StrategyType.MULTI_LEG_UNKNOWN:     "Multi-leg position",
}


def strategy_label(strategy_type: str) -> str:
    """Trader-facing name for a structure. Falls back to a readable form."""
    return STRATEGY_LABELS.get(
        strategy_type, (strategy_type or "").replace("_", " ").capitalize() or "Position"
    )


def classify_open_positions(positions: Sequence[Any]) -> List[Dict[str, Any]]:
    """
    Entry-time grouping: what structures do these OPEN positions form?

    The exit-time path cannot answer this — it waits for the second leg to
    close, which is why `detect_and_save`'s docstring calls entry-time detection
    a later improvement. Open positions carry everything the classifier needs:
    the symbol, and the direction from the sign of the quantity.

    Returns one entry per recognised structure. Single legs and unrecognised
    combinations are omitted — callers want to know "is this part of a
    structure", and a maybe is not useful for suppressing a false positive.
    """
    legs_by_key: Dict[tuple, List[Any]] = {}
    for p in positions:
        qty = getattr(p, "total_quantity", 0) or 0
        if qty == 0:
            continue
        parsed = parse_symbol(getattr(p, "tradingsymbol", "") or "")
        if not parsed.underlying or not parsed.expiry_key:
            continue
        legs_by_key.setdefault((parsed.underlying, parsed.expiry_key), []).append(p)

    structures: List[Dict[str, Any]] = []
    for (underlying, expiry_key), legs in legs_by_key.items():
        if len(legs) < 2:
            continue
        views = [
            LegView(
                getattr(p, "tradingsymbol", "") or "",
                "LONG" if (getattr(p, "total_quantity", 0) or 0) > 0 else "SHORT",
            )
            for p in legs
        ]
        strategy_type = classify_legs(views)
        if strategy_type == StrategyType.MULTI_LEG_UNKNOWN:
            continue
        structures.append({
            "strategy_type": strategy_type,
            "label": strategy_label(strategy_type),
            "underlying": underlying,
            "expiry_key": expiry_key,
            "symbols": [v.tradingsymbol for v in views],
            "leg_count": len(views),
        })
    return structures


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _drop_already_grouped(siblings: List, db: AsyncSession) -> List:
    """
    Remove siblings that are already a leg of some other strategy group.

    A CompletedTrade belongs to at most one group — `strategy_group_legs`
    enforces it with a UNIQUE on completed_trade_id. The guard above checks that
    for the trade being classified but never for its siblings, and on a busy day
    a sibling is very often already grouped: the same strike gets traded round
    after round, and _find_siblings matches on entry time, not on whether the
    candidate is still free.

    Building a group anyway made the bulk leg insert raise UniqueViolation. The
    caller catches it and logs "strategy detection failed ... behavior engine
    will not suppress hedge alerts" — so the failure is not just a lost group,
    it silently disables hedge suppression for that trade and every alert that
    depended on knowing the legs belonged together. It fired 36 times in a
    single 200-fill session and never appears at the volumes the other tests
    use, which is exactly why the volume scenario exists.
    """
    if not siblings:
        return []

    from sqlalchemy import select

    from app.models.strategy_group import StrategyGroupLeg

    ids = [t.id for t in siblings]
    taken = set((await db.execute(
        select(StrategyGroupLeg.completed_trade_id)
        .where(StrategyGroupLeg.completed_trade_id.in_(ids))
    )).scalars().all())

    return [t for t in siblings if t.id not in taken]


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


class LegView(NamedTuple):
    """
    The minimum a leg needs to be classified: what it is, and which way.

    The classifier never looked at P&L, exit price or duration — only the symbol
    and the direction — which is why the same logic works on an open position as
    on a closed round. This type is what makes that reusable: CompletedTrades at
    exit time, open Positions at entry time, both become LegViews.
    """
    tradingsymbol: str
    direction: str          # "LONG" | "SHORT"


def _classify(
    ct: CompletedTrade,
    parsed: ParsedSymbol,
    siblings: List[CompletedTrade],
) -> str:
    """Exit-time entry point — unchanged behaviour, delegates to classify_legs."""
    return classify_legs(
        [LegView(ct.tradingsymbol or "", ct.direction or "")]
        + [LegView(t.tradingsymbol or "", t.direction or "") for t in siblings]
    )


def classify_legs(legs: List[LegView]) -> str:
    """
    Classify a set of legs into a strategy type.

    Pure: no DB, no P&L, no timestamps. Callers are responsible for having
    established that these legs belong together (same underlying, entered
    together) — this answers only "what shape is it".

    **This is deliberately not a universal options-strategy classifier.** It
    names the small set of common structures whose semantics are unambiguous,
    and says so honestly about everything else. A trader can build a ratio,
    a diagonal, a custom or an exotic structure that no rule here will
    recognise, and that is the expected outcome rather than a shortfall.

    There are three states, and they are not interchangeable:

    * **a named type** — we are confident what this is
    * **MULTI_LEG_UNKNOWN** — these legs are one multi-leg decision, and we
      do not know which strategy. **An intentional uncertainty state, not a
      failed classification.** What it should EARN — suppression, collapsing
      to one decision — is a separate product question and is decided by the
      callers, not here
    * **not grouped at all** — the caller decided these entries were not
      related enough to be one structure; this function never sees them

    So a wrong name is a defect and MULTI_LEG_UNKNOWN is not. Every predicate
    below is written to fail closed into it: a structure is named only when
    the properties that DEFINE it are present, never on leg count alone.
    """
    all_trades = list(legs)
    all_parsed = [parse_symbol(t.tradingsymbol or "") for t in all_trades]

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
    # The option leg must be BOUGHT. A protective put is a put you own: it is
    # the long option that caps the loss on a long future. Selling the put
    # instead leaves the downside open and adds short-put risk underneath a
    # long future — the opposite structure, and it was reaching this branch
    # because only the option's TYPE was read, never its direction.
    if "FUT" in instrument_types and n == 2:
        other_type = (instrument_types - {"FUT"}).pop() if len(instrument_types) > 1 else None
        fut_trade = next(t for t, p in zip(all_trades, all_parsed) if p.instrument_type == "FUT")
        opt_trade = next(
            (t for t, p in zip(all_trades, all_parsed) if p.instrument_type in ("CE", "PE")),
            None,
        )
        option_is_bought = opt_trade is not None and opt_trade.direction == "LONG"
        if option_is_bought:
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

    # ── Iron butterfly / iron condor ─────────────────────────────────────────
    # Both are one shape: a SOLD body with BOUGHT wings outside it, two calls
    # and two puts on one expiry. They differ only in how wide the body is —
    # a butterfly sells a single strike (the CE and the PE together), a condor
    # sells two. So one ordering test decides both:
    #
    #     long put  <  short put  <=  short call  <  long call
    #
    # and `short put == short call` is what makes it a butterfly.
    #
    # Tested as ONE branch because splitting them is what broke this before:
    # the butterfly sat *below* a condor test written on leg count and mixed
    # direction alone, which every real butterfly also satisfies — so it
    # returned `iron_condor` first and the butterfly branch could only ever be
    # reached by four legs in the SAME direction, which is not a butterfly.
    # The condor test was also unvalidated: any four mixed-direction CE/PE
    # legs matched it, including the inverted structure (bought body, sold
    # wings) whose risk runs the other way.
    #
    # Anything that is not this shape falls to MULTI_LEG_UNKNOWN, which is
    # what the function already does with every combination it cannot name.
    if n == 4 and opt_types == {"CE", "PE"} and directions == {"LONG", "SHORT"}:
        calls = [(p.strike, t.direction) for t, p in zip(all_trades, all_parsed)
                 if p.instrument_type == "CE"]
        puts = [(p.strike, t.direction) for t, p in zip(all_trades, all_parsed)
                if p.instrument_type == "PE"]
        if len(calls) == 2 and len(puts) == 2 and all(s is not None for s, _ in calls + puts):
            short_call = [s for s, d in calls if d == "SHORT"]
            long_call = [s for s, d in calls if d == "LONG"]
            short_put = [s for s, d in puts if d == "SHORT"]
            long_put = [s for s, d in puts if d == "LONG"]
            if len(short_call) == len(long_call) == len(short_put) == len(long_put) == 1:
                sc, lc, sp, lp = short_call[0], long_call[0], short_put[0], long_put[0]
                if lp < sp <= sc < lc:
                    return (StrategyType.IRON_BUTTERFLY if sp == sc
                            else StrategyType.IRON_CONDOR)
        return StrategyType.MULTI_LEG_UNKNOWN

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
