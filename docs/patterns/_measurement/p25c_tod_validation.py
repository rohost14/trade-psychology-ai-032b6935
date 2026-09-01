"""
time_of_day_bias — are the learned danger hours real, and are 81 alerts meaningful?

The persistence chain turned out to be LIVE (see the correction in the design
doc), so the question is no longer "is it wired" but "should it fire".

Four tests:

  1. STABILITY. Learn danger_hours on the first half of the book and on the
     second. A rule that drives alerts must name the same hours in both, or it
     is describing noise that happened to land in one period.

  2. MULTIPLE COMPARISONS. The producer tests 7 hours at "win rate < 35% with
     >= 5 trades". Shuffle the hour labels across trades, keeping every trade's
     result, and count how often at least one hour clears that bar by chance.

  3. MEANINGFULNESS. Do the 81 flagged trades actually do worse than this
     trader's other trades? "The detector became reachable" and "the detector
     found something" are different claims.

  4. OVERLAP. What else already sees those 81 trades.
"""
import random
import sys
from collections import defaultdict
from statistics import mean, median

sys.path.insert(0, "D:/trade-psychology-ai")
sys.path.insert(0, "D:/trade-psychology-ai/backend")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

src = open("D:/trade-psychology-ai/docs/patterns/_measurement/p20_avgdown.py",
           encoding="utf-8").read()
src = src.replace("AVG = engine._detect_options_premium_avg_down\n", "")
exec(src.rsplit("\nmain()", 1)[0])

from app.core.trading_defaults import COLD_START_DEFAULTS   # noqa: E402
from collections import Counter                              # noqa: E402
from zoneinfo import ZoneInfo                                # noqa: E402

IST_TZ = ZoneInfo("Asia/Kolkata")
random.seed(20260901)
MIN_TRADES, WR_CUT = 5, 35.0


def learn(trades):
    """Exactly ai_personalization_service._learn_time_patterns' danger filter."""
    st = defaultdict(lambda: {"w": 0, "l": 0, "n": 0, "pnl": 0.0})
    for t in trades:
        h = t.entry_time.astimezone(IST_TZ).hour
        s = st[h]; s["n"] += 1; s["pnl"] += float(t.realized_pnl)
        if float(t.realized_pnl) > 0: s["w"] += 1
        elif float(t.realized_pnl) < 0: s["l"] += 1
    out = []
    for h, s in st.items():
        tot = s["w"] + s["l"]
        wr = (s["w"] / tot * 100) if tot else 50
        if wr < WR_CUT and s["n"] >= MIN_TRADES:
            out.append({"hour": h, "win_rate": round(wr, 1), "trades": s["n"],
                        "avg_pnl": round(s["pnl"] / s["n"], 2)})
    return sorted(out, key=lambda d: d["hour"]), st


