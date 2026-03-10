"""
Script 05: Overtrading Burst → overtrading_burst alert fires

4 more rapid trades in 15 minutes — 8 total in the session.

Usage:
    cd backend
    python scripts/validate/05_overtrading_burst.py
"""

import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scenario_utils import (
    get_broker_account_id, get_connection,
    insert_completed_trade, insert_trade, trigger_detection,
    print_banner, print_expect, print_check, print_wait, print_done,
)


async def main():
    print_banner(5, "Overtrading Burst — 4 rapid trades in succession")

    broker_account_id = await get_broker_account_id()

    rapid = [
        ("BANKNIFTY25APRFUT", 15, 48000.0, 47933.0, -1005.0, -14, 2),
        ("NIFTY25APRFUT",     50, 21910.0, 21876.0, -1700.0, -11, 2),
        ("BANKNIFTY25APRFUT", 15, 47950.0, 47883.0, -1005.0,  -8, 2),
        ("NIFTY25APRFUT",     50, 21880.0, 21846.0, -1700.0,  -5, 2),
    ]

    conn = await get_connection()
    try:
        for i, (sym, qty, entry, exit_p, pnl, offset, dur) in enumerate(rapid, 1):
            print(f"\n  Inserting rapid trade {i}/4:")
            await insert_completed_trade(
                conn, broker_account_id,
                symbol=sym, exchange="NFO",
                instrument_type="FUT", direction="LONG",
                qty=qty, avg_entry=entry, avg_exit=exit_p, pnl=pnl,
                entry_offset_min=offset, duration_min=dur,
            )
            await insert_trade(
                conn, broker_account_id,
                symbol=sym, exchange="NFO",
                transaction_type="SELL", qty=qty, price=exit_p, pnl=pnl,
                offset_min=offset + dur,
            )
    finally:
        await conn.close()

    await trigger_detection(broker_account_id)
    print_done("4 rapid trades inserted (8 total in ~30 min window)")
    print()
    print("━" * 60)
    print_expect("🚨  overtrading_burst (shadow) + consecutive_loss DANGER")
    print("━" * 60)
    print_check("Dashboard → Alerts: DANGER level alert (if streak >= 5)")
    print_check("Backend logs: [shadow] overtrading_burst, trades_in_window=8")
    total = 2500 + 3495 + 4200 + 2500 + 1005 + 1700 + 1005 + 1700
    print(f"\n    Session loss so far: ~₹{total:,.0f}")
    print_wait(2, "before size escalation")
    print("\n→  Next: python scripts/validate/06_size_escalation.py")


if __name__ == "__main__":
    asyncio.run(main())
