"""
Open-position-book harness for the position-monitor review (overexposure,
portfolio_concentration, holding_loser).

WHY THIS EXISTS. The closed-round CSV harness that carried the last twelve
pattern reviews reconstructs `CompletedTrade` rounds. These three detectors fire
on OPEN positions, priced from the Redis LTP cache. Forcing the closed-round
methodology onto them would produce false zeros - the artefact that made
`time_of_day_bias` look like it had never fired.

THE ONE DESIGN RULE. This harness does NOT reimplement the position state
machine. It calls `position_ledger_service._compute_fill_effect`, the pure,
no-DB function production uses for every fill. Anything the harness computes
itself is a place it can silently disagree with production, so it computes as
little as possible.

VALIDATION BEFORE USE. Nothing here may be used for firing, false-positive,
false-negative or threshold analysis until this file's validation passes.

Run:
    python -u docs/patterns/_measurement/p28_openbook.py
"""
import asyncio
import logging
import sys
from collections import defaultdict
from decimal import Decimal

sys.path.insert(0, "D:/trade-psychology-ai")
sys.path.insert(0, "D:/trade-psychology-ai/backend")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

from app.services.position_ledger_service import _compute_fill_effect  # noqa: E402


# ── the position KEY ───────────────────────────────────────────────────────
# (symbol, exchange, product). Product is part of the key: the same symbol held
# in MIS and NRML at once is two independent positions and must not net (M1).
# Nullable for rows written before migration 075, and NULL groups with NULL.

def key_of(tradingsymbol, exchange, product):
    return (tradingsymbol, exchange, product)


class OpenBook:
    """The set of open positions, advanced one fill at a time.

    State per key mirrors what the detectors read off a `Position` row:
      qty              -> total_quantity        (signed; + long, - short)
      avg_price        -> average_entry_price
      round_started_at -> first entry of the CURRENT round
      last_entry_at    -> last_entry_time, what holding_loser measures from
    """

    def __init__(self):
        self.qty = defaultdict(int)
        self.avg = {}
        self.round_started_at = {}
        self.last_entry_at = {}

    def apply(self, k, fill_qty, fill_price, at):
        """Advance one fill. Returns production's entry_type and the new state."""
        cur_q = self.qty[k]
        cur_a = self.avg.get(k)

        entry_type, new_q, new_a, rpnl = _compute_fill_effect(
            cur_q, cur_a, int(fill_qty), Decimal(str(fill_price)))

        if entry_type in ("OPEN", "FLIP"):
            self.round_started_at[k] = at
        if entry_type in ("OPEN", "INCREASE", "FLIP"):
            self.last_entry_at[k] = at

        self.qty[k] = new_q
        if new_q == 0:
            self.avg.pop(k, None)
            self.round_started_at.pop(k, None)
            self.last_entry_at.pop(k, None)
        else:
            self.avg[k] = new_a

        return entry_type, new_q, new_a, rpnl

    def open_positions(self):
        """Every key with a non-zero position, as the detectors would see it."""
        return [
            {
                "key": k,
                "tradingsymbol": k[0],
                "exchange": k[1],
                "product": k[2],
                "qty": q,
                "avg_entry_price": self.avg.get(k),
                "round_started_at": self.round_started_at.get(k),
                "last_entry_at": self.last_entry_at.get(k),
            }
            for k, q in self.qty.items() if q != 0
        ]


# ── VALIDATION ─────────────────────────────────────────────────────────────
#
# Three checks, in order. Each answers a different question, and running them
# together is the only way to tell a harness bug from a production data defect.
#
#   V0  Is PRODUCTION'S OWN LEDGER self-consistent? No harness involved: a
#       running total must satisfy qty_after[i] == qty_after[i-1] + fill_qty[i].
#       A symbol that fails V0 cannot validate anything, because production
#       offers no correct answer to match.
#   V1  Does the HARNESS reproduce production state, fill by fill, on the
#       symbols that pass V0? Exact match required on entry_type, quantity and
#       average entry price - the fields the three detectors actually read.
#   V2  Does the reconstructed open book agree with the `positions` table?

PNL_TOLERANCE = Decimal("0.01")   # see the note in main(); no detector reads it


