"""
Pattern #4 — is there a defensible severity signal at all?

Three candidates: absolute loss, loss against the declared daily limit, loss
against capital.

The bar is NOT "does it rank". Everything ranks. The bar is whether a candidate
separates genuinely different BEHAVIOUR - which for a streak means what the
trader does next, since that is observable and is not an outcome we would be
judging the product by.
"""
import json
import sys
from collections import Counter, defaultdict
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

sys.path.insert(0, "D:/trade-psychology-ai")
sys.path.insert(0, "D:/trade-psychology-ai/backend")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from tradedesk.scripts.replay_tradebook import read_fills, carry_fills  # noqa: E402
from app.core.instrument_risk import risk_basis  # noqa: E402
from app.services.behavior_engine import BehaviorEngine, EngineContext  # noqa: E402
from app.services.instrument_parser import parse_symbol  # noqa: E402

engine = BehaviorEngine()
CAPITAL = 50000.0


def meta(sym):
    try:
        p = parse_symbol(sym or "")
        return (p.instrument_type or "EQ"), (p.underlying or sym or "")
    except Exception:
        return "EQ", sym or ""


def build(day_fills, carry):
    st = defaultdict(lambda: {"qty": 0, "avg": 0.0, "opened": None, "pnl": 0.0})
    out = []
    for f in list(carry) + list(day_fills):
        sym = f["symbol"]
        p = st[sym]
        s = f["qty"] if f["side"] == "BUY" else -f["qty"]
        px = float(f["price"])
        if p["qty"] == 0:
            p.update(qty=s, avg=px, opened=f["at"], pnl=0.0)
            continue
        if (p["qty"] > 0) == (s > 0):
            nq = p["qty"] + s
            p["avg"] = (p["avg"] * abs(p["qty"]) + px * abs(s)) / abs(nq)
            p["qty"] = nq
            continue
        c = min(abs(s), abs(p["qty"]))
        d = 1 if p["qty"] > 0 else -1
        p["pnl"] += (px - p["avg"]) * c * d
        p["qty"] += s
        if p["qty"] == 0:
            it, und = meta(sym)
            out.append(SimpleNamespace(
                id=uuid4(), broker_account_id=None, tradingsymbol=sym,
                exchange="NFO", product="MIS", instrument_type=it,
                direction="LONG" if d > 0 else "SHORT", total_quantity=abs(c),
                avg_entry_price=Decimal(str(round(p["avg"], 4))),
                avg_exit_price=Decimal(str(px)),
                realized_pnl=Decimal(str(round(p["pnl"], 2))),
                pnl_pct=None, duration_minutes=None,
                entry_time=p["opened"], exit_time=f["at"],
                num_entries=1, num_exits=1, closed_by_flip=False,
                status="closed", quality_score=None, _und=und))
            p.update(qty=0, avg=0.0, opened=None, pnl=0.0)
    return [t for t in out if t.exit_time and t.exit_time.date() == day_fills[0]["date"]]


def risk_of(t):
    return risk_basis(t.instrument_type, t.tradingsymbol, t.direction,
                      float(t.avg_entry_price), int(t.total_quantity)).amount


def hist(vals, edges, label):
    print(f"\n  {label}   n={len(vals)}")
    mx = 0
    rows = []
    for lo, hi in zip(edges, edges[1:] + [float("inf")]):
        n = sum(1 for v in vals if lo <= v < hi)
        rows.append((lo, hi, n))
        mx = max(mx, n)
    for lo, hi, n in rows:
        name = f"{lo:>8,.0f}-{hi:<8,.0f}" if hi != float("inf") else f"{lo:>8,.0f}+       "
        print(f"    {name} {n:>4} {'#' * int(round(44 * n / mx)) if mx else ''}")


def gaps(vals, min_gap):
    v = sorted(vals)
    return [(round(v[i-1]), round(v[i])) for i in range(1, len(v))
            if v[i] - v[i-1] > min_gap]


