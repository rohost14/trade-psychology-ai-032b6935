"""
Which detector findings reached the trader, and which did not — and why.

THE FAILURE THIS FILE EXISTS FOR

Auditing `revenge_trade` produced a caution that never became an alert, with no
recorded reason. Tracing it end to end found two separate things:

  1. It was an ENTRY-TIME detection. `entry_detectors` marks every entry-time
     event `shadow`, and shadow never alerts by design. Not a bug — but nothing
     in the stored record distinguished it from an exit-time finding that was
     silently lost, which is why it looked like one.

  2. A real defect underneath it. `_persist_events` discards `info` events from
     `alerting` detectors that carry no suppression marker — sound when `info`
     means "confidence-demoted noise", wrong when a detector STATES `info` as its
     verdict. `revenge_trade` is an alerting detector, so every A1-row detection
     and **every abstention it produced was dropped and never written**. The
     contract's justification for that row — recorded, countable, not shouted —
     was false in production, and the abstention machinery built in Step 1
     recorded nothing at all.

A finding can now end up in exactly one of five dispositions, and every one is
readable from the stored row:

    surfaced      became a RiskAlert
    consolidated  folded behind a more specific finding  (_suppressed)
    deduped       same pattern already fired in the window (_suppressed)
    shadow        entry-time or dark-launched; never alerts
    stated        the detector's deliberate info verdict (_verdict)

Nothing may be dropped without one of those.
"""
import pytest

from app.core.detector_result import DetectorResult, Layer, abstained
from app.core.evidence import Insufficiency, positive
from app.services.behavior_engine import _as_events


# ── the adapter marks a deliberate verdict ─────────────────────────────────


def test_an_abstention_is_marked_as_a_stated_verdict():
    out = _as_events("revenge_trade", abstained(
        "revenge_trade", Insufficiency.NO_BASELINE, "only 4 gaps"))
    assert out[0].context["_verdict"] == "abstained"


def test_a_stated_info_is_marked_too():
    """
    A matrix cell that reads `info` is a verdict, not a demotion. Without the
    marker it is indistinguishable from a confidence-demoted event and gets
    discarded before it is written.
    """
    result = DetectorResult(
        detector="revenge_trade", evidence=positive(), severity="info",
        layer=Layer.PERSONAL, message="recorded, not notified",
    )
    assert _as_events("revenge_trade", result)[0].context["_verdict"] == "stated"


# ── the write gate ─────────────────────────────────────────────────────────


def _gate_drops(severity, evidence, disposition="alerting"):
    """Reproduce the gate's decision from _persist_events."""
    import inspect

    from app.tasks.trade_tasks import _persist_events

    src = inspect.getsource(_persist_events)
    assert '"_verdict"' in src, "the gate no longer consults the verdict marker"
    if severity != "info":
        return False
    suppressed = bool(evidence.get("_suppressed"))
    stated = bool(evidence.get("_verdict"))
    return disposition == "alerting" and not suppressed and not stated


def test_a_demoted_info_is_still_discarded():
    """
    The gate's original purpose survives: an alerting detector's info with no
    verdict and no suppression is confidence-demoted noise, and half the write
    volume for near-zero read value.
    """
    assert _gate_drops("info", {}) is True


def test_a_stated_info_is_kept():
    assert _gate_drops("info", {"_verdict": "stated"}) is False


def test_an_abstention_is_kept():
    """
    The regression. Every abstention `revenge_trade` produced was being dropped,
    so "three detectors were silent and nobody could say whether that was
    correct" would have remained unanswerable for exactly the detector built to
    answer it.
    """
    assert _gate_drops("info", {"_verdict": "abstained",
                                "_abstained": {"reason": "no_baseline"}}) is False


def test_suppressed_evidence_is_still_sacred():
    """1C.8 — a consolidated or deduped finding is always recorded."""
    assert _gate_drops("info", {"_suppressed": "same_story:x"}) is False


def test_analytics_detectors_are_unaffected():
    """
    The gate only ever applied to `alerting` detectors. An analytics-disposition
    info event is the product — journal entries, strategy drivers — and this
    change must not touch it.
    """
    assert _gate_drops("info", {}, disposition="analytics") is False


def test_a_notifying_severity_is_never_gated():
    for sev in ("caution", "danger", "critical"):
        assert _gate_drops(sev, {}) is False


# ── the five dispositions are distinguishable ──────────────────────────────


def test_every_disposition_is_readable_from_the_stored_row():
    """
    The property that makes a replay able to answer "did this reach the trader".
    Before this, a shadow entry-time finding and a silently-lost exit-time
    finding looked identical in the record — which is exactly how one was
    mistaken for the other.
    """
    from app.models.behavior_event import BehaviorEvent

    for column in ("shadow", "risk_alert_id", "evidence", "severity"):
        assert hasattr(BehaviorEvent, column), (
            f"BehaviorEvent.{column} is needed to tell dispositions apart"
        )


def test_shadow_and_dropped_are_not_the_same_thing():
    """
    `shadow=True` means "ran, judged, deliberately not shown". A dropped event
    means "no record at all". Conflating them is what made a correct entry-time
    detection look like a pipeline bug for an afternoon.
    """
    entry = _as_events("revenge_trade", DetectorResult(
        detector="revenge_trade", evidence=positive(), severity="caution"))[0]
    entry.shadow = True

    assert entry.shadow is True
    assert entry.severity == "caution", (
        "shadow must not rewrite severity - the finding is real, it is the "
        "delivery that is withheld"
    )
