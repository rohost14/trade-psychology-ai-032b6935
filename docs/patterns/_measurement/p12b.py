"""
Pattern #12 follow-up — is the consequence difference real?

p12_stoploss.py measured rest-of-session P&L of +296 after a flagged trade
against -518 after an unflagged one that cleared every gate but the loss
percentage. The flagged trades are followed by a BETTER session, which is the
same shape that retired Pattern 11.

Before reading anything into it, three things have to be ruled out:

  1. NOISE. 52 against 274, medians both zero, so the means are carried by a
     few sessions. Permutation test.
  2. POSITION IN SESSION. A bigger loss may simply arrive later in the day,
     leaving less session left to lose in. This is the confound that has
     distorted more than one pattern here already.
  3. STOPPING. If a flagged trade is usually the last of the day, "rest of
     session" is structurally zero and the mean says nothing about behaviour.

Also: what does the alert actually assert, and on how many trades can that
assertion be checked at all?
"""
import random
import sys
from collections import Counter
from decimal import Decimal
from statistics import mean, median

sys.path.insert(0, "D:/trade-psychology-ai")
sys.path.insert(0, "D:/trade-psychology-ai/backend")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

src = open("D:/trade-psychology-ai/docs/patterns/_measurement/p12_stoploss.py",
           encoding="utf-8").read()
exec(src.rsplit("\nmain()", 1)[0])          # helpers only, nothing runs

random.seed(20260829)


def collect():
    sessions = load()
    flagged, unflagged = [], []
    for _, trades in sessions:
        n = len(trades)
        for i, ct in enumerate(trades):
            if (ct.instrument_type or "") not in ("CE", "PE", "FUT"):
                continue
            if Decimal(str(ct.realized_pnl or 0)) >= 0:
                continue
            if (ct.duration_minutes or 0) < 5:
                continue
            entry = float(ct.avg_entry_price or 0) * (ct.total_quantity or 1)
            if entry <= 0:
                continue
            ev = engine._detect_no_stoploss(ctx_for(ct, trades[:i]))
            rec = {
                "rest": sum(float(t.realized_pnl) for t in trades[i + 1:]),
                "trades_left": n - i - 1,
                "pos_frac": i / max(n - 1, 1),
                "loss_pct": abs(float(ct.realized_pnl)) / entry * 100,
                "pnl": float(ct.realized_pnl),
                "is_last": i == n - 1,
            }
            (flagged if ev else unflagged).append(rec)
    return flagged, unflagged


def permutation(a, b, n=20000):
    """Two-sided: how often does a random split give a gap this large?"""
    obs = mean(a) - mean(b)
    pool = a + b
    k = len(a)
    hits = 0
    for _ in range(n):
        random.shuffle(pool)
        if abs(mean(pool[:k]) - mean(pool[k:])) >= abs(obs):
            hits += 1
    return obs, hits / n


def main():
    flagged, unflagged = collect()
    print(f"flagged {len(flagged)}   unflagged {len(unflagged)}\n")

    print("=" * 74)
    print("1. IS THE REST-OF-SESSION DIFFERENCE SIGNIFICANT?")
    print("=" * 74)
    obs, p = permutation([r["rest"] for r in flagged], [r["rest"] for r in unflagged])
    print(f"  observed difference in means: Rs {obs:>+10,.0f}")
    print(f"  permutation p (two-sided, 20k): {p:.3f}")
    print(f"  -> {'SIGNIFICANT' if p < 0.05 else 'NOT significant - consistent with chance'}")

    print("\n" + "=" * 74)
    print("2. POSITION-IN-SESSION CONFOUND")
    print("=" * 74)
    for label, xs in (("flagged", flagged), ("unflagged", unflagged)):
        print(f"  {label:10} mean position in session {mean(r['pos_frac'] for r in xs):.3f}"
              f"   median trades left {median([r['trades_left'] for r in xs]):.0f}"
              f"   last of day {sum(r['is_last'] for r in xs)}/{len(xs)}"
              f" ({sum(r['is_last'] for r in xs)/len(xs):.0%})")

    print("\n" + "=" * 74)
    print("3. CONTROLLING FOR IT — compare only where session remained")
    print("=" * 74)
    fa = [r["rest"] for r in flagged if r["trades_left"] >= 1]
    ua = [r["rest"] for r in unflagged if r["trades_left"] >= 1]
    if fa and ua:
        obs2, p2 = permutation(fa, ua)
        print(f"  flagged n={len(fa)} mean Rs {mean(fa):>+10,.0f}   "
              f"unflagged n={len(ua)} mean Rs {mean(ua):>+10,.0f}")
        print(f"  difference Rs {obs2:>+,.0f}   p = {p2:.3f}"
              f"  -> {'SIGNIFICANT' if p2 < 0.05 else 'NOT significant'}")

    print("\n" + "=" * 74)
    print("4. IS IT JUST LOSS SIZE? — matched on loss magnitude")
    print("=" * 74)
    # Unflagged losses in the top slice of the unflagged loss-% range, so both
    # groups are 'a meaningful loss', differing mainly by which side of 25% they
    # fell on.
    near = [r for r in unflagged if r["loss_pct"] >= 15]
    if near:
        obs3, p3 = permutation([r["rest"] for r in flagged], [r["rest"] for r in near])
        print(f"  flagged (>=25% loss)  n={len(flagged):>3} mean Rs {mean(r['rest'] for r in flagged):>+10,.0f}")
        print(f"  unflagged 15-25% loss n={len(near):>3} mean Rs {mean(r['rest'] for r in near):>+10,.0f}")
        print(f"  difference Rs {obs3:>+,.0f}   p = {p3:.3f}"
              f"  -> {'SIGNIFICANT' if p3 < 0.05 else 'NOT significant'}")

    print("\n" + "=" * 74)
    print("5. WHAT THE ALERT ASSERTS vs WHAT CAN BE CHECKED")
    print("=" * 74)
    print("  The message ends: 'No stop-loss order detected on this trade.'")
    print("  It is derived from the EXIT FILL's order type, via exit_order_types.")
    print(f"  In this book, order type is absent for every fill, so the claim was")
    print(f"  checkable on 0 of {len(flagged)} alerts.")
    print("  A trader holding a resting SL who exits manually first shows MKT and")
    print("  is told they had no stop - the inverse of the truth. The detector's")
    print("  own comment calls that 'benign'.")


main()
