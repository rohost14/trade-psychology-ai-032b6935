"""
Pattern 19 — `winning_streak_overconfidence`, measured.

THE CLAIM, as shown to the trader:

  "Last 3 trades all won. NIFTY position jumped 62% above your session average
   (50->81 qty)."

It is a TWO-PART claim, and the second part is doing all the work:

  A. the last N session exits (any instrument) all won
  B. this position is >= 1.3x (or 2.0x) the average size of prior trades

Neither half alone is a behaviour. Traders have winning runs; traders vary size.
The claim is that B FOLLOWS FROM A - that the run is why the size went up. That
is an ORDERING claim, so the shuffle null decides it, exactly as it decided
`size_escalation` (p = 0.880) and `early_exit` (p = 0.610).

WHAT TO MEASURE

  1. does it fire at all, at which severity - the 22 Aug audit says the danger
     tier has never fired in 203 sessions. Confirm, and find out WHY: is it
     correctly silent or structurally unreachable?
  2. base rates. How common is a 3-win run? A 5-win run? If 3-in-a-row is
     routine for this trader, condition A is not selective.
  3. THE DECIDING TEST. P(size >= 1.3x avg | last 3 won) against
     P(size >= 1.3x avg | last 3 did NOT all win). If sizing up is equally
     likely either way, the streak is decoration and the detector is a
     size-outlier alarm wearing a psychology label.
  4. the shuffle null. Permute exit order within each session, keeping every
     trade's size and P&L, and re-run the REAL detector. Under the detector's
     own theory the real order should fire more than chance.
  5. the units switch. `_cross = len(prior_same) < 2` silently changes what is
     compared: RUPEES of notional when cross-instrument, CONTRACTS when
     same-underlying. The same 1.3 and 2.0 multipliers are applied to both.
     How many firings come from each branch?
  6. does it withhold? (the Pattern 9 question - a detector that fires on
     everything it can judge is not judging)
  7. consequence: are flagged trades worse than comparable unflagged ones?
     Ranks, cannot judge - per the design of record.
  8. overlap with the other sizing detectors.

HARNESS NOTE
`avg_entry_price` is REQUIRED here, not optional: the cross-instrument branch
compares `_notional` = qty * entry price. p14 did not need it. `validate()`
proves the detector fires before any number below is trusted.
"""
import random
import sys
from collections import Counter, defaultdict
from decimal import Decimal
from statistics import mean, median

sys.path.insert(0, "D:/trade-psychology-ai")
sys.path.insert(0, "D:/trade-psychology-ai/backend")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

src = open("D:/trade-psychology-ai/docs/patterns/_measurement/p12_stoploss.py",
           encoding="utf-8").read()
exec(src.rsplit("\nmain()", 1)[0])

from app.core.trading_defaults import COLD_START_DEFAULTS      # noqa: E402
from app.services.instrument_parser import parse_symbol as _ps  # noqa: E402

random.seed(20260830)

CAUT_N = COLD_START_DEFAULTS["overconfidence_win_streak_caution"]
DANG_N = COLD_START_DEFAULTS["overconfidence_win_streak_danger"]
CAUT_M = COLD_START_DEFAULTS["overconfidence_size_mul_caution"]
DANG_M = COLD_START_DEFAULTS["overconfidence_size_mul_danger"]

D = engine._detect_winning_streak_overconfidence


def und(t):
    try:
        return _ps(t.tradingsymbol or "").underlying or t.tradingsymbol or ""
    except Exception:
        return t.tradingsymbol or ""


def notional(t):
    return float(abs(t.total_quantity or 0)) * float(t.avg_entry_price or 0)


def won(t):
    return float(t.realized_pnl or 0) > 0


def streak_len(prior):
    """Trailing run of wins in an exit-ordered prior list."""
    n = 0
    for t in reversed(prior):
        if won(t):
            n += 1
        else:
            break
    return n


