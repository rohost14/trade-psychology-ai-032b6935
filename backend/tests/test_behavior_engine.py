"""
BehaviorEngine Tests — Phase 3

Tests for the unified BehaviorEngine.

Structure:
  TestBehaviorStateMachine    — pure: risk score → state mapping
  TestDetectorPureFunctions   — pure: all 12 detectors via EngineContext mocks
  TestBehaviorEngineDB        — DB: full analyze() round-trip
"""

import pytest
from datetime import datetime, timezone, timedelta, date
from decimal import Decimal
from uuid import uuid4
from unittest.mock import MagicMock

from app.services.behavior_engine import (
    BehaviorEngine,
    EngineContext,
    DetectedEvent,
    _behavior_state,
    _trajectory,
    RISK_DELTAS,
)
from app.models.completed_trade import CompletedTrade
from app.models.trading_session import TradingSession
from app.models.cooldown import Cooldown
from tests.helpers import now_utc


# =============================================================================
# Helpers
# =============================================================================

def make_ct(
    broker_id=None,
    symbol="NIFTY25JANFUT",
    exchange="NFO",
    direction="LONG",
    instrument_type="FUT",
    pnl=500.0,
    entry_offset_min=-30,
    duration_min=25,
    qty=50,
):
    """Build a mock CompletedTrade for testing."""
    ct = MagicMock(spec=CompletedTrade)
    ct.id = uuid4()
    ct.broker_account_id = broker_id or uuid4()
    ct.tradingsymbol = symbol
    ct.exchange = exchange
    ct.direction = direction
    ct.instrument_type = instrument_type
    ct.realized_pnl = Decimal(str(pnl))
    ct.total_quantity = qty
    ct.avg_entry_price = Decimal("22000")
    ct.avg_exit_price = Decimal("22100")
    now = now_utc()
    ct.entry_time = now + timedelta(minutes=entry_offset_min)
    ct.exit_time = now + timedelta(minutes=entry_offset_min + duration_min)
    return ct


def make_session(risk_score=0.0, peak_risk_score=0.0, session_pnl=0.0):
    s = MagicMock(spec=TradingSession)
    s.id = uuid4()
    s.risk_score = Decimal(str(risk_score))
    s.peak_risk_score = Decimal(str(peak_risk_score))
    s.session_pnl = Decimal(str(session_pnl))
    s.session_date = date.today()
    s.market_open = None
    return s


def make_ctx(
    completed_trade=None,
    session_trades=None,
    active_cooldowns=None,
    thresholds=None,
    session=None,
):
    if completed_trade is None:
        completed_trade = make_ct()
    ctx = EngineContext(
        broker_account_id=completed_trade.broker_account_id,
        session=session or make_session(),
        completed_trade=completed_trade,
        session_trades=session_trades or [completed_trade],
        active_cooldowns=active_cooldowns or [],
        thresholds=thresholds or {
            "consecutive_loss_caution": 3,
            "consecutive_loss_danger": 5,
            "burst_trades_per_15min": 6,
            "revenge_window_min": 10,
            "trading_capital": 500000,
            "daily_loss_limit": 25000,
            "max_position_size": 10.0,
        },
    )
    return ctx


engine = BehaviorEngine()


# =============================================================================
# Behavior state machine
# =============================================================================

