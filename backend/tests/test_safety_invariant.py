"""
A personal baseline may never weaken a universal safety bound.

THE INVARIANT

Personal history decides what is UNUSUAL for a trader. It never decides what is
SAFE. A habit is not a licence: the trader who overtrades every day must keep
being told so, for as long as they keep doing it.

This is the specific way a self-relative engine fails, and it fails silently —
the detector goes quiet for exactly the person it exists for. `daily_trade_limit`
resolving to the 75th percentile of someone's own daily trade counts is that
failure in one line.

WHY THESE TESTS EXIST AS THEY DO

The rule used to be asserted over the registry as it stood. That proves today's
constants and today's ladder agree; it proves nothing about a rung added next
month. So the rule now runs inside `put()`, at the moment a resolution is
attempted, and these tests drive real resolutions rather than inspecting a table.

They deliberately classify a threshold as `universal_safety` *in the test* rather
than relying on production classifications — because there are none yet, and a
test that passes only because the guarded set is empty proves nothing.
"""
import pytest

from app.core import safety_bounds
from app.core.threshold_registry import (
    Maturity,
    Sensitivity,
    THRESHOLD_SPECS,
    ThresholdSpec,
)
from app.core.threshold_resolution import Kind, Source, resolve_thresholds


class _Profile:
    """A trader with enough history for the ladder to reach rung 1."""

    def __init__(self, **metrics):
        self.detected_patterns = {
            "baseline": {
                "version": 2,
                "metrics": {
                    k: {"value": v, "confidence": 1.0, "n": 60}
                    for k, v in metrics.items()
                },
            }
        }
        self.trading_capital = None


def _classify(monkeypatch, key, **overrides):
    """Put one key into the registry with a chosen Kind/direction/bound."""
    spec = ThresholdSpec(
        key=key,
        kind=overrides.pop("kind", Kind.UNIVERSAL_SAFETY),
        fallback=overrides.pop("fallback", 3),
        meaning="test",
        maturity=Maturity.NONE,
        **overrides,
    )
    patched = dict(THRESHOLD_SPECS)
    patched[key] = spec
    monkeypatch.setattr(
        "app.core.threshold_registry.THRESHOLD_SPECS", patched, raising=True
    )
    monkeypatch.setattr(
        "app.core.threshold_registry.kind_for",
        lambda k, _p=patched: _p[k].kind if k in _p else Kind.FALLBACK,
        raising=True,
    )
    return spec


# ── The rule runs at resolution time, not only in a test ────────────────────


def test_history_cannot_move_a_universal_safety_threshold(monkeypatch):
    """
    The invariant itself. A trader whose own history says "six losses in a row is
    normal for me" must not thereby raise the bar on a safety threshold.
    """
    _classify(monkeypatch, "consecutive_loss_caution", fallback=3)

    resolved = resolve_thresholds(_Profile(loss_streak_p60=9.0, loss_streak_p85=12.0))

    assert resolved.values["consecutive_loss_caution"] == 3, (
        "personal history moved a universal_safety threshold — a habit became a "
        "licence"
    )


def test_the_refusal_is_recorded_not_silent(monkeypatch):
    """
    Refusing quietly would leave a detector running against a number nobody
    sanctioned, and no way to find out.
    """
    _classify(monkeypatch, "consecutive_loss_caution", fallback=3)

    resolved = resolve_thresholds(_Profile(loss_streak_p60=9.0))
    record = resolved.explain("consecutive_loss_caution")

    assert record is not None
    assert "refused" in (record.detail or "").lower()
    assert record.source is not Source.HISTORY


def test_a_personal_baseline_threshold_still_learns(monkeypatch):
    """
    The guard must not become a blanket ban. Personalisation is the point
    everywhere it is legitimate — only safety is off limits.
    """
    _classify(
        monkeypatch,
        "consecutive_loss_caution",
        kind=Kind.PERSONAL_BASELINE,
        fallback=3,
    )

    resolved = resolve_thresholds(_Profile(loss_streak_p60=9.0))

    assert resolved.values["consecutive_loss_caution"] > 3
    assert resolved.explain("consecutive_loss_caution").source is Source.HISTORY


# ── Bounds: the guarantee UNIVERSAL_FLOORS could not express ────────────────


def test_a_bound_stops_history_making_a_detector_quieter(monkeypatch):
    """
    The trader who overtrades every day has a high P75, so their limit rises and
    the detector goes silent for exactly the person it exists for. A bound is the
    only thing that stops it.
    """
    _classify(
        monkeypatch,
        "daily_trade_limit",
        kind=Kind.PERSONAL_BASELINE,
        fallback=10,
        sensitivity=Sensitivity.HIGHER_IS_LOOSER,
        safety_bound=15,
        bound_provenance="test",
    )

    resolved = resolve_thresholds(_Profile(daily_trades_p75=40.0))

    assert resolved.values["daily_trade_limit"] == 15, (
        "history pushed the limit past its safety bound"
    )
    assert "bound" in (resolved.explain("daily_trade_limit").detail or "")


