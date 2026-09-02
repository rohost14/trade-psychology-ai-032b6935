# -*- coding: utf-8 -*-
"""
Two follow-ups the headline numbers demand.

A. WHAT CARRIES EACH DOMAIN? `discipline+risk` is 59 of 79 firings. If the
   discipline event is constitution_violation's `daily_loss` rule and the risk
   event is `session_meltdown`, then BOTH are reading the SAME declared
   daily_loss_limit - one fact, counted as two independent domains.

B. WHAT BROKE THE CRITICAL VERDICT? Both critical sessions changed under
   reordering. Which clause did it - the 180-minute compression window, or
   continued escalation?
"""
import json
from collections import Counter, defaultdict
from datetime import datetime
from itertools import permutations
from pathlib import Path
from types import SimpleNamespace

from app.services.behavior_scores_service import evaluate_death_spiral, _ALIAS_NATURE
from app.services.detector_registry import BY_NAME

SRC = Path(r"C:\Users\being\.claude\jobs\33a73186\tmp\RULES-replay.json")
DANGER = {"danger", "critical"}
DAYS = json.load(open(SRC))["days"]


def dt(s):
    return datetime.fromisoformat(s)


def nature(n):
    s = BY_NAME.get(n)
    return s.nature if s else _ALIAS_NATURE.get(n)


def events_of(d):
    return sorted((e for e in DAYS[d]["events"]
                   if not e["shadow"] and e["detector"] != "death_spiral"
                   and e["detected_at"]),
                  key=lambda e: e["detected_at"])


def ev(e):
    return SimpleNamespace(detector=e["detector"], severity=e["severity"],
                           detected_at=dt(e["detected_at"]))


def verdict(evs):
    return evaluate_death_spiral([ev(e) for e in evs], None)


ALL = sorted(DAYS)
FIRING = [d for d in ALL if verdict(events_of(d))]

print("=" * 80)
print("A. WHAT CARRIES EACH DOMAIN IN A FIRING SESSION?")
print("=" * 80)
carriers = defaultdict(Counter)
pair = Counter()
for d in FIRING:
    dgr = [e for e in events_of(d) if e["severity"] in DANGER]
    doms = defaultdict(set)
    for e in dgr:
        n = nature(e["detector"])
        if n:
            doms[n].add(e["detector"])
            carriers[n][e["detector"]] += 1
    key = tuple(sorted("%s:%s" % (k, "/".join(sorted(v))) for k, v in doms.items()))
    pair[key] += 1

for dom in sorted(carriers):
    print("\n  %s" % dom.upper())
    for det, n in carriers[dom].most_common():
        print("     %-34s %3d sessions" % (det, n))

print("\n  the exact domain-carrier combinations:")
for k, n in pair.most_common(8):
    print("     %3d  %s" % (n, "  |  ".join(k)))

print()
print("=" * 80)
print("A2. ARE THE TWO DOMAINS READING THE SAME DECLARED RULE?")
print("=" * 80)
print("  `session_meltdown` (risk) and constitution_violation's `daily_loss`")
print("  rule (discipline) are both driven by the declared daily_loss_limit.")
both = 0
only_sm = 0
for d in FIRING:
    dgr = [e for e in events_of(d) if e["severity"] in DANGER]
    dets = {e["detector"] for e in dgr}
    risk_dets = {x for x in dets if nature(x) == "risk"}
    disc_dets = {x for x in dets if nature(x) == "discipline"}
    if "session_meltdown" in risk_dets and "constitution_violation" in disc_dets:
        both += 1
        if risk_dets == {"session_meltdown"}:
            only_sm += 1
print("  sessions where BOTH domains come from those two detectors: %d of %d (%.0f%%)"
      % (both, len(FIRING), 100.0 * both / len(FIRING)))
print("  ...and session_meltdown is the ONLY risk contributor:      %d of %d (%.0f%%)"
      % (only_sm, len(FIRING), 100.0 * only_sm / len(FIRING)))
print("  -> in those, the 'two independent domains' are one declared limit,")
print("     breached, reported by two detectors that both read it.")

print()
print("=" * 80)
print("B. WHICH CLAUSE DECIDES `critical`?")
print("=" * 80)
CRIT = [d for d in FIRING if verdict(events_of(d))["severity"] == "critical"]
for d in CRIT:
    evs = events_of(d)
    v = verdict(evs)
    c = v["context"]
    print("\n  %s" % d)
    print("     domains=%s  compressed_within_min=%s  continued_escalation=%s"
          % (c["domains"], c["compressed_within_min"], c["continued_escalation"]))
    dgr = [e for e in evs if e["severity"] in DANGER]
    span = (dt(dgr[-1]["detected_at"]) - dt(dgr[0]["detected_at"])).total_seconds() / 60
    print("     danger+ events span %.0f min (window is 180)" % span)
    for e in dgr:
        print("        %s  %-32s %-8s %s"
              % (e["detected_at"][11:16], e["detector"], e["severity"],
                 nature(e["detector"])))
    # which permutation broke it, and into what
    times = sorted(e["detected_at"] for e in evs)
    idx = list(range(len(evs)))
    broke_to = Counter()
    space = list(permutations(idx))[:200] if len(evs) <= 7 else []
    if not space:
        import random
        random.seed(1)
        space = [tuple(random.sample(idx, len(idx))) for _ in range(500)]
    for perm in space:
        sh = [dict(evs[i], detected_at=times[j]) for j, i in enumerate(perm)]
        vv = verdict(sh)
        broke_to[vv["severity"] if vv else None] += 1
    print("     verdict across %d reorderings: %s" % (len(space), dict(broke_to)))

print()
print("=" * 80)
print("C. HOW OFTEN IS THE CRITICAL/DANGER BOUNDARY DECIDED BY ORDER ALONE?")
print("=" * 80)
import random
random.seed(7)
flip = 0
tested = 0
for d in FIRING:
    evs = events_of(d)
    base = verdict(evs)["severity"]
    if len(evs) < 2:
        continue
    tested += 1
    times = sorted(e["detected_at"] for e in evs)
    idx = list(range(len(evs)))
    seen = set()
    for _ in range(300):
        p = tuple(random.sample(idx, len(idx)))
        if p in seen:
            continue
        seen.add(p)
        sh = [dict(evs[i], detected_at=times[j]) for j, i in enumerate(p)]
        vv = verdict(sh)
        if (vv["severity"] if vv else None) != base:
            flip += 1
            break
print("  sessions whose TIER can change under reordering alone: %d of %d (%.0f%%)"
      % (flip, tested, 100.0 * flip / max(tested, 1)))
print("  -> for those, whether the trader gets a guardian-eligible `critical`")
print("     or a `danger` is decided by the minute-order of the day's events.")
