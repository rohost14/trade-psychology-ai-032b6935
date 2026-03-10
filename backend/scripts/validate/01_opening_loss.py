"""
Script 01: Opening Loss

NIFTY LONG trade, stopped out. Single loss — no alerts should fire.

Usage:
    cd backend
    python scripts/validate/01_opening_loss.py
"""

import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scenario_utils import (
    get_broker_account_id, get_connection,
    insert_completed_trade, insert_trade, trigger_detection,
    print_banner, print_expect, print_check, print_wait, print_done,
)


async def main():
    print_banner(1, "Opening Loss — NIFTY LONG stopped out")

    broker_account_id = await get_broker_account_id()

    conn = await get_connection()
    try:
        await insert_completed_trade(
            conn, broker_account_id,
            symbol="NIFTY25APRFUT", exchange="NFO",
            instrument_type="FUT", direction="LONG",
            qty=50, avg_entry=22050.0, avg_exit=22000.0, pnl=-2500.0,
            entry_offset_min=-25, duration_min=20,
        )
        await insert_trade(
            conn, broker_account_id,
            symbol="NIFTY25APRFUT", exchange="NFO",
            transaction_type="SELL", qty=50, price=22000.0, pnl=-2500.0,
            offset_min=-5,
        )
    finally:
        await conn.close()

    await trigger_detection(broker_account_id)
    print_done("NIFTY LONG → stopped out, loss ₹2,500 (1 consecutive loss)")
    print_expect("NO alerts — single loss is below threshold")
    print_check("Dashboard → Closed Trades tab: should show this trade")
    print_check("Alerts panel: empty (or only pre-existing alerts)")
    print_wait(2)
    print("\n→  Next: python scripts/validate/02_second_loss.py")


if __name__ == "__main__":
    asyncio.run(main())