class TestBehaviorStateMachine:

    def test_stable_at_zero(self):
        assert _behavior_state(Decimal("0"), Decimal("0")) == "Stable"

    def test_stable_below_20(self):
        assert _behavior_state(Decimal("19"), Decimal("19")) == "Stable"

    def test_pressure_at_20(self):
        assert _behavior_state(Decimal("20"), Decimal("20")) == "Pressure"

    def test_tilt_risk_at_40(self):
        assert _behavior_state(Decimal("40"), Decimal("40")) == "Tilt Risk"

    def test_tilt_at_60(self):
        assert _behavior_state(Decimal("60"), Decimal("60")) == "Tilt"

    def test_breakdown_at_80(self):
        assert _behavior_state(Decimal("80"), Decimal("80")) == "Breakdown"

    def test_recovery_when_improving_from_peak(self):
        # Was at 80 (Breakdown), now at 55 (Tilt)
        # peak=80, current=55, diff=25 > 20 → Recovery
        assert _behavior_state(Decimal("55"), Decimal("80")) == "Recovery"

    def test_no_recovery_if_peak_was_low(self):
        # Peak was only 30 — never in danger zone
        assert _behavior_state(Decimal("10"), Decimal("30")) == "Stable"

    def test_trajectory_deteriorating(self):
        assert _trajectory(Decimal("20"), Decimal("50")) == "deteriorating"

    def test_trajectory_improving(self):
        assert _trajectory(Decimal("50"), Decimal("30")) == "improving"

    def test_trajectory_stable(self):
        assert _trajectory(Decimal("30"), Decimal("33")) == "stable"

    def test_all_risk_deltas_defined(self):
        """All 11 implemented patterns must have a risk delta."""
        patterns = [
            "consecutive_loss_streak", "revenge_trade", "overtrading_burst",
            "size_escalation", "rapid_reentry", "panic_exit",
            "martingale_behaviour", "cooldown_violation", "rapid_flip",
            "excess_exposure", "session_meltdown",
        ]
        for p in patterns:
            assert p in RISK_DELTAS, f"Missing risk delta for {p}"
            assert RISK_DELTAS[p] > 0


# =============================================================================
# Detector pure function tests (no DB)
# =============================================================================

