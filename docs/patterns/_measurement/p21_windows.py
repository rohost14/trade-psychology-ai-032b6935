"""
Pattern 21 — `opening_5min_trap` and `end_of_session_mis_panic`, measured.

Reviewed together because they share session-boundary mechanics: both compare a
trade's ENTRY against an exchange session edge. They are NOT assumed to be the
same behaviour and each gets its own numbers.

THE DECIDING TEST for `opening_5min_trap` is the one that retired `panic_exit`:
it fires only on LOSING trades. If opening-window entries win at about the same
rate as the rest of the day, it is selecting on OUTCOME, not on behaviour -
labelling the losing half of an ordinary habit.

OBSERVABILITY LIMITS, stated before any number below:

  1. THE TRADEBOOK HAS NO PRODUCT COLUMN. Header is
     symbol,isin,trade_date,exchange,segment,series,trade_type,auction,
     quantity,price,trade_id,order_id,order_execution_time,expiry_date
     `end_of_session_mis_panic` gates on `product in ("MIS","INTRADAY")`, so
     its true firing rate is UNKNOWABLE here. Everything reported for it is an
     UPPER BOUND under an all-MIS assumption, and is labelled as such.

  2. The export's `exchange` is the UNDERLYING's (NSE/BSE), not the
     derivatives segment. Every row is segment=FO, so the engine would see
     NFO/BFO. There is no MCX or CDS in this book, so the commodity branches of
     `end_of_session_mis_panic` and the hardcoded 09:15 in `opening_5min_trap`
     are BOTH unexercised. A defect there would be latent, not observed.
"""
import sys
from collections import Counter, defaultdict
from datetime import timedelta
from statistics import mean, median
from zoneinfo import ZoneInfo

sys.path.insert(0, "D:/trade-psychology-ai")
sys.path.insert(0, "D:/trade-psychology-ai/backend")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

src = open("D:/trade-psychology-ai/docs/patterns/_measurement/p20_avgdown.py",
           encoding="utf-8").read()
src = src.replace("AVG = engine._detect_options_premium_avg_down\n", "")
exec(src.rsplit("\nmain()", 1)[0])

from app.core.trading_defaults import COLD_START_DEFAULTS    # noqa: E402

IST_TZ = ZoneInfo("Asia/Kolkata")
TRAP = engine._detect_opening_5min_trap
MIS = engine._detect_end_of_session_mis_panic

W_END = COLD_START_DEFAULTS["opening_trap_window_end_min"]
QUICK = COLD_START_DEFAULTS["opening_trap_quick_exit_min"]
BIGLOSS = COLD_START_DEFAULTS["opening_trap_large_loss_pct"]
MIS_C = COLD_START_DEFAULTS["end_session_mis_caution_count"]
MIS_D = COLD_START_DEFAULTS["end_session_mis_danger_count"]


def ist(t):
    return t.entry_time.astimezone(IST_TZ)


def in_window(t):
    e = ist(t)
    open_ = e.replace(hour=9, minute=15, second=0, microsecond=0)
    return open_ <= e <= open_ + timedelta(minutes=W_END)


def loss_pct(t):
    p = float(t.realized_pnl or 0)
    prem = float(t.avg_entry_price or 0) * (t.total_quantity or 1)
    return abs(p) / prem * 100 if prem > 0 and p < 0 else 0.0


def won(t):
    return float(t.realized_pnl or 0) > 0


