"""
What a scenario is, and how one runs.

A scenario is a trader story plus **both halves of the assertion**:

    must_fire      the patterns that should be raised, at the stated severity
    must_not_fire  what a naive implementation would wrongly raise

The second half is the point. Twelve of the fifteen defects found reviewing this
week's work were false positives or silent suppressions — a suite that only
asserts presence would have passed on every one of them. Roughly half of this
catalogue is negative by design.
"""
from __future__ import annotations

import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .collect import collect_all, collect_step
from .harness import (
    IST, ensure_lab_account, frozen_clock, lab_environment, teardown_lab,
)
from .inject import Fill, inject


@dataclass
class Expect:
    """One assertion about a pattern."""
    pattern: str
    severity: Optional[str] = None      # None = any severity
    reason: str = ""                    # why this matters, shown in the UI
    #: must_fire only. `live` means the alert was raised while the position was
    #: still open. Untested until now, and it is the field the UI uses to decide
    #: whether an alert is actionable or a post-mortem.
    lifecycle: Optional[str] = None
    #: must_fire only. Whether this alert should reach the accountability
    #: partner. Asserting False matters more than True: the contract that
    #: protects the trader is the one that keeps ordinary noise away from
    #: someone they had to ask permission from.
    routes_to_guardian: Optional[bool] = None
    #: must_record only. Require the detection to have happened at ENTRY rather
    #: than after the position closed. Without it a scenario meant to prove
    #: entry-time detection passes on the exit-time detection of the same
    #: pattern, which is the opposite of what it set out to show.
    at_entry: bool = False


@dataclass
class Scenario:
    id: str
    title: str
    story: str                          # what the trader did, in a sentence
    fills: List[Fill]
    section: str = "misc"
    capital: float = 500_000
    profile: Dict[str, Any] = field(default_factory=dict)
    wall_clock: Optional[datetime] = None   # freeze; None = trade time is enough
    must_fire: List[Expect] = field(default_factory=list)
    must_not_fire: List[Expect] = field(default_factory=list)
    # Detectors that are analytics-only by design: `rapid_reentry` and
    # `opening_5min_trap` return a hard-coded `info` severity, so they are
    # recorded as evidence and deliberately never surface as alerts. Asserting
    # them with must_fire can never pass, and asserting nothing at all would let
    # the detector break silently — this third kind covers exactly that gap.
    must_record: List[Expect] = field(default_factory=list)
    #: Ceiling on total alerts. The noise budget is a product property, not a
    #: detail: a session that produces forty alerts has told the trader nothing,
    #: however correct each one is. Only a volume scenario can test it, because
    #: dedup and consolidation windows do not bind at five fills.
    max_alerts: Optional[int] = None
    #: Volume scenarios skip the per-fill snapshot. It costs three queries per
    #: fill, which is worth it to see which trade caused which alert and is
    #: pointless across two hundred of them.
    snapshot_steps: bool = True

    def as_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "title": self.title, "story": self.story,
            "section": self.section, "capital": self.capital,
            "fills": len(self.fills),
            "must_fire": [e.pattern for e in self.must_fire],
            "must_not_fire": [e.pattern for e in self.must_not_fire],
            "must_record": [e.pattern for e in self.must_record],
            "max_alerts": self.max_alerts,
        }