async def _load_ledger():
    from app.core.database import SessionLocal
    from sqlalchemy import text
    async with SessionLocal() as db:
        return (await db.execute(text(
            "SELECT broker_account_id, tradingsymbol, exchange, product, "
            "       entry_type, fill_qty, fill_price, "
            "       position_qty_after, avg_entry_price_after, realized_pnl, "
            "       fill_order_id, occurred_at, created_at "
            "FROM position_ledger "
            "ORDER BY broker_account_id, occurred_at, created_at"
        ))).all()


def v0_production_self_consistency(rows):
    """Production's ledger checked against itself. No harness involved."""
    by = defaultdict(list)
    for r in rows:
        by[(r[0], r[1], r[3])].append(r)

    ok, broken = set(), {}
    for k, rs in by.items():
        prev = 0
        consistent = True
        for r in rs:
            if int(r[7]) != prev + int(r[5]):
                consistent = False
                break
            prev = int(r[7])
        if consistent:
            ok.add(k)
            continue
        # Impossible under ANY ordering? Equal fill_qty at one timestamp cannot
        # produce duplicate running totals.
        ts = defaultdict(list)
        for x in rs:
            ts[x[11]].append(x)
        proof = "running total breaks"
        for t, g in ts.items():
            q = [int(x[7]) for x in g]
            if len(g) > 1 and len(set(q)) != len(q) and all(int(x[5]) for x in g):
                proof = (f"{len(g)} fills at {t}, fill_qty={[int(x[5]) for x in g]}, "
                         f"qty_after={q} - duplicate running totals are "
                         f"IMPOSSIBLE under ANY ordering")
        broken[k] = proof
    return ok, broken


def v1_harness_matches_production(rows, allowed_keys):
    books = defaultdict(OpenBook)
    checked = 0
    mism = defaultdict(list)
    pnl_resid = []

    for r in rows:
        (acct, sym, exch, prod, exp_type, fq, fp,
         exp_qty, exp_avg, exp_pnl, order_id, occurred, created) = r
        if (acct, sym, prod) not in allowed_keys:
            continue

        k = key_of(sym, exch, prod)
        got_type, got_qty, got_avg, got_pnl = books[acct].apply(
            k, fq, fp, occurred or created)
        checked += 1
        where = f"{sym}/{prod} {order_id}"

        if got_type != exp_type:
            mism["entry_type"].append(f"{where}: prod={exp_type} harness={got_type}")
        if int(got_qty) != int(exp_qty):
            mism["quantity"].append(f"{where}: prod={exp_qty} harness={got_qty}")

        e = None if exp_avg is None else Decimal(str(exp_avg))
        g = None if got_avg is None else Decimal(str(got_avg))
        if (e is None) != (g is None) or (e is not None and e.compare(g) != 0):
            mism["avg_entry_price"].append(f"{where}: prod={e} harness={g}")

        d = (Decimal(str(exp_pnl or 0)) - Decimal(str(got_pnl or 0))).copy_abs()
        if d > PNL_TOLERANCE:
            mism["realized_pnl"].append(
                f"{where}: prod={exp_pnl} harness={got_pnl} (delta {d})")
        elif d > 0:
            pnl_resid.append((where, d))

    return checked, mism, pnl_resid, books


async def v2_against_positions_table(books):
    """The reconstructed open book vs what the `positions` table says."""
    from app.core.database import SessionLocal
    from sqlalchemy import text
    pairs, stats = [], {}
    async with SessionLocal() as db:
        for acct, book in books.items():
            rows = (await db.execute(text(
                "SELECT tradingsymbol, status, total_quantity, average_entry_price, "
                "       first_entry_time, last_entry_time, last_exit_time, "
                "       instrument_token, entry_price_source "
                "FROM positions WHERE broker_account_id = :a"
            ), {"a": str(acct)})).all()
            pos = {r[0]: r for r in rows}
            for p in book.open_positions():
                pairs.append((p, pos.get(p["tradingsymbol"])))
            stats = {
                "rows": len(rows),
                "open": sum(1 for r in rows if r[1] == "open"),
                "with_token": sum(1 for r in rows if r[7] is not None),
                "with_eps": sum(1 for r in rows if r[8] is not None),
            }
    return pairs, stats


