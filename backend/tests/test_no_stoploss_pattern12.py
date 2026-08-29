"""
Pattern 12 — `no_stoploss` after the 2026-08-29 review.

Two things changed and one thing deliberately did not.

CHANGED — the claim. The message used to end "No stop-loss order detected on
this trade", asserted from the EXIT FILL's order type. It was checkable on 0 of
52 alerts in the reference book, and structurally unknowable in production until
F1, because exit_trade_ids held Kite order ids while the consumer matched
Trade.id UUIDs. Even fixed, the exit fill cannot say whether a RESTING stop
existed - that needs the order book, which no detector reads.

CHANGED — the dead weekly-expiry arm. It read the same 25%/5min as the normal
gate, so it selected the same trades while labelling them "(expiry day)".

UNCHANGED — every threshold, the firing set, and the F4 direction question.
"""
import inspect
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.trading_defaults import COLD_START_DEFAULTS
from app.services.behavior_engine import BehaviorEngine, EngineContext

engine = BehaviorEngine()


def _ct(*, symbol="NIFTY25APR24000CE", itype="CE", direction="LONG",
        entry=100.0, qty=75, pnl=-3000.0, duration=30):
    return SimpleNamespace(
        id=uuid4(), broker_account_id=uuid4(), tradingsymbol=symbol,
        exchange="NFO", product="MIS", instrument_type=itype, direction=direction,
        total_quantity=qty, avg_entry_price=Decimal(str(entry)),
        avg_exit_price=Decimal("60"), realized_pnl=Decimal(str(pnl)),
        duration_minutes=duration,
        entry_time=datetime(2026, 4, 15, 10, 0, tzinfo=timezone.utc),
        exit_time=datetime(2026, 4, 15, 11, 0, tzinfo=timezone.utc),
        num_entries=1, num_exits=1, status="closed")


def _ctx(ct, exit_types=None):
    return EngineContext(
        broker_account_id=ct.broker_account_id,
        session=SimpleNamespace(session_pnl=Decimal("0"),
                                session_date=ct.exit_time.date(), market_open=None),
        completed_trade=ct, session_trades=[ct], active_cooldowns=[],
        thresholds=dict(COLD_START_DEFAULTS), exit_order_types=exit_types or [])


# ── the claim ──────────────────────────────────────────────────────────────

FORBIDDEN = ("no stop-loss", "no stop loss", "stop-loss order detected",
             "without a stop", "stop-loss was")


def test_it_never_claims_a_stop_loss_was_absent():
    """
    The alert must not assert the absence of something it did not look at. It
    reads the exit fill, never the resting order book.
    """
    ev = engine._detect_no_stoploss(_ctx(_ct()))
    assert ev is not None
    text = ev.message.lower()
    for phrase in FORBIDDEN:
        assert phrase not in text, "message still claims: " + phrase


def test_the_message_is_silent_on_mechanism_when_it_is_unobserved():
    """
    With no order type available - the state of every trade in the reference
    book, and of every live trade before F1 - the alert reports how far the loss
    ran and stops there.
    """
    ev = engine._detect_no_stoploss(_ctx(_ct(), exit_types=[]))
    assert ev.context["exit_mechanism_observed"] is False
    assert "exit was" not in ev.message.lower()
    assert "manual" not in ev.message.lower(), (
        "'manual exit' is itself unknowable without an order type")
    assert "held 30min" in ev.message
    assert "% loss" in ev.message


def test_the_mechanism_is_stated_only_when_it_was_actually_observed():
    ev = engine._detect_no_stoploss(_ctx(_ct(), exit_types=["MKT"]))
    assert ev.context["exit_mechanism_observed"] is True
    assert "Exit was a MKT order, not a stop." in ev.message


@pytest.mark.parametrize("order_type", ["SL", "SL-M", "SLM", "SL-MKT"])
def test_a_stop_execution_still_suppresses_the_alert(order_type):
    """The one thing the exit fill CAN establish, and it must keep working."""
    assert engine._detect_no_stoploss(_ctx(_ct(), exit_types=[order_type])) is None


