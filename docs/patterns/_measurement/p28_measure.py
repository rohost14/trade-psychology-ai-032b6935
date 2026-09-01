"""
Position-monitor measurement: overexposure, portfolio_concentration,
holding_loser.

USES THE VALIDATED HARNESS (p28_openbook.OpenBook -> production's own
`_compute_fill_effect`). Read docs/patterns/28-position-monitor/harness_validation.md
before trusting any number here.

THE DISTINCTION THIS FILE IS BUILT AROUND, and it is not a caveat:

  PREDICATE RECONSTRUCTION   - can we rebuild the exact decision the detector
                               makes, given the state it reads? YES for both,
                               because the state machine is validated and both
                               predicates are pure functions of it plus a price.
  FIRING-RATE VALIDATION     - is the resulting count what production would
                               actually have produced? NO. Both detectors read
                               `get_cached_ltp()` - a LIVE price - and the
                               tradebook carries only fill prices. Every count
                               below is a reconstruction under a stated price
                               substitution, NOT an observed firing rate.

The substitution is production's own fallback, not an invention:
`_concentration_task` already does `ltp = float(pos.average_entry_price)` when
the LTP cache misses. So the concentration numbers exercise a real production
branch. `_overexposure_task` has NO such fallback - it returns
{"skipped": "no_ltp"} - so its numbers are a reconstruction of a branch
production reaches only with a live price.

Run:
    python -u docs/patterns/_measurement/p28_measure.py
"""
import sys
from collections import defaultdict

sys.path.insert(0, "D:/trade-psychology-ai")
sys.path.insert(0, "D:/trade-psychology-ai/backend")
sys.path.insert(0, "D:/trade-psychology-ai/docs/patterns/_measurement")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from p28_openbook import OpenBook, key_of                              # noqa: E402
from tradedesk.scripts.replay_tradebook import read_fills              # noqa: E402
from app.services.fill_classification import POSITION_OPENING_FILLS    # noqa: E402
from app.tasks.position_monitor_tasks import _exposure_value           # noqa: E402
from app.tasks.position_monitor_tasks import (                         # noqa: E402
    HOLDING_LOSER_MIN_DURATION, HOLDING_LOSER_MIN_LOSS_PCT,
    MAX_HOLDING_LOSER_CHECKS,
)
from app.services.instrument_parser import parse_symbol                # noqa: E402

BOOK = "D:/trade-psychology-ai/docs/tradebook-CY6001-FO2025-26.csv"
EXCHANGE = "NFO"          # the reference book is NFO throughout
DEFAULT_MAX_POSITION_SIZE = 10.0   # `thresholds.get(...) or 10.0` in production


def underlying_of(sym):
    try:
        return parse_symbol(sym or "").underlying or sym
    except Exception:
        return sym


# ── the two predicates, transcribed from the production tasks ──────────────
# Only the ladder is transcribed. The quantity itself comes from production's
# own `_exposure_value`, so the F17 multiplier and the abstention path are the
# real ones.

def overexposure_predicate(symbol, exchange, price, qty, capital, max_size):
    value, reliable = _exposure_value(symbol, exchange, price, qty)
    if not reliable:
        return {"abstain": "unresolved_contract"}
    if not capital or capital <= 0 or qty == 0:
        return {"abstain": "no_capital"}
    pct = value / capital * 100
    if pct <= max_size * 1.5:
        return {"fired": False, "pct": pct, "value": value}
    if pct >= 30.0:
        sev = "critical"
    elif pct > max_size * 2:
        sev = "danger"
    else:
        sev = "caution"
    return {"fired": True, "severity": sev, "pct": pct, "value": value,
            "all_in": pct >= 50.0}


