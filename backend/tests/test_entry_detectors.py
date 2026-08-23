"""
E5 — the inferred detectors, run at entry, in shadow.

The plan assumed these would need rewriting against a new context. Reading them
showed otherwise: revenge_trade stacks confidence signals from the gap since the
last losing exit, the underlying, the size ratio and session P&L — none of which
need the outcome. It is already entry-decidable, and takes a CompletedTrade only
because that is what the engine hands it.

So the tests below drive the REAL detectors through an EntryView. If they passed
against a reimplementation they would prove nothing; the risk being guarded is
that a position which has not resolved makes a detector behave strangely, and
that is only visible with the actual detector bodies in the loop.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.models.completed_trade import CompletedTrade
from app.models.trading_session import TradingSession
from app.services.behavior_engine import BehaviorEngine, EngineContext
from app.services.entry_detectors import (
    ENTRY_CONFIDENCE_FLOOR, ENTRY_DECIDABLE, EntryView, above_entry_floor,
    evaluate_entry, summarise_entry_evaluation,
)

NOW = datetime.now(timezone.utc)
ACCOUNT = uuid4()
engine = BehaviorEngine()


def closed_trade(symbol="NIFTY25AUG24500CE", pnl=-4200.0, minutes_ago=8, qty=50):
    ct = MagicMock(spec=CompletedTrade)
    ct.id = uuid4()
    ct.broker_account_id = ACCOUNT
    ct.tradingsymbol = symbol
    ct.exchange = "NFO"
    ct.instrument_type = symbol[-2:]
    ct.direction = "LONG"
    ct.product = "MIS"
    ct.realized_pnl = Decimal(str(pnl))
    ct.pnl_pct = None
    ct.total_quantity = qty
    ct.avg_entry_price = Decimal("100")
    ct.avg_exit_price = Decimal("92")
    ct.entry_time = NOW - timedelta(minutes=minutes_ago + 5)
    ct.exit_time = NOW - timedelta(minutes=minutes_ago)
    ct.duration_minutes = 5
    ct.quality_score = None
    return ct


def entry(symbol="NIFTY25AUG24500CE", qty=150, direction="LONG"):
    return EntryView(
        broker_account_id=ACCOUNT, tradingsymbol=symbol, exchange="NFO",
        product="MIS", direction=direction, total_quantity=qty, entry_time=NOW,
        avg_entry_price=100.0,
    )


def session(pnl=-4200.0):
    s = MagicMock(spec=TradingSession)
    s.id = uuid4()
    s.session_pnl = Decimal(str(pnl))
    s.risk_score = Decimal("0")
    s.peak_risk_score = Decimal("0")
    s.market_open = None
    return s


def ctx(view, trades, session_pnl=-4200.0, thresholds=None):
    return EngineContext(
        broker_account_id=ACCOUNT,
        session=session(session_pnl),
        completed_trade=view,
        session_trades=trades,
        active_cooldowns=[],
        thresholds=thresholds or {
            "revenge_min_loss_inr": 500,
            "revenge_window_caution_min": 20,
            "revenge_window_danger_min": 5,
            "signal_points_critical": 30, "signal_points_high": 20,
            "signal_points_medium": 10, "signal_points_low": 5,
            "trading_capital": 500000,
        },
    )


# ── The adapter works on the real detectors ──────────────────────────────────

def test_revenge_trade_fires_at_entry_from_the_real_detector():
    """
    Eight minutes after a ₹4,200 loss on the same instrument, at 3× the size.
    Everything that decision needs is knowable the moment the position opens —
    which is the claim E5 rests on, tested through the detector itself.
    """
    events = evaluate_entry(engine, ctx(entry(), [closed_trade()]))
    types = [e.event_type for e in events]
    assert "revenge_trade" in types


def test_entry_events_are_always_marked_shadow():
    """
    Nothing in E5 may alert. A detection here is evidence for a promotion
    decision, and the flag machinery is what promotes it.
    """
    events = evaluate_entry(engine, ctx(entry(), [closed_trade()]))
    assert events
    assert all(e.shadow is True for e in events)


def test_entry_events_are_tagged_as_entry_time():
    events = evaluate_entry(engine, ctx(entry(), [closed_trade()]))
    assert all(e.context.get("at_entry") is True for e in events)


def test_no_prior_loss_means_no_revenge_detection():
    """A calm first trade of the day must produce nothing."""
    events = evaluate_entry(engine, ctx(entry(), [], session_pnl=0.0))
    assert [e for e in events if e.event_type == "revenge_trade"] == []


def test_a_profitable_prior_trade_is_not_revenge():
    events = evaluate_entry(engine, ctx(entry(), [closed_trade(pnl=3000.0)], session_pnl=3000.0))
    assert [e for e in events if e.event_type == "revenge_trade"] == []


def test_a_long_gap_since_the_loss_is_not_revenge():
    """Beyond the caution window it is a new decision, not a reaction."""
    events = evaluate_entry(engine, ctx(entry(), [closed_trade(minutes_ago=90)]))
    assert [e for e in events if e.event_type == "revenge_trade"] == []


def test_a_scratch_loss_is_recorded_but_never_notified():
    """
    REWRITTEN 2026-08-23 with its subject. This asserted that a loss below
    `revenge_min_loss_inr` produced nothing — and that gate was deleted, because
    it resolved to 1% of capital and therefore silenced the detector entirely on
    a larger account (8 alerts at Rs 50,000, zero at Rs 5,00,000).

    Under the frozen contract a small loss is A1: measured, and with no decided
    significance threshold there is no sanctioned rule for calling it large. So
    it is recorded as `info` — evidence, countable, never notified — rather than
    suppressed by a threshold nobody chose.
    """
    events = evaluate_entry(engine, ctx(entry(), [closed_trade(pnl=-120.0)]))
    revenge = [e for e in events if e.event_type == "revenge_trade"]
    assert revenge, "the structural fact should still be recorded"
    assert all(e.severity in ("info", "caution") for e in revenge)
    assert all(e.shadow for e in revenge), (
        "entry-time output is shadow evidence and never notifies, whatever the "
        "severity"
    )


# ── The whitelist is the safety property ─────────────────────────────────────

def test_outcome_dependent_detectors_are_never_asked():
    """
    early_exit, panic_exit and profit_giveaway are statements about a completed
    outcome. Run against a position that has not resolved they could only
    produce nonsense, so the whitelist never offers them the question.
    """
    for name in ("early_exit", "panic_exit", "profit_giveaway",
                 "consecutive_loss_streak", "no_stoploss", "opening_5min_trap"):
        assert name not in ENTRY_DECIDABLE


def test_whitelist_names_are_all_real_detectors():
    """A typo here would silently disable an entry detector."""
    from app.services.detector_registry import BY_NAME
    unknown = [n for n in ENTRY_DECIDABLE if n not in BY_NAME]
    assert unknown == []


def test_an_unknown_detector_in_the_whitelist_is_skipped_not_fatal():
    events = evaluate_entry(engine, ctx(entry(), [closed_trade()]),
                            whitelist=("does_not_exist", "revenge_trade"))
    assert [e.event_type for e in events] == ["revenge_trade"]


def test_one_failing_detector_does_not_lose_the_others():
    """
    A detector that trips over an unresolved position must not take the other
    nine down with it — entry evaluation is best-effort context.
    """
    class Boom(BehaviorEngine):
        def _detect_rapid_reentry(self, _ctx):
            raise RuntimeError("no exit price")

    events = evaluate_entry(Boom(), ctx(entry(), [closed_trade()]),
                            whitelist=("rapid_reentry", "revenge_trade"))
    assert [e.event_type for e in events] == ["revenge_trade"]


# ── The unresolved position must not read as a zero-P&L trade ────────────────

def test_entry_view_reports_no_outcome_rather_than_zero():
    """
    `float(ct.realized_pnl or 0)` is the idiom throughout the engine, so None
    flows through as "no loss" — the correct reading of a position that has not
    closed. A zero would be a claim about a trade that has not happened.
    """
    v = entry()
    assert v.realized_pnl is None
    assert v.exit_time is None
    assert v.duration_minutes is None
    assert v.pnl_pct is None


def test_entry_view_derives_instrument_type_from_the_symbol():
    assert entry("NIFTY25AUG24500CE").instrument_type == "CE"
    assert entry("NIFTY25AUG24500PE").instrument_type == "PE"
    assert entry("NIFTY25AUGFUT").instrument_type == "FUT"
    assert entry("RELIANCE").instrument_type == "EQ"


def test_short_positions_are_described_as_short():
    from app.services.entry_detectors import entry_view_from_position
    from types import SimpleNamespace

    pos = SimpleNamespace(tradingsymbol="NIFTY25AUG24500CE", total_quantity=-50,
                          exchange="NFO", product="MIS", average_entry_price=100)
    view = entry_view_from_position(ACCOUNT, pos, NOW)
    assert view.direction == "SHORT"
    assert view.total_quantity == 50


# ── The confidence floor ─────────────────────────────────────────────────────

def test_detections_below_the_floor_do_not_count_as_findings():
    """
    An inferred pattern raised from an unresolved position is a claim on partial
    evidence, so it clears a higher bar than the same pattern after the outcome
    is known. Below the floor it is still recorded — evidence is never
    suppressed — it just is not what a promotion decision reads.
    """
    low = MagicMock(confidence=ENTRY_CONFIDENCE_FLOOR - 1)
    high = MagicMock(confidence=ENTRY_CONFIDENCE_FLOOR)
    assert above_entry_floor(low) is False
    assert above_entry_floor(high) is True


def test_a_detection_with_no_confidence_does_not_clear_the_floor():
    assert above_entry_floor(MagicMock(confidence=None)) is False


def test_summary_separates_detections_from_findings():
    events = [
        MagicMock(event_type="revenge_trade", severity="danger", confidence=90),
        MagicMock(event_type="revenge_trade", severity="caution", confidence=20),
        MagicMock(event_type="fomo_entry", severity="caution", confidence=75),
    ]
    summary = summarise_entry_evaluation(events)
    assert summary["detections"] == 3
    assert summary["above_floor"] == 2
    assert summary["by_detector"][0]["detector"] == "revenge_trade"
    assert summary["by_detector"][0]["above_floor"] == 1
