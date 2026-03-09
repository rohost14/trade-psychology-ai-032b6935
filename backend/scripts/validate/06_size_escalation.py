"""
Script 06: Size Escalation → SIZE_ESCALATION + possible DANGER Alert

Scenario: Trader tries to 'make it all back' by doubling position size.
After 8 consecutive losses, takes a 100-lot NIFTY position (was trading 50).
This triggers size escalation AND potentially pushes consecutive loss to DANGER.

Expected alerts:
  PRODUCTION (RiskDetector):  consecutive_loss — severity: danger (if streak >= 5)
                               revenge_sizing (large position after losses)
  SHADOW (BehaviorEngine):    size_escalation + consecutive_loss_streak DANGER
                               martingale_behaviour (if pattern detected)

What to check:
  Dashboard → Alerts: DANGER level alert (red)
  Push notification should fire (if push notifications enabled)
  WhatsApp to guardian (if configured)
  Backend logs: [shadow] multiple events, risk_score jumping significantly

Wait before next script: 2 minutes

Usage:
    cd backend
    python scripts/validate/06_size_escalation.py
"""

import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scenario_utils import *
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def main():
    print_banner(6, "Size Escalation — doubling position to recover losses")

    broker_account_id = await get_broker_account_id()
    engine = make_engine()
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as db:
        # 100-lot NIFTY (was 50) — loss again
        ct = await insert_completed_trade(
            db, broker_account_id,
            symbol="NIFTY25APRFUT",
            exchange="NFO",
            instrument_type="FUT",
            direction="LONG",
            qty=100,          # ← DOUBLED from previous 50
            avg_entry=21860.0,
            avg_exit=21760.0,
            pnl=-10000.0,     # Big loss — ₹100 × 100 qty
            entry_offset_min=-3,
            duration_min=2,
        )
        await insert_trade(
            db, broker_account_id,
            symbol="NIFTY25APRFUT",
            exchange="NFO",
            transaction_type="SELL",
            qty=100,
            price=21760.0,
            pnl=-10000.0,
            offset_min=-1,
        )
        await db.commit()

    await engine.dispose()

    print_done("NIFTY LONG 100-lot → loss ₹10,000 (doubled size, 9th consecutive loss)")
    print()
    print("━" * 60)
    print_expect("🚨🚨  MULTIPLE DANGER ALERTS")
    print("    consecutive_loss_streak: DANGER (9 losses, threshold=5)")
    print("    size_escalation: sizes 50→50→100 after losses")
    print("    Shadow behavior_state may be 'Tilt' or 'Breakdown'")
    print("━" * 60)
    print_check("Dashboard → Alerts: DANGER level alert (red badge)")
    print_check("Push notification: should arrive on device (if enabled)")
    print_check("Backend logs: [shadow] multiple HIGH events, risk_score high")
    print_check("BlowupShield: may start showing checkpoint data for this alert")
    print()
    total = 2500+3495+4200+2500+1005+1700+1005+1700+10000
    print(f"Total session loss now: ~₹{total:,.0f}")
    print_wait(2, "before final session meltdown test")
    print("\n→  Next: python scripts/validate/07_session_meltdown.py")


if __name__ == "__main__":
    asyncio.run(main())
