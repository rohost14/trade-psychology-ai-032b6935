"""
Structure-level `martingale_behaviour` — Q1, 2026-09-02.

THE SUBJECT CHANGED; IT DID NOT DISAPPEAR.

Inside a recognised structure, "leg 2 is 2x leg 1" is not a finding: the legs
are one construction placed at once, which is why F6 suppressed this detector
there. But the STRUCTURE is a unit that can be escalated, and

    "this straddle is 2x your last straddle"

is the martingale question asked at the level the decision was actually made.
So the detector left `_STRATEGY_SUPPRESSED` — suppressing it would have made
this branch unreachable — and compares structures instead of legs whenever the
trade is a leg of one.

WHAT "COMPARABLE" MEANS, AND WHY IT IS STRICT

Same underlying, same expiry, same recognised strategy type, most recent
first. A straddle is not comparable to a strangle and NIFTY is not comparable
to BANKNIFTY. Like-for-like, or the comparison does not exist.

WHAT "DEPLOYMENT" MEANS, AND WHERE IT ABSTAINS

The net debit paid. Long legs are money out, short legs money in, so a debit
spread nets to the debit rather than the gross sum of its legs. A CREDIT
structure's commitment is margin, not the cash received, and broker margin is
not captured yet — so credit structures, futures hedges and calendars abstain
rather than being handed a number nobody can source.

VALIDATION LIMIT — STATED, NOT GLOSSED

These tests are deterministic and synthetic, and that is not a shortcut. The
reference book holds 11 recognised structures across 203 sessions — 8
strangles, 1 straddle, 1 bull call spread, 1 futures hedge — so two comparable
structures in sequence after a run of losses occurs approximately never in it.
This behaviour ships CORRECT BY CONSTRUCTION AND EMPIRICALLY UNVALIDATED, and
no replay on this book can change that. It needs a trader who repeats
structures.
"""
from types import SimpleNamespace

import pytest

from app.models.strategy_group import StrategyType
from app.services.strategy_detector import (
    DEPLOYMENT_MEASURABLE, DeploymentLeg, StructureSizing, structure_deployment,
)


def leg(itype, direction, price, qty=100):
    return DeploymentLeg(itype, direction, price, qty)


# ── Deployment: the pure function ────────────────────────────────────────────

def test_a_long_straddle_deploys_the_sum_of_both_premiums():
    assert structure_deployment(StrategyType.STRADDLE_BUY, [
        leg("CE", "LONG", 50.0), leg("PE", "LONG", 60.0),
    ]) == pytest.approx(11_000.0)


def test_a_long_strangle_deploys_the_sum_of_both_premiums():
    assert structure_deployment(StrategyType.STRANGLE_BUY, [
        leg("CE", "LONG", 30.0), leg("PE", "LONG", 25.0),
    ]) == pytest.approx(5_500.0)


def test_a_debit_spread_deploys_the_NET_debit_not_the_gross_sum():
    """
    Buying the 25000 CE and selling the 25200 CE commits the difference. The
    gross sum overstates the commitment by the credit received, and on a ratio
    that error does not cancel.
    """
    assert structure_deployment(StrategyType.BULL_CALL_SPREAD, [
        leg("CE", "LONG", 50.0), leg("CE", "SHORT", 20.0),
    ]) == pytest.approx(3_000.0)


def test_a_bear_put_spread_nets_the_same_way():
    assert structure_deployment(StrategyType.BEAR_PUT_SPREAD, [
        leg("PE", "LONG", 80.0), leg("PE", "SHORT", 30.0),
    ]) == pytest.approx(5_000.0)


@pytest.mark.parametrize("strategy_type,legs", [
    (StrategyType.STRANGLE_SELL, [leg("CE", "SHORT", 50.0), leg("PE", "SHORT", 60.0)]),
    (StrategyType.STRADDLE_SELL, [leg("CE", "SHORT", 50.0), leg("PE", "SHORT", 50.0)]),
    (StrategyType.IRON_CONDOR, [leg("CE", "SHORT", 50.0), leg("CE", "LONG", 20.0),
                                leg("PE", "SHORT", 40.0), leg("PE", "LONG", 15.0)]),
    (StrategyType.BULL_PUT_SPREAD, [leg("PE", "SHORT", 60.0), leg("PE", "LONG", 30.0)]),
    (StrategyType.CALENDAR_SPREAD, [leg("CE", "SHORT", 40.0), leg("CE", "LONG", 60.0)]),
    (StrategyType.SYNTHETIC_LONG, [leg("CE", "LONG", 50.0), leg("PE", "SHORT", 50.0)]),
])
def test_credit_and_unmeasurable_structures_abstain(strategy_type, legs):
    """
    Not "return zero", not "use the premium received" — None, so the caller
    abstains. What a credit structure commits is MARGIN, and broker margin is
    not captured yet.
    """
    assert structure_deployment(strategy_type, legs) is None


def test_a_futures_hedge_abstains_because_a_future_has_no_premium():
    assert structure_deployment(StrategyType.FUTURES_HEDGE_BULLISH, [
        leg("FUT", "LONG", 25_000.0, 50), leg("PE", "LONG", 60.0, 50),
    ]) is None


