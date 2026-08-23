"""
F3 maturity, F4 confidence, F5 instrument class. Shared, and inert.

All three are mechanisms nothing consumes yet. They exist so that when a detector
is migrated it does not re-answer questions that are the same everywhere — which
is how nine competing definitions of a session fact happened, and how seven call
sites came to compute confidence differently.

None of them introduces a threshold, a weight or a score.
"""
import pytest

from app.core import confidence, maturity
from app.core.evidence import Insufficiency
from app.core.instrument_risk import (
    DenominatorKind,
    InstrumentClass,
    classify,
    risk_basis,
)
from app.core.maturity import MaturityState
from app.core.measurements import loss_vs_risk_basis


# ── F3: maturity ───────────────────────────────────────────────────────────


def test_no_metric_is_unavailable():
    a = maturity.assess(None, 20)
    assert a.state is MaturityState.UNAVAILABLE
    assert a.reason is Insufficiency.NO_BASELINE


def test_some_history_but_not_enough_is_immature_not_unavailable():
    """
    The distinction that stops a fallback being described as personal. Both use
    the fallback; only one of them means "we are still learning about you".
    """
    a = maturity.assess({"n": 7}, 20)
    assert a.state is MaturityState.IMMATURE
    assert a.observed == 7 and a.required == 20
    assert "still learning" in a.describe()


def test_enough_history_is_mature():
    a = maturity.assess({"n": 40}, 20)
    assert a.state is MaturityState.MATURE
    assert a.is_usable and a.is_personalised
    assert a.reason is None


def test_an_undeclared_requirement_does_not_assume_readiness():
    """
    M1 is unresolved for every metric. Treating "nobody said how much is enough"
    as "enough" would invent the requirement at the moment of use, which is worse
    than leaving it unset.
    """
    a = maturity.assess({"n": 1000}, None)
    assert a.state is MaturityState.UNAVAILABLE
    assert a.is_usable is False


@pytest.mark.parametrize("state_input,expected", [
    ({"n": 40}, True),
    ({"n": 3}, False),
    (None, False),
])
def test_only_a_mature_metric_may_be_called_personal(state_input, expected):
    assert maturity.assess(state_input, 20).is_personalised is expected


# ── F4: confidence ─────────────────────────────────────────────────────────


def test_confidence_is_the_weakest_link_not_a_sum():
    """
    Three good inputs and one poor one is a poor conclusion. Adding them would
    let quantity of evidence stand in for quality of evidence, which is the
    behaviour score in miniature.
    """
    assert confidence.combine(100.0, 100.0, 100.0, 40.0) == 40.0


def test_inputs_that_were_not_consulted_are_ignored_not_zero():
    """
    A metric the verdict never used says nothing about certainty. Treating it as
    zero would punish a detector for evidence it correctly did not need.
    """
    assert confidence.combine(80.0, None, None) == 80.0


def test_no_inputs_means_no_confidence_not_zero_confidence():
    assert confidence.combine() is None
    assert confidence.combine(None, None) is None


def test_data_quality_bounds_everything_above_it():
    """A mature baseline cannot make a PARTIAL-quality trade more certain."""
    assert confidence.from_observables("PARTIAL", [1.0]) == 75.0


def test_a_purely_structural_verdict_is_as_good_as_its_data():
    """No personal metric used, so nothing but data quality bounds it."""
    assert confidence.from_observables("GOOD", []) == 100.0


def test_an_immature_sample_drags_confidence_down():
    assert confidence.from_observables("GOOD", [0.3]) == 30.0


def test_unparsed_inputs_reuse_the_existing_vocabulary():
    """Not a new number — the same UNKNOWN level the engine already uses."""
    assert (confidence.from_observables("GOOD", [], inputs_parsed=False)
            == confidence.from_data_quality("UNKNOWN"))


# ── F5: instrument class ───────────────────────────────────────────────────


@pytest.mark.parametrize("itype,direction,expected", [
    ("CE", "LONG", InstrumentClass.LONG_OPTION),
    ("PE", "LONG", InstrumentClass.LONG_OPTION),
    ("CE", "SHORT", InstrumentClass.SHORT_OPTION),
    ("FUT", "LONG", InstrumentClass.FUTURES),
    ("EQ", "LONG", InstrumentClass.EQUITY),
    (None, None, InstrumentClass.UNKNOWN),
])
def test_classification(itype, direction, expected):
    assert classify(itype, direction) is expected


def test_a_spread_is_supplied_by_the_caller_not_derived():
    """
    A spread is a relationship between trades, not a property of one, so it
    cannot come from a single CompletedTrade.
    """
    assert classify("CE", "LONG", is_spread=True) is InstrumentClass.SPREAD


def test_the_same_loss_means_different_things_by_class():
    """
    The finding that made this module necessary. One threshold cannot span these.
    """
    long_opt = risk_basis("CE", "NIFTY25SEP24000CE", "LONG", 200.0, 50)
    short_opt = risk_basis("CE", "NIFTY25SEP24000CE", "SHORT", 200.0, 50)

    lost = 8000.0
    as_long = loss_vs_risk_basis(lost, long_opt)
    as_short = loss_vs_risk_basis(lost, short_opt)

    assert as_long.value == pytest.approx(0.8), "80% of the premium paid"
    assert as_short.value > 5, "several times the margin posted"
    assert as_long.denominator_kind == DenominatorKind.LOSS_CEILING.value
    assert as_short.denominator_kind == DenominatorKind.MARGIN_POSTED.value


def test_a_spread_abstains_rather_than_reporting_a_known_wrong_ratio():
    """
    estimate_capital_at_risk over-estimates a hedged position, so the ratio is
    understated in a known direction — a confident false negative, which is worse
    than silence.
    """
    basis = risk_basis("CE", "NIFTY25SEP24000CE", "LONG", 200.0, 50, is_spread=True)
    m = loss_vs_risk_basis(8000.0, basis)

    assert basis.is_comparable is False
    assert m.value is None
    assert m.instrument_class == InstrumentClass.SPREAD.value


def test_the_amount_is_unchanged_from_the_existing_estimator():
    """
    F5 adds a label, never a different number. Anything reading the figure today
    must be unaffected.
    """
    from app.core.trading_defaults import estimate_capital_at_risk

    for itype, direction in (("CE", "LONG"), ("CE", "SHORT"), ("FUT", "LONG")):
        basis = risk_basis(itype, "NIFTY25SEP24000CE", direction, 200.0, 50)
        assert basis.amount == estimate_capital_at_risk(
            itype, "NIFTY25SEP24000CE", direction, 200.0, 50
        )


def test_the_label_names_the_denominator_in_the_trader_s_terms():
    """Copy must be able to say what it divided by, not just print a ratio."""
    assert "premium" in risk_basis("CE", "X", "LONG", 200.0, 50).label
    assert "margin" in risk_basis("FUT", "X", "LONG", 200.0, 50).label


# ── all three are inert ────────────────────────────────────────────────────


def test_nothing_consumes_these_yet():
    """
    F1-F5 are shared mechanisms, not behaviour. If a detector starts importing
    one before the pattern phase, it happened outside a detector review.
    """
    import inspect

    from app.services import behavior_engine

    src = inspect.getsource(behavior_engine)
    for module in ("core.maturity", "core.confidence", "core.instrument_risk"):
        assert module not in src, (
            f"behavior_engine imports {module} - adoption belongs to the "
            "pattern-by-pattern phase, behind a replay"
        )