def main():
    sessions = load_with_fills()
    trades = [t for _, ts in sessions for t in ts]
    print(f"BOOK: {len(sessions)} sessions, {len(trades)} rounds")
    print(f"opening_trap: window {W_END}min  quick_exit {QUICK}min  "
          f"large_loss {BIGLOSS}%")
    print(f"end_session_mis: caution {MIS_C}  danger {MIS_D}\n")

    # ═══════════════════════════ opening_5min_trap ═══════════════════════
    print("=" * 74)
    print("A1. THE DECIDING TEST — is the opening window selected on OUTCOME?")
    print("=" * 74)
    inw = [t for t in trades if in_window(t)]
    out = [t for t in trades if not in_window(t)]
    print(f"  entries inside 09:15-09:{15+W_END} : {len(inw)} of {len(trades)} "
          f"({len(inw)/len(trades):.1%})")
    for label, grp in (("inside window", inw), ("rest of day", out)):
        if grp:
            wr = sum(1 for t in grp if won(t)) / len(grp)
            print(f"    {label:<14} n={len(grp):<4} win {wr:.1%}  "
                  f"mean Rs {mean(float(t.realized_pnl) for t in grp):>8,.0f}  "
                  f"median Rs {median(float(t.realized_pnl) for t in grp):>7,.0f}")
    print("\n  If the two win rates are close, the window is not a worse place to")
    print("  trade and the detector is flagging the losing half of a habit.")

    print("\n" + "=" * 74)
    print("A2. WHAT THE DETECTOR ACTUALLY DOES")
    print("=" * 74)
    fires = []
    for _d, tr in sessions:
        for i, ct in enumerate(tr):
            pool = [t for t in tr if t.id != ct.id and t.exit_time <= ct.exit_time]
            ev = TRAP(ctx_fills(ct, pool))
            if ev:
                fires.append((_d, ct, ev))
    losers_inw = [t for t in inw if float(t.realized_pnl or 0) < 0]
    print(f"  firings                       : {len(fires)} / "
          f"{len({d for d,_,_ in fires})} sessions")
    print(f"  window entries                : {len(inw)}")
    print(f"  ...that LOST (its only pool)  : {len(losers_inw)}")
    if losers_inw:
        print(f"  -> the outcome gate alone discards "
              f"{len(inw)-len(losers_inw)} of {len(inw)} window entries "
              f"({1-len(losers_inw)/len(inw):.0%}) BEFORE any behaviour is looked at")
        q = [t for t in losers_inw if (t.duration_minutes or 0) <= QUICK]
        b = [t for t in losers_inw if loss_pct(t) >= BIGLOSS]
        both = [t for t in losers_inw if (t.duration_minutes or 0) <= QUICK
                and loss_pct(t) >= BIGLOSS]
        neither = [t for t in losers_inw if (t.duration_minutes or 0) > QUICK
                   and loss_pct(t) < BIGLOSS]
        print(f"  of the {len(losers_inw)} losers:")
        print(f"     quick exit (<= {QUICK}min)  : {len(q)}")
        print(f"     large loss (>= {BIGLOSS}%)   : {len(b)}")
        print(f"     both                     : {len(both)}")
        print(f"     NEITHER — withheld       : {len(neither)}")

    print("\n" + "=" * 74)
    print("A3. THE THREE WINDOWS — name, threshold, and copy disagree")
    print("=" * 74)
    for w in (5, 10, 15):
        n = sum(1 for t in trades
                if ist(t).replace(hour=9, minute=15, second=0, microsecond=0)
                <= ist(t) <=
                ist(t).replace(hour=9, minute=15, second=0, microsecond=0) + timedelta(minutes=w))
        print(f"    entries within {w:>2} min of 09:15 : {n}")
    print(f"  the detector is NAMED 5min, its threshold is {W_END}, and its")
    print(f"  message quotes '09:15-09:25' — which is the {W_END}-minute one.")

    print("\n" + "=" * 74)
    print("A4. OVERLAP")
    print("=" * 74)
    others = ("_detect_revenge_trade", "_detect_no_stoploss",
              "_detect_premium_loss_event", "_detect_fomo_entry",
              "_detect_same_symbol_obsession", "_detect_martingale_behaviour",
              "_detect_overtrading_burst", "_detect_adding_to_adverse_position")
    co = Counter(); alone = 0
    for _d, ct, _ev in fires:
        pool = [t for t in next(x for dd, x in sessions if dd == _d)
                if t.id != ct.id and t.exit_time <= ct.exit_time]
        c = ctx_fills(ct, pool)
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
            alone += 1
    for k, v in co.most_common():
        print(f"    {k:<32} {v:>3} / {len(fires)}")
    print(f"  fired ALONE on {alone} of {len(fires)}")

    # ═══════════════════════ end_of_session_mis_panic ════════════════════
    print("\n" + "=" * 74)
    print("B1. END-OF-SESSION — UPPER BOUND ONLY (no product column)")
    print("=" * 74)
    late = [t for t in trades if ist(t).hour >= 15]
    print(f"  entries at or after 15:00 IST : {len(late)} of {len(trades)} "
          f"({len(late)/len(trades):.1%})")
    per_session = Counter()
    for d, tr in sessions:
        per_session[d] = sum(1 for t in tr if ist(t).hour >= 15)
    dist = Counter(per_session.values())
    print("  late entries per session:")
    for k in sorted(dist):
        print(f"     {k:>2} late entries : {dist[k]:>3} sessions")
    ge2 = sum(v for k, v in dist.items() if k >= MIS_C)
    ge3 = sum(v for k, v in dist.items() if k >= MIS_D)
    print(f"  sessions reaching caution ({MIS_C}) : {ge2} of {len(sessions)}")
    print(f"  sessions reaching danger  ({MIS_D}) : {ge3} of {len(sessions)}")

    mis_fires = []
    for _d, tr in sessions:
        for i, ct in enumerate(tr):
            pool = [t for t in tr if t.id != ct.id and t.exit_time <= ct.exit_time]
            ev = MIS(ctx_fills(ct, pool))
            if ev:
                mis_fires.append((_d, ct, ev))
    sev = Counter(e.severity for _d, _c, e in mis_fires)
    print(f"\n  firings under the all-MIS assumption : {len(mis_fires)} "
          f"/ {len({d for d,_,_ in mis_fires})} sessions")
    print(f"  by severity: {dict(sev)}")
    print("  THIS IS AN UPPER BOUND. Any NRML/CNC position in the real book")
    print("  would be excluded by the product gate and is invisible here.")

    print("\n" + "=" * 74)
    print("B2. DOES THE 'DELIBERATE LATE SCALPING' GUARD EVER BIND?")
    print("=" * 74)
    bind = 0
    for d, tr in sessions:
        lates = [t for t in tr if ist(t).hour >= 15]
        if len(lates) >= MIS_C and all(float(t.realized_pnl or 0) > 0 for t in lates):
            bind += 1
    print(f"  sessions with >= {MIS_C} late entries, ALL profitable : {bind}")
    print("  (the guard downgrades danger to info and suppresses caution)")

    print("\n" + "=" * 74)
    print("B3. CONSEQUENCE — late entries vs the rest")
    print("=" * 74)
    for label, grp in (("late (>=15:00)", late),
                       ("rest of day", [t for t in trades if ist(t).hour < 15])):
        if grp:
            wr = sum(1 for t in grp if won(t)) / len(grp)
            print(f"    {label:<16} n={len(grp):<4} win {wr:.1%}  "
                  f"mean Rs {mean(float(t.realized_pnl) for t in grp):>8,.0f}  "
                  f"median Rs {median(float(t.realized_pnl) for t in grp):>7,.0f}")

    print("\n" + "=" * 74)
    print("B4. HOW LONG ARE LATE MIS POSITIONS ACTUALLY HELD?")
    print("=" * 74)
    print("  The claim is 'very little time for the position to work, and the")
    print("  exit is not yours to choose'. If they are squared off by the")
    print("  broker, holds should bunch against the 15:25 boundary.")
    held = [(ist(t), t.duration_minutes or 0) for t in late]
    if held:
        print(f"    n={len(held)}  median hold {median(h for _e,h in held):.0f}min  "
              f"mean {mean(h for _e,h in held):.0f}min")
        forced = sum(1 for e, h in held
                     if (e + timedelta(minutes=h)).hour * 60
                        + (e + timedelta(minutes=h)).minute >= 15 * 60 + 20)
        print(f"    exited at/after 15:20 (near squareoff) : {forced} of {len(held)}")


main()