def main():
    fills = read_fills("D:/trade-psychology-ai/docs/tradebook-CY6001-FO2025-26.csv")
    fills.sort(key=lambda f: f["at"])
    byday = defaultdict(list)
    for f in fills:
        byday[f["date"]].append(f)

    fired = []
    for day in sorted(byday):
        ts = build(byday[day], carry_fills(fills, day))
        if not ts:
            continue
        ts.sort(key=lambda t: t.exit_time)
        for i, ct in enumerate(ts):
            ctx = EngineContext(
                broker_account_id=uuid4(),
                session=SimpleNamespace(session_pnl=Decimal("0"),
                                        session_date=day, market_open=None),
                completed_trade=ct, session_trades=ts[:i],
                active_cooldowns=[], thresholds={})
            ev = engine._detect_consecutive_loss_streak(ctx)
            if not ev:
                continue
            after = ts[i+1:]
            fired.append({
                "day": str(day),
                "streak": ev.context["streak"],
                "loss": ev.context["total_loss"],
                "trades_after": len(after),
                "stopped": len(after) == 0,
                "risk_before": risk_of(ct),
                "risk_after": risk_of(after[0]) if after else None,
                "next_won": (float(after[0].realized_pnl) > 0) if after else None,
            })

    print(f"firings {len(fired)}")

    # ── the three candidates ─────────────────────────────────────────────
    A = [f["loss"] for f in fired]
    C = [100 * f["loss"] / CAPITAL for f in fired]

    print("\n" + "=" * 70)
    print("A. ABSOLUTE LOSS")
    print("=" * 70)
    hist(A, [0, 1000, 2000, 3000, 4000, 5000, 6000, 8000, 10000], "rupees")
    a = sorted(A)
    print(f"\n    p10 {a[len(a)//10]:,.0f}  p25 {a[len(a)//4]:,.0f}  "
          f"p50 {a[len(a)//2]:,.0f}  p75 {a[3*len(a)//4]:,.0f}  max {a[-1]:,.0f}")
    print(f"    empty gaps wider than Rs 1,000 inside the range: "
          f"{gaps(A, 1000) or 'none'}")

    print("\n" + "=" * 70)
    print("B. LOSS AS % OF THE DECLARED DAILY LIMIT")
    print("=" * 70)
    print("    The trader declared no limit, so this cannot be computed on this")
    print("    dataset at all. The engine returns None and provides no fallback.")
    print("    Any distribution shown here would be one I invented by choosing a")
    print("    limit - which is the thing this review may not do.")

    print("\n" + "=" * 70)
    print(f"C. LOSS AS % OF CAPITAL (assuming Rs {CAPITAL:,.0f})")
    print("=" * 70)
    hist(C, [0, 2, 4, 6, 8, 10, 15, 20], "percent of capital")
    c = sorted(C)
    print(f"\n    p25 {c[len(c)//4]:.1f}%  p50 {c[len(c)//2]:.1f}%  "
          f"p75 {c[3*len(c)//4]:.1f}%  max {c[-1]:.1f}%")
    print("    NOTE: this is A rescaled by a constant. Same shape, same gaps,")
    print("    same ranking - it cannot separate anything A does not.")

    # ── the bar: does any of it separate BEHAVIOUR? ──────────────────────
    print("\n" + "=" * 70)
    print("THE BAR: does loss size separate what the trader does NEXT?")
    print("=" * 70)
    a_sorted = sorted(fired, key=lambda f: f["loss"])
    half = len(a_sorted) // 2
    small, big = a_sorted[:half], a_sorted[half:]

    def summarise(g, label):
        stopped = sum(1 for f in g if f["stopped"])
        cont = [f for f in g if not f["stopped"]]
        grew = sum(1 for f in cont
                   if f["risk_after"] and f["risk_after"] > f["risk_before"])
        won = sum(1 for f in cont if f["next_won"])
        print(f"  {label:<26} n={len(g):<4} "
              f"stopped {100*stopped/len(g):>5.1f}%   "
              f"next trade bigger {100*grew/max(len(cont),1):>5.1f}%   "
              f"next trade won {100*won/max(len(cont),1):>5.1f}%")

    summarise(small, "smaller half of losses")
    summarise(big, "larger half of losses")
    print(f"\n  (median loss: small {small[-1]['loss']:,.0f} and below, "
          f"big above)")

    print("\n  Same split by STREAK LENGTH, for comparison:")
    s3 = [f for f in fired if f["streak"] == 3]
    s4 = [f for f in fired if f["streak"] >= 4]
    summarise(s3, "streak of 3")
    summarise(s4, "streak of 4 or more")

    print("\n" + "=" * 70)
    print("IS 0.5 x daily_loss_limit JUSTIFIED BY ANYTHING?")
    print("=" * 70)
    print(f"    times the branch fired in {len(fired)} firings: 0")
    print("    times it has fired in production: 0 (no real users)")
    print("    tests covering it: 0")
    print("    There is no evidence for it and none against it. It has never")
    print("    been exercised, so it is untested rather than wrong.")

    json.dump(fired, open(r"C:\Users\being\.claude\jobs\33a73186/tmp/streak_sev.json", "w"),
              indent=1, default=str)


main()
