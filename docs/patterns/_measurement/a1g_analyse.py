# -*- coding: utf-8 -*-
"""
The four measurements, against the rules-enabled replay.

  1. How often caution and critical fire, and on what domain sets.
  2. Whether `critical` is ORDER-DEPENDENT. If permuting the event times of a
     session cannot change the verdict, the compression window and the
     continued-escalation clause are decorative and the whole detector is
     co-occurrence rather than deterioration.
  3. Whether critical firings are INCREMENTAL, by the same test used on the
     danger tier: fires alone (no simultaneous alert) and trades remain.
  4. Whether admitting `session_meltdown` as a risk contributor changes the
     danger-tier set.

Reads BehaviorEvents, not RiskAlerts: with rules on, the engine suppresses
siblings as `constitution_breach`, and death_spiral counts suppressed events.
"""
import json
import random
from collections import Counter, defaultdict
from datetime import datetime
from itertools import permutations
from pathlib import Path
from types import SimpleNamespace

from app.services.behavior_scores_service import evaluate_death_spiral
from app.services.detector_registry import BY_NAME
from app.services.behavior_scores_service import _ALIAS_NATURE

SRC = Path(r"C:\Users\being\.claude\jobs\33a73186\tmp\RULES-replay.json")
DANGER = {"danger", "critical"}
random.seed(20260902)

blob = json.load(open(SRC))
DAYS = blob["days"]
print("source: %s   capital Rs %.0f   profile %s   %d sessions"
      % (blob["source"], blob["capital"], blob["profile"], len(DAYS)))


def dt(s):
    return datetime.fromisoformat(s)


def nature(n):
    s = BY_NAME.get(n)
    return s.nature if s else _ALIAS_NATURE.get(n)


def events_of(d, exclude=()):
    """Exactly what `_run_death_spiral` feeds the function: today's events,
    shadow excluded, suppressed INCLUDED, death_spiral itself excluded."""
    out = []
    for e in DAYS[d]["events"]:
        if e["shadow"] or e["detector"] == "death_spiral":
            continue
        if e["detector"] in exclude or not e["detected_at"]:
            continue
        out.append(e)
    return sorted(out, key=lambda e: e["detected_at"])


def ev(e):
    return SimpleNamespace(detector=e["detector"], severity=e["severity"],
                           detected_at=dt(e["detected_at"]))


def verdict(evs):
    return evaluate_death_spiral([ev(e) for e in evs], None)


def trades_of(d):
    return sorted((t for t in DAYS[d]["trades"] if t.get("exit_time")),
                  key=lambda t: t["exit_time"])


def first_moment(d, exclude=()):
    evs = events_of(d, exclude)
    for i in range(1, len(evs) + 1):
        v = verdict(evs[:i])
        if v:
            return dt(evs[i - 1]["detected_at"]), v, evs[:i]
    return None, None, None


ALL = sorted(DAYS)

# ══ 1. TIER FREQUENCY AND DOMAIN SETS ══════════════════════════════════════
print("\n" + "=" * 80)
print("1. HOW OFTEN DOES EACH TIER FIRE, AND ON WHAT DOMAINS?")
print("=" * 80)
tiers, combos, by_tier = Counter(), Counter(), defaultdict(list)
for d in ALL:
    m, v, _ = first_moment(d)
    if not v:
        continue
    # the FINAL verdict of the day, which is what escalation-dedup lands on
    fin = verdict(events_of(d))
    tiers[fin["severity"]] += 1
    combos[(fin["severity"], tuple(fin["context"]["domains"]))] += 1
    by_tier[fin["severity"]].append(d)
print("  sessions with any firing: %d of %d (%.1f%%)"
      % (sum(tiers.values()), len(ALL), 100.0 * sum(tiers.values()) / len(ALL)))
for t in ("caution", "danger", "critical"):
    print("     %-9s %3d" % (t, tiers.get(t, 0)))
print("\n  domain sets:")
for (t, c), n in combos.most_common():
    print("     %-9s %-34s %d" % (t, "+".join(c), n))

# ══ 2. IS CRITICAL ORDER-DEPENDENT? ════════════════════════════════════════
print("\n" + "=" * 80)
print("2. IS `critical` ORDER-DEPENDENT?")
print("=" * 80)
print("  Permute the event TIMES within the session, keeping the multiset of")
print("  times and the multiset of detectors. If no permutation changes the")
print("  verdict, order is not part of the condition.")


def order_test(d, want):
    evs = events_of(d)
    times = sorted(e["detected_at"] for e in evs)
    n = len(evs)
    idx = list(range(n))
    seen = set()
    trials = 0
    broke = None
    if n <= 7:
        space = list(permutations(idx))
    else:
        space = []
        for _ in range(3000):
            p = idx[:]
            random.shuffle(p)
            space.append(tuple(p))
    for perm in space:
        if perm in seen:
            continue
        seen.add(perm)
        trials += 1
        shuffled = [dict(evs[i], detected_at=times[j]) for j, i in enumerate(perm)]
        v = verdict(shuffled)
        sev = v["severity"] if v else None
        if sev != want:
            broke = (sev, perm)
            break
    return trials, broke


