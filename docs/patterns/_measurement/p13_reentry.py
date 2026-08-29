"""
Pattern #13 — `rapid_reentry`, measured.

Source-list #5. Registry: nature=emotional, disposition=analytics,
trigger=exit, v2.0.0, severity always "info".

The claim, as shown (to whom, is part of what this measures):

  "NIFTY25APR24000CE: re-entered 3min after a Rs 2,400 loss on the same
   instrument."

Copy: "Re-entering the same instrument shortly after closing it at a loss. The
setup that just failed has not changed in those few minutes."

WHAT TO MEASURE

  1. firing rate, and what the 5-minute window excludes
  2. DOES THE WINDOW DECIDE ANYTHING? Distribution of same-symbol re-entry gaps
     after a loss. If most re-entries are inside 5 minutes anyway, the gate is
     selecting the base rate rather than a behaviour.
  3. sensitivity - how much does the firing set move at 3, 5, 10, 15, 30 min?
  4. overlap with its own family, "going back to the same trade":
     same_symbol_obsession and revenge_trade. If those two see every one of
     these, the third adds nothing.
  5. the session blend. threshold_resolution shrinks 5 toward the trader's
     median gap today. Does that move the firing set, and in which direction?
  6. consequence - is the re-entry itself worse than a non-rapid re-entry?
"""
import sys
from collections import Counter, defaultdict
from decimal import Decimal
from statistics import mean, median

sys.path.insert(0, "D:/trade-psychology-ai")
sys.path.insert(0, "D:/trade-psychology-ai/backend")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

src = open("D:/trade-psychology-ai/docs/patterns/_measurement/p12_stoploss.py",
           encoding="utf-8").read()
exec(src.rsplit("\nmain()", 1)[0])          # load(), ctx_for(), engine, build()

from app.core.trading_defaults import COLD_START_DEFAULTS   # noqa: E402
from app.core.detector_result import DetectorResult         # noqa: E402
from app.services.detector_registry import REGISTRY         # noqa: E402


def ctx_win(ct, prior, window):
    c = ctx_for(ct, prior)
    c.thresholds = {**COLD_START_DEFAULTS, "rapid_reentry_min": window}
    return c


