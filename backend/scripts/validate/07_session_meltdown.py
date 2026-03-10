"""
Script 07: Session Meltdown → session_meltdown alert (shadow)

Pushes session loss past 80% of daily limit.
Requires daily_loss_limit set in Settings → Trading Limits.

Usage:
    cd backend
    python scripts/validate/07_session_meltdown.py
"""

import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scenario_utils import (
    get_broker_account_id, get_connection,
    insert_completed_trade, insert_trade, trigger_detection,
    print_banner, print_expect, print_check, print_done,
)


async def main():
    print_banner(7, "Session Meltdown — crossing daily loss limit")

    broker_account_id = await get_broker_account_id()

    # Check profile for daily_loss_limit
    conn = await get_connection()
    try:
        row = await conn.fetchrow(
            "SELECT daily_loss_limit, trading_capital FROM user_profiles WHERE broker_account_id = $1",
            broker_account_id
        )

        daily_loss_limit = None
        if row:
            daily_loss_limit = row['daily_loss_limit'] or (
                float(row['trading_capital']) * 0.05 if row['trading_capital'] else None
            )

        if not daily_loss_limit:
            print("\n⚠️   No daily_loss_limit or trading_capital set.")
            print("    Set in Settings → Trading Limits, then re-run.")
            await conn.close()
            return

        current_loss = 27605  # approximate from previous scripts
        target = float(daily_loss_limit) * 0.85
        extra_loss = max(1000, target - current_loss)

        print(f"\n    daily_loss_limit: ₹{daily_loss_limit:,.0f}")
        print(f"    current session loss: ~₹{current_loss:,.0f}")
        print(f"    inserting extra loss: ₹{extra_loss:,.0f}")

        await insert_completed_trade(
            conn, broker_account_id,
            symbol="BANKNIFTY25APRFUT", exchange="NFO",
            instrument_type="FUT", direction="LONG",
            qty=25, avg_entry=48000.0, avg_exit=48000.0 - (extra_loss / 25),
            pnl=-extra_loss,
            entry_offset_min=-2, duration_min=1,
        )
        await insert_trade(
            conn, broker_account_id,
            symbol="BANKNIFTY25APRFUT", exchange="NFO",
            transaction_type="SELL", qty=25,
            price=48000.0 - (extra_loss / 25), pnl=-extra_loss,
            offset_min=-1,
        )
    finally:
        await conn.close()

    await trigger_detection(broker_account_id)
    print_done(f"BANKNIFTY LONG → loss ₹{extra_loss:,.0f} (session meltdown triggered)")
    print()
    print("━" * 60)
    print_expect("🚨  session_meltdown (shadow_behavioral_events)")
    print("━" * 60)
    print_check("Backend logs: [shadow] session_meltdown event")
    print_check("Supabase: SELECT event_type, behavior_state, message")
    print_check("         FROM shadow_behavioral_events ORDER BY detected_at DESC LIMIT 10")
    print()
    print("━" * 60)
    print("  SCENARIO COMPLETE")
    print("━" * 60)
    print()
    print("When done observing:")
    print("→  Run: python scripts/validate/cleanup.py")


if __name__ == "__main__":
    asyncio.run(main())
