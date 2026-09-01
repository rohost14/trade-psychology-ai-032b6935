"""
BehaviorEngine — Unified Real-Time Behavioral Detection (Phase 3 — PRODUCTION)

Single source of truth for all behavioral pattern detection.
Frontend patternDetector.ts has been removed — backend is the only engine.

Architecture:
  - Session-scoped (today IST only)
  - Context loaded once per call (3 DB queries shared across all 15 detectors)
  - All detectors are pure (no DB access inside detectors)
  - Strategy-aware: suppresses false alerts on hedge/multi-leg strategy legs
  - Zero hardcoded constants — all thresholds from ctx.thresholds (trading_defaults.py)

Threshold source: app.core.trading_defaults.get_thresholds()
Research basis: SEBI FY2022-24, NSE market data, behavioral finance research.
See docs/validation/18_behavioral_engine_research_plan.md for full documentation.

Severity vocabulary:
  "danger"  — HIGH risk, action required
  "caution" — MEDIUM risk, awareness needed

Patterns (real-time, per CompletedTrade). Numbering is historical — gaps are
retirements, not omissions; detector_registry.REGISTRY is the authority:
  2.  revenge_trade
  3.  overtrading_burst          (burst + daily count)
  5.  rapid_reentry
  7.  martingale_behaviour
  9.  rapid_flip
  10. excess_exposure
  11. session_meltdown
  12. fomo_entry                  (any-time underlying scatter, not just market open)
  13. no_stoploss                 (expiry-day modifier)
  15. winning_streak_overconfidence
  16. options_direction_confusion (CE→PE flip on same underlying within 10 min)
  18. iv_crush_behavior           (fast large premium loss = buying into high IV)
  21. end_of_session_mis_panic    (MIS entries after 15:10 IST — forced 10-min exit)
  22. post_loss_recovery_bet      (one oversized position after 2+ consecutive losses)
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional, Dict, Any

from app.core.severity import SEVERITY_ORDER
from app.core import session_facts
from app.core.session_facts import SessionFacts
from app.core.detector_result import (
    DetectorResult,
    Layer,
    abstained,
    not_detected,
)
from app.core.position_fills import (
    PositionFill,
    adverse_adds,
    deepens_each_time,
)
from app.core.threshold_recorder import RecordingThresholds
from app.core.account_risk import AccountRisk, freeze_for_session, resolve_account_risk
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.completed_trade import CompletedTrade
from app.models.trading_session import TradingSession
from app.models.risk_alert import RiskAlert
from app.models.behavior_event import BehaviorEvent as BehaviorEventRecord
from app.models.strategy_group import StrategyGroup
from app.services.detector_registry import REGISTRY, BY_NAME
from app.services.trading_session_service import TradingSessionService
from app.core.risk_quantities import quantities_for_trade

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")

#: Exit order types meaning a stop-loss was resting on the position and fired.
#: Written out separately in panic_exit and no_stoploss until 2026-08-24; one
#: definition so the two cannot drift apart. Values unchanged.
_STOP_ORDER_TYPES = frozenset({"SL", "SL-M", "SLM", "SL-MKT"})

# Detector code version, stored on every alert (Engine v2 Appendix A.2).
# Bump on any detection-logic change so alerts remain attributable to the
# logic that produced them.
ENGINE_VERSION = "1.1.0"

# The per-pattern risk weights, the 0-100 session score they fed, and the
# Stable→Pressure→Tilt→Breakdown state machine were removed 2026-08-13.
#
# They were derived state with no consumer: nothing rendered the score, and
# `docs/GLOBALS_DERIVATION.md` measured the weights against a year of real
# trades — rank agreement with what the patterns actually cost was 0 of 16,
# and the mean weight was the same (17.1 vs 17.8) for patterns that predicted
# loss and patterns that did not. The escalation they expressed is a forecast,
# and the data does not support one.
#
# Detectors never read them (A.10 derived-state ban), so nothing about which
# alerts fire changed. Death spiral (L2) counts nature domains, not this score.


# ---------------------------------------------------------------------------
# Internal data classes
# ---------------------------------------------------------------------------

@dataclass
class DetectedEvent:
    event_type: str
    severity: str       # "info" | "caution" | "danger" | "critical" (info = analytics-only, no user alert)
    message: str
    context: Dict[str, Any] = field(default_factory=dict)
    risk_delta: Decimal = Decimal("0")
    confidence: Optional[float] = None  # 0-100; None → derived from data quality
    suppressed_reason: Optional[str] = None  # e.g. "strategy_group" — event recorded, no alert
    # Feature-flag shadow marker: set by the engine when the emitting detector is
    # in shadow/canary-dark mode. Recorded as evidence, but never alerts or scores.
    shadow: bool = False
    # Optional detector-supplied idempotency discriminator. When set, it (instead of
    # context['rule']) disambiguates the BehaviorEvent idempotency key — lets a
    # detector legitimately emit more than one event for the same trade.
    discriminator: Optional[str] = None
    # The thresholds this detector read, with the ladder rung each resolved from.
    # Filled in by the engine, never by the detector - see threshold_recorder.
    # Stored on the BehaviorEvent so an alert can be explained against the numbers
    # it was judged by, which is no longer answerable by reading a constant out of
    # a file: personal baselines move, and the ladder resolves per session.
    thresholds_used: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DetectionResult:
    alerts: List[RiskAlert]
    events: List["BehaviorEventRecord"]  # ALL detections incl. info/suppressed — caller persists
    session_id: Optional[UUID]


def _as_events(detector: str, result) -> Optional[List["DetectedEvent"]]:
    """
    Normalise whatever a detector returned into the list the engine persists.

    Accepts, in order of how much the detector has to say:

      None                 nothing happened, and nothing is recorded
      DetectedEvent        the current contract, passed through untouched
      list[DetectedEvent]  the constitution detector, several rules at once
      DetectorResult       the new contract

    WHY AN ABSTENTION BECOMES A RECORDED EVENT

    `Optional[DetectedEvent]` makes `None` mean both "the behaviour did not
    occur" and "I could not see well enough to say", which is why nobody could
    tell whether three detectors being silent across 203 replayed sessions was
    correct. A DetectorResult that abstained is therefore recorded as an `info`
    event carrying its reason: `info` never notifies, so this changes nothing a
    trader sees while making the distinction measurable.

    A NEGATIVE result - the detector looked and the behaviour genuinely did not
    happen - records nothing, exactly as `None` does today. Recording every
    non-detection for 27 detectors on every trade would be a write amplification
    with no reader.
    """
    if result is None:
        return None
    if isinstance(result, DetectedEvent):
        return [result]
    if isinstance(result, list):
        return result
    if isinstance(result, DetectorResult):
        return _events_from_result(detector, result)
    logger.error(
        "[BehaviorEngine] %s returned %s, which is neither a DetectedEvent nor a "
        "DetectorResult", detector, type(result).__name__
    )
    return None


def _events_from_result(detector: str, result: "DetectorResult") -> Optional[List["DetectedEvent"]]:
    """Project a DetectorResult onto the DetectedEvent the persistence path expects."""
    from app.core.evidence import Verdict as _Verdict

    if result.evidence.verdict is _Verdict.NEGATIVE:
        return None

    context: Dict[str, Any] = dict(result.context)
    # The measurements are the explanation: each carries its own denominator and
    # what that denominator was, so the alert reconstructs from stored evidence
    # rather than from its own prose.
    if result.measurements:
        context["_measurements"] = {
            name: {
                "value": m.value,
                "denominator": m.denominator,
                "denominator_label": m.denominator_label,
                "quality": m.quality.value if m.quality else None,
                "sample_size": m.sample_size,
            }
            for name, m in result.measurements.items()
        }
    if result.layer is not None:
        # Which layer judged this. A safety finding and a personal-deviation
        # finding are different claims and must stay distinguishable downstream.
        context["_layer"] = result.layer.value

    # A DetectorResult states its verdict deliberately. An `info` that comes from
    # a contract - an abstention, or a matrix cell that says "recorded, never
    # notified" - is EVIDENCE, and must not be mistaken for the confidence-demoted
    # noise the write gate exists to discard.
    context["_verdict"] = "abstained" if result.abstained else "stated"

    if result.abstained:
        context["_abstained"] = {
            "reason": result.evidence.reason.value
            if result.evidence.reason else "unknown",
            "detail": result.evidence.detail,
        }
        return [DetectedEvent(
            event_type=detector,
            severity="info",          # never notifies; recorded so it is countable
            message=result.message or "Could not judge this trade.",
            context=context,
            confidence=result.confidence,
            discriminator="abstained",
        )]

    return [DetectedEvent(
        event_type=detector,
        severity=result.severity or "info",
        message=result.message or "",
        context=context,
        confidence=result.confidence,
    )]


def _evidence_for(e: "DetectedEvent") -> Dict[str, Any]:
    """
    What gets stored so the alert can be explained later.

    The detector's own context, plus the thresholds it was judged against and
    where each of those came from. Kept under a reserved `_thresholds` key so it
    cannot collide with a detector's own field, and omitted entirely when the
    detector read no thresholds - an empty dict would imply "judged against
    nothing", which is a different claim from "reads no thresholds".
    """
    evidence = dict(e.context)
    if e.suppressed_reason:
        evidence["_suppressed"] = e.suppressed_reason
    if e.thresholds_used:
        evidence["_thresholds"] = e.thresholds_used
    return evidence


# Data quality → deterministic-detector confidence (master §1.3: for arithmetic
# detectors, confidence ≈ data quality).
DATA_QUALITY_CONFIDENCE = {"GOOD": 100.0, "PARTIAL": 75.0, "UNKNOWN": 50.0, "INVALID": 0.0}


@dataclass
class EngineContext:
    broker_account_id: UUID
    session: TradingSession
    completed_trade: CompletedTrade
    session_trades: List[CompletedTrade]
    thresholds: Dict[str, Any]
    strategy_group: Optional[StrategyGroup] = None
    # order_type values of the exit fills for the current completed_trade
    # (e.g. ["MKT"], ["SL"], ["SL-M", "MKT"]).  Empty when exit_trade_ids unknown.
    exit_order_types: List[str] = None  # type: ignore[assignment]
    # P2 shadow (Runtime Architecture Migration): fold-derived session state,
    # computed alongside the legacy recompute and compared per trade. Detectors
    # do NOT read this yet - cutover happens detector-by-detector once shadow
    # mismatch count stays zero across live sessions.
    session_state: Optional[object] = None
    # The session's canonical facts INCLUDING completed_trade: P&L, trade count,
    # loss/win streak, peak and drawdown. One definition, in app/core/session_facts.
    # Detectors read these instead of each recomputing their own version - which is
    # how four different answers to "how many losses in a row" got shipped.
    facts: Optional[SessionFacts] = None
    # The account-size denominator for this session, resolved once and frozen.
    # Detectors do NOT read this yet - no detector has been migrated. It is here
    # so that when one is, the number it divides by is the same number the rest
    # of the session was measured against, and is recorded on the session row.
    account_risk: Optional[AccountRisk] = None
    #: The trader's profile, for detectors that read their own baseline
    #: metrics. Loaded once in _load_context; previously it was fetched and
    #: then discarded after thresholds were resolved.
    profile: Optional[object] = None
    #: BROKER margin for this position, captured live while it was open, or
    #: None. Resolved ONCE per engine run rather than per detector - a detector
    #: is synchronous and must not issue its own query. None is a normal state,
    #: not an error: no observation exists for historical trades, and the
    #: capital-relative detectors then abstain.
    broker_margin: Optional[object] = None
    #: The fill sequence of THIS position, oldest first, straight from
    #: position_ledger. Empty for a single-entry position - which is ~90% of
    #: them - so only the detectors that need the sequence pay for it.
    #:
    #: A CompletedTrade folds every entry into one avg_entry_price, so without
    #: this an averaging-down ladder is invisible: 1 lot @50, add @40, add @30
    #: arrives as a single row at 40.
    position_fills: List[PositionFill] = field(default_factory=list)

    def __post_init__(self):
        # Derive rather than require. A context assembled anywhere - the engine,
        # a test, a future caller - has the same facts as any other, instead of
        # detectors silently seeing a streak of zero because whoever built the
        # context did not know to pass one.
        if self.facts is None:
            self.facts = session_facts.derive(
                list(self.session_trades) + [self.completed_trade]
            )

    @property
    def concluded_before_entry(self) -> List[CompletedTrade]:
        """
        Today's trades whose OUTCOME WAS KNOWN when this trade was entered.

        `session_trades` answers "did this happen in the session by now" -
        OCCURRED. It is the right relation for counting, and a trade entered
        after this one but closed before it is still one of today's trades.

        It is the WRONG relation for a causal claim. A detector whose message
        says "after X, you did Y" is asserting that the trader could see X when
        they decided Y, and that is only true if X had CLOSED STRICTLY BEFORE
        this position was ENTERED.

        The distinction is not academic. Before this property existed,
        `martingale_behaviour` built its run of consecutive losses straight from
        `session_trades`, and 9 of its 32 firings on the reference book rested on
        a loss that concluded AFTER the entry it explained - one of them by 125
        minutes. A live danger-tier alert named a cause that had not happened.

        Strictly `<`, not `<=`. A position closed in the same instant as the next
        was entered was not information the trader acted on.
        (`constitution_violation`'s cooldown rule still spells this `<=` inline;
        the two disagree only at identical timestamps, and which is right is
        recorded as open rather than decided here.)

        WHAT THIS DELIBERATELY DOES NOT COVER: concurrency. Two legs of a
        straddle entered in the same minute are one decision expressed as two
        rows, and are neither prior nor subsequent. They are excluded here
        because they did not conclude first - which is correct - but nothing yet
        NAMES them. See docs/patterns/00-shared/TEMPORAL_CONTRACT_INVESTIGATION.md.
        """
        entry = getattr(self.completed_trade, "entry_time", None)
        if entry is None:
            return []
        ct_id = getattr(self.completed_trade, "id", None)
        return sorted(
            (t for t in self.session_trades
             if t.id != ct_id
             and getattr(t, "exit_time", None) is not None
             and t.exit_time < entry),
            key=lambda t: t.exit_time,
        )


# ---------------------------------------------------------------------------
# BehaviorEngine
# ---------------------------------------------------------------------------

class BehaviorEngine:
    """
    Unified real-time behavioral detection engine.
    analyze() called once per CompletedTrade (after FIFO closes a position).
    """

    async def analyze(
        self,
        broker_account_id: UUID,
        completed_trade: CompletedTrade,
        db: AsyncSession,
        profile=None,
        source: str = "webhook",  # webhook | bulk_sync | unknown — drives data quality
    ) -> DetectionResult:
        try:
            today_ist = datetime.now(ZoneInfo("Asia/Kolkata")).date()
            session = await TradingSessionService.get_or_create_session(
                broker_account_id, today_ist, db
            )

            ctx = await self._load_context(
                broker_account_id, completed_trade, session, db, profile
            )
            # Resolve per-detector feature flags once for this run (registry
            # defaults + DB overrides, Redis-cached). Drives off/shadow/canary/on.
            from app.services.detector_flag_service import detector_flags as _detector_flags
            flags = await _detector_flags.get_flags(db)
            events = self._run_all_detectors(ctx, flags)

            now = datetime.now(timezone.utc)
            # detected_at = the trade's own exit time, never processing time.
            # A trade synced at 17:05 that closed at 14:20 gets detected_at 14:20.
            trade_time = completed_trade.exit_time or now

            # ── Data quality (A.6) ────────────────────────────────────────
            # webhook = live single-trade path; bulk_sync = historical replay
            # (state reconstructed, order context may be stale); unknown =
            # LIMIT-1 fallback. Missing exit order types degrades one level.
            data_quality = {"webhook": "GOOD", "bulk_sync": "PARTIAL"}.get(source, "UNKNOWN")
            if data_quality == "GOOD" and not ctx.exit_order_types:
                data_quality = "PARTIAL"
            default_confidence = DATA_QUALITY_CONFIDENCE.get(data_quality, 50.0)

            # ── Alerts: notification records ──────────────────────────────
            # info severity and suppressed events never alert — but ALL events
            # are recorded below (§1C.8: suppression is notification-layer only).
            alerts = []
            for e in events:
                # info = analytics-only; suppressed = notification withheld;
                # shadow = dark-launched detector — none of these alert.
                if e.severity == "info" or e.suppressed_reason or e.shadow:
                    continue
                alerts.append(RiskAlert(
                    id=uuid4(),  # explicit id so events can link pre-flush
                    broker_account_id=broker_account_id,
                    pattern_type=e.event_type,
                    severity=e.severity,
                    message=e.message,
                    details={**e.context, "exchange": completed_trade.exchange},
                    trigger_trade_id=None,
                    trigger_completed_trade_id=completed_trade.id,
                    detector_version=self._detector_version(e.event_type),
                    confidence=(min(e.confidence, default_confidence)
                                if e.confidence is not None else default_confidence),
                    detected_at=trade_time,
                ))

            # ── BehaviorEvents: evidence records for EVERY detection ──────
            # Addendum #3: snapshot only for danger/critical (~5-10% of
            # events) - audit of what the engine saw when data later changes.
            # 80-90% write-volume reduction on the heaviest column.
            input_snapshot = {
                "completed_trade_id": str(completed_trade.id),
                "session_trade_ids": [str(t.id) for t in ctx.session_trades],
                "source": source,
            }
            behavior_events = [
                BehaviorEventRecord(
                    broker_account_id=broker_account_id,
                    detector=e.event_type,
                    # P0 fix #1: deterministic key makes retries + bulk-sync
                    # re-processing insert-safe (rule disambiguates the
                    # multi-event constitution detector).
                    idempotency_key=(
                        f"{e.event_type}:{completed_trade.id}:"
                        f"{e.discriminator if e.discriminator is not None else (e.context or {}).get('rule', '')}"
                    ),
                    detector_version=self._detector_version(e.event_type),
                    severity=e.severity,
                    confidence=(min(e.confidence, default_confidence)
                                if e.confidence is not None else default_confidence),
                    data_quality=data_quality,
                    message=e.message,
                    evidence=_evidence_for(e),
                    input_snapshot=(input_snapshot
                                    if e.severity in ("danger", "critical") else None),
                    shadow=e.shadow,
                    trigger_completed_trade_id=completed_trade.id,
                    detected_at=trade_time,
                )
                for e in events
            ]

            # `update_risk_score` used to be called here, and its `db.flush()`
            # was the only thing persisting the `session.session_pnl` computed
            # `update_risk_score` used to be called here and its `db.flush()`
            # was documented as what persisted the `session.session_pnl` set in
            # `_load_context`. It was not: that call was conditional on
            # `total_delta != 0`, so a trade that fired no events never flushed
            # and session_pnl persisted anyway — every caller commits
            # (trade_tasks.py:1134/1422, alertlab inject.py:263), and the commit
            # flushes it. Adding an unconditional flush here instead made the
            # replay 5x slower: one long-lived session accumulates an identity
            # map across the whole year, so a per-trade flush turns O(n) work
            # into O(n²). Left to the caller's commit, which is where it was.

            if events:
                logger.info(
                    f"[BehaviorEngine] {broker_account_id} | "
                    f"{completed_trade.tradingsymbol} | "
                    f"{len(events)} patterns | "
                    f"{[e.event_type for e in events]}"
                )

            return DetectionResult(
                alerts=alerts,
                events=behavior_events,
                session_id=session.id,
            )

        except Exception as e:
            logger.error(f"[BehaviorEngine] analyze failed: {e}", exc_info=True)
            # E3: a swallowed failure here silently drops this trade's detection
            # (no alerts/events/score). Count it so the loss is visible on the
            # engine-metrics admin page instead of vanishing. Best-effort.
            try:
                from app.core.metrics import incr as _incr
                _incr("engine_analyze_failed")
            except Exception:
                pass
            return DetectionResult(alerts=[], events=[], session_id=None)

    @staticmethod
    def _detector_version(pattern_type: str) -> str:
        """Per-detector version from the registry, falling back to engine version."""
        spec = BY_NAME.get(pattern_type)
        if spec:
            return spec.version
        from app.services.detector_registry import ALIASES
        return ALIASES.get(pattern_type, ENGINE_VERSION)

    # ── Context loader ─────────────────────────────────────────────────────

    async def _load_context(
        self,
        broker_account_id: UUID,
        completed_trade: CompletedTrade,
        session: TradingSession,
        db: AsyncSession,
        profile=None,
    ) -> EngineContext:
        # Phase 2 fix: no live caller ever passed profile, so get_thresholds(None)
        # ran on pure research defaults — user-declared limits (daily loss, trade
        # cap, position size) were silently ignored in production detection.
        # Fetch it here; also apply any pending constitution loosening that has
        # reached its next-session effective time.
        if profile is None:
            try:
                from app.models.user_profile import UserProfile as _UP
                prof_result = await db.execute(
                    select(_UP).where(_UP.broker_account_id == broker_account_id)
                )
                profile = prof_result.scalar_one_or_none()
                if profile is not None:
                    from app.services.constitution_service import ConstitutionService
                    await ConstitutionService.apply_pending_if_due(profile, db)
            except Exception as _p_err:
                logger.warning(f"[BehaviorEngine] profile load failed, using defaults: {_p_err}")

        session_start = session.market_open
        if session_start is None:
            from app.core.market_hours import get_session_boundaries, MarketSegment
            session_start, _ = get_session_boundaries(
                segment=MarketSegment.FNO,
                for_date=session.session_date,
            )

        # Query 1: this session's completed trades, excluding the one being
        # analysed — it travels separately as ctx.completed_trade.
        #
        # `as_of` bounds the load at THIS trade's exit, which is the moment the
        # engine is reconstructing. Without it the bulk-sync replay
        # (`run_behavior_engine_full_session`) showed every detector the rest of
        # the day — 50% of what they were handed on the reference book had not
        # happened yet — while the live postback path saw only what had closed.
        # Two paths, two answers, from one engine. This makes them the same
        # path. See `load_session_trades` for the measurement and for why the
        # bound is on exit and not on entry.
        session_trades = await session_facts.load_session_trades(
            db, broker_account_id, session.session_date,
            exclude_id=completed_trade.id,
            as_of=getattr(completed_trade, "exit_time", None),
        )

        # Thresholds resolve AFTER today's trades are loaded, so the ladder can
        # use rung 2 — comparisons against what this trader has done today. That
        # is what lets a brand-new account get a threshold that fits it instead
        # of a constant chosen for an imaginary average trader.
        # Resolve once, keeping the provenance the ladder produced. `get_thresholds`
        # returns only `.values` and throws the rest away, which is what made an
        # alert unexplainable after the fact.
        from app.core.threshold_resolution import resolve_thresholds
        _resolved = resolve_thresholds(profile, session_trades=session_trades)
        thresholds = RecordingThresholds(_resolved.values, _resolved.meta)

        # Query 2 (active cooldowns) REMOVED 2026-08-29 with `cooldown_violation`.
        # `ctx.active_cooldowns` had exactly one reader - that detector - so the
        # query ran on every completed trade to feed something now retired. The
        # Cooldown model, table, service and API are untouched; only this
        # per-trade read is gone.

        # Query 3: strategy group for this trade (must run before BehaviorEngine)
        strategy_group: Optional[StrategyGroup] = None
        try:
            from app.services.strategy_detector import get_group_for_trade
            strategy_group = await get_group_for_trade(completed_trade.id, db)
        except Exception as _sg_e:
            logger.debug(f"Strategy group lookup skipped: {_sg_e}")

        # Query 4: exit order types for the current trade (SL/SL-M detection)
        exit_order_types: List[str] = []
        if completed_trade.exit_trade_ids:
            from app.models.trade import Trade as _Trade
            from sqlalchemy import cast as _cast, String as _String, or_ as _or
            try:
                # F1. `exit_trade_ids` holds TWO identifier spaces depending on
                # which writer produced the row:
                #
                #   live ledger  -> Kite order ids   (position_ledger_service:892
                #                   writes e.fill_order_id)
                #   batch FIFO   -> Trade.id UUIDs   (pnl_calculator:570)
                #
                # This matched only Trade.id, so on the LIVE path it matched
                # nothing at all and exit_order_types came back empty for every
                # trade - silently, because an empty list is indistinguishable
                # from "no stop-loss was used".
                #
                # Matching both columns fixes the live path without rewriting
                # stored data or breaking rows written by the other writer.
                # Trade.order_id is indexed.
                ot_result = await db.execute(
                    select(_Trade.order_type).where(_or(
                        _cast(_Trade.id, _String).in_(completed_trade.exit_trade_ids),
                        _Trade.order_id.in_(completed_trade.exit_trade_ids),
                    ))
                )
                exit_order_types = [r[0] for r in ot_result.all() if r[0]]
            except Exception as _ot_err:
                logger.debug(f"Exit order type lookup skipped: {_ot_err}")

        # Query 5: the fill sequence of THIS position, for detectors that need
        # to see inside it rather than only its aggregate.
        #
        # Gated on num_entries > 1, because a single-entry position has no
        # sequence to read - about 90% of positions on a real book - so nine
        # trades in ten never issue this at all. Served exactly by
        # idx_position_ledger_account_symbol (broker_account_id, tradingsymbol,
        # occurred_at), which already exists.
        #
        # One query inside a run that is already per-CompletedTrade: it cannot
        # become an N+1, because there is no loop over trades to nest it in.
        position_fills: List[PositionFill] = []
        if (completed_trade.num_entries or 1) > 1 and completed_trade.entry_time:
            from app.models.position_ledger import PositionLedger as _PL
            try:
                _pl_result = await db.execute(
                    select(_PL)
                    .where(
                        _PL.broker_account_id == broker_account_id,
                        _PL.tradingsymbol == completed_trade.tradingsymbol,
                        _PL.occurred_at >= completed_trade.entry_time,
                        _PL.occurred_at <= (completed_trade.exit_time
                                            or completed_trade.entry_time),
                    )
                    .order_by(_PL.occurred_at)
                )
                position_fills = [PositionFill.from_ledger(r)
                                  for r in _pl_result.scalars()]
            except Exception as _pf_err:
                # Best-effort context, never a precondition. A detector that
                # cannot see the sequence reports nothing rather than guessing.
                logger.debug(f"Position fill lookup skipped: {_pf_err}")

        # ── Session facts: this is their ONE owner ───────────────────────────
        # Both are derived fresh from the session's CompletedTrades on every
        # call. Deriving beats incrementing here because a replay, a late fill or
        # a retried task all recompute to the same answer, where increments
        # double-count.
        #
        # session_pnl: add_session_pnl() existed for this and had zero callers.
        # trade_count: had NO writer at all. Two live consumers read it anyway -
        #   the session log rendered "0 trades" for every session, and
        #   session_intent compared actual_trades (always 0) against the trader's
        #   declared limit, so the end-of-day comparison always reported that they
        #   had kept to it. Found by auditing ownership, not by a test.
        facts = session_facts.derive(list(session_trades) + [completed_trade])
        session.session_pnl = facts.pnl
        session.trade_count = facts.trades

        # ── Account-size denominator: resolved once per session, then frozen ──
        # Every "how much of the account did this cost" question divides by this
        # one number. Freezing it is a correctness decision before it is a
        # performance one: a deposit at 13:00 must not retroactively change what
        # the morning's alerts meant. It is also why this costs one query on the
        # first trade of a session and none afterwards - the frozen path reads
        # the session row that is already loaded.
        #
        # It can resolve to ABSTAIN, and that is a real answer, not a failure: a
        # trader whose equity we cannot see gets no account-relative claims,
        # rather than a fabricated denominator. The trade-relative and structural
        # families still work on their first ever trade - see core/measurements.
        try:
            account_risk = await resolve_account_risk(
                broker_account_id, db, session=session, profile=profile
            )
            await freeze_for_session(session, account_risk, db)
        except Exception as _ar_err:
            # Never let the denominator take the analysis down with it.
            logger.warning(f"[BehaviorEngine] account risk unresolved: {_ar_err}")
            account_risk = None

        # ── P2 shadow: SessionState fold vs legacy recompute ──────────────
        # Zero extra IO (folds rows already loaded). A mismatch means the
        # fold and the rescan disagree about reality - the exact drift the
        # migration gate must catch. Counted, never raised.
        shadow_state = None
        try:
            from app.services.state.session_state import SessionState
            from app.core.metrics import incr as _minc
            shadow_state = SessionState.rebuild(list(session_trades) + [completed_trade])
            _minc("state_shadow_checked")
            if shadow_state.session_pnl != session.session_pnl:
                _minc("state_shadow_mismatch")
                logger.error(
                    f"[state-shadow] session_pnl mismatch for {broker_account_id}: "
                    f"fold={shadow_state.session_pnl} legacy={session.session_pnl} "
                    f"trade={completed_trade.id}"
                )
        except Exception as _sh_err:
            logger.warning(f"[state-shadow] compute failed (non-fatal): {_sh_err}")

        # BROKER margin, if one was captured while this position was open. Never
        # fatal: a missing observation, an unapplied migration 081 and a failed
        # query are all simply "no broker figure", and the risk layer abstains.
        broker_margin = None
        try:
            from app.services.broker_margin_service import resolve_for_trade
            broker_margin = await resolve_for_trade(completed_trade, db)
        except Exception as _bm_err:                                # noqa: BLE001
            logger.debug("broker margin unavailable (non-fatal): %s", _bm_err)

        return EngineContext(
            broker_account_id=broker_account_id,
            session=session,
            completed_trade=completed_trade,
            session_trades=session_trades,
            thresholds=thresholds,
            strategy_group=strategy_group,
            exit_order_types=exit_order_types,
            position_fills=position_fills,
            session_state=shadow_state,
            facts=facts,
            account_risk=account_risk,
            profile=profile,
            broker_margin=broker_margin,
        )

    # ── Run all detectors ──────────────────────────────────────────────────

    # Patterns suppressed for strategy legs (hedge legs fire false positives on these)
    _STRATEGY_SUPPRESSED = frozenset({
        "revenge_trade",
        "martingale_behaviour",
        # Suppress for multi-leg hedges: buying a CE + PE simultaneously is
        # not rapid re-entry, missing stop-loss, or a recovery bet — it is a
        # defined strategy (straddle/strangle/spread). strategy_group is set by
        # get_group_for_trade() when the trade is part of a detected structure.
        "rapid_reentry",
        "no_stoploss",
        "post_loss_recovery_bet",
    })

    def _run_all_detectors(
        self, ctx: EngineContext, flags: Optional[Dict[str, tuple]] = None
    ) -> List[DetectedEvent]:
        """
        Iterate the Detector Registry (A.1) in declaration order.

        Feature flags (migration 068) gate each detector by its resolved mode:
          off    → detector method is not called
          shadow → method runs; its events are tagged shadow=True (recorded as
                   evidence but never alert and never move any score)
          on     → live

        Suppression (strategy legs, options overlap) marks events with
        suppressed_reason instead of dropping them — the BehaviorEvent is
        always recorded, only the notification is withheld (master §1C.8).
        """
        from app.services.detector_flag_service import detector_flags, EFFECTIVE_OFF, EFFECTIVE_SHADOW

        flags = flags or {}
        events = []
        for spec in REGISTRY:
            # trigger="entry" detectors fire on the fill, not when the position
            # closes, and are dispatched from the entry-batch flush instead. The
            # field was descriptive until 2026-08-24; this is the first detector
            # that needed it to mean something. Every other spec says "exit", so
            # nothing else changes.
            if spec.trigger == "entry":
                continue
            mode = detector_flags.resolve(spec.name, ctx.broker_account_id, flags)
            if mode == EFFECTIVE_OFF:
                continue
            detector = getattr(self, spec.method, None)
            if detector is None:
                logger.error(f"[BehaviorEngine] registry method missing: {spec.method}")
                continue
            try:
                # Note which thresholds this detector reads, so the alert it
                # produces can be explained against the numbers it was actually
                # judged by. Those numbers move now - baselines adapt, the ladder
                # resolves per session - so "the constant is in the file" stopped
                # being an answer to "why did this fire".
                recording = isinstance(ctx.thresholds, RecordingThresholds)
                if recording:
                    ctx.thresholds.start_recording()

                result = detector(ctx)

                if recording:
                    used = ctx.thresholds.provenance()

                # A detector may return DetectedEvent(s) as they all do today, or
                # a DetectorResult, which additionally carries which layer judged
                # it, the measurements behind the verdict, and - the point of the
                # type - the difference between "did not happen" and "could not
                # tell". Both are accepted during the migration; no detector has
                # been converted yet.
                result = _as_events(spec.name, result)

                if not result:
                    continue
                # constitution_violation returns a list (multiple rules can
                # breach on one trade); everything else returns a single event.
                for event in (result if isinstance(result, list) else [result]):
                    if mode == EFFECTIVE_SHADOW:
                        # Dark-launched detector: record evidence, but never alert
                        # or score. Tag every event this method produced.
                        event.shadow = True
                    if ctx.strategy_group and event.event_type in self._STRATEGY_SUPPRESSED:
                        event.suppressed_reason = f"strategy_group:{ctx.strategy_group.strategy_type}"
                        logger.debug(
                            f"[BehaviorEngine] suppressed {event.event_type} — "
                            f"trade is part of {ctx.strategy_group.strategy_type}"
                        )
                    if recording and used and not event.thresholds_used:
                        event.thresholds_used = used
                    events.append(event)
            except Exception as e:
                logger.warning(f"[BehaviorEngine] {spec.method} failed: {e}")

        # (Phase 4: the old iv_crush/premium_destruction overlap dedup is gone —
        # they are one pattern now: premium_loss_event.)

        # Constitution suppression (master §1C.8): when the user's OWN rule is
        # BREACHED (danger+), the overlapping behavioral pattern's notification
        # is withheld — "you violated YOUR rule" is the stronger message. The
        # behavioral event is still recorded and still feeds state/scores.
        _CONSTITUTION_PAIRS = {
            "cooldown":               ("revenge_trade",),
            "daily_trades":           ("overtrading_burst", "daily_overtrading"),
            "max_trade_risk":         ("excess_exposure",),
            "daily_loss":             ("session_meltdown",),
        }
        breached_rules = {
            e.context.get("rule") for e in events
            if e.event_type == "constitution_violation"
            and e.severity in ("danger", "critical")
            and not e.suppressed_reason
        }
        if breached_rules:
            suppressible = {p for r in breached_rules for p in _CONSTITUTION_PAIRS.get(r, ())}
            for e in events:
                if e.event_type in suppressible and not e.suppressed_reason:
                    e.suppressed_reason = "constitution_breach"
                    logger.debug(
                        f"[BehaviorEngine] {e.event_type} notification suppressed — "
                        f"constitution rule breached ({breached_rules})"
                    )

        self._consolidate(events)
        return events

    # ── One trade, one story ──────────────────────────────────────────────

    #: Detectors that describe the SAME underlying fact. Firing all of them is
    #: not three findings, it is one finding said three times.
    #:
    #: Within a family the FIRST name that fired wins and the rest are recorded
    #: as evidence — ordered most specific first, because "you are doubling
    #: after every loss" tells a trader more than "your position size is
    #: rising", and the specific one is the harder claim to make.
    _FAMILIES = (
        ("sizing after losses", (
            "martingale_behaviour",       # a doubling progression — the strongest claim
            "post_loss_recovery_bet",     # one oversized bet after losses
            # `size_escalation` was the third member until 2026-08-27. Retired:
            # its premise was ordering, and ordering fired less than chance
            # (42 vs 49.7, p = 0.880). The two above keep the claim.
        )),
        ("going back to the same trade", (
            "same_symbol_obsession",      # the whole session on one instrument
            "revenge_trade",              # straight back in after a loss
            "rapid_reentry",              # info-tier anyway, but keeps the order honest
        )),
        ("the position is too big", (
            "excess_exposure",
            "overexposure",
            "portfolio_concentration",
            "capital_mismatch",
        )),
    )

    #: Alerts that are summaries of other alerts. A composite firing ALONGSIDE
    #: what it summarises is double-reporting by construction: it exists to say
    #: "several things are going wrong at once", so the several things do not
    #: also need to be said.
    #: Only death_spiral. It is genuinely built FROM other detectors — it counts
    #: how many behavioural domains are deteriorating — so firing it beside its
    #: own inputs is double-reporting.
    #:
    #: session_meltdown was in this list and should never have been. It is a P&L
    #: threshold ("83% of your daily limit used"), not a summary of anything, and
    #: it fired on 41 of 61 real sessions. On every one of those days it absorbed
    #: every other behavioural alert — same_symbol_obsession went from nine days
    #: of behaviour in the tradebook to a single alert. A consolidation rule that
    #: silences the product on exactly the days it matters most is worse than the
    #: noise it was written to fix.
    _COMPOSITES = ("death_spiral",)

    def _consolidate(self, events: List[DetectedEvent]) -> None:
        """
        Collapse several descriptions of one behaviour into the strongest one.

        Seven alerts on a single closing trade was the real-world result of
        every detector answering independently and nothing asking how the answers
        read together. Three of those seven were the same sentence — size grew
        after losses — and two more were one rule-breach alert per rule broken.

        Nothing is deleted. A folded detection keeps its BehaviorEvent with a
        `_suppressed` marker, so it still appears in the suppression trace, still
        counts for detection-quality metrics, and can still be read back. It
        stops being shouted, which is different from being hidden.

        Deliberately NOT a cap on total alerts. A cap discards whichever
        detection happens to be last and gives no reason; this folds by meaning,
        so what survives is chosen rather than arbitrary.
        """
        live = [e for e in events if not e.suppressed_reason and not e.shadow
                and e.severity != "info"]
        if len(live) < 2:
            return

        fired = {e.event_type for e in live}

        # 1. A composite absorbs the alerts it summarises.
        composite = next((c for c in self._COMPOSITES if c in fired), None)
        if composite:
            for e in live:
                if e.event_type != composite and not e.suppressed_reason:
                    e.suppressed_reason = f"absorbed:{composite}"
            return

        # 2. Within a family, the most specific description wins.
        for label, members in self._FAMILIES:
            present = [m for m in members if m in fired]
            if len(present) < 2:
                continue
            winner = present[0]
            for e in live:
                if e.event_type in present[1:] and not e.suppressed_reason:
                    e.suppressed_reason = f"same_story:{winner}"
            logger.debug(
                f"[BehaviorEngine] {label}: kept {winner}, folded {present[1:]}"
            )

        # 3. Several rules broken on one trade is one alert, not one per rule.
        # The trader broke their constitution; which clauses is detail that
        # belongs inside that alert, not spread across several.
        breaches = [e for e in live
                    if e.event_type == "constitution_violation" and not e.suppressed_reason]
        if len(breaches) > 1:
            # Keep the most severe; on a tie the first, which is the order the
            # rules were evaluated in.
            keep = max(breaches, key=lambda e: SEVERITY_ORDER.index(e.severity)
                       if e.severity in SEVERITY_ORDER else 0)
            others = [e for e in breaches if e is not keep]
            rules = [e.context.get("rule") for e in breaches if e.context.get("rule")]
            keep.context = {**(keep.context or {}), "also_breached":
                            [r for r in rules if r != (keep.context or {}).get("rule")]}
            if len(rules) > 1:
                keep.message = (
                    f"{keep.message} "
                    f"({len(rules)} of your rules broke on this trade.)"
                )
            for e in others:
                e.suppressed_reason = "merged_into_rule_breach"

    # ── Pattern 2: Revenge trade ──────────────────────────────────────────

    # ── The A x B evidence model ──────────────────────────────────────────
    #
    # Two ordinal axes and a table. No score, no weights, no counting of signals.
    #
    #   A  how big was the thing they reacted to
    #   B  how much does the re-entry look like a reaction
    #
    # Each axis takes the HIGHEST level any frame establishes - a lattice join.
    # Two guarantees fall out of that structurally rather than by promise: an
    # abstaining frame can never lower a level, so missing equity cannot reduce
    # the severity of a large trade-relative loss; and personal history can only
    # raise a level, because no rule removes one. "This is normal for them" is
    # unreachable by construction.
    #
    # See docs/contracts/revenge_trade_implementation.md - frozen 23 Aug 2026.
    # Indexed [A][B]. B0 is absent by construction - the detector returns
    # NOT_DETECTED before reaching the table, because "these two trades were
    # unrelated" is a non-detection and recording it would write an event on
    # essentially every trade that follows a loss.
    _RT_MATRIX = {
        # A3 account-threatening
        3: {1: "danger", 2: "danger", 3: "critical"},
        # A2 large - a decided threshold was crossed
        2: {1: "caution", 2: "danger", 3: "danger"},
        # A1 measured, unjudged - we hold a number and have no sanctioned rule
        # for calling it significant, so claiming harm would decide significance
        # at the moment of use. B1 and B2 are therefore info: the abstention,
        # recorded and countable rather than shouted.
        #
        # B3 is caution, and that cell was decided from evidence rather than
        # taste. Auditing the eight sessions this detector used to alert on gave
        # eleven loss-to-re-entry pairs: five likely false positives, all of them
        # B1 re-entries into a DIFFERENT underlying; four ambiguous; and two
        # likely genuine. B3 occurred exactly ONCE in eleven, on a loss of 33% of
        # the premium, returning to the same strike two minutes later with 25%
        # more size, inside a session escalating 40 -> 40 -> 80 -> 100 -> 200
        # across four consecutive losses.
        #
        # An earlier revision made this info too, to suppress a trivial-loss case
        # that turned out to exist only in a unit test - B3 never co-occurred with
        # a trivial loss in the real book. Making it info removed the clearest
        # genuine sequence in the sample and suppressed no false positive, because
        # every false positive is B1 and no B3 cell can reach them.
        1: {1: "info", 2: "info", 3: "caution"},
        # A0 unmeasurable - every magnitude frame abstained, so the loss MIGHT
        # have been large and the structural claim is all the evidence there is.
        # Quieter at A1 than at A0 reads backwards until you see why: structure
        # alone can carry a claim, a number we are not licensed to interpret
        # cannot. This is the cold-start cell.
        0: {1: "info", 2: "info", 3: "caution"},
    }

    def _detect_revenge_trade(self, ctx: EngineContext) -> Optional[DetectorResult]:
        """
        A decision taken against the previous loss rather than on its own terms.

        REWRITTEN 2026-08-23 to the frozen contract. What changed and why:

        The old detector gated on `revenge_min_loss_inr`, which resolves to 1% of
        capital - so the bigger the account, the larger a loss had to be before
        the detector would look at it at all. Measured on 40 sessions with only
        capital changed: 8 alerts at Rs 50,000 and ZERO at Rs 5,00,000. Capital
        was being used to SUPPRESS. Account-relative measurement is a reason to
        fire, never a reason to stay quiet, so it moves to the safety trigger and
        is gone from the gate.

        It also summed invented points - 30 for a base case, 20 for this, 10 for
        that - into a confidence that decided whether the trader was told
        anything. That is the behaviour score in miniature and it is gone;
        severity is read from the matrix above and confidence is the shared
        weakest-link calculation.

        Frames degrade independently. With S1, S2 and every maturity requirement
        unresolved, the account, trade and personal frames all abstain and the
        detector still reports the structural fact - which is the cold-start
        behaviour the contract promises, not a degraded mode.
        """
        from app.core import confidence as _confidence
        from app.core import maturity as _maturity
        from app.core.evidence import Insufficiency, positive
        from app.core.instrument_risk import risk_basis
        from app.core.measurements import (
            UNMEASURABLE,
            loss_vs_account,
            loss_vs_risk_basis,
        )

        ct = ctx.completed_trade
        abstentions = {}
        measurements = {}

        # ── Structural gate ───────────────────────────────────────────────
        # Was this exact predicate spelled inline. Same semantics, one
        # definition - this detector was already right and its firing set must
        # not move (182 on the reference book, asserted in
        # tests/test_temporal_contract.py).
        prior = ctx.concluded_before_entry
        if not ct.entry_time or not prior:
            return not_detected("revenge_trade", "no closed trade to react to")

        last = prior[-1]
        last_pnl = Decimal(str(last.realized_pnl or 0))
        if last_pnl >= 0:
            return not_detected("revenge_trade", "the previous trade did not lose")

        if not last.exit_time:
            return abstained("revenge_trade", Insufficiency.MISSING_INPUT,
                             "the previous trade has no exit time")
        gap_min = (ct.entry_time - last.exit_time).total_seconds() / 60
        if gap_min < 0:
            return abstained("revenge_trade", Insufficiency.MISSING_INPUT,
                             "timestamps are out of order")

        prior_loss = abs(float(last_pnl))

        # ── A: trigger magnitude. Highest level any frame establishes ─────
        #
        # A1 is reached by MEASURABILITY, not by crossing a threshold. Measuring
        # a loss needs only a comparable denominator - risk_basis gives one for a
        # long option on trade one - while a threshold is needed to call the
        # result significant. Conflating the two made A1 unreachable and let a
        # Rs 120 scratch loss be treated exactly like a loss we could not see.
        a_level = 0

        # Account-relative. Abstains without equity, and S1 is unresolved, so it
        # abstains twice over today. Recorded both ways so the two reasons stay
        # distinguishable.
        acct = loss_vs_account(prior_loss, ctx.account_risk) if ctx.account_risk \
            else UNMEASURABLE
        measurements["loss_vs_account"] = acct
        s1 = ctx.thresholds.get("revenge_account_loss_pct")   # unresolved: absent
        if not acct.is_measurable:
            abstentions["account"] = "no usable account denominator"
        else:
            a_level = max(a_level, 1)          # measured
            if s1 is None:
                abstentions["account"] = "S1 undecided: no account-relative threshold"
            elif acct.value >= float(s1) / 100.0:
                a_level = max(a_level, 3)

        # Trade-relative, per instrument class. A spread's denominator is known to
        # be over-estimated, so loss_vs_risk_basis abstains rather than reporting
        # a ratio understated in a known direction.
        is_spread = ctx.strategy_group is not None
        basis = risk_basis(
            last.instrument_type, last.tradingsymbol or "", last.direction,
            float(last.avg_entry_price or 0), int(last.total_quantity or 0),
            is_spread=is_spread, exchange=last.exchange,      # F7
        )
        trade_m = loss_vs_risk_basis(prior_loss, basis)
        measurements["loss_vs_trade"] = trade_m
        s2 = ctx.thresholds.get(f"revenge_trade_loss_pct_{basis.instrument.value}")
        if not trade_m.is_measurable:
            abstentions["trade"] = f"denominator not comparable for {basis.instrument.value}"
        else:
            a_level = max(a_level, 1)          # measured
            if s2 is None:
                abstentions["trade"] = f"S2 undecided for {basis.instrument.value}"
            elif trade_m.value >= float(s2) / 100.0:
                a_level = max(a_level, 2)

        # Personal. maturity.assess returns UNAVAILABLE while M1 is undeclared, so
        # this abstains for every trader today.
        loss_metric = self._rt_metric(ctx, "own_loss_size")
        loss_maturity = _maturity.assess(loss_metric,
                                         ctx.thresholds.get("revenge_loss_min_sample"))
        if not loss_maturity.is_usable:
            abstentions["personal_loss"] = loss_maturity.describe()
        else:
            a_level = max(a_level, 1)          # measured against their own history
            p1 = ctx.thresholds.get("revenge_loss_percentile")
            marker = (loss_metric.get("percentiles") or {}).get(f"p{int(p1)}") if p1 else None
            if marker is None:
                abstentions["personal_loss"] = "P1 undecided: no percentile selected"
            elif prior_loss >= float(marker):
                a_level = max(a_level, 2)

        # ── B: reaction structure. Nested levels, never added ─────────────
        caution_window = ctx.thresholds.get("revenge_window_caution_min", 20)
        window_maturity = _maturity.assess(
            self._rt_metric(ctx, "reentry_after_loss_p25"),
            ctx.thresholds.get("revenge_gap_min_sample"),
        )
        if not window_maturity.is_usable:
            # The fallback carries its OWN provenance and is never relabelled as
            # personal - threshold_recorder already emits personalised: false with
            # the reason, and both non-mature states reuse that path.
            abstentions["personal_gap"] = window_maturity.describe()

        if gap_min > float(caution_window):
            # B0: outside the window, so these are two decisions rather than a
            # reaction. A non-detection, not evidence - recording it would write
            # an event on essentially every trade that follows a loss.
            return not_detected(
                "revenge_trade",
                f"re-entered {gap_min:.0f}min after the loss, outside the "
                f"{caution_window}min window",
            )

        b_level = 1                      # B1: inside the window
        try:
            from app.services.instrument_parser import parse_symbol as _ps
            same_underlying = (_ps(ct.tradingsymbol or "").underlying
                               == _ps(last.tradingsymbol or "").underlying)
            parsed = True
        except Exception:
            same_underlying = ct.tradingsymbol == last.tradingsymbol
            parsed = False

        # same_symbol IMPLIES same_underlying. One fact at two precisions, so
        # they are exclusive tiers of B2 rather than two observations - which is
        # why levels replaced points.
        if same_underlying or ct.tradingsymbol == last.tradingsymbol:
            b_level = 2
            # B3 needs no constant: bigger than the position that just lost.
            if (ct.total_quantity or 0) > (last.total_quantity or 0):
                b_level = 3

        severity = self._RT_MATRIX[a_level][b_level]

        # A declared cooldown breach is a fact about a COMMITMENT, not about harm.
        # It raises severity to at least caution and never on its own to danger.
        declared = ctx.thresholds.get("user_cooldown_min")
        declared_breach = bool(declared and gap_min < float(declared))
        if declared_breach and SEVERITY_ORDER.index(severity) < SEVERITY_ORDER.index("caution"):
            severity = "caution"

        # Confidence answers how well we could SEE this, never how bad it is.
        conf = _confidence.from_observables(
            data_quality=None,
            sample_confidences=[m.get("confidence") for m in
                                (loss_metric,) if m],
            inputs_parsed=parsed,
        )

        loc = "the same instrument" if ct.tradingsymbol == last.tradingsymbol \
            else last.tradingsymbol
        message = (f"Entered {ct.tradingsymbol} {gap_min:.0f}min after a "
                   f"Rs {prior_loss:,.0f} loss on {loc}.")
        if b_level == 3:
            message += " The new position is larger than the one that lost."

        return DetectorResult(
            detector="revenge_trade",
            evidence=positive("loss then re-entry", gap_minutes=round(gap_min, 1)),
            layer=Layer.SAFETY if a_level >= 2 else Layer.PERSONAL,
            severity=severity,
            confidence=conf,
            measurements=measurements,
            message=message,
            context={
                "gap_minutes": round(gap_min, 1),
                "prior_loss": float(last_pnl),
                "prior_symbol": last.tradingsymbol,
                "trigger_symbol": ct.tradingsymbol,
                "caution_window": caution_window,
                "a_level": a_level,
                "b_level": b_level,
                "instrument_class": basis.instrument.value,
                "denominator_kind": basis.kind.value,
                "declared_breach": declared_breach,
                "abstained_frames": abstentions,
            },
        )

    @staticmethod
    def _rt_metric(ctx: EngineContext, name: str):
        """One baseline metric record, or None. No thresholds, no defaults."""
        try:
            baseline = (getattr(ctx.profile, "detected_patterns", None) or {}).get("baseline")
            return ((baseline or {}).get("metrics") or {}).get(name)
        except Exception:
            return None

    # ── Pattern 3: Overtrading burst + daily count ────────────────────────

    def _detect_overtrading_burst(self, ctx: EngineContext) -> Optional[DetectedEvent]:
        ct = ctx.completed_trade
        if not ct.entry_time:
            return None

        from app.services.strategy_detector import count_structures as count_structures_fn

        burst_caution = ctx.thresholds.get("burst_trades_per_30min_caution", 5)
        burst_danger  = ctx.thresholds.get("burst_trades_per_30min_danger", 8)
        # The daily check reads `user_daily_trade_limit` — the number the trader
        # DECLARED — and not `daily_trade_limit`, which is the p75-derived line.
        # See Check 2 for why.
        declared_daily_limit = ctx.thresholds.get("user_daily_trade_limit")

        session_pnl = float(ctx.session.session_pnl or 0) if ctx.session else 0

        # ── Helpers ────────────────────────────────────────────────────────

        def _trade_entry(t) -> dict:
            """Single-trade dict for burst_trades / daily_trades context lists."""
            pnl = float(t.realized_pnl or 0)
            entry_ist = t.entry_time.astimezone(IST).strftime("%H:%M") if t.entry_time else None
            exit_ist  = t.exit_time.astimezone(IST).strftime("%H:%M")  if t.exit_time  else None
            return {
                "symbol":        t.tradingsymbol or "—",
                "entry_time_ist": entry_ist,
                "exit_time_ist":  exit_ist,
                "qty":           t.total_quantity or 0,
                "pnl":           round(pnl, 2),
                "is_loss":       pnl < 0,
            }

        def _burst_context(trades_in_window: list, include_loss_detail: bool = True) -> dict:
            """Build shared context for all burst-window alert paths."""
            all_trades = sorted(trades_in_window, key=lambda t: t.entry_time or datetime.min.replace(tzinfo=timezone.utc))
            pnls = [float(t.realized_pnl or 0) for t in all_trades]
            losing_pnls = [p for p in pnls if p < 0]
            entry_times = [t.entry_time for t in all_trades if t.entry_time]
            ctx_dict = {
                # Legs, and the decisions they represent. Both are kept: the
                # threshold is compared against structures, but the evidence
                # must still be able to show a trader their actual fills.
                "trades_in_window":    count_structures_fn(all_trades),
                "legs_in_window":      len(all_trades),
                "window_minutes":      30,
                "window_start_ist":    entry_times[0].astimezone(IST).strftime("%H:%M") if entry_times else None,
                "window_end_ist":      entry_times[-1].astimezone(IST).strftime("%H:%M") if entry_times else None,
                "winning_count":       sum(1 for p in pnls if p > 0),
                "losing_count":        len(losing_pnls),
                "total_loss_in_burst": round(sum(losing_pnls), 2),
                "session_pnl":         round(session_pnl, 2),
                "caution_limit":       burst_caution,
                "danger_limit":        burst_danger,
                "burst_trades":        [_trade_entry(t) for t in all_trades],
            }
            return ctx_dict

        # ── Check 1: burst (30-min rolling window) ─────────────────────────
        # "5 trades in 30 min" = 5 complete round-trips whose ENTRY fell within
        # a 30-min window ending at the current trade's entry. Open positions are
        # not counted (CompletedTrade only — engine is per-closed-trade by design).
        cutoff = ct.entry_time - timedelta(minutes=30)
        recent = [t for t in ctx.session_trades
                  if t.entry_time and t.entry_time >= cutoff and t.id != ct.id]
        burst_all = recent + [ct]
        # Count structures, not legs. A CompletedTrade is per tradingsymbol, so
        # one four-leg condor is four rows — two condors read as eight trades
        # against a burst threshold of five and fired a danger alert for two
        # positions. count_structures collapses a cluster only when it
        # classifies as a recognised strategy, so the count can only fall: a
        # trader who never trades multi-leg sees exactly the old number.
        burst_count = count_structures_fn(burst_all)

        if burst_count >= burst_caution:
            recent_pnls = [float(t.realized_pnl or 0) for t in burst_all]
            all_burst_profitable = all(p > 0 for p in recent_pnls)

            # Suppress entirely: profitable burst while session P&L positive
            if session_pnl > 0 and all_burst_profitable:
                pass

            elif burst_count >= burst_danger:
                bctx = _burst_context(burst_all)
                entry_range = (
                    f"{bctx['window_start_ist']}–{bctx['window_end_ist']}"
                    if bctx['window_start_ist'] else "30 min"
                )
                loss_note = (
                    f" while down ₹{abs(session_pnl):,.0f} on the session."
                    if session_pnl < 0 else "."
                )
                return DetectedEvent(
                    event_type="overtrading_burst",
                    severity="danger",
                    message=f"{burst_count} positions opened {entry_range}{loss_note}",
                    context=bctx,
                )

            else:
                bctx = _burst_context(burst_all)
                entry_range = (
                    f"{bctx['window_start_ist']}–{bctx['window_end_ist']}"
                    if bctx['window_start_ist'] else "30 min"
                )

                if session_pnl < 0:
                    return DetectedEvent(
                        event_type="overtrading_burst",
                        severity="caution",
                        message=(
                            f"{burst_count} positions opened {entry_range} "
                            f"while session is down ₹{abs(session_pnl):,.0f}."
                        ),
                        context=bctx,
                    )

                losing_in_burst = bctx["losing_count"]
                if losing_in_burst > 0:
                    total_loss = abs(bctx["total_loss_in_burst"])
                    return DetectedEvent(
                        event_type="overtrading_burst",
                        severity="caution",
                        message=(
                            f"{burst_count} positions opened {entry_range} — "
                            f"{losing_in_burst} closed at a loss "
                            f"(₹{total_loss:,.0f} total)."
                        ),
                        context=bctx,
                    )

        # ── Check 2: daily session count, against the DECLARED limit ────────
        #
        # REVIEWED 2026-08-26, Pattern #5. This fired at `daily_trade_limit`,
        # which resolves from history as the trader's own `daily_trades_p75`.
        # A line set at a p75 alerts on 25% of that trader's sessions BY
        # CONSTRUCTION — for anyone, forever, however they behave. Measured on
        # the reference book: 26%, 52 alerts. Halve your trading and the p75
        # halves with you and still takes a quarter of your sessions. That is a
        # quota, not a finding.
        #
        # And the claim it carried did not survive the book either. The copy
        # said a heavy day "becomes momentum"; past the line this trader was
        # SLOWER (median gap 4 -> 9 min), SMALLER (median risk 8,044 -> 7,213)
        # and no worse (win rate 44.7% -> 42.6%, 0.4 SE). Heavy days were 26% of
        # sessions and 2% of the book's loss, and the 141 positions taken past
        # the line made 1,265 net. Heavy days already differ at position ONE
        # (+14.9pp win rate), so the count is a symptom of the kind of day it
        # is, not a cause of anything.
        #
        # What is left is the only version that is true by construction: the
        # trader said they stop at N and they are at N. No declaration, no
        # alert — the count stays visible to analytics, which computes it from
        # the trades themselves and never needed this event.
        #
        # ONE severity. `daily_trade_danger` (12) is NOT read here: the file
        # that defines it records "no source", and it reached 3 of 189 sessions
        # while deciding a push. No approaching rung either — the constitution's
        # own `daily_trades` rule already fires at 80% of the same declared
        # number, and building a second voice for it is the consolidation
        # question this review deferred.
        if not declared_daily_limit:
            return None
        declared_daily_limit = int(declared_daily_limit)

        all_session = list(ctx.session_trades) + [ct]
        # Structures, not legs — see the burst check above.
        daily_count = count_structures_fn(all_session)
        daily_legs = len(all_session)

        if daily_count >= declared_daily_limit:
            pnls_today = [float(t.realized_pnl or 0) for t in all_session]
            winning_today = sum(1 for p in pnls_today if p > 0)
            losing_today  = sum(1 for p in pnls_today if p < 0)
            total_loss_today = sum(p for p in pnls_today if p < 0)
            return DetectedEvent(
                event_type="daily_overtrading",
                severity="caution",
                message=(
                    f"{daily_count} positions today — your limit is "
                    f"{declared_daily_limit}"
                    + (f". Session P&L: ₹{session_pnl:+,.0f}." if session_pnl != 0 else ".")
                ),
                context={
                    "daily_count":       daily_count,
                    "daily_legs":        daily_legs,
                    "declared_limit":    declared_daily_limit,
                    "session_pnl":       round(session_pnl, 2),
                    "winning_count":     winning_today,
                    "losing_count":      losing_today,
                    "total_loss_today":  round(total_loss_today, 2),
                    "daily_trades": [_trade_entry(t) for t in sorted(
                        all_session,
                        key=lambda t: t.entry_time or datetime.min.replace(tzinfo=timezone.utc)
                    )],
                },
            )

        # MED-4: the gains-erosion check that used to live here was moved to
        # profit_giveaway, which was itself RETIRED 2026-08-27. Nothing checks
        # session gains-erosion now, deliberately: the giveback was measured to
        # be indistinguishable from chance. See docs/patterns/06-profit_giveaway/.
        return None

    # ── RETIRED 2026-08-27 — `size_escalation` ────────────────────────────
    #
    # Its whole claim was that the ORDER of position sizes carries information:
    # three consecutive trades each larger than the last, while losing. Tested
    # with this detector's own code against 200 permutations of each session's
    # trade order — same trades, same sizes, same P&L, only the sequence changed
    # — the real order fired LESS than chance: 42 observed against 49.7 expected,
    # ratio 0.85, p(shuffled >= observed) = 0.880. Its defining gate selects at
    # exactly the rate three random numbers are increasing: 16.9% of 3-trade
    # windows in the book against 16.7% expected.
    #
    # The rest was already broken. 37 of 42 firings ran the cross-instrument
    # branch, whose headline named `ct_underlying` — the CURRENT trade — while
    # the three trades shown were the session's previous three, so the alert read
    # "ICICIGI: ... (TCS25APR2900PE / TCS25APR3500CE / HUDCO25APR230CE)". `prior`
    # excludes `ct`, so it fired on trade N and described N-3..N-1; only 7 of 42
    # alerts contained the trade that raised them. "While losing" tested
    # `pnls[:2]` for a single loss — true 83% of the time by base rate, and never
    # checking the trade at the top of the escalation. It predicted nothing
    # (+Rs 69/trade, p = 0.797, sign favouring the flagged trade).
    #
    # THE CONCEPT OF DANGEROUS SIZING IS NOT RETIRED. `martingale_behaviour`
    # (the step the trader took, capital at risk, >=2 trailing consecutive
    # losses) and `post_loss_recovery_bet` (current against the mean of the last
    # three) both keep the current trade as the subject and both survive
    # untouched. The one shape only this detector could have caught — a slow ramp
    # where every step stays under martingale's 1.5x and the current trade under
    # recovery's 2.0x of the recent mean — occurs 0 times in 3-trade windows
    # across 189 sessions (once each at 4 and 5 trades), so no replacement was
    # built. See docs/patterns/10-size_escalation/.
    #
    # AMENDED 2026-08-30: this note used to say "`_notional` stays: detectors at
    # 2473 and 3033 read it". Both readers are now gone - the last was
    # `winning_streak_overconfidence`, retired at Pattern 19 - so
    # `BehaviorEngine._notional` has NO callers. It is deliberately left in
    # place rather than deleted: removing a shared helper is a judgement beyond
    # a detector retirement, and the size_escalation retirement chose to keep
    # it. Recorded in PENDING_AND_TODO.md for the consolidated pass.
    # (`alert_outcome_service` has its own separate `_notional`; that one is
    # live and unrelated.)

    # ── Pattern 5: Rapid re-entry (same symbol) ───────────────────────────

    def _detect_rapid_reentry(self, ctx: EngineContext) -> Optional[DetectedEvent]:
        ct = ctx.completed_trade
        if not ct.entry_time:
            return None

        # Was filtered from `session_trades`, and protected only INCIDENTALLY:
        # an unconcluded prior yields a negative `gap_min`, which the `0 <=`
        # below rejects. That reads as a range bound, not a temporal contract,
        # so the guarantee is stated here instead. The `0 <=` stays - it is now
        # belt-and-braces rather than the only protection. Firing set unchanged
        # (14 on the reference book).
        prior_same = [t for t in ctx.concluded_before_entry
                      if t.tradingsymbol == ct.tradingsymbol]
        if not prior_same:
            return None

        last_same = max(prior_same, key=lambda t: t.exit_time)
        prior_pnl = Decimal(str(last_same.realized_pnl or 0))

        # Only flag rapid re-entry after a LOSS.
        # Re-entering quickly after a profit may be scalping — a valid strategy.
        if prior_pnl >= 0:
            return None

        gap_min = (ct.entry_time - last_same.exit_time).total_seconds() / 60
        window = ctx.thresholds.get("rapid_reentry_min", 5)
        if 0 <= gap_min <= window:
            return DetectedEvent(
                event_type="rapid_reentry",
                # Phase 4: analytics-only — profitable traders re-enter.
                # This said "evidence feeds revenge confidence" until 2026-08-24.
                # revenge_trade 3.0.0 takes its confidence from
                # confidence.from_observables and never reads this event.
                severity="info",
                message=(
                    f"{ct.tradingsymbol}: re-entered {gap_min:.0f}min after a "
                    f"₹{abs(float(prior_pnl)):,.0f} loss on the same instrument."
                ),
                context={"symbol": ct.tradingsymbol, "gap_minutes": round(gap_min, 1),
                         "prior_pnl": float(prior_pnl), "window_min": window,
                         "trigger_symbol": ct.tradingsymbol,
                         "prior_exit_time_ist": last_same.exit_time.astimezone(IST).strftime("%H:%M") if last_same.exit_time else None,
                         "reentry_time_ist": ct.entry_time.astimezone(IST).strftime("%H:%M") if ct.entry_time else None},
            )
        return None

    # ── Pattern 6: Panic exit ─────────────────────────────────────────────

    # ── RETIRED 2026-08-29 — `panic_exit` ─────────────────────────────────
    #
    # Retired because its subject does not exist. It was two conditions -
    # held under five minutes AND a loss - and "panic" was inferred entirely
    # from those. Measured against the 175-session book:
    #
    #   a sub-5-minute hold is 24% of everything this trader does (180 of 740)
    #
    #   THE DECIDING TEST - it fired on short LOSSES and never on short WINS:
    #     sub-5-min holds        180     win rate 38.3%
    #     5-min-or-longer holds  560     win rate 39.8%
    #
    # Short holds perform the SAME as long holds, so a fast exit is not a worse
    # decision for this trader. The detector fired on the losing 60% and ignored
    # 69 identical-behaviour trades purely because they made money - selection on
    # OUTCOME, not on behaviour. Same shape as `size_escalation`: the claimed
    # discriminator does not discriminate.
    #
    # It also fired on the trader's CHEAPEST losses - median Rs 308, and 69% of
    # firings were under Rs 500 - flagging plausibly-good risk management as a
    # psychological failure. (Short losses averaged -473 against -1,053 for
    # longer ones at p = 0.000, but that comparison is confounded: a longer hold
    # has more time to accumulate loss. The win-rate result above is the clean
    # one and carries the argument alone.)
    #
    # Its message made three unsupported claims in one sentence: "no stop-loss
    # order" (the Pattern 12 defect, unverifiable), "quick manual exit"
    # ("manual" is equally unknowable without an order type), and the event name
    # itself.
    #
    # THE CONCEPT OF A FAST EXIT IS NOT RETIRED as a neutral fact - hold time is
    # recorded on every CompletedTrade and analytics can read it. What is retired
    # is treating a short losing hold as a behavioural finding.
    #
    # Evidence: docs/patterns/14-panic_exit/ and _measurement/p14_panic.py.


    # ── Adding to an adverse position ─────────────────────────────────────
    #
    # The one behaviour in this engine that happens INSIDE a position rather
    # than between two of them, and the reason ctx.position_fills exists.

    #: Severity, as two ordinal axes and a table. No score, no weights, no sum.
    #:
    #:   A  how many times the trader added while under water
    #:   B  whether any of those adds was at least as large as the position it
    #:      was added to
    #:
    #: Both axes are definitional rather than calibrated, which is the whole
    #: reason this shape was chosen. "More than once" needs no number - a
    #: repetition requires two. "At least as much again" is the identity, 1.0,
    #: not a threshold somebody picked. The review measured every percentage
    #: candidate and found no defensible cut point in any of them: adverse depth
    #: is one smooth mode with no gap, and the median move when adding is 10.6%
    #: against and 10.4% in favour - the magnitude carries no information, only
    #: the sign does.
    #:
    #: Indexed [A][B]. See docs/patterns/02-adding_to_adverse_position/adding_to_adverse_position_contract.md
    #: and its three validation companions.
    _AAP_MATRIX = {
        # A3 three or more adverse adds - 9 of 64 positions in the real book
        3: {1: "danger", 2: "critical"},
        # A2 did it again
        2: {1: "caution", 2: "danger"},
        # A1 once. Recorded rather than shouted: 46 of the 64 positions sit
        # here, and one add while under water is a fact worth keeping, not an
        # interruption worth making.
        1: {1: "info", 2: "caution"},
    }

    def _detect_adding_to_adverse_position(self, ctx: EngineContext):
        """
        The position moved against the trader and the trader added to it.

        Size is deliberately not part of whether this happened. In a year of
        real trades, 95 of 96 adverse adds were SMALLER than 1.5x the position
        held and the median was 0.67x - a multiplier rule sees essentially none
        of this behaviour. What separates it from ordinary scaling is the sign
        of the move, not its magnitude.

        Strictly position-level: one symbol, one open position. A different
        strike is a different position, and strike progression on its own is not
        evidence of anything - that question is recorded as separate research
        rather than folded in here.
        """
        from app.core import confidence as _confidence
        from app.core.evidence import Insufficiency, positive
        from app.core.instrument_risk import risk_basis

        ct = ctx.completed_trade

        if not ctx.position_fills:
            # Either a single-entry position - the common case, and a real
            # non-detection - or the sequence could not be read. The loader
            # only queries when num_entries > 1, so the first reading is right
            # whenever the position had one entry.
            if (getattr(ct, "num_entries", 1) or 1) > 1:
                return abstained(
                    "adding_to_adverse_position", Insufficiency.MISSING_INPUT,
                    "the position had multiple entries but its fill sequence "
                    "could not be read",
                )
            return not_detected("adding_to_adverse_position",
                                "the position was opened in a single fill")

        # Exposure has to mean something before a claim about it can. A spread
        # leg's denominator is known to be over-estimated, so the honest answer
        # is to decline rather than report a ratio wrong in a known direction.
        basis = risk_basis(
            ct.instrument_type, ct.tradingsymbol or "", ct.direction,
            float(ct.avg_entry_price or 0), int(ct.total_quantity or 0),
            is_spread=ctx.strategy_group is not None, exchange=ct.exchange,   # F7
        )
        if not basis.is_comparable:
            return abstained(
                "adding_to_adverse_position", Insufficiency.NOT_APPLICABLE,
                f"exposure is not reliably determinable for a "
                f"{basis.instrument.value}",
                instrument=basis.instrument.value,
                denominator=basis.kind.value,
            )

        adds = adverse_adds(ctx.position_fills)
        if not adds:
            return not_detected(
                "adding_to_adverse_position",
                "every addition to this position was made after a favourable "
                "move, or the position was never added to",
            )

        a_level = min(len(adds), 3)
        b_level = 2 if any(a.at_least_doubled_down for a in adds) else 1
        severity = self._AAP_MATRIX[a_level][b_level]

        deepest = max(adds, key=lambda a: a.adverse_pct)
        first, last = adds[0], adds[-1]
        deepening = deepens_each_time(adds)

        exposure_at_open = risk_basis(
            ct.instrument_type, ct.tradingsymbol or "", ct.direction,
            first.avg_before, first.held_qty,
            is_spread=False, exchange=ct.exchange,            # F7
        ).amount
        exposure_now = basis.amount

        if len(adds) == 1:
            message = (
                f"{ct.tradingsymbol}: added {last.added_qty} to a position "
                f"already {last.adverse_pct:.0f}% against you "
                f"({last.avg_before:,.2f} -> {last.fill_price:,.2f})."
            )
        else:
            message = (
                f"{ct.tradingsymbol}: added to this position {len(adds)} times "
                f"while it moved against you, from {first.adverse_pct:.0f}% down "
                f"to {deepest.adverse_pct:.0f}% down."
            )
        if b_level == 2:
            message += " At least one addition was as large as the position it was added to."

        return DetectorResult(
            detector="adding_to_adverse_position",
            evidence=positive("adverse add", adverse_adds=len(adds)),
            layer=Layer.SAFETY if a_level >= 2 else Layer.PERSONAL,
            severity=severity,
            confidence=_confidence.from_observables(inputs_parsed=True),
            message=message,
            context={
                "adverse_add_count": len(adds),
                "deepest_adverse_pct": round(deepest.adverse_pct, 1),
                "first_adverse_pct": round(first.adverse_pct, 1),
                "deepens_each_time": deepening,
                "at_least_doubled_down": b_level == 2,
                "a_level": a_level,
                "b_level": b_level,
                "instrument_class": basis.instrument.value,
                "denominator_kind": basis.kind.value,
                "exposure_at_open": round(exposure_at_open),
                "exposure_at_close": round(exposure_now),
                "trigger_symbol": ct.tradingsymbol,
                "adds": [
                    {
                        "index": a.index,
                        "adverse_pct": round(a.adverse_pct, 1),
                        "added_qty": a.added_qty,
                        "held_qty": a.held_qty,
                        "add_ratio": round(a.add_ratio, 2),
                        "price": a.fill_price,
                        "avg_before": round(a.avg_before, 2),
                        "time_ist": (a.occurred_at.astimezone(IST).strftime("%H:%M")
                                     if a.occurred_at else None),
                    }
                    for a in adds
                ],
            },
        )

    # ── Pattern 7: Martingale / averaging down ────────────────────────────

    @staticmethod
    def _typical_loss(ctx) -> Optional[float]:
        """
        The trader's own median losing trade, in rupees.

        Replaces a flat ₹500 floor that meant something at ₹50,000 of capital
        and nothing at ₹10,00,000. Capital is the wrong base — it moves, gets
        withdrawn at month end and topped up mid-month — but the size of the
        trader's own losses is stable and observable, and it is what "a loss
        worth reacting to" actually means.

        Returns None when there is not enough history, and callers fall back to
        the configured floor rather than inventing one from two data points.
        """
        losses = sorted(
            abs(float(t.realized_pnl or 0))
            for t in (ctx.session_trades or [])
            if float(t.realized_pnl or 0) < 0
        )
        if len(losses) < 3:
            return None
        return losses[len(losses) // 2]

    @staticmethod
    def _notional(t) -> float:
        """
        What a position was worth, in rupees.

        The comparable size measure ACROSS instruments. Quantity is not: 50
        Nifty against 2000 Industower says nothing. Every sizing detector was
        restricted to a single underlying for that reason, and the restriction
        cost them — they saw nothing across 61 real sessions from a trader who
        escalates by rotating instruments.
        """
        return float(abs(t.total_quantity or 0)) * float(t.avg_entry_price or 0)

    def _detect_martingale_behaviour(self, ctx: EngineContext):
        """
        A loss, then the next attempt at materially more risk.

        REWRITTEN 2026-08-24, Pattern #1. What changed and why:

        This is NOT "adding to a losing position". The losing position here is
        CLOSED; the escalation happens on a SUBSEQUENT attempt. Adding to a
        position that is still open is `adding_to_adverse_position`, which reads
        a fill sequence this detector cannot see - a CompletedTrade folds every
        entry into one average price. The two can both be true and neither
        implies the other. See docs/patterns/00-shared/two_behaviours_not_one.md.

        Three corrections, each measured:

        1. The step is the one the TRADER TOOK - the previous closed position to
           this one. It used to be the largest step between two EARLIER
           positions, with the current trade displayed but taking part in no
           decision. On 58 firings that produced 29 alerts where the current
           position was smaller than the previous one and 26 where the trade was
           profitable, while missing 22 real escalations.

        2. The losses must be TRAILING CONSECUTIVE, which is what the message
           has always claimed. It used to count any 2 of the last 3, so 23 of 58
           firings said "consecutive losses" when there had not been two in a
           row.

        3. Size is CAPITAL AT RISK, via instrument_risk. It used to be quantity
           within one underlying and notional across them - two different units
           compared against one multiplier, and neither is risk for a short
           option or a future. 45 of the 64 escalations in the book are on a
           DIFFERENT underlying, so the cross-instrument comparison is the
           normal case rather than the exception, and it has to be valid.

        The 1.5x/2.0x multipliers are UNCHANGED. Measured on the corrected step
        they give 31 caution and 20 danger firings across the book. No natural
        break exists in the distribution to replace them with - p50 1.44x, p75
        2.79x, and the only gaps are in the two-point tail - so changing them
        would be inventing a number, not correcting one.
        """
        from app.core.evidence import Insufficiency, positive
        from app.core.instrument_risk import risk_basis

        ct = ctx.completed_trade
        # CONCLUDED, not OCCURRED. This detector's claim is causal - size
        # escalated AFTER a run of losses - so the run may only contain losses
        # the trader could actually see when they entered. Reading
        # `session_trades` here put 9 of 32 firings on the reference book behind
        # a loss that closed after the entry they explained, the worst by 125
        # minutes. Thresholds and the ladder are untouched.
        prior = ctx.concluded_before_entry
        min_losses = int(ctx.thresholds.get("martingale_min_losses", 2))
        if len(prior) < min_losses:
            return not_detected(
                "martingale_behaviour",
                f"fewer than {min_losses} closed trades to escalate from",
            )

        # Trailing consecutive losses, not any-N-of-the-last-3.
        run = 0
        for t in reversed(prior):
            if float(t.realized_pnl or 0) < 0:
                run += 1
            else:
                break
        if run < min_losses:
            return not_detected(
                "martingale_behaviour",
                f"{run} consecutive losing trades before this one, not {min_losses}",
            )

        previous = prior[-1]
        is_spread = ctx.strategy_group is not None
        cur = risk_basis(ct.instrument_type, ct.tradingsymbol or "", ct.direction,
                         float(ct.avg_entry_price or 0),
                         int(ct.total_quantity or 0), is_spread=is_spread,
                         exchange=ct.exchange)                # F7
        prv = risk_basis(previous.instrument_type, previous.tradingsymbol or "",
                         previous.direction, float(previous.avg_entry_price or 0),
                         int(previous.total_quantity or 0),
                         exchange=previous.exchange)          # F7
        if not cur.is_comparable or not prv.is_comparable:
            return abstained(
                "martingale_behaviour", Insufficiency.NOT_APPLICABLE,
                "risk is not comparable across these instruments",
                instrument=cur.instrument.value, denominator=cur.kind.value,
            )
        if prv.amount <= 0:
            return abstained("martingale_behaviour", Insufficiency.MISSING_INPUT,
                             "the previous attempt has no measurable risk")

        ratio = cur.amount / prv.amount
        caution_mul = float(ctx.thresholds.get("martingale_caution_multiplier", 1.5))
        danger_mul = float(ctx.thresholds.get("martingale_danger_multiplier", 2.0))

        if ratio < caution_mul:
            return not_detected(
                "martingale_behaviour",
                f"risk went {prv.amount:,.0f} to {cur.amount:,.0f} "
                f"({ratio:.2f}x) after {run} losses",
            )

        severity = "danger" if ratio >= danger_mul else "caution"
        total_loss = sum(abs(float(t.realized_pnl or 0)) for t in prior[-run:])
        from app.services.instrument_parser import parse_symbol as _ps

        def _und(sym):
            try:
                return _ps(sym or "").underlying or sym or ""
            except Exception:
                return sym or ""

        rotated = _und(ct.tradingsymbol) != _und(previous.tradingsymbol)
        where = (f"moved to {ct.tradingsymbol}" if rotated
                 else f"went back into {ct.tradingsymbol}")

        return DetectorResult(
            detector="martingale_behaviour",
            evidence=positive("escalation after losses", ratio=round(ratio, 2)),
            layer=Layer.SAFETY if severity == "danger" else Layer.PERSONAL,
            severity=severity,
            message=(
                f"After {run} losing trades (Rs {total_loss:,.0f}), you {where} "
                f"with {ratio:.1f}x the capital at risk "
                f"(Rs {prv.amount:,.0f} to Rs {cur.amount:,.0f})."
            ),
            context={
                "consecutive_losses": run,
                "prior_total_loss": round(total_loss, 2),
                "risk_before": round(prv.amount),
                "risk_after": round(cur.amount),
                "risk_ratio": round(ratio, 2),
                "rotated_instrument": rotated,
                "previous_symbol": previous.tradingsymbol,
                "trigger_symbol": ct.tradingsymbol,
                "instrument_class": cur.instrument.value,
                # Which unit the ratio is in. The old implementation compared
                # lots in one branch and rupees in the other without recording
                # which, so a reader could not tell what "2x" meant.
                "denominator_kind": cur.kind.value,
                "caution_multiplier": caution_mul,
                "danger_multiplier": danger_mul,
                "trade_list": [
                    {
                        "symbol": t.tradingsymbol or "-",
                        "qty": t.total_quantity or 0,
                        "pnl": float(Decimal(str(t.realized_pnl or 0))),
                        "exit_time_ist": (t.exit_time.astimezone(IST).strftime("%H:%M")
                                          if t.exit_time else None),
                    }
                    for t in prior[-run:]
                ] + [{
                    "symbol": ct.tradingsymbol or "-",
                    "qty": ct.total_quantity or 0,
                    "pnl": float(Decimal(str(ct.realized_pnl or 0))),
                    "exit_time_ist": (ct.exit_time.astimezone(IST).strftime("%H:%M")
                                      if ct.exit_time else None),
                }],
            },
        )


    # ── RETIRED 2026-08-29 — `cooldown_violation` ─────────────────────────
    #
    # Retired because its subject does not occur and the behaviour it named is
    # already covered, better, by a different detector.
    #
    # ITS PRECONDITION NEVER OCCURRED ON THE LIVE PATH. Cooldown rows are
    # written in exactly one place, danger_zone_service.trigger_intervention,
    # reachable only from POST /danger-zone/trigger-intervention and
    # POST /sync/all. No Celery task calls it, so the postback pipeline that ran
    # this detector never created a cooldown. It fired 0 times on the
    # 175-session book.
    #
    # THE BEHAVIOUR IS FULLY COVERED. `constitution_violation`'s `cooldown` rule
    # reads the trader's OWN declared `cooldown_after_loss`, measures the gap
    # from the last losing exit, and fires at DANGER. Measured at a 15-minute
    # declared value it raised 181 events on the same book, against this
    # detector's 0. `revenge_trade` also reads the declared value to raise its
    # own severity on a breach.
    #
    # Its registry copy - "the cooldown you set" - described that other
    # detector's mechanism, not this one's: this read a SYSTEM-imposed row and
    # never touched the declared value.
    #
    # SHARED COOLDOWN INFRASTRUCTURE IS UNTOUCHED. `cooldown_service`, the
    # `Cooldown` model and table, the `/cooldown` API, the danger zone's use of
    # them, and the trader's `cooldown_after_loss` rule all remain. Only this
    # detector and the context plumbing that existed solely for it are gone.
    #
    # Evidence: docs/patterns/15-cooldown_violation/.


    # ── RETIRED 2026-08-28 — `direction_instability` ──────────────────────
    #
    # Retired because it could not tell an emotional reversal from a change of
    # view, and what it selected looked like the change of view.
    #
    # Every CE<->PE transition on one underlying in the 189-session book: 10 had
    # OVERLAPPING legs (a hedge or structure — correctly excluded by the negative
    # gap), 16 were sequential inside 10 minutes (FLAGGED), 48 were sequential
    # beyond it (not flagged). So the only thing separating a flagged flip from
    # an unflagged one was the clock — and the clock sorted them backwards:
    #
    #   flagged flip trade        n=16  win 56.2%   mean +Rs 276
    #   not flagged (gap >=10m)   n=48  win 41.7%   mean -Rs  73
    #   the prior being exited    flagged -Rs 284 / 31% win  vs  +Rs 35 / 54%
    #
    # The trader reversed FAST when a position had gone badly and slowly when it
    # had not: cutting a loser. Sessions containing a flip ended +Rs 1,305
    # against -Rs 860 for no-flip sessions in the same trade-count band
    # (p = 0.129), and rest-of-session AFTER the first flip was +Rs 953 against
    # -Rs 112 matched (p = 0.095) — the premise predicts deterioration and the
    # measurement showed improvement. Flagged flips were flat-sized (median ratio
    # 1.03), so there was no escalation story either. `revenge_trade` already
    # fired on 10 of the 18 firings, so the emotional reading is owned.
    #
    # Nothing reached p < 0.05 at n=16, but five independent measures pointed the
    # same way. An alert that fires on good decisions is worse than one that
    # fires on noise.
    #
    # THE CONCEPT IS NOT RETIRED PERMANENTLY. Level 1 — a same-symbol LONG<->SHORT
    # reversal — was never testable here: the book is 911 LONG against 1 SHORT,
    # with zero same-symbol opposite-direction pairs at any gap. It would be the
    # live branch for a futures trader or an option seller. Revisit with a book
    # that contains shorts. See docs/patterns/11-direction_instability/.

    # ── Pattern 10: Excess exposure ───────────────────────────────────────

    def _detect_excess_exposure(self, ctx: EngineContext) -> Optional[DetectedEvent]:
        ct = ctx.completed_trade
        capital = ctx.thresholds.get("trading_capital")
        # Require a known (non-zero) capital figure but drop the ₹10 000 floor —
        # under-capitalised accounts are the ones most at risk of over-exposure.
        if not capital or float(capital) <= 0:
            return None

        # F17. This used to call estimate_capital_at_risk directly, which meant
        # risk_basis, is_comparable and every UNRELIABLE marking were unreachable
        # here - the safety layer existed and this detector never consulted it.
        # The canonical layer returns the figure WITH its provenance, and a
        # capital-relative rule has no business firing on a number the layer
        # could not stand behind.
        rq = quantities_for_trade(ct, margin=ctx.broker_margin)
        if not rq.usable_for_capital_rules:
            logger.debug(
                "excess_exposure abstains on %s: %s",
                ct.tradingsymbol, rq.capital_requirement.note)
            return None
        capital_at_risk = float(rq.capital_requirement.amount)
        risk_pct = capital_at_risk / capital * 100
        caution_pct = ctx.thresholds.get("max_position_pct_caution", 5.0)
        danger_pct  = ctx.thresholds.get("max_position_pct_danger", 10.0)

        if risk_pct > danger_pct:
            return DetectedEvent(
                event_type="excess_exposure",
                severity="danger",
                message=(
                    f"{ct.tradingsymbol}: ₹{capital_at_risk:,.0f} at risk "
                    f"— {risk_pct:.1f}% of capital on a single trade."
                ),
                context={"capital_at_risk": round(capital_at_risk),
                         "risk_pct": round(risk_pct, 1),
                         "caution_pct": caution_pct, "danger_pct": danger_pct},
            )
        if risk_pct > caution_pct:
            return DetectedEvent(
                event_type="excess_exposure",
                severity="caution",
                message=(
                    f"Your {ct.tradingsymbol} trade put {risk_pct:.1f}% of capital at risk "
                    f"(₹{capital_at_risk:,.0f}). "
                    f"Recommended maximum: {caution_pct:.0f}% per trade."
                ),
                context={"capital_at_risk": round(capital_at_risk),
                         "risk_pct": round(risk_pct, 1),
                         "caution_pct": caution_pct, "danger_pct": danger_pct},
            )
        return None

    # ── Pattern 11: Session meltdown ──────────────────────────────────────

    def _detect_session_meltdown(self, ctx: EngineContext) -> Optional[DetectedEvent]:
        # Strategy leg: use strategy net P&L to avoid flagging a losing leg in a net-profitable strategy
        if ctx.strategy_group and ctx.strategy_group.net_pnl is not None:
            leg_pnl = Decimal(str(ctx.completed_trade.realized_pnl or 0))
            net_pnl = Decimal(str(ctx.strategy_group.net_pnl))
            if net_pnl >= 0 and leg_pnl < 0:
                return None

        session_pnl = Decimal(str(ctx.session.session_pnl or 0))
        daily_loss_limit = ctx.thresholds.get("daily_loss_limit")

        # THE LIMIT MUST BE THE TRADER'S. Pattern 17, 2026-08-30.
        #
        # This used to fall back to `trading_capital * 0.05` when no limit was
        # declared. That number had no documented provenance - it predates the
        # visible history and no commit introduces or justifies it - and it
        # contradicted the product's own answer in two places: the
        # `constitution_service` experience matrix suggests 2% / 2% / 2.5% / 3%
        # by experience level, and the onboarding wizard computes 2%. The
        # detector's fallback was therefore higher than our own "professional"
        # tier and nearly triple what onboarding offers.
        #
        # More importantly it contradicted a DECIDED policy.
        # `constitution_service` owns `daily_loss_limit` as one of six
        # RULE_FIELDS and deliberately returns None for it, keeping its
        # recommendation in a separate `suggested_daily_loss_limit` key that
        # nothing consumes. Its comment records the decision and the
        # measurement behind it: money rules are SUGGESTED, NEVER APPLIED,
        # because F&O lot sizes make a percent-of-capital money rule unusable -
        # a real replay produced 212 rule violations across 61 sessions, 54% of
        # all alerts, none describing behaviour.
        #
        # `danger_zone_service` already follows that policy: it guards on the
        # limit being present and has no derivation at all.
        #
        # So: no declared limit, no judgement. This is applying the rule the
        # product already made, not inventing a new one, which is why no
        # replacement percentage was substituted.
        #
        # THE COST, recorded because it was a decision: a trader who has entered
        # capital but not a daily loss limit now gets no meltdown alert at all.
        # On the reference book at a Rs 50,000 account that is 226 events across
        # 91 sessions going to zero. The prompt to set a limit has to live
        # somewhere the trader still sees it - the setup nudge already tracks
        # `daily_loss_limit != null`.
        #
        # The paired change is `api/risk.py`, which copied this fallback so the
        # dashboard hero and the alert would agree on ONE limit. Both were
        # removed together; removing either alone would re-break that agreement.
        if not daily_loss_limit or daily_loss_limit <= 0:
            return None

        limit = Decimal(str(daily_loss_limit))
        caution_pct = Decimal(str(ctx.thresholds.get("meltdown_caution_pct", 0.40)))
        danger_pct  = Decimal(str(ctx.thresholds.get("meltdown_danger_pct", 0.75)))

        # The derived-limit branch went with the fallback: with abstention above,
        # every limit reaching here is the trader's own, so the second copy form
        # and the "capital_derived" source were unreachable. `limit_source` is
        # kept - now always "declared" - because stored rows carry it and a
        # reader should not have to infer it from absence.
        def _message(pct_used: Decimal) -> str:
            return (f"Today's P&L: ₹{session_pnl:,.0f} — {pct_used:.0f}% of your "
                    f"₹{limit:,.0f} daily limit used.")

        def _context(pct_used: Decimal) -> dict:
            return {"session_pnl": float(session_pnl),
                    "daily_loss_limit": float(limit),
                    "limit_source": "declared",
                    "pct_used": round(float(pct_used), 1)}

        if session_pnl < -(limit * danger_pct):
            pct_used = abs(session_pnl) / limit * 100
            return DetectedEvent(
                event_type="session_meltdown",
                severity="danger",
                message=_message(pct_used),
                context=_context(pct_used),
            )
        if session_pnl < -(limit * caution_pct):
            pct_used = abs(session_pnl) / limit * 100
            return DetectedEvent(
                event_type="session_meltdown",
                severity="caution",
                message=_message(pct_used),
                context=_context(pct_used),
            )
        return None

    # ── Pattern 12: FOMO entry ─────────────────────────────────────────────
    #
    # Detects scattering across different underlying instruments.
    # Buying multiple strikes of same underlying (NIFTY25500CE + NIFTY25600CE) = strategy.
    # Buying NIFTY CE + BANKNIFTY CE + RELIANCE option in 30 min = FOMO.
    # Works at any time of day (not just market open).

    def _detect_fomo_entry(self, ctx: EngineContext) -> Optional[DetectedEvent]:
        """
        How many different underlyings were entered inside a short window.

        REVIEWED 2026-08-27, Pattern #7. What changed, and why:

        1. **One threshold, every context.** There were four - expiry day 4,
           market open 2, pre-close 3, otherwise 3 - and on the reference book
           two of them could not fire at all. Expiry needed 4 distinct
           underlyings inside 30 minutes and the maximum ever reached across 142
           expiry entries was 3, once. Pre-close needed 3 and the maximum across
           50 entries was 2. A threshold above the highest value its own branch
           has ever produced is not conservative, it is absent. Both were
           removed rather than replaced, because replacing them means inventing
           a number this book cannot justify.

        2. **The market-open threshold of 2 is gone**, which is the outcome of
           the mandatory review it was flagged for. It produced 29 of the
           detector's 74 firings - 39% of all output - at 3.6:1 against the
           general threshold, on a state (two underlyings in half an hour) that
           occurs on 20% of all entries.

        3. **The cause claim is gone from the copy.** It said scattering
           "indicates FOMO - not a focused plan". A permutation null that keeps
           each session's exact entry times and its exact multiset of
           instruments, and permutes only WHICH was traded WHEN, reproduced the
           firings almost exactly: 74 observed against 78.4 expected, ratio
           0.94, and 1.02 on the market-open branch. The trader's pairing of
           instrument to moment carries no information, so the alert cannot say
           they were chased together. The flagged trades also win more often
           than this trader's average - 45.9% against 39.9% - so it cannot say
           they were bad either. It now states the breadth and stops.

        The context (expiry day, open, pre-close) is still computed and still
        reported as a fact on the evidence. It no longer changes the count.

        NOT changed, deliberately: the 30-minute window and the threshold of 3
        are unsourced and are left exactly as they were - this review found
        which numbers were wrong, not what the right ones are. Severity stays
        `caution` and the disposition stays `alerting`.
        """
        ct = ctx.completed_trade
        if not ct.entry_time or ct.instrument_type not in ("CE", "PE", "FUT"):
            return None

        from app.services.instrument_parser import parse_symbol, is_expiry_day as _is_expiry_day
        ct_parsed = parse_symbol(ct.tradingsymbol or "")

        fomo_window_min      = ctx.thresholds.get("fomo_window_min", 30)
        # ONE threshold, every context. See the docstring: the three
        # context-specific numbers were removed in the Pattern #7 review.
        fomo_threshold       = ctx.thresholds.get("fomo_symbols_in_window", 3)
        fomo_open_window_min = ctx.thresholds.get("fomo_open_window_min", 30)
        fomo_close_window_min = ctx.thresholds.get("fomo_close_window_min", 30)

        entry_ist = ct.entry_time.astimezone(IST)

        # Context flags — use symbol-parsed expiry date, NOT hardcoded weekday==3.
        # Weekly options carry the exact expiry date in the symbol (e.g. NIFTY2532025000CE).
        # Monthly options/futures use last Thursday of the contract month.
        is_expiry_day  = _is_expiry_day(ct.tradingsymbol or "", entry_ist.date())
        # Session bounds come from the instrument's OWN exchange. Hardcoding
        # 09:15/15:30 broke commodity traders: MCX runs 09:00-23:30, so
        # mins_after_open went negative for morning trades and mins_before_close
        # was ~450 min negative all evening — both FOMO windows silently never
        # fired on MCX.
        from app.core.exchange_constants import get_open_time, get_close_time
        _exch = (ct.exchange or "NFO").upper()
        _open_t, _close_t = get_open_time(_exch), get_close_time(_exch)
        market_open    = entry_ist.replace(hour=_open_t.hour,  minute=_open_t.minute,  second=0, microsecond=0)
        market_close   = entry_ist.replace(hour=_close_t.hour, minute=_close_t.minute, second=0, microsecond=0)
        mins_after_open  = (entry_ist - market_open).total_seconds() / 60
        mins_before_close = (market_close - entry_ist).total_seconds() / 60
        is_open_window  = 0 <= mins_after_open  <= fomo_open_window_min
        is_close_window = 0 <= mins_before_close <= fomo_close_window_min

        # Find all trades in the rolling window
        window_start = ct.entry_time - timedelta(minutes=fomo_window_min)
        window_trades = [
            t for t in ctx.session_trades
            if t.entry_time and window_start <= t.entry_time <= ct.entry_time
            and t.instrument_type in ("CE", "PE", "FUT")
        ]

        # Count distinct underlyings (not symbols — buying 2 NIFTY strikes is not FOMO).
        # LOW-2: include current trade's underlying so threshold N means N total
        # (not N prior + current = N+1 total).
        distinct_underlyings = {
            parse_symbol(t.tradingsymbol or "").underlying for t in window_trades
        }
        if ct_parsed.underlying:
            distinct_underlyings.add(ct_parsed.underlying)

        # The context is REPORTED, never used to move the threshold. Which part
        # of the session a trade landed in is a fact worth carrying on the
        # evidence; it is not a reason to count differently.
        if is_expiry_day:
            context_note = "expiry day"
        elif is_open_window:
            context_note = "market open"
        elif is_close_window:
            context_note = "pre-close"
        else:
            context_note = None

        if len(distinct_underlyings) >= fomo_threshold:
            label = f" ({context_note})" if context_note else ""
            return DetectedEvent(
                event_type="fomo_entry",
                severity="caution",
                message=(
                    f"{len(distinct_underlyings)} different underlyings entered "
                    f"within {fomo_window_min} min{label}: "
                    f"{', '.join(sorted(distinct_underlyings))}."
                ),
                context={
                    "distinct_underlyings": sorted(distinct_underlyings),
                    "window_minutes": fomo_window_min,
                    "threshold": fomo_threshold,
                    "is_expiry_day": is_expiry_day,
                    "context_note": context_note,
                },
            )
        return None

    # ── Pattern 13: large loss held to the exit ───────────────────────────
    #
    # Long-held option loser: held too long without an exit plan.
    # Expiry-day modifier: theta burns 3-5× faster — lower thresholds.

    def _detect_no_stoploss(self, ctx: EngineContext) -> Optional[DetectedEvent]:
        ct = ctx.completed_trade

        # CE/PE/FUT only — leveraged instruments where SL discipline is critical.
        instrument_type = ct.instrument_type or ""
        if instrument_type not in ("CE", "PE", "FUT"):
            return None

        pnl = Decimal(str(ct.realized_pnl or 0))
        if pnl >= 0:
            return None

        # SCOPE OF THIS CHECK - do not widen it.
        #
        # `ctx.exit_order_types` is built in _load_context from
        # `completed_trade.exit_trade_ids` alone, which are the EXIT FILLS of
        # THIS trade. It therefore answers exactly one question:
        #
        #     "was this exit EXECUTED by a stop order?"
        #
        # It cannot contain a resting order, an entry order, or an order
        # belonging to another position, so an observed stop anywhere else can
        # never reach here and suppress the alert.
        #
        # The distinction that matters and is NOT available: whether a resting
        # stop EXISTED EARLIER and was cancelled or pre-empted. That needs the
        # order book, which no detector reads. A trader who placed an SL then
        # exited manually first shows MKT here and is still flagged - which is
        # why the message no longer claims they had no stop.
        exit_types = {(ot or "").upper() for ot in (ctx.exit_order_types or [])}
        if exit_types & _STOP_ORDER_TYPES:
            return None

        duration = ct.duration_minutes or 0
        entry_price = Decimal(str(ct.avg_entry_price or 0))
        qty = ct.total_quantity or 1

        if instrument_type in ("CE", "PE"):
            capital_at_risk = entry_price * qty
            loss_label = "of premium"
        else:
            from app.core.trading_defaults import estimate_capital_at_risk
            capital_at_risk = Decimal(str(
                estimate_capital_at_risk(
                    instrument_type, ct.tradingsymbol or "",
                    ct.direction or "LONG",
                    float(entry_price), int(qty), exchange=ct.exchange,
                )
            ))
            loss_label = "of margin"

        if capital_at_risk <= 0:
            return None

        loss_pct = abs(pnl) / capital_at_risk * 100

        # Expiry modifiers — theta is more aggressive on expiry day.
        from app.services.instrument_parser import parse_symbol as _parse_sym, is_expiry_day as _is_expiry_day
        is_expiry = False
        is_monthly_expiry = False
        expiry_note = ""
        if ct.entry_time:
            entry_ist = ct.entry_time.astimezone(IST)
            is_expiry = _is_expiry_day(ct.tradingsymbol or "", entry_ist.date())
            if is_expiry:
                _parsed = _parse_sym(ct.tradingsymbol or "")
                is_monthly_expiry = len(_parsed.expiry_key) == 7

        # WEEKLY-EXPIRY ARM REMOVED, Pattern 12 review 2026-08-29.
        #
        # It read `no_stoploss_expiry_loss_pct` (25) and
        # `no_stoploss_expiry_hold_min` (5), which are the SAME values as the
        # normal gate below - so it selected exactly the trades the else arm
        # would have, while labelling them "(expiry day)". Measured: 23 of 52
        # firings carried that label, telling the trader a different standard
        # had been applied when none had.
        #
        # A weekly-expiry trade now falls through to the normal gate, which is
        # bit-identical to what the arm produced. Firing behaviour is unchanged.
        #
        # The MONTHLY arm is kept: 20% against the normal 25% is a real
        # difference, so it is not dead code. Giving weekly its own threshold is
        # a separate, unapproved decision.
        if is_monthly_expiry:
            loss_threshold = ctx.thresholds.get("no_stoploss_monthly_loss_pct", 20)
            hold_threshold = ctx.thresholds.get("no_stoploss_monthly_hold_min", 5)
            expiry_note = " (monthly expiry)"
        else:
            loss_threshold = ctx.thresholds.get("no_stoploss_loss_pct_caution", 25)
            # Minimum 5 min hold to exclude ultra-fast scalps where no formal SL is intentional.
            hold_threshold = ctx.thresholds.get("no_stoploss_hold_min", 5)

        # Both conditions needed: minimum hold time (exclude micro-scalps)
        # + significant loss (exclude noise).
        if duration < hold_threshold or loss_pct < loss_threshold:
            return None

        danger_loss_pct = ctx.thresholds.get("no_stoploss_loss_pct_danger", 50)
        severity = "danger" if loss_pct >= danger_loss_pct else "caution"

        # THE CLAIM, Pattern 12 review 2026-08-29.
        #
        # This used to end "No stop-loss order detected on this trade." It was
        # derived from the EXIT FILL's order type, and it asserted the absence
        # of something it had not looked at:
        #
        #   - in the 175-session reference book, order type is absent for every
        #     fill, so the claim was checkable on 0 of 52 alerts;
        #   - in production it was worse. F1 meant exit_trade_ids held Kite
        #     order ids while the consumer matched Trade.id UUIDs, so the list
        #     was structurally EMPTY for every live trade. Every alert ever
        #     raised asserted "no stop-loss detected" from a list that could not
        #     have contained one.
        #
        # Even with F1 fixed, the exit fill answers a different question. "Was
        # this exit executed by a stop order" is a fact about the fill. "Did the
        # trader have a resting stop" needs the ORDER BOOK, which Kite provides,
        # which our Order model can hold, and which no detector reads. A trader
        # holding a resting SL who exits manually first shows MKT and would be
        # told they had no stop - the inverse of the truth.
        #
        # So the message now states only what is known. The exit mechanism is
        # mentioned ONLY when it was actually observed; absent that, the alert
        # says how far the loss ran and stops there. Nothing implies a stop-loss
        # was available, absent, ignored or detected.
        #
        # RESEARCH FURTHER, not abandoned: routing the resting order book to
        # detectors would upgrade this from a factual loss/exit signal to a
        # genuine "a stop was available and was not used" behavioural signal.
        # That is the only thing that would, and it is not done here.
        mechanism_observed = bool(exit_types)
        if mechanism_observed:
            exit_note = (f" Exit was a {'/'.join(sorted(exit_types))} order, "
                         f"not a stop.")
        else:
            exit_note = ""

        return DetectedEvent(
            event_type="no_stoploss",
            severity=severity,
            message=(
                f"{ct.tradingsymbol}{expiry_note}: held {duration}min into a "
                f"{loss_pct:.0f}% loss {loss_label} (₹{abs(pnl):,.0f}).{exit_note}"
            ),
            context={
                "duration_minutes": duration,
                "loss_pct": round(float(loss_pct), 1),
                "realized_pnl": float(pnl),
                "capital_at_risk": round(float(capital_at_risk)),
                "instrument_type": instrument_type,
                "is_expiry_day": is_expiry,
                "exit_order_types": list(exit_types),
                # Whether the exit mechanism was observable at all. False means
                # the message deliberately says nothing about how it was closed.
                "exit_mechanism_observed": mechanism_observed,
            },
        )

    # ── Pattern 14: Early exit (disposition effect) ───────────────────────
    #
    # Session-level pattern: winners held significantly less time than losers.
    # Classic loss aversion / disposition effect (Shefrin & Statman, 1985).

    # ── RETIRED 2026-08-30 — `early_exit` ─────────────────────────────────
    #
    # THE MEASURE WAS RIGHT. THE SCOPE WAS NOT. Read this before reviving it.
    #
    # It computed the disposition effect - average winner hold against average
    # loser hold - which is long-established behavioural finance (Shefrin &
    # Statman 1985; Odean 1998) and the ONLY observable answer to "was that exit
    # early". Per trade the question is unanswerable: we see neither the plan
    # nor what the price did afterwards.
    #
    # What failed was computing it over ONE SESSION.
    #
    #   the effect is absent in this book
    #     winners  n=276  mean 41.0 min
    #     losers   n=413  mean 36.7 min      ratio 1.12 - winners held LONGER
    #
    #   and at session sample sizes the ratio is noise
    #     3 firings, computed from 3-5 trades per side
    #     shuffling win/loss labels within each qualifying session gives 4+
    #     sub-0.40 sessions 61% of the time:  p = 0.610
    #
    # That is not a threshold needing a better value - at n=3 the ratio of two
    # small means is unstable by arithmetic - which is why NO replacement was
    # substituted and 0.40 was not tuned. Raising the sample gate toward
    # validity raises it toward never firing: n=4 leaves 9 qualifying sessions
    # of 175, n=5 leaves 3.
    #
    # THE MEASURE SURVIVES, AT THE SCOPE WHERE IT WORKS. `baseline_service`
    # already computes `avg_winner_hold_min` and `avg_loser_hold_min` across
    # the trader's full history - 276 and 413 trades, not three and four - each
    # with a sample count and confidence. Those are UNTOUCHED by this
    # retirement. Nothing reads them yet; they may belong on an analytics
    # surface rather than as an alert, which is recorded in
    # docs/DEEP_REVIEW/PENDING_AND_TODO.md and is not decided here.
    #
    # Evidence: docs/patterns/18-early_exit/.


    # ── RETIRED 2026-08-30 — `winning_streak_overconfidence` ──────────────
    #
    # Pattern 19. THE CONCEPT IS REAL. THE CONDITIONING VARIABLE HAD THE
    # WRONG SIGN.
    #
    # It fired when the last N session exits all won AND the position was
    # >= M x the average size of prior trades. Neither half is a behaviour on
    # its own - traders have winning runs and traders vary size - so the whole
    # claim was that the RUN is why the SIZE went up. That is an ordering
    # claim, and it was measured directly.
    #
    #     P(size >= 1.3x baseline)
    #         after a 3+ win run        21.4%   (n=28)
    #         every other comparable    30.4%   (n=263)
    #
    # SIZING UP IS LESS LIKELY AFTER A WINNING RUN, and it is monotone across
    # run lengths - 32.1%, 27.9%, 27.0%, 28.6%, 0.0% for runs of 0 to 4.
    # Spearman rho(run length, size ratio) = -0.076, p = 0.902. The detector's
    # theory predicts a POSITIVE correlation.
    #
    # The response to a run does exist in this book, inverted: after LOSING
    # runs of 0 to 4 the same probability rises 26.0%, 28.4%, 30.6%, 40.0%,
    # 53.8%. THIS TRADER SIZES UP AFTER LOSSES AND DOWN AFTER WINS - which is
    # `martingale_behaviour`'s subject, and it already covers it. Nothing about
    # this trader's sizing goes unwatched by this removal.
    #
    # The shuffle null agrees: 6 real firings against a shuffled mean of 6.2,
    # p = 0.582. The same test retired `size_escalation` (0.880) and
    # `early_exit` (0.610).
    #
    # The danger tier never fired in 175 sessions and was not "correctly
    # silent" - only 1 trade of 740 ever had a 5-win run behind it, and it was
    # under 2.0x. Meanwhile the SIZE half of that tier was satisfied twice
    # (ratios 2.22 and 2.65), both emitting caution because the streak was 3.
    # The tier was gated by the half with no evidence behind it.
    #
    # THE CONCEPT IS NOT RETIRED PERMANENTLY. Overconfidence after wins is
    # established literature (Barber & Odean; Statman, Thorley & Vorkink).
    # This is one trader's answer to "is it present", not an answer to "does
    # the detector work when it is" - the same qualification recorded for
    # `direction_instability`'s Level 1. n=28 after a 3+ win run cannot exclude
    # a modest real effect; what it can exclude is this implementation.
    #
    # Two defects went with it and are recorded so they are not reintroduced:
    # the `_cross` branch compared RUPEES of notional while the message said
    # "qty" (3 of 6 firings, e.g. "10556 -> 23484.4935 qty"), which is the
    # defect the 24 Aug hygiene pass fixed in `size_escalation` and left here;
    # and `uses_baseline=True` was declared while the detector read no
    # baseline at all.
    #
    # PRESERVED, because it is the best provenance note in the registry and
    # applies to any future streak threshold: personalising a streak length
    # gives the absurd result that a trader with many streaks needs a LONGER
    # streak before anyone mentions it. Streak lengths are DEFINITIONAL.
    #
    # Evidence: docs/patterns/19-winning_streak_overconfidence/.


    # ── Pattern 16: Options direction confusion ───────────────────────────
    #
    # CE→PE (or PE→CE) flip on the same underlying within the confusion window.
    # Legitimate reversals require analysis time. < 10 min = confusion, not strategy.

    # options_direction_confusion: MERGED into direction_instability Level 2,
    # which was itself retired 2026-08-28. Both are gone.
    # (Phase 4, master doc 1). Historical alerts keep the old pattern_type.

    # ── Pattern 17: Options premium averaging down ────────────────────────
    #
    # Re-entering the same underlying options after a prior losing options position today.
    # Unlike equity averaging down, options premium erodes via theta — the hole gets bigger.

    # ── RETIRED 2026-08-30 — `options_premium_avg_down` ───────────────────
    #
    # Pattern 20. IT WAS NOT AN AVERAGE-DOWN. NOT ONCE.
    #
    # It fired on a NEW long option entry when any OTHER long option on the
    # same UNDERLYING had closed that session with a realised loss >= 20% of
    # premium. Not the same contract, not the same strike, not even the same
    # option type; no open position, no fill sequence.
    #
    #     firings where any "prior loser" was still an OPEN position:  0 of 44
    #
    # Averaging down means adding to a position you still hold, so by
    # construction this detector could never observe it. Its own threshold
    # comment said so plainly - "re-entry on same options underlying after
    # >=20% loss" - and so did the index at the top of this file. Only the
    # trader-facing copy claimed otherwise, and it claimed ANOTHER DETECTOR'S
    # mechanism: "Additional quantity on an option position already down on
    # premium." That is `adding_to_adverse_position`, verbatim. The same
    # failure retired `cooldown_violation` at Pattern 15.
    #
    # AND THAT OTHER DETECTOR ALREADY IS THE OPTION-PREMIUM-AVERAGING ONE.
    # All 64 of its 64 firings on the book are LONG options - quantity added
    # to an open long option that had already lost premium. So there was
    # nothing to consolidate: the option case is not a subset of this
    # detector's output, it is the whole of the other one's.
    #
    # What the 44 firings actually were:
    #     21  a prior loser was the same contract, re-entered after closing
    #     23  a prior loser was a different option entirely
    #      9  EVERY prior loser was the opposite type - a CE after a PE lost,
    #         which is a change of view, not an average-down. That is the call
    #         `direction_instability` was retired for being unable to make.
    #      5  LOOK-AHEAD: `session_trades` is EXIT-ordered, so a "prior"
    #         position can still have been OPEN when this trade was entered.
    #         For those the message "You entered X AFTER N losing positions"
    #         was false - the loss it cited had not happened yet.
    #
    # Its real subject was re-entry after a loss, and that is owned elsewhere:
    # `same_symbol_obsession` saw 70% of these firings and `revenge_trade`
    # 48%. It fired alone 7 times in 175 sessions, of which 3 were direction
    # changes and 2 were look-ahead - leaving TWO coherent firings, both of
    # which `same_symbol_obsession` already sees at contract level.
    #
    # NOT REPLACED. No narrowed same-contract variant was built: at that scope
    # it produces 2 events in 175 sessions and duplicates an existing detector.
    #
    # Evidence: docs/patterns/20-options_premium_avg_down/.


    # ── Pattern 18: IV crush behavior ─────────────────────────────────────
    #
    # Proxy: LONG options position losing >40% premium in <30 min.
    # Fast large premium collapse without a large directional move = IV crush.
    # Common pattern: buying before an event (FOMC, results, expiry) when IV is peaked.

    # iv_crush_behavior: MERGED into premium_loss_event (Phase 4, master doc 1).
    # Fast collapse is now a context flag on the same event — one trade, one alert.

    # ── Premium loss event (merged iv_crush + premium_destruction) ─────────
    #
    # Options trade exits losing a large share of premium. Levels (config):
    #   caution  ≥ 40% · danger ≥ 60% · critical ≥ 80%
    # Expiry day shifts all levels up (+15pp default) — deep OTM near expiry
    # loses 40% routinely without any behavioral failure.
    # hold < 30 min flags a fast collapse (IV-crush-like) in context.

    def _detect_premium_loss_event(self, ctx: EngineContext) -> Optional[DetectedEvent]:
        ct = ctx.completed_trade
        if ct.instrument_type not in ("CE", "PE") or ct.direction != "LONG":
            return None

        # Use stored pnl_pct if available; fall back to computing it
        if ct.pnl_pct is not None:
            pnl_pct = float(ct.pnl_pct)
        else:
            entry_price = float(ct.avg_entry_price or 0)
            exit_price  = float(ct.avg_exit_price  or 0)
            if entry_price <= 0:
                return None
            pnl_pct = (exit_price - entry_price) / entry_price * 100
        loss_pct = -pnl_pct  # positive % of premium lost

        # A long option's downside is the premium. Anything past 100% is a
        # defect in the stored pnl_pct, not a real loss — and "180% of premium
        # lost" reaching a trader would cost the credibility of every other
        # number on the screen. Report the truth (total loss) and refuse to
        # assert the impossible percentage.
        if loss_pct > 100:
            logger.warning(
                "[premium_loss_event] %s reported %.0f%% premium loss on a LONG "
                "option — impossible, pnl_pct is wrong. Capped at 100%%.",
                ct.tradingsymbol, loss_pct,
            )
            loss_pct = 100.0
        if loss_pct <= 0:
            return None

        l_caution  = float(ctx.thresholds.get("premium_loss_caution_pct", 40))
        l_danger   = float(ctx.thresholds.get("premium_loss_danger_pct", 60))
        l_critical = float(ctx.thresholds.get("premium_loss_critical_pct", 80))

        # Expiry-day adjustment (master §1D.7 review): thresholds shift up
        try:
            from app.services.instrument_parser import is_expiry_day as _ied
            if ct.exit_time and _ied(ct.tradingsymbol or "", ct.exit_time.astimezone(IST).date()):
                shift = float(ctx.thresholds.get("premium_loss_expiry_shift_pct", 15))
                l_caution += shift
                l_danger += shift
                l_critical += shift
        except Exception:
            pass

        if loss_pct < l_caution:
            return None

        # ANALYTICS ONLY since 2026-08-27 (Pattern #8 review).
        #
        # This path runs on a position that is already CLOSED, and the trader
        # necessarily knows - they just closed it. The alert that can change
        # something is the live one, raised on a band crossing while the position
        # is still open (`services/live_risk_state.py`), and this used to repeat
        # it: the same 80% event was reported once live and once here, because
        # the two paths have separate dedup scopes and nothing reconciles them.
        #
        # `info` is the existing mechanism for exactly this - "recorded as
        # evidence, never sent anywhere" - so demoting it removes the duplicate
        # without any dedup surgery. The BAND is still computed and still stored
        # in the evidence below, because Analytics and the daily report want it.
        band = ("critical" if loss_pct >= l_critical
                else "danger" if loss_pct >= l_danger
                else "caution")
        severity = "info"

        fast_hold = ctx.thresholds.get("premium_loss_fast_hold_min", 30)
        fast_collapse = (ct.duration_minutes is not None
                         and ct.duration_minutes < fast_hold)

        # Repeat destruction today escalates danger -> critical.
        #
        # The `>= 1` below is an INLINE LITERAL WITH NO KEY AND NO SOURCE, and
        # it is load-bearing: measured in the Pattern #8 review it engages on 5
        # of 48 firings and promotes twice, so 2 of the detector's 10 criticals
        # come from this rule rather than from the magnitude of the loss. Both
        # promotions were genuine large losses (85.5% against an expiry-shifted
        # critical level of 95, and 75.6% against 80), which is why the review
        # left it alone rather than changing it. Recorded here so the next person
        # does not have to rediscover that it is unsourced.
        repeat_count = sum(
            1 for t in ctx.session_trades
            if t.id != ct.id and t.instrument_type in ("CE", "PE")
            and t.direction == "LONG" and t.pnl_pct is not None
            and float(t.pnl_pct) <= -l_danger
        )
        # The promotion this rule used to perform (danger -> critical) is gone
        # with the severity it operated on: this path is analytics now. The count
        # itself is kept and still reported, because "two long options past the
        # danger level today" is a fact the daily report can use, and because the
        # live path may want it once it has completed-trade context.

        # This path runs on a CLOSED position. The median flagged trade in the
        # reference book was held 1,341 minutes - overnight - so the present
        # tense read as though something were still happening to a position that
        # no longer existed. The live variant
        # (`live_checks.evaluate_live_premium_loss`, fired from the 60-second
        # position-monitor beat) is the one that speaks while the trade is open
        # and can still be acted on; this one is the record of what happened.
        #
        # "likely bought into peak IV" went with the rewrite: the hold time is
        # observed, the reason for it is not, and this detector has no way to
        # see what implied volatility was at entry.
        speed_note = (f", held {ct.duration_minutes} min"
                      if fast_collapse else "")
        repeat_note = (f" ({repeat_count + 1} long options past the danger level today)"
                       if repeat_count else "")

        return DetectedEvent(
            event_type="premium_loss_event",
            severity=severity,
            message=(
                f"Closed {ct.tradingsymbol} having lost {loss_pct:.0f}% of the "
                f"premium paid (₹{abs(float(ct.realized_pnl or 0)):,.0f})"
                f"{speed_note}{repeat_note}."
            ),
            context={
                "tradingsymbol": ct.tradingsymbol,
                "loss_pct": round(loss_pct, 1),
                "entry_premium": round(float(ct.avg_entry_price or 0), 2),
                "exit_premium": round(float(ct.avg_exit_price or 0), 2),
                "realized_pnl": float(ct.realized_pnl or 0),
                "hold_minutes": ct.duration_minutes,
                "fast_collapse": fast_collapse,
                "repeat_count_today": repeat_count,
                "band": band,
                "levels": {"caution": l_caution, "danger": l_danger, "critical": l_critical},
            },
        )

    # ── RETIRED 2026-08-27 — `expiry_day_overtrading` ─────────────────────
    #
    # Deleted, not demoted. It never withheld: of the 55 positions it was
    # allowed to judge in the 189-session book (expiry + CE/PE/FUT + entry at or
    # after 13:00) it fired on 55 and stayed silent on 0. The cause was a units
    # bug — `today_lots` summed `total_quantity`, which is CONTRACTS
    # (completed_trade.py: "in units, lot_size already factored"), against a
    # threshold of 10. A NIFTY lot is 75, so the only reachable clause was
    # unconditionally true and the trade-count logic decided nothing. 71% of
    # firings came from that clause alone with a count under five; the count was
    # 1 on eight of them.
    #
    # Both trader-facing sentences were unsourced and both measured false. The
    # claimed ">85% structural loss rate in the last 2 hours of expiry day" is
    # 53.8% at 14:00+ and 61.8% at 13:00+, against a book-wide ~60% — no
    # different from the trader's ordinary trading. "Each additional trade after
    # 13:00 reduces your edge" asserts r < 0 and measured r = +0.260 (p = 0.056,
    # n = 55), the opposite sign. The reversal repeats at day level
    # (expiry-trade-count vs session P&L r = +0.107, p = 0.485, n = 45), and this
    # trader's expiry-active sessions are their BETTER sessions (51.1% green
    # against 38.9%). Post-13:00 expiry against all non-expiry trading is
    # Rs 58/trade at p = 0.863.
    #
    # Fixing the units would have moved the pass rate from 100% to 58% —
    # restoring discrimination without creating a finding, because there is no
    # outcome difference to discriminate on. So the units were not fixed.
    #
    # Expiry-day-ness survives where it already earns its place: as a MODIFIER
    # inside detectors that measure a decision — `premium_loss_event`
    # (premium_loss_expiry_shift_pct, +15pp), `no_stoploss`
    # (no_stoploss_expiry_loss_pct / _hold_min) and `fomo_entry`'s context_note.
    # `is_expiry_day` and `count_structures` both keep other readers.
    # See docs/patterns/09-expiry_day_overtrading/.

    # ── Pattern 20: Opening 5-minute trap ─────────────────────────────────
    #
    # Derivative entry in the 09:15–09:20 IST window.
    # First 5 minutes: gaps resolve, order books stabilise, premium pricing is distorted.
    # NSE data: 78% of retail opening-5-min derivative trades are unprofitable.

    # ── RETIRED 2026-08-30 — `opening_5min_trap` ──────────────────────────
    #
    # Pattern 21. THE OPENING WINDOW WAS NOT A WORSE PLACE TO TRADE.
    #
    # It fired on an entry within 10 minutes of 09:15 that LOST and either
    # exited within 15 minutes or lost >= 30% of premium. Its premise was that
    # price discovery makes the opening hazardous. Measured on 175 sessions:
    #
    #     inside 09:15-09:25   n=33   win 39.4%   mean +Rs 99
    #     rest of day          n=707  win 39.5%   mean -Rs 59
    #
    # Win rates 0.1 percentage points apart, and on money the window was
    # BETTER - permutation p = 0.274, so not a real edge in either direction.
    # The window is indistinguishable from the rest of the day for this trader.
    #
    # It reached its finding only by discarding 14 of 33 window entries (42%)
    # for having made money, before any behaviour was examined. That is
    # SELECTION ON OUTCOME - the shape that retired `panic_exit` - and the
    # code's own comment conceded it: "a profitable opening trade could be a
    # deliberate strategy". If the behaviour is indistinguishable and only the
    # result differs, the result is what was being flagged.
    #
    # Its message explained the loss with a mechanism it never measured -
    # "the widest bid-ask spreads of the day". Fairly stated that is market
    # microstructure rather than a fabricated statistic, and it is broadly
    # true; but we store no spread data, and the outcome the detector DOES
    # measure was not worse in that window.
    #
    # Three windows disagreed: the name said 5 minutes, the threshold said 10,
    # the copy said 09:15-09:25. Market open was hardcoded 09:15 while
    # `end_of_session_mis_panic` - reviewed alongside it - derives the
    # equivalent boundary from `exchange_constants`, having fixed exactly that
    # defect for MCX. `opening_trap_quick_exit_min` declared Source.SESSION
    # with metric `hold_minutes_p25`, which `_apply_session` computes and then
    # discards, so it could never personalise.
    #
    # DISTINGUISHED FROM `rapid_reentry`, kept at Pattern 13 while also being
    # info-with-no-reader: that detector's window WAS genuinely selective and
    # only its consumer was missing. This one's window was not selective on
    # anything measurable.
    #
    # THE CONCEPT IS NOT RETIRED PERMANENTLY. Opening spreads are real. What
    # would test it is spread and premium-stability data per fill, which we do
    # not store - recorded rather than proposed.
    #
    # Evidence: docs/patterns/21-session_windows/.


    # ── Pattern 21: End-of-session MIS panic ──────────────────────────────
    #
    # MIS trades entered after 15:00 IST — Zerodha auto-square-off varies by segment:
    #   Equity (NSE/BSE)  → 15:15 IST
    #   F&O    (NFO/BFO)  → 15:25 IST
    # Voluntarily entering a position with minutes until forced exit is panic, not trading.

    def _detect_end_of_session_mis_panic(self, ctx: EngineContext) -> Optional[DetectedEvent]:
        ct = ctx.completed_trade
        if ct.product not in ("MIS", "INTRADAY"):
            return None
        if not ct.entry_time:
            return None

        entry_ist = ct.entry_time.astimezone(IST)

        # Zerodha squareoff time depends on exchange segment. This must be
        # derived from the instrument's own exchange: previously `panic_start`
        # was a flat 15:00 IST with no commodity branch, so for MCX — which
        # trades until 23:30 — EVERY evening MIS entry from 15:00 onward was
        # scored as end-of-session panic. That was hours of false alerts a day
        # for commodity traders, not a missed signal.
        exchange = (ct.exchange or "").upper()
        if exchange in ("NFO", "BFO"):
            squareoff_total_min = 15 * 60 + 25
            squareoff_str = "15:25"
            panic_start_min = 15 * 60            # 15:00 — unchanged
        elif exchange in ("MCX", "CDS", "BCD"):
            from app.core.exchange_constants import get_close_time
            _close_t = get_close_time(exchange)
            # Commodity/currency MIS squares off ~5 min before close.
            squareoff_total_min = _close_t.hour * 60 + _close_t.minute - 5
            squareoff_str = f"{squareoff_total_min // 60:02d}:{squareoff_total_min % 60:02d}"
            # Same 25-minute run-up to squareoff that NFO gets, but anchored to
            # THIS exchange's close rather than 15:00.
            panic_start_min = squareoff_total_min - 25
        else:
            # NSE/BSE equity MIS
            squareoff_total_min = 15 * 60 + 15
            squareoff_str = "15:15"
            panic_start_min = 15 * 60            # 15:00 — unchanged

        panic_start = entry_ist.replace(
            hour=panic_start_min // 60, minute=panic_start_min % 60,
            second=0, microsecond=0,
        )

        if entry_ist < panic_start:
            return None

        # Count all MIS trades entered after 15:00 IST today (include current trade)
        panic_trades = [
            t for t in ctx.session_trades
            if t.product in ("MIS", "INTRADAY")
            and t.entry_time
            and t.entry_time.astimezone(IST) >= panic_start
        ]
        panic_count = len(panic_trades) + 1

        # Phase 4 (master doc 1): all late MIS entries profitable + session green
        # = deliberate late scalping, not panic. Record as info, don't alert.
        late_pnls = [float(t.realized_pnl or 0) for t in panic_trades] + [float(ct.realized_pnl or 0)]
        session_pnl_now = float(ctx.session.session_pnl or 0) if ctx.session else 0
        all_late_profitable = all(p > 0 for p in late_pnls) and session_pnl_now > 0

        caution_count = ctx.thresholds.get("end_session_mis_caution_count", 2)
        danger_count  = ctx.thresholds.get("end_session_mis_danger_count", 3)

        if panic_count >= danger_count:
            return DetectedEvent(
                event_type="end_of_session_mis_panic",
                severity="info" if all_late_profitable else "danger",
                message=(
                    f"{panic_count} MIS trades after 15:00 IST today. "
                    f"Zerodha auto-squares {exchange or 'MIS'} at {squareoff_str}."
                ),
                context={"entry_time_ist": entry_ist.strftime("%H:%M"),
                         "panic_count": panic_count,
                         "squareoff_time": squareoff_str},
            )
        if panic_count >= caution_count:
            mins_remaining = max(0, squareoff_total_min - (entry_ist.hour * 60 + entry_ist.minute))
            if all_late_profitable:
                return None  # deliberate late scalping — not even worth an info row at caution level
            return DetectedEvent(
                event_type="end_of_session_mis_panic",
                severity="caution",
                message=(
                    f"MIS entry at {entry_ist.strftime('%H:%M')} IST — "
                    f"{mins_remaining}min until Zerodha auto-square-off at {squareoff_str}."
                ),
                context={"entry_time_ist": entry_ist.strftime("%H:%M"),
                         "panic_count": panic_count,
                         "mins_to_squareoff": mins_remaining,
                         "squareoff_time": squareoff_str},
            )
        return None

    # ── Pattern 22: Post-loss single large recovery bet ───────────────────
    #
    # After 2+ consecutive losses, trader enters one significantly oversized position.
    # "I'll make it all back in one trade" — the most documented bias in retail trading.
    # Different from martingale (progressive escalation) — this is a single outsized bet.

    def _detect_post_loss_recovery_bet(self, ctx: EngineContext) -> Optional[DetectedEvent]:
        ct = ctx.completed_trade
        trades = ctx.session_trades
        if len(trades) < 3:
            return None

        # Compare ONLY within the same underlying — a Nifty lot (50 qty) vs
        # an Industower lot (2000 qty) are not comparable in raw quantity terms.
        from app.services.instrument_parser import parse_symbol as _ps
        try:
            ct_underlying = _ps(ct.tradingsymbol or "").underlying
        except Exception:
            ct_underlying = ct.tradingsymbol or ""

        # CONCLUDED, for the same reason as martingale_behaviour: "after 2+
        # losses, one oversized bet" is a causal claim. This detector happened to
        # be unaffected on the reference book - 0 of 7 firings - but the code had
        # the identical unguarded shape, so that was luck rather than protection.
        prior = [
            t for t in ctx.concluded_before_entry
            if (_ps(t.tradingsymbol or "").underlying if t.tradingsymbol else "") == ct_underlying
        ]
        if len(prior) < 2:
            return None

        # Last 2 trades on the same underlying must be losses
        last_two_pnls = [Decimal(str(t.realized_pnl or 0)) for t in prior[-2:]]
        if not all(p < 0 for p in last_two_pnls):
            return None

        # Compare current size against the recent average — by quantity within
        # one underlying, by value when the trader has moved between them.
        # F22. This used to branch on `_cross`, testing whether prior[-3:]
        # spanned more than one underlying. It never could: `prior` is built
        # above filtered to `== ct_underlying`, so the set always holds exactly
        # one element and the cross-underlying arm was unreachable. Only the
        # quantity comparison ever ran, and that is what remains.
        recent_qtys = [t.total_quantity or 1 for t in prior[-3:]]
        avg_qty = sum(recent_qtys) / len(recent_qtys)
        current_qty = ct.total_quantity or 1

        if avg_qty < 1:
            return None

        size_ratio = current_qty / avg_qty
        total_prior_loss = sum(abs(p) for p in last_two_pnls)

        caution_mul = ctx.thresholds.get("recovery_bet_caution_mul", 2.0)
        danger_mul  = ctx.thresholds.get("recovery_bet_danger_mul", 3.0)

        base_ctx = {
            "size_ratio": round(size_ratio, 1),
            "current_qty": current_qty,
            "avg_recent_qty": round(avg_qty, 1),
            "prior_total_loss": float(total_prior_loss),
            "underlying": ct_underlying,
            "trigger_symbol": ct.tradingsymbol,
            "prior_trades": [
                {
                    "symbol": t.tradingsymbol or "—",
                    "qty": t.total_quantity or 0,
                    "pnl": float(Decimal(str(t.realized_pnl or 0))),
                    "exit_time_ist": t.exit_time.astimezone(IST).strftime("%H:%M") if t.exit_time else None,
                }
                for t in prior[-3:]
            ],
        }

        if size_ratio >= danger_mul:
            return DetectedEvent(
                event_type="post_loss_recovery_bet",
                severity="danger",
                message=(
                    f"After 2 {ct_underlying} losses (₹{float(total_prior_loss):,.0f} total), "
                    f"your {ct.tradingsymbol} size is {size_ratio:.1f}× your recent {ct_underlying} average."
                ),
                context=base_ctx,
            )
        if size_ratio >= caution_mul:
            return DetectedEvent(
                event_type="post_loss_recovery_bet",
                severity="caution",
                message=(
                    f"After 2 {ct_underlying} losses (₹{float(total_prior_loss):,.0f} total), "
                    f"your {ct.tradingsymbol} size is {size_ratio:.1f}× your recent {ct_underlying} average."
                ),
                context=base_ctx,
            )
        return None

    # ── Pattern 23: Profit giveaway (peak P&L erosion) ────────────────────
    #
    # You had a great session, hit a profit high-watermark, then one trade
    # gave back most of it. Fires exactly once — only when THIS trade first
    # crosses the erosion threshold (not on every subsequent loss).
    #
    # Different from session_meltdown: meltdown fires when you're down X% of
    # your daily LOSS LIMIT (absolute loss). This fires when you give back X%
    # of gains you had already EARNED — even if you're still net positive.
    #
    # Research: NSE/SEBI data shows 38% of profitable intraday sessions end with
    # the trader giving back >50% of peak gains in a single subsequent trade.
    # This is the "one more trade" impulse after a good day.

    # ── Constitution violation (Engine v2 Phase 2, master §1C.4 / Q15) ──────
    #
    # Single pattern_type covering every user-declared rule; the specific rule
    # lives in context["rule"]. Severity ladder per rule:
    #   approaching (80% of rule)  → caution
    #   breached    (100%)         → danger
    #   severe      (120%+)        → critical (guardian-eligible)
    # Binary rules (cooldown, restricted windows) have no "approaching" — they
    # fire danger on violation.
    # Rules only exist if the user declared them; no declaration → no check.

    def _detect_constitution_violation(self, ctx: EngineContext) -> Optional[List[DetectedEvent]]:
        th = ctx.thresholds
        ct = ctx.completed_trade
        approaching = float(th.get("constitution_approaching_pct", 0.80))
        severe = float(th.get("constitution_severe_pct", 1.20))
        events: List[DetectedEvent] = []

        def ladder(ratio: float) -> Optional[str]:
            if ratio >= severe:
                return "critical"
            if ratio >= 1.0:
                return "danger"
            if ratio >= approaching:
                return "caution"
            return None

        def add(rule: str, severity: str, message: str, extra: Dict[str, Any]):
            events.append(DetectedEvent(
                event_type="constitution_violation",
                severity=severity,
                message=message,
                context={"rule": rule, **extra},
            ))

        # ── Rule: daily loss limit ────────────────────────────────────────
        loss_limit = th.get("daily_loss_limit")
        if loss_limit:
            session_pnl = Decimal(str(ctx.session.session_pnl or 0)) if ctx.session else Decimal("0")
            loss = float(-session_pnl) if session_pnl < 0 else 0.0
            ratio = loss / float(loss_limit)
            sev = ladder(ratio)
            if sev:
                if ratio >= 1.0:
                    msg = (f"Your daily loss limit is breached: ₹{loss:,.0f} lost "
                           f"of your ₹{float(loss_limit):,.0f} limit ({ratio*100:.0f}%).")
                else:
                    msg = (f"Approaching your daily loss limit: ₹{loss:,.0f} of "
                           f"₹{float(loss_limit):,.0f} ({ratio*100:.0f}%).")
                add("daily_loss", sev, msg,
                    {"limit": float(loss_limit), "current": round(loss, 2),
                     "ratio": round(ratio, 2)})

        # ── Rule: per-trade loss limit ────────────────────────────────────
        #
        # The most the trader is willing to lose on ONE position, in rupees.
        # Added 1 Sep 2026 (Pattern 24). Opt-in, no suggested value.
        #
        # POSITION-LEVEL, NOT FILL-LEVEL, and that is free rather than enforced:
        # a CompletedTrade is written only when the position returns to zero, so
        # `realized_pnl` already sums every exit tranche. Splitting an exit
        # cannot evade the limit. (Measured: 8 of 740 rounds on the reference
        # book closed in more than one tranche, all as single rows.)
        #
        # MULTI-LEG IS A KNOWN LIMITATION, DELIBERATELY NOT SOLVED HERE. Netting
        # a structure's legs was approved in principle and then measured as
        # unusable: `strategy_detector` groups on "same underlying, entered
        # within 15 minutes", which cannot separate a vertical spread from two
        # independent bets (29 of 48 candidate pairs are the same option type),
        # and 45% of grouped rounds have no closed sibling at their own exit -
        # so the same structure would be judged leg-level at one exit and
        # net-level at the next. `session_meltdown` reads `strategy_group` to
        # SUPPRESS, which fails safe; using it to MEASURE would make a false
        # statement to the trader in either direction. So this rule does NOT
        # read `ctx.strategy_group`: it measures each leg separately, and that
        # is recorded as an observability limitation rather than papered over.
        #
        # RAW P&L, like every other figure in the product - no brokerage, no
        # STT, no tax.
        per_trade_limit = th.get("per_trade_loss_limit")
        if per_trade_limit:
            trade_pnl = Decimal(str(ct.realized_pnl or 0))
            # Only a LOSS can breach a loss limit. A winning trade is not a
            # small breach, it is not a breach.
            if trade_pnl < 0:
                trade_loss = float(-trade_pnl)
                ratio = trade_loss / float(per_trade_limit)
                sev = ladder(ratio)
                if sev:
                    verb = "breached" if ratio >= 1.0 else "approaching"
                    add("per_trade_loss", sev,
                        f"Your per-trade loss limit {verb}: {ct.tradingsymbol} lost "
                        f"₹{trade_loss:,.0f} of your ₹{float(per_trade_limit):,.0f} "
                        f"limit ({ratio*100:.0f}%).",
                        {"limit": float(per_trade_limit),
                         "current": round(trade_loss, 2),
                         "ratio": round(ratio, 2),
                         "trigger_symbol": ct.tradingsymbol})

        # ── Rule: max trades per day ──────────────────────────────────────
        trade_limit = th.get("user_daily_trade_limit")
        if trade_limit:
            count = len(ctx.session_trades) + 1
            ratio = count / float(trade_limit)
            sev = ladder(ratio)
            if sev:
                verb = "breached" if ratio >= 1.0 else "approaching"
                add("daily_trades", sev,
                    f"Your daily trade limit {verb}: {count} of {int(trade_limit)} trades.",
                    {"limit": int(trade_limit), "current": count, "ratio": round(ratio, 2)})

        # ── Rule: max consecutive losses ──────────────────────────────────
        max_consec = th.get("max_consecutive_losses")
        if max_consec:
            # Canonical streak — the same session fact the retired
            # `consecutive_loss_streak` detector read. Since that retirement
            # (2026-08-26) this is the only place a losing run is alerted on, and
            # it is judged against the trader's OWN declared stop point rather
            # than a count the engine picked. See docs/patterns/04-*.
            streak = ctx.facts.consecutive_losses if ctx.facts else 0
            limit = int(max_consec)
            ratio = streak / float(max_consec)
            sev = ladder(ratio)
            # The percentage ladder cannot express "one away" on a small integer
            # rule. A streak moves in whole trades, and 0.80 x 3 = 2.4 and
            # 0.80 x 4 = 3.2 both round up to the limit itself — so for limits of
            # 2, 3 and 4 the first streak that clears `approaching` IS the
            # breach, and the warning rung can never fire. The onboarding default
            # is 3, so most traders got the breach with no run-up at all.
            #
            # No multiplier is needed to fix it, because "approaching" has an
            # exact meaning for a whole-number rule: one more loss breaks it.
            if sev is None and limit >= 2 and streak == limit - 1:
                sev = "caution"
            if sev:
                if ratio >= 1.0:
                    msg = (f"Your consecutive-loss rule breached: {streak} losses "
                           f"in a row (your stop point: {limit}).")
                elif streak == limit - 1:
                    msg = (f"One more loss breaks your consecutive-loss rule: "
                           f"{streak} losses in a row (your stop point: {limit}).")
                else:
                    msg = (f"Your consecutive-loss rule approaching: {streak} "
                           f"losses in a row (your stop point: {limit}).")
                add("max_consecutive_losses", sev, msg,
                    {"limit": limit, "current": streak, "ratio": round(ratio, 2)})

        # ── Rule: cooldown after loss (binary) ────────────────────────────
        cooldown_min = th.get("user_cooldown_min")
        if cooldown_min and ct.entry_time:
            # CONCLUDED, from the shared relation. This spelled the predicate
            # inline as `t.exit_time <= ct.entry_time` while
            # `EngineContext.concluded_before_entry` uses `<`, so the two
            # disagreed at identical timestamps and nothing decided which was
            # right. Measured before the change: the two select different sets
            # on 0 of 740 trades, so this is a consistency fix with no
            # behavioural change - the firing set is unchanged at 181 events
            # against a declared 15-minute cooldown.
            #
            # `<` is the right one: a position closed in the same instant the
            # next was entered was not information the trader acted on.
            prior_losses = [t for t in ctx.concluded_before_entry
                            if Decimal(str(t.realized_pnl or 0)) < 0]
            if prior_losses:
                last_loss = max(prior_losses, key=lambda t: t.exit_time)
                gap_min = (ct.entry_time - last_loss.exit_time).total_seconds() / 60
                if 0 <= gap_min < float(cooldown_min):
                    add("cooldown", "danger",
                        f"Your {int(cooldown_min)}-minute cooldown rule violated: entered "
                        f"{ct.tradingsymbol} {gap_min:.0f} min after a "
                        f"₹{abs(float(last_loss.realized_pnl or 0)):,.0f} loss.",
                        {"limit_min": int(cooldown_min), "gap_min": round(gap_min, 1),
                         "prior_loss": float(last_loss.realized_pnl or 0),
                         "prior_symbol": last_loss.tradingsymbol})

        # ── Rule: restricted windows (binary) ─────────────────────────────
        windows = th.get("restricted_windows") or []
        if windows and ct.entry_time:
            entry_ist = ct.entry_time.astimezone(IST)
            entry_min = entry_ist.hour * 60 + entry_ist.minute
            for w in windows:
                try:
                    start_s, end_s = w.split("-")
                    sh, sm = map(int, start_s.split(":"))
                    eh, em = map(int, end_s.split(":"))
                    if sh * 60 + sm <= entry_min <= eh * 60 + em:
                        add("restricted_window", "danger",
                            f"Your no-trade window ({w} IST) violated: entered "
                            f"{ct.tradingsymbol} at {entry_ist.strftime('%H:%M')}.",
                            {"window": w, "entry_time_ist": entry_ist.strftime("%H:%M")})
                        break
                except (ValueError, AttributeError):
                    continue

        # ── Rule: max capital-at-risk per trade ───────────────────────────
        risk_pct_limit = th.get("max_position_size")
        capital = th.get("trading_capital")
        if risk_pct_limit and capital:
            # F17 - same reasoning as excess_exposure. A trader's own per-trade
            # risk rule is a capital-relative rule, so it must abstain rather
            # than judge against premium, notional or a percentage stand-in.
            rq = quantities_for_trade(ct, margin=ctx.broker_margin)
            if not rq.usable_for_capital_rules:
                # ABSTAIN, and fall through to whatever follows.
                #
                # This was `return events or None`, which was correct only
                # because max_trade_risk happens to be the LAST rule. A rule
                # added below it would have been silently skipped whenever
                # capital was not determinable - on 2% of trades today, and on
                # 100% of them for an exchange the risk layer must abstain on
                # (MCX, CDS, BFO). Abstaining from ONE rule must never abstain
                # from the others.
                logger.debug(
                    "max_trade_risk abstains on %s: %s",
                    ct.tradingsymbol, rq.capital_requirement.note)
            else:
                risk = float(rq.capital_requirement.amount)
                risk_pct = risk / float(capital) * 100
                ratio = risk_pct / float(risk_pct_limit)
                sev = ladder(ratio)
                if sev:
                    verb = "breached" if ratio >= 1.0 else "approaching"
                    add("max_trade_risk", sev,
                        f"Your per-trade risk rule {verb}: {ct.tradingsymbol} risked "
                        f"{risk_pct:.1f}% of capital (your limit: {float(risk_pct_limit):.0f}%).",
                        {"limit_pct": float(risk_pct_limit), "current_pct": round(risk_pct, 2),
                         "ratio": round(ratio, 2), "capital_at_risk": round(risk, 2)})

        return events or None

    # ── Same symbol obsession (Phase 4, doc 4 P27) ──
    #
    # Chasing one underlying: 3+ losses on it today after repeated re-entries.
    # "Not trading. Chasing." Escalates to danger when position size is rising.

    def _detect_same_symbol_obsession(self, ctx: EngineContext) -> Optional[DetectedEvent]:
        """
        Coming back to the same underlying, losing on it, and coming back again.

        REVIEWED 2026-08-24, Pattern #3. What this is NOT: it is not martingale,
        which needs escalation across attempts, and not
        adding_to_adverse_position, which needs an OPEN position being added to.
        Its own subject is the session's relationship with ONE UNDERLYING, and
        on 4 of the 20 episodes in the reference book no other detector fires at
        all - repeated losing attempts at flat or falling size. Nothing else in
        the engine sees persistence without escalation.

        Two corrections, both measured:

        1. Severity used `qtys[-1] > qtys[0]`. Because the last element changes
           as the episode grows, the comparison FLIPPED - four of twenty episodes
           changed severity across their repeats, and changed back. It also
           missed what it existed to catch: a sequence of 75, 150, 375, 75 was
           scored caution because only the endpoints were compared.

           It is now `max(qty) > qty[0]`, which can only ever rise. When size
           does rise in these episodes it rises a long way - minimum 1.67x,
           median 3.00x, and not one rise below 1.5x - so the comparison
           separates "stayed level" from "tripled" rather than splitting hairs.

        2. `obsession_min_reentries` is gone. `losses` is a subset of the
           attempts, so `losses >= 3` implies `attempts >= 3` implies
           `reentries >= 2`. It could never bind, and the minimum attempts
           observed across the whole book is 3.

        A loss-count tier was considered for severity and REJECTED: the
        distribution is {3: 11, 4: 6, 5: 2, 6: 1}, a smooth decay with no break
        anywhere, so any boundary would be a choice presented as a fact.
        """
        ct = ctx.completed_trade
        from app.services.instrument_parser import parse_symbol as _ps

        def _u(sym):
            try:
                return _ps(sym or "").underlying or sym or ""
            except Exception:
                return sym or ""

        underlying = _u(ct.tradingsymbol)
        if not underlying:
            return None

        same = sorted(
            [t for t in ctx.session_trades if t.id != ct.id and _u(t.tradingsymbol) == underlying],
            key=lambda t: t.exit_time or datetime.min.replace(tzinfo=timezone.utc),
        ) + [ct]

        losses = [t for t in same if float(t.realized_pnl or 0) < 0]
        min_losses = ctx.thresholds.get("obsession_min_losses", 3)
        if len(losses) < min_losses:
            return None

        total_loss = sum(abs(float(t.realized_pnl or 0)) for t in losses)
        qtys = [t.total_quantity or 1 for t in same]
        # The peak, not the last. Quantity is comparable here because every
        # strike and expiry of one underlying shares a lot size.
        size_rising = max(qtys) > qtys[0]

        # How many of these "attempts" were actually held at the same time. The
        # count is not changed by this - excluding concurrent positions needs a
        # rule no evidence supports - but the alert must not imply a sequence it
        # has not checked. 24 of 49 firings in the book contain such a pair.
        concurrent_pairs = sum(
            1 for a, b in zip(same, same[1:])
            if a.exit_time and b.entry_time and b.entry_time < a.exit_time
        )

        return DetectedEvent(
            event_type="same_symbol_obsession",
            severity="danger" if size_rising else "caution",
            message=(
                f"{underlying}: {len(losses)} losses across {len(same)} attempts today "
                f"(₹{total_loss:,.0f} total)"
                + (f" and position size reached {max(qtys)} against {qtys[0]} at the start."
                   if size_rising else ".")
            ),
            context={
                "underlying": underlying,
                "attempts": len(same),
                "losses": len(losses),
                "total_loss": round(total_loss, 2),
                "size_rising": size_rising,
                "size_first": qtys[0],
                "size_peak": max(qtys),
                "concurrent_pairs": concurrent_pairs,
                "trade_list": [
                    {"symbol": t.tradingsymbol or "—", "qty": t.total_quantity or 0,
                     "pnl": round(float(t.realized_pnl or 0), 2),
                     "exit_time_ist": t.exit_time.astimezone(IST).strftime("%H:%M") if t.exit_time else None}
                    for t in same
                ],
            },
        )

    # ── Time-of-day bias (Phase 4, doc 4 P28) ──
    #
    # The learned danger_hours (learn_patterns, nightly) finally consumed in
    # real time: trade entered inside a historically losing hour → nudge with
    # the user's own numbers. Needs 30+ sessions of history (config).

    def _detect_time_of_day_bias(self, ctx: EngineContext) -> Optional[DetectedEvent]:
        ct = ctx.completed_trade
        if not ct.entry_time:
            return None
        danger_hours = ctx.thresholds.get("danger_hours") or []
        if not danger_hours:
            return None
        if ctx.thresholds.get("baseline_sessions", 0) < ctx.thresholds.get("tod_bias_min_sessions", 30):
            return None

        entry_hour = ct.entry_time.astimezone(IST).hour
        hit = next((d for d in danger_hours if d.get("hour") == entry_hour), None)
        if not hit:
            return None

        h12 = entry_hour % 12 or 12
        ampm = "AM" if entry_hour < 12 else "PM"
        return DetectedEvent(
            event_type="time_of_day_bias",
            severity="caution",
            message=(
                f"Entered {ct.tradingsymbol} at {ct.entry_time.astimezone(IST).strftime('%H:%M')} — "
                f"historically your {h12} {ampm} hour runs a {hit.get('win_rate', 0):.0f}% win rate "
                f"over {hit.get('trades', 0)} trades (avg ₹{hit.get('avg_pnl', 0):,.0f})."
            ),
            context={
                "entry_hour_ist": entry_hour,
                "historical_win_rate": hit.get("win_rate"),
                "historical_trades": hit.get("trades"),
                "historical_avg_pnl": hit.get("avg_pnl"),
                "trigger_symbol": ct.tradingsymbol,
            },
        )


    # ── Win rate collapse (Phase 7, doc 4 P29 — ANALYTICS-ONLY) ─────────────
    #
    # Never a real-time alert (user review #5: win rate is strategy-dependent;
    # a 30% WR trader with PF 2.3 is excellent). info severity feeds the
    # Strategy Health driver only. Guards against noise: needs 8+ trades today
    # AND a trade-count-confident baseline.

    def _detect_win_rate_collapse(self, ctx: EngineContext) -> Optional[DetectedEvent]:
        baseline = ctx.thresholds.get("baseline_win_rate")
        if not baseline or (baseline.get("confidence") or 0) < 0.5:
            return None
        trades = list(ctx.session_trades) + [ctx.completed_trade]
        n = len(trades)
        if n < 8:
            return None
        wins = sum(1 for t in trades if float(t.realized_pnl or 0) > 0)
        today_wr = wins / n * 100
        base_wr = float(baseline["value"])
        if base_wr <= 0:
            return None
        deterioration = (base_wr - today_wr) / base_wr
        if deterioration < 0.4:  # severe tier only — mild tiers are pure variance
            return None
        return DetectedEvent(
            event_type="win_rate_collapse",
            severity="info",
            confidence=min(100.0, float(baseline.get("confidence", 0.5)) * 100),
            message=(
                f"Today's win rate {today_wr:.0f}% vs your {base_wr:.0f}% baseline "
                f"({n} trades). Strategy or conditions, not psychology."
            ),
            context={"today_win_rate": round(today_wr, 1), "baseline_win_rate": base_wr,
                     "deterioration_pct": round(deterioration * 100, 1), "trades_today": n},
        )

    # ── Strategy breakdown (Phase 7, doc 4 P30 — ANALYTICS-ONLY) ────────────
    #
    # Multi-signal degradation: win rate collapse AND profit factor collapse
    # together. Statistically sounder than either alone. info → Strategy driver.

    def _detect_strategy_breakdown(self, ctx: EngineContext) -> Optional[DetectedEvent]:
        wr_base = ctx.thresholds.get("baseline_win_rate")
        pf_base = ctx.thresholds.get("baseline_profit_factor")
        if not wr_base or not pf_base:
            return None
        if (wr_base.get("confidence") or 0) < 0.5 or (pf_base.get("confidence") or 0) < 0.5:
            return None
        trades = list(ctx.session_trades) + [ctx.completed_trade]
        n = len(trades)
        if n < 8:
            return None
        pnls = [float(t.realized_pnl or 0) for t in trades]
        wins = sum(1 for p in pnls if p > 0)
        gross_win = sum(p for p in pnls if p > 0)
        gross_loss = abs(sum(p for p in pnls if p < 0))
        if gross_loss <= 0:
            return None
        today_wr = wins / n * 100
        today_pf = gross_win / gross_loss
        base_wr = float(wr_base["value"])
        base_pf = float(pf_base["value"])
        if base_wr <= 0 or base_pf <= 0:
            return None
        wr_collapsed = (base_wr - today_wr) / base_wr >= 0.4
        pf_collapsed = today_pf <= base_pf * 0.5
        if not (wr_collapsed and pf_collapsed):
            return None
        return DetectedEvent(
            event_type="strategy_breakdown",
            severity="info",
            confidence=min(100.0, min(float(wr_base.get("confidence", 0.5)),
                                      float(pf_base.get("confidence", 0.5))) * 100),
            message=(
                f"Multiple performance signals degrading: win rate "
                f"{today_wr:.0f}% (baseline {base_wr:.0f}%) and profit factor "
                f"{today_pf:.2f} (baseline {base_pf:.2f}) over {n} trades today."
            ),
            context={"today_win_rate": round(today_wr, 1), "baseline_win_rate": base_wr,
                     "today_profit_factor": round(today_pf, 2),
                     "baseline_profit_factor": base_pf, "trades_today": n},
        )


# Singleton
behavior_engine = BehaviorEngine()
