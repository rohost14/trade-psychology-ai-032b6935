# -*- coding: utf-8 -*-
"""
Does the DOMAIN structure earn its place, or is it a rename of "two danger
alerts"? And is a firing session distinguishable from the near miss it excludes?

No thresholds are changed anywhere. Alternative gates are evaluated only as
COMPARISONS, to see what the current gate buys over a simpler one.
"""
import json
import random
from collections import Counter
from datetime import datetime
from types import SimpleNamespace

from app.services.behavior_scores_service import evaluate_death_spiral
from app.services.detector_registry import BY_NAME, all_pattern_types

LIVE = set(all_pattern_types())
DANGER = {"danger", "critical"}
DAYS = json.load(open("D:/trade-psychology-ai/docs/tradebook-CY6001-FO2025-26-replay.json"))["days"]
random.seed(20260902)


def dt(s):
    return datetime.fromisoformat(s)


def nature(n):
    s = BY_NAME.get(n)
    return s.nature if s else None


def alerts_of(d):
    return sorted((a for a in DAYS[d].get("alerts", [])
                   if a["pattern_type"] in LIVE and a["pattern_type"] != "death_spiral"),
                  key=lambda a: a["detected_at"])


def trades_of(d):
    return sorted((t for t in DAYS[d].get("trades", []) if t.get("exit_time")),
                  key=lambda t: t["exit_time"])


def ev(a):
    return SimpleNamespace(detector=a["pattern_type"], severity=a["severity"],
                           detected_at=dt(a["detected_at"]))


ALL = sorted(DAYS)

# ── gate definitions, evaluated incrementally so each has a fire MOMENT ────
def gate_current(al):
    return evaluate_death_spiral([ev(a) for a in al], None) is not None


def gate_two_danger(al):
    return sum(1 for a in al if a["severity"] in DANGER) >= 2


def gate_one_danger(al):
    return any(a["severity"] in DANGER for a in al)


def gate_two_danger_diff_detector(al):
    d = {a["pattern_type"] for a in al if a["severity"] in DANGER}
    return len(d) >= 2


def first_moment(d, gate):
    al = alerts_of(d)
    for i in range(1, len(al) + 1):
        if gate(al[:i]):
            return dt(al[i - 1]["detected_at"]), al[:i]
    return None, None


