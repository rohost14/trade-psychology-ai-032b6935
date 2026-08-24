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


#: Detectors whose pattern review is complete. Adoption of the shared mechanisms
#: is allowed only for these — one at a time, each behind a replay.
REVIEWED_DETECTORS = {
    "revenge_trade",
    # Pattern #1, reviewed 2026-08-24. Reads instrument_risk for its
    # exposure denominator and abstains when is_comparable is False.
    # docs/contracts/adding_to_adverse_position_contract.md + three
    # validation companions.
    "adding_to_adverse_position",
    # Pattern #1, reviewed 2026-08-24. Uses instrument_risk for capital at
    # risk and abstains when is_comparable is False.
    "martingale_behaviour",
}


def test_only_reviewed_detectors_consume_the_shared_mechanisms():
    """
    F1-F5 are mechanisms, not behaviour, and adoption is a per-detector decision
    taken during that detector's review.

    This guarded "nobody consumes them" until revenge_trade was reviewed. It now
    guards the real property: the modules are imported inside the reviewed
    detector's own method and nowhere else. A second detector reaching for them
    without a review fails here.
    """
    import inspect

    from app.services.behavior_engine import BehaviorEngine

    for module in ("core.maturity", "core.confidence", "core.instrument_risk"):
        for name in dir(BehaviorEngine):
            if not name.startswith("_detect_"):
                continue
            detector = name.replace("_detect_", "", 1)
            if detector in REVIEWED_DETECTORS:
                continue
            method = getattr(BehaviorEngine, name, None)
            try:
                src = inspect.getsource(method)
            except (TypeError, OSError):
                continue
            assert module not in src, (
                f"{detector} imports {module} but has not been reviewed - "
                "adoption belongs to that detector's own review, behind a replay"
            )


# ── F2: every universal floor declares which way it points ─────────────────


def test_every_universal_floor_declares_a_direction():
    """
    A floor is the same arithmetic either way and means opposite things. Without
    a declared direction the same dict reads as a safety guarantee on some keys
    and as spam suppression on others, and a bound applied to one of them later
    would silently invert its guarantee.
    """
    from app.core.threshold_registry import THRESHOLD_SPECS, Sensitivity
    from app.core.trading_defaults import UNIVERSAL_FLOORS

    undeclared = [
        key for key in UNIVERSAL_FLOORS
        if key not in THRESHOLD_SPECS
        or THRESHOLD_SPECS[key].sensitivity is Sensitivity.UNKNOWN
    ]
    assert undeclared == [], f"floors with no declared direction: {undeclared}"


def test_the_floors_contain_both_kinds():
    """
    Not a formality. Four are noise floors and six are sensitivity floors — if
    they were all one kind, a single comparison would have been defensible.
    """
    from app.core.threshold_registry import THRESHOLD_SPECS, Sensitivity
    from app.core.trading_defaults import UNIVERSAL_FLOORS

    kinds = {THRESHOLD_SPECS[k].sensitivity for k in UNIVERSAL_FLOORS}
    assert Sensitivity.HIGHER_IS_LOOSER in kinds
    assert Sensitivity.HIGHER_IS_STRICTER in kinds


def test_declaring_direction_never_overwrites_an_existing_classification():
    """
    The regression this test exists for, and the reason it is written this way.

    The first cut of F2 rebuilt every floor entry with kind=FALLBACK and silently
    downgraded two thresholds that were already personal_baseline —
    revenge_window_danger_min and rapid_flip_min. No value moved, so a
    threshold-equality check showed nothing: what was lost was classification,
    which is the one thing this registry exists to hold.

    Worse, the first version of THIS test asserted every floor was FALLBACK, so
    it passed *because* of the bug. A test that encodes the defect it should
    catch is worse than no test, so it now names the two keys that carry a prior
    classification and requires them to keep it.
    """
    from app.core.threshold_registry import THRESHOLD_SPECS, Sensitivity
    from app.core.threshold_resolution import Kind
    from app.core.trading_defaults import UNIVERSAL_FLOORS

    # revenge_window_danger_min was the second key here until 2026-08-24, when
    # it was deleted as unread. rapid_flip_min still carries the property.
    already_classified = {
        "rapid_flip_min": Kind.PERSONAL_BASELINE,
    }
    for key, expected in already_classified.items():
        spec = THRESHOLD_SPECS[key]
        assert spec.kind is expected, (
            f"{key} was {expected.value} and is now {spec.kind.value}; declaring "
            "a direction must not overwrite a decision someone else made"
        )
        assert spec.sensitivity is not Sensitivity.UNKNOWN, (
            f"{key} kept its Kind but lost its direction"
        )