def size_ratio(ct, prior):
    """
    Reproduces the detector's own baseline choice, including the units switch.
    Returns (ratio, branch) or (None, branch) when there is no usable baseline.
    """
    u = und(ct)
    same = [t for t in prior if und(t) == u]
    cross = len(same) < 2
    pool = prior if cross else same
    if not pool:
        return None, "cross" if cross else "same"
    if cross:
        base = sum(notional(t) for t in pool) / len(pool)
        cur = max(notional(ct), 1.0)
    else:
        base = sum(t.total_quantity or 1 for t in pool) / len(pool)
        cur = ct.total_quantity or 1
    if not base:                      # F23: a zero baseline is not a small one
        return None, "cross" if cross else "same"
    return cur / base, ("cross" if cross else "same")


def fire_all(sessions):
    """Every firing, with the facts needed to interpret it."""
    out = []
    for day, trades in sessions:
        for i, ct in enumerate(trades):
            prior = trades[:i]
            ev = D(ctx_for(ct, prior))
            if ev:
                r, branch = size_ratio(ct, prior)
                out.append(dict(day=day, ct=ct, prior=prior, ev=ev, i=i,
                                ratio=r, branch=branch,
                                streak=streak_len(prior)))
    return out


def validate(sessions):
    n = sum(1 for _, tr in sessions for i, ct in enumerate(tr)
            if D(ctx_for(ct, tr[:i])))
    assert n > 0, "harness inert - detector never fires, every number below is meaningless"
    print(f"  harness validated: detector fires {n} times on the real book")
    return n