for tier in ("critical", "caution", "danger"):
    ds = by_tier.get(tier, [])
    if not ds:
        print("\n  %s: never fired - nothing to test." % tier)
        continue
    stable = 0
    print("\n  %s  (%d sessions)" % (tier, len(ds)))
    for d in ds[:25]:
        trials, broke = order_test(d, tier)
        if broke is None:
            stable += 1
            print("     %-12s %5d reorderings, verdict UNCHANGED" % (d, trials))
        else:
            print("     %-12s %5d reorderings, BROKE -> %s" % (d, trials, broke[0]))
    print("     order-independent: %d of %d tested" % (stable, len(ds[:25])))

# ══ 3. ARE CRITICAL FIRINGS INCREMENTAL? ═══════════════════════════════════
print("\n" + "=" * 80)
print("3. ARE THE FIRINGS INCREMENTAL?")
print("=" * 80)
print("  incremental = at the moment it becomes true, no other alert fires at")
print("  that same instant AND at least one trade is still to come.")
for tier in ("critical", "caution", "danger"):
    ds = by_tier.get(tier, [])
    if not ds:
        continue
    inc = 0
    zero_left = 0
    already = 0
    print("\n  %s (%d)" % (tier, len(ds)))
    print("     %-12s %-13s %-12s %-22s %s"
          % ("session", "simultaneous", "trades left", "danger already delivered", "verdict"))
    for d in ds:
        m, v, prefix = first_moment(d)
        evs = events_of(d)
        simul = [e for e in evs if dt(e["detected_at"]) == m]
        left = [t for t in trades_of(d) if dt(t["exit_time"]) > m]
        prior_danger = [e for e in evs
                        if dt(e["detected_at"]) < m and e["severity"] in DANGER
                        and not e["suppressed"]]
        is_inc = len(simul) == 1 and len(left) > 0
        inc += is_inc
        zero_left += len(left) == 0
        already += len(prior_danger) > 0
        if len(ds) <= 30:
            print("     %-12s %-13s %-12s %-22s %s"
                  % (d, "%d" % len(simul), "%d" % len(left), "%d" % len(prior_danger),
                     "INCREMENTAL" if is_inc else "redundant"))
    print("     incremental %d/%d (%.0f%%) · zero trades left %d · "
          "had a danger alert already delivered %d"
          % (inc, len(ds), 100.0 * inc / len(ds), zero_left, already))

# ══ 4. DOES session_meltdown CHANGE THE DANGER SET? ════════════════════════
print("\n" + "=" * 80)
print("4. DOES ADMITTING session_meltdown CHANGE THE DANGER-TIER SET?")
print("=" * 80)
sm_events = sum(1 for d in ALL for e in DAYS[d]["events"]
                if e["detector"] == "session_meltdown")
sm_danger = sum(1 for d in ALL for e in DAYS[d]["events"]
                if e["detector"] == "session_meltdown" and e["severity"] in DANGER)
print("  session_meltdown events in this run: %d (%d at danger+)" % (sm_events, sm_danger))

with_sm, without_sm = set(), set()
for d in ALL:
    if verdict(events_of(d)):
        with_sm.add(d)
    if verdict(events_of(d, exclude=("session_meltdown",))):
        without_sm.add(d)
print("  firing WITH session_meltdown   : %d sessions" % len(with_sm))
print("  firing WITHOUT session_meltdown: %d sessions" % len(without_sm))
print("  sessions that exist ONLY because of it: %d -> %s"
      % (len(with_sm - without_sm), sorted(with_sm - without_sm)[:12]))

# ══ CONTEXT: compare with the no-rules book ════════════════════════════════
print("\n" + "=" * 80)
print("CONTEXT - the no-rules baseline, same book")
print("=" * 80)
print("  no-rules: 10 sessions, all danger, all emotional+risk")
print("  rules-on: %d sessions -> %s"
      % (sum(tiers.values()), dict(tiers)))
fire_pnl = [DAYS[d]["pnl"] for d in ALL if verdict(events_of(d))]
other = [DAYS[d]["pnl"] for d in ALL if not verdict(events_of(d))]


def med(x):
    x = sorted(x)
    return x[len(x) // 2] if x else float("nan")


print("  firing sessions  n=%3d median Rs %8.0f  losing %d%%"
      % (len(fire_pnl), med(fire_pnl),
         round(100 * sum(1 for p in fire_pnl if p < 0) / max(len(fire_pnl), 1))))
print("  other sessions   n=%3d median Rs %8.0f  losing %d%%"
      % (len(other), med(other),
         round(100 * sum(1 for p in other if p < 0) / max(len(other), 1))))
