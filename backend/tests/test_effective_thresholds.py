"""
The declared-vs-enforced resolution behind GET /api/constitution/effective.

These pin the behaviour that motivated the endpoint: a declared rule is applied
only when it is more restrictive than the threshold already in force, so the
number a trader typed is not always the number being enforced. That is correct
-- a stale daily_trade_limit of 50 must not silently disable overtrading alerts
-- but it means the rules page has to be able to tell the two apart.
"""

from types import SimpleNamespace

import pytest

from app.core.trading_defaults import get_thresholds


def profile(**kw):
    base = dict(
        trading_style="intraday",
        trading_capital=500000,
        daily_loss_limit=None,
        daily_trade_limit=None,
        max_position_size=None,
        cooldown_after_loss=None,
        max_consecutive_losses=None,
        restricted_windows=[],
        detected_patterns=None,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def test_declared_trade_limit_wins_when_tighter_than_default():
    loose = get_thresholds(profile())["daily_trade_limit"]
    got = get_thresholds(profile(daily_trade_limit=max(1, loose - 2)))["daily_trade_limit"]
    assert got == max(1, loose - 2)


def test_declared_trade_limit_is_NOT_used_when_looser_than_baseline():
    """The case the rules page was misreporting: declare 50, trade 6, get 6."""
    p = profile(
        daily_trade_limit=50,
        detected_patterns={"baseline": {"daily_trade_limit": 6}},
    )
    assert get_thresholds(p)["daily_trade_limit"] <= 6


# `test_cooldown_takes_the_longer_of_declared_and_current` was DELETED
# 2026-09-02 WITH ITS SUBJECT. It asserted that a declared cooldown
# raised the revenge window. `cooldown_after_loss` stopped being a user-configurable rule on 2026-09-02. The engine keeps its own revenge window (`revenge_window_min`, fallback 10); the trader no longer sets it. The window itself is now
# pinned by test_rule_clearing_and_removals::
# test_THE_PROTECTION_SURVIVES_at_its_own_value.


def test_loss_and_capital_limits_pass_through_as_declared():
    """Factual inputs, not behavioural thresholds — never blended."""
    t = get_thresholds(profile(daily_loss_limit=25000, max_position_size=200000))
    assert t["daily_loss_limit"] == 25000
    assert t["max_position_size"] == 200000


def test_unset_rules_leave_a_threshold_in_force():
    """No declared rule does not mean no limit — this is what the rules page
    was implying with 'no rule set', and why ungoverned thresholds are now
    returned alongside."""
    t = get_thresholds(profile())
    assert t["daily_trade_limit"] is not None
    assert t["consecutive_loss_caution"] is not None


def test_engine_enforces_thresholds_no_rule_can_set():
    t = get_thresholds(profile())
    for key in ("burst_trades_per_30min_caution", "consecutive_loss_danger"):
        assert t.get(key) is not None, f"{key} should always resolve"