def main():
    sessions = load()
    trades = [t for _, ts in sessions for t in ts]
    print(f"BOOK: {len(sessions)} sessions, {len(trades)} rounds")
    print(f"THRESHOLDS: caution {CAUT_N} wins & {CAUT_M}x   "
          f"danger {DANG_N} wins & {DANG_M}x\n")
    validate(sessions)

    fires = fire_all(sessions)

    # ------------------------------------------------------------------ 1
    print("\n" + "=" * 74)
    print("1. DOES IT FIRE, AND AT WHICH SEVERITY")
    print("=" * 74)
    sev = Counter(f["ev"].severity for f in fires)
    days = len({f["day"] for f in fires})
    print(f"  {len(fires)} events / {days} sessions of {len(sessions)}")
    for s, n in sev.most_common():
        print(f"    {s:<8} {n}")
    if not sev.get("danger"):
        print("  -> DANGER NEVER FIRES. The 22 Aug audit note is confirmed.")

    # why not? how far does the book get toward the danger condition
    got5 = sum(1 for _, tr in sessions for i, ct in enumerate(tr)
               if streak_len(tr[:i]) >= DANG_N)
    got5_size = 0
    for _, tr in sessions:
        for i, ct in enumerate(tr):
            if streak_len(tr[:i]) >= DANG_N:
                r, _b = size_ratio(ct, tr[:i])
                if r and r >= DANG_M:
                    got5_size += 1
    print(f"\n  reachability of the danger tier:")
    print(f"    trades with a {DANG_N}-win run behind them : {got5}")
    print(f"    ...and size >= {DANG_M}x baseline           : {got5_size}")

    # ------------------------------------------------------------------ 2
    print("\n" + "=" * 74)
    print("2. BASE RATES - how selective is condition A (the streak)?")
    print("=" * 74)
    dist = Counter()
    for _, tr in sessions:
        for i, ct in enumerate(tr):
            dist[min(streak_len(tr[:i]), 8)] += 1
    tot = sum(dist.values())
    print(f"  trailing win-run length at the moment of each of {tot} trades")
    for k in sorted(dist):
        lbl = f"{k}" + ("+" if k == 8 else "")
        print(f"    {lbl:>2} wins behind it : {dist[k]:>4}  ({dist[k]/tot:6.1%})")
    ge3 = sum(v for k, v in dist.items() if k >= CAUT_N)
    ge5 = sum(v for k, v in dist.items() if k >= DANG_N)
    print(f"\n  >= {CAUT_N} wins behind it : {ge3} / {tot}  ({ge3/tot:.1%})")
    print(f"  >= {DANG_N} wins behind it : {ge5} / {tot}  ({ge5/tot:.1%})")
    wr = sum(1 for t in trades if won(t)) / len(trades)
    print(f"\n  overall win rate {wr:.1%} -> if wins were independent, "
          f"P(3 in a row) = {wr**3:.1%}, P(5 in a row) = {wr**5:.1%}")

    # ------------------------------------------------------------------ 3
    print("\n" + "=" * 74)
    print("3. THE DECIDING TEST - does a winning run predict sizing up?")
    print("=" * 74)
    after_streak, after_not = [], []
    for _, tr in sessions:
        for i, ct in enumerate(tr):
            prior = tr[:i]
            if len(prior) < CAUT_N:
                continue
            r, _b = size_ratio(ct, prior)
            if r is None:
                continue
            (after_streak if streak_len(prior) >= CAUT_N else after_not).append(r)

    def rate(rs, m):
        return sum(1 for r in rs if r >= m) / len(rs) if rs else float("nan")

    print(f"  comparable trades: {len(after_streak)} after a {CAUT_N}+ win run, "
          f"{len(after_not)} otherwise")
    print(f"\n  P(size >= {CAUT_M}x baseline)")
    print(f"    after a {CAUT_N}-win run : {rate(after_streak, CAUT_M):.1%}")
    print(f"    otherwise          : {rate(after_not, CAUT_M):.1%}")
    print(f"\n  P(size >= {DANG_M}x baseline)")
    print(f"    after a {CAUT_N}-win run : {rate(after_streak, DANG_M):.1%}")
    print(f"    otherwise          : {rate(after_not, DANG_M):.1%}")
    if after_streak and after_not:
        print(f"\n  median size ratio  after run {median(after_streak):.2f}"
              f"   otherwise {median(after_not):.2f}")
        print(f"  mean   size ratio  after run {mean(after_streak):.2f}"
              f"   otherwise {mean(after_not):.2f}")

    # permutation test on the difference in rates
    obs = rate(after_streak, CAUT_M) - rate(after_not, CAUT_M)
    pool = after_streak + after_not
    k = len(after_streak)
    hits = 0
    RUNS = 20000
    for _ in range(RUNS):
        random.shuffle(pool)
        d = rate(pool[:k], CAUT_M) - rate(pool[k:], CAUT_M)
        if d >= obs:
            hits += 1
    print(f"\n  label-permutation null on that difference "
          f"(observed {obs:+.1%}): p = {hits/RUNS:.3f}")

    # ------------------------------------------------------------------ 4
    print("\n" + "=" * 74)
    print("4. THE SHUFFLE NULL - permute exit order, run the REAL detector")
    print("=" * 74)
    print("  The detector's claim is that the RUN causes the SIZE. Shuffling")
    print("  order destroys that link while keeping every size and every P&L.")
    real = len(fires)
    counts = []
    for _ in range(2000):
        n = 0
        for _day, tr in sessions:
            sh = list(tr)
            random.shuffle(sh)
            for i, ct in enumerate(sh):
                if D(ctx_for(ct, sh[:i])):
                    n += 1
        counts.append(n)
    ge = sum(1 for c in counts if c >= real)
    print(f"\n  real trade order      : {real} firings")
    print(f"  shuffled order (2000) : mean {mean(counts):.1f}  "
          f"median {median(counts):.0f}  min {min(counts)}  max {max(counts)}")
    print(f"  p(shuffled >= real)   : {ge/len(counts):.3f}")

    # ------------------------------------------------------------------ 5
    print("\n" + "=" * 74)
    print("5. THE UNITS SWITCH - rupees or contracts?")
    print("=" * 74)
    br = Counter(f["branch"] for f in fires)
    print(f"  firings by baseline branch: {dict(br)}")
    print("    'cross' compares RUPEES of notional; 'same' compares CONTRACTS.")
    print(f"    Both are tested against the same {CAUT_M} / {DANG_M} multipliers.")
    allbr = Counter()
    for _, tr in sessions:
        for i, ct in enumerate(tr):
            if len(tr[:i]) >= CAUT_N:
                _r, b = size_ratio(ct, tr[:i])
                allbr[b] += 1
    print(f"  eligible trades by branch : {dict(allbr)}")
    print("\n  message check - the copy always says 'qty':")
    for f in fires[:6]:
        print(f"    [{f['branch']:>5}] {f['ev'].message[:96]}")

    # ------------------------------------------------------------------ 6
    print("\n" + "=" * 74)
    print("6. DOES IT WITHHOLD?  (the Pattern 9 question)")
    print("=" * 74)
    elig = 0
    for _, tr in sessions:
        for i, ct in enumerate(tr):
            if streak_len(tr[:i]) >= CAUT_N:
                r, _b = size_ratio(ct, tr[:i])
                if r is not None:
                    elig += 1
    print(f"  trades meeting condition A with a usable baseline : {elig}")
    print(f"  of those, fired                                   : {len(fires)}")
    if elig:
        print(f"  -> withholds on {elig - len(fires)} of {elig} "
              f"({1 - len(fires)/elig:.0%})")

    # ------------------------------------------------------------------ 7
    print("\n" + "=" * 74)
    print("7. CONSEQUENCE - ranks, cannot judge")
    print("=" * 74)
    fl = [float(f["ct"].realized_pnl) for f in fires]
    fids = {id(f["ct"]) for f in fires}
    # control: same condition A, usable baseline, but size below the multiplier
    ctrl = []
    for _, tr in sessions:
        for i, ct in enumerate(tr):
            if id(ct) in fids:
                continue
            if streak_len(tr[:i]) >= CAUT_N:
                r, _b = size_ratio(ct, tr[:i])
                if r is not None:
                    ctrl.append(float(ct.realized_pnl))
    if fl:
        print(f"  flagged   n={len(fl):<4} mean Rs {mean(fl):>9,.0f}  "
              f"median Rs {median(fl):>8,.0f}  win {sum(1 for x in fl if x>0)/len(fl):.1%}")
    if ctrl:
        print(f"  unflagged n={len(ctrl):<4} mean Rs {mean(ctrl):>9,.0f}  "
              f"median Rs {median(ctrl):>8,.0f}  win {sum(1 for x in ctrl if x>0)/len(ctrl):.1%}")
        print("    (same streak condition, size below the multiplier)")
    if fl and ctrl:
        obs2 = mean(fl) - mean(ctrl)
        both = fl + ctrl
        n1 = len(fl)
        h = 0
        for _ in range(20000):
            random.shuffle(both)
            if mean(both[:n1]) - mean(both[n1:]) <= obs2:
                h += 1
        print(f"  difference {obs2:+,.0f}  permutation p(shuffled <= observed) = "
              f"{h/20000:.3f}")

    # ------------------------------------------------------------------ 8
    print("\n" + "=" * 74)
    print("8. OVERLAP - what else sees these trades?")
    print("=" * 74)
    others = ("_detect_martingale_behaviour", "_detect_post_loss_recovery_bet",
              "_detect_same_symbol_obsession", "_detect_overtrading_burst",
              "_detect_fomo_entry", "_detect_no_stoploss",
              "_detect_options_premium_avg_down")
    co = Counter()
    alone = 0
    for f in fires:
        c = ctx_for(f["ct"], f["prior"])
        hit = []
        for m in others:
            fn = getattr(engine, m, None)
            if not fn:
                continue
            try:
                r = fn(c)
            except Exception:
                continue
            fired = bool(getattr(r, "fired", r))
            if fired:
                hit.append(m.replace("_detect_", ""))
        for h_ in hit:
            co[h_] += 1
        if not hit:
            alone += 1
    print(f"  co-firing detectors across the {len(fires)} events:")
    for k, v in co.most_common():
        print(f"    {k:<32} {v}")
    print(f"  fired ALONE on {alone} of {len(fires)} "
          f"({alone/len(fires):.0%})" if fires else "")

    # ------------------------------------------------------------------ 9
    print("\n" + "=" * 74)
    print("9. THE FIRINGS THEMSELVES")
    print("=" * 74)
    for f in fires:
        c = f["ev"].context
        print(f"  {f['day']}  streak={f['streak']}  branch={f['branch']:>5}  "
              f"ratio={f['ratio']:.2f}  pnl=Rs {float(f['ct'].realized_pnl):>9,.0f}  "
              f"{f['ct'].tradingsymbol}")
        print(f"      baseline={c['avg_baseline_qty']}  current={c['current_qty']}  "
              f"escalation={c['escalation_pct']}%  streak_profit=Rs {c['streak_profit']:,.0f}")


main()
