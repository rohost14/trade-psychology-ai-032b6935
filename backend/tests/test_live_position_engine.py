"""
Tests for the live (pre-close) no_stoploss detector.

Pure-function tests on detect_no_stoploss — no DB, no fixtures. The engine's
write path is deliberately untested here; it is a thin wrapper and the thing
worth pinning down is the decision, because a wrong warning mid-position erodes
trust far more than a wrong receipt does.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.services.live_position_engine import (
    GRACE_MINUTES,
    LivePosition,
    detect_no_stoploss,
)

NOW = datetime(2026, 8, 1, 10, 30, tzinfo=timezone.utc)


def position(**kwargs) -> LivePosition:
    defaults = dict(
        position_id=uuid4(),
        tradingsymbol="NIFTY25AUG24000CE",
        quantity=50,
        entry_time=NOW - timedelta(minutes=30),
        has_stoploss_order=False,
        unrealized_pnl=-3200.0,
    )
    defaults.update(kwargs)
    return LivePosition(**defaults)


def test_fires_when_open_without_stoploss_past_grace():
    d = detect_no_stoploss(position(), now=NOW)
    assert d is not None
    assert d.pattern_type == "no_stoploss"
    assert "NIFTY25AUG24000CE" in d.message
    assert d.details["live"] is True


def test_silent_when_a_stoploss_exists():
    assert detect_no_stoploss(position(has_stoploss_order=True), now=NOW) is None


def test_silent_inside_the_grace_window():
    """An SL order often lands seconds after the entry fill. Firing on that race
    would teach the user to distrust the alert on day one."""
    just_opened = position(entry_time=NOW - timedelta(minutes=GRACE_MINUTES - 1))
    assert detect_no_stoploss(just_opened, now=NOW) is None


def test_fires_exactly_at_the_grace_boundary():
    at_boundary = position(entry_time=NOW - timedelta(minutes=GRACE_MINUTES))
    assert detect_no_stoploss(at_boundary, now=NOW) is not None


def test_silent_on_a_flat_position():
    assert detect_no_stoploss(position(quantity=0), now=NOW) is None


def test_severity_follows_exposure_not_opinion():
    losing = detect_no_stoploss(position(unrealized_pnl=-3200.0), now=NOW)
    winning = detect_no_stoploss(position(unrealized_pnl=1800.0), now=NOW)
    assert losing.severity == "danger"
    assert winning.severity == "caution"


def test_losing_message_states_the_exposure_and_winning_does_not():
    losing = detect_no_stoploss(position(unrealized_pnl=-3200.0), now=NOW)
    winning = detect_no_stoploss(position(unrealized_pnl=1800.0), now=NOW)
    assert "3,200" in losing.message
    assert "down" in losing.message
    # A position in profit with no stop is worth noting, not dramatising.
    assert "down" not in winning.message


def test_naive_entry_time_is_treated_as_utc_not_crashed_on():
    """Postback payloads are not consistently tz-aware; a naive datetime must
    not raise on subtraction."""
    naive = position(entry_time=(NOW - timedelta(minutes=30)).replace(tzinfo=None))
    assert detect_no_stoploss(naive, now=NOW) is not None


def test_message_never_instructs():
    """Mirror, not blocker. The alert states the fact; it does not tell the
    trader what to do and must never read as an instruction."""
    d = detect_no_stoploss(position(), now=NOW)
    lowered = d.message.lower()
    for banned in ("should", "must", "don't", "do not", "place a stop", "close it"):
        assert banned not in lowered
