"""
The giveback survives `profit_giveaway`'s retirement as a reported fact.

`profit_giveaway` was retired as a behavioural detector on 2026-08-27: a
drawdown from the session high-water mark is arithmetic, not behaviour. 181 of
189 sessions contain one, and shuffling each session's trade order reproduced
the money given back to within 1% (Rs 624,839 actual against Rs 616,891
shuffled) while producing MORE firings than the real order.

None of that makes the number uninteresting after the close. "You were up
Rs 8,000 and finished at Rs 1,200" is a true and useful sentence for a post-market
report; it is only a bad basis for interrupting a session.

`_generate_emotional_journey` already computed peak, trough and final and the
frontend rendered none of them. These tests pin the three derived fields that
were added with the retirement, and the arithmetic they rest on. No threshold is
involved anywhere here.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.services.daily_reports_service import daily_reports_service as svc


def _pos(pnl, minute, symbol="NIFTY25AUGFUT"):
    at = datetime(2026, 8, 27, 4, 0, tzinfo=timezone.utc) + timedelta(minutes=minute)
    return SimpleNamespace(
        realized_pnl=pnl, pnl=pnl,
        first_entry_time=at, last_exit_time=at + timedelta(minutes=5),
        tradingsymbol=symbol, holding_duration_minutes=5,
    )


def _journey(pnls):
    return svc._generate_emotional_journey(
        [_pos(p, 30 + i * 20) for i, p in enumerate(pnls)]
    )


def test_a_session_that_built_and_gave_back_reports_both():
    j = _journey([8000, -6800])
    assert j["peak_pnl"] == 8000
    assert j["final_pnl"] == 1200
    assert j["given_back"] == 6800
    assert j["given_back_pct"] == 85.0
    assert j["finished_green"] is True


def test_a_session_that_kept_everything_gave_nothing_back():
    j = _journey([3000, 2000])
    assert j["peak_pnl"] == 5000
    assert j["given_back"] == 0
    assert j["given_back_pct"] == 0.0
    assert j["finished_green"] is True


def test_green_to_red_is_reported_as_red():
    j = _journey([2000, -5000])
    assert j["peak_pnl"] == 2000
    assert j["final_pnl"] == -3000
    assert j["given_back"] == 5000, "the giveback runs past the peak into loss"
    assert j["finished_green"] is False


def test_a_session_that_never_went_green_has_no_percentage():
    """
    There are no gains to take a percentage of. Reporting 0% or 100% here would
    both be inventions; None says the question does not apply.
    """
    j = _journey([-1000, -2000])
    assert j["peak_pnl"] <= 0
    assert j["given_back_pct"] is None
    assert j["finished_green"] is False


def test_given_back_is_never_negative():
    """final above peak is impossible, but the floor is cheap and explicit."""
    for pnls in ([500], [1000, 500], [-100, 4000], [7000, -1000, 3000]):
        assert _journey(pnls)["given_back"] >= 0


def test_no_positions_is_not_a_crash():
    j = svc._generate_emotional_journey([])
    assert j["timeline"] == []


def test_peak_trough_and_final_are_still_reported():
    """The three fields that already existed must not have moved."""
    j = _journey([4000, -6000, 3000])
    assert j["peak_pnl"] == 4000
    assert j["trough_pnl"] == -2000
    assert j["final_pnl"] == 1000


def test_the_detector_is_still_gone():
    """This file exists because the alert does not."""
    from app.services.behavior_engine import BehaviorEngine
    from app.services.detector_registry import BY_NAME, all_pattern_types

    assert not hasattr(BehaviorEngine(), "_detect_profit_giveaway")
    assert "profit_giveaway" not in BY_NAME
    assert "profit_giveaway" not in all_pattern_types()
