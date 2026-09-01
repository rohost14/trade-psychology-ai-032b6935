"""
Reviews 25-27 — time_of_day_bias, win_rate_collapse, strategy_breakdown.

All three have never fired. The brief's instruction is not to stop at "0
firings" but to ask WHERE the conditions die: correctly selective, unreachable,
mis-wired, starved of data, or simply absent from this book.

Each is gated on BASELINE inputs, so each is measured twice:

  1. as the engine sees it today - cold-start thresholds, no baseline
  2. with the baseline SUPPLIED from this book's own history, which is what the
     detector would see for a mature trader

The second is the real test. If a detector still fires 0 with its baseline
handed to it, the silence is about the book. If it fires, the silence is about
the plumbing.

Filters replicated exactly from the producers:
  danger_hours   win_rate < 35 AND trades >= 5   (ai_personalization_service)
  wr collapse    (base - today) / base >= 0.40
  pf collapse    today_pf <= base_pf * 0.50
  both need      >= 8 trades today, baseline confidence >= 0.5
"""
import sys
from collections import Counter, defaultdict
from statistics import mean

sys.path.insert(0, "D:/trade-psychology-ai")
sys.path.insert(0, "D:/trade-psychology-ai/backend")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

src = open("D:/trade-psychology-ai/docs/patterns/_measurement/p20_avgdown.py",
           encoding="utf-8").read()
src = src.replace("AVG = engine._detect_options_premium_avg_down\n", "")
exec(src.rsplit("\nmain()", 1)[0])

from app.core.trading_defaults import COLD_START_DEFAULTS   # noqa: E402
from zoneinfo import ZoneInfo                                # noqa: E402

IST_TZ = ZoneInfo("Asia/Kolkata")
TOD = engine._detect_time_of_day_bias
WRC = engine._detect_win_rate_collapse
SBD = engine._detect_strategy_breakdown


def pf(pnls):
    gw = sum(p for p in pnls if p > 0)
    gl = abs(sum(p for p in pnls if p < 0))
    return gw / gl if gl > 0 else None


