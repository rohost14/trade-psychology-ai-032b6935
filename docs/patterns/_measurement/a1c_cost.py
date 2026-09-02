# -*- coding: utf-8 -*-
"""
death_spiral's cost, and what the trader is actually told.

`_run_death_spiral` runs once per completed trade and reloads EVERY
BehaviorEvent of the day each time, so the work over a session is quadratic in
events. Quantified here against the real book rather than asserted.

Also measures the gap between what the alert SAYS ("N signals today") and what
happens to the other alerts on that day, since the review document claims the
composite absorbs them.
"""
import json
from collections import Counter, defaultdict
from datetime import datetime
from types import SimpleNamespace

from app.services.behavior_scores_service import evaluate_death_spiral
from app.services.detector_registry import BY_NAME, all_pattern_types
from app.services.behavior_scores_service import _ALIAS_NATURE

LIVE = set(all_pattern_types())
ART = "D:/trade-psychology-ai/docs/tradebook-CY6001-FO2025-26-replay.json"


def ev(a):
    return SimpleNamespace(detector=a["pattern_type"], severity=a["severity"],
                           detected_at=datetime.fromisoformat(a["detected_at"]))


art = json.load(open(ART))
days = art["days"]

print("── 1. WORK PER SESSION ──")
print("   `_run_death_spiral` is called once per CompletedTrade and each call")
print("   re-SELECTs every BehaviorEvent of the day, then SELECTs prior alerts.")
loads = []
for dt, d in days.items():
    n_tr = len(d.get("trades", []))
    n_ev = len(d.get("alerts", []))
    # trade i sees roughly the events produced by trades 0..i
    loads.append((dt, n_tr, n_ev, n_tr * n_ev))
loads.sort(key=lambda r: -r[3])
print("   %-12s %7s %8s %12s" % ("session", "trades", "alerts", "rows read"))
for dt, t, e, w in loads[:6]:
    print("   %-12s %7d %8d %12d" % (dt, t, e, w))
tot_tr = sum(r[1] for r in loads)
print("   total trades %d -> %d death_spiral invocations, %d SELECTs"
      % (tot_tr, tot_tr, tot_tr * 2))
print("   NOTE: alerts under-counts events (info + suppressed are also rows),")
print("   so these are lower bounds on rows read.")

print("\n── 2. WHAT A FIRING SESSION LOOKS LIKE TO THE TRADER ──")
fired = []
for dt in sorted(days):
    alerts = [a for a in days[dt].get("alerts", []) if a["pattern_type"] in LIVE]
    evs = [ev(a) for a in alerts if a["pattern_type"] != "death_spiral"]
    v = evaluate_death_spiral(evs, None)
    if v:
        others = [a for a in alerts if a["pattern_type"] != "death_spiral"]
        fired.append((dt, v, others))

print("   %-12s %-9s %-8s %-9s %s" % ("session", "verdict", "counted", "alerts", "message quote"))
for dt, v, others in fired:
    print("   %-12s %-9s %-8d %-9d %s"
          % (dt, v["severity"], v["context"]["event_count"], len(others),
             ("%d signals" % v["context"]["event_count"])))
counted = sum(v["context"]["event_count"] for _, v, _ in fired)
present = sum(len(o) for _, _, o in fired)
print("   ACROSS %d FIRING SESSIONS: message counts %d signals; %d alerts exist."
      % (len(fired), counted, present))
print("   The count is danger+ only, so every caution on the day is uncounted.")

print("\n── 3. SEVERITY MIX ON FIRING DAYS ──")
mix = Counter()
for _, _, others in fired:
    for a in others:
        mix[(a["pattern_type"], a["severity"])] += 1
for (p, s), n in sorted(mix.items(), key=lambda kv: -kv[1]):
    print("   %-32s %-8s %d" % (p, s, n))

print("\n── 4. IS A FIRING DAY DIFFERENT? ──")
fired_days = {dt for dt, _, _ in fired}
fp = [days[d]["pnl"] for d in fired_days if days[d].get("pnl") is not None]
op = [days[d]["pnl"] for d in days if d not in fired_days and days[d].get("pnl") is not None]


def med(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2] if xs else float("nan")


print("   firing sessions   n=%3d  median P&L Rs %9.0f  mean Rs %9.0f  losing %d%%"
      % (len(fp), med(fp), sum(fp) / max(len(fp), 1),
         round(100 * sum(1 for x in fp if x < 0) / max(len(fp), 1))))
print("   other  sessions   n=%3d  median P&L Rs %9.0f  mean Rs %9.0f  losing %d%%"
      % (len(op), med(op), sum(op) / max(len(op), 1),
         round(100 * sum(1 for x in op if x < 0) / max(len(op), 1))))
print("   Descriptive only. It cannot judge the alert - the alert fires at the")
print("   END of a session it is describing, so a worse day is what it is made of.")

print("\n── 5. TIMING: WHEN IN THE SESSION DOES IT FIRE? ──")
for dt, v, others in fired:
    ts = sorted(datetime.fromisoformat(a["detected_at"]) for a in others)
    trades = days[dt].get("trades", [])
    exits = sorted(datetime.fromisoformat(t["exit_time"]) for t in trades if t.get("exit_time"))
    if not ts or not exits:
        continue
    trigger = ts[-1] if False else max(
        t for t in ts if t <= max(ts))
    after = sum(1 for e in exits if e > trigger)
    print("   %s  fires after trade %d of %d  (%d trades still to come)"
          % (dt, len(exits) - after, len(exits), after))
