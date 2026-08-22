"""
The canonical session-fact definitions, pinned.

These tests are the specification. If one of them has to change, a definition
changed, and every consumer of that fact changed with it — which is the whole
point of there being one definition to change.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.core.session_facts import EMPTY, as_of, derive, in_exit_order

BASE = datetime(2026, 8, 21, 4, 0, tzinfo=timezone.utc)  # 09:30 IST, a Friday


class FakeTrade:
    """Only the two fields the definitions read. Keeps the spec readable."""

    def __init__(self, pnl, minute):
        self.realized_pnl = Decimal(str(pnl))
        self.exit_time = BASE + timedelta(minutes=minute)


def _trades(*pairs):
    return [FakeTrade(pnl, minute) for pnl, minute in pairs]


def test_empty_session_is_all_zeros_not_none():
    f = derive([])
    assert f == EMPTY
    assert f.trades == 0 and f.pnl == 0 and f.consecutive_losses == 0
    assert f.is_empty


def test_pnl_is_the_raw_sum():
    f = derive(_trades((-2000, 10), (-1500, 20), (3000, 30)))
    assert f.pnl == Decimal("-500")
    assert f.trades == 3


def test_streak_counts_back_from_the_most_recent_close():
    f = derive(_trades((5000, 10), (-1000, 20), (-800, 30), (-1200, 40)))
    assert f.consecutive_losses == 3
    assert f.consecutive_wins == 0


def test_a_win_breaks_the_streak():
    f = derive(_trades((-1000, 10), (-800, 20), (500, 30)))
    assert f.consecutive_losses == 0
    assert f.consecutive_wins == 1


def test_a_flat_trade_breaks_the_streak():
    """
    Zero is not a loss. Stated as a test because it is the kind of boundary that
    gets decided differently by four authors and noticed by none.
    """
    f = derive(_trades((-1000, 10), (0, 20)))
    assert f.consecutive_losses == 0
    assert f.losers == 1


def test_peak_is_the_running_maximum():
    # +5000, then -2000 → cumulative 5000 then 3000. Peak stays 5000.
    f = derive(_trades((5000, 10), (-2000, 20)))
    assert f.peak_pnl == Decimal("5000")
    assert f.pnl == Decimal("3000")
    assert f.drawdown_from_peak == Decimal("2000")


def test_a_session_that_never_went_green_has_a_peak_of_zero():
    f = derive(_trades((-1000, 10), (-2000, 20)))
    assert f.peak_pnl == Decimal("0")
    assert f.pnl == Decimal("-3000")
    assert f.drawdown_from_peak == Decimal("3000"), (
        "drawdown from a zero peak is the whole loss"
    )


def test_drawdown_is_never_negative():
    f = derive(_trades((1000, 10), (2000, 20)))
    assert f.drawdown_from_peak == Decimal("0")


def test_order_does_not_matter_because_it_sorts_first():
    """
    A replay can hand these over out of order. The streak must not depend on the
    order they arrived in.
    """
    forward = derive(_trades((5000, 10), (-1000, 20), (-800, 30)))
    shuffled = derive(_trades((-800, 30), (5000, 10), (-1000, 20)))
    assert forward == shuffled
    assert shuffled.consecutive_losses == 2


def test_derive_is_idempotent():
    ts = _trades((-2000, 10), (1000, 20))
    assert derive(ts) == derive(ts)


def test_as_of_sees_only_trades_already_closed():
    ts = _trades((-1000, 10), (-2000, 20), (8000, 30))
    at_25 = as_of(ts, BASE + timedelta(minutes=25))
    assert at_25.trades == 2
    assert at_25.consecutive_losses == 2
    assert at_25.pnl == Decimal("-3000")

    at_end = as_of(ts, BASE + timedelta(minutes=99))
    assert at_end.trades == 3
    assert at_end.consecutive_losses == 0


def test_as_of_excludes_a_trade_closing_exactly_at_the_moment():
    """
    Strictly before. A trade closing at the same instant a new one opens has not
    informed the decision to open it.
    """
    ts = _trades((-1000, 10))
    assert as_of(ts, BASE + timedelta(minutes=10)).trades == 0


def test_winners_and_losers_exclude_flat_trades():
    f = derive(_trades((100, 10), (0, 20), (-100, 30)))
    assert (f.winners, f.losers, f.trades) == (1, 1, 3)


def test_last_trade_is_the_last_by_close_not_by_position():
    f = derive(_trades((-500, 30), (900, 10)))
    assert f.last_trade_pnl == Decimal("-500")


def test_missing_exit_time_sorts_first_rather_than_crashing():
    """
    Nulls exist in this table. Sorting must not raise, and an untimed trade must
    not be treated as the most recent one.
    """
    t = FakeTrade(-9999, 0)
    t.exit_time = None
    ordered = in_exit_order([FakeTrade(100, 10), t])
    assert ordered[0] is t
    assert derive([FakeTrade(100, 10), t]).last_trade_pnl == Decimal("100")


def test_none_pnl_counts_as_flat_not_as_a_loss():
    t = FakeTrade(0, 10)
    t.realized_pnl = None
    f = derive([t])
    assert f.pnl == Decimal("0")
    assert f.consecutive_losses == 0


def test_max_drawdown_is_not_the_same_as_drawdown_from_peak():
    """
    The distinction the baseline needs. Up 20k, down to 0, back to 20k: the
    trader ENDS at no drawdown, but they lived through a 20k one.
    """
    f = derive(_trades((20000, 10), (-20000, 20), (20000, 30)))
    assert f.drawdown_from_peak == Decimal("0")
    assert f.max_drawdown == Decimal("20000")


def test_longest_loss_run_is_not_the_trailing_run():
    # four losses, then a win: the run in progress is 0, the longest was 4.
    f = derive(_trades((-1, 10), (-1, 20), (-1, 30), (-1, 40), (5, 50)))
    assert f.consecutive_losses == 0
    assert f.longest_loss_run == 4


def test_longest_loss_run_includes_a_run_still_going():
    f = derive(_trades((-1, 10), (-1, 20), (5, 30), (-1, 40), (-1, 50), (-1, 60)))
    assert f.consecutive_losses == 3
    assert f.longest_loss_run == 3


def test_max_drawdown_on_a_session_that_never_went_green():
    f = derive(_trades((-1000, 10), (-2000, 20)))
    assert f.max_drawdown == Decimal("3000")
