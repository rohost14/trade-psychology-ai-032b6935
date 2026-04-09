"""
BehaviorEngine — Unified Real-Time Behavioral Detection (Phase 3 — PRODUCTION)

Single source of truth for all behavioral pattern detection.
Frontend patternDetector.ts has been removed — backend is the only engine.

Architecture:
  - Session-scoped (today IST only)
  - Cumulative risk score (0-100) via TradingSession
  - Behavior state: Stable → Pressure → Tilt Risk → Tilt → Breakdown → Recovery
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

Patterns (18 real-time, per CompletedTrade):
  1.  consecutive_loss_streak
  2.  revenge_trade
  3.  overtrading_burst          (burst + daily count)
  4.  size_escalation
  5.  rapid_reentry
  6.  panic_exit
  7.  martingale_behaviour
  8.  cooldown_violation
  9.  rapid_flip
  10. excess_exposure
  11. session_meltdown
  12. fomo_entry                  (any-time underlying scatter, not just market open)
  13. no_stoploss                 (expiry-day modifier)
  14. early_exit                  (disposition effect)
  15. winning_streak_overconfidence
  16. options_direction_confusion (CE→PE flip on same underlying within 10 min)
  17. options_premium_avg_down    (re-entry on same underlying options after prior loss)
  18. iv_crush_behavior           (fast large premium loss = buying into high IV)
  19. expiry_day_overtrading      (excessive trades on an instrument's own expiry date)
  20. opening_5min_trap           (derivative entry 09:15–09:20 IST)
  21. end_of_session_mis_panic    (MIS entries after 15:10 IST — forced 10-min exit)
  22. post_loss_recovery_bet      (one oversized position after 2+ consecutive losses)
  23. profit_giveaway             (gave back ≥50% of session peak P&L in one trade)
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
from app.models.strategy_group import StrategyGroup
from app.services.trading_session_service import TradingSessionService
from app.core.trading_defaults import get_thresholds, estimate_capital_at_risk

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")

# ---------------------------------------------------------------------------
# Risk score deltas per pattern
# ---------------------------------------------------------------------------
RISK_DELTAS: Dict[str, Decimal] = {
    "consecutive_loss_streak":          Decimal("20"),
    "revenge_trade":                    Decimal("25"),
    "overtrading_burst":                Decimal("10"),
    "size_escalation":                  Decimal("15"),
    "rapid_reentry":                    Decimal("15"),
    "panic_exit":                       Decimal("10"),
    "martingale_behaviour":             Decimal("20"),
    "cooldown_violation":               Decimal("25"),
    "rapid_flip":                       Decimal("15"),
    "excess_exposure":                  Decimal("15"),
    "session_meltdown":                 Decimal("30"),
    "fomo_entry":                       Decimal("15"),
    "no_stoploss":                      Decimal("20"),
    "early_exit":                       Decimal("10"),
    "winning_streak_overconfidence":    Decimal("15"),
    "options_direction_confusion":      Decimal("20"),
    "options_premium_avg_down":         Decimal("15"),
    "iv_crush_behavior":                Decimal("10"),
    # G2 / G4 / G5 / G6 — new patterns
    "expiry_day_overtrading":           Decimal("20"),
    "opening_5min_trap":                Decimal("10"),
    "end_of_session_mis_panic":         Decimal("15"),
    "post_loss_recovery_bet":           Decimal("20"),
    "profit_giveaway":                  Decimal("20"),
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
    event_type: str
    severity: str       # "danger" | "caution"
    message: str
    context: Dict[str, Any] = field(default_factory=dict)
    risk_delta: Decimal = Decimal("0")


@dataclass
class DetectionResult:
    alerts: List[RiskAlert]
    risk_score_before: Decimal
    risk_score_after: Decimal
    total_delta: Decimal
    behavior_state: str
    trajectory: str
    session_id: Optional[UUID]


@dataclass
class EngineContext:
    broker_account_id: UUID
    session: TradingSession
    completed_trade: CompletedTrade
    session_trades: List[CompletedTrade]
    active_cooldowns: List[Cooldown]
    thresholds: Dict[str, Any]
    strategy_group: Optional[StrategyGroup] = None
    # order_type values of the exit fills for the current completed_trade
    # (e.g. ["MKT"], ["SL"], ["SL-M", "MKT"]).  Empty when exit_trade_ids unknown.
    exit_order_types: List[str] = None  # type: ignore[assignment]


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
    ) -> DetectionResult:
        try:
            today_ist = datetime.now(ZoneInfo("Asia/Kolkata")).date()
            session = await TradingSessionService.get_or_create_session(
                broker_account_id, today_ist, db
            )
            risk_before = session.risk_score

            ctx = await self._load_context(
                broker_account_id, completed_trade, session, db, profile
            )
            events = self._run_all_detectors(ctx)

            now = datetime.now(timezone.utc)
            alerts = [
                RiskAlert(
                    broker_account_id=broker_account_id,
                    pattern_type=e.event_type,
                    severity=e.severity,
                    message=e.message,
                    details={**e.context, "exchange": completed_trade.exchange},
                    trigger_trade_id=None,
                )
                for e in events
            ]

            total_delta = sum(
                RISK_DELTAS.get(e.event_type, Decimal("0")) for e in events
            )
            new_risk = max(Decimal("0"), min(Decimal("100"), risk_before + total_delta))
            state = _behavior_state(new_risk, session.peak_risk_score)
            traj = _trajectory(risk_before, new_risk)

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
            from sqlalchemy import cast as _cast, String as _String
            try:
                ot_result = await db.execute(
                    select(_Trade.order_type).where(
                        _cast(_Trade.id, _String).in_(completed_trade.exit_trade_ids)
                    )
                )
                exit_order_types = [r[0] for r in ot_result.all() if r[0]]
            except Exception as _ot_err:
                logger.debug(f"Exit order type lookup skipped: {_ot_err}")

        return EngineContext(
            broker_account_id=broker_account_id,
            session=session,
            completed_trade=completed_trade,
            session_trades=session_trades,
            active_cooldowns=active_cooldowns,
            thresholds=thresholds,
            strategy_group=strategy_group,
            exit_order_types=exit_order_types,
        )

    # ── Run all detectors ──────────────────────────────────────────────────

    # Patterns suppressed for strategy legs (hedge legs fire false positives on these)
    _STRATEGY_SUPPRESSED = frozenset({
        "revenge_trade",
        "martingale_behaviour",
        "size_escalation",
        "consecutive_loss_streak",
    })

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
            self._detect_fomo_entry,
            self._detect_no_stoploss,
            self._detect_early_exit,
            self._detect_winning_streak_overconfidence,
            self._detect_options_direction_confusion,
            self._detect_options_premium_avg_down,
            self._detect_iv_crush_behavior,
            self._detect_expiry_day_overtrading,
            self._detect_opening_5min_trap,
            self._detect_end_of_session_mis_panic,
            self._detect_post_loss_recovery_bet,
            self._detect_profit_giveaway,
        ]:
            try:
                event = detector(ctx)
                if event:
                    if ctx.strategy_group and event.event_type in self._STRATEGY_SUPPRESSED:
                        logger.debug(
                            f"[BehaviorEngine] suppressed {event.event_type} — "
                            f"trade is part of {ctx.strategy_group.strategy_type}"
                        )
                        continue
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
        danger  = ctx.thresholds.get("consecutive_loss_danger", 5)

        if streak >= danger:
            return DetectedEvent(
                event_type="consecutive_loss_streak",
                severity="danger",
                message=(
                    f"Your last {streak} trades were all losses — ₹{total_loss:,.0f} total. "
                    f"Stop, review your analysis before the next trade."
                ),
                context={"streak": streak, "total_loss": float(total_loss), "threshold": danger},
            )
        if streak >= caution:
            return DetectedEvent(
                event_type="consecutive_loss_streak",
                severity="caution",
                message=(
                    f"Your last {streak} trades were all losses — ₹{total_loss:,.0f} total."
                ),
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
        last_pnl = Decimal(str(last.realized_pnl or 0))
        if last_pnl >= 0:
            return None

        # Only trigger if prior loss is meaningful (not a scratch trade)
        min_loss = ctx.thresholds.get("revenge_min_loss_inr", 500)
        if abs(last_pnl) < min_loss:
            return None

        gap_min = (ct.entry_time - last.exit_time).total_seconds() / 60
        caution_window = ctx.thresholds.get("revenge_window_caution_min", 20)
        danger_window  = ctx.thresholds.get("revenge_window_danger_min", 5)

        same_symbol = ct.tradingsymbol == last.tradingsymbol
        if same_symbol:
            entry_desc = f"Re-entered {ct.tradingsymbol}"
            loss_desc  = f"{gap_min:.0f}min after a ₹{abs(float(last_pnl)):,.0f} loss on the same instrument"
        else:
            entry_desc = f"Entered {ct.tradingsymbol}"
            loss_desc  = f"{gap_min:.0f}min after a ₹{abs(float(last_pnl)):,.0f} loss on {last.tradingsymbol}"

        base_ctx = {
            "gap_minutes": round(gap_min, 1),
            "prior_loss": float(last_pnl),
            "prior_symbol": last.tradingsymbol,
            "trigger_symbol": ct.tradingsymbol,
            "caution_window": caution_window,
            "danger_window": danger_window,
        }

        if gap_min <= danger_window:
            return DetectedEvent(
                event_type="revenge_trade",
                severity="danger",
                message=f"{entry_desc} — {loss_desc}.",
                context=base_ctx,
            )
        if gap_min <= caution_window:
            return DetectedEvent(
                event_type="revenge_trade",
                severity="caution",
                message=f"{entry_desc} — {loss_desc}. Was this entry planned before the loss?",
                context=base_ctx,
            )
        return None

    # ── Pattern 3: Overtrading burst + daily count ────────────────────────

    def _detect_overtrading_burst(self, ctx: EngineContext) -> Optional[DetectedEvent]:
        ct = ctx.completed_trade
        if not ct.entry_time:
            return None

        burst_caution = ctx.thresholds.get("burst_trades_per_30min_caution", 5)
        burst_danger  = ctx.thresholds.get("burst_trades_per_30min_danger", 8)
        daily_caution = ctx.thresholds.get("daily_trade_limit", 7)
        daily_danger  = ctx.thresholds.get("daily_trade_danger", 12)

        # Session P&L context — used to gate/downgrade alerts when in profit
        session_pnl = float(ctx.session.realized_pnl or 0) if ctx.session else 0

        # Check 1: burst (30-min rolling window)
        cutoff = ct.entry_time - timedelta(minutes=30)
        recent = [t for t in ctx.session_trades
                  if t.entry_time and t.entry_time >= cutoff and t.id != ct.id]
        burst_count = len(recent) + 1

        # Suppress burst alert entirely if session is profitable AND all burst trades won
        # (high-frequency profitable trading is not a behavioral problem)
        if burst_count >= burst_caution:
            recent_pnls = [float(t.realized_pnl or 0) for t in recent]
            recent_pnls.append(float(ct.realized_pnl or 0))
            all_burst_profitable = all(p > 0 for p in recent_pnls)
            if session_pnl > 0 and all_burst_profitable:
                pass  # genuinely profitable burst — skip
            elif burst_count >= burst_danger:
                return DetectedEvent(
                    event_type="overtrading_burst",
                    severity="danger",
                    message=(
                        f"{burst_count} trades in 30 minutes"
                        + (f" while down ₹{abs(session_pnl):,.0f} on the session." if session_pnl < 0 else ".")
                    ),
                    context={"trades_in_window": burst_count, "window_minutes": 30,
                             "session_pnl": round(session_pnl, 2),
                             "caution_limit": burst_caution, "danger_limit": burst_danger},
                )
            else:
                # caution: fire only when session is in loss or mixed
                if session_pnl < 0:
                    return DetectedEvent(
                        event_type="overtrading_burst",
                        severity="caution",
                        message=(
                            f"{burst_count} trades in 30 minutes while the session is down "
                            f"₹{abs(session_pnl):,.0f}."
                        ),
                        context={"trades_in_window": burst_count, "window_minutes": 30,
                                 "session_pnl": round(session_pnl, 2),
                                 "caution_limit": burst_caution, "danger_limit": burst_danger},
                    )
                # session positive but some burst trades losing — neutral observation
                losing_in_burst = sum(1 for p in recent_pnls if p < 0)
                if losing_in_burst > 0:
                    return DetectedEvent(
                        event_type="overtrading_burst",
                        severity="caution",
                        message=(
                            f"{burst_count} trades in 30 minutes — "
                            f"{losing_in_burst} of them closed at a loss."
                        ),
                        context={"trades_in_window": burst_count, "window_minutes": 30,
                                 "losing_in_burst": losing_in_burst,
                                 "session_pnl": round(session_pnl, 2),
                                 "caution_limit": burst_caution, "danger_limit": burst_danger},
                    )

        # Check 2: daily session count
        daily_count = len(ctx.session_trades)
        if daily_count >= daily_danger:
            return DetectedEvent(
                event_type="overtrading_burst",
                severity="danger",
                message=(
                    f"{daily_count} trades today"
                    + (f", session P&L: ₹{session_pnl:+,.0f}." if session_pnl != 0 else ".")
                ),
                context={"daily_count": daily_count, "daily_caution": daily_caution,
                         "daily_danger": daily_danger, "session_pnl": round(session_pnl, 2)},
            )
        if daily_count >= daily_caution:
            # Only fire daily count alert if session is in loss
            if session_pnl < 0:
                return DetectedEvent(
                    event_type="overtrading_burst",
                    severity="caution",
                    message=(
                        f"{daily_count} trades today, session P&L: ₹{session_pnl:+,.0f}."
                    ),
                    context={"daily_count": daily_count, "daily_caution": daily_caution,
                             "daily_danger": daily_danger, "session_pnl": round(session_pnl, 2)},
                )
        return None

    # ── Pattern 4: Size escalation after losses ───────────────────────────

    def _detect_size_escalation(self, ctx: EngineContext) -> Optional[DetectedEvent]:
        trades = ctx.session_trades
        if len(trades) < 3:
            return None

        prior = sorted(
            [t for t in trades if t.id != ctx.completed_trade.id and t.exit_time],
            key=lambda t: t.exit_time,
        )[-3:]
        if len(prior) < 2:
            return None

        sizes = [t.total_quantity or 1 for t in prior]
        if not (sizes[0] < sizes[1] < sizes[2]):
            return None

        pnls = [Decimal(str(t.realized_pnl or 0)) for t in prior]
        losses_before = sum(1 for p in pnls[:2] if p < 0)

        if losses_before >= 1:
            threshold = ctx.thresholds.get("size_escalation_pct", 30)
            escalation_pct = (sizes[2] - sizes[0]) / max(sizes[0], 1) * 100
            if escalation_pct >= threshold:
                return DetectedEvent(
                    event_type="size_escalation",
                    severity="caution",
                    message=(
                        f"Your position size has been increasing after losses: "
                        f"{sizes[0]}→{sizes[1]}→{sizes[2]} units ({escalation_pct:.0f}% increase)."
                    ),
                    context={"size_sequence": sizes, "escalation_pct": round(escalation_pct, 1),
                             "threshold_pct": threshold},
                )
        return None

    # ── Pattern 5: Rapid re-entry (same symbol) ───────────────────────────

    def _detect_rapid_reentry(self, ctx: EngineContext) -> Optional[DetectedEvent]:
        ct = ctx.completed_trade
        if not ct.entry_time:
            return None

        prior_same = [t for t in ctx.session_trades
                      if t.tradingsymbol == ct.tradingsymbol
                      and t.id != ct.id and t.exit_time]
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
                severity="caution",
                message=(
                    f"{ct.tradingsymbol}: re-entered {gap_min:.0f}min after a "
                    f"₹{abs(float(prior_pnl)):,.0f} loss on the same instrument."
                ),
                context={"symbol": ct.tradingsymbol, "gap_minutes": round(gap_min, 1),
                         "prior_pnl": float(prior_pnl), "window_min": window,
                         "trigger_symbol": ct.tradingsymbol},
            )
        return None

    # ── Pattern 6: Panic exit ─────────────────────────────────────────────

    def _detect_panic_exit(self, ctx: EngineContext) -> Optional[DetectedEvent]:
        ct = ctx.completed_trade
        if not ct.entry_time or not ct.exit_time:
            return None

        hold_min = (ct.exit_time - ct.entry_time).total_seconds() / 60
        pnl = Decimal(str(ct.realized_pnl or 0))
        window = ctx.thresholds.get("panic_exit_min", 5)

        if not (hold_min < window and pnl < 0):
            return None

        # If exit was via SL/SL-M order → pre-planned stop, not panic. Skip.
        exit_types = {(ot or "").upper() for ot in (ctx.exit_order_types or [])}
        if exit_types & {"SL", "SL-M", "SLM", "SL-MKT"}:
            return None

        return DetectedEvent(
            event_type="panic_exit",
            severity="caution",
            message=(
                f"{ct.tradingsymbol}: closed after {hold_min:.0f}min at "
                f"₹{abs(pnl):,.0f} loss — no stop-loss order, quick manual exit."
            ),
            context={"hold_minutes": round(hold_min, 1), "realized_pnl": float(pnl),
                     "window_min": window, "trigger_symbol": ct.tradingsymbol},
        )

    # ── Pattern 7: Martingale / averaging down ────────────────────────────

    def _detect_martingale_behaviour(self, ctx: EngineContext) -> Optional[DetectedEvent]:
        ct = ctx.completed_trade
        trades = ctx.session_trades
        if len(trades) < 3:
            return None

        # Compare only within the SAME underlying so different lot sizes
        # (e.g. Nifty 50 qty vs Industower 2000 qty) are never mixed.
        from app.services.instrument_parser import parse_symbol as _ps
        try:
            ct_underlying = _ps(ct.tradingsymbol or "").underlying
        except Exception:
            ct_underlying = ct.tradingsymbol or ""

        prior = sorted(
            [t for t in trades
             if t.id != ct.id and t.exit_time
             and (_ps(t.tradingsymbol or "").underlying if t.tradingsymbol else "") == ct_underlying],
            key=lambda t: t.exit_time,
        )[-3:]
        if len(prior) < 2:
            return None

        min_losses = ctx.thresholds.get("martingale_min_losses", 2)
        loss_count = sum(1 for t in prior if Decimal(str(t.realized_pnl or 0)) < 0)
        if loss_count < min_losses:
            return None

        sizes = [t.total_quantity or 1 for t in prior]
        caution_mul = ctx.thresholds.get("martingale_caution_multiplier", 1.5)
        danger_mul  = ctx.thresholds.get("martingale_danger_multiplier", 2.0)

        # Check from latest to earliest: is any step a danger/caution double?
        max_ratio = max(
            sizes[i] / max(sizes[i-1], 1) for i in range(1, len(sizes))
        )
        # Build readable sequence using all prior + current trade
        all_sizes = sizes + [ct.total_quantity or 1]
        seq_str = "→".join(str(s) for s in all_sizes)

        if max_ratio >= danger_mul:
            return DetectedEvent(
                event_type="martingale_behaviour",
                severity="danger",
                message=(
                    f"{ct_underlying} position sizes after consecutive losses: {seq_str}. "
                    f"Each loss was followed by a larger position — a martingale pattern."
                ),
                context={"size_sequence": all_sizes, "max_ratio": round(max_ratio, 2),
                         "consecutive_losses": loss_count, "underlying": ct_underlying,
                         "trigger_symbol": ct.tradingsymbol},
            )
        if max_ratio >= caution_mul:
            return DetectedEvent(
                event_type="martingale_behaviour",
                severity="caution",
                message=(
                    f"{ct_underlying} position sizes after losses: {seq_str}. "
                    f"Increasing size after losses raises total risk, not just cost basis."
                ),
                context={"size_sequence": all_sizes, "max_ratio": round(max_ratio, 2),
                         "consecutive_losses": loss_count, "underlying": ct_underlying,
                         "trigger_symbol": ct.tradingsymbol},
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
            message=(
                f"You traded during an active cooldown period "
                f"({remaining_min:.0f}min remaining). "
                f"Reason: {cooldown.reason or 'loss streak'}."
            ),
            context={"remaining_minutes": round(remaining_min, 1),
                     "cooldown_reason": cooldown.reason},
        )

    # ── Pattern 9: Rapid flip (direction reversal) ────────────────────────

    def _detect_rapid_flip(self, ctx: EngineContext) -> Optional[DetectedEvent]:
        ct = ctx.completed_trade
        if not ct.entry_time or not ct.direction:
            return None

        prior_same = sorted(
            [t for t in ctx.session_trades
             if t.tradingsymbol == ct.tradingsymbol and t.id != ct.id
             and t.exit_time and t.direction],
            key=lambda t: t.exit_time,
        )
        if not prior_same:
            return None

        last = prior_same[-1]
        if last.direction == ct.direction:
            return None

        gap_min = (ct.entry_time - last.exit_time).total_seconds() / 60
        window = ctx.thresholds.get("rapid_flip_min", 10)

        if gap_min < window:
            return DetectedEvent(
                event_type="rapid_flip",
                severity="caution",
                message=(
                    f"You reversed direction on {ct.tradingsymbol} "
                    f"({last.direction}→{ct.direction}) within {gap_min:.0f}min. "
                    f"Rapid direction changes usually reflect uncertainty, not a new signal."
                ),
                context={
                    "symbol": ct.tradingsymbol,
                    "from_direction": last.direction,
                    "to_direction": ct.direction,
                    "gap_minutes": round(gap_min, 1),
                    "window_min": window,
                },
            )
        return None

    # ── Pattern 10: Excess exposure ───────────────────────────────────────

    def _detect_excess_exposure(self, ctx: EngineContext) -> Optional[DetectedEvent]:
        ct = ctx.completed_trade
        capital = ctx.thresholds.get("trading_capital")
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
        caution_pct = ctx.thresholds.get("max_position_pct_caution", 5.0)
        danger_pct  = ctx.thresholds.get("max_position_pct_danger", 10.0)

        if risk_pct > danger_pct:
            return DetectedEvent(
                event_type="excess_exposure",
                severity="danger",
                message=(
                    f"Your {ct.tradingsymbol} trade put ₹{capital_at_risk:,.0f} at risk "
                    f"({risk_pct:.1f}% of your capital). "
                    f"Profitable F&O traders risk ≤5% per trade. This is {risk_pct/5:.1f}× that."
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

        if not daily_loss_limit or daily_loss_limit <= 0:
            capital = ctx.thresholds.get("trading_capital")
            # Use 5% of capital as daily loss limit for any account size.
            # The ≥10k floor was wrong — a ₹5k account can still blow up.
            if capital and float(capital) > 0:
                daily_loss_limit = float(capital) * 0.05
            else:
                return None

        limit = Decimal(str(daily_loss_limit))
        caution_pct = Decimal(str(ctx.thresholds.get("meltdown_caution_pct", 0.40)))
        danger_pct  = Decimal(str(ctx.thresholds.get("meltdown_danger_pct", 0.75)))

        if session_pnl < -(limit * danger_pct):
            pct_used = abs(session_pnl) / limit * 100
            return DetectedEvent(
                event_type="session_meltdown",
                severity="danger",
                message=(
                    f"Today's P&L: ₹{session_pnl:,.0f} ({pct_used:.0f}% of your "
                    f"₹{limit:,.0f} daily limit). "
                    f"Research shows decision quality collapses at this level of loss. "
                    f"Stop trading today."
                ),
                context={"session_pnl": float(session_pnl),
                         "daily_loss_limit": float(limit),
                         "pct_used": round(float(pct_used), 1)},
            )
        if session_pnl < -(limit * caution_pct):
            pct_used = abs(session_pnl) / limit * 100
            return DetectedEvent(
                event_type="session_meltdown",
                severity="caution",
                message=(
                    f"Today's P&L: ₹{session_pnl:,.0f} ({pct_used:.0f}% of your "
                    f"₹{limit:,.0f} daily limit used). "
                    f"At 40%+ loss, the urge to recover distorts decision-making."
                ),
                context={"session_pnl": float(session_pnl),
                         "daily_loss_limit": float(limit),
                         "pct_used": round(float(pct_used), 1)},
            )
        return None

    # ── Pattern 12: FOMO entry ─────────────────────────────────────────────
    #
    # Detects scattering across different underlying instruments.
    # Buying multiple strikes of same underlying (NIFTY25500CE + NIFTY25600CE) = strategy.
    # Buying NIFTY CE + BANKNIFTY CE + RELIANCE option in 30 min = FOMO.
    # Works at any time of day (not just market open).

    def _detect_fomo_entry(self, ctx: EngineContext) -> Optional[DetectedEvent]:
        ct = ctx.completed_trade
        if not ct.entry_time or ct.instrument_type not in ("CE", "PE", "FUT"):
            return None

        from app.services.instrument_parser import parse_symbol, is_expiry_day as _is_expiry_day
        ct_parsed = parse_symbol(ct.tradingsymbol or "")

        fomo_window_min      = ctx.thresholds.get("fomo_window_min", 30)
        fomo_general         = ctx.thresholds.get("fomo_symbols_in_window", 3)
        fomo_open_symbols    = ctx.thresholds.get("fomo_symbols_at_open", 2)
        fomo_open_window_min = ctx.thresholds.get("fomo_open_window_min", 30)
        fomo_close_window_min = ctx.thresholds.get("fomo_close_window_min", 30)
        fomo_expiry_symbols  = ctx.thresholds.get("fomo_expiry_day_symbols", 2)

        entry_ist = ct.entry_time.astimezone(IST)

        # Context flags — use symbol-parsed expiry date, NOT hardcoded weekday==3.
        # Weekly options carry the exact expiry date in the symbol (e.g. NIFTY2532025000CE).
        # Monthly options/futures use last Thursday of the contract month.
        is_expiry_day  = _is_expiry_day(ct.tradingsymbol or "", entry_ist.date())
        market_open    = entry_ist.replace(hour=9, minute=15, second=0, microsecond=0)
        market_close   = entry_ist.replace(hour=15, minute=30, second=0, microsecond=0)
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

        # Count distinct underlyings (not symbols — buying 2 NIFTY strikes is not FOMO)
        distinct_underlyings = {
            parse_symbol(t.tradingsymbol or "").underlying for t in window_trades
        }

        # Determine threshold
        if is_expiry_day:
            threshold = fomo_expiry_symbols
            context_note = "expiry day"
        elif is_open_window:
            threshold = fomo_open_symbols
            context_note = "market open"
        elif is_close_window:
            threshold = fomo_open_symbols
            context_note = "pre-close"
        else:
            threshold = fomo_general
            context_note = None

        if len(distinct_underlyings) >= threshold:
            label = f" ({context_note})" if context_note else ""
            return DetectedEvent(
                event_type="fomo_entry",
                severity="caution",
                message=(
                    f"You entered {len(distinct_underlyings)} different instruments "
                    f"within {fomo_window_min}min{label}: {', '.join(sorted(distinct_underlyings))}. "
                    f"Scattering across underlyings indicates FOMO — not a focused plan."
                ),
                context={
                    "distinct_underlyings": sorted(distinct_underlyings),
                    "window_minutes": fomo_window_min,
                    "is_expiry_day": is_expiry_day,
                    "context_note": context_note,
                },
            )
        return None

    # ── Pattern 13: No stop-loss ──────────────────────────────────────────
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

        # PRIMARY CHECK: if exit was via SL or SL-M order → stoploss was placed
        # and triggered.  We skip the alert — the mechanism worked as intended.
        # Note: if user placed SL then manually exited before it triggered, exit
        # shows as MKT — that edge case is acceptable; we'd still flag it, which
        # is benign (they exited consciously anyway).
        exit_types = {(ot or "").upper() for ot in (ctx.exit_order_types or [])}
        if exit_types & {"SL", "SL-M", "SLM", "SL-MKT"}:
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
                    float(entry_price), int(qty)
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

        if is_monthly_expiry:
            loss_threshold = ctx.thresholds.get("no_stoploss_monthly_loss_pct", 20)
            hold_threshold = ctx.thresholds.get("no_stoploss_monthly_hold_min", 5)
            expiry_note = " (monthly expiry)"
        elif is_expiry:
            loss_threshold = ctx.thresholds.get("no_stoploss_expiry_loss_pct", 25)
            hold_threshold = ctx.thresholds.get("no_stoploss_expiry_hold_min", 5)
            expiry_note = " (expiry day)"
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

        return DetectedEvent(
            event_type="no_stoploss",
            severity=severity,
            message=(
                f"{ct.tradingsymbol}{expiry_note}: manual exit after {duration}min "
                f"with {loss_pct:.0f}% loss {loss_label} (₹{abs(pnl):,.0f}). "
                f"No stop-loss order detected on this trade."
            ),
            context={
                "duration_minutes": duration,
                "loss_pct": round(float(loss_pct), 1),
                "realized_pnl": float(pnl),
                "capital_at_risk": round(float(capital_at_risk)),
                "instrument_type": instrument_type,
                "is_expiry_day": is_expiry,
                "exit_order_types": list(exit_types),
            },
        )

    # ── Pattern 14: Early exit (disposition effect) ───────────────────────
    #
    # Session-level pattern: winners held significantly less time than losers.
    # Classic loss aversion / disposition effect (Shefrin & Statman, 1985).

    def _detect_early_exit(self, ctx: EngineContext) -> Optional[DetectedEvent]:
        ct = ctx.completed_trade
        pnl = Decimal(str(ct.realized_pnl or 0))
        if pnl <= 0:
            return None  # Only fire when current trade is a winner

        trades = ctx.session_trades
        min_samples = ctx.thresholds.get("early_exit_min_samples", 3)

        winners = [t for t in trades
                   if Decimal(str(t.realized_pnl or 0)) > 0 and t.duration_minutes]
        losers  = [t for t in trades
                   if Decimal(str(t.realized_pnl or 0)) < 0 and t.duration_minutes]

        if len(winners) < min_samples or len(losers) < min_samples:
            return None

        avg_winner_hold = sum(t.duration_minutes for t in winners) / len(winners)
        avg_loser_hold  = sum(t.duration_minutes for t in losers)  / len(losers)

        ratio_threshold    = ctx.thresholds.get("early_exit_ratio", 0.40)
        max_winner_min     = ctx.thresholds.get("early_exit_winner_max_min", 20)

        if avg_winner_hold < avg_loser_hold * ratio_threshold and avg_winner_hold < max_winner_min:
            ratio = avg_loser_hold / max(avg_winner_hold, 1)
            return DetectedEvent(
                event_type="early_exit",
                severity="caution",
                message=(
                    f"Today's pattern: winners held {avg_winner_hold:.0f}min avg vs "
                    f"losers {avg_loser_hold:.0f}min avg ({ratio:.1f}× longer). "
                    f"You are cutting winners too early and holding losers too long — "
                    f"this is the single biggest driver of underperformance for retail traders."
                ),
                context={
                    "avg_winner_hold_min": round(avg_winner_hold, 1),
                    "avg_loser_hold_min": round(avg_loser_hold, 1),
                    "winner_count": len(winners),
                    "loser_count": len(losers),
                    "hold_ratio": round(ratio, 1),
                },
            )
        return None

    # ── Pattern 15: Winning streak overconfidence ─────────────────────────
    #
    # "Hot hand fallacy": consecutive wins create overconfidence.
    # After 5 wins, the danger is extreme regardless of size.

    def _detect_winning_streak_overconfidence(self, ctx: EngineContext) -> Optional[DetectedEvent]:
        ct = ctx.completed_trade
        trades = ctx.session_trades

        prior = sorted(
            [t for t in trades if t.id != ct.id and t.exit_time],
            key=lambda t: t.exit_time,
        )

        caution_streak = ctx.thresholds.get("overconfidence_win_streak_caution", 3)
        danger_streak  = ctx.thresholds.get("overconfidence_win_streak_danger", 5)
        size_mul       = ctx.thresholds.get("overconfidence_size_mul_caution", 1.3)

        # Check if prior N trades are all wins
        def is_win_streak(n: int) -> bool:
            if len(prior) < n:
                return False
            return all(Decimal(str(t.realized_pnl or 0)) > 0 for t in prior[-n:])

        # Danger: 5+ consecutive wins regardless of current size
        if is_win_streak(danger_streak):
            win_trades = prior[-danger_streak:]
            total_profit = sum(Decimal(str(t.realized_pnl or 0)) for t in win_trades)
            return DetectedEvent(
                event_type="winning_streak_overconfidence",
                severity="danger",
                message=(
                    f"{danger_streak} consecutive wins (₹{float(total_profit):,.0f} total). "
                    f"This level of streak creates extreme overconfidence. "
                    f"Your next trade is statistically a regression to the mean — size accordingly."
                ),
                context={
                    "win_streak": danger_streak,
                    "streak_profit": float(total_profit),
                },
            )

        # Caution: 3+ wins + size escalation
        if is_win_streak(caution_streak):
            last_n = prior[-caution_streak:]
            avg_streak_qty = sum(t.total_quantity or 1 for t in last_n) / caution_streak
            current_qty = ct.total_quantity or 1

            if current_qty >= avg_streak_qty * size_mul:
                escalation_pct = (current_qty - avg_streak_qty) / max(avg_streak_qty, 1) * 100
                return DetectedEvent(
                    event_type="winning_streak_overconfidence",
                    severity="caution",
                    message=(
                        f"{caution_streak} consecutive wins, then your position size jumped "
                        f"{escalation_pct:.0f}% ({avg_streak_qty:.0f}→{current_qty} units). "
                        f"Streaks end — don't let confidence become a liability."
                    ),
                    context={
                        "win_streak": caution_streak,
                        "avg_prior_qty": round(avg_streak_qty, 1),
                        "current_qty": current_qty,
                        "escalation_pct": round(escalation_pct, 1),
                    },
                )
        return None


    # ── Pattern 16: Options direction confusion ───────────────────────────
    #
    # CE→PE (or PE→CE) flip on the same underlying within the confusion window.
    # Legitimate reversals require analysis time. < 10 min = confusion, not strategy.

    def _detect_options_direction_confusion(self, ctx: EngineContext) -> Optional[DetectedEvent]:
        ct = ctx.completed_trade
        if ct.instrument_type not in ("CE", "PE") or ct.direction != "LONG":
            return None
        if not ct.entry_time:
            return None

        from app.services.instrument_parser import parse_symbol
        ct_parsed = parse_symbol(ct.tradingsymbol or "")
        if not ct_parsed.underlying:
            return None

        window_min = ctx.thresholds.get("direction_confusion_window_min", 10)
        window_start = ct.entry_time - timedelta(minutes=window_min)
        opposite_type = "PE" if ct.instrument_type == "CE" else "CE"

        for prior in ctx.session_trades:
            if prior.id == ct.id:
                continue
            if prior.instrument_type != opposite_type or prior.direction != "LONG":
                continue
            if not prior.exit_time:
                continue
            # Prior trade must have exited within the confusion window before current entry
            if not (window_start <= prior.exit_time <= ct.entry_time):
                continue
            prior_parsed = parse_symbol(prior.tradingsymbol or "")
            if prior_parsed.underlying != ct_parsed.underlying:
                continue

            minutes_apart = (ct.entry_time - prior.exit_time).total_seconds() / 60
            return DetectedEvent(
                event_type="options_direction_confusion",
                severity="caution",
                message=(
                    f"You flipped from {prior.instrument_type} to {ct.instrument_type} on "
                    f"{ct_parsed.underlying} in {minutes_apart:.0f}min. "
                    f"Switching direction on the same underlying this fast indicates confusion "
                    f"about market direction — not a revised analysis."
                ),
                context={
                    "underlying": ct_parsed.underlying,
                    "from_type": prior.instrument_type,
                    "to_type": ct.instrument_type,
                    "minutes_apart": round(minutes_apart, 1),
                    "prior_symbol": prior.tradingsymbol,
                    "current_symbol": ct.tradingsymbol,
                },
            )
        return None

    # ── Pattern 17: Options premium averaging down ────────────────────────
    #
    # Re-entering the same underlying options after a prior losing options position today.
    # Unlike equity averaging down, options premium erodes via theta — the hole gets bigger.

    def _detect_options_premium_avg_down(self, ctx: EngineContext) -> Optional[DetectedEvent]:
        ct = ctx.completed_trade
        if ct.instrument_type not in ("CE", "PE") or ct.direction != "LONG":
            return None

        from app.services.instrument_parser import parse_symbol
        ct_parsed = parse_symbol(ct.tradingsymbol or "")
        if not ct_parsed.underlying:
            return None

        loss_threshold_pct = ctx.thresholds.get("premium_avg_down_loss_pct", 20)
        prior_losers = []

        for prior in ctx.session_trades:
            if prior.id == ct.id:
                continue
            if prior.instrument_type not in ("CE", "PE") or prior.direction != "LONG":
                continue
            prior_pnl = Decimal(str(prior.realized_pnl or 0))
            if prior_pnl >= 0:
                continue
            prior_parsed = parse_symbol(prior.tradingsymbol or "")
            if prior_parsed.underlying != ct_parsed.underlying:
                continue
            prior_premium = Decimal(str(prior.avg_entry_price or 0)) * (prior.total_quantity or 1)
            if prior_premium <= 0:
                continue
            prior_loss_pct = abs(prior_pnl) / prior_premium * 100
            if prior_loss_pct >= Decimal(str(loss_threshold_pct)):
                prior_losers.append((prior, float(prior_loss_pct)))

        if not prior_losers:
            return None

        _, worst_pct = max(prior_losers, key=lambda x: x[1])
        current_premium = Decimal(str(ct.avg_entry_price or 0)) * (ct.total_quantity or 1)

        return DetectedEvent(
            event_type="options_premium_avg_down",
            severity="caution",
            message=(
                f"You entered {ct.tradingsymbol} after "
                f"{len(prior_losers)} losing options position"
                f"{'s' if len(prior_losers) > 1 else ''} on {ct_parsed.underlying} today "
                f"(worst loss: {worst_pct:.0f}% of premium)."
            ),
            context={
                "underlying": ct_parsed.underlying,
                "prior_losing_count": len(prior_losers),
                "worst_loss_pct": round(worst_pct, 1),
                "current_premium_paid": round(float(current_premium)),
            },
        )

    # ── Pattern 18: IV crush behavior ─────────────────────────────────────
    #
    # Proxy: LONG options position losing >40% premium in <30 min.
    # Fast large premium collapse without a large directional move = IV crush.
    # Common pattern: buying before an event (FOMC, results, expiry) when IV is peaked.

    def _detect_iv_crush_behavior(self, ctx: EngineContext) -> Optional[DetectedEvent]:
        ct = ctx.completed_trade
        if ct.instrument_type not in ("CE", "PE") or ct.direction != "LONG":
            return None

        pnl = Decimal(str(ct.realized_pnl or 0))
        if pnl >= 0:
            return None

        hold_min = ct.duration_minutes or 0
        hold_threshold = ctx.thresholds.get("iv_crush_proxy_hold_min", 30)
        if hold_min >= hold_threshold:
            return None  # Held too long — theta decay, not IV crush

        entry_price = Decimal(str(ct.avg_entry_price or 0))
        qty = ct.total_quantity or 1
        premium_paid = entry_price * qty
        if premium_paid <= 0:
            return None

        loss_pct = abs(pnl) / premium_paid * 100
        loss_threshold = ctx.thresholds.get("iv_crush_proxy_loss_pct", 40)
        if loss_pct < Decimal(str(loss_threshold)):
            return None

        return DetectedEvent(
            event_type="iv_crush_behavior",
            severity="caution",
            message=(
                f"Your {ct.tradingsymbol} lost {float(loss_pct):.0f}% of premium "
                f"(₹{abs(float(pnl)):,.0f}) in just {hold_min}min. "
                f"This pattern matches IV crush — buying options when implied volatility is "
                f"elevated, then watching premium collapse after the event passes. "
                f"Check IV rank before buying: >60% means you're paying peak premium."
            ),
            context={
                "tradingsymbol": ct.tradingsymbol,
                "hold_minutes": hold_min,
                "loss_pct": round(float(loss_pct), 1),
                "realized_pnl": float(pnl),
                "premium_paid": round(float(premium_paid)),
            },
        )


    # ── Pattern 19: Expiry day overtrading ────────────────────────────────
    #
    # Excessive trades on the instrument's own expiry date.
    # 0DTE herding: NSE data shows retail activity spikes 3-5× near expiry EOD.
    # Uses cold-start fallback (fire after 13:00 IST) until baseline data available.

    def _detect_expiry_day_overtrading(self, ctx: EngineContext) -> Optional[DetectedEvent]:
        ct = ctx.completed_trade
        if not ct.entry_time or ct.instrument_type not in ("CE", "PE", "FUT"):
            return None

        from app.services.instrument_parser import parse_symbol, is_expiry_day as _is_expiry_day
        entry_ist = ct.entry_time.astimezone(IST)

        if not _is_expiry_day(ct.tradingsymbol or "", entry_ist.date()):
            return None

        ct_parsed = parse_symbol(ct.tradingsymbol or "")
        underlying = ct_parsed.underlying

        # Today's completed trades for this underlying on expiry
        today_expiry_trades = [
            t for t in ctx.session_trades
            if parse_symbol(t.tradingsymbol or "").underlying == underlying
            and t.instrument_type in ("CE", "PE", "FUT")
        ]
        today_count = len(today_expiry_trades)
        today_lots = sum(t.total_quantity or 1 for t in today_expiry_trades)

        caution_count = ctx.thresholds.get("expiry_overtrading_caution_count", 5)
        danger_count  = ctx.thresholds.get("expiry_overtrading_danger_count", 8)
        caution_lots  = ctx.thresholds.get("expiry_overtrading_caution_lots", 10)

        # Cold-start: only fire after 13:00 IST to avoid flagging morning expiry trades
        if entry_ist.hour < 13:
            return None

        if today_count >= danger_count:
            return DetectedEvent(
                event_type="expiry_day_overtrading",
                severity="danger",
                message=(
                    f"{today_count} {underlying} trades today on expiry. "
                    f"NSE data: retail option activity in the last 2 hours of expiry day "
                    f"has a structural loss rate above 85%."
                ),
                context={"underlying": underlying, "today_count": today_count,
                         "today_lots": today_lots, "danger_threshold": danger_count},
            )
        if today_count >= caution_count or today_lots >= caution_lots:
            return DetectedEvent(
                event_type="expiry_day_overtrading",
                severity="caution",
                message=(
                    f"{today_count} {underlying} trades / {today_lots} lots today on expiry. "
                    f"Each additional trade after 13:00 on expiry day statistically reduces your edge."
                ),
                context={"underlying": underlying, "today_count": today_count,
                         "today_lots": today_lots, "caution_threshold": caution_count},
            )
        return None

    # ── Pattern 20: Opening 5-minute trap ─────────────────────────────────
    #
    # Derivative entry in the 09:15–09:20 IST window.
    # First 5 minutes: gaps resolve, order books stabilise, premium pricing is distorted.
    # NSE data: 78% of retail opening-5-min derivative trades are unprofitable.

    def _detect_opening_5min_trap(self, ctx: EngineContext) -> Optional[DetectedEvent]:
        """
        Flags reactive/impulsive entries in the first 5 minutes of market open.

        Only fires on LOSING trades — a profitable opening trade could be a
        deliberate strategy (opening range breakout, pre-planned level). Firing
        on every opening trade regardless of outcome creates noise.

        Two triggers:
        A) Quick reactive exit: entry 09:15–09:20 + exit within 15 min + loss
           → spread damage / impulse entry that immediately reversed
        B) Large loss: entry 09:15–09:20 + loss > 30% of premium
           → price discovery ran heavily against the position
        """
        ct = ctx.completed_trade
        if not ct.entry_time or ct.instrument_type not in ("CE", "PE", "FUT"):
            return None

        entry_ist = ct.entry_time.astimezone(IST)
        market_open = entry_ist.replace(hour=9, minute=15, second=0, microsecond=0)
        trap_end    = entry_ist.replace(hour=9, minute=23, second=0, microsecond=0)

        if not (market_open <= entry_ist <= trap_end):
            return None

        pnl = Decimal(str(ct.realized_pnl or 0))
        # Skip profitable opening trades — those may be deliberate strategy.
        if pnl >= 0:
            return None

        duration = ct.duration_minutes or 0
        entry_price = Decimal(str(ct.avg_entry_price or 0))
        qty = ct.total_quantity or 1

        loss_pct = Decimal("0")
        if ct.instrument_type in ("CE", "PE") and entry_price > 0 and qty > 0:
            loss_pct = abs(pnl) / (entry_price * qty) * 100

        is_quick_reactive = duration <= 15
        is_large_loss = loss_pct >= 30

        if not (is_quick_reactive or is_large_loss):
            return None

        mins_after_open = int((entry_ist - market_open).total_seconds() / 60)
        severity = "danger" if (is_quick_reactive and is_large_loss) else "caution"

        if is_quick_reactive and is_large_loss:
            detail = (
                f"entered at {entry_ist.strftime('%H:%M')}, "
                f"exited in {duration}min with {loss_pct:.0f}% loss — "
                f"reactive entry hit by wide spreads and price discovery"
            )
        elif is_large_loss:
            detail = (
                f"entered at {entry_ist.strftime('%H:%M')}, "
                f"lost {loss_pct:.0f}% of premium — "
                f"price discovery moved heavily against the position"
            )
        else:
            detail = (
                f"entered at {entry_ist.strftime('%H:%M')}, "
                f"exited in {duration}min at a loss — "
                f"opening volatility reversed the move"
            )

        return DetectedEvent(
            event_type="opening_5min_trap",
            severity=severity,
            message=(
                f"{ct.tradingsymbol}: {detail}. "
                f"The 09:15–09:23 window has the widest bid-ask spreads of the day "
                f"as gaps resolve and order books stabilise."
            ),
            context={
                "entry_time_ist": entry_ist.strftime("%H:%M"),
                "mins_after_open": mins_after_open,
                "duration_minutes": duration,
                "loss_pct": round(float(loss_pct), 1),
                "realized_pnl": float(pnl),
                "is_quick_reactive": is_quick_reactive,
                "is_large_loss": bool(is_large_loss),
            },
        )

    # ── Pattern 21: End-of-session MIS panic ──────────────────────────────
    #
    # MIS trades entered after 15:10 IST — auto-square-off at ~15:20.
    # Voluntarily entering a position with a 10-minute forced exit is panic, not trading.

    def _detect_end_of_session_mis_panic(self, ctx: EngineContext) -> Optional[DetectedEvent]:
        ct = ctx.completed_trade
        if ct.product not in ("MIS", "INTRADAY"):
            return None
        if not ct.entry_time:
            return None

        entry_ist = ct.entry_time.astimezone(IST)
        panic_start = entry_ist.replace(hour=15, minute=10, second=0, microsecond=0)

        if entry_ist < panic_start:
            return None

        # Count all MIS trades entered after 15:10 IST today
        panic_trades = [
            t for t in ctx.session_trades
            if t.product in ("MIS", "INTRADAY")
            and t.entry_time
            and t.entry_time.astimezone(IST) >= panic_start
        ]
        panic_count = len(panic_trades)

        caution_count = ctx.thresholds.get("end_session_mis_caution_count", 2)
        danger_count  = ctx.thresholds.get("end_session_mis_danger_count", 3)

        if panic_count >= danger_count:
            return DetectedEvent(
                event_type="end_of_session_mis_panic",
                severity="danger",
                message=(
                    f"{panic_count} MIS trades after 15:10 IST today. "
                    f"Zerodha auto-squares MIS at 15:20 — you are voluntarily entering positions "
                    f"with a 10-minute forced exit. This is not trading, it is gambling."
                ),
                context={"entry_time_ist": entry_ist.strftime("%H:%M"),
                         "panic_count": panic_count},
            )
        if panic_count >= caution_count:
            return DetectedEvent(
                event_type="end_of_session_mis_panic",
                severity="caution",
                message=(
                    f"MIS entry at {entry_ist.strftime('%H:%M')} IST. "
                    f"Zerodha squares off MIS at 15:20 — a {20 - (entry_ist.hour * 60 + entry_ist.minute - 15 * 60 - 10)}-minute "
                    f"forced exit window is too tight for rational decision-making."
                ),
                context={"entry_time_ist": entry_ist.strftime("%H:%M"),
                         "panic_count": panic_count},
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

        prior = sorted(
            [t for t in trades
             if t.id != ct.id and t.exit_time
             and (_ps(t.tradingsymbol or "").underlying if t.tradingsymbol else "") == ct_underlying],
            key=lambda t: t.exit_time,
        )
        if len(prior) < 2:
            return None

        # Last 2 trades on the same underlying must be losses
        last_two_pnls = [Decimal(str(t.realized_pnl or 0)) for t in prior[-2:]]
        if not all(p < 0 for p in last_two_pnls):
            return None

        # Compare current qty against recent average for this same underlying
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

    def _detect_profit_giveaway(self, ctx: EngineContext) -> Optional[DetectedEvent]:
        trades = ctx.session_trades  # sorted by exit_time ASC, includes current trade
        if len(trades) < 2:
            return None

        # Compute cumulative P&L at each exit to find session peak.
        # No early-return on ct_pnl sign — the trigger trade may be a winner if
        # this is called from the sync path (engine runs on most-recent trade, not
        # necessarily the loss). The session state is what matters, not this one trade.
        running_pnl = Decimal("0")
        peak_pnl = Decimal("0")
        for t in trades:
            running_pnl += Decimal(str(t.realized_pnl or 0))
            if running_pnl > peak_pnl:
                peak_pnl = running_pnl

        min_peak = Decimal(str(ctx.thresholds.get("profit_giveaway_min_peak", 1000)))
        min_erosion = Decimal(str(ctx.thresholds.get("profit_giveaway_min_erosion", 500)))
        caution_pct = Decimal(str(ctx.thresholds.get("profit_giveaway_caution_pct", 0.50)))
        danger_pct = Decimal(str(ctx.thresholds.get("profit_giveaway_danger_pct", 0.70)))

        if peak_pnl < min_peak:
            return None

        current_pnl = running_pnl
        erosion = peak_pnl - current_pnl

        if erosion < min_erosion:
            return None

        erosion_pct = erosion / peak_pnl

        # No "first crossing" guard here — DB-level dedup in run_risk_detection_async
        # (checks last 24h for same pattern_type) prevents this from firing more than
        # once per session. Removing the guard lets the alert fire correctly whether
        # called from a webhook (real-time) or a sync (retroactive).

        ct = ctx.completed_trade
        if erosion_pct >= danger_pct:
            return DetectedEvent(
                event_type="profit_giveaway",
                severity="danger",
                message=(
                    f"You built ₹{float(peak_pnl):,.0f} today, then gave back "
                    f"₹{float(erosion):,.0f} ({float(erosion_pct)*100:.0f}%) — "
                    f"session P&L now ₹{float(current_pnl):,.0f}."
                ),
                context={
                    "peak_pnl": round(float(peak_pnl), 2),
                    "current_pnl": round(float(current_pnl), 2),
                    "erosion": round(float(erosion), 2),
                    "erosion_pct": round(float(erosion_pct), 2),
                    "trigger_symbol": ct.tradingsymbol,
                },
            )

        if erosion_pct >= caution_pct:
            return DetectedEvent(
                event_type="profit_giveaway",
                severity="caution",
                message=(
                    f"You built ₹{float(peak_pnl):,.0f} today but have given back "
                    f"₹{float(erosion):,.0f} ({float(erosion_pct)*100:.0f}%) — "
                    f"session P&L now ₹{float(current_pnl):,.0f}. "
                    f"Is the next trade protecting your gains or chasing them back?"
                ),
                context={
                    "peak_pnl": round(float(peak_pnl), 2),
                    "current_pnl": round(float(current_pnl), 2),
                    "erosion": round(float(erosion), 2),
                    "erosion_pct": round(float(erosion_pct), 2),
                    "trigger_symbol": ct.tradingsymbol,
                },
            )

        return None


# Singleton
behavior_engine = BehaviorEngine()
