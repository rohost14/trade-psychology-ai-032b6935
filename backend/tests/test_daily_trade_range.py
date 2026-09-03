"""
The daily trade rule is a RANGE the trader declared, and the maximum is not a
breach.

TWO DEFECTS THIS PINS

1. OFF BY ONE. Both the detector and the constitution rule treated the declared
   number as breached when it was REACHED — `daily_count >= limit` and
   `ratio >= 1.0`. A trader who declared 5 was told they had exceeded their
   limit on their fifth trade, the last one their own rule allows. Reaching a
   maximum is not exceeding it.

2. ONE NUMBER FOR A RANGE. Onboarding asked for "Max Trades Per Day" on a
   slider. What a trader has in mind is a band — three to five on a normal day
   — and only the top of it can be breached.

There is NO tolerance around the declared maximum. If the trader says 3–5 then
5 is inside the rule and 6 is a breach. The range is what they intended, not a
statistical interval to be widened by some margin.

AND TWO DIFFERENT CLAIMS, kept apart:
  "You exceeded your daily limit"  — a fact about one day, needs no history.
  "Repeatedly exceeding ... may indicate overtrading" — a habit claim, only
  defensible once there is repetition to point at.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from pytz import timezone as _tz

from app.models.completed_trade import CompletedTrade
from app.models.trading_session import TradingSession
from app.services.behavior_engine import BehaviorEngine, EngineContext
from app.services.entry_checks import (
    REPEATED_BREACH_DAYS,
    REPEATED_BREACH_WINDOW,
    breach_days_in_window,
    is_repeated_breach,
)

IST = _tz("Asia/Kolkata")
engine = BehaviorEngine()
TODAY = date.today()
MID = IST.localize(datetime.combine(TODAY, time(10, 0))).astimezone(timezone.utc)
BROKER = uuid4()


def _ct(symbol, *, opened, pnl=-100.0):
    ct = MagicMock(spec=CompletedTrade)
    ct.id = uuid4()
    ct.broker_account_id = BROKER
    ct.tradingsymbol = symbol
    ct.exchange = "NFO"
    ct.direction = "LONG"
    ct.instrument_type = "FUT"
    ct.realized_pnl = Decimal(str(pnl))
    ct.total_quantity = 50
    ct.avg_entry_price = Decimal("22000")
    ct.avg_exit_price = Decimal("21900")
    ct.entry_time = opened
    ct.exit_time = MID + timedelta(hours=3)
    return ct


def _session():
    s = MagicMock(spec=TradingSession)
    s.id = uuid4()
    s.session_date = TODAY
    s.session_pnl = Decimal("0")
    s.risk_score = Decimal("0")
    s.peak_risk_score = Decimal("0")
    s.market_open = None
    return s


def _fire(n_structures: int, declared_max: int):
    """n distinct single-leg positions opened today, against a declared max."""
    # 40 minutes apart so the BURST arm (5+ in 30 min) cannot fire first and
    # mask the daily arm - the two share one detector and burst returns early.
    trades = [
        _ct(f"NIFTY25SEP{i}FUT", opened=MID + timedelta(minutes=40 * i))
        for i in range(n_structures)
    ]
    ctx = EngineContext(
        broker_account_id=BROKER,
        session=_session(),
        completed_trade=trades[-1],
        session_trades=trades[:-1],
        thresholds={"user_daily_trade_limit": declared_max, "trading_capital": 500_000},
    )
    ev = engine._detect_overtrading_burst(ctx)
    if ev is None or getattr(ev, "event_type", None) != "daily_overtrading":
        return None
    return ev


# ── the maximum is not a breach ────────────────────────────────────────────

def test_below_the_maximum_is_silent():
    assert _fire(4, declared_max=5) is None


def test_exactly_the_maximum_is_not_a_breach():
    """
    The defect. Declaring 5 and taking 5 is compliance, not a breach — it is
    the last trade the trader's own rule permits.
    """
    assert _fire(5, declared_max=5) is None


def test_one_above_the_maximum_is_a_breach():
    ev = _fire(6, declared_max=5)
    assert ev is not None
    assert ev.context["daily_count"] == 6
    assert ev.context["declared_limit"] == 5


def test_there_is_no_tolerance_band_around_the_declared_number():
    """
    Not `limit + 3`, not `limit * 1.2`. The first count above the declared
    maximum is the breach, at every limit.
    """
    for limit in (1, 2, 3, 5, 8):
        assert _fire(limit, declared_max=limit) is None, f"limit {limit} fired AT the max"
        assert _fire(limit + 1, declared_max=limit) is not None, f"limit {limit} missed +1"


def test_the_message_states_the_fact_not_an_interpretation():
    ev = _fire(7, declared_max=5)
    assert ev is not None
    msg = ev.message.lower()
    assert "opened today" in msg
    assert "maximum" in msg
    # A single day is not evidence of a habit, so it must not claim one.
    for banned in ("overtrading", "pattern", "repeatedly", "habit"):
        assert banned not in msg, f"single-day breach claims a habit: {ev.message!r}"


def test_no_declared_maximum_means_no_alert():
    trades = [
        _ct(f"NIFTY25SEP{i}FUT", opened=MID + timedelta(minutes=40 * i)) for i in range(9)
    ]
    ctx = EngineContext(
        broker_account_id=BROKER, session=_session(),
        completed_trade=trades[-1], session_trades=trades[:-1],
        thresholds={"trading_capital": 500_000},
    )
    ev = engine._detect_overtrading_burst(ctx)
    assert ev is None or ev.event_type != "daily_overtrading"


# ── repeated breach: the habit claim ───────────────────────────────────────

def _days(*offsets):
    return [TODAY - timedelta(days=o) for o in offsets]


def test_a_single_breach_is_not_a_pattern():
    active = _days(0, 1, 2, 3, 4)
    assert is_repeated_breach(_days(0), active) is False


def test_enough_breaches_in_the_window_is_a_pattern():
    active = _days(0, 1, 2, 3, 4)
    assert is_repeated_breach(_days(0, 1, 2), active) is True


def test_the_window_is_over_ACTIVE_days_not_calendar_days():
    """
    A trader who trades twice a month is judged on their own last five
    sessions. Calendar windows would dilute a real habit into nothing.
    """
    active = _days(0, 30, 60, 90, 120)
    assert is_repeated_breach(_days(0, 30, 60), active) is True


def test_old_breaches_fall_out_of_the_window():
    active = _days(0, 1, 2, 3, 4, 5, 6, 7)
    # three breaches, all older than the last five active days
    assert is_repeated_breach(_days(5, 6, 7), active) is False


def test_not_enough_history_is_not_a_pattern():
    """
    Three breaches in a trader's first three sessions is true and useless:
    there is no normal for it to depart from yet.
    """
    active = _days(0, 1, 2)
    assert is_repeated_breach(_days(0, 1, 2), active) is False


def test_breach_count_reports_the_window_it_used():
    active = _days(0, 1, 2, 3, 4, 5)
    hits, size = breach_days_in_window(_days(0, 2, 5), active)
    assert size == REPEATED_BREACH_WINDOW
    # day 5 is outside the last five active days
    assert hits == 2


def test_no_activity_is_not_a_pattern():
    assert breach_days_in_window([], []) == (0, 0)
    assert is_repeated_breach([], []) is False


def test_the_threshold_is_a_declared_product_decision():
    """
    Pinned so it cannot drift into looking like a measured constant. There is
    no evidence base for these numbers and the comment beside them says so.
    """
    assert (REPEATED_BREACH_DAYS, REPEATED_BREACH_WINDOW) == (3, 5)


# ── the observation is actually wired to a surface ─────────────────────────
#
# `is_repeated_breach` was implemented and unit-tested but nothing rendered it,
# so the habit observation could never reach a trader. These drive the real
# service method that builds the insights array `InsightsTab` renders.

class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def __iter__(self):
        return iter(self._rows)


class _FakeDB:
    """Answers the two queries the insight makes, in the order it makes them."""

    def __init__(self, breach_dates, active_dates):
        self._queue = [
            [(IST.localize(datetime.combine(d, time(11, 0))),) for d in breach_dates],
            [(IST.localize(datetime.combine(d, time(15, 0))),) for d in active_dates],
        ]

    async def execute(self, *_a, **_k):
        return _FakeResult(self._queue.pop(0))


async def _insight(breach_dates, active_dates, declared_max=5):
    from app.services.ai_personalization_service import ai_personalization_service

    profile = MagicMock()
    profile.daily_trade_limit = declared_max
    return await ai_personalization_service._repeated_limit_breach_insight(
        BROKER, _FakeDB(breach_dates, active_dates), profile
    )


@pytest.mark.asyncio
async def test_the_observation_reaches_the_insights_surface():
    ins = await _insight(_days(0, 1, 2), _days(0, 1, 2, 3, 4))
    assert ins is not None, "repeated breach never reaches a trader"
    assert ins["type"] == "repeated_daily_limit_breach"
    # the fields InsightsTab actually renders
    for field in ("icon", "title", "value", "detail", "recommendation"):
        assert ins[field], f"{field} is empty — the card would render blank"
    assert "3 of your last 5 trading days" in ins["detail"]
    assert "self-set daily trading limit" in ins["detail"]


@pytest.mark.asyncio
async def test_the_observation_says_nothing_about_populations_or_motive():
    ins = await _insight(_days(0, 1, 2), _days(0, 1, 2, 3, 4))
    blob = " ".join(str(v) for v in ins.values()).lower()
    for banned in ("most traders", "average trader", "research", "typically",
                   "emotional", "tilt", "revenge", "impulsive", "discipline"):
        assert banned not in blob, f"observation claims {banned!r}: {blob}"


@pytest.mark.asyncio
async def test_it_does_not_fire_on_a_single_breach():
    assert await _insight(_days(0), _days(0, 1, 2, 3, 4)) is None


@pytest.mark.asyncio
async def test_it_does_not_fire_below_the_declared_line():
    """Two breaches in five active days is not the 3-in-5 product decision."""
    assert await _insight(_days(0, 1), _days(0, 1, 2, 3, 4)) is None


@pytest.mark.asyncio
async def test_it_does_not_fire_before_there_is_enough_history():
    """Three breaches in three sessions is a trader's whole record, not a habit."""
    assert await _insight(_days(0, 1, 2), _days(0, 1, 2)) is None


