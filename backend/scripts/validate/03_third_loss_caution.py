"""
Script 03: Third Consecutive Loss → CAUTION Alert

Scenario: NIFTY again, loss. 3 in a row hits the caution threshold.
This is the first alert you should see fire.

Expected alerts:
  PRODUCTION (RiskDetector):  consecutive_loss — severity: caution
  SHADOW (BehaviorEngine):    consecutive_loss_streak — logged to shadow table

What to check:
  Dashboard → Alerts panel: should show a new CAUTION alert
  Backend logs: RiskDetector alert saved, [shadow] event logged
  Sentry: no errors

Wait before next script: 3 minutes
  (The revenge trade window is 10 minutes — run Script 04 within 10 min)

Usage:
    cd backend
    python scripts/validate/03_third_loss_caution.py
"""

import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scenario_utils import *
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def main():
    print_banner(3, "Third Loss → CAUTION alert fires")

    broker_account_id = await get_broker_account_id()
    engine = make_engine()
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as db:
        ct = await insert_completed_trade(
            db, broker_account_id,
            symbol="NIFTY25APRFUT",
            exchange="NFO",
            instrument_type="FUT",
            direction="LONG",
            qty=50,
            avg_entry=22020.0,
            avg_exit=21936.0,
            pnl=-4200.0,
            entry_offset_min=-10,
            duration_min=7,
        )
        await insert_trade(
            db, broker_account_id,
            symbol="NIFTY25APRFUT",
            exchange="NFO",
            transaction_type="SELL",
            qty=50,
            price=21936.0,
            pnl=-4200.0,
            offset_min=-3,
        )
        await db.commit()

    await engine.dispose()

    print_done("NIFTY LONG → stopped out, loss ₹4,200 (3 consecutive losses)")
    print()
    print("━" * 60)
    print_expect("🚨  consecutive_loss alert (CAUTION level)")
    print("    Message: '3 consecutive losing trades, total loss ₹10,195'")
    print("━" * 60)
    print_check("Dashboard → Alerts: NEW caution alert should appear")
    print_check("Backend logs: 'Risk detection: 1 new alerts' OR [shadow] event")
    print_check("Sentry: no new errors")
    print()
    print("⏱️   The REVENGE TRADE window is 10 minutes from now.")
    print("    Run Script 04 within the next 10 minutes to trigger revenge_trade alert.")
    print_wait(3, "observe the alert, then run Script 04 within 10 min total")
    print("\n→  Next: python scripts/validate/04_revenge_entry.py")


if __name__ == "__main__":
    asyncio.run(main())
