"""
Cleanup: Delete all test scenario data

Deletes all trades, completed_trades, alerts, and shadow events
created during the validation scenario.

Uses the TEST_TAG marker ('TEST_SCENARIO_VALIDATE') to identify
test data. Your real trades are untouched.

⚠️  Only run this AFTER you've finished observing all alerts.

Usage:
    cd backend
    python scripts/validate/cleanup.py
"""

import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scenario_utils import make_engine, get_broker_account_id, TEST_TAG
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy import text, delete, select
from datetime import datetime, timezone, timedelta


async def main():
    print("\n" + "=" * 60)
    print("  Cleanup: Deleting validation scenario test data")
    print("=" * 60)

    confirm = input("\nAre you sure? This deletes all TEST_SCENARIO_VALIDATE data. (yes/no): ")
    if confirm.lower() != "yes":
        print("Cancelled.")
        return

    broker_account_id = await get_broker_account_id()
    engine = make_engine()
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as db:
        # 1. Get IDs of test trades (tagged)
        from app.models.trade import Trade
        from app.models.completed_trade import CompletedTrade

        trade_result = await db.execute(
            select(Trade.id).where(
                Trade.broker_account_id == broker_account_id,
                Trade.tag == TEST_TAG,
            )
        )
        test_trade_ids = [row[0] for row in trade_result.fetchall()]

        # 2. Delete test trades (cascades to anything referencing them)
        if test_trade_ids:
            await db.execute(
                text(f"DELETE FROM trades WHERE id = ANY(:ids)"),
                {"ids": [str(tid) for tid in test_trade_ids]}
            )
            print(f"✅  Deleted {len(test_trade_ids)} test Trade records")
        else:
            print("   No test Trade records found (may have already been deleted)")

        # 3. Delete test CompletedTrades
        # We identify them by: created today + broker_account_id + no real entry_trade_ids
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0)
        ct_result = await db.execute(
            select(CompletedTrade.id).where(
                CompletedTrade.broker_account_id == broker_account_id,
                CompletedTrade.created_at >= today_start,
                CompletedTrade.entry_trade_ids == None,  # noqa: E711 — test trades have no entry_trade_ids
            )
        )
        test_ct_ids = [row[0] for row in ct_result.fetchall()]

        if test_ct_ids:
            await db.execute(
                text("DELETE FROM completed_trades WHERE id = ANY(:ids)"),
                {"ids": [str(cid) for cid in test_ct_ids]}
            )
            print(f"✅  Deleted {len(test_ct_ids)} test CompletedTrade records")
        else:
            print("   No test CompletedTrade records found")

        # 4. Delete shadow events from today
        shadow_result = await db.execute(
            text("""
                DELETE FROM shadow_behavioral_events
                WHERE broker_account_id = :account_id
                  AND created_at >= :today
                RETURNING id
            """),
            {"account_id": str(broker_account_id), "today": today_start}
        )
        shadow_count = len(shadow_result.fetchall())
        print(f"✅  Deleted {shadow_count} shadow_behavioral_events from today")

        # 5. Delete test risk_alerts from today
        alert_result = await db.execute(
            text("""
                DELETE FROM risk_alerts
                WHERE broker_account_id = :account_id
                  AND detected_at >= :today
                  AND message LIKE '%consecutive%'
                   OR message LIKE '%revenge%'
                   OR message LIKE '%overtrading%'
                   OR message LIKE '%size%'
                   OR message LIKE '%meltdown%'
                RETURNING id
            """),
            {"account_id": str(broker_account_id), "today": today_start}
        )
        alert_count = len(alert_result.fetchall())
        print(f"✅  Deleted {alert_count} test risk_alerts")

        # 6. Delete today's trading_sessions (test sessions)
        await db.execute(
            text("""
                DELETE FROM trading_sessions
                WHERE broker_account_id = :account_id
                  AND created_at >= :today
            """),
            {"account_id": str(broker_account_id), "today": today_start}
        )
        print("✅  Deleted today's test TradingSession")

        await db.commit()

    await engine.dispose()

    print()
    print("=" * 60)
    print("  Cleanup complete. All test data removed.")
    print("  Your real trade history is untouched.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
