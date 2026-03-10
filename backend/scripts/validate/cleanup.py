"""
Cleanup: Delete all validation scenario test data.

Usage:
    cd backend
    python scripts/validate/cleanup.py
"""

import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scenario_utils import get_broker_account_id, get_connection, TEST_TAG


async def main():
    print("\n" + "=" * 60)
    print("  Cleanup: Deleting validation test data")
    print("=" * 60)

    confirm = input("\nDelete all TEST_SCENARIO data? (yes/no): ")
    if confirm.lower() != "yes":
        print("Cancelled.")
        return

    broker_account_id = await get_broker_account_id()
    conn = await get_connection()

    try:
        # 1. Delete test Trade records (by tag)
        result = await conn.execute(
            "DELETE FROM trades WHERE tag = $1 AND broker_account_id = $2",
            TEST_TAG, broker_account_id
        )
        print(f"✅  Deleted test Trade records: {result.split()[-1]}")

        # 2. Delete test CompletedTrade records (by symbol + today's date)
        result = await conn.execute(
            """
            DELETE FROM completed_trades
            WHERE broker_account_id = $1
              AND tradingsymbol IN ('NIFTY25APRFUT', 'BANKNIFTY25APRFUT')
              AND created_at >= now() - interval '7 days'
            """,
            broker_account_id
        )
        print(f"✅  Deleted test CompletedTrade records: {result.split()[-1]}")

        # 3. Delete shadow events from last 7 days
        result = await conn.execute(
            """
            DELETE FROM shadow_behavioral_events
            WHERE broker_account_id = $1
              AND created_at >= now() - interval '7 days'
            """,
            broker_account_id
        )
        print(f"✅  Deleted shadow_behavioral_events: {result.split()[-1]}")

        # 4. Delete test risk_alerts from last 7 days
        result = await conn.execute(
            """
            DELETE FROM risk_alerts
            WHERE broker_account_id = $1
              AND detected_at >= now() - interval '7 days'
              AND (
                message ILIKE '%consecutive%' OR
                message ILIKE '%revenge%' OR
                message ILIKE '%overtrading%' OR
                message ILIKE '%TEST%'
              )
            """,
            broker_account_id
        )
        print(f"✅  Deleted test risk_alerts: {result.split()[-1]}")

        # 5. Delete test trading_sessions from last 7 days
        result = await conn.execute(
            """
            DELETE FROM trading_sessions
            WHERE broker_account_id = $1
              AND created_at >= now() - interval '7 days'
            """,
            broker_account_id
        )
        print(f"✅  Deleted test TradingSessions: {result.split()[-1]}")

    finally:
        await conn.close()

    print("\n✅  Cleanup complete. Real trade history untouched.")


if __name__ == "__main__":
    asyncio.run(main())
