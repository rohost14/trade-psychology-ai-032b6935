"""
Pattern 23 — `post_loss_recovery_bet`, measured.

THE CLAIM, as shown to the trader:

  "After 2 NIFTY losses (Rs 6,400 total), your NIFTY25SEP24000CE size is
   3.2x your recent NIFTY average."

and the registry copy: "A position materially larger than your average, entered
after a loss on the same underlying. If this one also loses, the combined loss
exceeds everything it was meant to recover."

Its docstring asserts a distinction that decides the review:

  "Different from martingale (progressive escalation) - this is a single
   outsized bet."

WHAT TO MEASURE

  1. does it fire, at what severity, and does it withhold
  2. THE DISTINCTION. `martingale_behaviour` also fires on size raised after a
     run of losses. If every recovery-bet firing is also a martingale firing,
     the claimed difference does not exist in the data whatever the code says.
  3. the shuffle null. Its claim is ORDERING - losses THEN an oversized bet.
     Standing first test for any such claim.
  4. does the SIZE gate do work, or would "2 losses then any trade" fire the
     same? The 2.0x/3.0x multipliers have no THRESHOLD_SPECS record and no
     stated provenance beyond a comment.
  5. `size_escalation` was retired 2026-08-27 with the note that
     "`martingale_behaviour` + `post_loss_recovery_bet` keep the claim".
     Verify this detector actually carries its half.
  6. is it selected on OUTCOME? It fires regardless of the current trade's
     result, unlike the last three retirements - check that holds.
  7. consequence: ranks, cannot judge.
"""
import random
import sys
from collections import Counter
from statistics import mean, median

sys.path.insert(0, "D:/trade-psychology-ai")
sys.path.insert(0, "D:/trade-psychology-ai/backend")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

src = open("D:/trade-psychology-ai/docs/patterns/_measurement/p20_avgdown.py",
           encoding="utf-8").read()
src = src.replace("AVG = engine._detect_options_premium_avg_down\n", "")
exec(src.rsplit("\nmain()", 1)[0])

from app.core.trading_defaults import COLD_START_DEFAULTS      # noqa: E402
from app.services.instrument_parser import parse_symbol as _ps  # noqa: E402

random.seed(20260901)
RB = engine._detect_post_loss_recovery_bet
MG = engine._detect_martingale_behaviour
CAUT = COLD_START_DEFAULTS["recovery_bet_caution_mul"]
DANG = COLD_START_DEFAULTS["recovery_bet_danger_mul"]


def und(t):
    try:
        return _ps(t.tradingsymbol or "").underlying or t.tradingsymbol or ""
    except Exception:
        return t.tradingsymbol or ""


def pool_for(ct, tr):
    return [t for t in tr if t.id != ct.id and t.exit_time <= ct.exit_time]


