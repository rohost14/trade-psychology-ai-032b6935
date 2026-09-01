"""
Design input for the overexposure / excess_exposure pass.

THE QUESTION. `overexposure` divides NOTIONAL by capital; `excess_exposure`
divides CAPITAL REQUIREMENT by capital. How often do those two differ, on what,
and what does each one cover?

This is not a threshold search. It measures, per instrument type and direction:

  * whether capital_requirement is even AVAILABLE without a broker margin figure
  * how far notional and capital_requirement diverge when both exist
  * what share of the book each detector can actually judge

No threshold is proposed anywhere in this file.
"""
import sys
from collections import defaultdict
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

sys.path.insert(0, "D:/trade-psychology-ai")
sys.path.insert(0, "D:/trade-psychology-ai/backend")
sys.path.insert(0, "D:/trade-psychology-ai/docs/patterns/_measurement")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from p28_openbook import OpenBook, key_of                              # noqa: E402
from p28_measure import BOOK, EXCHANGE, pctile                         # noqa: E402
from tradedesk.scripts.replay_tradebook import read_fills              # noqa: E402
from app.services.fill_classification import POSITION_OPENING_FILLS    # noqa: E402
from app.tasks.position_monitor_tasks import _exposure_value           # noqa: E402
from app.core.risk_quantities import quantities_for_trade              # noqa: E402
from app.services.instrument_parser import parse_symbol                # noqa: E402


def meta(sym):
    try:
        p = parse_symbol(sym or "")
        return (p.instrument_type or "EQ"), (p.underlying or sym)
    except Exception:
        return "EQ", sym


def main():
    fills = sorted(read_fills(BOOK), key=lambda f: f["at"])
    book = OpenBook()

    rows = []
    for f in fills:
        sym = f["symbol"]
        k = key_of(sym, EXCHANGE, "MIS")
        signed = f["qty"] if f["side"] == "BUY" else -f["qty"]
        px = float(f["price"])
        etype, newq, newavg, _ = book.apply(k, signed, px, f["at"])
        if etype not in POSITION_OPENING_FILLS:
            continue

        it, und = meta(sym)
        is_long = newq > 0
        # the shape excess_exposure evaluates, built from the open position
        ct = SimpleNamespace(
            id=uuid4(), tradingsymbol=sym, exchange=EXCHANGE, product="MIS",
            instrument_type=it, direction="LONG" if is_long else "SHORT",
            total_quantity=abs(newq),
            avg_entry_price=Decimal(str(round(float(newavg or px), 4))),
            avg_exit_price=None, realized_pnl=None,
        )
        rq = quantities_for_trade(ct, margin=None)   # no broker margin, as live
        notional, reliable = _exposure_value(sym, EXCHANGE, px, newq)

        rows.append({
            "sym": sym, "it": it, "long": is_long,
            "notional": notional if reliable else None,
            "notional_ok": reliable,
            "cap": rq.capital_requirement.amount,
            "cap_ok": rq.usable_for_capital_rules,
            "kind": rq.denominator_kind.value,
            "note": rq.capital_requirement.note,
        })

    print("=" * 78)
    print("A. COVERAGE - what can each detector's quantity even be computed for?")
    print("=" * 78)
    print("   (no broker margin supplied, which is the live situation: the Kite")
    print("    postback carries none and /margins/orders is prospective only)")
    print()
    print(f"   {'type':>5} {'dir':>6} {'n':>6} {'notional ok':>12} "
          f"{'capital_req ok':>15}  denominator kind")
    grp = defaultdict(list)
    for r in rows:
        grp[(r["it"], "LONG" if r["long"] else "SHORT")].append(r)
    for k in sorted(grp):
        g = grp[k]
        nk = {r["kind"] for r in g}
        print(f"   {k[0]:>5} {k[1]:>6} {len(g):>6} "
              f"{sum(r['notional_ok'] for r in g):>12} "
              f"{sum(r['cap_ok'] for r in g):>15}  {','.join(sorted(nk))}")
    n = len(rows)
    print()
    print(f"   TOTAL opening fills                 : {n:,}")
    print(f"   notional computable                 : "
          f"{sum(r['notional_ok'] for r in rows):,}")
    print(f"   capital_requirement usable          : "
          f"{sum(r['cap_ok'] for r in rows):,}")
    absent = [r for r in rows if not r["cap_ok"]]
    print(f"   capital_requirement ABSTAINS        : {len(absent):,}")
    reasons = defaultdict(int)
    for r in absent:
        reasons[(r["it"], r["note"] or "")[0] + " | " + (r["note"] or "")[:60]] += 1
    for why, c in sorted(reasons.items(), key=lambda kv: -kv[1]):
        print(f"      {c:>4}  {why}")

    print()
    print("=" * 78)
    print("B. WHERE THE TWO QUANTITIES DIVERGE")
    print("=" * 78)
    both = [r for r in rows if r["notional_ok"] and r["cap_ok"] and r["cap"]]
    same = [r for r in both if abs(r["notional"] - r["cap"]) < 0.01]
    diff = [r for r in both if abs(r["notional"] - r["cap"]) >= 0.01]
    print(f"   both quantities available : {len(both):,}")
    print(f"   IDENTICAL                 : {len(same):,} "
          f"({len(same)/len(both)*100:.1f}%)" if both else "")
    print(f"   different                 : {len(diff):,}")
    if same:
        kinds = defaultdict(int)
        for r in same:
            kinds[r["kind"]] += 1
        print(f"   the identical set is      : {dict(kinds)}")
        print("   -> for a BOUGHT option the premium IS the capital. Definitional,")
        print("      not a coincidence, and true on any exchange incl. MCX.")
    if diff:
        for r in diff[:8]:
            print(f"      {r['sym']:<26} notional {r['notional']:>12,.0f}  "
                  f"capital {r['cap']:>12,.0f}")

    print()
    print("=" * 78)
    print("C. THE DISTRIBUTION, for whoever must later choose a line")
    print("=" * 78)
    print("   NOT a threshold proposal. Percentiles of capital_requirement as a")
    print("   share of capital, on the entries where it is usable.")
    for cap_base in (100_000, 200_000, 500_000):
        vals = [r["cap"] / cap_base * 100 for r in rows if r["cap_ok"] and r["cap"]]
        if not vals:
            continue
        print(f"   capital Rs {cap_base:>9,} : p50 {pctile(vals,0.50):>6.2f}%  "
              f"p75 {pctile(vals,0.75):>6.2f}%  p90 {pctile(vals,0.90):>6.2f}%  "
              f"p99 {pctile(vals,0.99):>7.2f}%  max {max(vals):>7.2f}%")
    print()
    print("   Same for NOTIONAL, the quantity in use today:")
    for cap_base in (100_000, 200_000, 500_000):
        vals = [r["notional"] / cap_base * 100 for r in rows if r["notional_ok"]]
        print(f"   capital Rs {cap_base:>9,} : p50 {pctile(vals,0.50):>6.2f}%  "
              f"p75 {pctile(vals,0.75):>6.2f}%  p90 {pctile(vals,0.90):>6.2f}%  "
              f"p99 {pctile(vals,0.99):>7.2f}%  max {max(vals):>7.2f}%")


if __name__ == "__main__":
    main()
