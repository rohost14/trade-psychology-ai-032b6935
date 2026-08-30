"""
`session_trades` ordering — what is actually wrong, and how big is each fix?

THREE CANDIDATE VISIBILITY RULES for "which session trades may a detector see
when analysing trade X".

  A  CURRENT: everything today except X.
     `load_session_trades` filters on `exit_time >= session_start` with NO
     upper bound, and the engine passes `exclude_id=X`. On the LIVE postback
     path that is harmless - a trade that has not closed yet is not in
     CompletedTrade, so the DB bound is implicit. On the BULK-SYNC path
     (`run_behavior_engine_full_session`) every trade of the day already
     exists, so analysing trade 3 of 10 shows it trades 4-10. FUTURE TRADES.

  B  exit_time <= X.exit_time
     Everything that had CLOSED by the moment the engine fires. This is
     EXACTLY what the live path sees, so adopting it makes bulk == live and
     changes live behaviour not at all.

  C  entry_time <= X.entry_time
     Decision order: a trade is "prior" only if the trader had already
     committed to it. Stricter than B, and a genuine semantic change - it
     would alter the live path too.

WHAT TO MEASURE
  1. how much A over-reports against B  (the bulk-sync divergence)
  2. how much B over-reports against C  (the look-ahead Pattern 20 hit)
  3. which detectors already guard themselves, and which rely on the boundary
"""
import sys
from collections import Counter

sys.path.insert(0, "D:/trade-psychology-ai")
sys.path.insert(0, "D:/trade-psychology-ai/backend")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

src = open("D:/trade-psychology-ai/docs/patterns/_measurement/p20_avgdown.py",
           encoding="utf-8").read()
src = src.replace("AVG = engine._detect_options_premium_avg_down\n", "")
exec(src.rsplit("\nmain()", 1)[0])


def main():
    sessions = load_with_fills()
    trades = [t for _, ts in sessions for t in ts]
    print(f"BOOK: {len(sessions)} sessions, {len(trades)} rounds\n")

    print("=" * 74)
    print("1. RULE A vs RULE B — the bulk-sync divergence (FUTURE trades)")
    print("=" * 74)
    tot_a = tot_b = 0
    affected = 0
    worst = None
    for _day, tr in sessions:
        for i, ct in enumerate(tr):
            a = [t for t in tr if t.id != ct.id]                     # everything
            b = [t for t in a if t.exit_time <= ct.exit_time]        # closed by now
            tot_a += len(a); tot_b += len(b)
            extra = len(a) - len(b)
            if extra:
                affected += 1
                if worst is None or extra > worst[0]:
                    worst = (extra, ct.tradingsymbol, str(_day))
    print(f"  session_trades entries handed to detectors, rule A : {tot_a:,}")
    print(f"  ...that had actually closed yet,          rule B : {tot_b:,}")
    print(f"  FUTURE entries visible under A                   : {tot_a - tot_b:,} "
          f"({(tot_a-tot_b)/tot_a:.0%} of everything detectors see)")
    print(f"  trades affected                                  : {affected} of {len(trades)}")
    if worst:
        print(f"  worst single trade: {worst[0]} future trades visible "
              f"({worst[1]}, {worst[2]})")
    print("\n  NOTE: unreachable on the live postback path (those rows do not")
    print("  exist yet). Reachable on run_behavior_engine_full_session, the")
    print("  REST bulk-sync replay, where every row already exists.")

    print("\n" + "=" * 74)
    print("2. RULE B vs RULE C — overlapping positions (the Pattern 20 hit)")
    print("=" * 74)
    tot_c = 0
    affected_c = 0
    for _day, tr in sessions:
        for i, ct in enumerate(tr):
            b = [t for t in tr if t.id != ct.id and t.exit_time <= ct.exit_time]
            c = [t for t in b if t.entry_time and ct.entry_time
                 and t.entry_time <= ct.entry_time]
            tot_c += len(c)
            if len(b) != len(c):
                affected_c += 1
    print(f"  visible under B : {tot_b:,}")
    print(f"  visible under C : {tot_c:,}")
    print(f"  entries B shows that C would hide : {tot_b - tot_c:,} "
          f"({(tot_b-tot_c)/tot_b:.1%})")
    print(f"  trades affected : {affected_c} of {len(trades)}")
    print("\n  These are trades ENTERED after this one but CLOSED before it.")
    print("  They are real facts by the time the engine fires at this trade's")
    print("  EXIT - so hiding them is a semantic choice about what 'prior'")
    print("  means, not a correctness fix.")

    print("\n" + "=" * 74)
    print("3. WHICH DETECTORS GUARD THEMSELVES ALREADY")
    print("=" * 74)
    print("""  Reading the code, three already compare against ct.entry_time and are
  immune to both A and C:

    revenge_trade            t.exit_time < ct.entry_time
    constitution_violation   t.exit_time <= ct.entry_time   (cooldown rule)
    fomo_entry               window_start <= t.entry_time <= ct.entry_time

  Two bound entry_time below but NOT above, so a future entry counts:

    overtrading_burst        t.entry_time >= cutoff
    end_of_session_mis_panic t.entry_time >= panic_start

  The rest take session_trades wholesale and depend entirely on the
  boundary being right:

    overtrading_burst (daily count), rapid_reentry, martingale_behaviour,
    _typical_loss, premium_loss_event, post_loss_recovery_bet,
    constitution_violation (trade count), same_symbol_obsession,
    win_rate_collapse, strategy_breakdown""")

    print("\n" + "=" * 74)
    print("4. FIRING IMPACT of adopting rule B, per detector")
    print("=" * 74)
    dets = [n for n in dir(engine) if n.startswith("_detect_")]
    before = Counter(); after = Counter()
    for _day, tr in sessions:
        for i, ct in enumerate(tr):
            all_others = [t for t in tr if t.id != ct.id]
            closed_only = [t for t in all_others if t.exit_time <= ct.exit_time]
            for label, pool in (("before", all_others), ("after", closed_only)):
                c = ctx_fills(ct, pool)
                for d in dets:
                    try:
                        if fired(getattr(engine, d)(c)):
                            (before if label == "before" else after)[d] += 1
                    except Exception:
                        pass
    keys = sorted(set(before) | set(after))
    print(f"  {'detector':<38} {'A (now)':>9} {'B (fix)':>9} {'delta':>7}")
    for k in keys:
        b_, a_ = before[k], after[k]
        if b_ or a_:
            flag = "  <-- CHANGES" if b_ != a_ else ""
            print(f"  {k.replace('_detect_',''):<38} {b_:>9} {a_:>9} "
                  f"{a_-b_:>+7}{flag}")


main()
