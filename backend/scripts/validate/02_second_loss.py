"""
Script 02: Second Consecutive Loss

BANKNIFTY LONG, another loss. 2 in a row — still below caution threshold.

Usage:
    cd backend
    python scripts/validate/02_second_loss.py
"""

import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scenario_utils import (
    get_broker_account_id, get_connection,
    insert_completed_trade, insert_trade,
    print_banner, print_expect, print_check, print_wait, print_done,
)


async def main():
    print_banner(2, "Second Loss — BANKNIFTY LONG stopped out")

    broker_account_id = await get_broker_account_id()

    conn = await get_connection()
    try:
        await insert_completed_trade(
            conn, broker_account_id,
            symbol="BANKNIFTY25APRFUT", exchange="NFO",
            instrument_type="FUT", direction="LONG",
            qty=15, avg_entry=48200.0, avg_exit=47967.0, pnl=-3495.0,
            entry_offset_min=-18, duration_min=12,
        )
        await insert_trade(
            conn, broker_account_id,
            symbol="BANKNIFTY25APRFUT", exchange="NFO",
            transaction_type="SELL", qty=15, price=47967.0, pnl=-3495.0,
            offset_min=-6,
        )
    finally:
        await conn.close()

    print_done("BANKNIFTY LONG → stopped out, loss ₹3,495 (2 consecutive losses)")
    print_expect("NO alerts — 2 consecutive losses, below caution threshold of 3")
    print_check("Dashboard → Closed Trades: should show 2 losing trades now")
    print_wait(2, "before triggering the caution threshold")
    print("\n→  Next: python scripts/validate/03_third_loss_caution.py")


if __name__ == "__main__":
    asyncio.run(main())
