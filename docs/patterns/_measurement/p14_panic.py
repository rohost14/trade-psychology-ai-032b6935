"""
`panic_exit` — is there a detectable behaviour here at all?

Not the Pattern 14 review. This answers the six questions asked before deciding
whether that review is worth running.

The detector is two conditions:  held < 5 min  AND  realised P&L < 0
(plus: the exit was not an SL execution).

THE DECIDING TEST

It fires on short LOSSES and never on short WINS. If this trader routinely holds
for under five minutes and wins roughly as often as they lose there, then a
short hold is their normal style and the detector is selecting on OUTCOME, not
on behaviour - labelling the losing half of an ordinary habit "panic".

That is measurable, and it decides the question. Everything else is secondary.
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
exec(src.rsplit("\nmain()", 1)[0])

from app.core.trading_defaults import COLD_START_DEFAULTS   # noqa: E402

random.seed(20260829)


def main():
    sessions = load()
    trades = [t for _, ts in sessions for t in ts]
    print(f"BOOK: {len(sessions)} sessions, {len(trades)} rounds\n")

    holds = [(t.duration_minutes or 0) for t in trades]
    pnls = [float(t.realized_pnl) for t in trades]

    # ---------------------------------------------------------------- 1 & 4
    print("=" * 74)
    print("1. WHAT IS 'SHORT' FOR THIS TRADER?  (personal baseline)")
    print("=" * 74)
    h = sorted(holds)
    def q(p): return h[min(int(len(h) * p), len(h) - 1)]
    print(f"  hold minutes over ALL {len(h)} rounds")
    print(f"    p10 {q(.10):5.0f}   p25 {q(.25):5.0f}   median {median(h):5.0f}"
          f"   p75 {q(.75):5.0f}   p90 {q(.90):5.0f}")
    for t in (1, 2, 5, 10, 15, 30):
        n = sum(1 for x in h if x < t)
        print(f"    < {t:>2} min: {n:>4} / {len(h)}  ({n/len(h):.1%})")
    under5 = sum(1 for x in h if x < 5)
    print(f"\n  -> a sub-5-minute hold is {under5/len(h):.0%} of everything this "
          f"trader does.")

    # ------------------------------------------------------------- THE TEST
    print("\n" + "=" * 74)
    print("2. THE DECIDING TEST — does it select BEHAVIOUR or OUTCOME?")
    print("=" * 74)
    short = [t for t in trades if (t.duration_minutes or 0) < 5]
    short_win = [t for t in short if float(t.realized_pnl) > 0]
    short_loss = [t for t in short if float(t.realized_pnl) < 0]
    long_ = [t for t in trades if (t.duration_minutes or 0) >= 5]
    long_win = [t for t in long_ if float(t.realized_pnl) > 0]

    print(f"  sub-5-minute holds : {len(short):>4}")
    print(f"    of which WINS    : {len(short_win):>4}  ({len(short_win)/max(len(short),1):.1%})")
    print(f"    of which LOSSES  : {len(short_loss):>4}  ({len(short_loss)/max(len(short),1):.1%})  <-- the ONLY ones that fire")
    print(f"  5-min-or-longer    : {len(long_):>4}   win rate {len(long_win)/max(len(long_),1):.1%}")
    print(f"\n  -> the detector ignores {len(short_win)} identical-behaviour trades")
    print(f"     purely because they made money.")

    # -------------------------------------------------------- is it unusual
    print("\n" + "=" * 74)
    print("3. IS A SHORT LOSING EXIT UNUSUAL FOR THIS TRADER?")
    print("=" * 74)
    losses = [t for t in trades if float(t.realized_pnl) < 0]
    print(f"  losses            : {len(losses)}")
    print(f"  losses under 5min : {len(short_loss)}  ({len(short_loss)/max(len(losses),1):.1%} of losses)")
    print(f"  sessions with >=1 : {len({t.exit_time.date() for t in short_loss})} of {len(sessions)}")
    per_day = Counter(t.exit_time.date() for t in short_loss)
    if per_day:
        print(f"  per active session: mean {mean(per_day.values()):.1f}  max {max(per_day.values())}")

    # ------------------------------------------------------- does it matter
    print("\n" + "=" * 74)
    print("4. IS THE SHORT LOSS WORSE THAN A LONGER ONE?")
    print("=" * 74)
    a = [float(t.realized_pnl) for t in short_loss]
    b = [float(t.realized_pnl) for t in losses if (t.duration_minutes or 0) >= 5]
    for lbl, xs in (("loss held < 5 min", a), ("loss held >= 5 min", b)):
        if xs:
            print(f"  {lbl}  n={len(xs):>4}  mean Rs {mean(xs):>9,.0f}  median Rs {median(xs):>9,.0f}")
    if a and b:
        obs = mean(a) - mean(b); pool = a + b; k = len(a); hits = 0
        for _ in range(20000):
            random.shuffle(pool)
            if abs(mean(pool[:k]) - mean(pool[k:])) >= abs(obs):
                hits += 1
        print(f"  difference Rs {obs:+,.0f}   permutation p = {hits/20000:.3f}")
        print(f"  -> a short loss is {'SMALLER' if obs > 0 else 'LARGER'} than a long one")

    # ------------------------------------------------------ actual firings
    print("\n" + "=" * 74)
    print("5. ACTUAL FIRINGS (real detector)")
    print("=" * 74)
    fires = []
    for _, ts in sessions:
        for i, ct in enumerate(ts):
            ev = engine._detect_panic_exit(ctx_for(ct, ts[:i]))
            if ev:
                fires.append((ct, ev))
    print(f"  {len(fires)} events across "
          f"{len({c.exit_time.date() for c, _ in fires})} sessions")
    print(f"  severity: {dict(Counter(e.severity for _, e in fires))}")
    tiny = sum(1 for c, _ in fires if abs(float(c.realized_pnl)) < 500)
    print(f"  of those, losses under Rs 500: {tiny} ({tiny/max(len(fires),1):.0%})")
    print(f"  median loss: Rs {median([abs(float(c.realized_pnl)) for c, _ in fires]):,.0f}")

    # ------------------------------------------------------ window sensitivity
    print("\n" + "=" * 74)
    print("6. WINDOW SENSITIVITY")
    print("=" * 74)
    for w in (1, 2, 3, 5, 10, 15):
        c = 0
        for _, ts in sessions:
            for i, ct in enumerate(ts):
                cx = ctx_for(ct, ts[:i])
                cx.thresholds = {**COLD_START_DEFAULTS, "panic_exit_min": w}
                if engine._detect_panic_exit(cx):
                    c += 1
        print(f"    window {w:>2} min -> {c:>4} events{'   <-- current' if w == 5 else ''}")

    # --------------------------------------------------------- the message
    print("\n" + "=" * 74)
    print("7. WHAT THE MESSAGE CLAIMS")
    print("=" * 74)
    if fires:
        print(f"  {fires[0][1].message}")
    print("\n  'no stop-loss order'  -> the Pattern 12 defect, unverifiable here")
    print("  'quick manual exit'   -> 'manual' is equally unknowable without an order type")
    print("  'panic'               -> the event name itself is an inference")


main()
