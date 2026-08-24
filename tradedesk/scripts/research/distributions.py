"""
Point 2 — do defensible separations exist in the candidate measures?

Bar set BEFORE looking, so the answer cannot be fitted to the data:

  A separation counts only if the distribution shows it - a gap with no mass in
  it, or two distinguishable modes. A percentile is not a separation; it is a
  number I chose, and choosing one is how S2a and the exposure ratio were
  invented and then refuted.

Control throughout: the FAVOURABLE adds. If adverse adds look like favourable
adds on a measure, that measure is describing scaling into a position, not
reacting to a loss.
"""
import json
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
E = json.load(open(r"C:\Users\being\.claude\jobs\33a73186/tmp/adverse_adds.json"))

adv = [a for e in E for a in e["adds"] if a["adverse_pct"] > 0]
fav = [a for e in E for a in e["adds"] if a["adverse_pct"] <= 0]


def hist(vals, lo, hi, step, label, width=54):
    print(f"\n{label}   n={len(vals)}")
    edges = []
    x = lo
    while x < hi:
        edges.append((x, x + step))
        x += step
    mx = 0
    rows = []
    for a, b in edges:
        c = sum(1 for v in vals if a <= v < b)
        rows.append((a, b, c))
        mx = max(mx, c)
    over = sum(1 for v in vals if v >= hi)
    for a, b, c in rows:
        bar = "#" * int(round(width * c / mx)) if mx else ""
        print(f"  {a:6.1f}-{b:<6.1f} {c:>4} {bar}")
    if over:
        print(f"  {hi:6.1f}+       {over:>4} {'#' * int(round(width*over/mx))}")


def pct(vals, q):
    v = sorted(vals)
    return v[min(int(q * len(v)), len(v) - 1)]


print("=" * 70)
print("MEASURE 1 — % adverse movement at the moment of adding")
print("=" * 70)
hist([a["adverse_pct"] for a in adv], 0, 40, 2.5, "adverse adds")
v = [a["adverse_pct"] for a in adv]
print(f"\n  p10 {pct(v,.10):.1f}  p25 {pct(v,.25):.1f}  p50 {pct(v,.50):.1f}  "
      f"p75 {pct(v,.75):.1f}  p90 {pct(v,.90):.1f}  max {max(v):.1f}")
print(f"  favourable adds, same measure (negative = in profit): "
      f"p50 {pct([a['adverse_pct'] for a in fav],.50):.1f}")
gaps = []
sv = sorted(v)
for i in range(1, len(sv)):
    if sv[i] - sv[i - 1] > 2.0:
        gaps.append((round(sv[i - 1], 1), round(sv[i], 1)))
print(f"  empty gaps wider than 2pp inside the range: {gaps if gaps else 'none'}")

print("\n" + "=" * 70)
print("MEASURE 2 — % additional exposure vs exposure already held")
print("=" * 70)
# For a long option, exposure added = add_qty * add_price; held = qty_before * avg_before.
def exp_ratio(a):
    held = abs(a["qty_before"]) * a["avg_before"]
    added = abs(a["add_qty"]) * a["price"]
    return 100 * added / held if held else 0


ea = [exp_ratio(a) for a in adv]
ef = [exp_ratio(a) for a in fav]
hist(ea, 0, 160, 10, "adverse adds — exposure added as % of exposure held")
print(f"\n  adverse   p25 {pct(ea,.25):.0f}%  p50 {pct(ea,.50):.0f}%  p75 {pct(ea,.75):.0f}%  max {max(ea):.0f}%")
print(f"  favourable p25 {pct(ef,.25):.0f}%  p50 {pct(ef,.50):.0f}%  p75 {pct(ef,.75):.0f}%  max {max(ef):.0f}%")
print("  NOTE: adding at a LOWER price adds less exposure per lot, so a 1.0x")
print("        quantity add is always BELOW 100% exposure when averaging down.")
print(f"  quantity ratio for the same adds: p50 {pct([a['add_ratio'] for a in adv],.50):.2f}x  "
      f"max {max(a['add_ratio'] for a in adv):.2f}x")

print("\n" + "=" * 70)
print("MEASURE 3 — cumulative exposure increase over the whole episode")
print("=" * 70)
cum = []
for e in E:
    if not any(a["adverse_pct"] > 0 for a in e["adds"]):
        continue
    first = e["adds"][0]
    held0 = abs(first["qty_before"]) * first["avg_before"]
    total_added = sum(abs(a["add_qty"]) * a["price"] for a in e["adds"])
    cum.append(100 * total_added / held0 if held0 else 0)
hist(cum, 0, 400, 25, "cumulative exposure added as % of the original entry")
print(f"\n  p25 {pct(cum,.25):.0f}%  p50 {pct(cum,.50):.0f}%  p75 {pct(cum,.75):.0f}%  max {max(cum):.0f}%")

print("\n" + "=" * 70)
print("MEASURE 4 — repetition: adverse adds within one position")
print("=" * 70)
rep = Counter(sum(1 for a in e["adds"] if a["adverse_pct"] > 0)
              for e in E if any(a["adverse_pct"] > 0 for a in e["adds"]))
tot = sum(rep.values())
run = 0
for k in sorted(rep):
    run += rep[k]
    print(f"  {k} adverse add(s): {rep[k]:>3} positions   ({100*rep[k]/tot:>5.1f}%)   "
          f"cumulative {100*run/tot:>5.1f}%")

print("\n" + "=" * 70)
print("MEASURE 5 — progression: does the adverse depth deepen across the episode?")
print("=" * 70)
mono = deeper = flat = 0
for e in E:
    a = [x["adverse_pct"] for x in e["adds"] if x["adverse_pct"] > 0]
    if len(a) < 2:
        continue
    if all(b > c for c, b in zip(a, a[1:])):
        mono += 1
    elif a[-1] > a[0]:
        deeper += 1
    else:
        flat += 1
print(f"  positions with 2+ adverse adds: {mono+deeper+flat}")
print(f"    strictly deepening each time : {mono}")
print(f"    deeper at the end than start : {deeper}")
print(f"    not deepening                : {flat}")

print("\n" + "=" * 70)
print("CONTROL — is any measure different for adverse vs favourable adds?")
print("=" * 70)
print(f"  exposure added %:  adverse p50 {pct(ea,.50):.0f}%   favourable p50 {pct(ef,.50):.0f}%")
print(f"  quantity ratio  :  adverse p50 {pct([a['add_ratio'] for a in adv],.50):.2f}x   "
      f"favourable p50 {pct([a['add_ratio'] for a in fav],.50):.2f}x")
print(f"  |move| at add   :  adverse p50 {pct([abs(a['adverse_pct']) for a in adv],.50):.1f}%   "
      f"favourable p50 {pct([abs(a['adverse_pct']) for a in fav],.50):.1f}%")