def main():
    sessions = load_with_fills()
    trades = [t for _, ts in sessions for t in ts]
    print(f"BOOK: {len(sessions)} sessions, {len(trades)} rounds\n")

    # ── the book's own baseline ────────────────────────────────────────────
    wins = sum(1 for t in trades if float(t.realized_pnl) > 0)
    book_wr = wins / len(trades) * 100
    book_pf = pf([float(t.realized_pnl) for t in trades])
    print("=" * 76)
    print("THE BOOK'S OWN BASELINE (what a mature trader's would look like)")
    print("=" * 76)
    print(f"  win rate      {book_wr:.1f}%")
    print(f"  profit factor {book_pf:.2f}")
    print(f"  sessions      {len(sessions)}  (tod_bias needs >= 30)")

    # ══════════════════════════ 25. time_of_day_bias ═══════════════════════
    print("\n" + "=" * 76)
    print("25. time_of_day_bias")
    print("=" * 76)
    hourly = defaultdict(lambda: {"w": 0, "l": 0, "n": 0, "pnl": 0.0})
    for t in trades:
        h = t.entry_time.astimezone(IST_TZ).hour
        s = hourly[h]
        s["n"] += 1
        s["pnl"] += float(t.realized_pnl)
        if float(t.realized_pnl) > 0:
            s["w"] += 1
        elif float(t.realized_pnl) < 0:
            s["l"] += 1
    print(f"  {'hour':>5} {'trades':>7} {'win %':>7} {'avg P&L':>10}   danger?")
    danger = []
    for h in sorted(hourly):
        s = hourly[h]
        tot = s["w"] + s["l"]
        wr = (s["w"] / tot * 100) if tot else 50
        is_d = wr < 35 and s["n"] >= 5
        if is_d:
            danger.append({"hour": h, "win_rate": round(wr, 1),
                           "trades": s["n"], "avg_pnl": round(s["pnl"] / s["n"], 2)})
        print(f"  {h:>5} {s['n']:>7} {wr:>6.1f}% {s['pnl']/s['n']:>10,.0f}   "
              f"{'YES' if is_d else ''}")
    print(f"\n  danger hours the producer WOULD learn: {len(danger)}")
    for d in danger:
        print(f"      {d['hour']}:00  win {d['win_rate']}%  n={d['trades']}  avg Rs {d['avg_pnl']:,.0f}")

    for label, th_extra in (
        ("as the engine sees it today (no baseline)", {}),
        ("with the learned danger_hours SUPPLIED",
         {"danger_hours": danger, "baseline_sessions": len(sessions)}),
    ):
        n = 0
        for _d, tr in sessions:
            for ct in tr:
                c = ctx_fills(ct, [])
                t = dict(COLD_START_DEFAULTS); t.update(th_extra); c.thresholds = t
                if TOD(c):
                    n += 1
        print(f"  firings — {label:<44}: {n}")

    # ══════════════════════ 26/27. the two baseline detectors ══════════════
    print("\n" + "=" * 76)
    print("26/27. win_rate_collapse and strategy_breakdown")
    print("=" * 76)
    big = [(d, tr) for d, tr in sessions if len(tr) >= 8]
    print(f"  sessions with >= 8 trades (the shared gate): {len(big)} of {len(sessions)}")

    wr_hits = pf_hits = both = 0
    rows = []
    for d, tr in big:
        pnls = [float(t.realized_pnl) for t in tr]
        w = sum(1 for p in pnls if p > 0)
        wr = w / len(tr) * 100
        p_f = pf(pnls)
        det = (book_wr - wr) / book_wr
        wr_c = det >= 0.40
        pf_c = p_f is not None and p_f <= book_pf * 0.50
        if wr_c:
            wr_hits += 1
        if pf_c:
            pf_hits += 1
        if wr_c and pf_c:
            both += 1
            rows.append((d, len(tr), wr, p_f, det))
    print(f"  ...of those, win-rate deterioration >= 40%   : {wr_hits}")
    print(f"  ...of those, profit factor <= 50% of baseline: {pf_hits}")
    print(f"  ...BOTH (strategy_breakdown's condition)     : {both}")

    base_wr = {"value": book_wr, "confidence": 1.0}
    base_pf = {"value": book_pf, "confidence": 1.0}
    for label, extra in (
        ("as the engine sees it today (no baseline)", {}),
        ("with the book's own baseline SUPPLIED",
         {"baseline_win_rate": base_wr, "baseline_profit_factor": base_pf}),
    ):
        nw = ns = 0
        for _d, tr in sessions:
            for i, ct in enumerate(tr):
                c = ctx_fills(ct, tr[:i])
                t = dict(COLD_START_DEFAULTS); t.update(extra); c.thresholds = t
                if WRC(c):
                    nw += 1
                if SBD(c):
                    ns += 1
        print(f"  {label}")
        print(f"      win_rate_collapse   : {nw}")
        print(f"      strategy_breakdown  : {ns}")

    if rows:
        print("\n  sessions meeting strategy_breakdown's full condition:")
        for d, n, wr, p_f, det in rows[:10]:
            print(f"      {d}  n={n:<3} win {wr:>5.1f}%  PF {p_f:>5.2f}  deterioration {det:.0%}")

    # ── the trigger="session" question ────────────────────────────────────
    print("\n" + "=" * 76)
    print("THE trigger=\"session\" DECLARATION")
    print("=" * 76)
    from app.services.detector_registry import BY_NAME
    for n in ("time_of_day_bias", "win_rate_collapse", "strategy_breakdown"):
        s = BY_NAME[n]
        print(f"  {n:<22} trigger={s.trigger:<8} disposition={s.disposition:<10} "
              f"notif={s.notification_level}")
    print("  The engine branches on trigger == 'entry' only; everything else,")
    print("  'session' included, falls through to the per-trade exit loop.")


main()
