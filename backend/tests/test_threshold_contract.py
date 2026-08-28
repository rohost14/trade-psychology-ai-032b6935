"""
The threshold registry must describe what resolution actually does.

WHY THIS FILE EXISTS

Four consecutive pattern reviews (7, 9, 10, 11) each independently found a
threshold "declared personal that can never personalise" and treated it as a
local defect. It was one systemic question with local symptoms, and answering it
properly turned up something the pattern reviews had not: a UNIVERSAL_SAFETY
threshold that a trader could loosen by declaring a number.

These tests are the machinery for the parts of that contract that were only ever
prose. Full findings in docs/contracts/PERSONAL_BASELINE_AUDIT.md.
"""
from types import SimpleNamespace

import pytest

from app.core.safety_bounds import bound_for, clamp_to_bound
from app.core.threshold_registry import (
    THRESHOLD_SPECS,
    Sensitivity,
    kind_for,
)
from app.core.threshold_resolution import (
    Kind,
    Source,
    resolve_thresholds,
    violates_kind,
)


def _profile(**kw):
    base = dict(detected_patterns={}, trading_capital=200000)
    base.update(kw)
    return SimpleNamespace(**base)


BASELINE_V2 = {
    "version": 2,
    "computed_at": "2026-08-01T00:00:00Z",
    "sessions_analyzed": 40,
    "metrics": {
        "daily_trades_p75": {"value": 7.0, "confidence": 0.9, "n": 40},
        "burst_per_30min_p75": {"value": 4.0, "confidence": 0.8, "n": 40},
        "reentry_after_loss_p25": {"value": 3.0, "confidence": 0.7, "n": 40},
        "loss_streak_p60": {"value": 4.0, "confidence": 0.6, "n": 40},
    },
}

#: The four thresholds that are actually personalised, and the metric each uses.
#: Kept here rather than read from the registry so the test fails if either side
#: drifts — reading the registry would make it agree with itself.
ACTUALLY_PERSONALISED = {
    "daily_trade_limit": "daily_trades_p75",
    "burst_trades_per_30min_caution": "burst_per_30min_p75",
    "revenge_window_caution_min": "reentry_after_loss_p25",
    "consecutive_loss_caution": "loss_streak_p60",
}


# ── 1. safety cannot be loosened ───────────────────────────────────────────

def test_a_declared_size_cannot_loosen_the_universal_safety_line():
    """
    THE BUG THIS FILE WAS WRITTEN FOR.

    `_apply_profile_facts` maps a declared `max_position_size` onto
    `max_position_pct_caution` / `_danger`, both Kind.UNIVERSAL_SAFETY, using
    Source.CAPITAL. `violates_kind` does not refuse it, because CAPITAL is not a
    *learned* source. Measured before the fix: declaring 40 moved caution from
    5.0 to 40.0 and danger from 10.0 to 80.0 — the detector that says "this
    position is dangerously large" went quiet for exactly the traders taking the
    largest positions.
    """
    loose = resolve_thresholds(profile=_profile(max_position_size=40))
    assert loose.get("max_position_pct_caution") == 5.0
    assert loose.get("max_position_pct_danger") == 10.0

    why = loose.explain("max_position_pct_caution").detail or ""
    assert "safety bound" in why, "a held threshold must say that it was held"


def test_a_declared_size_may_still_tighten():
    """
    The fix bounds looseness only. A trader who declares a 3% cap still gets
    alerts at 3% — removing that would be silently dropping working behaviour.
    """
    tight = resolve_thresholds(profile=_profile(max_position_size=3))
    assert tight.get("max_position_pct_caution") == 3.0
    assert tight.get("max_position_pct_danger") == 6.0


@pytest.mark.parametrize("declared,expected_caution", [
    (3, 3.0), (4, 4.0), (5, 5.0), (10, 5.0), (25, 5.0), (40, 5.0),
])
def test_the_safety_line_is_monotone_and_capped(declared, expected_caution):
    ts = resolve_thresholds(profile=_profile(max_position_size=declared))
    assert ts.get("max_position_pct_caution") == expected_caution


