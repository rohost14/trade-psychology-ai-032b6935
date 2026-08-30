"""
p20 addendum — the three questions that decide the consolidation.

1. Does `adding_to_adverse_position` ALREADY cover option premium averaging?
   If its firings are mostly long options, the option-specific detector adds
   nothing on that subject and there is nothing to fold in.

2. What are the 7 firings `options_premium_avg_down` produces ALONE? Those are
   what would actually be lost.

3. On the 8 trades where both fire, are they describing the same fact or two
   different facts about one trade?
"""
import sys
from collections import Counter

sys.path.insert(0, "D:/trade-psychology-ai")
sys.path.insert(0, "D:/trade-psychology-ai/backend")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

src = open("D:/trade-psychology-ai/docs/patterns/_measurement/p20_avgdown.py",
           encoding="utf-8").read()
exec(src.rsplit("\nmain()", 1)[0])


def main():
    sessions = load_with_fills()

    avg_f, aap_f, both = [], [], []
    for day, tr in sessions:
        for i, ct in enumerate(tr):
            c = ctx_fills(ct, tr[:i])
            a, b = AVG(c), AAP(c)
            if fired(a):
                avg_f.append((day, ct, tr[:i], a))
            if fired(b):
                aap_f.append((day, ct, tr[:i], b))
            if fired(a) and fired(b):
                both.append((day, ct, tr[:i], a, b))

    # ------------------------------------------------------------------ 1
    print("=" * 74)
    print("1. WHAT adding_to_adverse_position ALREADY COVERS")
    print("=" * 74)
    kinds = Counter(ct.instrument_type for _d, ct, _p, _e in aap_f)
    dirs = Counter(ct.direction for _d, ct, _p, _e in aap_f)
    print(f"  {len(aap_f)} firings by instrument type: {dict(kinds)}")
    print(f"  by direction: {dict(dirs)}")
    longopt = sum(1 for _d, ct, _p, _e in aap_f
                  if ct.instrument_type in ("CE", "PE") and ct.direction == "LONG")
    print(f"\n  LONG option firings: {longopt} of {len(aap_f)} "
          f"({longopt/len(aap_f):.0%})")
    print("  -> these ARE option premium averaging: quantity added to an open")
    print("     long option that had already lost premium. Same subject the")
    print("     registry copy of the other detector promises.")

    print("\n  a sample, to show the copy already fits:")
    shown = 0
    for _d, ct, _p, ev in aap_f:
        if ct.instrument_type in ("CE", "PE") and ct.direction == "LONG":
            msg = getattr(ev, "message", None) or getattr(
                getattr(ev, "event", None), "message", "")
            print(f"    {ct.tradingsymbol:<26} {str(msg)[:88]}")
            shown += 1
            if shown >= 5:
                break

    # ------------------------------------------------------------------ 2
    print("\n" + "=" * 74)
    print("2. THE FIRINGS options_premium_avg_down PRODUCES ALONE")
    print("=" * 74)
    others = ("_detect_same_symbol_obsession", "_detect_revenge_trade",
              "_detect_rapid_reentry", "_detect_premium_loss_event",
              "_detect_martingale_behaviour", "_detect_post_loss_recovery_bet",
              "_detect_fomo_entry", "_detect_overtrading_burst",
              "_detect_adding_to_adverse_position")
    alone = []
    for _d, ct, prior, ev in avg_f:
        c = ctx_fills(ct, prior)
        hit = False
        for m in others:
            fn = getattr(engine, m, None)
            if fn:
                try:
                    if fired(fn(c)):
                        hit = True
                        break
                except Exception:
                    pass
        if not hit:
            alone.append((_d, ct, prior, ev))

    print(f"  {len(alone)} of {len(avg_f)} fire with nothing else\n")
    for _d, ct, prior, ev in alone:
        u = und(ct)
        losers = [p for p in prior
                  if p.instrument_type in ("CE", "PE") and p.direction == "LONG"
                  and float(p.realized_pnl) < 0 and und(p) == u]
        same = [p for p in losers if p.tradingsymbol == ct.tradingsymbol]
        opp = [p for p in losers if p.instrument_type != ct.instrument_type]
        kind = ("SAME CONTRACT re-entry" if same else
                "OPPOSITE TYPE (direction change)" if opp and len(opp) == len(losers)
                else "different strike, same type")
        gap = None
        if losers:
            last = max(losers, key=lambda p: p.exit_time)
            gap = (ct.entry_time - last.exit_time).total_seconds() / 60
        print(f"    {_d}  {ct.tradingsymbol:<26} {kind}")
        print(f"        priors={len(losers)}  gap={gap:.0f}min  "
              f"pnl=Rs {float(ct.realized_pnl):>8,.0f}")

    # ------------------------------------------------------------------ 3
    print("\n" + "=" * 74)
    print("3. THE 8 CO-FIRINGS - same fact, or two facts?")
    print("=" * 74)
    for _d, ct, prior, a, b in both:
        msg_b = getattr(b, "message", None) or getattr(
            getattr(b, "event", None), "message", "")
        print(f"  {_d}  {ct.tradingsymbol}")
        print(f"    avg_down : {a.message[:96]}")
        print(f"    aap      : {str(msg_b)[:96]}")
    print("\n  aap describes the fill sequence INSIDE this position.")
    print("  avg_down describes OTHER positions closed earlier today.")
    print("  Two different facts about one trade, not one fact twice.")


main()