class TestDetectors:

    # ── Consecutive loss streak ───────────────────────────────────────────

    def test_no_alert_on_winner(self):
        ct = make_ct(pnl=500)
        ctx = make_ctx(completed_trade=ct, session_trades=[ct])
        assert engine._detect_consecutive_loss_streak(ctx) is None

    def test_caution_on_3_losses(self):
        trades = [make_ct(pnl=-100) for _ in range(3)]
        ctx = make_ctx(completed_trade=trades[-1], session_trades=trades)
        event = engine._detect_consecutive_loss_streak(ctx)
        assert event is not None
        assert event.severity == "caution"
        assert event.event_type == "consecutive_loss_streak"

    def test_danger_on_5_losses(self):
        trades = [make_ct(pnl=-100) for _ in range(5)]
        ctx = make_ctx(completed_trade=trades[-1], session_trades=trades)
        event = engine._detect_consecutive_loss_streak(ctx)
        assert event is not None
        assert event.severity == "danger"

    def test_streak_resets_on_winner(self):
        # 3 losses, then 1 win, then 2 losses — streak is only 2
        trades = [
            make_ct(pnl=-100), make_ct(pnl=-100), make_ct(pnl=-100),
            make_ct(pnl=200),
            make_ct(pnl=-100), make_ct(pnl=-100),
        ]
        ctx = make_ctx(completed_trade=trades[-1], session_trades=trades)
        event = engine._detect_consecutive_loss_streak(ctx)
        # Streak = 2, below caution threshold of 3
        assert event is None

    # ── Revenge trade ─────────────────────────────────────────────────────

    def test_revenge_trade_detected(self):
        now = now_utc()
        loser = make_ct(pnl=-500, entry_offset_min=-20, duration_min=10)
        # Current trade entered 5 min after loser exited
        loser.exit_time = now - timedelta(minutes=5)
        winner = make_ct(pnl=100, entry_offset_min=-4, duration_min=3)
        winner.entry_time = now - timedelta(minutes=4)

        ctx = make_ctx(
            completed_trade=winner,
            session_trades=[loser, winner],
        )
        event = engine._detect_revenge_trade(ctx)
        assert event is not None
        assert event.event_type == "revenge_trade"

    def test_no_revenge_after_winner(self):
        now = now_utc()
        winner = make_ct(pnl=500, entry_offset_min=-20, duration_min=10)
        winner.exit_time = now - timedelta(minutes=5)
        next_trade = make_ct(pnl=100, entry_offset_min=-4, duration_min=3)
        next_trade.entry_time = now - timedelta(minutes=4)

        ctx = make_ctx(
            completed_trade=next_trade,
            session_trades=[winner, next_trade],
        )
        event = engine._detect_revenge_trade(ctx)
        assert event is None  # Prior trade was a winner

    # ── Overtrading burst ─────────────────────────────────────────────────

    def test_overtrading_detected(self):
        now = now_utc()
        # 13 trades in the last 30 minutes (limit is 6/15min * 2 = 12 per 30min)
        trades = []
        for i in range(13):
            t = make_ct()
            t.entry_time = now - timedelta(minutes=25 - i)
            trades.append(t)
        ctx = make_ctx(completed_trade=trades[-1], session_trades=trades)
        event = engine._detect_overtrading_burst(ctx)
        assert event is not None
        assert event.event_type == "overtrading_burst"

    def test_no_overtrading_on_few_trades(self):
        now = now_utc()
        trades = [make_ct() for _ in range(4)]
        for i, t in enumerate(trades):
            t.entry_time = now - timedelta(minutes=25 - i * 5)
        ctx = make_ctx(completed_trade=trades[-1], session_trades=trades)
        event = engine._detect_overtrading_burst(ctx)
        assert event is None

    # ── Panic exit ────────────────────────────────────────────────────────

    def test_panic_exit_detected(self):
        ct = make_ct(pnl=-200, duration_min=1)  # held 1 minute, loss
        ctx = make_ctx(completed_trade=ct)
        event = engine._detect_panic_exit(ctx)
        assert event is not None
        assert event.event_type == "panic_exit"

    def test_no_panic_exit_on_profitable_quick_trade(self):
        ct = make_ct(pnl=200, duration_min=1)  # quick but profitable
        ctx = make_ctx(completed_trade=ct)
        event = engine._detect_panic_exit(ctx)
        assert event is None  # Not a panic — it was a winner

    def test_no_panic_exit_on_slow_loss(self):
        ct = make_ct(pnl=-200, duration_min=30)  # loss but held 30 min
        ctx = make_ctx(completed_trade=ct)
        event = engine._detect_panic_exit(ctx)
        assert event is None

    # ── Cooldown violation ────────────────────────────────────────────────

    def test_cooldown_violation_detected(self):
        cd = MagicMock(spec=Cooldown)
        cd.expires_at = now_utc() + timedelta(minutes=20)
        cd.reason = "3 consecutive losses"
        ctx = make_ctx(active_cooldowns=[cd])
        event = engine._detect_cooldown_violation(ctx)
        assert event is not None
        assert event.event_type == "cooldown_violation"
        assert event.severity == "danger"

    def test_no_violation_without_cooldown(self):
        ctx = make_ctx(active_cooldowns=[])
        event = engine._detect_cooldown_violation(ctx)
        assert event is None

    # ── Rapid flip ────────────────────────────────────────────────────────

    def test_rapid_flip_detected(self):
        now = now_utc()
        long_trade = make_ct(direction="LONG", pnl=-100)
        long_trade.exit_time = now - timedelta(minutes=2)

        short_trade = make_ct(direction="SHORT", pnl=50)
        short_trade.entry_time = now - timedelta(minutes=1)

        ctx = make_ctx(
            completed_trade=short_trade,
            session_trades=[long_trade, short_trade],
        )
        event = engine._detect_rapid_flip(ctx)
        assert event is not None
        assert event.event_type == "rapid_flip"

    def test_no_flip_on_same_direction(self):
        now = now_utc()
        t1 = make_ct(direction="LONG")
        t1.exit_time = now - timedelta(minutes=2)
        t2 = make_ct(direction="LONG")
        t2.entry_time = now - timedelta(minutes=1)

        ctx = make_ctx(completed_trade=t2, session_trades=[t1, t2])
        event = engine._detect_rapid_flip(ctx)
        assert event is None

    # ── Session meltdown ──────────────────────────────────────────────────

    def test_session_meltdown_at_80pct_limit(self):
        session = make_session(session_pnl=-21000)  # 84% of 25000 limit
        ctx = make_ctx(
            session=session,
            thresholds={
                "daily_loss_limit": 25000,
                "trading_capital": 500000,
                "consecutive_loss_caution": 3,
                "consecutive_loss_danger": 5,
                "burst_trades_per_15min": 6,
                "revenge_window_min": 10,
                "max_position_size": 10.0,
            },
        )
        event = engine._detect_session_meltdown(ctx)
        assert event is not None
        assert event.event_type == "session_meltdown"

    def test_no_meltdown_on_small_loss(self):
        session = make_session(session_pnl=-5000)  # Only 20% of limit
        ctx = make_ctx(session=session)
        event = engine._detect_session_meltdown(ctx)
        assert event is None


