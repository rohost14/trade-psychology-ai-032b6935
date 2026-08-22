"""
The detector contract: which layer spoke, and whether it could see.

Two properties that cannot be expressed by the current return type and are the
reason this exists:

  - a SAFETY finding is a different claim from a PERSONAL one, and must not be
    suppressible by anything learned from the trader;
  - "did not happen" and "cannot tell" are different answers, and collapsing
    them is how a blind detector passes for a clean trader.
"""
import pytest

from app.core.account_risk import Quality
from app.core.detector_result import (
    DetectorResult,
    EpisodeHint,
    EpisodeRole,
    Layer,
    abstained,
    not_detected,
)
from app.core.evidence import Insufficiency, Verdict, positive
from app.core.measurements import loss_vs_trade, loss_vs_own_losses


def test_abstained_is_not_a_finding_and_never_an_alert():
    r = abstained("revenge_trade", Insufficiency.NO_BASELINE, "need 20 losses", have=3)
    assert r.abstained
    assert not r.fired
    assert r.evidence.basis["have"] == 3


def test_not_detected_is_a_finding():
    """
    What makes a clean session distinguishable from an unmonitored one. Three
    detectors were silent for 203 sessions and nothing could say which.
    """
    r = not_detected("revenge_trade", "no loss preceded this entry")
    assert not r.fired
    assert not r.abstained
    assert r.evidence.verdict is Verdict.NEGATIVE


def test_a_result_explains_itself_from_its_measurements():
    r = DetectorResult(
        detector="revenge_trade",
        evidence=positive("re-entered fast after a large loss"),
        layer=Layer.PERSONAL,
        severity="danger",
        confidence=70.0,
        measurements={
            "loss size": loss_vs_own_losses(3_000, [600] * 25, min_sample=20),
            "position": loss_vs_trade(3_000, 10_000),
        },
    )
    lines = r.explain()
    assert any("typical losing trade" in l for l in lines)
    assert any("put at risk" in l for l in lines)


def test_unmeasurable_inputs_are_omitted_from_the_explanation():
    """Never show a trader a line we could not compute."""
    r = DetectorResult(
        detector="x", evidence=positive(),
        measurements={"loss size": loss_vs_own_losses(1, [], min_sample=20)},
    )
    assert r.explain() == []


def test_severity_and_confidence_are_independent_fields():
    """
    A 60%-confident potentially account-ending exposure must be able to be
    high-severity. Anything deriving one from the other has conflated them.
    """
    r = DetectorResult(detector="x", evidence=positive(),
                       severity="critical", confidence=60.0)
    assert r.severity == "critical"
    assert r.confidence == 60.0


def test_the_layer_is_recorded_so_safety_can_be_protected():
    safety = DetectorResult(detector="x", evidence=positive(), layer=Layer.SAFETY)
    personal = DetectorResult(detector="y", evidence=positive(), layer=Layer.PERSONAL)
    assert safety.is_safety
    assert not personal.is_safety


def test_data_quality_defaults_to_good_but_is_expressible():
    assert DetectorResult(detector="x", evidence=positive()).data_quality is Quality.GOOD
    degraded = DetectorResult(detector="x", evidence=positive(),
                              data_quality=Quality.PARTIAL)
    assert degraded.data_quality is Quality.PARTIAL


# ---------------------------------------------------------------------------
# Episode interface — defined, deliberately not implemented
# ---------------------------------------------------------------------------

def test_episode_hint_exists_and_defaults_to_standalone():
    """
    The interface is available so detectors can declare a role now and
    consolidation can group on it later without a migration. Nothing consumes it
    yet, and the state machine is deliberately not built.
    """
    h = EpisodeHint()
    assert h.role is EpisodeRole.NONE
    assert h.key is None


def test_episode_roles_can_express_a_sequence():
    trigger = EpisodeHint(role=EpisodeRole.TRIGGER, key="NIFTY:2026-08-23", sequence=0)
    escalation = EpisodeHint(role=EpisodeRole.ESCALATION, key="NIFTY:2026-08-23", sequence=1)
    assert trigger.key == escalation.key
    assert trigger.sequence < escalation.sequence


def test_episode_key_is_not_a_database_id():
    """
    Intentionally a computable string (underlying + session), so episodes can be
    grouped without persistence when they are eventually built.
    """
    h = EpisodeHint(role=EpisodeRole.TRIGGER, key="NIFTY:2026-08-23")
    assert isinstance(h.key, str)
