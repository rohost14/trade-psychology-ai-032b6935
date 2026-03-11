"""
BehaviorEngine — Unified Real-Time Behavioral Detection (Phase 3 — PRODUCTION)

Replaces RiskDetector + BehavioralEvaluator.

Key improvements:
  - Session-scoped (today only, not 24h rolling)
  - Cumulative risk score (0-100) via TradingSession
  - Behavior state model: Stable → Pressure → Tilt Risk → Tilt → Breakdown → Recovery
  - Single context load per call (2 DB queries for all patterns)
  - All detectors are pure functions (no DB access inside detectors)
  - Returns RiskAlert objects — plugs directly into existing dedup/notification pipeline

Severity vocabulary: matches existing RiskAlert convention
  "danger"  — HIGH risk, action required (maps to DANGER alerts)
  "caution" — MEDIUM risk, awareness needed

Patterns (11 real-time, run on every completed trade):
  consecutive_loss_streak, revenge_trade, overtrading_burst,
  size_escalation, rapid_reentry, panic_exit, martingale_behaviour,
  cooldown_violation, rapid_flip, excess_exposure, session_meltdown
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional, Dict, Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.completed_trade import CompletedTrade
from app.models.trading_session import TradingSession
from app.models.cooldown import Cooldown
from app.models.risk_alert import RiskAlert
from app.services.trading_session_service import TradingSessionService
from app.core.trading_defaults import get_thresholds, estimate_capital_at_risk

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")

# ---------------------------------------------------------------------------
# Risk score deltas per pattern
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
}

# ---------------------------------------------------------------------------
# Behavior state
# ---------------------------------------------------------------------------

def _behavior_state(risk_score: Decimal, peak: Decimal) -> str:
    if peak >= Decimal("60") and risk_score <= peak - Decimal("20"):
        return "Recovery"
    s = float(risk_score)
    if s >= 80: return "Breakdown"
    if s >= 60: return "Tilt"
    if s >= 40: return "Tilt Risk"
    if s >= 20: return "Pressure"
    return "Stable"


def _trajectory(risk_before: Decimal, risk_after: Decimal) -> str:
    delta = risk_after - risk_before
    if delta > Decimal("5"):  return "deteriorating"
    if delta < Decimal("-5"): return "improving"
    return "stable"


# ---------------------------------------------------------------------------
# Internal data classes
# ---------------------------------------------------------------------------

@dataclass
class DetectedEvent:
    """Internal representation of one detected pattern."""
    event_type: str
    severity: str       # "danger" | "caution"
    message: str
    context: Dict[str, Any] = field(default_factory=dict)
    risk_delta: Decimal = Decimal("0")


@dataclass
class DetectionResult:
    """Full output of one BehaviorEngine.analyze() call."""
    alerts: List[RiskAlert]          # ready to save to risk_alerts table
    risk_score_before: Decimal
    risk_score_after: Decimal
    total_delta: Decimal
    behavior_state: str
    trajectory: str
    session_id: Optional[UUID]


@dataclass
class EngineContext:
    """Pre-loaded context shared across all detectors. Single DB fetch."""
    broker_account_id: UUID
    session: TradingSession
    completed_trade: CompletedTrade
    session_trades: List[CompletedTrade]
    active_cooldowns: List[Cooldown]
    thresholds: Dict[str, Any]


# ---------------------------------------------------------------------------
# BehaviorEngine
# ---------------------------------------------------------------------------

class BehaviorEngine:
    """
    Unified real-time behavioral detection engine.

    analyze() is called once per CompletedTrade (after FIFO closes a position).
    Returns DetectionResult with RiskAlert objects ready to save.

    Replaces RiskDetector + BehavioralEvaluator in trade_tasks.py.
    """

    async def analyze(
        self,
        broker_account_id: UUID,
        completed_trade: CompletedTrade,
        db: AsyncSession,
        profile=None,
    ) -> DetectionResult:
        """
        Main entry point. Returns DetectionResult with RiskAlert objects.
        Never raises — returns empty result on any error.
        """
        try:
            # 1. Get/create today's session
            today_ist = datetime.now(ZoneInfo("Asia/Kolkata")).date()
            session = await TradingSessionService.get_or_create_session(
                broker_account_id, today_ist, db
            )
            risk_before = session.risk_score

            # 2. Load all context in 2 queries
            ctx = await self._load_context(
                broker_account_id, completed_trade, session, db, profile
            )

            # 3. Run all 11 detectors (pure functions)
            events = self._run_all_detectors(ctx)

            # 4. Build RiskAlert objects
            now = datetime.now(timezone.utc)
            alerts = [
                RiskAlert(
                    broker_account_id=broker_account_id,
                    pattern_type=e.event_type,
                    severity=e.severity,
                    message=e.message,
                    details=e.context,
                    trigger_trade_id=None,  # CompletedTrade, not raw Trade
                )
                for e in events
            ]

            # 5. Accumulate risk score
            total_delta = sum(
                RISK_DELTAS.get(e.event_type, Decimal("0")) for e in events
            )
            new_risk = max(Decimal("0"), min(Decimal("100"), risk_before + total_delta))
            state = _behavior_state(new_risk, session.peak_risk_score)
            traj = _trajectory(risk_before, new_risk)

            # 6. Update session risk score
            if total_delta != Decimal("0"):
                await TradingSessionService.update_risk_score(session.id, total_delta, db)

            if events:
                logger.info(
                    f"[BehaviorEngine] {broker_account_id} | "
                    f"{completed_trade.tradingsymbol} | "
                    f"{len(events)} patterns | "
                    f"risk {float(risk_before):.0f}→{float(new_risk):.0f} | "
                    f"state={state} | {[e.event_type for e in events]}"
                )

            return DetectionResult(
                alerts=alerts,
                risk_score_before=risk_before,
                risk_score_after=new_risk,
                total_delta=total_delta,
                behavior_state=state,
                trajectory=traj,
                session_id=session.id,
            )

        except Exception as e:
            logger.error(f"[BehaviorEngine] analyze failed: {e}", exc_info=True)
            return DetectionResult(
                alerts=[],
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
        thresholds = get_thresholds(profile)

        session_start = session.market_open
        if session_start is None:
            from app.core.market_hours import get_session_boundaries, MarketSegment
            session_start, _ = get_session_boundaries(
                segment=MarketSegment.FNO,
                for_date=session.session_date,
            )

        # Query 1: today's completed trades
        ct_result = await db.execute(
            select(CompletedTrade)
            .where(and_(
                CompletedTrade.broker_account_id == broker_account_id,
                CompletedTrade.exit_time >= session_start,
            ))
            .order_by(CompletedTrade.exit_time.asc())
        )
        session_trades = list(ct_result.scalars().all())

        # Query 2: active cooldowns
        now_utc = datetime.now(timezone.utc)
        cd_result = await db.execute(
            select(Cooldown).where(and_(
                Cooldown.broker_account_id == broker_account_id,
                Cooldown.expires_at > now_utc,
                Cooldown.skipped == False,  # noqa: E712
            ))
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

    # ── Run all detectors ──────────────────────────────────────────────────

    def _run_all_detectors(self, ctx: EngineContext) -> List[DetectedEvent]:
        events = []
        for detector in [
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
        ]:
            try:
                event = detector(ctx)
                if event:
                    events.append(event)
            except Exception as e:
                logger.warning(f"[BehaviorEngine] {detector.__name__} failed: {e}")
        return events

    # ── Pattern 1: Consecutive loss streak ────────────────────────────────

    def _detect_consecutive_loss_streak(self, ctx: EngineContext) -> Optional[DetectedEvent]:
        trades = ctx.session_trades
        if not trades:
            return None

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
                severity="danger",
                message=f"{streak} consecutive losses — ₹{total_loss:,.0f} total. Stop and review.",
                context={"streak": streak, "total_loss": float(total_loss), "threshold": danger},
            )
        if streak >= caution:
            return DetectedEvent(
                event_type="consecutive_loss_streak",
                severity="caution",
                message=f"{streak} consecutive losses — ₹{total_loss:,.0f}. Caution.",
                context={"streak": streak, "total_loss": float(total_loss), "threshold": caution},
            )
        return None

    # ── Pattern 2: Revenge trade ──────────────────────────────────────────

    def _detect_revenge_trade(self, ctx: EngineContext) -> Optional[DetectedEvent]:
        ct = ctx.completed_trade
        trades = ctx.session_trades
        if not ct.entry_time or len(trades) < 2:
            return None

        prior = [t for t in trades if t.exit_time and t.exit_time < ct.entry_time]
        if not prior:
            return None

        last = prior[-1]
        if Decimal(str(last.realized_pnl or 0)) >= 0:
            return None

        gap_min = (ct.entry_time - last.exit_time).total_seconds() / 60
        revenge_window = ctx.thresholds.get("revenge_window_min", 10)

        if gap_min <= revenge_window:
            severity = "danger" if gap_min <= 3 else "caution"
            return DetectedEvent(
                event_type="revenge_trade",
                severity=severity,
                message=f"Entry {gap_min:.0f}min after ₹{abs(float(last.realized_pnl)):,.0f} loss. Revenge trading risk.",
                context={"gap_minutes": round(gap_min, 1), "prior_loss": float(last.realized_pnl),
                         "revenge_window_min": revenge_window},
            )
        return None

    # ── Pattern 3: Overtrading burst ──────────────────────────────────────

    def _detect_overtrading_burst(self, ctx: EngineContext) -> Optional[DetectedEvent]:
        ct = ctx.completed_trade
        if not ct.entry_time:
            return None

        cutoff = ct.entry_time - timedelta(minutes=30)
        recent = [t for t in ctx.session_trades if t.entry_time and t.entry_time >= cutoff and t.id != ct.id]
        count = len(recent) + 1

        burst_limit = ctx.thresholds.get("burst_trades_per_15min", 6) * 2  # 30-min window

        if count >= burst_limit:
            severity = "danger" if count >= burst_limit * 1.5 else "caution"
            return DetectedEvent(
                event_type="overtrading_burst",
                severity=severity,
                message=f"{count} trades in 30 minutes. Overtrading burst.",
                context={"trades_in_window": count, "window_minutes": 30, "limit": burst_limit},
            )
        return None

    # ── Pattern 4: Size escalation ────────────────────────────────────────

    def _detect_size_escalation(self, ctx: EngineContext) -> Optional[DetectedEvent]:
        trades = ctx.session_trades
        if len(trades) < 3:
            return None

        prior = sorted([t for t in trades if t.id != ctx.completed_trade.id and t.exit_time],
                       key=lambda t: t.exit_time)[-3:]
        if len(prior) < 2:
            return None

        sizes = [t.total_quantity or 1 for t in prior]
        if not (sizes[0] < sizes[1] < sizes[2]):
            return None

        pnls = [Decimal(str(t.realized_pnl or 0)) for t in prior]
        losses_before = sum(1 for p in pnls[:2] if p < 0)

        if losses_before >= 1:
            escalation_pct = (sizes[2] - sizes[0]) / max(sizes[0], 1) * 100
            if escalation_pct >= 50:
                return DetectedEvent(
                    event_type="size_escalation",
                    severity="caution",
                    message=f"Position size escalating after losses: {sizes[0]}→{sizes[1]}→{sizes[2]} units.",
                    context={"size_sequence": sizes, "escalation_pct": round(escalation_pct, 1)},
                )
        return None

    # ── Pattern 5: Rapid re-entry ─────────────────────────────────────────

    def _detect_rapid_reentry(self, ctx: EngineContext) -> Optional[DetectedEvent]:
        ct = ctx.completed_trade
        if not ct.entry_time:
            return None

        prior_same = [t for t in ctx.session_trades
                      if t.tradingsymbol == ct.tradingsymbol and t.id != ct.id and t.exit_time]
        if not prior_same:
            return None

        last_same = max(prior_same, key=lambda t: t.exit_time)
        gap_min = (ct.entry_time - last_same.exit_time).total_seconds() / 60

        if 0 <= gap_min <= 3:
            prior_pnl = Decimal(str(last_same.realized_pnl or 0))
            return DetectedEvent(
                event_type="rapid_reentry",
                severity="caution",
                message=f"Re-entered {ct.tradingsymbol} {gap_min:.0f}min after last trade.",
                context={"symbol": ct.tradingsymbol, "gap_minutes": round(gap_min, 1),
                         "prior_pnl": float(prior_pnl)},
            )
        return None

    # ── Pattern 6: Panic exit ─────────────────────────────────────────────

    def _detect_panic_exit(self, ctx: EngineContext) -> Optional[DetectedEvent]:
        ct = ctx.completed_trade
        if not ct.entry_time or not ct.exit_time:
            return None

        hold_min = (ct.exit_time - ct.entry_time).total_seconds() / 60
        pnl = Decimal(str(ct.realized_pnl or 0))

        if hold_min < 2 and pnl < 0:
            return DetectedEvent(
                event_type="panic_exit",
                severity="caution",
                message=f"Position closed after {hold_min:.0f}min with ₹{abs(pnl):,.0f} loss. Possible panic exit.",
                context={"hold_minutes": round(hold_min, 1), "realized_pnl": float(pnl)},
            )
        return None

    # ── Pattern 7: Martingale ─────────────────────────────────────────────

    def _detect_martingale_behaviour(self, ctx: EngineContext) -> Optional[DetectedEvent]:
        trades = ctx.session_trades
        if len(trades) < 3:
            return None

        prior = sorted([t for t in trades if t.id != ctx.completed_trade.id and t.exit_time],
                       key=lambda t: t.exit_time)[-3:]
        if len(prior) < 2:
            return None

        if not all(Decimal(str(t.realized_pnl or 0)) < 0 for t in prior):
            return None

        sizes = [t.total_quantity or 1 for t in prior]
        doublings = sum(1 for i in range(1, len(sizes)) if sizes[i] >= sizes[i-1] * 1.8)

        if doublings >= len(sizes) - 1:
            return DetectedEvent(
                event_type="martingale_behaviour",
                severity="danger",
                message=f"Doubling position after consecutive losses: {sizes}. Classic martingale.",
                context={"size_sequence": sizes, "consecutive_losses": len(prior)},
            )
        return None

    # ── Pattern 8: Cooldown violation ─────────────────────────────────────

    def _detect_cooldown_violation(self, ctx: EngineContext) -> Optional[DetectedEvent]:
        if not ctx.active_cooldowns:
            return None

        cooldown = ctx.active_cooldowns[0]
        remaining_min = (cooldown.expires_at - datetime.now(timezone.utc)).total_seconds() / 60

        return DetectedEvent(
            event_type="cooldown_violation",
            severity="danger",
            message=f"Trade during active cooldown ({remaining_min:.0f}min remaining). Reason: {cooldown.reason or 'loss streak'}",
            context={"remaining_minutes": round(remaining_min, 1), "cooldown_reason": cooldown.reason},
        )

    # ── Pattern 9: Rapid flip ─────────────────────────────────────────────

    def _detect_rapid_flip(self, ctx: EngineContext) -> Optional[DetectedEvent]:
        ct = ctx.completed_trade
        if not ct.entry_time or not ct.direction:
            return None

        prior_same = sorted(
            [t for t in ctx.session_trades
             if t.tradingsymbol == ct.tradingsymbol and t.id != ct.id and t.exit_time and t.direction],
            key=lambda t: t.exit_time
        )
        if not prior_same:
            return None

        last = prior_same[-1]
        if last.direction == ct.direction:
            return None

        gap_min = (ct.entry_time - last.exit_time).total_seconds() / 60
        if gap_min < 5:
            return DetectedEvent(
                event_type="rapid_flip",
                severity="caution",
                message=f"{ct.tradingsymbol}: reversed {last.direction}→{ct.direction} within {gap_min:.0f}min.",
                context={"symbol": ct.tradingsymbol, "from_direction": last.direction,
                         "to_direction": ct.direction, "gap_minutes": round(gap_min, 1)},
            )
        return None

    # ── Pattern 10: Excess exposure ───────────────────────────────────────

    def _detect_excess_exposure(self, ctx: EngineContext) -> Optional[DetectedEvent]:
        ct = ctx.completed_trade
        capital = ctx.thresholds.get("trading_capital")
        # Guard: skip if capital is clearly wrong/unconfigured
        if not capital or float(capital) < 10000:
            return None

        capital_at_risk = estimate_capital_at_risk(
            instrument_type=ct.instrument_type,
            tradingsymbol=ct.tradingsymbol or "",
            direction=ct.direction or "LONG",
            avg_entry_price=float(ct.avg_entry_price or 0),
            total_quantity=ct.total_quantity or 0,
        )
        risk_pct = capital_at_risk / capital * 100
        limit_pct = ctx.thresholds.get("max_position_size") or 10.0

        if risk_pct > limit_pct * 1.5:
            severity = "danger" if risk_pct > limit_pct * 2 else "caution"
            return DetectedEvent(
                event_type="excess_exposure",
                severity=severity,
                message=f"{ct.tradingsymbol}: ₹{capital_at_risk:,.0f} at risk ({risk_pct:.1f}% of capital). Limit is {limit_pct:.0f}%.",
                context={"capital_at_risk": round(capital_at_risk), "risk_pct": round(risk_pct, 1),
                         "limit_pct": limit_pct},
            )
        return None

    # ── Pattern 11: Session meltdown ──────────────────────────────────────

    def _detect_session_meltdown(self, ctx: EngineContext) -> Optional[DetectedEvent]:
        session_pnl = Decimal(str(ctx.session.session_pnl or 0))
        daily_loss_limit = ctx.thresholds.get("daily_loss_limit")

        if not daily_loss_limit or daily_loss_limit <= 0:
            capital = ctx.thresholds.get("trading_capital")
            # Guard: trading_capital must be >= ₹10,000 to be sensible for F&O trading.
            # Values below this indicate a misconfigured profile (e.g. ₹0.30 from test data).
            if capital and float(capital) >= 10000:
                daily_loss_limit = float(capital) * 0.05
            else:
                return None

        limit = Decimal(str(daily_loss_limit))
        if session_pnl < -(limit * Decimal("0.8")):
            pct_used = abs(session_pnl) / limit * 100
            severity = "danger" if pct_used >= 100 else "caution"
            return DetectedEvent(
                event_type="session_meltdown",
                severity=severity,
                message=f"Session P&L: ₹{session_pnl:,.0f}. Used {pct_used:.0f}% of daily loss limit.",
                context={"session_pnl": float(session_pnl), "daily_loss_limit": float(limit),
                         "pct_used": round(float(pct_used), 1)},
            )
        return None


# Singleton
behavior_engine = BehaviorEngine()
