"""
Script 02: Second Consecutive Loss

Scenario: BANKNIFTY LONG, another loss. 2 in a row now.
Still below caution threshold (default = 3 consecutive).

Expected alerts: NONE yet (2 < 3 threshold)
What to check: Closed Trades shows 2 losses. No alert.
               [shadow] log should show consecutive_loss_streak = 2,
               but no event fired (below threshold).

Wait before next script: 1–2 minutes

Usage:
    cd backend
    python scripts/validate/02_second_loss.py
"""

import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scenario_utils import *
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def main():
    print_banner(2, "Second Loss — BANKNIFTY LONG stopped out")

    broker_account_id = await get_broker_account_id()
    engine = make_engine()
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as db:
        ct = await insert_completed_trade(
            db, broker_account_id,
            symbol="BANKNIFTY25APRFUT",
            exchange="NFO",
            instrument_type="FUT",
            direction="LONG",
            qty=15,
            avg_entry=48200.0,
            avg_exit=47967.0,
            pnl=-3495.0,
            entry_offset_min=-18,
            duration_min=12,
        )
        await insert_trade(
            db, broker_account_id,
            symbol="BANKNIFTY25APRFUT",
            exchange="NFO",
            transaction_type="SELL",
            qty=15,
            price=47967.0,
            pnl=-3495.0,
            offset_min=-6,
        )
        await db.commit()

    await engine.dispose()

    print_done("BANKNIFTY LONG → stopped out, loss ₹3,495 (2 consecutive losses)")
    print_expect("NO alerts — 2 consecutive losses, below caution threshold of 3")
    print_check("Closed Trades: should show 2 losing trades")
    print_check("Backend logs: [shadow] may log 'streak=2' but no event fired")
    print_wait(2, "before triggering the caution threshold")
    print("\n→  Next: python scripts/validate/03_third_loss_caution.py")


if __name__ == "__main__":
    asyncio.run(main())
