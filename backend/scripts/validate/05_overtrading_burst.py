"""
Script 05: Overtrading Burst → OVERTRADING_BURST Alert

Scenario: Trader places 4 more trades in rapid succession (all within 15 min).
Combined with the previous trades, this hits the overtrading threshold.

Default threshold: 6 trades per 15 min (burst_trades_per_15min).
We now have 4 trades from scripts 01-04 + 4 more = 8 in 30 min → burst alert.

Expected alerts:
  PRODUCTION (RiskDetector):  overtrading (caution or danger)
  SHADOW (BehaviorEngine):    overtrading_burst

What to check:
  Dashboard → Alerts: overtrading alert
  Backend logs: [shadow] overtrading_burst, trades_in_window count

Wait before next script: 2 minutes

Usage:
    cd backend
    python scripts/validate/05_overtrading_burst.py
"""

import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scenario_utils import *
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def main():
    print_banner(5, "Overtrading Burst — 4 rapid trades in succession")

    broker_account_id = await get_broker_account_id()
    engine = make_engine()
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Insert 4 rapid trades, each 2 minutes apart, all small
    rapid_trades = [
        ("BANKNIFTY25APRFUT", 15, 48000.0, 47933.0, -1005.0, -14, 2),
        ("NIFTY25APRFUT",     50, 21910.0, 21876.0, -1700.0, -11, 2),
        ("BANKNIFTY25APRFUT", 15, 47950.0, 47883.0, -1005.0,  -8, 2),
        ("NIFTY25APRFUT",     50, 21880.0, 21846.0, -1700.0,  -5, 2),
    ]

    async with Session() as db:
        for i, (sym, qty, entry, exit_p, pnl, offset, dur) in enumerate(rapid_trades, 1):
            await insert_completed_trade(
                db, broker_account_id,
                symbol=sym,
                exchange="NFO",
                instrument_type="FUT",
                direction="LONG",
                qty=qty,
                avg_entry=entry,
                avg_exit=exit_p,
                pnl=pnl,
                entry_offset_min=offset,
                duration_min=dur,
            )
            await insert_trade(
                db, broker_account_id,
                symbol=sym,
                exchange="NFO",
                transaction_type="SELL",
                qty=qty,
                price=exit_p,
                pnl=pnl,
                offset_min=offset + dur,
            )
            print(f"   Inserted rapid trade {i}/4: {sym} loss ₹{abs(pnl):,.0f}")

        await db.commit()

    await engine.dispose()

    print()
    print_done("4 rapid trades inserted (8 total in ~30 min window)")
    print()
    print("━" * 60)
    print_expect("🚨  overtrading_burst alert")
    print("    Shadow: '8 trades in 30 minutes. Overtrading burst.'")
    print("━" * 60)
    print_check("Dashboard → Alerts: overtrading alert")
    print_check("Backend logs: [shadow] overtrading_burst, trades_in_window=8")
    print_check("Session P&L is now very negative — check the dashboard P&L card")
    print()
    print(f"Total session loss so far: ~₹{2500+3495+4200+2500+1005+1700+1005+1700:,.0f}")
    print_wait(2, "before size escalation test")
    print("\n→  Next: python scripts/validate/06_size_escalation.py")


if __name__ == "__main__":
    asyncio.run(main())
