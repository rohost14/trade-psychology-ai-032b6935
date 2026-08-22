"""
The rules that stop a baseline learning a trader's destructive behaviour.

Governing principle: **normal is not safe**. A trader's history defines what is
normal for them; it must never define what is safe. The failure this guards
against is silent — the detector goes quiet exactly for the trader who most
needs it, because they have done the dangerous thing often enough for it to look
ordinary.
"""
import pytest

from app.core.baseline_rules import (
    DIVERGENCE_REPORT_RATIO,
    MAX_ADAPTATION_PER_PERIOD,
    cap_adaptation,
    clean_for_learning,
    divergence,
    is_outlier,
    mad,
    median,
    percentile,
)
from app.core.threshold_resolution import Kind, Source, violates_kind


# ---------------------------------------------------------------------------
# Robust statistics — rule 1
# ---------------------------------------------------------------------------

def test_median_survives_the_outlier_that_destroys_a_mean():
    """
    The document's own example: nine ordinary losses and one catastrophe. A mean
    reports ~2,950 as typical, which is true of nothing the trader does.
    """
    losses = [400, 500, 450, 600, 550, 500, 700, 450, 600, 25_000]
    assert median(losses) == pytest.approx(525)
    assert sum(losses) / len(losses) > 2_900


def test_mad_is_not_moved_by_a_single_extreme():
    ordinary = [400, 500, 450, 600, 550, 500]
    with_shock = ordinary + [25_000]
    assert mad(with_shock) == pytest.approx(mad(ordinary), rel=0.5)


def test_percentile_on_a_small_sample_does_not_explode():
    assert percentile([100, 200, 300], 50) in (200, 300)
    assert percentile([], 50) is None


# ---------------------------------------------------------------------------
# Outliers train nothing, but are not erased — rule 5
# ---------------------------------------------------------------------------

def test_a_catastrophic_loss_is_excluded_from_learning():
    losses = [400, 500, 450, 600, 550, 500, 700, 450, 600]
    assert is_outlier(25_000, losses)
    assert not is_outlier(650, losses)


def test_clean_for_learning_drops_extremes_but_keeps_the_ordinary():
    losses = [400, 500, 450, 600, 550, 500, 700, 450, 600, 25_000]
    kept = clean_for_learning(losses)
    assert 25_000 not in kept
    assert len(kept) == 9


def test_confirmed_harmful_trades_do_not_train_the_baseline():
    """
    Rule 4. Revenge sequences are fast by definition, so learning from them
    drags "normal" downward until nothing looks fast any more. A detector's own
    positives must not feed the baseline it is judged against.
    """
    gaps = [11.0, 12.0, 10.0, 9.0, 0.5, 0.7]      # last two from a revenge run
    clean = clean_for_learning(gaps, excluded_indices=[4, 5])
    assert 0.5 not in clean and 0.7 not in clean
    assert median(clean) == pytest.approx(10.5)


def test_too_few_points_to_identify_an_outlier_keeps_them_all():
    """With three observations the outlier would define the distribution."""
    assert clean_for_learning([100, 200, 9_000]) == [100, 200, 9_000]


# ---------------------------------------------------------------------------
# Capped adaptation — rule 3
# ---------------------------------------------------------------------------

def test_a_bad_fortnight_cannot_redefine_normal_in_one_step():
    """
    Trader normally sizes at 10k and escalates to 50k. Without a cap the
    baseline follows and the detector dies quietly.
    """
    assert cap_adaptation(10_000, 50_000) == pytest.approx(12_000)


def test_adaptation_is_capped_downward_too():
    assert cap_adaptation(10_000, 1_000) == pytest.approx(8_000)


def test_small_moves_pass_through_unchanged():
    assert cap_adaptation(10_000, 10_500) == pytest.approx(10_500)


def test_a_first_baseline_is_not_capped():
    assert cap_adaptation(None, 42_000) == 42_000


def test_cap_is_slow_on_purpose():
    assert 0 < MAX_ADAPTATION_PER_PERIOD <= 0.25


# ---------------------------------------------------------------------------
# Two windows — rule 2
# ---------------------------------------------------------------------------

def test_escalation_is_visible_as_divergence():
    """
    The case a single rolling window cannot express: by the time one window has
    adapted, there is nothing left to compare against.
    """
    d = divergence(long_values=[10_000] * 40, recent_values=[18_000] * 15)
    assert d.is_notable
    assert d.direction == "escalating"
    assert d.ratio == pytest.approx(1.8)
    assert "1.8x" in d.describe()


def test_moderation_is_reported_as_well():
    d = divergence(long_values=[20_000] * 40, recent_values=[8_000] * 15)
    assert d.is_notable
    assert d.direction == "moderating"


def test_ordinary_drift_is_not_notable():
    d = divergence(long_values=[10_000] * 40, recent_values=[11_000] * 15)
    assert not d.is_notable
    assert d.describe() is None


def test_divergence_abstains_without_both_windows():
    assert divergence([], [1, 2, 3]).ratio is None
    assert divergence([1, 2, 3], []).ratio is None


# ---------------------------------------------------------------------------
# Normal is not safe — rule 0, as machinery
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("source", [Source.HISTORY, Source.SESSION, Source.POPULATION])
def test_a_safety_threshold_may_never_resolve_from_learned_behaviour(source):
    """
    If a trader risks 15% of their account every day, the engine must keep
    saying so. Personalisation may make it MORE sensitive; it may never make an
    objectively dangerous event invisible.
    """
    reason = violates_kind(Kind.UNIVERSAL_SAFETY, source)
    assert reason is not None
    assert "objective danger" in reason


def test_a_commitment_is_never_inferred():
    assert violates_kind(Kind.USER_RULE, Source.HISTORY) is not None


def test_product_policy_is_not_learned_from_one_trader():
    assert violates_kind(Kind.PRODUCT_POLICY, Source.HISTORY) is not None


@pytest.mark.parametrize("kind,source", [
    (Kind.PERSONAL_BASELINE, Source.HISTORY),
    (Kind.PERSONAL_BASELINE, Source.SESSION),
    (Kind.UNIVERSAL_SAFETY, Source.GLOBAL),
    (Kind.USER_RULE, Source.DECLARED),
    (Kind.FALLBACK, Source.GLOBAL),
])
def test_legitimate_pairings_are_allowed(kind, source):
    assert violates_kind(kind, source) is None
