"""
Script 01: Opening Loss

Scenario: NIFTY LONG trade, entered at market open, stopped out.
A normal loss — no alerts should fire yet.

Expected alerts: NONE
What to check: Dashboard shows the completed trade in history.
               No alerts in the alerts panel.

Wait before next script: 2 minutes (simulate thinking time)

Usage:
    cd backend
    python scripts/validate/01_opening_loss.py
"""

import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scenario_utils import *
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def main():
    print_banner(1, "Opening Loss — NIFTY LONG stopped out")

    broker_account_id = await get_broker_account_id()
    engine = make_engine()
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as db:
        # Trade: BUY NIFTY 50 @ 22,050, exit @ 22,000 → loss ₹2,500
        ct = await insert_completed_trade(
            db, broker_account_id,
            symbol="NIFTY25APRFUT",
            exchange="NFO",
            instrument_type="FUT",
            direction="LONG",
            qty=50,
            avg_entry=22050.0,
            avg_exit=22000.0,
            pnl=-2500.0,
            entry_offset_min=-25,
            duration_min=20,
        )
        await insert_trade(
            db, broker_account_id,
            symbol="NIFTY25APRFUT",
            exchange="NFO",
            transaction_type="SELL",   # closing fill
            qty=50,
            price=22000.0,
            pnl=-2500.0,
            offset_min=-5,
        )
        await db.commit()

    await engine.dispose()

    print_done("NIFTY LONG → stopped out, loss ₹2,500 (1 consecutive loss)")
    print_expect("NO alerts — single loss is normal, below threshold")
    print_check("Dashboard → Closed Trades: should show this trade")
    print_check("Alerts panel: should be empty (or only pre-existing alerts)")
    print_check("Backend logs: no [shadow] events")
    print_wait(2, "simulate thinking time before next trade")
    print("\n→  Next: python scripts/validate/02_second_loss.py")


if __name__ == "__main__":
    asyncio.run(main())
