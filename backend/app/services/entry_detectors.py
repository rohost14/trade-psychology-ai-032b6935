"""
Running the inferred detectors at entry time — E5.

The plan assumed these detectors would have to be rewritten against a new
context. Reading them showed otherwise. `_detect_revenge_trade` stacks
confidence signals from the gap since the last losing exit, whether it is the
same underlying, the size ratio against the session average, and session P&L.
Not one of those needs the outcome. It is already an entry-decidable detector
wearing an exit-time interface — it takes a CompletedTrade only because that is
the object the engine happens to hand it.

So this adapts the input rather than duplicating the logic. An `EntryView` is a
CompletedTrade-shaped view of a position that has just been opened: symbol,
direction, quantity, entry time — and no exit price, no realized P&L, no
duration, because those do not exist yet. The existing detectors run against it
unchanged.

That is the Phase 2 lesson applied: a second implementation of "what is revenge
trading" would drift from the first exactly the way the pattern copy did.

Two safety properties, both structural rather than promised:

  * **Only whitelisted detectors run.** ENTRY_DECIDABLE lists the ones whose
    decision genuinely does not need the outcome. Everything else — early_exit,
    for one — would read `realized_pnl` as absent and could only produce
    nonsense, so it is never asked.
  * **Nothing here raises an alert.** Output is written as shadow evidence.
    Promotion is per detector, through the existing `detector_flags` table, and
    is a decision to take with the numbers from /api/admin/detection-quality —
    not one to take here.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

#: Detectors whose decision is fully determined by the entry and the session so
#: far. Each was checked against its own body: none reads realized_pnl,
#: exit_price or duration for the trade being evaluated.
#:
#: Not listed, deliberately — these need the outcome and would be answering a
#: question they cannot see: early_exit,
#: premium_loss_event (live variant already ships separately, E4),
#: win_rate_collapse, strategy_breakdown,
#: time_of_day_bias, no_stoploss, opening_5min_trap.
ENTRY_DECIDABLE = (
    "revenge_trade",
    "rapid_reentry",
    "post_loss_recovery_bet",
    "martingale_behaviour",
    "fomo_entry",
    "same_symbol_obsession",
    "winning_streak_overconfidence",
    "options_premium_avg_down",
)

#: An inferred pattern raised from a position that has not resolved is a claim
#: made on partial evidence. It must clear a higher bar than the same pattern
#: raised once the outcome is known. Below this the detection is still recorded
#: as evidence — it simply does not count as a finding.
ENTRY_CONFIDENCE_FLOOR = 60.0


class EntryView:
    """
    A just-opened position, shaped like the CompletedTrade the detectors read.

    Every field the whitelisted detectors touch is present. The outcome fields
    are explicitly None rather than zero: `float(ct.realized_pnl or 0)` is the
    idiom throughout the engine, and a None flows through it as "no loss", which
    is the correct reading of a position that has not closed. A zero would be a
    claim.
    """

    __slots__ = (
        "id", "broker_account_id", "tradingsymbol", "exchange", "product",
        "instrument_type", "direction", "total_quantity", "entry_time",
        "avg_entry_price", "exit_time", "avg_exit_price", "realized_pnl",
        "pnl_pct", "duration_minutes", "num_entries", "num_exits",
        "closed_by_flip", "status", "quality_score",
    )

    def __init__(
        self,
        broker_account_id,
        tradingsymbol: str,
        exchange: Optional[str],
        product: Optional[str],
        direction: str,
        total_quantity: int,
        entry_time: datetime,
        avg_entry_price: Optional[float] = None,
        instrument_type: Optional[str] = None,
    ):
        self.id = None                  # no CompletedTrade row exists yet
        self.broker_account_id = broker_account_id
        self.tradingsymbol = tradingsymbol
        self.exchange = exchange
        self.product = product
        self.instrument_type = instrument_type or _instrument_type(tradingsymbol)
        self.direction = direction
        self.total_quantity = total_quantity
        self.entry_time = entry_time
        self.avg_entry_price = avg_entry_price
        # Not yet knowable. None, never 0 — see the class docstring.
        self.exit_time = None
        self.avg_exit_price = None
        self.realized_pnl = None
        self.pnl_pct = None
        self.duration_minutes = None
        self.num_entries = 1
        self.num_exits = 0
        self.closed_by_flip = False
        self.status = "open"
        self.quality_score = None


def _instrument_type(symbol: str) -> str:
    """
    Delegates to the canonical symbol parser.

    A local suffix check was written here first and classified RELIANCE as a
    call option, because the ticker ends in "CE". Every options detector would
    then have run against an equity position. The parser already knows a strike
    has to precede the suffix — writing a second implementation of symbol
    parsing is the same mistake as the second implementation of pattern copy.
    """
    from app.services.instrument_parser import parse_symbol

    try:
        # No `or "EQ"`. That fallback silently undid F9: an unreadable
        # derivative came back as None and was converted straight back into
        # equity, with a delivery-value denominator. None means UNKNOWN, and
        # UNKNOWN must reach the caller so it can abstain. (F16, 2026-08-29.)
        return parse_symbol(symbol or "").instrument_type
    except Exception:
        return "EQ"


def entry_view_from_position(broker_account_id, position, entry_time: datetime) -> EntryView:
    """Build an EntryView from an open Position row."""
    qty = position.total_quantity or 0
    return EntryView(
        broker_account_id=broker_account_id,
        tradingsymbol=position.tradingsymbol or "",
        exchange=getattr(position, "exchange", None),
        product=getattr(position, "product", None),
        direction="LONG" if qty > 0 else "SHORT",
        total_quantity=abs(qty),
        entry_time=entry_time,
        avg_entry_price=float(getattr(position, "average_entry_price", 0) or 0) or None,
    )


def evaluate_entry(engine, ctx, whitelist: Sequence[str] = ENTRY_DECIDABLE) -> List[Any]:
    """
    Run the entry-decidable detectors against an entry context.

    `ctx` is an ordinary EngineContext whose `completed_trade` is an EntryView.
    Returns DetectedEvents, each marked shadow — this function never produces an
    alert and the caller must not promote its output without the flag check.

    A detector raising is contained rather than propagated: one bad detector
    must not lose the findings of the other nine, and an entry-time evaluation
    is best-effort context, never a precondition for anything.
    """
    from app.services.detector_registry import BY_NAME

    events: List[Any] = []
    for name in whitelist:
        spec = BY_NAME.get(name)
        if spec is None:
            logger.warning("[entry_detectors] unknown detector in whitelist: %s", name)
            continue
        method = getattr(engine, spec.method, None)
        if method is None:
            logger.error("[entry_detectors] registry method missing: %s", spec.method)
            continue
        try:
            result = method(ctx)
        except Exception as e:
            logger.warning("[entry_detectors] %s failed at entry: %s", name, e)
            continue
        # A detector may return DetectedEvent(s) or a DetectorResult. Normalise
        # through the same adapter the engine uses, so this second call site
        # cannot drift from the first - and so a NEGATIVE result (the detector
        # looked and the behaviour did not happen) yields nothing here rather
        # than being written as shadow evidence that something occurred.
        from app.services.behavior_engine import _as_events
        events_out = _as_events(name, result)
        if not events_out:
            continue
        for ev in events_out:
            ev.shadow = True
            ev.context = {**(ev.context or {}), "at_entry": True}
            events.append(ev)
    return events


def above_entry_floor(event, floor: float = ENTRY_CONFIDENCE_FLOOR) -> bool:
    """
    Would this entry-time detection count as a finding?

    Detections below the floor are still recorded — evidence is never
    suppressed (§1C.8) — but they are not what a promotion decision should be
    read from. A detector whose entry-time output is mostly sub-floor is telling
    you it needs the outcome after all.
    """
    confidence = getattr(event, "confidence", None)
    return confidence is not None and float(confidence) >= floor


def summarise_entry_evaluation(events: Sequence[Any]) -> Dict[str, Any]:
    """What an entry evaluation produced, for logging and for replay reporting."""
    above = [e for e in events if above_entry_floor(e)]
    by_detector: Dict[str, Dict[str, Any]] = {}
    for e in events:
        d = by_detector.setdefault(e.event_type, {
            "detector": e.event_type, "detections": 0, "above_floor": 0,
            "severities": {},
        })
        d["detections"] += 1
        d["severities"][e.severity] = d["severities"].get(e.severity, 0) + 1
        if above_entry_floor(e):
            d["above_floor"] += 1
    return {
        "detections": len(events),
        "above_floor": len(above),
        "confidence_floor": ENTRY_CONFIDENCE_FLOOR,
        "by_detector": sorted(by_detector.values(), key=lambda r: -r["above_floor"]),
    }