def main():
    sessions = load_with_fills()
    trades = [t for _, ts in sessions for t in ts]
    print(f"BOOK: {len(sessions)} sessions, {len(trades)} rounds\n")

    full, _ = learn(trades)
    print("=" * 74)
    print("1. STABILITY — do the same hours appear in both halves?")
    print("=" * 74)
    mid = len(sessions) // 2
    h1 = [t for _, tr in sessions[:mid] for t in tr]
    h2 = [t for _, tr in sessions[mid:] for t in tr]
    d1, _ = learn(h1)
    d2, _ = learn(h2)
    print(f"  full book   : {[d['hour'] for d in full]}")
    print(f"  first half  : {[d['hour'] for d in d1]}   ({len(h1)} trades)")
    print(f"  second half : {[d['hour'] for d in d2]}   ({len(h2)} trades)")
    s1, s2 = {d["hour"] for d in d1}, {d["hour"] for d in d2}
    print(f"\n  hours flagged in BOTH halves : {sorted(s1 & s2) or 'NONE'}")
    print(f"  flagged in only one half     : {sorted(s1 ^ s2)}")

    # quarter-level
    q = len(sessions) // 4
    qs = [learn([t for _, tr in sessions[i*q:(i+1)*q] for t in tr])[0] for i in range(4)]
    print("\n  by quarter:")
    for i, dd in enumerate(qs, 1):
        print(f"    Q{i}: {[d['hour'] for d in dd]}")
    allq = Counter(h for dd in qs for h in [d["hour"] for d in dd])
    print(f"  hour appearing in all 4 quarters: "
          f"{[h for h, c in allq.items() if c == 4] or 'NONE'}")

    print("\n" + "=" * 74)
    print("2. MULTIPLE COMPARISONS — shuffle the hour labels")
    print("=" * 74)
    hours = [t.entry_time.astimezone(IST_TZ).hour for t in trades]
    pnls = [float(t.realized_pnl) for t in trades]
    real_n = len(full)
    hits = Counter()
    RUNS = 5000
    for _ in range(RUNS):
        random.shuffle(hours)
        st = defaultdict(lambda: {"w": 0, "l": 0, "n": 0})
        for h, p in zip(hours, pnls):
            s = st[h]; s["n"] += 1
            if p > 0: s["w"] += 1
            elif p < 0: s["l"] += 1
        k = 0
        for h, s in st.items():
            tot = s["w"] + s["l"]
            wr = (s["w"] / tot * 100) if tot else 50
            if wr < WR_CUT and s["n"] >= MIN_TRADES:
                k += 1
        hits[k] += 1
    ge = sum(v for k, v in hits.items() if k >= real_n)
    print(f"  real book flags {real_n} danger hour(s)")
    print(f"  shuffled label distribution over {RUNS} runs:")
    for k in sorted(hits):
        print(f"     {k} hour(s) flagged : {hits[k]:>5}  ({hits[k]/RUNS:.1%})")
    print(f"\n  p(chance flags >= {real_n}) = {ge/RUNS:.3f}")
    print("  Trades are NOT independent within a session, so this is a")
    print("  lower bound on the false-positive rate, not an exact test.")

    print("\n" + "=" * 74)
    print("3. MEANINGFULNESS — do the flagged trades actually do worse?")
    print("=" * 74)
    dh = {d["hour"] for d in full}
    flagged = [t for t in trades if t.entry_time.astimezone(IST_TZ).hour in dh
               and float(t.realized_pnl) != 0]
    rest = [t for t in trades if t.entry_time.astimezone(IST_TZ).hour not in dh]
    for label, grp in (("in a danger hour", flagged), ("every other hour", rest)):
        if grp:
            w = sum(1 for t in grp if float(t.realized_pnl) > 0) / len(grp)
            print(f"  {label:<20} n={len(grp):<4} win {w:>5.1%}  "
                  f"mean Rs {mean(float(t.realized_pnl) for t in grp):>8,.0f}  "
                  f"median Rs {median(float(t.realized_pnl) for t in grp):>7,.0f}")
    obs = mean(float(t.realized_pnl) for t in flagged) - mean(float(t.realized_pnl) for t in rest)
    pool = [float(t.realized_pnl) for t in flagged + rest]
    n1 = len(flagged); h = 0
    for _ in range(20000):
        random.shuffle(pool)
        if mean(pool[:n1]) - mean(pool[n1:]) <= obs: h += 1
    print(f"\n  difference {obs:+,.0f}   permutation p = {h/20000:.3f}")

    # per hour, so the thin one is visible
    print("\n  each flagged hour on its own:")
    _, st = learn(trades)
    for d in full:
        s = st[d["hour"]]
        print(f"    {d['hour']}:00  n={d['trades']:<4} win {d['win_rate']:>5.1f}%  "
              f"avg Rs {d['avg_pnl']:>8,.0f}")

    print("\n" + "=" * 74)
    print("4. OVERLAP — what already sees those trades?")
    print("=" * 74)
    others = ("_detect_revenge_trade", "_detect_no_stoploss", "_detect_premium_loss_event",
              "_detect_fomo_entry", "_detect_same_symbol_obsession",
              "_detect_martingale_behaviour", "_detect_overtrading_burst",
              "_detect_adding_to_adverse_position", "_detect_excess_exposure")
    co = Counter(); alone = 0; n = 0
    for _d, tr in sessions:
        for i, ct in enumerate(tr):
            if ct.entry_time.astimezone(IST_TZ).hour not in dh:
                continue
            n += 1
            c = ctx_fills(ct, tr[:i])
            hit = []
            for m in others:
                fn = getattr(engine, m, None)
                if fn:
                    try:
                        if fired(fn(c)): hit.append(m.replace("_detect_", ""))
                    except Exception: pass
            for x in hit: co[x] += 1
            if not hit: alone += 1
    print(f"  trades entered in a danger hour: {n}")
    for k, v in co.most_common():
        print(f"    {k:<32} {v:>3} / {n}  ({v/n:.0%})")
    print(f"  seen by NOTHING else: {alone} of {n} ({alone/n:.0%})")


main()
