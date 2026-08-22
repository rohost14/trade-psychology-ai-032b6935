"""
Everything that folds session state must agree with the one definition.

There is no way to test "nobody computes their own version" directly. What can
be tested is that the folds which remain — SessionState's incremental update,
and the feature builder's as-of cutoff — land on the same numbers as
`session_facts.derive`. If a future edit teaches one of them a different rule
about, say, a scratch trade, this is where it surfaces.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.core import session_facts
from app.services.state.session_state import SessionState

BASE = datetime(2026, 8, 21, 4, 0, tzinfo=timezone.utc)


class FakeTrade:
    def __init__(self, pnl, minute):
        self.realized_pnl = Decimal(str(pnl))
        self.exit_time = BASE + timedelta(minutes=minute)
        self.entry_time = self.exit_time - timedelta(minutes=10)
        self.duration_minutes = 10


SEQUENCES = [
    pytest.param([], id="empty"),
    pytest.param([(-1000, 10)], id="single-loss"),
    pytest.param([(1000, 10)], id="single-win"),
    pytest.param([(-1000, 10), (-500, 20), (-800, 30)], id="losing-run"),
    pytest.param([(5000, 10), (-2000, 20)], id="gave-some-back"),
    pytest.param([(5000, 10), (-9000, 20)], id="green-to-red"),
    pytest.param([(-1000, 10), (0, 20), (-500, 30)], id="scratch-between-losses"),
    pytest.param([(-1000, 10), (0, 20)], id="ends-on-scratch"),
    pytest.param([(0, 10), (0, 20)], id="all-scratch"),
    pytest.param([(800, 10), (900, 20), (-100, 30), (400, 40)], id="mixed"),
]


@pytest.mark.parametrize("pairs", SEQUENCES)
def test_session_state_matches_canonical_facts(pairs):
    trades = [FakeTrade(p, m) for p, m in pairs]
    facts = session_facts.derive(trades)
    state = SessionState.rebuild(trades)

    assert state.trade_count == facts.trades
    assert state.session_pnl == facts.pnl
    assert state.peak_pnl == facts.peak_pnl
    assert state.drawdown_from_peak == facts.drawdown_from_peak
    assert state.winners == facts.winners
    assert state.losers == facts.losers
    assert state.consecutive_losses == facts.consecutive_losses, (
        "SessionState and session_facts disagree about what ends a losing streak"
    )
    assert state.consecutive_wins == facts.consecutive_wins


def test_a_scratch_trade_ends_a_losing_run_everywhere():
    """
    The specific disagreement this file was written for: SessionState used to
    treat a flat trade as not breaking the run, while the live detector treated
    it as breaking. Loss, scratch, is a streak of zero.
    """
    trades = [FakeTrade(-1000, 10), FakeTrade(0, 20)]
    assert session_facts.derive(trades).consecutive_losses == 0
    assert SessionState.rebuild(trades).consecutive_losses == 0


@pytest.mark.parametrize("pairs", SEQUENCES)
def test_incremental_update_matches_rebuild(pairs):
    """
    The property that makes caching safe later: folding trade by trade and
    rebuilding from scratch must land in the same place.
    """
    trades = [FakeTrade(p, m) for p, m in pairs]
    incremental = SessionState()
    for t in trades:
        incremental.update(t)
    rebuilt = SessionState.rebuild(trades)

    for field in ("trade_count", "session_pnl", "peak_pnl", "drawdown_from_peak",
                  "winners", "losers", "consecutive_losses", "consecutive_wins"):
        assert getattr(incremental, field) == getattr(rebuilt, field), field