def test_multi_leg_unknown_is_not_measurable():
    """It is not a structure at all any more — belt and braces."""
    assert structure_deployment(StrategyType.MULTI_LEG_UNKNOWN, [
        leg("CE", "LONG", 50.0), leg("CE", "LONG", 60.0),
    ]) is None


@pytest.mark.parametrize("bad", [
    [leg("CE", "LONG", 0.0), leg("PE", "LONG", 60.0)],
    [leg("CE", "LONG", 50.0), leg("PE", "LONG", 60.0, 0)],
    [leg("CE", "LONG", None), leg("PE", "LONG", 60.0)],
])
def test_an_unusable_price_or_quantity_abstains(bad):
    assert structure_deployment(StrategyType.STRADDLE_BUY, bad) is None


def test_the_allow_list_is_exactly_the_four_debit_structures():
    assert DEPLOYMENT_MEASURABLE == frozenset({
        StrategyType.STRADDLE_BUY, StrategyType.STRANGLE_BUY,
        StrategyType.BULL_CALL_SPREAD, StrategyType.BEAR_PUT_SPREAD,
    })


# ── The detector branch ──────────────────────────────────────────────────────

def _ctx(sizing_value, losses=2, strategy_type=StrategyType.STRADDLE_BUY):
    from tests.test_behavior_engine import make_ct, make_ctx

    prior = [make_ct(symbol="NIFTY25AUG25000CE", instrument_type="CE",
                     pnl=-500.0, entry_offset_min=-60 + i * 10)
             for i in range(losses)]
    ct = make_ct(symbol="NIFTY25AUG25000CE", instrument_type="CE",
                 pnl=-400.0, entry_offset_min=-5)
    ctx = make_ctx(completed_trade=ct, session_trades=prior)
    ctx.strategy_group = SimpleNamespace(strategy_type=strategy_type, net_pnl=None)
    ctx.structure_sizing = sizing_value
    # `concluded_before_entry` is derived from `session_trades` — priors close
    # at -35/-25 min, the current trade enters at -5, so both are CONCLUDED
    # before this entry, which is what the causal claim requires.
    return ctx


def _run(ctx):
    from tests.test_behavior_engine import engine
    return engine._detect_martingale_behaviour(ctx)


def sizing(current, previous, strategy_type=StrategyType.STRADDLE_BUY):
    return StructureSizing(strategy_type=strategy_type, current=current,
                           previous=previous, previous_opened_at=None)


def test_doubling_a_straddle_after_losses_is_a_danger_finding():
    """The case from the spec: a 10k straddle, a loss, then a 20k straddle."""
    r = _run(_ctx(sizing(20_000.0, 10_000.0)))
    assert r.fired
    assert r.severity == "danger"
    assert r.context["scope"] == "structure"
    assert r.context["ratio"] == pytest.approx(2.0)
    assert "2.0x the deployment of your last one" in r.message


def test_a_modest_increase_is_caution_not_danger():
    r = _run(_ctx(sizing(16_000.0, 10_000.0)))
    assert r.fired and r.severity == "caution"


def test_the_same_deployment_twice_is_not_a_finding():
    assert not _run(_ctx(sizing(10_000.0, 10_000.0))).fired


def test_a_smaller_structure_after_losses_is_not_a_finding():
    """Sizing DOWN after losses is the opposite behaviour."""
    assert not _run(_ctx(sizing(5_000.0, 10_000.0))).fired


def test_it_abstains_inside_a_structure_with_no_comparable_predecessor():
    """
    A first straddle has nothing to be 2x of. It abstains rather than falling
    back to a leg-level comparison — the legs are one construction, and that
    comparison is exactly what F6 established is meaningless here.
    """
    r = _run(_ctx(None))
    assert not r.fired
    assert r.abstained


def test_it_abstains_inside_a_credit_structure():
    """`structure_sizing` yields None for these, so the detector abstains."""
    assert _run(_ctx(None, strategy_type=StrategyType.STRANGLE_SELL)).abstained


def test_the_multipliers_are_the_existing_ones_not_new_ones():
    """1.5x caution / 2.0x danger, unchanged — the thresholds did not move."""
    assert _run(_ctx(sizing(14_900.0, 10_000.0))).fired is False
    assert _run(_ctx(sizing(15_100.0, 10_000.0))).severity == "caution"
    assert _run(_ctx(sizing(20_100.0, 10_000.0))).severity == "danger"


def test_the_loss_run_precondition_still_applies():
    """No run of losses, no finding — however large the escalation."""
    from tests.test_behavior_engine import make_ct

    ctx = _ctx(sizing(50_000.0, 10_000.0))
    ctx.session_trades = [
        make_ct(symbol="NIFTY25AUG25000CE", instrument_type="CE",
                pnl=+500.0, entry_offset_min=-60 + i * 10) for i in range(2)
    ]
    assert not _run(ctx).fired


def test_a_trade_with_no_structure_uses_the_leg_level_path():
    """
    The other half of the rule: ordinary CE -> CE trades are ordinary trades.
    No group means the existing leg-level comparison, untouched.
    """
    ctx = _ctx(None)
    ctx.strategy_group = None
    ctx.structure_sizing = None
    assert _run(ctx).context.get("scope") != "structure"
