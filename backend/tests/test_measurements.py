"""
The denominators, and what happens when one of them is unavailable.

The cold-start question this settles: does a brand-new user with no account data
get any safety protection at all? Yes — because only ONE of the three
measurement families needs an account size. The other two work on trade #1.
"""
from decimal import Decimal

import pytest

from app.core.account_risk import ABSTAIN, AccountRisk, DenominatorSource, Quality
from app.core.measurements import (
    UNMEASURABLE,
    dispersion,
    gap_vs_own_gaps,
    loss_vs_account,
    loss_vs_own_losses,
    loss_vs_trade,
    size_vs_own_sizes,
)

ACCOUNT_50K = AccountRisk(Decimal("50000"), DenominatorSource.OPENING_BALANCE,
                          None, Quality.GOOD)


# ---------------------------------------------------------------------------
# Cold start — the question the specification leaves open
# ---------------------------------------------------------------------------

def test_a_brand_new_user_still_gets_trade_relative_safety():
    """
    No equity, no history, first ever trade. Account-relative must abstain, but
    "you have lost 80% of what you put at risk" needs nothing but the trade —
    so the user is NOT unprotected.
    """
    assert loss_vs_account(8_000, ABSTAIN).is_measurable is False
    trade = loss_vs_trade(8_000, capital_at_risk=10_000)
    assert trade.is_measurable
    assert trade.value == pytest.approx(0.80)


def test_account_relative_abstains_rather_than_inventing_a_denominator():
    """
    The alternative to abstaining is telling someone they lost 40% of an account
    we cannot see. Silence is the honest answer.
    """
    m = loss_vs_account(20_000, ABSTAIN)
    assert m is UNMEASURABLE or not m.is_measurable
    assert m.value is None
    assert m.quality is Quality.UNKNOWN


def test_the_three_families_are_independent():
    """Losing the account denominator must not disable the other two."""
    assert not loss_vs_account(5_000, ABSTAIN).is_measurable
    assert loss_vs_trade(5_000, 10_000).is_measurable
    assert loss_vs_own_losses(5_000, [500] * 25, min_sample=20).is_measurable


# ---------------------------------------------------------------------------
# Provenance travels with the number
# ---------------------------------------------------------------------------

def test_every_measurement_names_what_it_divided_by():
    """An alert must be explainable back to its arithmetic."""
    assert "opening balance" in loss_vs_account(5_000, ACCOUNT_50K).denominator_label
    assert "put at risk" in loss_vs_trade(5_000, 10_000).denominator_label
    assert "typical losing trade" in loss_vs_own_losses(
        5_000, [500] * 25, min_sample=20).denominator_label


def test_quality_is_inherited_from_the_denominator():
    """A stale account figure must not yield a confident measurement."""
    stale = AccountRisk(Decimal("50000"), DenominatorSource.DECLARED_CAPITAL,
                        None, Quality.PARTIAL)
    assert loss_vs_account(5_000, stale).quality is Quality.PARTIAL


# ---------------------------------------------------------------------------
# Trader-relative states its evidence, and refuses without enough
# ---------------------------------------------------------------------------

def test_below_the_sample_bar_it_abstains_and_reports_what_it_had():
    m = loss_vs_own_losses(3_000, [500, 600, 550], min_sample=20)
    assert not m.is_measurable
    assert m.sample_size == 3


def test_the_sample_bar_comes_from_the_caller_not_this_module():
    """
    A minimum sample buried in measurements.py would be an unprovenanced number.
    It belongs to the detector's declared maturity, so the same history can be
    sufficient for one detector and not another.
    """
    history = [500] * 10
    assert loss_vs_own_losses(3_000, history, min_sample=5).is_measurable
    assert not loss_vs_own_losses(3_000, history, min_sample=20).is_measurable


def test_median_not_mean_so_one_catastrophe_does_not_redefine_typical():
    ordinary = [500] * 24
    with_shock = ordinary + [25_000]
    m = loss_vs_own_losses(1_000, with_shock, min_sample=20)
    assert m.denominator == pytest.approx(500)     # mean would be ~1,480


def test_scale_independence_across_two_very_different_traders():
    """
    The property the whole redesign turns on: the same behaviour reads the same
    for a Rs 50k trader and a Rs 50L trader.
    """
    small = loss_vs_own_losses(3_000, [600] * 25, min_sample=20)
    large = loss_vs_own_losses(40_000, [8_000] * 25, min_sample=20)
    assert small.value == pytest.approx(5.0)
    assert large.value == pytest.approx(5.0)


def test_gap_ratio_is_smaller_when_faster():
    """
    Direction matters and getting it backwards is silent: a SMALLER ratio means
    a faster re-entry, so callers compare against a LOW percentile.
    """
    fast = gap_vs_own_gaps(1.0, [10.0] * 25, min_sample=20)
    slow = gap_vs_own_gaps(30.0, [10.0] * 25, min_sample=20)
    assert fast.value < 1.0 < slow.value


def test_size_ratio_uses_the_same_machinery():
    m = size_vs_own_sizes(60_000, [10_000] * 25, min_sample=20)
    assert m.value == pytest.approx(6.0)


def test_dispersion_separates_two_traders_with_the_same_median():
    """
    6 +/- 1 and 6 +/- 9 have the same median and completely different normality.
    A percentile without dispersion can call routine variance unusual.
    """
    steady = dispersion([6, 6, 7, 5, 6, 6])
    erratic = dispersion([6, 1, 15, 2, 12, 6])
    assert steady < erratic


# ---------------------------------------------------------------------------
# Degenerate inputs must abstain, never divide by zero
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad", [0, None, -100])
def test_a_nonpositive_denominator_is_unmeasurable(bad):
    assert not loss_vs_trade(5_000, bad).is_measurable


def test_all_zero_history_is_unmeasurable():
    assert not loss_vs_own_losses(5_000, [0] * 25, min_sample=20).is_measurable
