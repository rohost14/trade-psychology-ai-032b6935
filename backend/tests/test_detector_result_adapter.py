"""
The engine accepts both detector contracts during the migration.

WHY THIS STEP EXISTS SEPARATELY

Twenty-seven detectors return `Optional[DetectedEvent]`. One is about to start
returning `DetectorResult`, which additionally carries which layer judged the
trade, the measurements behind the verdict, and — the reason the type exists —
the difference between "did not happen" and "could not tell".

Converting the engine and the detector in one change would mean a failure could
be in either. So the engine learns the new type first, while nothing returns it,
and that step is behaviour-neutral by construction.

THE ABSTENTION DECISION THESE TESTS PIN

An abstention is recorded as an `info` event carrying its reason. `info` never
notifies, so nothing a trader sees changes — but "three detectors were silent
across 203 sessions and nobody could say whether that was correct" becomes a
countable question instead of an unanswerable one.

A NEGATIVE result records nothing, exactly as `None` does today. Recording every
non-detection for 27 detectors on every trade would be write amplification with
no reader.
"""
import pytest

from app.core.detector_result import DetectorResult, Layer, abstained, not_detected
from app.core.evidence import Insufficiency, positive
from app.core.measurements import Measurement
from app.core.account_risk import Quality
from app.services.behavior_engine import DetectedEvent, _as_events


def test_none_still_means_nothing_recorded():
    assert _as_events("d", None) is None


def test_a_detected_event_passes_through_untouched():
    e = DetectedEvent(event_type="d", severity="danger", message="m")
    out = _as_events("d", e)
    assert out == [e]
    assert out[0] is e, "the existing contract must not be copied or rebuilt"


def test_a_list_passes_through():
    """The constitution detector emits one event per rule breached."""
    events = [
        DetectedEvent(event_type="d", severity="caution", message="a"),
        DetectedEvent(event_type="d", severity="danger", message="b"),
    ]
    assert _as_events("d", events) == events


def test_a_negative_result_records_nothing():
    assert _as_events("d", not_detected("d", "no loss to react to")) is None


def test_an_abstention_is_recorded_as_info_with_its_reason():
    result = abstained("d", Insufficiency.NO_BASELINE, "only 4 gaps observed")
    out = _as_events("d", result)

    assert out is not None, "an abstention must be recorded, not dropped"
    event = out[0]
    assert event.severity == "info", "an abstention must never notify"
    assert event.context["_abstained"]["reason"] == "no_baseline"
    assert "4 gaps" in event.context["_abstained"]["detail"]


def test_an_abstention_gets_its_own_idempotency_discriminator():
    """
    Otherwise an abstention and a real detection on the same trade collide on the
    idempotency key, and whichever arrives second is silently dropped.
    """
    out = _as_events("d", abstained("d", Insufficiency.MISSING_INPUT))
    assert out[0].discriminator == "abstained"


def test_a_positive_result_becomes_an_alertable_event():
    result = DetectorResult(
        detector="d",
        evidence=positive("fired"),
        layer=Layer.SAFETY,
        severity="danger",
        confidence=80.0,
        message="you re-entered four minutes after a loss",
    )
    event = _as_events("d", result)[0]

    assert event.severity == "danger"
    assert event.confidence == 80.0
    assert event.message.startswith("you re-entered")


def test_the_layer_that_judged_it_survives_into_the_record():
    """
    A safety finding and a personal-deviation finding are different claims. If
    the layer is lost here, "normal is not safe" stops being checkable
    downstream.
    """
    result = DetectorResult(
        detector="d", evidence=positive(), layer=Layer.SAFETY, severity="danger"
    )
    assert _as_events("d", result)[0].context["_layer"] == "safety"


def test_measurements_survive_with_their_denominators():
    """
    The measurement IS the explanation. A ratio without the thing it was divided
    by cannot be checked, and cannot be described to a trader honestly.
    """
    result = DetectorResult(
        detector="d",
        evidence=positive(),
        severity="caution",
        measurements={
            "loss_vs_trade": Measurement(
                value=0.8,
                denominator=15000.0,
                denominator_label="the premium you paid",
                quality=Quality.GOOD,
            )
        },
    )
    stored = _as_events("d", result)[0].context["_measurements"]["loss_vs_trade"]

    assert stored["value"] == 0.8
    assert stored["denominator"] == 15000.0
    assert stored["denominator_label"] == "the premium you paid"


def test_an_unmeasurable_measurement_is_recorded_as_such():
    """`value is None` is a real answer and must not be flattened to zero."""
    result = DetectorResult(
        detector="d",
        evidence=positive(),
        severity="info",
        measurements={
            "loss_vs_account": Measurement(None, None, None, Quality.UNKNOWN)
        },
    )
    stored = _as_events("d", result)[0].context["_measurements"]["loss_vs_account"]
    assert stored["value"] is None
    assert stored["quality"] == Quality.UNKNOWN.value


def test_an_unknown_return_type_is_logged_and_dropped(caplog):
    """A detector returning nonsense must not take the whole analysis down."""
    assert _as_events("d", "not a result") is None
    assert "neither a DetectedEvent nor a DetectorResult" in caplog.text


def test_evidence_still_refuses_to_be_truthy():
    """
    The guard that makes all of this worth doing: `if evidence:` would treat an
    abstention as a "no".
    """
    result = abstained("d", Insufficiency.NO_BASELINE)
    with pytest.raises(TypeError):
        bool(result.evidence)
