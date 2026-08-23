"""
15 loss-chasing signatures, each measured independently.

Method: every signature is measured AFTER A LOSS and AFTER A WIN. The post-win
rate is the control. No thresholds are invented anywhere - "unusually fast" means
"faster than this same trader after a win", which the data answers by itself.
"""
import json
import sys
from collections import Counter, defaultdict

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
D = json.load(open("docs/research/data/signatures.json"))
T, S = D["trades"], D["sessions"]
L = [r for r in T if not r["won"] and r["next_sym"]]
W = [r for r in T if r["won"] and r["next_sym"]]


def pct(rows, f):
    ok = [r for r in rows if f(r) is not None]
    if not ok:
        return None, 0
    return 100.0 * sum(1 for r in ok if f(r)) / len(ok), len(ok)


def med(xs):
    xs = sorted(x for x in xs if x is not None)
    return xs[len(xs) // 2] if xs else None


def line(name, f):
    a, na = pct(L, f)
    b, nb = pct(W, f)
    d = (a - b) if (a is not None and b is not None) else None
    print(f"{name:<46} after-loss {a:5.1f}% (n={na:4})   after-win {b:5.1f}% (n={nb:4})"
          f"   diff {d:+5.1f}pp")
    return d


print(f"=== BOOK: {len(S)} sessions, {len(T)} round-trips, "
      f"{sum(1 for r in T if not r['won'])} losses, {len(L)} losses with a next trade\n")

print("--- S1 fast re-entry ---")
gl = [r["gap_to_next"] for r in L]
gw = [r["gap_to_next"] for r in W]
print(f"  median gap after loss {med(gl)}  after win {med(gw)} (min)")
line("S1  re-entry faster than session median", lambda r: (
    r["gap_to_next"] < r["session_med_gap"] if r["gap_to_next"] is not None
    and r["session_med_gap"] else None))

print("\n--- S2/S3 size and risk ---")
line("S2  next position larger (qty)", lambda r: (
    r["next_qty"] > r["qty"] if r["next_qty"] else None))
line("S3  next position higher risk", lambda r: (
    r["next_risk"] > r["risk"] if r["next_risk"] and r["risk"] else None))

print("\n--- S4/S5/S6 instrument and direction ---")
line("S4  same underlying", lambda r: r["next_und"] == r["und"])
line("S5  same underlying AND same direction",
     lambda r: r["next_und"] == r["und"] and r["next_dir"] == r["dir"])
line("S6  different instrument but larger risk", lambda r: (
    r["next_und"] != r["und"] and r["next_risk"] > r["risk"]
    if r["next_risk"] and r["risk"] else None))

print("\n--- S7 frequency burst ---")
print(f"  median trades within 30min of exit: loss {med([r['burst_30min'] for r in L])}"
      f"  win {med([r['burst_30min'] for r in W])}")
line("S7  3+ trades within 30 min of the exit", lambda r: r["burst_30min"] >= 3)

print("\n--- S8 repeated recovery attempts (consecutive-loss runs) ---")
runs, cur = [], 0
bysess = defaultdict(list)
for r in T:
    bysess[r["day"]].append(r)
for day, rows in bysess.items():
    cur = 0
    for r in sorted(rows, key=lambda x: x["idx"]):
        if not r["won"]:
            cur += 1
        else:
            if cur:
                runs.append(cur)
            cur = 0
    if cur:
        runs.append(cur)
print("  loss-run length distribution:", dict(sorted(Counter(runs).items())))
print(f"  runs of 3+: {sum(1 for x in runs if x >= 3)} of {len(runs)}")

print("\n--- S9 session P&L deterioration ---")
print(f"  median rest-of-session P&L after a loss {med([r['rest_of_session_pnl'] for r in L]):,.0f}"
      f"   after a win {med([r['rest_of_session_pnl'] for r in W]):,.0f}")
line("S9  rest of session is negative", lambda r: r["rest_of_session_pnl"] < 0)

print("\n--- S10 deviation from the trader's own normal ---")
line("S10 next qty above session median size", lambda r: (
    r["next_qty"] > r["session_med_qty"] if r["next_qty"] and r["session_med_qty"] else None))

print("\n--- S11 combinations ---")
def sigs(r):
    n = 0
    if r["gap_to_next"] is not None and r["session_med_gap"] and r["gap_to_next"] < r["session_med_gap"]:
        n += 1
    if r["next_qty"] and r["next_qty"] > r["qty"]:
        n += 1
    if r["next_und"] == r["und"]:
        n += 1
    if r["next_und"] == r["und"] and r["next_dir"] == r["dir"]:
        n += 1
    return n
cl, cw = Counter(sigs(r) for r in L), Counter(sigs(r) for r in W)
for k in range(5):
    a = 100.0 * cl[k] / len(L)
    b = 100.0 * cw[k] / len(W)
    print(f"  {k} of 4 signals co-occur:  after-loss {a:5.1f}%   after-win {b:5.1f}%   {a-b:+5.1f}pp")

print("\n--- S12 next-day loss-chasing ---")
S2 = sorted(S, key=lambda x: x["day"])
after_loss_day, after_win_day = [], []
for a, b in zip(S2, S2[1:]):
    tgt = after_loss_day if a["pnl"] < 0 else after_win_day
    tgt.append(b)
for nm, g in (("after a losing day", after_loss_day), ("after a winning day", after_win_day)):
    print(f"  {nm:<20} n={len(g):3}  median trades {med([x['trades'] for x in g])}"
          f"   median first-trade qty {med([x['first_qty'] for x in g])}"
          f"   median day P&L {med([x['pnl'] for x in g]):,.0f}")

print("\n--- S13 abandoning stops --- UNOBSERVABLE (no order-type column in tradebook)")

print("\n--- S14 recovery-target-like sizing ---")
line("S14 next trade's risk >= the loss just taken", lambda r: (
    r["next_risk"] >= r["loss"] if r["next_risk"] and r["loss"] else None))

print("\n--- S15 rotation revenge (3 different underlyings, risk rising) ---")
rot_l = rot_w = 0
examples = []
for day, rows in bysess.items():
    rows = sorted(rows, key=lambda x: x["idx"])
    for i in range(len(rows) - 2):
        a, b, c = rows[i], rows[i + 1], rows[i + 2]
        if len({a["und"], b["und"], c["und"]}) == 3 and a["risk"] < b["risk"] < c["risk"]:
            if a["won"]:
                rot_w += 1
            else:
                rot_l += 1
                examples.append((day, a["und"], b["und"], c["und"],
                                 round(a["risk"]), round(b["risk"]), round(c["risk"]),
                                 round(a["pnl"]), round(b["pnl"]), round(c["pnl"])))
print(f"  starting from a LOSS: {rot_l}   starting from a WIN: {rot_w}")
for e in examples[:12]:
    print("   ", e)

print("\n=== representative post-loss sequences (largest losses with a next trade) ===")
for r in sorted(L, key=lambda x: -x["loss"])[:15]:
    print(f"  {r['day']} #{r['idx']:<2} {r['und']:<10} loss {r['loss']:>8,.0f} "
          f"risk {r['risk']:>8,.0f} -> next {r['next_und']:<10} risk {r['next_risk']:>8,.0f} "
          f"gap {r['gap_to_next'] if r['gap_to_next'] is None else round(r['gap_to_next'])!s:>5}m "
          f"same_dir {r['next_dir']==r['dir']!s:<5} next_pnl {r['next_pnl']:>9,.0f} "
          f"rest {r['rest_of_session_pnl']:>10,.0f}")

json.dump({"n_sessions": len(S), "n_trades": len(T), "n_losses_with_next": len(L)},
          open("docs/research/data/analysis_meta.json", "w"))
