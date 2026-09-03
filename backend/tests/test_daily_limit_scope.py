"""
The daily trade limit counts positions OPENED today.

THE BUG THIS EXISTS TO PREVENT (F14)

`daily_overtrading`'s copy has always said "positions opened today against the
daily trade limit you declared". The count did not match it. `session_trades`
is loaded on an EXIT bound, so the detector counted rounds that CLOSED today —
including ones opened days earlier.

A trader holding five NRML positions overnight, who opens nothing at all the
next morning and simply closes them, was told:

    "5 positions today — your limit is 5"

They took no decisions that day. Nothing unusual is required to reach this, only
an overnight book.

Filtering on entry_time can only UNDER-count: a position opened today and still
open has no CompletedTrade row yet. That direction is safe and is already
covered where it matters — `entry_checks.count_entries_today` counts opening
ledger rows at the moment the decision is made. This exit-time check is the
restatement at the close, and a restatement must not overclaim.

Structure counting (2026-09-02) is preserved and applied AFTER the filter: a
four-leg condor opened today is one decision, not four.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from pytz import timezone as _tz

IST = _tz("Asia/Kolkata")

from app.models.completed_trade import CompletedTrade
from app.models.trading_session import TradingSession
from app.services.behavior_engine import BehaviorEngine, EngineContext

engine = BehaviorEngine()
TODAY = date.today()
# Mid-session instant on today's date, in UTC. The filter compares IST
# calendar days, so any within-day instant works.
OPEN_UTC = IST.localize(datetime.combine(TODAY, time(10, 0))).astimezone(timezone.utc)


def _ct(symbol="NIFTY25SEPFUT", *, opened, pnl=-500.0, qty=50,
        direction="LONG", itype="FUT"):
    ct = MagicMock(spec=CompletedTrade)
    ct.id = uuid4()
    ct.broker_account_id = BROKER
    ct.tradingsymbol = symbol
    ct.exchange = "NFO"
    ct.direction = direction
    ct.instrument_type = itype
    ct.realized_pnl = Decimal(str(pnl))
    ct.total_quantity = qty
    ct.avg_entry_price = Decimal("22000")
    ct.avg_exit_price = Decimal("21900")
    ct.entry_time = opened
    # Everything here closed during today's session; only entry varies.
    ct.exit_time = OPEN_UTC + timedelta(hours=3)
    return ct


BROKER = uuid4()


def _session():
    s = MagicMock(spec=TradingSession)
    s.id = uuid4()
    s.session_date = TODAY
    s.session_pnl = Decimal("0")
    s.risk_score = Decimal("0")
    s.peak_risk_score = Decimal("0")
    s.market_open = None
    return s


def _ctx(trades, declared_limit=2):
    return EngineContext(
        broker_account_id=BROKER,
        session=_session(),
        completed_trade=trades[-1],
        session_trades=trades[:-1],
        thresholds={
            "user_daily_trade_limit": declared_limit,
            "trading_capital": 500_000,
        },
    )


def _fire(trades, declared_limit=2):
    """The daily arm of the overtrading detector, or None."""
    ev = engine._detect_overtrading_burst(_ctx(trades, declared_limit))
    if ev is None or getattr(ev, "event_type", None) != "daily_overtrading":
        return None
    return ev



# NOTE on the declared limit used below. The breach point is `count > maximum`
# (see tests/test_daily_trade_range.py): reaching the declared maximum is
# compliance, exceeding it is the breach. These tests are about WHICH trades are
# counted - opened today versus closed today - so they declare a maximum of 2
# and open 3, which breaches under the correct semantics. Every scoping
# assertion below is unchanged.

# ── the defect ─────────────────────────────────────────────────────────────

def test_positions_opened_yesterday_and_closed_today_do_not_count():
    """The overnight book. Five closes, zero decisions taken today."""
    yesterday = OPEN_UTC - timedelta(days=1)
    trades = [_ct(f"NIFTY25SEP{i}FUT", opened=yesterday) for i in range(5)]
    assert _fire(trades, declared_limit=2) is None


def test_positions_opened_today_do_count():
    trades = [
        _ct(f"NIFTY25SEP{i}FUT", opened=OPEN_UTC + timedelta(minutes=10 * i))
        for i in range(3)
    ]
    ev = _fire(trades, declared_limit=2)
    assert ev is not None
    assert ev.context["daily_count"] == 3


def test_a_mixed_book_counts_only_todays_opens():
    yesterday = OPEN_UTC - timedelta(days=1)
    trades = [
        _ct("NIFTY25SEP1FUT", opened=yesterday),
        _ct("NIFTY25SEP2FUT", opened=yesterday),
        _ct("NIFTY25SEP3FUT", opened=OPEN_UTC + timedelta(minutes=5)),
        _ct("NIFTY25SEP4FUT", opened=OPEN_UTC + timedelta(minutes=15)),
    ]
    # Two opened today, limit 3 — must not fire on a count of four.
    assert _fire(trades, declared_limit=2) is None

    trades.append(_ct("NIFTY25SEP5FUT", opened=OPEN_UTC + timedelta(minutes=25)))
    ev = _fire(trades, declared_limit=2)
    assert ev is not None
    assert ev.context["daily_count"] == 3


# ── session boundary ───────────────────────────────────────────────────────

#: IST midnight — the first instant that belongs to today's session day.
MIDNIGHT_IST = IST.localize(datetime.combine(TODAY, time(0, 0))).astimezone(timezone.utc)


def test_a_trade_opened_at_the_first_instant_of_the_session_day_counts():
    """The bound is the IST calendar day, and it is inclusive."""
    trades = [
        _ct("NIFTY25SEP1FUT", opened=MIDNIGHT_IST),
        _ct("NIFTY25SEP2FUT", opened=OPEN_UTC + timedelta(minutes=1)),
        _ct("NIFTY25SEP3FUT", opened=OPEN_UTC + timedelta(minutes=2)),
    ]
    ev = _fire(trades, declared_limit=2)
    assert ev is not None
    assert ev.context["daily_count"] == 3


def test_a_trade_opened_one_second_before_the_session_day_does_not_count():
    """
    One second earlier is the previous IST day, so it is an overnight round.
    This is the boundary the filter is actually drawn on: the day, not market
    open. A market-open bound would additionally drop anything timestamped
    before 09:15 for any reason and silently silence a live alert.
    """
    trades = [
        _ct("NIFTY25SEP1FUT", opened=MIDNIGHT_IST - timedelta(seconds=1)),
        _ct("NIFTY25SEP2FUT", opened=OPEN_UTC + timedelta(minutes=1)),
        _ct("NIFTY25SEP3FUT", opened=OPEN_UTC + timedelta(minutes=2)),
    ]
    assert _fire(trades, declared_limit=2) is None


def test_a_trade_opened_before_market_open_still_counts():
    """
    The filter must not double as a market-hours check. A round timestamped
    08:00 IST on the session day is unusual, but it is not an overnight
    position and must not be silently dropped.
    """
    early = IST.localize(datetime.combine(TODAY, time(8, 0))).astimezone(timezone.utc)
    trades = [
        _ct("NIFTY25SEP1FUT", opened=early),
        _ct("NIFTY25SEP2FUT", opened=OPEN_UTC + timedelta(minutes=1)),
        _ct("NIFTY25SEP3FUT", opened=OPEN_UTC + timedelta(minutes=2)),
    ]
    ev = _fire(trades, declared_limit=2)
    assert ev is not None
    assert ev.context["daily_count"] == 3


def test_a_trade_with_no_entry_time_is_counted_not_dropped():
    """Cannot tell, so do not silence — the pre-fix behaviour is preserved."""
    trades = [
        _ct("NIFTY25SEP1FUT", opened=None),
        _ct("NIFTY25SEP2FUT", opened=OPEN_UTC + timedelta(minutes=1)),
        _ct("NIFTY25SEP3FUT", opened=OPEN_UTC + timedelta(minutes=2)),
    ]
    ev = _fire(trades, declared_limit=2)
    assert ev is not None
    assert ev.context["daily_count"] == 3


# ── structure counting survives the filter ─────────────────────────────────

def test_a_multi_leg_structure_opened_today_is_one_decision():
    """
    Four legs of one condor, opened together. Counting legs would put a spread
    trader over a limit of 3 on their first position.
    """
    t0 = OPEN_UTC + timedelta(minutes=10)
    legs = [
        _ct("NIFTY25SEP23800PE", opened=t0, direction="LONG", itype="PE"),
        _ct("NIFTY25SEP23900PE", opened=t0, direction="SHORT", itype="PE"),
        _ct("NIFTY25SEP24100CE", opened=t0, direction="SHORT", itype="CE"),
        _ct("NIFTY25SEP24200CE", opened=t0, direction="LONG", itype="CE"),
    ]
    ev = _fire(legs, declared_limit=2)
    assert ev is None, "a single four-leg structure is one decision, not four"


def test_legs_are_still_reported_alongside_the_structure_count():
    t0 = OPEN_UTC + timedelta(minutes=10)
    singles = [
        _ct(f"NIFTY25SEP{i}FUT", opened=OPEN_UTC + timedelta(minutes=30 + 10 * i))
        for i in range(3)
    ]
    legs = [
        _ct("NIFTY25SEP23800PE", opened=t0, direction="LONG", itype="PE"),
        _ct("NIFTY25SEP23900PE", opened=t0, direction="SHORT", itype="PE"),
    ]
    ev = _fire(legs + singles, declared_limit=2)
    assert ev is not None
    assert ev.context["daily_legs"] == 5
    assert ev.context["daily_count"] < ev.context["daily_legs"]


# ── the message and the evidence must agree with the count ─────────────────

def test_the_message_says_opened_and_the_evidence_list_matches_the_count():
    yesterday = OPEN_UTC - timedelta(days=1)
    trades = [
        _ct("NIFTY25SEP0FUT", opened=yesterday),
        _ct("NIFTY25SEP1FUT", opened=OPEN_UTC + timedelta(minutes=5)),
        _ct("NIFTY25SEP2FUT", opened=OPEN_UTC + timedelta(minutes=15)),
        _ct("NIFTY25SEP3FUT", opened=OPEN_UTC + timedelta(minutes=25)),
    ]
    ev = _fire(trades, declared_limit=2)
    assert ev is not None
    assert "opened today" in ev.message
    assert ev.context["daily_count"] == 3
    # The yesterday round must not appear in the evidence the trader is shown.
    assert len(ev.context["daily_trades"]) == 3


def test_realised_pnl_stays_scoped_to_what_closed_today():
    """
    Deliberate asymmetry: how many decisions were OPENED is a different
    question from what P&L was REALISED. The overnight round contributes to the
    second and not the first.
    """
    yesterday = OPEN_UTC - timedelta(days=1)
    trades = [
        _ct("NIFTY25SEP0FUT", opened=yesterday, pnl=-9_000.0),
        _ct("NIFTY25SEP1FUT", opened=OPEN_UTC + timedelta(minutes=5), pnl=-100.0),
        _ct("NIFTY25SEP2FUT", opened=OPEN_UTC + timedelta(minutes=15), pnl=-100.0),
        _ct("NIFTY25SEP3FUT", opened=OPEN_UTC + timedelta(minutes=25), pnl=-100.0),
    ]
    ev = _fire(trades, declared_limit=2)
    assert ev is not None
    assert ev.context["daily_count"] == 3
    assert ev.context["losing_count"] == 4
    assert ev.context["total_loss_today"] == pytest.approx(-9_300.0)


def test_no_declared_limit_means_no_alert():
    """Unchanged: money and count rules are opt-in."""
    trades = [
        _ct(f"NIFTY25SEP{i}FUT", opened=OPEN_UTC + timedelta(minutes=10 * i))
        for i in range(9)
    ]
    ctx = EngineContext(
        broker_account_id=BROKER,
        session=_session(),
        completed_trade=trades[-1],
        session_trades=trades[:-1],
        thresholds={"trading_capital": 500_000},
    )
    ev = engine._detect_overtrading_burst(ctx)
    assert ev is None or ev.event_type != "daily_overtrading"
