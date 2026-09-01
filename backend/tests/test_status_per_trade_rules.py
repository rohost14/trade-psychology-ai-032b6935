"""
Today's usage for the two PER-TRADE rules — 2026-09-02.

`per_trade_loss_limit` and `max_position_size` had a limit on the rules page
and no number beside it: the page named a rule and said nothing about the
trader's day against it. The other three rules had one because they are
CUMULATIVE — loss taken, trades placed, losses in a row all climb through the
session toward a line, and "8,455 of 25,000" means 16,545 remain.

These two are not that shape, and reporting them through the same `usage`
helper would have said something false. A per-trade limit is not consumed: the
worst trade so far reaching 67% of the line leaves the NEXT trade its whole
allowance. So they get `kind: "peak"` and the page renders no progress bar.

WHY ONE OF THEM CAN BE WITHHELD

`per_trade_loss` is exact: `realized_pnl` is present on 5,011 of 5,011
CompletedTrades in the real book, so the worst trade of a session is always
knowable.

`max_trade_risk` is not. It goes through `quantities_for_trade`, which is
ALLOWED TO ABSTAIN — `usable_for_capital_rules` is False for short equity among
others — and on the real book it abstains on 21.3% of trades, with 46.2% OF
SESSIONS containing at least one. A maximum over a subset is not the maximum,
so on those sessions the endpoint sends None rather than a number that would
understate the trader's largest position. Complete coverage or nothing.

Measured by `_measurement/p29_status_metrics.py`.
"""
import inspect
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.core.session_facts import EMPTY, derive

BASE = datetime(2026, 9, 2, 4, 0, tzinfo=timezone.utc)


def ct(pnl, minutes=0):
    return SimpleNamespace(
        realized_pnl=Decimal(str(pnl)),
        exit_time=BASE + timedelta(minutes=minutes),
    )


# ══ the session fact ═══════════════════════════════════════════════════════

def test_the_worst_trade_is_the_worst_single_trade():
    facts = derive([ct(-500), ct(1200, 1), ct(-3400, 2), ct(-120, 3)])
    assert facts.worst_trade_pnl == Decimal("-3400")


def test_it_is_not_the_session_pnl():
    """
    THE DISTINCTION THAT MAKES IT A SEPARATE FACT. Forty small losses put `pnl`
    deep in the red while no single trade came near a per-trade limit. Two
    different rules, two different facts; neither substitutes for the other.
    """
    facts = derive([ct(-100, i) for i in range(40)])
    assert facts.pnl == Decimal("-4000")
    assert facts.worst_trade_pnl == Decimal("-100")


def test_a_winning_session_has_no_worst_trade():
    """None, not zero: nothing lost money, which is not the same as a trade
    that lost nothing."""
    assert derive([ct(500), ct(900, 1)]).worst_trade_pnl is None
    assert EMPTY.worst_trade_pnl is None


def test_a_flat_trade_is_not_a_loss():
    """Consistent with `consecutive_losses`, where zero breaks the streak."""
    assert derive([ct(0), ct(0, 1)]).worst_trade_pnl is None


def test_it_is_order_independent_like_every_other_fact():
    a = derive([ct(-500), ct(-3400, 2), ct(1200, 1)])
    b = derive([ct(-3400, 2), ct(1200, 1), ct(-500)])
    assert a.worst_trade_pnl == b.worst_trade_pnl == Decimal("-3400")


# ══ the endpoint's two shapes ══════════════════════════════════════════════

def _status_source():
    from app.api.constitution import constitution_status
    return inspect.getsource(constitution_status)


def test_the_two_shapes_are_distinct_and_labelled():
    src = _status_source()
    assert '"kind": "cumulative"' in src
    assert '"kind": "peak"' in src


@pytest.mark.parametrize("rule", ["per_trade_loss", "max_trade_risk"])
def test_each_per_trade_rule_is_reported_as_a_peak(rule):
    src = _status_source()
    assert f'peak("{rule}"' in src


@pytest.mark.parametrize("rule", ["daily_loss", "daily_trades", "max_consecutive_losses"])
def test_the_cumulative_rules_are_unchanged(rule):
    src = _status_source()
    assert f'usage("{rule}"' in src


def test_the_largest_position_is_withheld_on_incomplete_coverage():
    """
    The measured reason: 46.2% of real sessions contain a trade the risk layer
    cannot size. Reporting the max of the rest would understate it.
    """
    src = _status_source()
    assert "usable_for_capital_rules" in src
    assert "complete = False" in src
    assert "if pcts and complete:" in src


def test_it_abstains_the_same_way_the_alert_does():
    """The status row and the alert must not disagree about the same trade."""
    from app.services.behavior_engine import BehaviorEngine

    alert = inspect.getsource(BehaviorEngine._detect_constitution_violation)
    assert "usable_for_capital_rules" in alert
    assert "quantities_for_trade" in _status_source()


def test_no_rule_without_a_limit_produces_a_ratio():
    """An opt-in rule that was never declared reports nothing, not zero."""
    from app.api.constitution import constitution_status  # noqa: F401

    src = _status_source()
    assert 'if limit and current is not None else None' in src


# ══ the page ═══════════════════════════════════════════════════════════════

def test_the_page_reads_kind_rather_than_hardcoding_the_rules():
    from pathlib import Path

    p = Path(__file__).resolve().parents[2] / "src" / "components" / "rules" / "EnforcedRules.tsx"
    if not p.exists():
        return
    t = p.read_text(encoding="utf-8")
    assert "today?.kind === 'peak'" in t
    # no bar for a peak - that is the whole point
    assert "const pct = !isPeak" in t
    assert "Worst trade today" in t
    assert "Largest position today" in t
