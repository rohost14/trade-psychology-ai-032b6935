"""
`daily_overtrading` fires against the trader's declared daily trade limit.

WHAT CHANGED, 2026-08-26 (Pattern #5)

The line used to be `daily_trade_limit`, which resolves from history as the
trader's own `daily_trades_p75`. Two problems, either fatal on its own:

  * **A p75 line is a quota.** Set a threshold at a trader's 75th percentile and
    it alerts on 25% of their sessions BY CONSTRUCTION — for any trader, forever,
    however they behave. Measured on the reference book: 26%, 52 alerts. A
    trader who halves their trading takes the p75 down with them and is still
    alerted on a quarter of their sessions.

  * **The claim was contradicted.** The copy said a heavy day "becomes
    momentum". Past the line this trader was slower (median gap 4 -> 9 min),
    smaller (median risk Rs 8,044 -> 7,213) and no worse (win rate 44.7% ->
    42.6%, 0.4 SE). Heavy days were 26% of sessions and 2% of the book's loss,
    and the 141 positions past the line made Rs 1,265 net.

What survives is the version that is true by construction: you said you stop at
N, and you are at N. No declaration means no alert — the daily count is still
visible to analytics, which computes it from the trades and never read this
event.

Deliberately NOT here: any replacement default, the `daily_trade_danger` = 12
tier (its own definition file records "no source"), and any change to
`overtrading_burst`, which the review DEFERRED for lack of evidence.
"""

from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.models.completed_trade import CompletedTrade
from app.services.behavior_engine import BehaviorEngine, EngineContext
from tests.helpers import now_utc

engine = BehaviorEngine()

#: Wide enough that the 30-minute burst check cannot fire and confuse a result.
#: Every test here is about the DAILY count.
SPACING_MIN = 45


def _ct(pnl=-100.0, offset_min=-30, symbol="NIFTY25AUGFUT"):
    ct = MagicMock(spec=CompletedTrade)
    ct.id = uuid4()
    ct.broker_account_id = uuid4()
    ct.tradingsymbol = symbol
    ct.exchange = "NFO"
    ct.direction = "LONG"
    ct.instrument_type = "FUT"
    ct.realized_pnl = Decimal(str(pnl))
    ct.total_quantity = 50
    ct.avg_entry_price = Decimal("22000")
    ct.avg_exit_price = Decimal("21990")
    now = now_utc()
    ct.entry_time = now + timedelta(minutes=offset_min)
    ct.exit_time = now + timedelta(minutes=offset_min + 5)
    return ct


def _run(n_positions, thresholds):
    """n_positions total in the session, spaced so no burst can fire."""
    trades = [_ct(offset_min=-(n_positions - i) * SPACING_MIN)
              for i in range(n_positions)]
    ct = trades[-1]
    ctx = EngineContext(
        broker_account_id=ct.broker_account_id,
        session=SimpleNamespace(session_pnl=Decimal("-500"),
                                session_date=None, market_open=None),
        completed_trade=ct,
        session_trades=trades[:-1],
        active_cooldowns=[],
        thresholds=thresholds,
    )
    return engine._detect_overtrading_burst(ctx)


# ── no declared limit → no behavioural alert ───────────────────────────────

@pytest.mark.parametrize("n", [7, 12, 20])
def test_no_declared_limit_produces_no_alert(n):
    """
    The cold-start case, and the common one: nothing is declared, so there is
    no line, so there is nothing to say. Twenty positions in a day is still
    twenty positions — analytics counts them from the trades.
    """
    assert _run(n, {}) is None


def test_a_declared_limit_of_none_is_the_same_as_no_limit():
    """`daily_trade_limit` is nullable on the profile. None must not default."""
    assert _run(12, {"user_daily_trade_limit": None}) is None