def test_a_bound_works_in_the_other_direction_too(monkeypatch):
    """
    For a window, a SMALLER number is quieter — a narrow re-entry window catches
    fewer re-entries. The trader who always re-enters fast has a low P25, so
    their window shrinks and revenge_trade stops firing for the fastest
    re-enterer. Same failure, opposite arithmetic.
    """
    _classify(
        monkeypatch,
        "revenge_window_caution_min",
        kind=Kind.PERSONAL_BASELINE,
        fallback=20,
        sensitivity=Sensitivity.HIGHER_IS_STRICTER,
        safety_bound=10,
        bound_provenance="test",
    )

    resolved = resolve_thresholds(_Profile(reentry_after_loss_p25=2.0))

    assert resolved.values["revenge_window_caution_min"] == 10


def test_a_bound_without_a_declared_direction_is_not_enforced(monkeypatch):
    """
    A bound applied the wrong way silently inverts the guarantee it exists to
    provide. Refusing to act is the honest failure; guessing is not.
    """
    _classify(
        monkeypatch,
        "daily_trade_limit",
        kind=Kind.PERSONAL_BASELINE,
        fallback=10,
        sensitivity=Sensitivity.UNKNOWN,
        safety_bound=15,
        bound_provenance="test",
    )

    value, why = safety_bounds.clamp_to_bound("daily_trade_limit", 40)
    assert value == 40
    assert why is None


def test_a_bound_does_not_touch_a_value_on_the_safe_side(monkeypatch):
    _classify(
        monkeypatch,
        "daily_trade_limit",
        kind=Kind.PERSONAL_BASELINE,
        fallback=10,
        sensitivity=Sensitivity.HIGHER_IS_LOOSER,
        safety_bound=15,
        bound_provenance="test",
    )
    value, why = safety_bounds.clamp_to_bound("daily_trade_limit", 8)
    assert value == 8 and why is None


def test_the_bound_outranks_a_universal_floor(monkeypatch):
    """
    Ordering matters and is easy to get wrong. A floor raises a threshold to stop
    noise; a bound pulls it back to stop silence. The bound has to be the last
    word, or a floor could push a value past its own safety bound.
    """
    _classify(
        monkeypatch,
        "consecutive_loss_caution",
        kind=Kind.PERSONAL_BASELINE,
        fallback=1,
        sensitivity=Sensitivity.HIGHER_IS_LOOSER,
        safety_bound=2,
        bound_provenance="test",
    )

    # UNIVERSAL_FLOORS raises consecutive_loss_caution to 3; the bound says 2.
    resolved = resolve_thresholds(None)
    assert resolved.values["consecutive_loss_caution"] == 2


# ── Guards on the mechanism itself ─────────────────────────────────────────


def test_no_bound_has_been_filled_in_as_a_batch():
    """
    The point of the whole exercise. A ceiling is an architectural constraint;
    each value is a claim about one behaviour and has to be argued from that
    detector's evidence during its review.

    If this test starts failing, check the commit that added the bound also
    argued for it. Delete this test when the first reviewed bound lands — and
    only then, deliberately.
    """
    declared = {k: s.safety_bound for k, s in THRESHOLD_SPECS.items()
                if s.safety_bound is not None}
    assert declared == {}, (
        f"bounds appeared without a detector review: {declared}. A wall of "
        "ceilings is the same mistake as a wall of thresholds, pointing the "
        "other way."
    )


def test_a_declared_bound_must_carry_its_reason():
    """A bound without a justification is an arbitrary constant with a new name."""
    for key, spec in THRESHOLD_SPECS.items():
        if spec.safety_bound is not None:
            assert spec.bound_provenance, f"{key} declares a bound with no reason"
            assert spec.sensitivity is not Sensitivity.UNKNOWN, (
                f"{key} declares a bound but no direction, so it cannot be enforced"
            )


def test_detector_frames_are_deferred_not_guessed():
    """
    `frames` exists so the pattern review can fill it in one detector at a time.
    A bulk annotation pass would read as decisions somebody made.
    """
    from app.services.detector_registry import REGISTRY

    assert all(hasattr(spec, "frames") for spec in REGISTRY)
    assert not any(spec.frames for spec in REGISTRY), (
        "frames were assigned outside a detector review"
    )