def concentration_predicate(open_positions, price_of):
    if len(open_positions) < 2:
        return {"abstain": "single_position"}
    by_u = defaultdict(float)
    for p in open_positions:
        v, reliable = _exposure_value(
            p["tradingsymbol"], p["exchange"] or EXCHANGE,
            price_of(p), p["qty"])
        if not reliable:
            return {"abstain": "unresolved_contract"}
        by_u[underlying_of(p["tradingsymbol"])] += v
    if len(by_u) < 2:
        return {"abstain": "single_underlying"}
    total = sum(by_u.values())
    if total <= 0:
        return {"abstain": "zero_exposure"}
    top_u, top_v = max(by_u.items(), key=lambda kv: kv[1])
    pct = top_v / total * 100
    if pct >= 80:
        sev = "critical"
    elif pct >= 60:
        sev = "danger"
    elif pct >= 40:
        sev = "caution"
    else:
        return {"fired": False, "pct": pct, "top": top_u}
    return {"fired": True, "severity": sev, "pct": pct, "top": top_u}


# ── the walk ───────────────────────────────────────────────────────────────

def walk(capital, max_size=DEFAULT_MAX_POSITION_SIZE, collect_positions=False):
    """Chronological walk of every fill. NO daily reset - an open position that
    survives the close is still open the next morning, which is exactly what
    these three detectors are about and what the closed-round harness discards.
    """
    fills = sorted(read_fills(BOOK), key=lambda f: f["at"])
    book = OpenBook()
    last_price = {}

    oe = {"eval": 0, "fired": 0, "abstain": defaultdict(int),
          "sev": defaultdict(int), "pct": [], "all_in": 0}
    pc = {"eval": 0, "fired": 0, "abstain": defaultdict(int),
          "sev": defaultdict(int), "pct": []}
    opened_rounds = []          # (symbol, opened_at, closed_at, qty, avg)
    round_open_at = {}

    for f in fills:
        sym = f["symbol"]
        k = key_of(sym, EXCHANGE, "MIS")
        signed = f["qty"] if f["side"] == "BUY" else -f["qty"]
        px = float(f["price"])
        last_price[sym] = px

        before = book.qty[k]
        etype, newq, newavg, _ = book.apply(k, signed, px, f["at"])

        if before == 0 and newq != 0:
            round_open_at[k] = f["at"]
        if newq == 0 and k in round_open_at:
            opened_rounds.append((sym, round_open_at.pop(k), f["at"]))

        if etype not in POSITION_OPENING_FILLS:
            continue

        # ── overexposure: the symbol just filled, priced at the fill ───────
        oe["eval"] += 1
        r = overexposure_predicate(sym, EXCHANGE, px, newq, capital, max_size)
        if "abstain" in r:
            oe["abstain"][r["abstain"]] += 1
        else:
            oe["pct"].append(r["pct"])
            if r["fired"]:
                oe["fired"] += 1
                oe["sev"][r["severity"]] += 1
                oe["all_in"] += int(r["all_in"])

        # ── concentration: the whole open book ────────────────────────────
        pc["eval"] += 1
        openpos = book.open_positions()
        c = concentration_predicate(
            openpos,
            lambda p: last_price.get(p["tradingsymbol"],
                                     float(p["avg_entry_price"] or 0)))
        if "abstain" in c:
            pc["abstain"][c["abstain"]] += 1
        else:
            pc["pct"].append(c["pct"])
            if c["fired"]:
                pc["fired"] += 1
                pc["sev"][c["severity"]] += 1

    leftover = book.open_positions()
    return oe, pc, opened_rounds, leftover, len(fills)


def pctile(xs, q):
    if not xs:
        return None
    s = sorted(xs)
    return s[min(len(s) - 1, int(len(s) * q))]