def test_the_p75_derived_line_is_no_longer_read():
    """
    Regression on the whole point of the change. `daily_trade_limit` is the
    p75-derived value and is still resolved for other readers (the Rules page,
    /api/risk). It must no longer put an alert in front of the trader.
    """
    ev = _run(12, {"daily_trade_limit": 7, "daily_trade_danger": 12})
    assert ev is None, (
        "the derived p75 line still fires — a threshold at a trader's own p75 "
        "alerts on a quarter of their sessions by construction"
    )


def test_the_derived_line_does_not_win_when_a_declared_one_exists():
    """
    Both keys present and they disagree. The declared number decides; 8 is under
    the declared 10, so nothing fires even though it is past the derived 7.
    """
    assert _run(8, {"user_daily_trade_limit": 10, "daily_trade_limit": 7}) is None


# ── declared limit → alert at that limit ───────────────────────────────────

def test_reaching_the_declared_limit_alerts():
    ev = _run(5, {"user_daily_trade_limit": 5})
    assert ev is not None
    assert ev.event_type == "daily_overtrading"
    assert ev.severity == "caution"
    assert ev.context["declared_limit"] == 5
    assert ev.context["daily_count"] == 5
    assert "your limit is 5" in ev.message


def test_one_below_the_declared_limit_is_silent():
    assert _run(4, {"user_daily_trade_limit": 5}) is None


def test_no_tier_above_the_declared_limit():
    """
    `daily_trade_danger` = 12 was not reimplemented — the file that defines it
    records "no source" and it reached 3 of 189 sessions while deciding a push.
    Fifteen positions against a declared 5 is exactly as loud as five.
    """
    ev = _run(15, {"user_daily_trade_limit": 5, "daily_trade_danger": 12})
    assert ev is not None
    assert ev.severity == "caution", "there is no second tier"


# ── the threshold follows each trader's own number ─────────────────────────

@pytest.mark.parametrize("limit,count,should_fire", [
    (3, 2, False), (3, 3, True),
    (5, 4, False), (5, 5, True),
    (10, 9, False), (10, 10, True),
    (20, 19, False), (20, 20, True),
])
def test_the_line_is_wherever_the_trader_put_it(limit, count, should_fire):
    ev = _run(count, {"user_daily_trade_limit": limit})
    assert (ev is not None) is should_fire, (
        f"limit {limit}, {count} positions: expected "
        f"{'an alert' if should_fire else 'silence'}"
    )
    if ev:
        assert ev.context["declared_limit"] == limit


def test_two_traders_same_day_different_answers():
    """
    The point of the change, stated as one comparison: identical sessions, two
    declared limits, two different answers — because they said different things.
    """
    tight = _run(6, {"user_daily_trade_limit": 5})
    loose = _run(6, {"user_daily_trade_limit": 12})

    assert tight is not None and tight.context["declared_limit"] == 5
    assert loose is None, "6 positions is not past a limit of 12"


def test_a_trader_who_raises_their_limit_hears_less():
    """
    The inverse of the p75 problem. Under the old derivation the line followed
    the trader's behaviour, so it could never be escaped; a declared limit can.
    """
    assert _run(9, {"user_daily_trade_limit": 8}) is not None
    assert _run(9, {"user_daily_trade_limit": 15}) is None


# ── the burst half of this method is untouched ─────────────────────────────

def test_overtrading_burst_still_fires_with_no_declared_limit():
    """
    DEFERRED, not disabled. The burst check runs before the daily one and does
    not read the declared limit at all — six positions inside 30 minutes with no
    profile still produces its own alert.
    """
    trades = [_ct(offset_min=-25 + i * 3) for i in range(6)]
    ct = trades[-1]
    ctx = EngineContext(
        broker_account_id=ct.broker_account_id,
        session=SimpleNamespace(session_pnl=Decimal("-2000"),
                                session_date=None, market_open=None),
        completed_trade=ct, session_trades=trades[:-1],
        active_cooldowns=[], thresholds={},
    )
    ev = engine._detect_overtrading_burst(ctx)
    assert ev is not None
    assert ev.event_type == "overtrading_burst"
    assert ev.context["trades_in_window"] >= 5
