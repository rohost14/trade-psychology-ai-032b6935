"""
Script 04: Revenge Trade → REVENGE_TRADE Alert

Scenario: Trader enters NIFTY again, just 4 minutes after the last loss.
This is classic revenge trading — entering immediately after a loss
without cooling down.

⚠️  RUN THIS WITHIN 10 MINUTES OF SCRIPT 03.
    The revenge window is 10 minutes. After that, it won't trigger.

Expected alerts:
  PRODUCTION (RiskDetector):  revenge_sizing (if position is larger than last)
  SHADOW (BehaviorEngine):    revenge_trade — HIGH severity (gap < 10 min)

What to check:
  Dashboard → Alerts: new alert for revenge trading
  Backend logs: [shadow] revenge_trade event
  Note the gap_minutes in the alert context

Wait before next script: 1 minute (we're going to overtrade rapidly)

Usage:
    cd backend
    python scripts/validate/04_revenge_entry.py
"""

import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scenario_utils import *
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from datetime import datetime, timezone, timedelta


async def main():
    print_banner(4, "Revenge Entry — NIFTY again, 4 minutes after last loss")

    broker_account_id = await get_broker_account_id()
    engine = make_engine()
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as db:
        # Entry is NOW (just inserted) — 4 minutes after script 03's exit
        # Script 03 exit was ~3 min ago, so this entry gap = ~4 min
        ct = await insert_completed_trade(
            db, broker_account_id,
            symbol="NIFTY25APRFUT",
            exchange="NFO",
            instrument_type="FUT",
            direction="LONG",
            qty=50,        # Same size as before — same symbol, quick re-entry
            avg_entry=21950.0,
            avg_exit=21900.0,
            pnl=-2500.0,   # Another loss — the revenge trade also lost
            entry_offset_min=-4,
            duration_min=3,
        )
        await insert_trade(
            db, broker_account_id,
            symbol="NIFTY25APRFUT",
            exchange="NFO",
            transaction_type="SELL",
            qty=50,
            price=21900.0,
            pnl=-2500.0,
            offset_min=-1,
        )
        await db.commit()

    await engine.dispose()

    print_done("NIFTY LONG → loss ₹2,500 entered 4 minutes after last loss")
    print()
    print("━" * 60)
    print_expect("🚨  revenge_trade alert")
    print("    Shadow: 'Entry 4min after a ₹4,200 loss. Revenge trading risk.'")
    print("━" * 60)
    print_check("Dashboard → Alerts: revenge trading alert")
    print_check("Backend logs: [shadow] revenge_trade event, gap_minutes=~4")
    print_check("Alert context should show gap_minutes and prior_loss values")
    print()
    print("Now you have 4 consecutive losses. Streak = 4 → may upgrade to DANGER")
    print("depending on your danger threshold setting (default = 5).")
    print_wait(1, "prepare for rapid overtrading burst")
    print("\n→  Next: python scripts/validate/05_overtrading_burst.py")


if __name__ == "__main__":
    asyncio.run(main())
