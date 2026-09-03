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
    anchor=None,
):
    """
    Build a mock CompletedTrade for testing.

    `anchor` is the instant the offsets are measured from. It defaults to now,
    which is what almost every caller wants and what every existing caller
    got. Pass a fixed instant when the test asserts on something the calendar
    can move - "opened today", session boundaries - so the result does not
    depend on what time the suite happens to run.
    """
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
    now = anchor or now_utc()
    ct.entry_time = now + timedelta(minutes=entry_offset_min)
    ct.exit_time = now + timedelta(minutes=entry_offset_min + duration_min)
    return ct


def make_session(risk_score=0.0, peak_risk_score=0.0, session_pnl=0.0,
                 session_date=None):
    """
    `session_date` defaults to today. Pass it explicitly alongside a fixed
    `anchor` on the trades, or the two disagree the moment the suite runs
    across a day boundary.
    """
    s = MagicMock(spec=TradingSession)
    s.id = uuid4()
    s.risk_score = Decimal(str(risk_score))
    s.peak_risk_score = Decimal(str(peak_risk_score))
    s.session_pnl = Decimal(str(session_pnl))
    s.session_date = session_date or date.today()
    s.market_open = None
    return s


def make_ctx(
    completed_trade=None,
    session_trades=None,
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

    # ── Panic exit — RETIRED 2026-08-29 (Pattern 14) ─────────────────────
    #
    # `test_panic_exit_detected`, `test_no_panic_exit_on_profitable_quick_trade`
    # and `test_no_panic_exit_on_slow_loss` were DELETED with their subject.
    # `_detect_panic_exit` no longer exists, so they could only fail on an
    # AttributeError and prove nothing.
    #
    # Retired because its subject did not exist: sub-5-minute holds won at 38.3%
    # against 39.8% for longer holds, so it selected the losing half of an
    # ordinary habit - outcome, not behaviour. Its retirement is held in place by
    # tests/test_panic_exit_retired.py.

    # ── Cooldown violation — RETIRED 2026-08-29 (Pattern 15) ─────────────
    #
    # `test_cooldown_violation_detected`, `test_no_violation_without_cooldown`,
    # `test_no_violation_when_the_position_was_opened_before_the_cooldown` and
    # `test_cooldown_violation_survives_missing_timestamps` were DELETED with
    # their subject. `_detect_cooldown_violation` no longer exists, so they
    # could only fail on an AttributeError.
    #
    # Retired because its precondition never occurred on the live path and the
    # behaviour is covered by constitution_violation's `cooldown` rule at
    # danger. Held in place by tests/test_cooldown_violation_retired.py, which
    # also pins that the shared cooldown infrastructure still works.

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

    def test_meltdown_abstains_when_no_limit_is_declared(self):
        """
        REWRITTEN 2026-08-30 with its subject.

        This test previously asserted the OPPOSITE - that with no declared limit
        the detector invents one at 5% of capital and still fires, because "a
        derived limit protects just as well". That fallback is gone.

        It had no documented provenance and contradicted a decided policy:
        `constitution_service` owns `daily_loss_limit` as a RULE_FIELD and
        deliberately returns None for it, because F&O lot sizes make a
        percent-of-capital money rule unusable - a real replay produced 212 rule
        violations across 61 sessions, 54% of all alerts, none describing
        behaviour. Money rules are suggested, never applied.

        The test is kept rather than deleted because its SUBJECT survives: what
        the detector may claim about a limit. The answer changed from "say where
        the number came from" to "there is no number".
        """
        session = make_session(session_pnl=-21000)
        ctx = make_ctx(session=session, thresholds={
            "daily_loss_limit": None, "trading_capital": 500000,
        })
        assert engine._detect_session_meltdown(ctx) is None, (
            "capital is not a loss limit - with none declared there is no "
            "judgement to make")

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
