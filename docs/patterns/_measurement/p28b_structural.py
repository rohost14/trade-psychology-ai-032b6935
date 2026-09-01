"""
Follow-up: are the two reconstructions measuring BEHAVIOUR or ARITHMETIC?

Two suspicions from p28_measure:

  portfolio_concentration fires on 90.3% of the moments it judges. With only
  TWO open positions the top underlying is >= 50% BY CONSTRUCTION, and the
  caution cut is 40% - so a 2-position book cannot NOT fire. If that is where
  the firings live, the detector is reporting the size of the book, not
  concentration. This is the `profit_giveaway` shape (a drawdown from the
  session peak is arithmetic) and the `expiry_day_overtrading` shape (it fired
  on 55 of 55 and never withheld).

  overexposure has a median exposure of 14.1% of Rs 1L against a 15% trigger.
  A threshold sitting on the median of its own distribution is not selective.
  And the max is 1237% of capital - which is what NOTIONAL does to a futures
  or short-option position, and the reason excess_exposure's MARGIN quantity
  is the other half of this question.
"""
import sys
from collections import defaultdict

sys.path.insert(0, "D:/trade-psychology-ai")
sys.path.insert(0, "D:/trade-psychology-ai/backend")
sys.path.insert(0, "D:/trade-psychology-ai/docs/patterns/_measurement")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from p28_openbook import OpenBook, key_of                              # noqa: E402
from p28_measure import (                                              # noqa: E402
    BOOK, EXCHANGE, underlying_of, concentration_predicate,
    overexposure_predicate, pctile,
)
from tradedesk.scripts.replay_tradebook import read_fills              # noqa: E402
from app.services.fill_classification import POSITION_OPENING_FILLS    # noqa: E402
from app.services.instrument_parser import parse_symbol                # noqa: E402


def main():
    fills = sorted(read_fills(BOOK), key=lambda f: f["at"])
    book = OpenBook()
    last_price = {}

    by_n = defaultdict(lambda: {"eval": 0, "fired": 0, "pct": []})
    by_nu = defaultdict(lambda: {"eval": 0, "fired": 0})
    big = []
    inst_fired = defaultdict(int)
    inst_all = defaultdict(int)

    for f in fills:
        sym = f["symbol"]
        k = key_of(sym, EXCHANGE, "MIS")
        signed = f["qty"] if f["side"] == "BUY" else -f["qty"]
        px = float(f["price"])
        last_price[sym] = px
        etype, newq, _, _ = book.apply(k, signed, px, f["at"])
        if etype not in POSITION_OPENING_FILLS:
            continue

        openpos = book.open_positions()
        n = len(openpos)
        nu = len({underlying_of(p["tradingsymbol"]) for p in openpos})

        c = concentration_predicate(
            openpos,
            lambda p: last_price.get(p["tradingsymbol"],
                                     float(p["avg_entry_price"] or 0)))
        if "abstain" not in c:
            by_n[n]["eval"] += 1
            by_n[n]["pct"].append(c["pct"])
            by_n[n]["fired"] += int(c["fired"])
            by_nu[nu]["eval"] += 1
            by_nu[nu]["fired"] += int(c["fired"])

        r = overexposure_predicate(sym, EXCHANGE, px, newq, 100_000, 10.0)
        if "abstain" not in r:
            try:
                it = parse_symbol(sym).instrument_type or "?"
            except Exception:
                it = "?"
            inst_all[it] += 1
            if r["fired"]:
                inst_fired[it] += 1
            if r["pct"] >= 100:
                big.append((sym, it, r["pct"], r["value"], newq, px))

    print("=" * 78)
    print("A. portfolio_concentration by NUMBER OF OPEN POSITIONS")
    print("=" * 78)
    print("   With n equal-valued positions the top share is 1/n. The caution")
    print("   cut is 40%, so n=2 (>=50% always) can NEVER withhold, and n=3")
    print("   withholds only if the book is near-perfectly balanced.")
    print()
    print(f"   {'n open':>7} {'evals':>7} {'fired':>7} {'rate':>8}  "
          f"{'min share':>10} {'median':>8}")
    for n in sorted(by_n):
        d = by_n[n]
        if not d["eval"]:
            continue
        print(f"   {n:>7} {d['eval']:>7} {d['fired']:>7} "
              f"{d['fired']/d['eval']*100:>7.1f}%  "
              f"{min(d['pct']):>9.1f}% {pctile(d['pct'],0.5):>7.1f}%")

    tot_e = sum(d["eval"] for d in by_n.values())
    tot_f = sum(d["fired"] for d in by_n.values())
    two = by_n.get(2, {"eval": 0, "fired": 0})
    print()
    print(f"   total judged {tot_e}, fired {tot_f}")
    if tot_f:
        print(f"   share of ALL firings that came from a 2-POSITION book: "
              f"{two['fired']/tot_f*100:.1f}%  ({two['fired']}/{tot_f})")
    if two["eval"]:
        print(f"   2-position withhold rate: "
              f"{(two['eval']-two['fired'])/two['eval']*100:.1f}%")

    print()
    print("=" * 78)
    print("B. portfolio_concentration by NUMBER OF DISTINCT UNDERLYINGS")
    print("=" * 78)
    print(f"   {'n underlyings':>14} {'evals':>7} {'fired':>7} {'rate':>8}")
    for nu in sorted(by_nu):
        d = by_nu[nu]
        print(f"   {nu:>14} {d['eval']:>7} {d['fired']:>7} "
              f"{d['fired']/d['eval']*100:>7.1f}%")

    print()
    print("=" * 78)
    print("C. overexposure - what NOTIONAL does, by instrument type (Rs 1L)")
    print("=" * 78)
    print(f"   {'type':>6} {'evals':>7} {'fired':>7} {'rate':>8}")
    for it in sorted(inst_all):
        print(f"   {it:>6} {inst_all[it]:>7} {inst_fired[it]:>7} "
              f"{inst_fired[it]/inst_all[it]*100:>7.1f}%")
    print()
    print(f"   entries whose NOTIONAL exceeded 100% of Rs 1L capital: {len(big)}")
    for s, it, pct, val, q, px in sorted(big, key=lambda x: -x[2])[:10]:
        print(f"     {s:<26} {it:<4} {pct:>8.1f}%  value Rs {val:>12,.0f}  "
              f"qty {q:>6} @ {px}")
    print()
    print("   A position cannot cost more capital than the account holds. These")
    print("   are NOTIONAL - contract value - not what the position required.")
    print("   That is the quantity `overexposure` divides by capital, and it is")
    print("   the half of the question `excess_exposure` answers differently.")


if __name__ == "__main__":
    main()
