"""
Script 03: Third Consecutive Loss → CAUTION alert fires

Usage:
    cd backend
    python scripts/validate/03_third_loss_caution.py
"""

import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scenario_utils import (
    get_broker_account_id, get_connection,
    insert_completed_trade, insert_trade, trigger_detection,
    print_banner, print_expect, print_check, print_wait, print_done,
)


async def main():
    print_banner(3, "Third Loss → CAUTION alert fires")

    broker_account_id = await get_broker_account_id()

    conn = await get_connection()
    try:
        await insert_completed_trade(
            conn, broker_account_id,
            symbol="NIFTY25APRFUT", exchange="NFO",
            instrument_type="FUT", direction="LONG",
            qty=50, avg_entry=22020.0, avg_exit=21936.0, pnl=-4200.0,
            entry_offset_min=-10, duration_min=7,
        )
        await insert_trade(
            conn, broker_account_id,
            symbol="NIFTY25APRFUT", exchange="NFO",
            transaction_type="SELL", qty=50, price=21936.0, pnl=-4200.0,
            offset_min=-3,
        )
    finally:
        await conn.close()

    await trigger_detection(broker_account_id)
    print_done("NIFTY LONG → stopped out, loss ₹4,200 (3 consecutive losses)")
    print()
    print("━" * 60)
    print_expect("🚨  consecutive_loss alert (CAUTION level)")
    print("━" * 60)
    print_check("Dashboard → Alerts panel: NEW caution alert should appear")
    print_check("Backend logs: 'Risk detection: 1 new alerts'")
    print()
    print("⏱️   REVENGE WINDOW = 10 minutes from now.")
    print("    Run Script 04 within 10 minutes to trigger revenge_trade.")
    print_wait(3, "observe the alert, then run Script 04 within 10 min")
    print("\n→  Next: python scripts/validate/04_revenge_entry.py")


if __name__ == "__main__":
    asyncio.run(main())
