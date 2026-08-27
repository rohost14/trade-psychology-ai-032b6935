"""
Pattern #9 - `expiry_day_overtrading`, measured.

The claim, as shown to the trader:

  danger : "N NIFTY trades today on expiry. NSE data: retail option activity in
            the last 2 hours of expiry day has a structural loss rate above 85%."
  caution: "N trades / M lots today on expiry. Each additional trade after 13:00
            on expiry day statistically reduces your edge."

Both are falsifiable against this book, and both are attributed to a source. The
attribution traces only to docs/archive/PATTERN_REFERENCE.md, which asserts "NSE
market data shows" and cites nothing.

WHAT TO MEASURE

  1. what it fires on, and which branch
  2. THE UNITS QUESTION. `today_lots` sums `total_quantity`, which is CONTRACTS,
     not lots - one NIFTY lot is 75 contracts. The threshold is 10. If the sum is
     in contracts then a single option trade clears it and the caution branch is
     not a threshold at all.
  3. the 13:00 gate - how much expiry trading is on each side of it
  4. the claim itself: is post-13:00 expiry trading actually worse for this
     trader, and does each additional trade reduce the edge?
"""
import sys
from collections import Counter, defaultdict
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4
from zoneinfo import ZoneInfo

sys.path.insert(0, "D:/trade-psychology-ai")
sys.path.insert(0, "D:/trade-psychology-ai/backend")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from tradedesk.scripts.replay_tradebook import read_fills, carry_fills  # noqa: E402
from app.services.behavior_engine import BehaviorEngine, EngineContext  # noqa: E402
from app.services.instrument_parser import parse_symbol, is_expiry_day  # noqa: E402

engine = BehaviorEngine()
IST = ZoneInfo("Asia/Kolkata")


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


def main():
    fills = read_fills("D:/trade-psychology-ai/docs/tradebook-CY6001-FO2025-26.csv")
    fills.sort(key=lambda f: f["at"])
    byday = defaultdict(list)
    for f in fills:
        byday[f["date"]].append(f)
    sessions = []
    for day in sorted(byday):
        ts = build(byday[day], carry_fills(fills, day))
        if ts:
            ts.sort(key=lambda t: t.entry_time or t.exit_time)
            sessions.append((day, ts))
    allp = [t for _, t in sessions for t in t]
    print(f"{len(sessions)} sessions, {len(allp)} positions")

    # ── the population it can see ─────────────────────────────────────────
    exp = []
    for _, ts in sessions:
        for t in ts:
            if t.instrument_type not in ("CE", "PE", "FUT") or not t.entry_time:
                continue
            ist = t.entry_time.astimezone(IST)
            if is_expiry_day(t.tradingsymbol or "", ist.date()):
                exp.append((t, ist))
    print(f"expiry-day positions: {len(exp)} ({100*len(exp)/len(allp):.0f}% of all)")

    before = [x for x in exp if x[1].hour < 13]
    after = [x for x in exp if x[1].hour >= 13]
    print(f"  entered before 13:00 IST (gate excludes): {len(before)}")
    print(f"  entered at/after 13:00 (eligible)       : {len(after)}")

    # ── THE UNITS QUESTION ───────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("2. UNITS - is `today_lots` counting lots, or contracts?")
    print("=" * 78)
    qtys = sorted(int(t.total_quantity) for t, _ in exp)
    print(f"  total_quantity on expiry positions: min {qtys[0]}  "
          f"median {qtys[len(qtys)//2]}  max {qtys[-1]}")
    over = sum(1 for q in qtys if q >= 10)
    print(f"  positions whose SINGLE quantity already reaches the 10-'lot' line: "
          f"{over} of {len(qtys)} ({100*over/len(qtys):.0f}%)")
    print("  A NIFTY lot is 75 contracts. If these are contracts, the lots")
    print("  threshold is cleared by one ordinary trade and is not a threshold.")

    # ── run the detector ─────────────────────────────────────────────────
    fired = []
    for day, ts in sessions:
        for i, ct in enumerate(ts):
            ctx = EngineContext(
                broker_account_id=uuid4(),
                session=SimpleNamespace(session_pnl=Decimal("0"),
                                        session_date=day, market_open=None),
                completed_trade=ct, session_trades=ts[:i],
                active_cooldowns=[], thresholds={})
            ev = engine._detect_expiry_day_overtrading(ctx)
            if ev:
                c = ev.context
                fired.append({
                    "day": str(day), "sev": ev.severity,
                    "count": c["today_count"], "lots": c["today_lots"],
                    "legs": c["today_legs"], "und": c["underlying"],
                    "pnl": float(ct.realized_pnl),
                    "by_lots_only": (ev.severity == "caution"
                                     and c["today_count"] < 5),
                })

    print("\n" + "=" * 78)
    print("1. WHAT IT FIRES")
    print("=" * 78)
    days = {f["day"] for f in fired}
    print(f"  detections: {len(fired)} on {len(days)} of {len(sessions)} sessions")
    print(f"  severity: {dict(Counter(f['sev'] for f in fired))}")
    only_lots = [f for f in fired if f["by_lots_only"]]
    print(f"  fired on the LOTS clause alone (trade count under 5): "
          f"{len(only_lots)} of {len(fired)} ({100*len(only_lots)/max(1,len(fired)):.0f}%)")
    print(f"  trade count at firing: {dict(sorted(Counter(f['count'] for f in fired).items()))}")

    # ── the claim ────────────────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("4. THE CLAIM - is post-13:00 expiry trading worse for THIS trader?")
    print("=" * 78)

    def stats(rows, label):
        if not rows:
            print(f"  {label:<44} n=0")
            return
        pnls = [float(t.realized_pnl) for t, _ in rows]
        wins = sum(1 for p in pnls if p > 0)
        print(f"  {label:<44} n={len(rows):<5} win {100*wins/len(rows):>5.1f}%   "
              f"total Rs {sum(pnls):>10,.0f}   mean Rs {sum(pnls)/len(pnls):>8,.0f}")

    nonexp = [(t, None) for t in allp
              if (t, None) not in exp and t.instrument_type in ("CE", "PE", "FUT")]
    expset = {id(t) for t, _ in exp}
    nonexp = [(t, None) for t in allp if id(t) not in expset]

    stats(after, "expiry day, entered 13:00 or later")
    stats(before, "expiry day, entered before 13:00")
    stats(nonexp, "every non-expiry position")
    print(f"\n  book-wide win rate for reference: 39.9%")

    print("\n  Does each ADDITIONAL post-13:00 expiry trade reduce the edge?")
    seq = defaultdict(list)
    for day, ts in sessions:
        n = 0
        for t in ts:
            if t.instrument_type not in ("CE", "PE", "FUT") or not t.entry_time:
                continue
            ist = t.entry_time.astimezone(IST)
            if not is_expiry_day(t.tradingsymbol or "", ist.date()) or ist.hour < 13:
                continue
            n += 1
            seq[min(n, 6)].append(float(t.realized_pnl))
    print(f"    {'nth trade':>10}{'n':>6}{'win rate':>10}{'mean Rs':>12}")
    for k in sorted(seq):
        v = seq[k]
        w = sum(1 for p in v if p > 0)
        label = f"{k}" if k < 6 else "6+"
        print(f"    {label:>10}{len(v):>6}{100*w/len(v):>9.1f}%{sum(v)/len(v):>12,.0f}")


main()