def test_every_universal_safety_threshold_is_its_own_bound():
    """
    Definitional, not a tuning choice: the Kind means "objective danger, never
    personalised", so the universal value IS the loosest it may become. This is
    what makes the guarantee general instead of a patch on the one key that was
    found to be reachable.
    """
    safety = [k for k, s in THRESHOLD_SPECS.items() if s.kind is Kind.UNIVERSAL_SAFETY]
    assert safety, "no universal-safety thresholds — the audit's subject vanished"
    for key in safety:
        bound, why = bound_for(key)
        assert bound is not None, f"{key} is UNIVERSAL_SAFETY with no bound"
        assert bound == float(THRESHOLD_SPECS[key].fallback)
        assert why, f"{key} has a bound with no reason"


@pytest.mark.parametrize("key", [
    k for k, s in THRESHOLD_SPECS.items() if s.kind is Kind.UNIVERSAL_SAFETY
])
def test_no_safety_threshold_can_be_pushed_past_its_bound(key):
    spec = THRESHOLD_SPECS[key]
    bound = float(spec.fallback)
    looser = bound * 4 if spec.sensitivity is Sensitivity.HIGHER_IS_LOOSER else bound / 4
    clamped, why = clamp_to_bound(key, looser)
    assert clamped == bound, f"{key} accepted a looser value than its bound"
    assert why is not None


def test_learned_sources_are_still_refused_outright():
    """The original invariant. The bound is a second line, not a replacement."""
    for src in (Source.HISTORY, Source.SESSION, Source.POPULATION):
        assert violates_kind(Kind.UNIVERSAL_SAFETY, src) is not None
        assert violates_kind(Kind.USER_RULE, src) is not None
        assert violates_kind(Kind.PRODUCT_POLICY, src) is not None


def test_the_declared_rule_is_not_lost_when_the_bound_holds():
    """
    Blocking the safety override must not remove the trader's rule. It is a
    RULE_FIELD in constitution_service and is still enforced there.
    """
    from app.services.constitution_service import RULE_FIELDS

    assert "max_position_size" in RULE_FIELDS
    ts = resolve_thresholds(profile=_profile(max_position_size=40))
    assert ts.get("max_position_size") == 40


# ── 2. personalisation actually resolves ───────────────────────────────────

@pytest.mark.parametrize("key,metric", sorted(ACTUALLY_PERSONALISED.items()))
def test_personalised_thresholds_really_personalise(key, metric):
    cold = resolve_thresholds()
    warm = resolve_thresholds(profile=_profile(detected_patterns={"baseline": BASELINE_V2}))

    r = warm.explain(key)
    assert r is not None, f"{key} has no provenance"
    assert r.source is Source.HISTORY, (
        f"{key} did not resolve from history — personalisation is broken"
    )
    assert warm.get(key) != cold.get(key) or r.confidence > 0, (
        f"{key} claims history but is indistinguishable from the default"
    )


def test_registry_classification_matches_reality():
    """
    THE INVARIANT THAT REPLACES THE GUARD PATTERN 11 EMPTIED.

    `test_declaring_direction_never_overwrites_an_existing_classification` named
    specific keys and required them to keep their Kind. Its last key went with
    `direction_instability`, leaving it looping over nothing.

    This is the same guarantee stated as a property rather than a list, so it
    cannot be emptied by a retirement: whatever the registry SAYS a threshold is,
    resolution must be allowed to do. A Kind that forbids the source its own key
    actually uses is the failure mode — it would silently refuse the resolution
    at runtime and fall back, with only a log line.
    """
    warm = resolve_thresholds(profile=_profile(detected_patterns={"baseline": BASELINE_V2}))
    offenders = []
    for key, r in warm.meta.items():
        reason = violates_kind(kind_for(key), r.source)
        if reason is not None:
            offenders.append(f"{key}: {kind_for(key).value} <- {r.source.value}")
    assert offenders == [], (
        "the registry forbids a resolution that actually happens: " + "; ".join(offenders)
    )


