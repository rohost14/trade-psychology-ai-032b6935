"""
Is CAPITAL UTILIZATION a behavioural signal, or just a level?

The product question: 80% utilized across 3 positions may be completely ordinary
for an F&O trader. Alerting on it would be alerting on normal operation.

So this measures, at every position-opening fill:

  utilization       = sum(capital_requirement over the OPEN BOOK) / capital
  largest_share     = largest single position's capital_requirement / capital
  concentration     = largest_share / utilization  (how much of the deployed
                      capital sits in one position)

and then asks the only question that licenses an alert:

  DOES ANY OF IT PREDICT A WORSE OUTCOME?

If high utilization does not separate outcomes, it is a level to display, not a
behaviour to flag - the same test that retired five detectors.

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
from app.core.risk_quantities import quantities_for_trade              # noqa: E402
from app.services.instrument_parser import parse_symbol                # noqa: E402


def meta(sym):
    try:
        p = parse_symbol(sym or "")
        return (p.instrument_type or "EQ"), (p.underlying or sym)
    except Exception:
        return "EQ", sym


def cap_req(sym, qty, avg_price):
    it, _ = meta(sym)
    ct = SimpleNamespace(
        id=uuid4(), tradingsymbol=sym, exchange=EXCHANGE, product="MIS",
        instrument_type=it, direction="LONG" if qty > 0 else "SHORT",
        total_quantity=abs(qty),
        avg_entry_price=Decimal(str(round(float(avg_price or 0), 4))),
        avg_exit_price=None, realized_pnl=None)
    rq = quantities_for_trade(ct, margin=None)
    return (rq.capital_requirement.amount if rq.usable_for_capital_rules else None)


def main(CAPITAL=100_000):
    fills = sorted(read_fills(BOOK), key=lambda f: f["at"])
    book = OpenBook()
    opened_at, cost = {}, defaultdict(float)
    events = []            # one per opening fill
    pending = {}           # k -> list of event indexes awaiting the round result

    for f in fills:
        sym = f["symbol"]
        k = key_of(sym, EXCHANGE, "MIS")
        s = f["qty"] if f["side"] == "BUY" else -f["qty"]
        px = float(f["price"])
        before = book.qty[k]
        et, nq, na, rp = book.apply(k, s, px, f["at"])
        cost[k] += float(rp or 0)
        if before == 0 and nq != 0:
            opened_at[k] = f["at"]

        if et in POSITION_OPENING_FILLS:
            reqs, unknown = {}, 0
            for p in book.open_positions():
                c = cap_req(p["tradingsymbol"], p["qty"], p["avg_entry_price"])
                if c is None:
                    unknown += 1
                else:
                    reqs[p["key"]] = c
            total = sum(reqs.values())
            this = reqs.get(k)
            events.append({
                "at": f["at"], "sym": sym, "n": len(book.open_positions()),
                "util": total / CAPITAL * 100,
                "this": (this / CAPITAL * 100) if this is not None else None,
                "share_of_deployed": (this / total * 100) if this and total else None,
                "unknown": unknown, "pnl": None,
            })
            pending.setdefault(k, []).append(len(events) - 1)

        if nq == 0 and k in opened_at:
            for i in pending.pop(k, []):
                events[i]["pnl"] = cost[k]
            opened_at.pop(k, None)
            cost[k] = 0.0

    done = [e for e in events if e["pnl"] is not None]
    print("=" * 78)
    print(f"CAPITAL UTILIZATION AS A SIGNAL   (declared capital Rs {CAPITAL:,})")
    print("=" * 78)
    print(f"  opening fills          : {len(events):,}")
    print(f"  with a known outcome   : {len(done):,}")
    print(f"  fills where some open position had NO usable capital figure: "
          f"{sum(1 for e in events if e['unknown']):,}")

    u = [e["util"] for e in events]
    print()
    print("  utilization at the moment of an opening fill:")
    print(f"    p10 {pctile(u,0.10):>6.1f}%  p25 {pctile(u,0.25):>6.1f}%  "
          f"p50 {pctile(u,0.50):>6.1f}%  p75 {pctile(u,0.75):>6.1f}%  "
          f"p90 {pctile(u,0.90):>6.1f}%  max {max(u):>7.1f}%")
    for lo, hi in [(0,25),(25,50),(50,80),(80,100),(100,10**9)]:
        c = sum(1 for x in u if lo <= x < hi)
        print(f"    {lo:>4}-{hi if hi<10**9 else '+':<5} {c:>5,}  "
              f"({c/len(u)*100:5.1f}%)")

    print()
    print("=" * 78)
    print("A. DOES UTILIZATION PREDICT A WORSE OUTCOME?")
    print("=" * 78)
    print("   Outcome of the position OPENED at that moment, by the utilization")
    print("   of the whole book at that moment.")
    print()
    print(f"   {'utilization':>14} {'n':>5} {'win%':>7} {'mean Rs':>10} {'median Rs':>11}")
    for lo, hi in [(0,25),(25,50),(50,80),(80,100),(100,10**9)]:
        g = [e for e in done if lo <= e["util"] < hi]
        if not g:
            continue
        w = sum(1 for e in g if e["pnl"] > 0)
        m = sorted(e["pnl"] for e in g)[len(g)//2]
        lab = f"{lo}-{hi}%" if hi < 10**9 else f"{lo}%+"
        print(f"   {lab:>14} {len(g):>5} {w/len(g)*100:>6.1f}% "
              f"{sum(e['pnl'] for e in g)/len(g):>10,.0f} {m:>11,.0f}")

    print()
    print("=" * 78)
    print("B. DOES THE SIZE OF THE SINGLE POSITION PREDICT ONE?")
    print("=" * 78)
    print("   Same outcomes, bucketed by THIS position's capital as a share of")
    print("   total capital - the thing overexposure actually measures.")
    print()
    print(f"   {'this position':>14} {'n':>5} {'win%':>7} {'mean Rs':>10} {'median Rs':>11}")
    have = [e for e in done if e["this"] is not None]
    for lo, hi in [(0,5),(5,10),(10,15),(15,25),(25,10**9)]:
        g = [e for e in have if lo <= e["this"] < hi]
        if not g:
            continue
        w = sum(1 for e in g if e["pnl"] > 0)
        m = sorted(e["pnl"] for e in g)[len(g)//2]
        lab = f"{lo}-{hi}%" if hi < 10**9 else f"{lo}%+"
        print(f"   {lab:>14} {len(g):>5} {w/len(g)*100:>6.1f}% "
              f"{sum(e['pnl'] for e in g)/len(g):>10,.0f} {m:>11,.0f}")

    print()
    print("=" * 78)
    print("C. UTILIZATION vs CONCENTRATION - are they the same thing here?")
    print("=" * 78)
    print("   'share of deployed' = this position / all deployed capital.")
    print("   1 open position => 100% by construction, so the split matters.")
    print()
    byn = defaultdict(list)
    for e in events:
        byn[e["n"]].append(e)
    print(f"   {'n open':>7} {'evals':>6} {'median util':>12} "
          f"{'median share of deployed':>26}")
    for n in sorted(byn):
        g = byn[n]
        sh = [x["share_of_deployed"] for x in g if x["share_of_deployed"]]
        print(f"   {n:>7} {len(g):>6} {pctile([x['util'] for x in g],0.5):>11.1f}% "
              f"{(pctile(sh,0.5) if sh else float('nan')):>25.1f}%")


if __name__ == "__main__":
    main()