@pytest.mark.asyncio
async def test_no_declared_maximum_means_no_observation():
    assert await _insight(_days(0, 1, 2), _days(0, 1, 2, 3, 4), declared_max=None) is None


@pytest.mark.asyncio
async def test_get_personalized_insights_includes_the_observation():
    """
    The wiring itself, end to end through the public method the API calls.

    The helper passing its own unit tests proves nothing about whether anything
    renders it — that was exactly the gap: `is_repeated_breach` was implemented
    and tested while no surface read it. This substitutes the helper and asserts
    its result reaches the `insights` array that `InsightsTab` renders.
    """
    from app.services import ai_personalization_service as mod

    svc = mod.ai_personalization_service
    sentinel = {
        "type": "repeated_daily_limit_breach", "icon": "📊",
        "title": "Repeated limit breaches", "value": "3 of last 5 days",
        "detail": "sentinel detail", "recommendation": "sentinel recommendation",
    }

    profile = MagicMock()
    profile.daily_trade_limit = 5
    profile.detected_patterns = {
        "symbol_patterns": {}, "intervention_timing": {},
        "predictive_windows": {}, "trades_analyzed": 100,
    }

    class _Res:
        def scalar_one_or_none(self):
            return profile

    class _DB:
        async def execute(self, *_a, **_k):
            return _Res()

    original = svc._repeated_limit_breach_insight

    async def _stub(*_a, **_k):
        return sentinel

    svc._repeated_limit_breach_insight = _stub
    try:
        out = await svc.get_personalized_insights(BROKER, _DB())
    finally:
        svc._repeated_limit_breach_insight = original

    assert out.get("has_data") is True, out
    types = [i["type"] for i in out["insights"]]
    assert "repeated_daily_limit_breach" in types, (
        f"the observation is not wired into the insights array: {types}"
    )
