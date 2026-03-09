"""
Script 00: Setup check

Run this FIRST before any other script.
Verifies:
  - DB connection works
  - A connected broker account exists
  - Prints your account details
  - Checks if daily_loss_limit is set (needed for session_meltdown test)

Usage:
    cd backend
    python scripts/validate/00_setup.py
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scenario_utils import make_engine, get_broker_account_id
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy import select


async def main():
    print("\n" + "=" * 60)
    print("  TradeMentor AI — Validation Scenario Setup Check")
    print("=" * 60)

    # Check broker account
    broker_account_id = await get_broker_account_id()

    # Check user profile thresholds
    engine = make_engine()
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as db:
        from app.models.user_profile import UserProfile
        result = await db.execute(
            select(UserProfile).where(UserProfile.broker_account_id == broker_account_id)
        )
        profile = result.scalar_one_or_none()

        print("\n📋  Your Profile Settings:")
        if profile:
            print(f"    daily_loss_limit:    ₹{profile.daily_loss_limit or 'NOT SET'}")
            print(f"    trading_capital:     ₹{profile.trading_capital or 'NOT SET'}")
            print(f"    daily_trade_limit:   {profile.daily_trade_limit or 'NOT SET'}")
            print(f"    cooldown_after_loss: {profile.cooldown_after_loss or 'NOT SET'} min")

            if not profile.daily_loss_limit:
                print("\n⚠️   daily_loss_limit is not set.")
                print("    Script 07 (session_meltdown) will use 5% of trading_capital as fallback.")
                if not profile.trading_capital:
                    print("    trading_capital is also not set — Script 07 may not fire.")
                    print("    Set these in Settings → Trading Limits before running Script 07.")
        else:
            print("    No profile found. Alerts will use default thresholds.")
            print("    ⚠️  Set trading limits in Settings for best test results.")

    await engine.dispose()

    print("\n📝  Scenario: 'The Revenge Spiral'")
    print("    A realistic bad trading day that builds up patterns naturally.")
    print()
    print("    Script 01 → First trade, loss                (no alert)")
    print("    Script 02 → Second loss                      (no alert)")
    print("    Script 03 → Third loss quickly               → consecutive_loss_streak CAUTION")
    print("    Script 04 → Immediate re-entry after loss    → revenge_trade")
    print("    Script 05 → 4 more rapid trades              → overtrading_burst")
    print("    Script 06 → Double position after losses     → size_escalation")
    print("    Script 07 → Massive loss                     → session_meltdown")
    print("    cleanup   → Deletes all test data")
    print()
    print("⚠️   IMPORTANT:")
    print("    • Run scripts in order (01 → 07)")
    print("    • Wait between scripts as instructed")
    print("    • Watch the dashboard and backend logs after each script")
    print("    • Do NOT run cleanup until you've observed all alerts")
    print()
    print("✅  Setup check complete. Ready to start.")
    print("    Run: python scripts/validate/01_opening_loss.py")


if __name__ == "__main__":
    asyncio.run(main())