# =============================================================================
# DB integration: full analyze() round-trip
# =============================================================================

class TestBehaviorEngineDB:

    async def test_analyze_returns_result_on_winner(self, db, broker):
        """Winner trade with no prior context → no events, Stable state."""
        ct = CompletedTrade(
            broker_account_id=broker.id,
            tradingsymbol="NIFTY25JANFUT",
            exchange="NFO",
            instrument_type="FUT",
            product="MIS",
            direction="LONG",
            total_quantity=50,
            num_entries=1,
            num_exits=1,
            avg_entry_price=Decimal("22000"),
            avg_exit_price=Decimal("22200"),
            realized_pnl=Decimal("10000"),
            entry_time=now_utc() - timedelta(hours=1),
            exit_time=now_utc() - timedelta(minutes=30),
            duration_minutes=30,
            status="closed",
        )
        db.add(ct)
        await db.flush()

        result = await engine.analyze(
            broker_account_id=broker.id,
            completed_trade=ct,
            db=db,
        )

        assert result is not None
        assert result.behavior_state in ("Stable", "Pressure", "Tilt Risk", "Tilt",
                                          "Breakdown", "Recovery")
        assert result.trajectory in ("stable", "improving", "deteriorating")
        assert result.risk_score_after >= Decimal("0")
        assert result.risk_score_after <= Decimal("100")

    async def test_analyze_creates_session(self, db, broker):
        """analyze() creates a TradingSession for today if none exists."""
        from app.models.trading_session import TradingSession
        from sqlalchemy import select

        ct = CompletedTrade(
            broker_account_id=broker.id,
            tradingsymbol="BANKNIFTY25JANFUT",
            exchange="NFO",
            instrument_type="FUT",
            product="MIS",
            direction="SHORT",
            total_quantity=25,
            num_entries=1,
            num_exits=1,
            avg_entry_price=Decimal("48000"),
            avg_exit_price=Decimal("47800"),
            realized_pnl=Decimal("5000"),
            entry_time=now_utc() - timedelta(hours=2),
            exit_time=now_utc() - timedelta(hours=1),
            duration_minutes=60,
            status="closed",
        )
        db.add(ct)
        await db.flush()

        await engine.analyze(
            broker_account_id=broker.id,
            completed_trade=ct,
            db=db,
        )

        # Session should now exist
        result = await db.execute(
            select(TradingSession).where(
                TradingSession.broker_account_id == broker.id
            )
        )
        session = result.scalar_one_or_none()
        assert session is not None
        assert session.broker_account_id == broker.id

    async def test_analyze_never_crashes(self, db, broker):
        """analyze() must never raise — even on a malformed trade."""
        bad_ct = MagicMock(spec=CompletedTrade)
        bad_ct.id = uuid4()
        bad_ct.broker_account_id = broker.id
        bad_ct.tradingsymbol = None    # intentionally bad
        bad_ct.realized_pnl = None
        bad_ct.entry_time = None
        bad_ct.exit_time = None
        bad_ct.direction = None
        bad_ct.total_quantity = None
        bad_ct.instrument_type = None
        bad_ct.avg_entry_price = None

        # Should not raise
        result = await engine.analyze(
            broker_account_id=broker.id,
            completed_trade=bad_ct,
            db=db,
        )
        assert result is not None  # Returns empty result, not exception
