"""
Script 06: Size Escalation → size_escalation + DANGER alert

Doubles position size after 8 consecutive losses.

Usage:
    cd backend
    python scripts/validate/06_size_escalation.py
"""

import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scenario_utils import (
    get_broker_account_id, get_connection,
    insert_completed_trade, insert_trade, trigger_detection,
    print_banner, print_expect, print_check, print_wait, print_done,
)


async def main():
    print_banner(6, "Size Escalation — doubling position to recover losses")

    broker_account_id = await get_broker_account_id()

    conn = await get_connection()
    try:
        await insert_completed_trade(
            conn, broker_account_id,
            symbol="NIFTY25APRFUT", exchange="NFO",
            instrument_type="FUT", direction="LONG",
            qty=100,  # doubled from previous 50
            avg_entry=21860.0, avg_exit=21760.0, pnl=-10000.0,
            entry_offset_min=-3, duration_min=2,
        )
        await insert_trade(
            conn, broker_account_id,
            symbol="NIFTY25APRFUT", exchange="NFO",
            transaction_type="SELL", qty=100, price=21760.0, pnl=-10000.0,
            offset_min=-1,
        )
    finally:
        await conn.close()

    await trigger_detection(broker_account_id)
    print_done("NIFTY LONG 100-lot → loss ₹10,000 (doubled size, 9th consecutive loss)")
    print()
    print("━" * 60)
    print_expect("🚨🚨  DANGER: consecutive_loss + size_escalation (shadow)")
    print("━" * 60)
    print_check("Dashboard → Alerts: DANGER badge (red)")
    print_check("Push notification should arrive on your device")
    print_check("Backend logs: [shadow] multiple HIGH events, risk_score high")
    total = 2500 + 3495 + 4200 + 2500 + 1005 + 1700 + 1005 + 1700 + 10000
    print(f"\n    Session loss now: ~₹{total:,.0f}")
    print_wait(2, "before session meltdown test")
    print("\n→  Next: python scripts/validate/07_session_meltdown.py")


if __name__ == "__main__":
    asyncio.run(main())
