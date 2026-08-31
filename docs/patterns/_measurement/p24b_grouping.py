"""
Is strategy grouping reliable enough to net P&L across legs?

The per-trade loss rule was approved to use NET strategy P&L for multi-leg
positions — but only if reliable grouping exists. This measures whether it
does, using the real detector's own criteria.

`strategy_detector._find_siblings` matches:

    same account
    entry_time within +/- 15 minutes
    DIFFERENT tradingsymbol
    SAME underlying
    a parseable expiry

That is "same underlying, entered close together". Two things to test:

  1. HOW OFTEN does it group, and do the groups look like structures or like
     coincidence? Two independent directional bets on NIFTY ten minutes apart
     match every one of those criteria.

  2. THE FIRST-LEG PROBLEM. `_find_siblings` queries CompletedTrade, so a
     sibling must ALREADY HAVE CLOSED. The group therefore does not exist when
     the first leg closes — the detector's own docstring says so: "The FIRST
     leg of a strategy may still fire some alerts (we don't know it's a
     strategy leg until the second leg closes)."

     For a rule that must choose between leg P&L and net P&L, that is decisive:
     the same structure would be judged leg-level at one exit and net-level at
     the next.
"""
import sys
from collections import Counter
from datetime import timedelta
from statistics import median

sys.path.insert(0, "D:/trade-psychology-ai")
sys.path.insert(0, "D:/trade-psychology-ai/backend")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

src = open("D:/trade-psychology-ai/docs/patterns/_measurement/p20_avgdown.py",
           encoding="utf-8").read()
src = src.replace("AVG = engine._detect_options_premium_avg_down\n", "")
exec(src.rsplit("\nmain()", 1)[0])

from app.services.instrument_parser import parse_symbol as _ps   # noqa: E402
from app.services.strategy_detector import ENTRY_WINDOW_MINUTES  # noqa: E402

W = timedelta(minutes=ENTRY_WINDOW_MINUTES)


def parsed(t):
    try:
        return _ps(t.tradingsymbol or "")
    except Exception:
        return None


def siblings_of(ct, day_trades):
    """The detector's own criteria, applied to the reconstructed book."""
    p = parsed(ct)
    if p is None or not p.underlying:
        return []
    out = []
    for c in day_trades:
        if c.id == ct.id or c.tradingsymbol == ct.tradingsymbol:
            continue
        if not c.entry_time or not ct.entry_time:
            continue
        if not (ct.entry_time - W <= c.entry_time <= ct.entry_time + W):
            continue
        q = parsed(c)
        if q is None or q.underlying != p.underlying or not q.expiry_key:
            continue
        if q.instrument_type == "EQ":
            continue
        out.append(c)
    return out


def main():
    sessions = load_with_fills()
    trades = [t for _, ts in sessions for t in ts]
    print(f"BOOK: {len(sessions)} sessions, {len(trades)} rounds")
    print(f"WINDOW: +/- {ENTRY_WINDOW_MINUTES} min on entry, same underlying\n")

    print("=" * 74)
    print("1. HOW OFTEN WOULD THE DETECTOR GROUP?")
    print("=" * 74)
    with_sib = 0
    sib_counts = Counter()
    for _d, tr in sessions:
        for ct in tr:
            s = siblings_of(ct, tr)
            if s:
                with_sib += 1
                sib_counts[min(len(s), 5)] += 1
    print(f"  rounds with >= 1 candidate sibling : {with_sib} of {len(trades)} "
          f"({with_sib/len(trades):.0%})")
    for k in sorted(sib_counts):
        lbl = f"{k}+" if k == 5 else str(k)
        print(f"    {lbl} siblings : {sib_counts[k]}")

    print("\n" + "=" * 74)
    print("2. THE FIRST-LEG PROBLEM — was a sibling already CLOSED at this exit?")
    print("=" * 74)
    print("  `_find_siblings` queries CompletedTrade, so a sibling only counts")
    print("  once it has closed. This is what the rule would actually see.\n")
    net_view = leg_view = 0
    for _d, tr in sessions:
        for ct in tr:
            s = siblings_of(ct, tr)
            if not s:
                continue
            closed_first = [c for c in s if c.exit_time <= ct.exit_time]
            if closed_first:
                net_view += 1
            else:
                leg_view += 1
    tot = net_view + leg_view
    print(f"  of the {tot} rounds with a sibling:")
    print(f"    a sibling had ALREADY closed -> NET view  : {net_view} ({net_view/tot:.0%})")
    print(f"    no sibling closed yet        -> LEG view  : {leg_view} ({leg_view/tot:.0%})")
    print("\n  -> the SAME structure is judged leg-level at its first exit and")
    print("     net-level at the next. The rule's answer depends on close order.")

    print("\n" + "=" * 74)
    print("3. DO THE GROUPS LOOK LIKE STRUCTURES, OR LIKE COINCIDENCE?")
    print("=" * 74)
    print("  A real structure is usually entered together AND closed together.")
    print("  Two independent bets on one underlying are not.\n")
    entry_gaps, exit_gaps = [], []
    same_type = diff_type = 0
    for _d, tr in sessions:
        for ct in tr:
            for c in siblings_of(ct, tr):
                if c.id < ct.id:      # count each pair once
                    continue
                entry_gaps.append(abs((c.entry_time - ct.entry_time).total_seconds()) / 60)
                exit_gaps.append(abs((c.exit_time - ct.exit_time).total_seconds()) / 60)
                p, q = parsed(ct), parsed(c)
                if p and q and p.instrument_type == q.instrument_type:
                    same_type += 1
                else:
                    diff_type += 1
    if entry_gaps:
        print(f"  candidate pairs: {len(entry_gaps)}")
        print(f"    entry gap  median {median(entry_gaps):5.1f} min")
        print(f"    EXIT  gap  median {median(exit_gaps):5.1f} min")
        far = sum(1 for g in exit_gaps if g > 30)
        print(f"    pairs closing MORE THAN 30 MIN apart : {far} of {len(exit_gaps)} "
              f"({far/len(exit_gaps):.0%})")
        print(f"    same option type (CE+CE / PE+PE) : {same_type}")
        print(f"    opposite type   (CE+PE)          : {diff_type}")
        print("\n  A CE+CE pair on one underlying is a spread OR two directional")
        print("  bets — the criteria cannot tell them apart.")

    print("\n" + "=" * 74)
    print("4. WHAT NETTING WOULD DO TO A LOSS FIGURE")
    print("=" * 74)
    flips = 0
    examples = []
    for _d, tr in sessions:
        for ct in tr:
            if float(ct.realized_pnl) >= 0:
                continue
            s = [c for c in siblings_of(ct, tr) if c.exit_time <= ct.exit_time]
            if not s:
                continue
            net = float(ct.realized_pnl) + sum(float(c.realized_pnl) for c in s)
            if net >= 0:
                flips += 1
                if len(examples) < 5:
                    examples.append((_d, ct, float(ct.realized_pnl), net, len(s)))
    print(f"  losing rounds whose NET (with closed siblings) is >= 0 : {flips}")
    print("  For those, a leg-level rule reports a loss and a net-level rule")
    print("  reports none. Both are defensible; they are not the same rule.\n")
    for d, ct, leg, net, n in examples:
        print(f"    {d}  {ct.tradingsymbol:<26} leg Rs {leg:>8,.0f} -> net Rs {net:>8,.0f}  ({n} sibling(s))")


main()
