"""
Phase 4 — the measurement the product never had.

28 detectors and zero accuracy metrics. That absence is why two of the defects
in docs/VOCABULARY_AUDIT.md survived for months: every WhatsApp alert falling
back to generic text, and the most common alert opening an empty panel, are
both invisible without an instrument.

These are pure functions over rows that already exist, so the tests are about
the judgement calls: what counts as measurable, what a thin sample is allowed to
claim, and which absences must read as "no data" rather than as a good result.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.services.detection_quality import (
    LATENCY_GATE_SECONDS, MIN_ALERTS_FOR_RATE, latency_seconds, percentile,
    summarise_latency, summarise_precision, summarise_shadow,
)

NOW = datetime(2026, 8, 9, 10, 0, tzinfo=timezone.utc)


def alert(seconds=1.0, lifecycle="post", pattern="revenge_trade",
          outcome=None, acknowledged=False, detected=None, created=None):
    detected = detected if detected is not None else NOW
    created = created if created is not None else (
        None if seconds is None else detected + timedelta(seconds=seconds)
    )
    return SimpleNamespace(
        pattern_type=pattern, lifecycle=lifecycle,
        detected_at=detected, created_at=created,
        outcome=outcome, acknowledged_at=NOW if acknowledged else None,
    )


# ── Percentiles ──────────────────────────────────────────────────────────────

def test_empty_sample_has_no_percentile():
    """None, not 0 — "no data" and "instant" are opposite conclusions."""
    assert percentile([], 50) is None
    assert percentile([], 95) is None


def test_single_sample_is_its_own_percentile():
    assert percentile([2.5], 50) == 2.5
    assert percentile([2.5], 95) == 2.5


def test_percentiles_are_ordered():
    values = [float(i) for i in range(1, 101)]
    assert percentile(values, 50) < percentile(values, 95)
    assert percentile(values, 95) <= max(values)


# ── Latency ──────────────────────────────────────────────────────────────────

def test_latency_is_trade_close_to_alert_written():
    assert latency_seconds(alert(seconds=3.0)) == 3.0


def test_live_alerts_are_excluded_from_latency():
    """
    An alert raised while the position is open sets detected_at to the moment
    it fired, so its latency is zero by construction. Including them would
    report a pipeline that looks instant because half the sample measures
    nothing.
    """
    assert latency_seconds(alert(seconds=0.0, lifecycle="live")) is None


def test_negative_latency_is_discarded_not_reported_as_fast():
    """Clock skew or a backfill, not a fast pipeline."""
    a = alert()
    a.created_at = a.detected_at - timedelta(seconds=5)
    assert latency_seconds(a) is None


def test_missing_timestamps_are_not_measurable():
    assert latency_seconds(alert(seconds=None)) is None


def test_latency_summary_reports_the_gate():
    summary = summarise_latency([alert(seconds=s) for s in (1, 2, 3, 4)])
    assert summary["alerts_measured"] == 4
    assert summary["gate_seconds"] == LATENCY_GATE_SECONDS
    assert summary["over_gate"] == 0
    assert summary["meets_gate"] is True


def test_latency_summary_flags_breaches():
    summary = summarise_latency([alert(seconds=s) for s in (1, 2, 30)])
    assert summary["over_gate"] == 1
    assert summary["meets_gate"] is False
    assert summary["max_seconds"] == 30.0


def test_no_measurable_alerts_does_not_pass_the_gate():
    """
    The important one. An empty sample has not met the gate, it has said
    nothing about it — and a metric that reports success on no data is how a
    broken pipeline looks healthy.
    """
    summary = summarise_latency([alert(lifecycle="live") for _ in range(5)])
    assert summary["alerts_measured"] == 0
    assert summary["meets_gate"] is None
    assert summary["alerts_excluded_live"] == 5


# ── Precision proxy ──────────────────────────────────────────────────────────

def mute(pattern, account="a1"):
    return SimpleNamespace(pattern_type=pattern, broker_account_id=account)


def test_not_useful_rate_is_computed_per_detector():
    alerts = [alert(outcome="not_useful") for _ in range(3)] + [alert() for _ in range(7)]
    row = summarise_precision(alerts, [], accounts_seen=1)[0]
    assert row["alerts"] == 10
    assert row["not_useful"] == 3
    assert row["not_useful_rate"] == 0.3


def test_thin_samples_are_marked_insignificant():
    """
    A 100% not-useful rate off one alert is not a finding. The rate is still
    reported, but flagged, so a reader cannot mistake it for a headline.
    """
    rows = summarise_precision([alert(outcome="not_useful")], [], accounts_seen=1)
    assert rows[0]["not_useful_rate"] == 1.0
    assert rows[0]["significant"] is False


def test_sufficient_samples_are_marked_significant():
    alerts = [alert() for _ in range(MIN_ALERTS_FOR_RATE)]
    assert summarise_precision(alerts, [], accounts_seen=1)[0]["significant"] is True


def test_mute_rate_uses_accounts_that_saw_an_alert():
    """
    Dividing by all accounts would flatter every rate with users who were never
    shown anything.
    """
    alerts = [alert(pattern="fomo_entry") for _ in range(10)]
    mutes = [mute("fomo_entry", f"a{i}") for i in range(4)]
    row = summarise_precision(alerts, mutes, accounts_seen=8)[0]
    assert row["muted_by_accounts"] == 4
    assert row["mute_rate"] == 0.5


def test_a_muted_pattern_with_no_alerts_still_appears():
    """
    Muting is the strongest signal we get — "never show me this again". A
    pattern silenced by everyone would otherwise vanish from the report
    precisely because it stopped being shown.
    """
    rows = summarise_precision([], [mute("no_stoploss")], accounts_seen=5)
    assert rows[0]["detector"] == "no_stoploss"
    assert rows[0]["muted_by_accounts"] == 1
    assert rows[0]["not_useful_rate"] is None


def test_worst_detector_sorts_first():
    """The point of the list is finding the one to fix."""
    alerts = ([alert(pattern="good") for _ in range(10)]
              + [alert(pattern="bad", outcome="not_useful") for _ in range(10)])
    rows = summarise_precision(alerts, [], accounts_seen=1)
    assert rows[0]["detector"] == "bad"


def test_no_accounts_seen_yields_no_mute_rate():
    rows = summarise_precision([], [mute("x")], accounts_seen=0)
    assert rows[0]["mute_rate"] is None


# ── Shadow readout ───────────────────────────────────────────────────────────

def event(detector="fomo_entry", severity="danger"):
    return SimpleNamespace(detector=detector, severity=severity)


def test_shadow_counts_what_would_have_alerted():
    """
    The flag machinery was built for promote-on-parity and never given a
    readout, so "parity holds" was never checkable.
    """
    events = [event(severity="danger"), event(severity="caution"), event(severity="info")]
    summary = summarise_shadow(events)
    assert summary["events"] == 3
    assert summary["would_have_alerted"] == 2      # info is evidence, not an alert


def test_shadow_groups_by_detector():
    events = [event("a"), event("a"), event("b")]
    summary = summarise_shadow(events)
    assert summary["detectors_in_shadow"] == 2
    assert summary["by_detector"][0]["detector"] == "a"


def test_shadow_records_the_severity_mix():
    events = [event(severity="critical"), event(severity="danger"), event(severity="danger")]
    row = summarise_shadow(events)["by_detector"][0]
    assert row["severities"] == {"critical": 1, "danger": 2}


def test_no_shadow_detectors_reports_zero_not_an_error():
    summary = summarise_shadow([])
    assert summary == {"detectors_in_shadow": 0, "events": 0,
                       "would_have_alerted": 0, "by_detector": []}


# ── "Planned" is its own signal ──────────────────────────────────────────────
# Phase 5. `not_useful` conflated two opposite statements: "your detection is
# wrong" and "I meant to do that". The second is not a precision problem at all
# — it is an accurate detector telling this trader something they already knew.

def test_planned_is_counted_separately_from_not_useful():
    alerts = ([alert(outcome="planned") for _ in range(4)]
              + [alert(outcome="not_useful") for _ in range(2)]
              + [alert() for _ in range(4)])
    row = summarise_precision(alerts, [], accounts_seen=1)[0]
    assert row["planned"] == 4
    assert row["not_useful"] == 2
    assert row["planned_rate"] == 0.4
    assert row["not_useful_rate"] == 0.2


def test_planned_does_not_inflate_the_false_positive_rate():
    """
    The whole reason for the fourth option. A detector firing accurately on a
    deliberate strategy must not look like one firing on nothing — they need
    different fixes.
    """
    alerts = [alert(outcome="planned") for _ in range(10)]
    row = summarise_precision(alerts, [], accounts_seen=1)[0]
    assert row["not_useful_rate"] == 0.0
    assert row["planned_rate"] == 1.0


def test_a_detector_with_no_feedback_has_zero_rates_not_null():
    alerts = [alert() for _ in range(5)]
    row = summarise_precision(alerts, [], accounts_seen=1)[0]
    assert row["planned_rate"] == 0.0
    assert row["not_useful_rate"] == 0.0