def main():
    sessions = load_with_fills()
    trades = [t for _, ts in sessions for t in ts]
    print(f"BOOK: {len(sessions)} sessions, {len(trades)} rounds")
    print(f"THRESHOLDS: caution {CAUT}x  danger {DANG}x  (neither has a spec)\n")

    fires, mg_fires, both = [], [], []
    for d, tr in sessions:
        for ct in tr:
            c = ctx_fills(ct, pool_for(ct, tr))
            r, m = RB(c), MG(c)
            if fired(r):
                fires.append((d, ct, c, r))
            if fired(m):
                mg_fires.append((d, ct))
            if fired(r) and fired(m):
                both.append((d, ct))
    assert fires, "harness inert"

    # ------------------------------------------------------------------ 1
    print("=" * 74)
    print("1. FIRING AND WITHHOLDING")
    print("=" * 74)
    sev = Counter(getattr(getattr(r, "event", None) or r, "severity", None)
                  for _d, _c, _x, r in fires)
    print(f"  {len(fires)} events / {len({d for d,_,_,_ in fires})} sessions of {len(sessions)}")
    print(f"  by severity: {dict(sev)}")

    # how many trades reach each gate
    g_len = g_two = g_loss = 0
    ratios = []
    for d, tr in sessions:
        for ct in tr:
            c = ctx_fills(ct, pool_for(ct, tr))
            if len(c.session_trades) < 3:
                continue
            g_len += 1
            u = und(ct)
            prior = [t for t in c.concluded_before_entry if und(t) == u]
            if len(prior) < 2:
                continue
            g_two += 1
            if not all(float(t.realized_pnl or 0) < 0 for t in prior[-2:]):
                continue
            g_loss += 1
            qs = [t.total_quantity or 1 for t in prior[-3:]]
            avg = sum(qs) / len(qs)
            if avg >= 1:
                ratios.append((ct.total_quantity or 1) / avg)
    print(f"\n  gate funnel:")
    print(f"    >= 3 session trades                      : {g_len}")
    print(f"    >= 2 CONCLUDED priors on same underlying : {g_two}")
    print(f"    ...last two both losses                  : {g_loss}")
    print(f"    ...and size >= {CAUT}x                        : {len(fires)}")
    if g_loss:
        print(f"  -> the SIZE gate withholds on {g_loss - len(fires)} of {g_loss} "
              f"({1 - len(fires)/g_loss:.0%})")

    # ------------------------------------------------------------------ 4
    print("\n" + "=" * 74)
    print("4. DOES THE SIZE GATE DO WORK, OR IS IT THE LOSS RUN DOING IT ALL?")
    print("=" * 74)
    if ratios:
        rs = sorted(ratios)
        def q(p): return rs[min(int(len(rs) * p), len(rs) - 1)]
        print(f"  size ratio after 2 same-underlying losses, n={len(rs)}")
        print(f"    p10 {q(.10):.2f}  p25 {q(.25):.2f}  median {median(rs):.2f}  "
              f"p75 {q(.75):.2f}  p90 {q(.90):.2f}  max {max(rs):.2f}")
        for m in (1.0, 1.5, 2.0, 3.0):
            n = sum(1 for r in rs if r >= m)
            print(f"    >= {m}x : {n:>3} / {len(rs)}  ({n/len(rs):.0%})")
        print(f"  -> if most post-loss trades were already >= {CAUT}x the gate")
        print(f"     would be decoration; it is not.")

    # ------------------------------------------------------------------ 2
    print("\n" + "=" * 74)
    print("2. THE DISTINCTION FROM martingale_behaviour")
    print("=" * 74)
    print(f"  martingale_behaviour firings : {len(mg_fires)}")
    print(f"  post_loss_recovery_bet       : {len(fires)}")
    print(f"  BOTH on the same trade       : {len(both)}  "
          f"({len(both)/len(fires):.0%} of recovery-bet firings)")
    ids = {id(ct) for _d, ct in both}
    alone = [(d, ct) for d, ct, _c, _r in fires if id(ct) not in ids]
    print(f"  recovery_bet ALONE           : {len(alone)}")
    for d, ct in alone:
        print(f"      {d}  {ct.tradingsymbol}")

    # ------------------------------------------------------------------ 5
    print("\n" + "=" * 74)
    print("5. OVERLAP WITH EVERYTHING ELSE")
    print("=" * 74)
    others = ("_detect_revenge_trade", "_detect_same_symbol_obsession",
              "_detect_adding_to_adverse_position", "_detect_rapid_reentry",
              "_detect_overtrading_burst", "_detect_no_stoploss",
              "_detect_premium_loss_event", "_detect_fomo_entry",
              "_detect_session_meltdown")
    co = Counter(); solo = 0
    for _d, ct, c, _r in fires:
        hit = []
        for m in others:
            fn = getattr(engine, m, None)
            if fn:
                try:
                    if fired(fn(c)):
                        hit.append(m.replace("_detect_", ""))
                except Exception:
                    pass
        for h in hit:
            co[h] += 1
        if not hit:
            solo += 1
    for k, v in co.most_common():
        print(f"    {k:<32} {v:>3} / {len(fires)}")
    print(f"  fired with NOTHING else (martingale excluded): {solo} of {len(fires)}")

    # ------------------------------------------------------------------ 3
    print("\n" + "=" * 74)
    print("3. THE SHUFFLE NULL — permute exit order, run the REAL detector")
    print("=" * 74)
    real = len(fires)
    counts = []
    for _ in range(2000):
        n = 0
        for _d, tr in sessions:
            sh = list(tr)
            random.shuffle(sh)
            for i, ct in enumerate(sh):
                if fired(RB(ctx_fills(ct, sh[:i]))):
                    n += 1
        counts.append(n)
    ge = sum(1 for c in counts if c >= real)
    print(f"  real trade order      : {real} firings")
    print(f"  shuffled order (2000) : mean {mean(counts):.1f}  median {median(counts):.0f}  "
          f"min {min(counts)}  max {max(counts)}")
    print(f"  p(shuffled >= real)   : {ge/len(counts):.3f}")

    # ------------------------------------------------------------------ 6
    print("\n" + "=" * 74)
    print("6. IS IT SELECTED ON OUTCOME?")
    print("=" * 74)
    fl = [float(ct.realized_pnl) for _d, ct, _c, _r in fires]
    wins = sum(1 for x in fl if x > 0)
    print(f"  flagged trades that WON : {wins} of {len(fl)}")
    print("  (a detector that only fires on losers cannot separate the")
    print("   behaviour from the result - the panic_exit / opening_trap shape)")

    # ------------------------------------------------------------------ 7
    print("\n" + "=" * 74)
    print("7. CONSEQUENCE — ranks, cannot judge")
    print("=" * 74)
    ids2 = {id(ct) for _d, ct, _c, _r in fires}
    ctrl = [float(t.realized_pnl) for t in trades if id(t) not in ids2]
    print(f"  flagged   n={len(fl):<4} mean Rs {mean(fl):>9,.0f}  "
          f"median Rs {median(fl):>8,.0f}  win {wins/len(fl):.1%}")
    print(f"  all other n={len(ctrl):<4} mean Rs {mean(ctrl):>9,.0f}  "
          f"median Rs {median(ctrl):>8,.0f}  "
          f"win {sum(1 for x in ctrl if x>0)/len(ctrl):.1%}")

    print("\n" + "=" * 74)
    print("8. THE FIRINGS")
    print("=" * 74)
    for d, ct, c, r in fires:
        ev = getattr(r, "event", None) or r
        x = ev.context
        print(f"  {d}  {ev.severity:<7} ratio={x['size_ratio']}x  "
              f"qty {x['avg_recent_qty']}->{x['current_qty']}  "
              f"prior loss Rs {x['prior_total_loss']:,.0f}  pnl Rs {float(ct.realized_pnl):,.0f}")
        print(f"      {ev.message[:112]}")


main()
