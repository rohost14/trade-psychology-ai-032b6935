"""
Every threshold declares what it is, and illegal pairings are rejected.

The registry exists because comments cannot be asserted. `burst_trades_per_15min`
carried "Used by RiskDetector" for months after RiskDetector was archived and
nothing caught it. A spec can be checked; a comment cannot.
"""
import pytest

from app.core.threshold_registry import (
    MANDATORY_REVIEW,
    THRESHOLD_SPECS,
    Maturity,
    kind_for,
    personalisable_keys,
    spec_for,
)
from app.core.threshold_resolution import Kind, Source, resolve_thresholds, violates_kind
from app.core.trading_defaults import COLD_START_DEFAULTS


def test_every_spec_fallback_matches_the_live_default():
    """
    A spec whose fallback has drifted from the actual constant is worse than no
    spec: it documents a number the engine does not use.
    """
    drift = {
        k: (s.fallback, COLD_START_DEFAULTS.get(k))
        for k, s in THRESHOLD_SPECS.items()
        if k in COLD_START_DEFAULTS and s.fallback != COLD_START_DEFAULTS[k]
    }
    assert not drift, f"spec fallback disagrees with the live constant: {drift}"


def test_nothing_is_personalised_yet():
    """
    This migration builds the path and changes no behaviour. Each detector flips
    its own at review, behind a replay. If this fails, something was switched on
    without that review.
    """
    on = [k for k, s in THRESHOLD_SPECS.items() if s.personalise]
    assert not on, f"personalisation enabled without detector review: {on}"


def test_a_named_metric_does_not_mean_it_should_be_personal():
    """
    Documents the distinction explicitly: naming a metric records that
    personalisation is AVAILABLE, not that it is correct. Whether it makes a
    detector more accurate is evidence work at review.
    """
    for key, s in personalisable_keys().items():
        assert s.metric
        assert s.personalise is False
        assert s.maturity is not Maturity.NONE, (
            f"{key} names a metric but requires no maturity - a percentile over "
            f"no observations is not personalisation, it is noise"
        )


def test_definitional_thresholds_name_no_metric():
    """
    A streak of three is a definition. Personalising it would mean a trader with
    many streaks needs a LONGER streak before anyone mentions it.
    """
    for key, s in THRESHOLD_SPECS.items():
        if s.kind is Kind.DEFINITIONAL:
            assert s.metric is None, f"{key} is definitional but names a metric"


def test_the_flagged_judgements_are_marked_for_mandatory_review():
    flagged = {k for k, s in THRESHOLD_SPECS.items() if s.review_required}
    assert "fomo_symbols_at_open" in flagged
    # revenge_window_danger_min was flagged here until 2026-08-24, when the
    # constant was deleted as unread - the frozen A x B matrix has no danger
    # sub-tier on the reaction axis. Its MANDATORY_REVIEW entry is kept so the
    # reason survives, but it no longer has a spec to carry review_required.
    for k in flagged:
        assert "FLAGGED" in spec_for(k).provenance


def test_mandatory_review_set_records_the_retired_constant():
    """burst_trades_per_15min is gone; the reason it went must not be."""
    assert "burst_trades_per_15min" in MANDATORY_REVIEW
    assert "burst_trades_per_15min" not in COLD_START_DEFAULTS


def test_every_spec_carries_provenance():
    missing = [k for k, s in THRESHOLD_SPECS.items() if not s.provenance.strip()]
    assert not missing, f"specs with no stated reason: {missing}"


# ---------------------------------------------------------------------------
# The invariant, checked against real resolutions
# ---------------------------------------------------------------------------

def test_no_resolution_violates_its_kind_at_cold_start():
    ts = resolve_thresholds(None)
    bad = [
        (k, r.kind, r.source)
        for k, r in ts.meta.items()
        if r.kind and violates_kind(r.kind, r.source)
    ]
    assert not bad, f"illegal kind/source pairings: {bad}"


def test_unclassified_constants_read_as_fallback_not_as_considered():
    """
    An unclassified constant should look unclassified. Defaulting to anything
    else would let it pass as a decision someone made.
    """
    assert kind_for("a_constant_that_does_not_exist") is Kind.FALLBACK


def test_kind_comes_from_the_registry_not_the_caller():
    """
    What a threshold IS must not depend on which code path resolved it, or the
    same constant could be safety on one route and personal on another.
    """
    ts = resolve_thresholds(None)
    for key, s in THRESHOLD_SPECS.items():
        if key in ts.values:
            assert ts.explain(key).kind is s.kind