def main():
    sessions = load()
    print(f"BOOK: {len(sessions)} sessions, {sum(len(t) for _, t in sessions)} rounds\n")

    # ------------------------------------------------------------ 1. funnel
    print("=" * 74)
    print("1. FUNNEL")
    print("=" * 74)
    n_all = n_prior = n_loss = n_win = 0
    fires = []
    gaps_after_loss = []
    for _, trades in sessions:
        for i, ct in enumerate(trades):
            n_all += 1
            prior = trades[:i]
            same = [t for t in prior if t.tradingsymbol == ct.tradingsymbol and t.exit_time]
            if not same:
                continue
            n_prior += 1
            last = max(same, key=lambda t: t.exit_time)
            if Decimal(str(last.realized_pnl or 0)) >= 0:
                continue
            n_loss += 1
            gap = (ct.entry_time - last.exit_time).total_seconds() / 60
            if gap >= 0:
                gaps_after_loss.append(gap)
            ev = engine._detect_rapid_reentry(ctx_for(ct, prior))
            if ev:
                n_win += 1
                fires.append((ct, ev, gap, i, trades))
    for label, n in (("all rounds", n_all), ("prior trade on same symbol", n_prior),
                     ("that prior trade was a LOSS", n_loss),
                     ("re-entered within 5 min -> FIRES", n_win)):
        print(f"  {label:36} {n:>5}")
    days = len({ct.exit_time.date() for ct, _, _, _, _ in fires})
    print(f"\n  {n_win} events across {days} sessions, severity: "
          f"{dict(Counter(e.severity for _, e, _, _, _ in fires))}")

    # ---------------------------------------------- 2. does the window decide
    print("\n" + "=" * 74)
    print("2. DOES THE 5-MINUTE WINDOW DECIDE ANYTHING?")
    print("=" * 74)
    g = sorted(gaps_after_loss)
    if g:
        def q(p): return g[min(int(len(g) * p), len(g) - 1)]
        print(f"  same-symbol re-entry gaps after a loss, n={len(g)} (minutes)")
        print(f"    p10 {q(.10):6.1f}   p25 {q(.25):6.1f}   median {median(g):6.1f}"
              f"   p75 {q(.75):6.1f}   p90 {q(.90):6.1f}")
        for t in (1, 3, 5, 10, 15, 30, 60):
            n = sum(1 for x in g if x <= t)
            print(f"    <= {t:>2} min: {n:>4} / {len(g)}  ({n / len(g):.1%})")

    # --------------------------------------------------- 3. window sensitivity
    print("\n" + "=" * 74)
    print("3. WINDOW SENSITIVITY")
    print("=" * 74)
    for w in (1, 3, 5, 10, 15, 30):
        c = 0
        for _, trades in sessions:
            for i, ct in enumerate(trades):
                if engine._detect_rapid_reentry(ctx_win(ct, trades[:i], w)):
                    c += 1
        mark = "   <-- current" if w == 5 else ""
        print(f"    window {w:>2} min -> {c:>4} events{mark}")

    # ------------------------------------------------------- 4. family overlap
    print("\n" + "=" * 74)
    print("4. OVERLAP WITH ITS OWN FAMILY  ('going back to the same trade')")
    print("=" * 74)
    fam = ("same_symbol_obsession", "revenge_trade")
    co = Counter(); alone = 0; any_other = Counter()
    for ct, _, _, i, trades in fires:
        c = ctx_for(ct, trades[:i])
        seen = set()
        for spec in REGISTRY:
            if spec.name == "rapid_reentry" or spec.trigger == "entry":
                continue
            m = getattr(engine, spec.method, None)
            if not m:
                continue
            try:
                r = m(c)
            except Exception:
                continue
            for x in (r if isinstance(r, list) else [r]):
                if x is None:
                    continue
                if isinstance(x, DetectorResult):
                    if x.fired:
                        seen.add(spec.name)
                elif getattr(x, "event_type", None):
                    seen.add(spec.name)
        for s in seen:
            any_other[s] += 1
        if seen & set(fam):
            co["family sees it"] += 1
        else:
            co["family MISSES it"] += 1
        if not seen:
            alone += 1
    print(f"  of {len(fires)} events:")
    for k, v in co.items():
        print(f"    {k:24} {v:>4}  ({v/max(len(fires),1):.0%})")
    print(f"    seen by NOTHING else     {alone:>4}  ({alone/max(len(fires),1):.0%})")
    print("\n  what else fires on them:")
    for n, c in any_other.most_common(8):
        print(f"    {n:32} {c:>4} / {len(fires)}  ({c/max(len(fires),1):.0%})")

    # ---------------------------------------------------- 5. consequence
    print("\n" + "=" * 74)
    print("5. CONSEQUENCE — is the rapid re-entry itself worse?")
    print("=" * 74)
    rapid_pnl, slow_pnl = [], []
    for _, trades in sessions:
        for i, ct in enumerate(trades):
            prior = trades[:i]
            same = [t for t in prior if t.tradingsymbol == ct.tradingsymbol and t.exit_time]
            if not same:
                continue
            last = max(same, key=lambda t: t.exit_time)
            if Decimal(str(last.realized_pnl or 0)) >= 0:
                continue
            gap = (ct.entry_time - last.exit_time).total_seconds() / 60
            if gap < 0:
                continue
            (rapid_pnl if gap <= 5 else slow_pnl).append(float(ct.realized_pnl))
    for label, xs in (("re-entry <= 5 min", rapid_pnl), ("re-entry  > 5 min", slow_pnl)):
        if xs:
            wins = sum(1 for x in xs if x > 0)
            print(f"  {label}  n={len(xs):>4}  mean Rs {mean(xs):>9,.0f}  "
                  f"median Rs {median(xs):>9,.0f}  win rate {wins/len(xs):.1%}")

    print("\n" + "=" * 74)
    print("6. PURITY / DB ACCESS")
    print("=" * 74)
    import inspect
    s = inspect.getsource(engine._detect_rapid_reentry)
    print(f"    reads ctx only    : {'db' not in s and 'await' not in s}")
    print(f"    imports in body   : {'import' in s}")
    print(f"    lines             : {len(s.splitlines())}")


main()
