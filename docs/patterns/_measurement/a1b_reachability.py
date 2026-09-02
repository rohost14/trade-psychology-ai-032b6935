# -*- coding: utf-8 -*-
"""
Which death_spiral tiers can be reached, and by what?

Exhaustive over domain subsets rather than sampled: there are only four nature
domains, so every combination can be enumerated and asked directly. Also
quantifies what the fourteen retirements did to the composite, which the pace
rule predicts is pure arithmetic.
"""
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from itertools import combinations
from types import SimpleNamespace

from app.services.behavior_scores_service import (
    _ALIAS_NATURE, evaluate_death_spiral)
from app.services.detector_registry import BY_NAME, all_pattern_types

LIVE = set(all_pattern_types())
T0 = datetime(2026, 2, 5, 5, 0, tzinfo=timezone.utc)

#: One danger-capable detector per domain, from the live registry.
REP = {
    "emotional": "same_symbol_obsession",
    "risk": "martingale_behaviour",
    "discipline": "constitution_violation",
    "performance": "win_rate_collapse",
}

#: The natures of the retired types, from the master table, so the artifact can
#: be replayed as it actually stood rather than with those events silently
#: dropped for having no spec.
RETIRED_NATURE = {
    "size_escalation": "emotional",
    "options_premium_avg_down": "emotional",
    "direction_instability": "emotional",
    "winning_streak_overconfidence": "emotional",
}


def ev(detector, severity="danger", at=T0):
    return SimpleNamespace(detector=detector, severity=severity, detected_at=at)


print("── 1. CAN EACH DOMAIN CONTRIBUTE AT ALL? ──")
print("   (the filter is severity >= danger)")
for dom, name in REP.items():
    spec = BY_NAME.get(name)
    print("   %-12s %-26s disposition=%-10s" % (dom, name, spec.disposition if spec else "?"))
print("   performance detectors hardcode severity='info', so the domain is")
print("   unreachable by construction - not rare, IMPOSSIBLE.")

print("\n── 2. EVERY DOMAIN COMBINATION, ENUMERATED ──")
doms = ["emotional", "risk", "discipline", "performance"]
print("   %-42s %-10s %s" % ("domains present (all at danger)", "verdict", "note"))
for r in range(1, 5):
    for combo in combinations(doms, r):
        evs = [ev(REP[d], at=T0 + timedelta(minutes=i * 10))
               for i, d in enumerate(combo)]
        # a later event so continued_escalation can be true where applicable
        evs.append(ev(REP[combo[0]], at=T0 + timedelta(minutes=len(combo) * 10 + 5)))
        v = evaluate_death_spiral(evs, T0 + timedelta(hours=3))
        note = ""
        if "performance" in combo:
            note = "performance can never actually be danger"
        print("   %-42s %-10s %s" % ("+".join(combo), v["severity"] if v else "-", note))

print("\n── 3. WHAT CRITICAL ACTUALLY REQUIRES ──")
print("   >=3 domains AND discipline AND risk AND continued_escalation AND compressed.")
print("   performance is impossible, so the 3 must be emotional+risk+discipline.")
print("   discipline has exactly ONE detector: constitution_violation, which")
print("   fires only on a rule the trader DECLARED. Money rules are opt-in and")
print("   default to None.")
evs = [ev("same_symbol_obsession", at=T0),
       ev("martingale_behaviour", at=T0 + timedelta(minutes=20)),
       ev("constitution_violation", at=T0 + timedelta(minutes=40)),
       ev("revenge_trade", at=T0 + timedelta(minutes=50))]
v = evaluate_death_spiral(evs, T0 + timedelta(hours=2))
print("   with a declared rule breached : %s" % (v["severity"] if v else "-"))
evs2 = [e for e in evs if e.detector != "constitution_violation"]
v2 = evaluate_death_spiral(evs2, T0 + timedelta(hours=2))
print("   same session, no rules declared: %s" % (v2["severity"] if v2 else "-"))

print("\n── 4. THE COMPRESSION WINDOW ──")
for gap in (0, 60, 179, 180, 181, 300, 600):
    evs = [ev("same_symbol_obsession", at=T0),
           ev("martingale_behaviour", at=T0 + timedelta(minutes=gap)),
           ev("constitution_violation", at=T0 + timedelta(minutes=gap)),
           ev("revenge_trade", at=T0 + timedelta(minutes=gap + 1))]
    v = evaluate_death_spiral(evs, T0 + timedelta(hours=12))
    print("   domains %4d min apart -> %-9s compressed=%s"
          % (gap, v["severity"] if v else "-",
             v["context"]["compressed_within_min"] if v else "-"))
print("   NOTE: a trading session is ~6h15m (09:15-15:30). 180 min is under half")
print("   of it, so the window can separate a morning cluster from an afternoon")
print("   one - but ONLY the critical tier consults it. danger ignores it.")

print("\n── 5. WHAT THE RETIREMENTS DID (the arithmetic the pace rule predicts) ──")
art = json.load(open("D:/trade-psychology-ai/docs/tradebook-CY6001-FO2025-26-replay.json"))
days = art["days"]


def run(day_alerts, natures):
    evs = []
    for a in day_alerts:
        n = a["pattern_type"]
        if n == "death_spiral":
            continue
        if n not in natures:
            continue
        evs.append(ev(n, a["severity"], datetime.fromisoformat(a["detected_at"])))
    return evaluate_death_spiral(evs, None)


then_natures = {n: (BY_NAME[n].nature if n in BY_NAME else _ALIAS_NATURE.get(n))
                for n in {a["pattern_type"] for d in days.values() for a in d.get("alerts", [])}}
then_natures.update(RETIRED_NATURE)
then_natures = {k: v for k, v in then_natures.items() if v}
now_natures = {k: v for k, v in then_natures.items() if k in LIVE}

for label, natures in (("BEFORE the 14 retirements", then_natures),
                       ("AFTER  (current registry)", now_natures)):
    c = Counter()
    for dt in sorted(days):
        v = run(days[dt].get("alerts", []), natures)
        if v:
            c[v["severity"]] += 1
    print("   %-28s fires %3d / 203  (%s)"
          % (label, sum(c.values()),
             ", ".join("%s=%d" % (k, c[k]) for k in ("caution", "danger", "critical") if c.get(k))))
print("   The artifact itself recorded %d death_spiral alerts at the time."
      % sum(1 for d in days.values() for a in d.get("alerts", [])
            if a["pattern_type"] == "death_spiral"))