def main():
    # ONE event loop for every DB call. A second asyncio.run() reuses a pool
    # whose connections belong to the first, closed, loop.
    state = {}

    async def _everything():
        rows = await _load_ledger()
        ok, broken = v0_production_self_consistency(rows)
        checked, mism, resid, books = v1_harness_matches_production(rows, ok)
        pairs, stats = await v2_against_positions_table(books)
        state.update(rows=rows, ok=ok, broken=broken, checked=checked,
                     mism=mism, resid=resid, books=books,
                     pairs=pairs, stats=stats)

    asyncio.run(_everything())
    rows = state["rows"]
    print("=" * 78)
    print("OPEN-BOOK HARNESS VALIDATION")
    print("=" * 78)
    print(f"  production ledger rows : {len(rows)}")
    print(f"  accounts               : {len({r[0] for r in rows})}")
    print(f"  symbols                : {len({r[1] for r in rows})}")
    if not rows:
        print("\n  NO LEDGER ROWS - the harness CANNOT be validated. Stop.")
        return 1
    print(f"  window                 : {rows[0][11]}  ->  {rows[-1][11]}")

    print("\n" + "-" * 78)
    print("V0  production ledger vs ITSELF (no harness involved)")
    print("-" * 78)
    ok, broken = state['ok'], state['broken']
    print(f"  self-consistent  : {len(ok)}")
    print(f"  NOT consistent   : {len(broken)}")
    for k, why in broken.items():
        print(f"     {k[1]}/{k[2]}")
        print(f"       {why}")
    if broken:
        print("\n  EXCLUDED from V1: production offers no correct answer to match,")
        print("  so these can neither validate nor invalidate a harness.")

    print("\n" + "-" * 78)
    print("V1  harness vs production, fill by fill, on the self-consistent set")
    print("-" * 78)
    checked, mism, resid = state['checked'], state['mism'], state['resid']
    print(f"  fills replayed   : {checked}")
    hard = ("entry_type", "quantity", "avg_entry_price")
    for f in hard + ("realized_pnl",):
        items = mism.get(f, [])
        print(f"  {'OK  ' if not items else 'FAIL'} {f:18s} {len(items)} mismatches")
        for line in items[:5]:
            print(f"        {line}")
    if resid:
        print(f"\n  realized_pnl residuals within +/-{PNL_TOLERANCE}: {len(resid)}")
        for w, d in resid[:5]:
            print(f"        {w}: delta {d}")
        print("  Cause: a ledger row can aggregate several exchange fills - P&L")
        print("  summed at true prices, fill_price stored as the rounded average -")
        print("  so no single-price recomputation reproduces it exactly.")
        print("  NONE of the three detectors reads realized_pnl.")

    et = defaultdict(int)
    for r in rows:
        et[r[4]] += 1
    print(f"\n  entry types exercised : {dict(et)}")
    missing = {"OPEN", "INCREASE", "DECREASE", "CLOSE", "FLIP"} - set(et)
    if missing:
        print(f"  NOT exercised         : {sorted(missing)}  <- UNTESTED paths")

    print("\n" + "-" * 78)
    print("V2  reconstructed open book vs the `positions` table")
    print("-" * 78)
    pairs, stats = state['pairs'], state['stats']
    print(f"  positions rows {stats['rows']} | status=open {stats['open']} | "
          f"instrument_token {stats['with_token']} | entry_price_source {stats['with_eps']}")
    print(f"  ledger says still open at the end: {len(pairs)}")
    for p, row in pairs:
        st = "MISSING" if row is None else f"status={row[1]} qty={row[2]} last_exit={row[6]}"
        print(f"     {p['tradingsymbol']:26s} ledger qty={p['qty']:>6d} "
              f"avg={p['avg_entry_price']}  |  {st}")

    fatal = sum(len(mism.get(f, [])) for f in hard)
    print("\n" + "=" * 78)
    if fatal == 0 and checked:
        print(f"  V1 PASSED - entry_type, quantity and average entry price match")
        print(f"  production EXACTLY on all {checked} replayed fills.")
        print("  Scope limits above MUST be carried into any measurement made here.")
        print("=" * 78)
        return 0
    print(f"  NOT VALIDATED - {fatal} mismatches on fields the detectors read.")
    print("=" * 78)
    return 1


if __name__ == "__main__":
    sys.exit(main())
