"""
Is the engine any good? — the measurement the product never had.

28 detectors, and until now zero accuracy metrics. `alert-response-stats` looks
like a quality metric but ranks by `took_anyway` and `ignored`, which measure
the trader's compliance, not our correctness. `not_useful` — the one field that
says we were wrong rather than they were — was accepted, stored, and read by
nothing. Shadow mode was built, wired to a flag table and an admin screen, and
never given a readout, so the promote decision had no evidence next to it.

That absence is why two of the defects in docs/VOCABULARY_AUDIT.md survived for
months: every WhatsApp alert falling back to generic text, and our most common
alert opening an empty panel, are both invisible without an instrument.

Everything here is a read over columns that already exist. No new storage, no
new pipeline — the raw material was always there, nobody was looking at it.

Three questions, three answers:

  latency    — how long from the trade closing to the alert existing
  precision  — how often the trader tells us the alert was not useful, and how
               often they mute the pattern outright
  shadow     — what a detector in shadow mode has been quietly producing
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

#: The review's proposed gate: event to alert in under five seconds.
LATENCY_GATE_SECONDS = 5.0

#: Below this, a rate is noise. Stated in the payload so the reader can see
#: which rows are actually saying something.
MIN_ALERTS_FOR_RATE = 10


def percentile(values: Sequence[float], p: float) -> Optional[float]:
    """
    Nearest-rank percentile. No numpy — this runs in an admin request.

    Returns None for an empty sample rather than 0, because "no data" and
    "instant" are very different answers and conflating them is how a broken
    metric looks healthy.
    """
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 3)
    k = max(0, min(len(ordered) - 1, int(round(p / 100 * len(ordered) + 0.5)) - 1))
    return round(ordered[k], 3)


def _raised_while_open(alert) -> bool:
    """
    Was this alert raised while the position was still open?

    Three signals, because none of them is sufficient alone. `lifecycle` is the
    obvious one and it is destroyed by the merge — linking a live alert to its
    completed trade rewrites the row to 'post'. The details markers survive
    that: `live` is stamped on every position-monitor alert at creation, and
    `at_entry` on the entry-rule checks.
    """
    if getattr(alert, "lifecycle", "post") == "live":
        return True
    details = getattr(alert, "details", None) or {}
    return bool(details.get("at_entry") or details.get("live"))


def latency_seconds(alert) -> Optional[float]:
    """
    Trade close → alert row written, in seconds.

    `detected_at` is the triggering trade's exit time and `created_at` is when
    we persisted the finding, so the difference is the real end-to-end lag.

    Only meaningful for post-hoc alerts. An alert raised while the position is
    open sets `detected_at` to the moment it fired, so its latency is zero by
    construction — including those would report a pipeline that looks instant
    because half the sample is measuring nothing.

    `lifecycle` alone is not enough to tell them apart. When the exit pass links
    a live alert to its completed trade it flips that row to 'post', so the
    near-zero delta would quietly re-enter the sample and reintroduce exactly
    the distortion this exclusion exists to prevent. A merged row is identified
    by its evidence rather than its lifecycle: entry-time detections carry
    `at_entry` in their details, and that marker survives the merge.
    """
    if _raised_while_open(alert):
        return None
    detected, created = alert.detected_at, alert.created_at
    if detected is None or created is None:
        return None
    delta = (created - detected).total_seconds()
    # A negative delta means clock skew or a backfill, not a fast pipeline.
    return delta if delta >= 0 else None


def summarise_latency(alerts: Sequence[Any]) -> Dict[str, Any]:
    samples = [s for s in (latency_seconds(a) for a in alerts) if s is not None]
    breaching = [s for s in samples if s > LATENCY_GATE_SECONDS]
    return {
        "alerts_measured": len(samples),
        # Counts merged rows too: they are 'post' by lifecycle but were raised
        # at entry, and reporting them as measured would overstate coverage.
        "alerts_excluded_live": sum(1 for a in alerts if _raised_while_open(a)),
        "p50_seconds": percentile(samples, 50),
        "p95_seconds": percentile(samples, 95),
        "max_seconds": round(max(samples), 3) if samples else None,
        "gate_seconds": LATENCY_GATE_SECONDS,
        "over_gate": len(breaching),
        # None, not True: an empty sample has not met the gate, it has said
        # nothing about it.
        "meets_gate": (len(breaching) == 0) if samples else None,
    }


def summarise_precision(
    alerts: Sequence[Any],
    mutes: Sequence[Any],
    accounts_seen: int,
) -> List[Dict[str, Any]]:
    """
    Per detector: how often the trader said it was not useful, and how often
    they silenced it.

    A mute is the strongest signal we get. Marking an alert not useful takes a
    tap on that alert; muting a pattern says "never show me this again" and
    costs the same tap. A pattern many accounts have muted is a pattern that is
    wrong for them, whatever its fire count says.
    """
    def _blank(name: str) -> Dict[str, Any]:
        return {"detector": name, "alerts": 0, "not_useful": 0, "planned": 0,
                "acknowledged": 0, "muted_by_accounts": 0}

    per: Dict[str, Dict[str, Any]] = {}
    for a in alerts:
        d = per.setdefault(a.pattern_type, _blank(a.pattern_type))
        d["alerts"] += 1
        if a.outcome == "not_useful":
            d["not_useful"] += 1
        elif a.outcome == "planned":
            d["planned"] += 1
        if a.acknowledged_at is not None:
            d["acknowledged"] += 1

    for m in mutes:
        d = per.setdefault(m.pattern_type, _blank(m.pattern_type))
        d["muted_by_accounts"] += 1

    rows = []
    for d in per.values():
        n = d["alerts"]
        rows.append({
            **d,
            "not_useful_rate": round(d["not_useful"] / n, 3) if n else None,
            # Kept apart from not_useful_rate on purpose. "Planned" means the
            # detection was CORRECT and the trader had already accounted for it
            # — a detector with a high planned rate is accurate and redundant,
            # which is a different problem from one that is wrong, and needs a
            # different fix. Folding them together would hide both.
            "planned_rate": round(d["planned"] / n, 3) if n else None,
            "mute_rate": (round(d["muted_by_accounts"] / accounts_seen, 3)
                          if accounts_seen else None),
            # Whether these rates mean anything yet. Rendering a 100% not-useful
            # rate off one alert as a headline is how a metric misleads.
            "significant": n >= MIN_ALERTS_FOR_RATE,
        })
    # Worst first: the point of this list is finding the detector to fix.
    rows.sort(key=lambda r: (-(r["not_useful_rate"] or 0), -r["muted_by_accounts"]))
    return rows


def summarise_shadow(events: Sequence[Any]) -> Dict[str, Any]:
    """
    What the detectors running in shadow have been producing.

    `DetectorSpec.default_mode`, the `detector_flags` table and
    `BehaviorEvent.shadow` were all built for a detector-by-detector migration —
    ship as shadow, promote once parity holds. Nothing ever reported what shadow
    produced, so "parity holds" was never checkable and the mechanism went
    unused. This is the missing half.
    """
    per: Dict[str, Dict[str, Any]] = {}
    for ev in events:
        d = per.setdefault(ev.detector, {
            "detector": ev.detector, "events": 0, "would_have_alerted": 0,
            "severities": {},
        })
        d["events"] += 1
        d["severities"][ev.severity] = d["severities"].get(ev.severity, 0) + 1
        # info is analytics-only evidence; anything above it would have been an
        # alert had the detector been live.
        if ev.severity != "info":
            d["would_have_alerted"] += 1

    rows = sorted(per.values(), key=lambda r: -r["would_have_alerted"])
    return {
        "detectors_in_shadow": len(rows),
        "events": sum(r["events"] for r in rows),
        "would_have_alerted": sum(r["would_have_alerted"] for r in rows),
        "by_detector": rows,
    }