def evaluate(gate, label):
    fired, remaining, zero = [], [], 0
    for d in ALL:
        m, _ = first_moment(d, gate)
        if not m:
            continue
        tr = trades_of(d)
        after = [t for t in tr if dt(t["exit_time"]) > m]
        fired.append(d)
        remaining.append(len(after))
        zero += len(after) == 0
    pnl = [DAYS[d]["pnl"] for d in fired]

    def med(x):
        x = sorted(x)
        return x[len(x) // 2] if x else float("nan")

    print("  %-42s n=%3d  median Rs %8.0f  losing %3d%%  median trades left %3.1f  zero-left %d%%"
          % (label, len(fired), med(pnl),
             round(100 * sum(1 for p in pnl if p < 0) / max(len(pnl), 1)),
             med(remaining), round(100 * zero / max(len(fired), 1))))
    return set(fired)


print("=" * 84)
print("GATE COMPARISON - what does the domain structure buy?")
print("=" * 84)
g_cur = evaluate(gate_current, "CURRENT: >=2 nature domains, risk present")
g_2d = evaluate(gate_two_danger, "simpler:  >=2 danger alerts, any domain")
g_2dd = evaluate(gate_two_danger_diff_detector, "simpler:  >=2 danger alerts, 2 DETECTORS")
g_1d = evaluate(gate_one_danger, "simplest: >=1 danger alert")

print()
print("  overlap: current gate vs '>=2 danger alerts, 2 detectors'")
print("     both      %d" % len(g_cur & g_2dd))
print("     current only %d -> %s" % (len(g_cur - g_2dd), sorted(g_cur - g_2dd)))
print("     simpler only %d -> %s" % (len(g_2dd - g_cur), sorted(g_2dd - g_cur)))

print()
print("=" * 84)
print("IS THE COMPOSITE EQUIVALENT TO A TWO-DETECTOR CONJUNCTION?")
print("=" * 84)
emo = {n for n in LIVE if nature(n) == "emotional"}
risk = {n for n in LIVE if nature(n) == "risk"}
manual = set()
for d in ALL:
    al = alerts_of(d)
    dgr = {a["pattern_type"] for a in al if a["severity"] in DANGER}
    if dgr & emo and dgr & risk:
        manual.add(d)
print("  'a danger EMOTIONAL alert and a danger RISK alert in one session': %d sessions"
      % len(manual))
print("  the composite fires on                                          : %d sessions"
      % len(g_cur))
print("  identical set: %s" % (manual == g_cur))
print("  -> at danger, death_spiral IS that conjunction, restated.")

print()
print("=" * 84)
print("FIRING vs NM-A  (the near miss it excludes: 2+ danger, ONE domain)")
print("=" * 84)
nm_a = []
for d in ALL:
    if d in g_cur:
        continue
    al = alerts_of(d)
    dgr = [a for a in al if a["severity"] in DANGER]
    doms = {nature(a["pattern_type"]) for a in dgr} - {None}
    if len(dgr) >= 2 and len(doms) == 1:
        nm_a.append(d)

f_pnl = [DAYS[d]["pnl"] for d in sorted(g_cur)]
n_pnl = [DAYS[d]["pnl"] for d in nm_a]


def med(x):
    x = sorted(x)
    return x[len(x) // 2]


print("  FIRING  n=%2d  median Rs %8.0f  mean Rs %8.0f" % (len(f_pnl), med(f_pnl), sum(f_pnl)/len(f_pnl)))
print("  NM-A    n=%2d  median Rs %8.0f  mean Rs %8.0f" % (len(n_pnl), med(n_pnl), sum(n_pnl)/len(n_pnl)))
print("  The excluded near miss is WORSE on money than the flagged session.")

obs = med(f_pnl) - med(n_pnl)
pool = f_pnl + n_pnl
hits = 0
N = 20000
for _ in range(N):
    random.shuffle(pool)
    a, b = pool[:len(f_pnl)], pool[len(f_pnl):]
    if abs(med(a) - med(b)) >= abs(obs):
        hits += 1
print("  permutation test on the median gap (%.0f): p = %.3f  (n=%d vs %d)"
      % (obs, hits / N, len(f_pnl), len(n_pnl)))
print("  -> firing and near-miss sessions are NOT separable on outcome here.")

print()
print("=" * 84)
print("INCREMENTAL vs REDUNDANT - per firing episode")
print("=" * 84)
print("  A firing is INCREMENTAL only if, at the moment it becomes true,")
print("  (a) no other alert fires at that same instant - otherwise the trader")
print("      receives the underlying alert and the summary together - and")
print("  (b) at least one trade is still to come.")
print()
print("  %-12s %-12s %-14s %s" % ("session", "simultaneous", "trades left", "verdict"))
inc = 0
for d in sorted(g_cur):
    m, prefix = first_moment(d, gate_current)
    al = alerts_of(d)
    simul = [a for a in al if dt(a["detected_at"]) == m]
    tr_left = [t for t in trades_of(d) if dt(t["exit_time"]) > m]
    is_inc = len(simul) == 1 and len(tr_left) > 0
    inc += is_inc
    print("  %-12s %-12s %-14s %s"
          % (d, "%d alerts" % len(simul), "%d" % len(tr_left),
             "INCREMENTAL" if is_inc else "redundant"))
print()
print("  genuinely incremental: %d of %d (%.0f%%)" % (inc, len(g_cur), 100.0*inc/len(g_cur)))
