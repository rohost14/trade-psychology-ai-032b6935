"""
The global baseline rules, as they behave inside baseline_service.

test_baseline_rules covers the primitives. This covers the wiring: that a metric
record actually excludes outliers, actually caps its movement, and says so.
"""
import pytest

from app.services.baseline_service import (
    _apply_adaptation_cap,
    _metric,
    _pct_metric,
)


def test_a_metric_excludes_outliers_and_reports_how_many():
    """
    Nine ordinary losses and one catastrophe. The catastrophe must not define
    what is typical, and the exclusion must be visible rather than silent.
    """
    losses = [500, 520, 480, 510, 495, 505, 515, 490, 500, 25_000]
    rec = _metric(losses, n=len(losses), target=100)
    assert rec["value"] == pytest.approx(500, abs=15)
    assert rec["n_excluded"] == 1
    assert rec["n"] == 10          # raw sample size, as passed in
    assert rec["n_learned"] == 9   # what the baseline was allowed to learn from


def test_a_metric_reports_mad_not_only_stddev():
    """
    stddev is defined around the mean and inherits its sensitivity to exactly
    the outliers trading data is full of.
    """
    rec = _metric([500, 520, 480, 510, 495, 505], n=6, target=100)
    assert rec["mad"] is not None


def test_percentile_metrics_also_learn_only_from_clean_observations():
    counts = [5, 6, 5, 7, 6, 5, 6, 7, 5, 400]
    rec = _pct_metric(counts, 75, n=len(counts), target=20)
    assert rec["n_excluded"] == 1
    assert rec["value"] < 20


def test_adaptation_is_capped_against_the_previous_baseline():
    """
    The escalation case: trader normally sizes at 10k, escalates to 50k. Without
    a cap the baseline follows and the detector dies quietly.
    """
    previous = {"metrics": {"typical_size": {"value": 10_000}}}
    proposed = {"typical_size": {"value": 50_000}}
    capped = _apply_adaptation_cap(proposed, previous)
    assert capped["typical_size"]["value"] == pytest.approx(12_000)
    assert capped["typical_size"]["adaptation_capped"] is True
    assert capped["typical_size"]["uncapped_value"] == 50_000


def test_a_cap_that_did_not_bind_leaves_no_marker():
    previous = {"metrics": {"typical_size": {"value": 10_000}}}
    proposed = {"typical_size": {"value": 10_500}}
    capped = _apply_adaptation_cap(proposed, previous)
    assert capped["typical_size"]["value"] == 10_500
    assert "adaptation_capped" not in capped["typical_size"]


def test_a_first_baseline_is_not_capped():
    """Nothing to cap against, and a first estimate is legitimately free."""
    proposed = {"typical_size": {"value": 42_000}}
    assert _apply_adaptation_cap(proposed, None)["typical_size"]["value"] == 42_000


def test_a_metric_absent_from_the_previous_baseline_is_not_capped():
    previous = {"metrics": {"something_else": {"value": 1}}}
    proposed = {"typical_size": {"value": 42_000}}
    assert _apply_adaptation_cap(proposed, previous)["typical_size"]["value"] == 42_000


def test_all_outliers_yields_no_metric_rather_than_a_wrong_one():
    """Better to have no estimate than one built from nothing learnable."""
    assert _metric([], n=0, target=10) is None