def _check(scenario: Scenario, alerts: List[Dict[str, Any]],
           suppressed: List[Dict[str, Any]] | None = None) -> List[Dict[str, Any]]:
    """Evaluate every kind of expectation and explain each outcome."""
    fired = {a["pattern_type"] for a in alerts}
    recorded: Dict[str, Dict[str, Any]] = {}
    for s in (suppressed or []):
        # A detector can be recorded twice in one scenario — once at entry, once
        # at exit. Keep the entry record: it is the stronger fact, and the last
        # writer would otherwise be whichever the query happened to return last.
        if s["detector"] not in recorded or s.get("at_entry"):
            recorded[s["detector"]] = s
    by_pattern: Dict[str, List[Dict[str, Any]]] = {}
    for a in alerts:
        by_pattern.setdefault(a["pattern_type"], []).append(a)

    results = []
    for exp in scenario.must_fire:
        got = by_pattern.get(exp.pattern, [])
        if not got:
            # Distinguish "the detector never triggered" from "it triggered and
            # something downstream stopped it". Those are completely different
            # bugs, and reporting both as "never fired" sent me looking in the
            # wrong half of the pipeline twice.
            held = recorded.get(exp.pattern)
            detail = f"detected, but never surfaced — {held['reason']}" if held else "never fired"
            results.append({"kind": "must_fire", "pattern": exp.pattern, "pass": False,
                            "detail": detail, "reason": exp.reason})
            continue
        if exp.severity:
            severities = {a["severity"] for a in got}
            ok = exp.severity in severities
            # Severity is not cosmetic: it drives guardian routing and the
            # critical tier, so the right pattern at the wrong level is a
            # failure, not a warning.
            results.append({
                "kind": "must_fire", "pattern": exp.pattern, "pass": ok,
                "detail": f"expected {exp.severity}, got {', '.join(sorted(severities))}",
                "reason": exp.reason,
            })
        elif exp.lifecycle is not None:
            seen = {a.get("lifecycle") for a in got}
            results.append({
                "kind": "must_fire", "pattern": exp.pattern,
                "pass": exp.lifecycle in seen,
                "detail": f"expected lifecycle {exp.lifecycle}, got {', '.join(sorted(str(x) for x in seen))}",
                "reason": exp.reason,
            })
        elif exp.routes_to_guardian is not None:
            routed = any(a.get("would_route_to_guardian") for a in got)
            results.append({
                "kind": "must_fire", "pattern": exp.pattern,
                "pass": routed == exp.routes_to_guardian,
                "detail": ("routes to guardian" if routed else "does not route to guardian")
                          + f" (expected {'routes' if exp.routes_to_guardian else 'no route'})",
                "reason": exp.reason,
            })
        else:
            results.append({"kind": "must_fire", "pattern": exp.pattern, "pass": True,
                            "detail": f"fired ({got[0]['severity']})", "reason": exp.reason})

    for exp in scenario.must_record:
        held = recorded.get(exp.pattern)
        if held and exp.at_entry and not held.get("at_entry"):
            ok, detail = False, ("detected, but only after the position closed — "
                                 "the entry-time check did not raise it")
        elif held:
            ok, detail = True, f"recorded as evidence — {held['reason']}"
        elif exp.pattern in fired:
            # Louder than expected. An analytics-only detector that starts
            # alerting is a regression in the noise budget, not an improvement.
            ok, detail = False, "surfaced as an ALERT — expected evidence only"
        else:
            ok, detail = False, "not detected at all"
        results.append({"kind": "must_record", "pattern": exp.pattern,
                        "pass": ok, "detail": detail, "reason": exp.reason})

    if scenario.max_alerts is not None:
        count = len(alerts)
        results.append({
            "kind": "max_alerts", "pattern": f"≤{scenario.max_alerts} alerts",
            "pass": count <= scenario.max_alerts,
            "detail": f"{count} alerts raised, budget {scenario.max_alerts}",
            "reason": "an alert nobody reads is worse than no alert — dedup and "
                      "consolidation only bind at real session volume",
        })

    for exp in scenario.must_not_fire:
        # Checked against evidence as well as alerts. An analytics-only detector
        # never reaches the alert feed, so testing the feed alone would pass
        # every near-miss scenario about one of them without testing anything.
        # A wrong detection is a false positive whether or not it was shown.
        if exp.pattern in fired:
            ok, detail = False, "fired when it should not have"
        elif exp.pattern in recorded:
            ok, detail = False, "detected when it should not have (recorded as evidence)"
        else:
            ok, detail = True, "correctly silent"
        results.append({"kind": "must_not_fire", "pattern": exp.pattern,
                        "pass": ok, "detail": detail, "reason": exp.reason})
    return results