# ── the dead expiry branch ─────────────────────────────────────────────────

def test_weekly_expiry_creates_no_distinction():
    """
    The removed arm read the same thresholds as the normal gate. A weekly-expiry
    trade must now be judged, and labelled, exactly like any other.
    """
    src = inspect.getsource(engine._detect_no_stoploss)
    assert "elif is_expiry:" not in src, "the dead arm is back"
    assert '" (expiry day)"' not in src, "the misleading label is back"
    assert "(expiry day)" not in engine._detect_no_stoploss(_ctx(_ct())).message


def test_no_new_expiry_threshold_was_invented():
    """
    The review said resolve the dead branch, not tune it. The weekly keys are
    left in defaults untouched and simply unread; giving them a value is a
    separate, unapproved decision.
    """
    assert COLD_START_DEFAULTS["no_stoploss_expiry_loss_pct"] == 25
    assert COLD_START_DEFAULTS["no_stoploss_expiry_hold_min"] == 5
    assert COLD_START_DEFAULTS["no_stoploss_loss_pct_caution"] == 25
    assert COLD_START_DEFAULTS["no_stoploss_hold_min"] == 5


def test_the_monthly_branch_is_kept_because_it_is_not_dead():
    """
    20% against the normal 25% is a real difference, so the monthly arm is not
    the same defect. It stays, label and all.
    """
    src = inspect.getsource(engine._detect_no_stoploss)
    assert "no_stoploss_monthly_loss_pct" in src
    assert '" (monthly expiry)"' in src
    assert COLD_START_DEFAULTS["no_stoploss_monthly_loss_pct"] == 20


# ── nothing else moved ─────────────────────────────────────────────────────

@pytest.mark.parametrize("loss_pct,duration,should_fire", [
    (30, 30, True),      # clears both gates
    (24, 30, False),     # under the 25% loss gate
    (30, 4, False),      # under the 5-minute hold gate
    (60, 30, True),      # danger territory
])
def test_the_gates_are_unchanged(loss_pct, duration, should_fire):
    pnl = -(100.0 * 75 * loss_pct / 100)
    ev = engine._detect_no_stoploss(_ctx(_ct(pnl=pnl, duration=duration)))
    assert (ev is not None) is should_fire


def test_severity_ladder_is_unchanged():
    caution = engine._detect_no_stoploss(_ctx(_ct(pnl=-(100 * 75 * 0.30))))
    danger = engine._detect_no_stoploss(_ctx(_ct(pnl=-(100 * 75 * 0.60))))
    assert caution.severity == "caution"
    assert danger.severity == "danger"
    assert COLD_START_DEFAULTS["no_stoploss_loss_pct_danger"] == 50


def test_f4_is_untouched():
    """
    The direction-aware denominator stays on the Pending register. A short
    option is still measured against premium RECEIVED, which is the defect - it
    must not have been silently changed here.
    """
    src = inspect.getsource(engine._detect_no_stoploss)
    assert "capital_at_risk = entry_price * qty" in src, (
        "the CE/PE denominator changed - that is F4 and it is not approved")
    long_ev = engine._detect_no_stoploss(_ctx(_ct(direction="LONG")))
    short_ev = engine._detect_no_stoploss(_ctx(_ct(direction="SHORT")))
    assert long_ev.context["capital_at_risk"] == short_ev.context["capital_at_risk"], (
        "direction still does not enter the denominator, by design, pending F4")


def test_the_registry_copy_no_longer_asserts_absence():
    from app.services.detector_registry import PATTERN_COPY

    copy = PATTERN_COPY["no_stoploss"]
    blob = " ".join(str(x) for x in copy).lower()   # label, observes, explanation
    assert "no stop-loss on record" not in blob
    assert "whether a stop-loss order was on the position" not in blob
