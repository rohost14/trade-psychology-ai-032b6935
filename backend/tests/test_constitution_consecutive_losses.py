"""
The trader's own consecutive-loss rule, under `constitution_violation`.

Since `consecutive_loss_streak` was retired (2026-08-26) this is the only place
a losing run is alerted on. It is judged against the number the trader declared
at onboarding, not one the engine chose — which is the whole reason it survived
the retirement and the count-based detector did not.

The defect these tests pin down: the shared percentage ladder fires `caution` at
80% of a rule, and a streak moves in whole trades. For limits of 2, 3 and 4 the
first integer streak that clears 0.80 IS the limit — so `approaching` was
unreachable and the trader got the breach with no warning. **The onboarding
default is 3**, so this was the common case, not an edge one.
"""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.models.completed_trade import CompletedTrade
from app.services.behavior_engine import BehaviorEngine, EngineContext

engine = BehaviorEngine()


def _ctx(streak: int, limit: int) -> EngineContext:
    ct = MagicMock(spec=CompletedTrade)
    ct.id = uuid4()
    ct.tradingsymbol = "NIFTY25JANFUT"
    ct.instrument_type = "FUT"
    ct.direction = "LONG"
    ct.avg_entry_price = Decimal("22000")
    ct.total_quantity = 50
    ct.entry_time = None
    return EngineContext(
        broker_account_id=uuid4(),
        session=SimpleNamespace(session_pnl=Decimal("0"),
                                session_date=date.today(), market_open=None),
        completed_trade=ct,
        session_trades=[],
        # ONLY the consecutive-loss rule is declared, so nothing else can add an
        # event and the assertions below are about this rule alone.
        thresholds={"max_consecutive_losses": limit},
        facts=SimpleNamespace(consecutive_losses=streak),
    )


def _severity(streak: int, limit: int):
    events = engine._detect_constitution_violation(_ctx(streak, limit)) or []
    mine = [e for e in events
            if e.context.get("rule") == "max_consecutive_losses"]
    assert len(mine) <= 1, "one rule must not produce two events"
    return (mine[0].severity, mine[0].message) if mine else (None, None)


# ── the defect ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("limit", [2, 3, 4])
def test_the_warning_rung_is_reachable_on_small_integer_limits(limit):
    """
    Regression. ceil(0.80 x 3) == 3 and ceil(0.80 x 4) == 4, so the percentage
    ladder alone gave these limits a breach and nothing before it.
    """
    severity, message = _severity(limit - 1, limit)
    assert severity == "caution", (
        f"limit {limit}: a streak of {limit - 1} produced {severity!r} — the "
        f"trader gets no warning before breaking their own rule"
    )
    assert "One more loss" in message


def test_the_onboarding_default_warns_before_it_breaches():
    """The default is 3. Before this fix, every trader on it went 0 → breach."""
    assert _severity(2, 3)[0] == "caution"
    assert _severity(3, 3)[0] == "danger"


# ── the rest of the ladder is untouched ────────────────────────────────────

def test_breach_is_still_the_limit_itself():
    for limit in (2, 3, 4, 5, 8):
        assert _severity(limit, limit)[0] == "danger", limit


def test_severe_is_still_120_percent():
    # 6 / 5 = 1.20
    assert _severity(6, 5)[0] == "critical"


def test_below_the_warning_says_nothing():
    assert _severity(2, 5) == (None, None)
    assert _severity(0, 3) == (None, None)
    assert _severity(1, 3) == (None, None)


def test_a_limit_of_one_has_no_room_for_a_warning():
    """
    Nothing precedes the first loss, so the rule can only ever breach. The
    `limit >= 2` guard exists to stop a streak of 0 reading as "one away".
    """
    assert _severity(0, 1) == (None, None)
    assert _severity(1, 1)[0] == "danger"


def test_the_percentage_ladder_still_wins_where_it_fires_earlier():
    """
    On a limit of 10, 0.80 lands on a streak of 8 — two away, not one. The
    one-away rung is additive and must not pull that warning later.
    """
    assert _severity(8, 10)[0] == "caution"
    assert _severity(9, 10)[0] == "caution"
    assert "One more loss" in _severity(9, 10)[1]
    assert "One more loss" not in _severity(8, 10)[1]


def test_the_message_names_the_traders_own_number():
    for streak, limit in ((2, 3), (3, 3), (4, 3)):
        message = _severity(streak, limit)[1]
        assert "your stop point: 3" in message
        assert str(streak) in message


# ── the retirement itself ──────────────────────────────────────────────────

def test_the_retired_count_detector_is_gone():
    """
    `consecutive_loss_streak` fired on chance: 63 of 189 sessions contained a 3+
    loss run against 63.0 expected from the trader's win rate alone.
    """
    from app.services.detector_registry import BY_NAME, all_pattern_types

    assert not hasattr(engine, "_detect_consecutive_loss_streak")
    assert "consecutive_loss_streak" not in BY_NAME
    assert "consecutive_loss_streak" not in all_pattern_types()
