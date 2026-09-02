# -*- coding: utf-8 -*-
"""
death_spiral, part 2: is it a state, or a summary?

Reconstructs each firing episode chronologically, then asks four separable
questions. Evidence available BEFORE the condition, the condition itself, and
what happened AFTER are kept apart throughout; nothing here is a claim about
prediction or cause.

  Q1 distinct   does the firing set differ from "a bad session"?
  Q2 additive   at the moment it fires, what did the trader not already know?
  Q3 escalation is the condition ordered in time, or just co-occurrence?
  Q4 actionable how much of the session is left?
"""
import json
from collections import Counter, defaultdict
from datetime import datetime
from itertools import permutations
from types import SimpleNamespace

from app.services.behavior_scores_service import evaluate_death_spiral
from app.services.detector_registry import BY_NAME, all_pattern_types

LIVE = set(all_pattern_types())
ART = "D:/trade-psychology-ai/docs/tradebook-CY6001-FO2025-26-replay.json"
DANGER = {"danger", "critical"}

art = json.load(open(ART))
DAYS = art["days"]


def dt(s):
    return datetime.fromisoformat(s)


def nature(name):
    spec = BY_NAME.get(name)
    return spec.nature if spec else None


def alerts_of(day, drop_spiral=True):
    out = []
    for a in DAYS[day].get("alerts", []):
        p = a["pattern_type"]
        if p not in LIVE:
            continue
        if drop_spiral and p == "death_spiral":
            continue
        out.append(a)
    return sorted(out, key=lambda a: a["detected_at"])


def trades_of(day):
    return sorted((t for t in DAYS[day].get("trades", []) if t.get("exit_time")),
                  key=lambda t: t["exit_time"])


def ev(a):
    return SimpleNamespace(detector=a["pattern_type"], severity=a["severity"],
                           detected_at=dt(a["detected_at"]))


def verdict(day_alerts):
    return evaluate_death_spiral([ev(a) for a in day_alerts], None)


def first_true_moment(day):
    """
    The instant the condition BECOMES true, evaluated incrementally the way the
    live task does - one call per completed trade, over everything so far.
    """
    al = alerts_of(day)
    for i in range(1, len(al) + 1):
        v = verdict(al[:i])
        if v:
            return dt(al[i - 1]["detected_at"]), v, al[:i]
    return None, None, None


FIRING = [d for d in sorted(DAYS) if verdict(alerts_of(d))]

print("=" * 78)
print("OBSERVABILITY - what this evidence CANNOT show")
print("=" * 78)
print("""  consecutive_loss_streak  RETIRED 2026-08-26. Does not exist; cannot appear.
  excess_exposure          RETIRED 2026-09-01, and was harness-skipped before.
  session_meltdown         harness-skipped (CAPITAL_DERIVED). It is a `risk`
                           detector that CAN reach danger, so it is a missing
                           potential domain contributor - firing counts here are
                           a LOWER bound for any trader with a declared limit.
  rapid_reentry            analytics, severity hardcoded `info`. It can never
                           pass the >=danger gate, so it can never contribute a
                           domain. Absence here is structural, not sampling.
  4 of the 9 focus detectors therefore carry no evidence in this book.""")

print()
print("=" * 78)
print("Q3  ESCALATION OR CO-OCCURRENCE?  (the condition itself)")
print("=" * 78)
print("""  The danger tier is `capital_at_risk and len(domains) >= 2`. No timestamp
  enters it. Tested by permuting each firing session's alert times and asking
  whether the verdict survives - if order cannot break it, order is not part
  of it.""")
order_free = 0
for d in FIRING:
    al = alerts_of(d)
    times = sorted(a["detected_at"] for a in al)
    survived = True
    for perm in list(permutations(range(len(al))))[:120]:
        shuffled = [dict(al[i], detected_at=times[j]) for j, i in enumerate(perm)]
        if not verdict(shuffled):
            survived = False
            break
    order_free += survived
print("  verdict unchanged under EVERY tested reordering: %d of %d sessions"
      % (order_free, len(FIRING)))
print("  -> the danger tier is a SET condition. It cannot express deterioration.")
print("     (only `critical` reads time, via compression + continued escalation,")
print("      and critical never fired in this book - 0 of 203.)")

print()
print("=" * 78)
print("EPISODES  (each firing session, in order)")
print("=" * 78)
rows = []
for d in FIRING:
    moment, v, prefix = first_true_moment(d)
    al = alerts_of(d)
    tr = trades_of(d)
    before = [a for a in al if dt(a["detected_at"]) < moment]
    at = [a for a in al if dt(a["detected_at"]) == moment]
    after = [a for a in al if dt(a["detected_at"]) > moment]
    tr_before = [t for t in tr if dt(t["exit_time"]) <= moment]
    tr_after = [t for t in tr if dt(t["exit_time"]) > moment]
    pnl_before = sum(t["pnl"] for t in tr_before)
    pnl_after = sum(t["pnl"] for t in tr_after)
    danger_before = [a for a in before if a["severity"] in DANGER]

    print("\n%s   fires %s   domains=%s" % (d, v["severity"], "+".join(v["context"]["domains"])))
    print("   session: %d trades, P&L Rs %.0f" % (len(tr), DAYS[d]["pnl"]))
    print("   timeline:")
    for a in al:
        mark = "  <== SPIRAL CONDITION TRUE" if dt(a["detected_at"]) == moment and a in at else ""
        print("      %s  %-30s %-8s%s"
              % (a["detected_at"][11:16], a["pattern_type"], a["severity"], mark))
    print("   BEFORE the condition : %d alerts (%d already danger+), %d trades, Rs %.0f"
          % (len(before), len(danger_before), len(tr_before), pnl_before))
    print("   AFTER  the condition : %d alerts, %d trades, Rs %.0f"
          % (len(after), len(tr_after), pnl_after))
    rows.append(dict(day=d, moment=moment, n_alerts=len(al), before=len(before),
                     danger_before=len(danger_before), after_alerts=len(after),
                     tr=len(tr), tr_after=len(tr_after),
                     pnl=DAYS[d]["pnl"], pnl_after=pnl_after,
                     domains=v["context"]["domains"],
                     detectors=[a["pattern_type"] for a in prefix
                                if a["severity"] in DANGER]))

