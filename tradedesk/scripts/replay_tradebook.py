"""
Replay a real Zerodha tradebook through the behavioural engine.

Everything else built this week proves the engine implements its thresholds.
Nothing proves the thresholds are RIGHT — ₹500 as the scratch floor, three
losses as a streak, 1.5x as escalation — because no synthetic test can. Those
numbers are somebody's judgement, and the only thing that can check them is a
real trader's real trades.

This replays your actual fills, day by day, and reports every alert the engine
would have raised, on which trade, with the numbers behind it. Then you mark it
up: fair, or wrong. A false-positive rate on your own trading is worth more than
every scenario in the suite.

    python tradedesk/scripts/replay_tradebook.py path/to/tradebook.csv --capital 500000

Writes a markdown report next to the CSV. Nothing is sent anywhere; the trades
land in the desk's synthetic account and `--wipe` removes them.

TWO ASSUMPTIONS, STATED because they affect what fires:

  **Product.** The Console tradebook has no MIS/NRML column. A symbol whose
  fills net to zero within one day is replayed as MIS, anything carried
  overnight as NRML. That is a good inference and it is still an inference —
  the intraday square-off detectors depend on it.

  **Order type.** There is no column for it, so `no_stoploss` cannot be judged
  from a tradebook at all. Its verdicts here mean nothing and are excluded from
  the report rather than left to look like findings.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from alertlab.runner.harness import (                       # noqa: E402
    DESK, IST, ensure_lab_account, frozen_clock, lab_environment, quiet_logs,
    teardown_lab, use_identity,
)
from alertlab.runner.collect import collect_alerts, collect_positions  # noqa: E402
from alertlab.runner.inject import Fill, inject             # noqa: E402

use_identity(DESK)

#: Judged from a tradebook alone, these mean nothing — the export carries no
#: order type, so "no stop-loss on record" only ever means "no record".
UNJUDGEABLE = {"no_stoploss"}


def _db():
    from app.core.database import SessionLocal
    quiet_logs()
    return SessionLocal


def read_fills(path: Path):
    """Parse the Console export into fills, oldest first."""
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            try:
                when = datetime.fromisoformat(r["order_execution_time"]).replace(tzinfo=IST)
                rows.append({
                    "symbol": (r["symbol"] or "").strip().upper(),
                    "side": "BUY" if (r["trade_type"] or "").lower().startswith("b") else "SELL",
                    "qty": int(float(r["quantity"])),
                    "price": float(r["price"]),
                    "at": when,
                    "date": when.date(),
                    "exchange": "NFO" if (r.get("segment") or "").upper() == "FO"
                                else (r.get("exchange") or "NSE").strip().upper(),
                    "order_id": (r.get("order_id") or "").strip() or None,
                })
            except (KeyError, ValueError, TypeError):
                continue        # a malformed row must not stop the replay
    rows.sort(key=lambda x: x["at"])
    return rows


def infer_products(day_rows):
    """
    MIS if the symbol went flat within the day, NRML if it was carried.

    The export has no product column and the intraday detectors depend on one,
    so this is inferred rather than guessed at random — but it is still an
    inference and the report says so.
    """
    net = defaultdict(int)
    for r in day_rows:
        net[r["symbol"]] += r["qty"] if r["side"] == "BUY" else -r["qty"]
    return {sym: ("MIS" if qty == 0 else "NRML") for sym, qty in net.items()}


async def replay_day(day, rows, capital):
    factory = _db()
    async with factory() as db:
        await teardown_lab(db)
        await ensure_lab_account(db, capital=capital)

    products = infer_products(rows)
    with lab_environment(None):
        for r in rows:
            fill = Fill(symbol=r["symbol"], side=r["side"], qty=r["qty"],
                        price=r["price"], at=r["at"], exchange=r["exchange"],
                        product=products.get(r["symbol"], "NRML"),
                        order_id=r["order_id"])
            with frozen_clock(r["at"]):
                await inject(fill)

    async with factory() as db:
        alerts = await collect_alerts(db)
        positions = await collect_positions(db)
    return alerts, positions


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", type=Path)
    ap.add_argument("--capital", type=float, required=True,
                    help="your trading capital — most rules are a share of it")
    ap.add_argument("--days", type=int, default=0, help="replay only the last N days")
    ap.add_argument("--wipe", action="store_true", help="delete the synthetic rows and exit")
    args = ap.parse_args()

    if args.wipe:
        async with _db()() as db:
            print(await teardown_lab(db))
        return 0

    fills = read_fills(args.csv)
    if not fills:
        print("No usable rows. Expected a Zerodha Console tradebook export.", file=sys.stderr)
        return 2

    by_day = defaultdict(list)
    for f in fills:
        by_day[f["date"]].append(f)
    days = sorted(by_day)
    if args.days:
        days = days[-args.days:]

    print(f"{len(fills)} fills across {len(by_day)} sessions; replaying {len(days)}.\n")

    report, totals, session_rows = [], defaultdict(int), []
    for i, day in enumerate(days, 1):
        alerts, positions = await replay_day(day, by_day[day], args.capital)
        judged = [a for a in alerts if a["pattern_type"] not in UNJUDGEABLE]
        pnl = round(sum(c["pnl"] for c in positions["closed"]), 2)
        for a in judged:
            totals[a["pattern_type"]] += 1
        session_rows.append((day, len(by_day[day]), len(positions["closed"]), pnl, len(judged)))
        print(f"  [{i}/{len(days)}] {day}  {len(by_day[day]):>3} fills  "
              f"{len(positions['closed']):>3} trades  P&L {pnl:>12,.0f}  "
              f"{len(judged)} alert(s)", flush=True)

        if judged:
            report.append(f"\n## {day} — P&L ₹{pnl:,.0f}, {len(judged)} alert(s)\n")
            for a in judged:
                report.append(
                    f"- **{a['severity']}** · {a['label']} · {a['detected_at_ist']}  \n"
                    f"  {a['message']}  \n"
                    f"  `fair / wrong:` \n"
                )

    out = args.csv.with_name(args.csv.stem + "-replay.md")
    header = [
        "# Tradebook replay\n",
        f"\n{len(fills)} fills · {len(days)} sessions · capital ₹{args.capital:,.0f}\n",
        "\nMark each alert `fair` or `wrong`. A pattern with several `wrong` marks "
        "has a threshold problem, not a code problem.\n",
        "\n> Product (MIS/NRML) is inferred: flat by end of day = MIS, carried = NRML. "
        "The export has no product column.  \n"
        "> `no_stoploss` is excluded — the export has no order type, so it can only "
        "ever mean \"no record\".\n",
        "\n## Sessions\n\n| Date | Fills | Trades | P&L | Alerts |\n|---|---|---|---|---|\n",
    ]
    header += [f"| {d} | {f} | {t} | ₹{p:,.0f} | {a} |\n" for d, f, t, p, a in session_rows]
    header += ["\n## Alerts by pattern\n\n| Pattern | Count | Per session |\n|---|---|---|\n"]
    header += [f"| {k} | {v} | {v / len(days):.2f} |\n"
               for k, v in sorted(totals.items(), key=lambda kv: -kv[1])]

    out.write_text("".join(header) + "".join(report), encoding="utf-8")

    total_alerts = sum(totals.values())
    print(f"\n{total_alerts} alerts across {len(days)} sessions "
          f"({total_alerts / len(days):.1f} per session)")
    print(f"Report: {out}")
    print("\nMark each alert fair or wrong, then send it back.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