def main():
    print("=" * 78)
    print("POSITION-MONITOR MEASUREMENT")
    print("=" * 78)
    print("  harness : p28_openbook.OpenBook (V1 PASSED - 93 fills, 0 mismatches")
    print("            on entry_type / quantity / avg_entry_price)")
    print("  source  : the reference tradebook, walked chronologically with NO")
    print("            daily reset")
    print()
    print("  PRICE SUBSTITUTION - the whole reason these are reconstructions:")
    print("    both detectors read get_cached_ltp(). The tradebook has fill")
    print("    prices only. Each position is valued at its own LAST FILL price.")
    print("    For the symbol just filled that is exact at the instant of the")
    print("    fill. For every OTHER open position it is stale by however long")
    print("    since its last fill.")
    print()

    CAPITALS = [50_000, 100_000, 200_000, 500_000, 1_000_000]

    print("=" * 78)
    print("1. overexposure  -  RECONSTRUCTED, not observed")
    print("=" * 78)
    base = None
    print(f"  {'capital':>10}  {'evals':>7}  {'fired':>7}  {'rate':>7}   "
          f"{'caution':>8} {'danger':>7} {'critical':>9} {'ALL-IN':>7}")
    for cap in CAPITALS:
        oe, pc, rounds, leftover, nf = walk(cap)
        if base is None:
            base = (oe, pc, rounds, leftover, nf)
        n = oe["eval"] - sum(oe["abstain"].values())
        rate = oe["fired"] / n * 100 if n else 0
        print(f"  {cap:>10,}  {n:>7,}  {oe['fired']:>7,}  {rate:>6.1f}%   "
              f"{oe['sev']['caution']:>8} {oe['sev']['danger']:>7} "
              f"{oe['sev']['critical']:>9} {oe['all_in']:>7}")

    oe, pc, rounds, leftover, nfills = base
    print()
    print(f"  fills in book              : {nfills:,}")
    print(f"  position-opening fills     : {oe['eval']:,}")
    print(f"  abstentions                : {dict(oe['abstain'])}")
    if oe["pct"]:
        print(f"  exposure % of capital @Rs1L: "
              f"p50 {pctile(oe['pct'],0.50):.1f}  p90 {pctile(oe['pct'],0.90):.1f}  "
              f"p99 {pctile(oe['pct'],0.99):.1f}  max {max(oe['pct']):.1f}")

    print()
    print("=" * 78)
    print("2. portfolio_concentration  -  RECONSTRUCTED, not observed")
    print("=" * 78)
    n = pc["eval"] - sum(pc["abstain"].values())
    print(f"  evaluations                : {pc['eval']:,}")
    print(f"  abstentions                : {dict(pc['abstain'])}")
    print(f"  reached the ladder         : {n:,}")
    print(f"  fired                      : {pc['fired']:,}"
          f"  ({pc['fired']/n*100:.1f}% of those reached)" if n else "")
    print(f"  by severity                : {dict(pc['sev'])}")
    if pc["pct"]:
        print(f"  top-underlying share       : "
              f"p50 {pctile(pc['pct'],0.50):.1f}%  p90 {pctile(pc['pct'],0.90):.1f}%  "
              f"max {max(pc['pct']):.1f}%")
    print("  NOTE: capital-independent - it is a ratio of open exposure, so the")
    print("        numbers above do not move with trading_capital.")

    print()
    print("=" * 78)
    print("3. holding_loser  -  what CAN be established")
    print("=" * 78)
    print(f"  gate: down >= {HOLDING_LOSER_MIN_LOSS_PCT}% AND held >= "
          f"{HOLDING_LOSER_MIN_DURATION} min, re-checked up to "
          f"{MAX_HOLDING_LOSER_CHECKS} times (4h)")
    durs = [int((c - o).total_seconds() // 60) for _, o, c in rounds]
    durs.sort()
    over = sum(1 for d in durs if d >= HOLDING_LOSER_MIN_DURATION)
    print(f"  completed rounds           : {len(durs):,}")
    if durs:
        print(f"  hold minutes               : p10 {pctile(durs,0.10)}  "
              f"p25 {pctile(durs,0.25)}  p50 {pctile(durs,0.50)}  "
              f"p75 {pctile(durs,0.75)}  p90 {pctile(durs,0.90)}  max {max(durs)}")
        print(f"  held >= {HOLDING_LOSER_MIN_DURATION} min             : "
              f"{over:,}  ({over/len(durs)*100:.1f}%)  <- UPPER BOUND on firings")
        for cut in (30, 60, 120, 240):
            c = sum(1 for d in durs if d >= cut)
            print(f"     >= {cut:>4} min  {c:>5,}  ({c/len(durs)*100:5.1f}%)")
    print(f"  positions left open at book end: {len(leftover)}")
    print("  The 0.5% loss test needs the price path at T+30/60/90 min.")
    print("  NOT AVAILABLE - no candles are stored. Firing rate, false-positive")
    print("  rate and outcome CANNOT be established. Stated as insufficient.")


if __name__ == "__main__":
    main()
