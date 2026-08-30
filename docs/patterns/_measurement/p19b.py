"""
p19 addendum. Two questions the main script left open.

1. Is "sizes DOWN after a winning run" a single-threshold artefact at n=3, or
   does it hold across run lengths? A monotone relationship would be evidence
   about the trader; one noisy cut would not.

2. Does the same trader size UP after a LOSING run? If they do, the sizing
   response to a run exists - it just points the other way, which is
   `martingale_behaviour`'s subject, not this detector's.
"""
import random
import sys
from statistics import mean, median

sys.path.insert(0, "D:/trade-psychology-ai")
sys.path.insert(0, "D:/trade-psychology-ai/backend")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

src = open("D:/trade-psychology-ai/docs/patterns/_measurement/p19_streak.py",
           encoding="utf-8").read()
exec(src.rsplit("\nmain()", 1)[0])

random.seed(20260830)


def loss_streak_len(prior):
    n = 0
    for t in reversed(prior):
        if float(t.realized_pnl or 0) < 0:
            n += 1
        else:
            break
    return n


def main():
    sessions = load()
    rows = []
    for _, tr in sessions:
        for i, ct in enumerate(tr):
            prior = tr[:i]
            if len(prior) < 3:
                continue
            r, _b = size_ratio(ct, prior)
            if r is None:
                continue
            rows.append((streak_len(prior), loss_streak_len(prior), r))

    print(f"comparable trades: {len(rows)}\n")

    print("=" * 70)
    print("1. SIZE RATIO BY LENGTH OF THE PRECEDING WINNING RUN")
    print("=" * 70)
    print(f"  {'run':>4} {'n':>5} {'median':>8} {'mean':>8} {'P(>=1.3x)':>11}")
    for k in range(0, 5):
        sel = [r for w, _l, r in rows if w == k]
        if not sel:
            continue
        p = sum(1 for r in sel if r >= CAUT_M) / len(sel)
        print(f"  {k:>4} {len(sel):>5} {median(sel):>8.2f} {mean(sel):>8.2f} {p:>10.1%}")
    sel = [r for w, _l, r in rows if w >= 3]
    if sel:
        p = sum(1 for r in sel if r >= CAUT_M) / len(sel)
        print(f"  {'>=3':>4} {len(sel):>5} {median(sel):>8.2f} {mean(sel):>8.2f} {p:>10.1%}")

    # rank correlation between run length and size ratio
    ws = [w for w, _l, _r in rows]
    rs = [r for _w, _l, r in rows]

    def rank(xs):
        order = sorted(range(len(xs)), key=lambda i: xs[i])
        rk = [0.0] * len(xs)
        for pos, i in enumerate(order):
            rk[i] = pos
        return rk

    rw, rr = rank(ws), rank(rs)
    mw, mr = mean(rw), mean(rr)
    num = sum((a - mw) * (b - mr) for a, b in zip(rw, rr))
    den = (sum((a - mw) ** 2 for a in rw) * sum((b - mr) ** 2 for b in rr)) ** 0.5
    rho = num / den if den else 0.0
    hits = 0
    for _ in range(20000):
        random.shuffle(rr)
        mr2 = mean(rr)
        n2 = sum((a - mw) * (b - mr2) for a, b in zip(rw, rr))
        if (n2 / den if den else 0.0) >= rho:
            hits += 1
    print(f"\n  Spearman rho(win-run length, size ratio) = {rho:+.3f}   "
          f"permutation p(>= observed) = {hits/20000:.3f}")
    print("  A positive rho is what the detector's theory predicts.")

    print("\n" + "=" * 70)
    print("2. THE MIRROR - size ratio after a LOSING run")
    print("=" * 70)
    print(f"  {'run':>4} {'n':>5} {'median':>8} {'mean':>8} {'P(>=1.3x)':>11}")
    for k in range(0, 5):
        sel = [r for _w, l, r in rows if l == k]
        if not sel:
            continue
        p = sum(1 for r in sel if r >= CAUT_M) / len(sel)
        print(f"  {k:>4} {len(sel):>5} {median(sel):>8.2f} {mean(sel):>8.2f} {p:>10.1%}")
    sel = [r for _w, l, r in rows if l >= 3]
    if sel:
        p = sum(1 for r in sel if r >= CAUT_M) / len(sel)
        print(f"  {'>=3':>4} {len(sel):>5} {median(sel):>8.2f} {mean(sel):>8.2f} {p:>10.1%}")


main()
