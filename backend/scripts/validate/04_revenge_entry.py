"""
Script 04: Revenge Trade → revenge_trade alert fires

⚠️  RUN WITHIN 10 MINUTES OF SCRIPT 03.

Usage:
    cd backend
    python scripts/validate/04_revenge_entry.py
"""

import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scenario_utils import (
    get_broker_account_id, get_connection,
    insert_completed_trade, insert_trade, trigger_detection,
    print_banner, print_expect, print_check, print_wait, print_done,
)


async def main():
    print_banner(4, "Revenge Entry — NIFTY again, 4 minutes after last loss")

    broker_account_id = await get_broker_account_id()

    conn = await get_connection()
    try:
        await insert_completed_trade(
            conn, broker_account_id,
            symbol="NIFTY25APRFUT", exchange="NFO",
            instrument_type="FUT", direction="LONG",
            qty=50, avg_entry=21950.0, avg_exit=21900.0, pnl=-2500.0,
            entry_offset_min=-4, duration_min=3,
        )
        await insert_trade(
            conn, broker_account_id,
            symbol="NIFTY25APRFUT", exchange="NFO",
            transaction_type="SELL", qty=50, price=21900.0, pnl=-2500.0,
            offset_min=-1,
        )
    finally:
        await conn.close()

    await trigger_detection(broker_account_id)
    print_done("NIFTY LONG → loss ₹2,500 entered 4 minutes after last loss")
    print()
    print("━" * 60)
    print_expect("🚨  revenge_trade (shadow) + 4th consecutive loss")
    print("━" * 60)
    print_check("Dashboard → Alerts panel: consecutive_loss now at 4 (may hit DANGER if threshold=5)")
    print_check("Backend logs: [shadow] revenge_trade event")
    print_wait(1, "prepare for overtrading burst")
    print("\n→  Next: python scripts/validate/05_overtrading_burst.py")


if __name__ == "__main__":
    asyncio.run(main())
