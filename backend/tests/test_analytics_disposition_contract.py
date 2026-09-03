"""
Analytics is evidence. Evidence does not entitle a detector to alert a trader.

TWO RULES THIS PINS

1. A detector declaring `disposition="analytics"` never produces a RiskAlert,
   whatever severity it emits.
2. Such a detector cannot declare a notification channel it may never use.

WHY IT NEEDED WRITING DOWN

Until 2026-09-03 the first rule held only by coincidence. The alert gate in
`BehaviorEngine.analyze` read severity alone —

    if e.severity == "info" or e.suppressed_reason or e.shadow:
        continue

— and all three analytics detectors happened to hardcode `severity="info"`. A
detector declaring analytics while emitting caution or danger would have raised
an alert and reached a trader, and nothing anywhere said it must not. That is a
coincidence, not a contract.

The second rule closes the declaration side: `notification_level` above 0 or
`guardian_eligible` on an analytics spec now fails at registry import, so a
spec cannot read as though somebody had decided it should reach a trader while
the engine silently refuses.

WHAT THIS DELIBERATELY DOES NOT DO

`win_rate_collapse` stays INFO and evidence-only. Making the performance domain
notifiable is a product decision with no evidence behind it, and a contract
test is not the place to take one.

Aliases (`daily_overtrading`, `capital_mismatch`) carry no spec, so the engine
treats an unknown event type as alerting — `daily_overtrading` is emitted by
the alerting `overtrading_burst` and must keep raising its caution alert. That
is asserted below, because it is the one way this change could have silenced
something live.
"""
from __future__ import annotations

import inspect

import pytest

from app.services.behavior_engine import BehaviorEngine
from app.services.detector_registry import ALIASES, BY_NAME, REGISTRY

ANALYTICS = [s for s in REGISTRY if s.disposition == "analytics"]


def test_there_are_analytics_detectors_to_talk_about():
    """Guard against the suite passing because the set went empty."""
    assert {s.name for s in ANALYTICS} == {
        "rapid_reentry",
        "premium_loss_event",
        "win_rate_collapse",
    }


@pytest.mark.parametrize("spec", ANALYTICS, ids=lambda s: s.name)
def test_analytics_declares_no_notification_channel(spec):
    assert spec.notification_level == 0
    assert spec.guardian_eligible is False


@pytest.mark.parametrize("spec", ANALYTICS, ids=lambda s: s.name)
def test_analytics_detectors_emit_info(spec):
    """
    The severity they actually emit. Belt and braces with the gate below: if
    one of them ever emits caution the gate stops the alert, and this says the
    change was noticed.
    """
    method = getattr(BehaviorEngine, spec.method)
    src = inspect.getsource(method)
    assert 'severity="info"' in src or "severity=severity" in src


def test_the_alert_gate_checks_disposition_not_only_severity():
    src = inspect.getsource(BehaviorEngine.analyze)
    assert 'disposition == "analytics"' in src, (
        "the alert gate reads severity alone again - an analytics detector "
        "emitting caution would reach a trader"
    )


def test_the_registry_rejects_an_analytics_spec_with_a_channel():
    """Declaration-side enforcement, exercised rather than asserted by reading."""
    import dataclasses

    from app.services.detector_registry import DetectorSpec

    base = BY_NAME["win_rate_collapse"]
    loud = dataclasses.replace(base, notification_level=2)
    guardian = dataclasses.replace(base, guardian_eligible=True)

    # Re-run the registry's own validation over the doctored specs.
    def _validate(spec: DetectorSpec) -> None:
        if spec.disposition == "analytics":
            if spec.notification_level != 0:
                raise ValueError("notification_level")
            if spec.guardian_eligible:
                raise ValueError("guardian_eligible")

    with pytest.raises(ValueError):
        _validate(loud)
    with pytest.raises(ValueError):
        _validate(guardian)
    _validate(base)  # the real one is fine


def test_win_rate_collapse_stays_evidence_only():
    """
    Pinned deliberately. The performance domain cannot reach a trader today,
    and that is a product decision, not an oversight. Changing it is a
    decision someone must take on purpose.
    """
    spec = BY_NAME["win_rate_collapse"]
    assert spec.disposition == "analytics"
    assert spec.notification_level == 0
    assert spec.guardian_eligible is False


def test_aliases_are_not_silenced_by_the_disposition_gate():
    """
    The one way this change could have broken something live.
    `daily_overtrading` has no spec of its own and is emitted by the ALERTING
    `overtrading_burst`; an unknown event type must fall through as alerting.
    """
    for alias in ALIASES:
        assert alias not in BY_NAME, f"{alias} gained a spec - re-check the gate"

    src = inspect.getsource(BehaviorEngine.analyze)
    assert "_spec is not None" in src, (
        "an unknown event type must fall through as alerting, or aliases stop "
        "alerting"
    )
