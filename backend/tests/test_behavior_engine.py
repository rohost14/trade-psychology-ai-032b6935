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
# TestBehaviorStateMachine (11 tests) was removed 2026-08-13 along with its
# subject — `_behavior_state`, `_trajectory` and `RISK_DELTAS` no longer exist.
# See docs/GLOBALS_DERIVATION.md. The detector tests below are untouched.
# =============================================================================
# Detector pure function tests (no DB)
# =============================================================================

class TestDetectors:

    # ── Consecutive loss streak ───────────────────────────────────────────
    #
    # Four tests (no_alert_on_winner, caution_on_3_losses, danger_on_5_losses,
    # streak_resets_on_winner) were deleted 2026-08-26 with their subject.
    # `consecutive_loss_streak` is retired; the trader's own declared
    # max_consecutive_losses rule under constitution_violation covers the
    # behaviour, and is tested in test_constitution_consecutive_losses.py.

    # ── Revenge trade ─────────────────────────────────────────────────────

    def test_revenge_trade_detected(self):
        """
        REWRITTEN 2026-08-23 with its subject: revenge_trade returns a
        DetectorResult, not a DetectedEvent. It carries the layer that judged it,
        the measurements behind the verdict, and the difference between "did not
        happen" and "could not tell".

        A fast re-entry after a loss, with no equity, no baseline and no decided
        significance threshold, is A1 — measured, unjudged — so it is recorded
        and never notified. That is the designed cost of deleting the
        capital-derived gate, not a regression.
        """
        prior = make_ct(pnl=-3000, entry_offset_min=-60, duration_min=25)
        current = make_ct(pnl=-1000, entry_offset_min=-30, duration_min=20)
        ctx = make_ctx(completed_trade=current, session_trades=[prior])

        result = engine._detect_revenge_trade(ctx)

        assert result is not None
        assert result.detector == "revenge_trade"
        assert result.fired, "the structural fact should be established"
        assert result.severity == "info", (
            "measured but unjudged must not reach a notifying severity"
        )
        assert result.context["b_level"] >= 1
        assert result.context["a_level"] == 1, "the loss was measurable"

    def test_no_revenge_after_winner(self):
        """
        A winner is not something to avenge. NOT_DETECTED rather than None: the
        detector looked and can say the behaviour did not occur, which is a
        different claim from "could not tell" and is what makes a clean session
        distinguishable from an unmonitored one.
        """
        prior = make_ct(pnl=5000, entry_offset_min=-60, duration_min=25)
        current = make_ct(pnl=-1000, entry_offset_min=-30, duration_min=20)
        ctx = make_ctx(completed_trade=current, session_trades=[prior])

        result = engine._detect_revenge_trade(ctx)

        assert result is not None
        assert not result.fired
        assert not result.abstained, "we could see clearly enough to say no"

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
        # F18: the detector now reads started_at, so the fixture must supply a
        # real one. Entry falls INSIDE the cooldown here, which is the violation.
        cd.started_at = now_utc() - timedelta(minutes=10)
        cd.reason = "3 consecutive losses"
        ctx = make_ctx(active_cooldowns=[cd])
        ctx.completed_trade.entry_time = now_utc() - timedelta(minutes=5)
        event = engine._detect_cooldown_violation(ctx)
        assert event is not None
        assert event.event_type == "cooldown_violation"
        # S28+: cooldown_violation is analytics-only (severity="info", never a
        # user-facing alert). Registry: disposition=analytics, level 0.
        # Phase 2 redesigns it as the constitution_violation discipline pattern.
        assert event.severity == "info"

    def test_no_violation_without_cooldown(self):
        ctx = make_ctx(active_cooldowns=[])
        event = engine._detect_cooldown_violation(ctx)
        assert event is None

    def test_no_violation_when_the_position_was_opened_before_the_cooldown(self):
        """
        F18. The engine runs on position CLOSE, and this detector used to read
        only the cooldown - never the trade - so a position opened well before
        a cooldown began and merely closed during it was reported as
        "Traded during active cooldown". Closing is what a cooldown wants.

        The decision a cooldown governs is the ENTRY.
        """
        cd = MagicMock(spec=Cooldown)
        cd.expires_at = now_utc() + timedelta(minutes=20)
        cd.started_at = now_utc() - timedelta(minutes=5)
        cd.reason = "3 consecutive losses"
        ctx = make_ctx(active_cooldowns=[cd])
        ctx.completed_trade.entry_time = now_utc() - timedelta(hours=2)
        assert engine._detect_cooldown_violation(ctx) is None

    def test_cooldown_violation_survives_missing_timestamps(self):
        """A detector must not crash on a row with no started_at."""
        cd = MagicMock(spec=Cooldown)
        cd.expires_at = now_utc() + timedelta(minutes=20)
        cd.started_at = None
        cd.reason = "loss limit"
        ctx = make_ctx(active_cooldowns=[cd])
        assert engine._detect_cooldown_violation(ctx) is not None

    # ── Direction instability — RETIRED 2026-08-28 (Pattern #11) ─────────
    #
    # `test_direction_instability_detected` and `test_no_flip_on_same_direction`
    # were deleted with their subject. They exercised `_detect_direction_
    # instability`, which no longer exists, so they could only fail on an
    # AttributeError. The retirement is covered by
    # tests/test_direction_instability_retired.py.
    #
    # Worth noting what the first of them asserted: `level == 1`, the exact
    # same-symbol LONG->SHORT reversal. That branch never fired once on the real
    # book (911 LONG against 1 SHORT), so the only coverage it ever had was
    # synthetic.

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

    def test_meltdown_says_your_limit_only_when_it_is_theirs(self):
        """
        A declared limit is the trader's commitment and may be called "your".
        """
        session = make_session(session_pnl=-21000)
        ctx = make_ctx(session=session, thresholds={
            "daily_loss_limit": 25000, "trading_capital": 500000,
        })
        event = engine._detect_session_meltdown(ctx)
        assert event is not None
        assert "of your" in event.message
        assert event.context["limit_source"] == "declared"

    def test_meltdown_does_not_call_an_invented_limit_theirs(self):
        """
        With no declared limit the detector invents one at 5% of capital. It
        still fires - a derived limit protects just as well - but calling it
        "your ₹25,000 daily limit" claims the trader set a number they never
        saw. The copy has to say where it came from, and that doubles as the
        prompt to set a real one.
        """
        session = make_session(session_pnl=-21000)   # 84% of 5% of 500000
        ctx = make_ctx(session=session, thresholds={
            "daily_loss_limit": None, "trading_capital": 500000,
        })
        event = engine._detect_session_meltdown(ctx)
        assert event is not None, "a derived limit must still protect the trader"
        # The forbidden claim is that the LIMIT is theirs, not any use of the
        # word "your" - the honest message legitimately says "your capital",
        # which IS a fact about them. So assert on the possessive applied to the
        # rupee figure: "your Rs 25,000 daily limit" is the lie.
        assert "your ₹" not in event.message
        assert "5% of your capital" in event.message
        assert "not set a daily loss limit" in event.message
        assert event.context["limit_source"] == "capital_derived"

    def test_meltdown_stays_silent_when_neither_limit_nor_capital_is_known(self):
        session = make_session(session_pnl=-21000)
        ctx = make_ctx(session=session, thresholds={
            "daily_loss_limit": None, "trading_capital": None,
        })
        assert engine._detect_session_meltdown(ctx) is None

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
        assert result.alerts == []
        assert result.session_id is not None

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
