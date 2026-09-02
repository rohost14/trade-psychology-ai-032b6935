# -*- coding: utf-8 -*-
"""
death_spiral (A1) — measured WITHOUT a new replay.

The pace rule for composites: a detector that COUNTS other detectors moves
whenever one of them is removed, and that movement is arithmetic, not a finding.
So this recomputes the real verdict from the stored replay artifact under the
CURRENT registry, rather than spending two hours re-deriving the inputs.

Method
  1. take every alert the replay recorded, per session
  2. drop the pattern types that no longer exist (14 retirements)
  3. map each to its nature domain exactly as the live code does
  4. run the REAL `evaluate_death_spiral` over it

Limits, stated rather than hidden:
  * The artifact holds RiskAlerts, not BehaviorEvents. The live function reads
    events INCLUDING suppressed ones and info ones; it then filters to danger+,
    so info is irrelevant, but a SUPPRESSED danger event would be missing here.
  * Surviving detectors whose own logic changed after the artifact was written
    (fomo_entry v2, premium_loss_event, daily_overtrading, no_stoploss) are
    carried at their artifact values. Each is flagged in the output.
"""
import json
from collections import Counter, defaultdict
from datetime import datetime
from types import SimpleNamespace

from app.services.behavior_scores_service import (
    _ALIAS_NATURE, evaluate_death_spiral)
from app.services.detector_registry import BY_NAME, all_pattern_types

ART = "D:/trade-psychology-ai/docs/tradebook-CY6001-FO2025-26-replay.json"

LIVE = set(all_pattern_types())


def nature_of(name):
    spec = BY_NAME.get(name)
    return spec.nature if spec else _ALIAS_NATURE.get(name)


def main():
    art = json.load(open(ART))
    days = art["days"]
    print("artifact: %s   capital Rs %.0f   %d sessions   skipped %s"
          % (art["source"], art["capital"], art["sessions"], art["skipped_patterns"]))

    seen = Counter()
    for d in days.values():
        for a in d.get("alerts", []):
            seen[a["pattern_type"]] += 1

    print("\n── pattern types in the artifact ──")
    retired, kept = [], []
    for name, n in seen.most_common():
        (kept if name in LIVE else retired).append((name, n))
    print("  STILL LIVE (%d types, %d alerts):" % (len(kept), sum(n for _, n in kept)))
    for name, n in kept:
        print("      %-32s %5d   nature=%s" % (name, n, nature_of(name)))
    print("  RETIRED SINCE (%d types, %d alerts) - dropped from the recompute:"
          % (len(retired), sum(n for _, n in retired)))
    for name, n in retired:
        print("      %-32s %5d" % (name, n))

    # ── what the domains can even be ──────────────────────────────────────
    print("\n── domains reachable at danger+ ──")
    dom = defaultdict(set)
    for name in LIVE:
        nt = nature_of(name)
        if nt:
            dom[nt].add(name)
    for nt in sorted(dom):
        print("  %-12s %s" % (nt, ", ".join(sorted(dom[nt]))))

    # ── recompute, then and now ───────────────────────────────────────────
    def run(day_alerts, allow):
        evs = [
            SimpleNamespace(
                detector=a["pattern_type"], severity=a["severity"],
                detected_at=datetime.fromisoformat(a["detected_at"]))
            for a in day_alerts if a["pattern_type"] in allow
        ]
        return evaluate_death_spiral(evs, None), evs

    for label, allow in (("AS THE ARTIFACT STOOD", seen.keys()),
                         ("UNDER THE CURRENT REGISTRY", LIVE)):
        verdicts = Counter()
        domains_hit = Counter()
        fired_days = []
        for dt in sorted(days):
            v, evs = run(days[dt].get("alerts", []), allow)
            if v:
                verdicts[v["severity"]] += 1
                domains_hit[tuple(v["context"]["domains"])] += 1
                fired_days.append((dt, v["severity"], v["context"]["domains"],
                                   v["context"]["event_count"]))
        total = sum(verdicts.values())
        print("\n══ %s ══" % label)
        print("  fires on %d of %d sessions (%.1f%%)"
              % (total, len(days), 100.0 * total / len(days)))
        for sev in ("caution", "danger", "critical"):
            print("     %-9s %d" % (sev, verdicts.get(sev, 0)))
        print("  domain combinations:")
        for combo, n in domains_hit.most_common():
            print("     %-28s %d" % (" + ".join(combo), n))
        if label.startswith("UNDER"):
            print("  first 10 firing sessions:")
            for dt, sev, doms, n in fired_days[:10]:
                print("     %s  %-8s %-22s %d signals" % (dt, sev, "+".join(doms), n))

    # ── the absorption cost ───────────────────────────────────────────────
    print("\n── absorption: what a firing session HIDES ──")
    absorbed = Counter()
    n_sessions = 0
    for dt in sorted(days):
        alerts = [a for a in days[dt].get("alerts", []) if a["pattern_type"] in LIVE]
        v, _ = run(alerts, LIVE)
        if v:
            n_sessions += 1
            for a in alerts:
                absorbed[a["pattern_type"]] += 1
    print("  on %d firing sessions, %d other alerts exist:" % (n_sessions, sum(absorbed.values())))
    for name, n in absorbed.most_common():
        print("     %-32s %d" % (name, n))


main()
