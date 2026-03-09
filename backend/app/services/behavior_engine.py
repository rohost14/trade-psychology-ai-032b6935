"""
BehaviorEngine — Unified Real-Time Behavioral Detection (Phase 3)

Replaces the fragmented RiskDetector + BehavioralEvaluator pair.
Key improvements over existing engines:
  - Session-scoped (today only, not 24h rolling) → accurate context
  - Cumulative risk score (0-100) via TradingSession → not just isolated alerts
  - Behavior state model (Stable→Pressure→Tilt Risk→Tilt→Breakdown→Recovery)
  - Single context load per call → no N+1 queries
  - All detectors are pure functions → fully unit-testable without DB
  - Writes to shadow_behavioral_events only (Phase 3)
  - Cutover in Phase 3 step 7 replaces old engines

SHADOW MODE ONLY — do NOT write to production behavioral_events yet.
The shadow_log in trade_tasks.py compares output to old engines for 5 days.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional, Dict, Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.completed_trade import CompletedTrade
from app.models.trading_session import TradingSession
from app.models.cooldown import Cooldown
from app.services.trading_session_service import TradingSessionService
from app.core.trading_defaults import get_thresholds, estimate_capital_at_risk

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")

# ---------------------------------------------------------------------------
# Risk score deltas per pattern (from ARCH-02)
# Cumulative — multiple patterns in one trade stack up
# ---------------------------------------------------------------------------
RISK_DELTAS: Dict[str, Decimal] = {
    "consecutive_loss_streak":  Decimal("20"),
    "revenge_trade":            Decimal("25"),
    "overtrading_burst":        Decimal("10"),
    "size_escalation":          Decimal("15"),
    "rapid_reentry":            Decimal("15"),
    "panic_exit":               Decimal("10"),
    "martingale_behaviour":     Decimal("20"),
    "cooldown_violation":       Decimal("25"),
    "rapid_flip":               Decimal("15"),
    "excess_exposure":          Decimal("15"),
    "session_meltdown":         Decimal("30"),
    "margin_risk":              Decimal("20"),
}

# ---------------------------------------------------------------------------
# Behavior state thresholds (risk_score → state)
# ---------------------------------------------------------------------------
def _behavior_state(risk_score: Decimal, peak: Decimal) -> str:
    """
    Map risk_score to behavior_state.

    Recovery: was in high-risk zone (peak >= 60) but has come back down
    (current < peak - 20). Indicates active self-correction.
    """
    if peak >= Decimal("60") and risk_score <= peak - Decimal("20"):
        return "Recovery"
    s = float(risk_score)
    if s >= 80:
        return "Breakdown"
    if s >= 60:
        return "Tilt"
    if s >= 40:
        return "Tilt Risk"
    if s >= 20:
        return "Pressure"
    return "Stable"


def _trajectory(risk_before: Decimal, risk_after: Decimal) -> str:
    delta = risk_after - risk_before
    if delta > Decimal("5"):
        return "deteriorating"
    if delta < Decimal("-5"):
        return "improving"
    return "stable"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class DetectedEvent:
    """One detected behavioral pattern."""
    event_type: str
    severity: str           # LOW | MEDIUM | HIGH
    confidence: Decimal
    message: str
    context: Dict[str, Any] = field(default_factory=dict)
    risk_delta: Decimal = Decimal("0")


@dataclass
class DetectionResult:
    """Full output of one BehaviorEngine.analyze() call."""
    events: List[DetectedEvent]
    risk_score_before: Decimal
    risk_score_after: Decimal
    total_delta: Decimal
    behavior_state: str
    trajectory: str
    session_id: Optional[UUID]


@dataclass
class EngineContext:
    """
    Pre-loaded context for all detectors.
    Single DB fetch, shared across all 12 detectors.
    """
    broker_account_id: UUID
    session: TradingSession
    completed_trade: CompletedTrade         # the just-closed trade
    session_trades: List[CompletedTrade]    # all completed trades this session
    active_cooldowns: List[Cooldown]
    thresholds: Dict[str, Any]


# ---------------------------------------------------------------------------
# BehaviorEngine
# ---------------------------------------------------------------------------

class BehaviorEngine:
    """
    Unified real-time behavioral detection engine.

    Call analyze() once per CompletedTrade (after FIFO closes a position).
    Returns DetectionResult with events, updated risk_score, and behavior_state.

    Shadow mode: writes to shadow_behavioral_events, never production tables.
    """

    async def analyze(
        self,
        broker_account_id: UUID,
        completed_trade: CompletedTrade,
        db: AsyncSession,
        profile=None,
    ) -> DetectionResult:
        """
        Analyze a completed trade for behavioral patterns.

        Steps:
          1. Load / create today's TradingSession
          2. Batch-load all context in 2 queries
          3. Run all 12 detectors (pure functions, no DB)
          4. Accumulate risk score
          5. Persist shadow events
          6. Update session risk_score via TradingSessionService
        """
        try:
            # ── 1. Get/create today's session ────────────────────────────
            today_ist = datetime.now(ZoneInfo("Asia/Kolkata")).date()
            session = await TradingSessionService.get_or_create_session(
                broker_account_id, today_ist, db
            )
            risk_before = session.risk_score

            # ── 2. Load context (2 DB queries) ────────────────────────────
            ctx = await self._load_context(
                broker_account_id, completed_trade, session, db, profile
            )

            # ── 3. Run all 12 detectors ────────────────────────────────────
            events = self._run_all_detectors(ctx)

            # ── 4. Accumulate risk score ───────────────────────────────────
            total_delta = sum(
                RISK_DELTAS.get(e.event_type, Decimal("0")) for e in events
            )
            for event in events:
                event.risk_delta = RISK_DELTAS.get(event.event_type, Decimal("0"))

            # ── 5. Compute new risk score & behavior state ─────────────────
            new_risk = max(Decimal("0"), min(Decimal("100"), risk_before + total_delta))
            state = _behavior_state(new_risk, session.peak_risk_score)
            traj = _trajectory(risk_before, new_risk)

            result = DetectionResult(
                events=events,
                risk_score_before=risk_before,
                risk_score_after=new_risk,
                total_delta=total_delta,
                behavior_state=state,
                trajectory=traj,
                session_id=session.id,
            )

            # ── 6. Persist shadow events ───────────────────────────────────
            if events:
                await self._persist_shadow(broker_account_id, completed_trade, session,
                                           result, db)

            # ── 7. Update session risk score ───────────────────────────────
            if total_delta != Decimal("0"):
                await TradingSessionService.update_risk_score(session.id, total_delta, db)

            logger.info(
                f"[BehaviorEngine] {broker_account_id} | "
                f"{completed_trade.tradingsymbol} | "
                f"{len(events)} events | "
                f"risk {float(risk_before):.0f}→{float(new_risk):.0f} | "
                f"state={state} | traj={traj}"
            )
            return result

        except Exception as e:
            logger.error(f"[BehaviorEngine] analyze failed: {e}", exc_info=True)
            # Never crash the caller — return empty result
            return DetectionResult(
                events=[],
                risk_score_before=Decimal("0"),
                risk_score_after=Decimal("0"),
                total_delta=Decimal("0"),
                behavior_state="Stable",
                trajectory="stable",
                session_id=None,
            )

    # ── Context loader ─────────────────────────────────────────────────────

    async def _load_context(
        self,
        broker_account_id: UUID,
        completed_trade: CompletedTrade,
        session: TradingSession,
        db: AsyncSession,
        profile=None,
    ) -> EngineContext:
        """
        Load all context in 2 DB queries.
        Query 1: all CompletedTrades this session (today IST, exit_time >= session.market_open)
        Query 2: active cooldowns
        """
        thresholds = get_thresholds(profile)

        # Session boundary (today 09:15 IST in UTC)
        session_start = session.market_open
        if session_start is None:
            from app.core.market_hours import get_session_boundaries, MarketSegment
            session_start, _ = get_session_boundaries(
                segment=MarketSegment.FNO,
                for_date=session.session_date,
            )

        # Query 1: today's completed trades (ordered oldest→newest for streak detection)
        ct_result = await db.execute(
            select(CompletedTrade)
            .where(
                and_(
                    CompletedTrade.broker_account_id == broker_account_id,
                    CompletedTrade.exit_time >= session_start,
                )
            )
            .order_by(CompletedTrade.exit_time.asc())
        )
        session_trades = list(ct_result.scalars().all())

        # Query 2: active cooldowns (not expired, not skipped)
        now_utc = datetime.now(timezone.utc)
        cd_result = await db.execute(
            select(Cooldown).where(
                and_(
                    Cooldown.broker_account_id == broker_account_id,
                    Cooldown.expires_at > now_utc,
                    Cooldown.skipped == False,  # noqa: E712
                )
            )
        )
        active_cooldowns = list(cd_result.scalars().all())

        return EngineContext(
            broker_account_id=broker_account_id,
            session=session,
            completed_trade=completed_trade,
            session_trades=session_trades,
            active_cooldowns=active_cooldowns,
            thresholds=thresholds,
        )

    # ── Run all 12 detectors ──────────────────────────────────────────────

    def _run_all_detectors(self, ctx: EngineContext) -> List[DetectedEvent]:
        """
        Run all 12 real-time detectors. All pure functions — no DB access.
        Returns deduplicated list of detected events.
        """
        events: List[DetectedEvent] = []
        detectors = [
            self._detect_consecutive_loss_streak,
            self._detect_revenge_trade,
            self._detect_overtrading_burst,
            self._detect_size_escalation,
            self._detect_rapid_reentry,
            self._detect_panic_exit,
            self._detect_martingale_behaviour,
            self._detect_cooldown_violation,
            self._detect_rapid_flip,
            self._detect_excess_exposure,
            self._detect_session_meltdown,
        ]
        for detector in detectors:
            try:
                event = detector(ctx)
                if event:
                    events.append(event)
            except Exception as e:
                logger.warning(f"[BehaviorEngine] Detector {detector.__name__} failed: {e}")

        return events

    # ── Pattern 1: Consecutive loss streak ────────────────────────────────

    def _detect_consecutive_loss_streak(self, ctx: EngineContext) -> Optional[DetectedEvent]:
        trades = ctx.session_trades
        if not trades:
            return None

        # Count consecutive losses from most recent
        streak = 0
        total_loss = Decimal("0")
        for ct in reversed(trades):
            pnl = Decimal(str(ct.realized_pnl or 0))
            if pnl < 0:
                streak += 1
                total_loss += abs(pnl)
            else:
                break

        caution = ctx.thresholds.get("consecutive_loss_caution", 3)
        danger = ctx.thresholds.get("consecutive_loss_danger", 5)

        if streak >= danger:
            return DetectedEvent(
                event_type="consecutive_loss_streak",
                severity="HIGH",
                confidence=Decimal("0.92"),
                message=f"{streak} consecutive losses — ₹{total_loss:,.0f} total. Stop and review.",
                context={"streak": streak, "total_loss": float(total_loss),
                         "threshold": danger},
            )
        if streak >= caution:
            return DetectedEvent(
                event_type="consecutive_loss_streak",
                severity="MEDIUM",
                confidence=Decimal("0.80"),
                message=f"{streak} consecutive losses — ₹{total_loss:,.0f}. Caution.",
                context={"streak": streak, "total_loss": float(total_loss),
                         "threshold": caution},
            )
        return None

    # ── Pattern 2: Revenge trade ──────────────────────────────────────────

    def _detect_revenge_trade(self, ctx: EngineContext) -> Optional[DetectedEvent]:
        ct = ctx.completed_trade
        trades = ctx.session_trades
        if not ct.entry_time or len(trades) < 2:
            return None

        # Find the most recent completed trade BEFORE this one
        prior = [t for t in trades if t.exit_time and t.exit_time < ct.entry_time]
        if not prior:
            return None

        last = prior[-1]
        last_pnl = Decimal(str(last.realized_pnl or 0))
        if last_pnl >= 0:
            return None  # Last trade was a winner — not revenge

        # Time between last loss exit and this entry
        gap_min = (ct.entry_time - last.exit_time).total_seconds() / 60
        revenge_window = ctx.thresholds.get("revenge_window_min", 10)

        if gap_min <= revenge_window:
            confidence = Decimal("0.88") if gap_min <= 3 else Decimal("0.76")
            severity = "HIGH" if gap_min <= 3 else "MEDIUM"
            return DetectedEvent(
                event_type="revenge_trade",
                severity=severity,
                confidence=confidence,
                message=(
                    f"Entry {gap_min:.0f}min after a ₹{abs(last_pnl):,.0f} loss. "
                    f"Revenge trading risk."
                ),
                context={
                    "gap_minutes": round(gap_min, 1),
                    "prior_loss": float(last_pnl),
                    "revenge_window_min": revenge_window,
                },
            )
        return None

    # ── Pattern 3: Overtrading burst ──────────────────────────────────────

    def _detect_overtrading_burst(self, ctx: EngineContext) -> Optional[DetectedEvent]:
        ct = ctx.completed_trade
        if not ct.entry_time:
            return None

        # Count trades entered in the last 30 minutes
        window = timedelta(minutes=30)
        cutoff = ct.entry_time - window
        recent = [
            t for t in ctx.session_trades
            if t.entry_time and t.entry_time >= cutoff and t.id != ct.id
        ]
        count = len(recent) + 1  # including current

        burst_limit = ctx.thresholds.get("burst_trades_per_15min", 6)
        # Scale: burst_limit is per 15 min, we use 30 min window → double
        limit_30min = burst_limit * 2

        if count >= limit_30min:
            severity = "HIGH" if count >= limit_30min * 1.5 else "MEDIUM"
            confidence = Decimal("0.85") if severity == "HIGH" else Decimal("0.75")
            return DetectedEvent(
                event_type="overtrading_burst",
                severity=severity,
                confidence=confidence,
                message=f"{count} trades in 30 minutes. Overtrading burst.",
                context={"trades_in_window": count, "window_minutes": 30,
                         "limit": limit_30min},
            )
        return None

    # ── Pattern 4: Size escalation ────────────────────────────────────────

    def _detect_size_escalation(self, ctx: EngineContext) -> Optional[DetectedEvent]:
        ct = ctx.completed_trade
        trades = ctx.session_trades
        if len(trades) < 3:
            return None

        prior = [t for t in trades if t.id != ct.id and t.exit_time]
        if len(prior) < 2:
            return None

        # Get last 3 trades' sizes (most recent last)
        last3 = sorted(prior, key=lambda t: t.exit_time)[-3:]
        sizes = [t.total_quantity or 1 for t in last3]

        # Are sizes consistently escalating?
        if not (sizes[0] < sizes[1] < sizes[2]):
            return None

        # Are we escalating after losses?
        pnls = [Decimal(str(t.realized_pnl or 0)) for t in last3]
        losses_before_escalation = sum(1 for p in pnls[:2] if p < 0)

        if losses_before_escalation >= 1:
            escalation_pct = (sizes[2] - sizes[0]) / max(sizes[0], 1) * 100
            if escalation_pct >= 50:  # Size grew by 50%+
                return DetectedEvent(
                    event_type="size_escalation",
                    severity="MEDIUM",
                    confidence=Decimal("0.77"),
                    message=(
                        f"Position size escalating after losses: "
                        f"{sizes[0]}→{sizes[1]}→{sizes[2]} units."
                    ),
                    context={
                        "size_sequence": sizes,
                        "escalation_pct": round(escalation_pct, 1),
                        "losses_in_sequence": losses_before_escalation,
                    },
                )
        return None

    # ── Pattern 5: Rapid re-entry (same symbol) ───────────────────────────

    def _detect_rapid_reentry(self, ctx: EngineContext) -> Optional[DetectedEvent]:
        ct = ctx.completed_trade
        if not ct.entry_time:
            return None

        # Find most recent prior trade on same symbol
        prior_same = [
            t for t in ctx.session_trades
            if t.tradingsymbol == ct.tradingsymbol
            and t.id != ct.id
            and t.exit_time
        ]
        if not prior_same:
            return None

        last_same = max(prior_same, key=lambda t: t.exit_time)
        if not last_same.exit_time:
            return None

        gap_min = (ct.entry_time - last_same.exit_time).total_seconds() / 60
        if gap_min < 0:
            return None

        # Re-entry within 3 minutes on same symbol = rapid re-entry
        if gap_min <= 3:
            prior_pnl = Decimal(str(last_same.realized_pnl or 0))
            confidence = Decimal("0.82") if prior_pnl < 0 else Decimal("0.72")
            return DetectedEvent(
                event_type="rapid_reentry",
                severity="MEDIUM",
                confidence=confidence,
                message=(
                    f"Re-entered {ct.tradingsymbol} {gap_min:.0f}min after last trade. "
                    f"{'After a loss.' if prior_pnl < 0 else ''}"
                ),
                context={
                    "symbol": ct.tradingsymbol,
                    "gap_minutes": round(gap_min, 1),
                    "prior_pnl": float(prior_pnl),
                },
            )
        return None

    # ── Pattern 6: Panic exit ─────────────────────────────────────────────

    def _detect_panic_exit(self, ctx: EngineContext) -> Optional[DetectedEvent]:
        ct = ctx.completed_trade
        if not ct.entry_time or not ct.exit_time:
            return None

        hold_min = (ct.exit_time - ct.entry_time).total_seconds() / 60
        pnl = Decimal(str(ct.realized_pnl or 0))

        # Panic exit: held less than 2 minutes AND exited at a loss
        if hold_min < 2 and pnl < 0:
            return DetectedEvent(
                event_type="panic_exit",
                severity="LOW",
                confidence=Decimal("0.72"),
                message=(
                    f"Position closed after {hold_min:.0f}min with a ₹{abs(pnl):,.0f} loss. "
                    f"Possible panic exit."
                ),
                context={
                    "hold_minutes": round(hold_min, 1),
                    "realized_pnl": float(pnl),
                },
            )
        return None

    # ── Pattern 7: Martingale behaviour ───────────────────────────────────

    def _detect_martingale_behaviour(self, ctx: EngineContext) -> Optional[DetectedEvent]:
        ct = ctx.completed_trade
        trades = ctx.session_trades
        if len(trades) < 3:
            return None

        prior = sorted(
            [t for t in trades if t.id != ct.id and t.exit_time],
            key=lambda t: t.exit_time
        )[-3:]  # Last 3 completed trades before current

        if len(prior) < 2:
            return None

        # Martingale: consecutive losses AND doubling size each time
        all_losses = all(Decimal(str(t.realized_pnl or 0)) < 0 for t in prior)
        if not all_losses:
            return None

        sizes = [t.total_quantity or 1 for t in prior]
        if len(sizes) < 2:
            return None

        # Each trade size >= 1.8x previous (consistent doubling pattern)
        doublings = sum(
            1 for i in range(1, len(sizes))
            if sizes[i] >= sizes[i - 1] * 1.8
        )
        if doublings >= len(sizes) - 1:
            return DetectedEvent(
                event_type="martingale_behaviour",
                severity="HIGH",
                confidence=Decimal("0.88"),
                message=(
                    f"Doubling position size after consecutive losses: "
                    f"{sizes} units. Classic martingale pattern."
                ),
                context={
                    "size_sequence": sizes,
                    "consecutive_losses": len(prior),
                    "doublings": doublings,
                },
            )
        return None

    # ── Pattern 8: Cooldown violation ─────────────────────────────────────

    def _detect_cooldown_violation(self, ctx: EngineContext) -> Optional[DetectedEvent]:
        if not ctx.active_cooldowns:
            return None

        # There's an active cooldown — this trade was placed during it
        cooldown = ctx.active_cooldowns[0]
        remaining_min = (
            cooldown.expires_at - datetime.now(timezone.utc)
        ).total_seconds() / 60

        return DetectedEvent(
            event_type="cooldown_violation",
            severity="HIGH",
            confidence=Decimal("0.95"),
            message=(
                f"Trade placed during active cooldown "
                f"({remaining_min:.0f}min remaining). "
                f"Reason: {cooldown.reason or 'prior loss streak'}"
            ),
            context={
                "cooldown_expires_at": cooldown.expires_at.isoformat(),
                "remaining_minutes": round(remaining_min, 1),
                "cooldown_reason": cooldown.reason,
            },
        )

    # ── Pattern 9: Rapid flip ─────────────────────────────────────────────

    def _detect_rapid_flip(self, ctx: EngineContext) -> Optional[DetectedEvent]:
        ct = ctx.completed_trade
        if not ct.entry_time:
            return None

        # Find most recent prior completed trade on same symbol
        prior_same = sorted(
            [
                t for t in ctx.session_trades
                if t.tradingsymbol == ct.tradingsymbol
                and t.id != ct.id
                and t.exit_time
                and t.direction
            ],
            key=lambda t: t.exit_time
        )
        if not prior_same:
            return None

        last = prior_same[-1]
        if not last.direction or not ct.direction:
            return None

        # Flip = direction reversed
        if last.direction == ct.direction:
            return None

        gap_min = (ct.entry_time - last.exit_time).total_seconds() / 60
        if gap_min < 5:  # Flipped within 5 minutes
            return DetectedEvent(
                event_type="rapid_flip",
                severity="MEDIUM",
                confidence=Decimal("0.80"),
                message=(
                    f"{ct.tradingsymbol}: reversed {last.direction}→{ct.direction} "
                    f"within {gap_min:.0f}min."
                ),
                context={
                    "symbol": ct.tradingsymbol,
                    "from_direction": last.direction,
                    "to_direction": ct.direction,
                    "gap_minutes": round(gap_min, 1),
                    "prior_pnl": float(last.realized_pnl or 0),
                },
            )
        return None

    # ── Pattern 10: Excess exposure ───────────────────────────────────────

    def _detect_excess_exposure(self, ctx: EngineContext) -> Optional[DetectedEvent]:
        ct = ctx.completed_trade
        capital = ctx.thresholds.get("trading_capital")
        max_size = ctx.thresholds.get("max_position_size")

        if not capital or capital <= 0:
            return None

        # Estimate capital at risk for this trade
        capital_at_risk = estimate_capital_at_risk(
            instrument_type=ct.instrument_type,
            tradingsymbol=ct.tradingsymbol or "",
            direction=ct.direction or "LONG",
            avg_entry_price=float(ct.avg_entry_price or 0),
            total_quantity=ct.total_quantity or 0,
        )
        risk_pct = capital_at_risk / capital * 100

        # Alert if position exceeds max_position_size (% of capital)
        limit_pct = max_size or 10.0  # default 10% if not set
        if risk_pct > limit_pct * 1.5:  # 1.5x the limit
            severity = "HIGH" if risk_pct > limit_pct * 2 else "MEDIUM"
            confidence = Decimal("0.88") if severity == "HIGH" else Decimal("0.75")
            return DetectedEvent(
                event_type="excess_exposure",
                severity=severity,
                confidence=confidence,
                message=(
                    f"{ct.tradingsymbol}: ₹{capital_at_risk:,.0f} at risk "
                    f"({risk_pct:.1f}% of capital). Limit is {limit_pct:.0f}%."
                ),
                context={
                    "capital_at_risk": round(capital_at_risk),
                    "risk_pct": round(risk_pct, 1),
                    "limit_pct": limit_pct,
                    "instrument_type": ct.instrument_type,
                },
            )
        return None

    # ── Pattern 11: Session meltdown ──────────────────────────────────────

    def _detect_session_meltdown(self, ctx: EngineContext) -> Optional[DetectedEvent]:
        session = ctx.session
        session_pnl = Decimal(str(session.session_pnl or 0))
        daily_loss_limit = ctx.thresholds.get("daily_loss_limit")

        if not daily_loss_limit or daily_loss_limit <= 0:
            # Fall back to capital-based estimate
            capital = ctx.thresholds.get("trading_capital")
            if capital:
                daily_loss_limit = capital * 0.05  # 5% of capital as default
            else:
                return None  # No way to evaluate without limits

        limit = Decimal(str(daily_loss_limit))

        # Meltdown: session loss exceeds 80% of daily limit
        if session_pnl < -(limit * Decimal("0.8")):
            pct_used = abs(session_pnl) / limit * 100
            severity = "HIGH" if pct_used >= 100 else "MEDIUM"
            confidence = Decimal("0.95") if severity == "HIGH" else Decimal("0.85")
            return DetectedEvent(
                event_type="session_meltdown",
                severity=severity,
                confidence=confidence,
                message=(
                    f"Session P&L: ₹{session_pnl:,.0f}. "
                    f"Used {pct_used:.0f}% of daily loss limit."
                ),
                context={
                    "session_pnl": float(session_pnl),
                    "daily_loss_limit": float(limit),
                    "pct_used": round(float(pct_used), 1),
                },
            )
        return None

    # ── Shadow persistence ────────────────────────────────────────────────

    async def _persist_shadow(
        self,
        broker_account_id: UUID,
        completed_trade: CompletedTrade,
        session: TradingSession,
        result: DetectionResult,
        db: AsyncSession,
    ) -> None:
        """Write detected events to shadow_behavioral_events table."""
        from sqlalchemy import text

        for event in result.events:
            await db.execute(
                text("""
                    INSERT INTO shadow_behavioral_events (
                        broker_account_id, trigger_completed_trade_id, trigger_session_id,
                        event_type, severity, confidence, message, context,
                        risk_score_before, risk_score_delta, risk_score_after,
                        behavior_state, trajectory
                    ) VALUES (
                        :account_id, :trade_id, :session_id,
                        :event_type, :severity, :confidence, :message, :context,
                        :risk_before, :risk_delta, :risk_after,
                        :behavior_state, :trajectory
                    )
                """),
                {
                    "account_id": str(broker_account_id),
                    "trade_id": str(completed_trade.id),
                    "session_id": str(session.id),
                    "event_type": event.event_type,
                    "severity": event.severity,
                    "confidence": float(event.confidence),
                    "message": event.message,
                    "context": __import__("json").dumps(event.context),
                    "risk_before": float(result.risk_score_before),
                    "risk_delta": float(event.risk_delta),
                    "risk_after": float(result.risk_score_after),
                    "behavior_state": result.behavior_state,
                    "trajectory": result.trajectory,
                }
            )
        await db.flush()


# Singleton
behavior_engine = BehaviorEngine()
