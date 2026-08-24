"""Does the replay actually write position_ledger? Run one day and count."""
import asyncio, sys
from collections import defaultdict
sys.path.insert(0, "D:/trade-psychology-ai")
sys.path.insert(0, "D:/trade-psychology-ai/backend")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from sqlalchemy import select

NO_RULES = dict(daily_loss_limit=None, daily_trade_limit=None, max_position_size=None,
                max_consecutive_losses=None, cooldown_after_loss=0)

async def main():
    from tradedesk.scripts.replay_tradebook import read_fills, _replay_day_once
    from app.core.database import SessionLocal
    from app.models.broker_account import BrokerAccount
    from app.models.position_ledger import PositionLedger
    from app.models.completed_trade import CompletedTrade

    fills = read_fills("D:/trade-psychology-ai/docs/tradebook-CY6001-FO2025-26.csv")
    by_day = defaultdict(list)
    for f in fills:
        by_day[f["date"]].append(f)
    # a day known to contain a multi-fill averaging-down position
    from datetime import date
    day = date(2025, 11, 25)
    rows = by_day[day]
    print(f"replaying {day}: {len(rows)} fills")
    await _replay_day_once(day, rows, 50000.0, NO_RULES)

    async with SessionLocal() as db:
        ids = (await db.execute(select(BrokerAccount.id).where(
            BrokerAccount.broker_name == "synthetic"))).scalars().all()
        led = list((await db.execute(
            select(PositionLedger).where(PositionLedger.broker_account_id.in_(ids))
            .order_by(PositionLedger.occurred_at))).scalars())
        cts = list((await db.execute(
            select(CompletedTrade).where(CompletedTrade.broker_account_id.in_(ids)))).scalars())

    print(f"\nposition_ledger rows written: {len(led)}")
    print(f"completed_trades written:      {len(cts)}")
    if not led:
        print("\n>>> LEDGER EMPTY - the replay cannot validate a fill-level detector")
        return
    print("\nledger for the averaging-down position:")
    for r in led:
        if "26000CE" in (r.tradingsymbol or ""):
            print(f"  {r.occurred_at:%H:%M:%S} {r.tradingsymbol:<22} {r.entry_type:<6} "
                  f"qty {r.fill_qty:>+6} @ {float(r.fill_price):>8.2f}  "
                  f"pos_after {r.position_qty_after:>6}  avg_after "
                  f"{float(r.avg_entry_price_after or 0):>8.2f}")
    print("\nfields needed by the contract, present on every row:")
    r = led[0]
    for f in ("fill_qty", "fill_price", "position_qty_after",
              "avg_entry_price_after", "occurred_at", "entry_type"):
        print(f"  {f:<24} {getattr(r, f)!r}")

asyncio.run(main())