def test_f2_did_not_classify_anything_as_safety():
    """
    Declaring direction is F2; deciding what is universal safety is F1. If a
    floor became universal_safety while its direction was being recorded, two
    decisions were conflated in one change.
    """
    from app.core.threshold_registry import THRESHOLD_SPECS
    from app.core.threshold_resolution import Kind
    from app.core.trading_defaults import UNIVERSAL_FLOORS

    for key in UNIVERSAL_FLOORS:
        assert THRESHOLD_SPECS[key].kind is not Kind.UNIVERSAL_SAFETY, (
            f"{key} was classified as safety during F2"
        )
        assert THRESHOLD_SPECS[key].safety_bound is None



# ── F1: the safety classification ──────────────────────────────────────────


def test_the_safety_guard_now_guards_something():
    """
    `violates_kind` has been enforced at resolution time since the foundation
    work, and guarded an empty set: no threshold was classified universal_safety,
    so the central invariant was machinery protecting nothing.
    """
    from app.core.threshold_registry import THRESHOLD_SPECS
    from app.core.threshold_resolution import Kind

    safety = [k for k, s in THRESHOLD_SPECS.items()
              if s.kind is Kind.UNIVERSAL_SAFETY]
    assert safety, "no threshold is classified universal_safety"


def test_tempo_thresholds_are_deliberately_not_safety():
    """
    The seven keys personal history actually moves describe a trader's TEMPO, not
    objective harm. "Six losses in a row" is a streak, and whether it hurt depends
    entirely on the size of the six.

    Classifying them universal_safety would forbid the personalisation that is the
    entire purpose of a baseline — the opposite error to the one being fixed.
    """
    from app.core.threshold_registry import kind_for
    from app.core.threshold_resolution import Kind

    tempo = (
        "daily_trade_limit", "daily_trade_danger",
        "burst_trades_per_30min_caution", "burst_trades_per_30min_danger",
        "revenge_window_caution_min",
        "consecutive_loss_caution", "consecutive_loss_danger",
    )
    for key in tempo:
        assert kind_for(key) is not Kind.UNIVERSAL_SAFETY, (
            f"{key} was classified as safety; it describes tempo, and this would "
            "silently disable personalisation for it"
        )


def test_a_safety_threshold_may_still_come_from_capital():
    """
    violates_kind forbids HISTORY, SESSION and POPULATION. CAPITAL must remain
    allowed: account-relative safety needs an account size, and capital comes off
    the broker rather than out of the trader's habits.
    """
    from app.core.threshold_resolution import Kind, Source, violates_kind

    assert violates_kind(Kind.UNIVERSAL_SAFETY, Source.CAPITAL) is None
    assert violates_kind(Kind.UNIVERSAL_SAFETY, Source.HISTORY) is not None
    assert violates_kind(Kind.UNIVERSAL_SAFETY, Source.SESSION) is not None


def test_no_safety_threshold_is_reachable_by_a_learning_rung_today():
    """
    Neutrality, asserted rather than hoped. Rung 1 moves seven keys and rung 2
    moves exactly two; if a future rung starts writing one of the safety keys,
    this fails before the guard has to.
    """
    from app.core.threshold_registry import THRESHOLD_SPECS
    from app.core.threshold_resolution import (
        Kind,
        Source,
        _LEARNED_SOURCES,
        resolve_thresholds,
    )

    class _Rich:
        detected_patterns = {"baseline": {"version": 2, "metrics": {
            k: {"value": 9.0, "confidence": 1.0, "n": 60} for k in (
                "daily_trades_p75", "burst_per_30min_p75",
                "reentry_after_loss_p25", "loss_streak_p60", "loss_streak_p85")
        }}}
        trading_capital = 500000

    resolved = resolve_thresholds(_Rich())
    for key, spec in THRESHOLD_SPECS.items():
        if spec.kind is not Kind.UNIVERSAL_SAFETY:
            continue
        record = resolved.explain(key)
        if record is None:
            continue
        assert record.source not in _LEARNED_SOURCES, (
            f"{key} is universal_safety and resolved from {record.source.value}"
        )