def test_the_personalise_flag_still_governs_only_the_registry_path():
    """
    `personalise` means "the registry-driven path is switched on for this key,
    behind a detector review and a replay". It does NOT mean "this threshold is
    personalised somewhere".

    The distinction is the whole finding. Four thresholds ARE personalised, by
    hand-written `place()` calls in `_apply_history_v2` that predate the registry
    and never consult it. Setting personalise=True on them was tried during this
    change and reverted: it would have swapped one false statement for another,
    and two existing tests correctly rejected it.

    So the flag stays False everywhere, and the fact that hand-wiring exists
    outside it is recorded here rather than hidden.
    """
    assert not [k for k, s in THRESHOLD_SPECS.items() if s.personalise], (
        "personalise=True implies the registry drives resolution for that key, "
        "and it does not — the resolver never reads spec.metric"
    )
    warm = resolve_thresholds(profile=_profile(detected_patterns={"baseline": BASELINE_V2}))
    hand_wired = {k for k in ACTUALLY_PERSONALISED
                  if (warm.explain(k) or SimpleNamespace(source=None)).source is Source.HISTORY}
    assert hand_wired == set(ACTUALLY_PERSONALISED), (
        "a threshold stopped being personalised by the hand-written wiring: "
        f"{sorted(set(ACTUALLY_PERSONALISED) - hand_wired)}"
    )


def test_specs_that_only_declare_availability_resolve_globally():
    """
    The other PERSONAL_BASELINE specs mean "personalisation is available", not
    "is enabled" — the module docstring is explicit. They must therefore resolve
    from the repo constant, not from history.
    """
    warm = resolve_thresholds(profile=_profile(detected_patterns={"baseline": BASELINE_V2}))
    for key, spec in THRESHOLD_SPECS.items():
        if spec.kind is not Kind.PERSONAL_BASELINE:
            continue
        if key in ACTUALLY_PERSONALISED:
            continue   # hand-wired outside the registry path; covered above
        r = warm.explain(key)
        if r is None:
            continue
        assert r.source is not Source.HISTORY, (
            f"{key} has personalise=False but resolved from history"
        )


def test_every_personalised_key_names_a_metric_that_is_produced():
    """
    The defect four pattern reviews kept finding, as a test. A key that is
    switched ON must name a metric something actually writes.
    """
    import inspect

    from app.services import baseline_service

    src = inspect.getsource(baseline_service)
    for key, metric in ACTUALLY_PERSONALISED.items():
        assert metric in src, (
            f"{key} is personalise=True but nothing produces {metric}"
        )


# ── 3. cold start and fallbacks ────────────────────────────────────────────

def test_cold_start_claims_nothing_personal():
    cold = resolve_thresholds()
    assert cold.personal_keys() == {}, "a cold start must not claim personal values"


def test_cold_start_uses_the_declared_fallback_for_personalised_keys():
    cold = resolve_thresholds()
    for key in ACTUALLY_PERSONALISED:
        assert cold.get(key) == THRESHOLD_SPECS[key].fallback, (
            f"{key} cold-starts at something other than its declared fallback"
        )


def test_a_profile_without_a_baseline_still_falls_back():
    ts = resolve_thresholds(profile=_profile())
    for key in ACTUALLY_PERSONALISED:
        r = ts.explain(key)
        assert r is None or r.source is not Source.HISTORY


def test_an_empty_baseline_does_not_personalise():
    ts = resolve_thresholds(profile=_profile(
        detected_patterns={"baseline": {"version": 2, "metrics": {}}}))
    for key in ACTUALLY_PERSONALISED:
        r = ts.explain(key)
        assert r is None or r.source is not Source.HISTORY


# ── 4. the registry describes the resolver ─────────────────────────────────

def test_no_universal_safety_key_is_missing_from_the_registry():
    """
    `kind_for()` returns FALLBACK for an unregistered key, and FALLBACK permits
    learned sources. So an unregistered safety-critical threshold would be
    silently personalisable. Anything the resolver writes that is safety-shaped
    must be declared.
    """
    import inspect
    import re

    import app.core.threshold_resolution as tr

    written = set(re.findall(r'put\(\s*"([a-z_0-9]+)"', inspect.getsource(tr)))
    written |= set(re.findall(r'place\(\s*"([a-z_0-9]+)"', inspect.getsource(tr)))
    for key in written:
        if key.startswith("max_position_pct") or key.startswith("premium_loss"):
            assert key in THRESHOLD_SPECS, (
                f"{key} looks safety-shaped and is not in the registry, so it "
                f"defaults to the permissive FALLBACK kind"
            )
