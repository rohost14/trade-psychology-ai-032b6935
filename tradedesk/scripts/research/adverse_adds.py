"""
Pattern #1 rework — measuring ADDING TO AN ADVERSE POSITION from raw fills.

The unit is the fill, not the CompletedTrade. A CompletedTrade aggregates every
entry into one avg_entry_price, so "1 lot @50, add 1 @40, add 1 @30" collapses
into a single row at 40 and the adds vanish. Everything below therefore works
from the tradebook's own orders.

Directionally symmetric by construction: adverse is measured against the
position's own direction, so a long filling lower and a short filling higher are
the same event.
"""
import json
import sys
from collections import defaultdict

sys.path.insert(0, "backend")
sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from tradedesk.scripts.replay_tradebook import read_fills  # noqa: E402
from app.services.instrument_parser import parse_symbol  # noqa: E402

OUT = r"C:\Users\being\.claude\jobs\33a73186/tmp/adverse_adds.json"


def itype(sym):
    try:
        p = parse_symbol(sym or "")
        return (p.instrument_type or "EQ"), (p.underlying or sym or "")
    except Exception:
        return "EQ", sym or ""


def main():
    fills = read_fills("docs/tradebook-CY6001-FO2025-26.csv")
    fills.sort(key=lambda f: f["at"])

    # running position per (date, symbol) — intraday book, positions are per day
    pos = defaultdict(lambda: {"qty": 0, "avg": 0.0, "adds": [], "opened": None,
                               "realized": 0.0, "legs": 0})
    episodes = []

    for f in fills:
        key = (f["date"], f["symbol"])
        p = pos[key]
        signed = f["qty"] if f["side"] == "BUY" else -f["qty"]
        price = float(f["price"])

        if p["qty"] == 0:
            # opening fill
            p.update(qty=signed, avg=price, adds=[], opened=f["at"], legs=1)
            continue

        same_direction = (p["qty"] > 0) == (signed > 0)
        if same_direction:
            # ADD to an existing position — the event this review is about
            direction = 1 if p["qty"] > 0 else -1
            # adverse move since the position's average entry, signed by direction
            adverse_pct = ((p["avg"] - price) / p["avg"] * 100) * direction
            add_ratio = abs(signed) / abs(p["qty"])          # size of the add vs what is held
            p["adds"].append({
                "adverse_pct": round(adverse_pct, 2),
                "add_ratio": round(add_ratio, 3),
                "price": price,
                "avg_before": round(p["avg"], 2),
                "qty_before": p["qty"],
                "add_qty": signed,
                "at": f["at"].isoformat(),
            })
            new_qty = p["qty"] + signed
            p["avg"] = (p["avg"] * abs(p["qty"]) + price * abs(signed)) / abs(new_qty)
            p["qty"] = new_qty
            p["legs"] += 1
        else:
            # reducing or closing
            closing = min(abs(signed), abs(p["qty"]))
            direction = 1 if p["qty"] > 0 else -1
            p["realized"] += (price - p["avg"]) * closing * direction
            p["qty"] += signed
            if p["qty"] == 0 or (p["qty"] > 0) != (direction > 0):
                it, und = itype(f["symbol"])
                episodes.append({
                    "date": str(f["date"]), "symbol": f["symbol"],
                    "instrument": it, "underlying": und,
                    "direction": "LONG" if direction > 0 else "SHORT",
                    "legs": p["legs"], "adds": p["adds"],
                    "realized": round(p["realized"], 2),
                    "opened": p["opened"].isoformat() if p["opened"] else None,
                })
                leftover = p["qty"]
                p.update(qty=0, avg=0.0, adds=[], opened=None, realized=0.0, legs=0)
                if leftover != 0:      # flipped through zero
                    p.update(qty=leftover, avg=price, opened=f["at"], legs=1)

    json.dump(episodes, open(OUT, "w"), indent=1)

    # ---------------- summary ----------------
    n = len(episodes)
    multi = [e for e in episodes if e["adds"]]
    adverse = [e for e in episodes if any(a["adverse_pct"] > 0 for a in e["adds"])]
    favourable = [e for e in episodes
                  if e["adds"] and all(a["adverse_pct"] <= 0 for a in e["adds"])]
    print(f"positions (open->flat): {n}")
    print(f"  with at least one ADD:        {len(multi)}  ({100*len(multi)/n:.1f}%)")
    print(f"  at least one ADVERSE add:     {len(adverse)}  ({100*len(adverse)/n:.1f}%)")
    print(f"  adds only while FAVOURABLE:   {len(favourable)}")
    print()

    all_adv = [a for e in episodes for a in e["adds"] if a["adverse_pct"] > 0]
    all_fav = [a for e in episodes for a in e["adds"] if a["adverse_pct"] <= 0]
    print(f"individual adds: {len(all_adv)} adverse, {len(all_fav)} favourable")
    if all_adv:
        v = sorted(a["adverse_pct"] for a in all_adv)
        print(f"  adverse move at the moment of adding: "
              f"p25 {v[len(v)//4]:.1f}%  p50 {v[len(v)//2]:.1f}%  "
              f"p75 {v[3*len(v)//4]:.1f}%  max {v[-1]:.1f}%")
        r = sorted(a["add_ratio"] for a in all_adv)
        print(f"  size of the add vs position held: "
              f"p25 {r[len(r)//4]:.2f}x  p50 {r[len(r)//2]:.2f}x  "
              f"p75 {r[3*len(r)//4]:.2f}x  max {r[-1]:.2f}x")
        under = sum(1 for x in r if x < 1.5)
        print(f"  adds SMALLER than 1.5x the held position: {under} of {len(r)} "
              f"({100*under/len(r):.0f}%)  <- invisible to a 1.5x rule")
    print()

    from collections import Counter
    c = Counter(sum(1 for a in e["adds"] if a["adverse_pct"] > 0) for e in adverse)
    print("adverse adds per position:", dict(sorted(c.items())))
    print()
    print("instrument mix of adverse-add positions:",
          dict(Counter(e["instrument"] for e in adverse)))
    print("direction mix:", dict(Counter(e["direction"] for e in adverse)))
    print()
    def med(xs):
        xs = sorted(xs)
        return xs[len(xs)//2] if xs else 0
    print(f"median realized P&L — adverse-add positions: "
          f"{med([e['realized'] for e in adverse]):,.0f}")
    print(f"median realized P&L — favourable-add only:   "
          f"{med([e['realized'] for e in favourable]):,.0f}")
    print(f"median realized P&L — single-fill positions: "
          f"{med([e['realized'] for e in episodes if not e['adds']]):,.0f}")


main()