async def run_scenario(scenario: Scenario, db_factory,
                       include_probe: bool = False) -> Dict[str, Any]:
    """
    Clear, seed, replay, collect, assert, tear down.

    Teardown always runs. Lab alerts share `risk_alerts` with
    /api/admin/detection-quality, so leaving them behind would corrupt the
    metrics that measure the real engine — teardown is not housekeeping here.
    """
    started = time.perf_counter()
    timeline: List[Dict[str, Any]] = []
    error = None

    try:
        async with db_factory() as db:
            await teardown_lab(db)
            await ensure_lab_account(db, capital=scenario.capital, **scenario.profile)

        injection_errors: List[str] = []
        # The clock advances WITH the scenario: each fill is injected with the
        # wall clock pinned to that fill's own timestamp.
        #
        # One frozen instant for the whole run is not enough. The engine builds
        # `session_trades` by querying today's completed trades — "today" by wall
        # clock — so a scenario dated in the past saw an empty session and no
        # detector that needs history could fire. Advancing the clock makes the
        # synthetic session real to the engine, and is why scenarios never need
        # market hours.
        seen_alerts: set = set()
        seen_events: set = set()
        with lab_environment(None):
            for fill in scenario.fills:
                with frozen_clock(scenario.wall_clock or fill.at):
                    outcome = await inject(fill)
                if outcome.get("error"):
                    injection_errors.append(f"{fill.symbol} {fill.side}: {outcome['error']}")

                # Snapshot immediately, so an alert is attributed to the fill
                # that raised it rather than appearing in one undifferentiated
                # heap at the end.
                if scenario.snapshot_steps:
                    async with db_factory() as db:
                        step = await collect_step(db, seen_alerts, seen_events)
                else:
                    step = {"new_alerts": [], "new_suppressed": [], "open": [],
                            "closed_count": 0, "session_pnl": 0, "last_closed": None}

                timeline.append({
                    "at_ist": fill.at.astimezone(IST).strftime("%H:%M:%S"),
                    "symbol": fill.symbol, "side": fill.side, "qty": fill.qty,
                    "price": fill.price, "product": fill.product, "note": fill.note,
                    "error": outcome.get("error"),
                    **step,
                })

        # A fill that never processed makes every negative assertion pass for
        # the wrong reason. Loud, not silent.
        if injection_errors:
            error = "fills failed to process:\n" + "\n".join(injection_errors)

        async with db_factory() as db:
            collected = await collect_all(db)
    except Exception:
        error = traceback.format_exc()
        collected = {"alerts": [], "suppressed": [], "positions": {"open": [], "closed": []},
                     "structures": [], "guardian": [], "session_pnl": 0}

    # Taken here, inside the run, because teardown at the end would leave the
    # account empty and the probe would report "no completed trades" for a
    # scenario that had just produced four. Off by default: it evaluates all 27
    # detectors, which is worth a second for one scenario and not worth 108.
    if include_probe and not error:
        try:
            from .probe import probe as _probe
            collected["probe"] = await _probe()
        except Exception as exc:
            collected["probe"] = {"ready": False, "reason": f"probe failed: {exc}"}

    checks = _check(scenario, collected["alerts"], collected["suppressed"]) if not error else []
    passed = bool(checks) and all(c["pass"] for c in checks) and not error

    try:
        async with db_factory() as db:
            await teardown_lab(db)
    except Exception:
        pass

    return {
        "scenario": scenario.as_dict(),
        "passed": passed,
        "error": error,
        "checks": checks,
        "timeline": timeline,
        "elapsed_ms": round((time.perf_counter() - started) * 1000),
        **collected,
    }