print()
print("=" * 78)
print("Q2  WHAT DID THE TRADER NOT ALREADY KNOW?")
print("=" * 78)
print("  A death_spiral at `danger` requires two danger+ events. Both are")
print("  themselves notifiable (NOTIFIABLE = {danger, critical}), so both have")
print("  already been pushed by the time the composite can exist.")
print()
print("  %-12s %-8s %-9s %s" % ("session", "alerts", "danger+", "already delivered before the composite"))
redundant = 0
for r in rows:
    # the composite's own trigger event is simultaneous, so "already known" is
    # everything strictly before plus the one that completes it
    known = r["danger_before"]
    inc = known < 1
    redundant += (not inc)
    print("  %-12s %-8d %-9d %s"
          % (r["day"], r["n_alerts"], known + 1,
             "%d danger alert(s) already sent; composite is the %dnd/rd"
             % (known, known + 1)))
print()
print("  every firing session had at least one danger alert ALREADY DELIVERED")
print("  before the composite became possible: %d of %d" % (redundant, len(rows)))

print()
print("=" * 78)
print("Q4  HOW MUCH SESSION IS LEFT?")
print("=" * 78)
print("  %-12s %-16s %-14s %s" % ("session", "trades after", "P&L after", "note"))
zero = 0
for r in rows:
    zero += r["tr_after"] == 0
    print("  %-12s %-16s Rs %-11.0f %s"
          % (r["day"], "%d of %d" % (r["tr_after"], r["tr"]), r["pnl_after"],
             "NOTHING LEFT TO ACT ON" if r["tr_after"] == 0 else ""))
after_all = sum(r["pnl_after"] for r in rows)
print("\n  sessions with zero trades remaining: %d of %d" % (zero, len(rows)))
print("  total P&L across everything that happened AFTER the condition: Rs %.0f"
      % after_all)
print("  (descriptive only - the alert did not intervene in this book)")

print()
print("=" * 78)
print("Q1  NEAR MISSES - is a firing session different from a bad session?")
print("=" * 78)


def profile(day):
    al = alerts_of(day)
    tr = trades_of(day)
    dgr = [a for a in al if a["severity"] in DANGER]
    doms = {nature(a["pattern_type"]) for a in dgr} - {None}
    return dict(day=day, n=len(al), dgr=len(dgr), doms=doms, tr=len(tr),
                pnl=DAYS[day]["pnl"],
                worst=min([t["pnl"] for t in tr], default=0.0))


P = {d: profile(d) for d in DAYS}
fire = set(FIRING)

# near-miss families, each one gate away from firing
nm_one_domain = [d for d, p in P.items() if d not in fire and p["dgr"] >= 2 and len(p["doms"]) == 1]
nm_single_dgr = [d for d, p in P.items() if d not in fire and p["dgr"] == 1 and p["n"] >= 2]
nm_two_dom_caution = []
for d, p in P.items():
    if d in fire or len(p["doms"]) >= 2:
        continue
    all_doms = {nature(a["pattern_type"]) for a in alerts_of(d)} - {None}
    if len(all_doms) >= 2 and "risk" in all_doms:
        nm_two_dom_caution.append(d)
quiet = [d for d, p in P.items() if d not in fire and p["n"] == 0]


def summarise(label, ds):
    if not ds:
        print("  %-34s n=0" % label)
        return
    def med(xs):
        xs = sorted(xs); return xs[len(xs)//2]
    print("  %-34s n=%3d  median P&L Rs %8.0f  losing %3d%%  median trades %2d  median worst-trade Rs %8.0f"
          % (label, len(ds), med([P[d]["pnl"] for d in ds]),
             round(100*sum(1 for d in ds if P[d]["pnl"] < 0)/len(ds)),
             med([P[d]["tr"] for d in ds]), med([P[d]["worst"] for d in ds])))


summarise("FIRING (2 domains, risk present)", sorted(fire))
summarise("NM-A 2+ danger, ONE domain only", nm_one_domain)
summarise("NM-B exactly 1 danger + others", nm_single_dgr)
summarise("NM-C 2 domains, 2nd only caution", nm_two_dom_caution)
summarise("no alerts at all", quiet)

print()
print("  Which detectors carry the ONE-domain near misses (NM-A)?")
c = Counter()
for d in nm_one_domain:
    for a in alerts_of(d):
        if a["severity"] in DANGER:
            c[a["pattern_type"]] += 1
for k, n in c.most_common():
    print("      %-32s %d   (domain=%s)" % (k, n, nature(k)))

print()
print("=" * 78)
print("REDUNDANCY - what pair actually carries every firing")
print("=" * 78)
pairs = Counter()
for r in rows:
    pairs[tuple(sorted(set(r["detectors"])))] += 1
for p, n in pairs.most_common():
    print("   %-64s %d" % (" + ".join(p), n))
