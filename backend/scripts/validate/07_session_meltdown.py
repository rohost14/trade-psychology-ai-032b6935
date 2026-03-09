"""
Script 07: Session Meltdown → SESSION_MELTDOWN Alert

Scenario: One final catastrophic trade wipes out 80%+ of daily loss limit.
This triggers the session_meltdown pattern in the BehaviorEngine.

Note: This alert requires daily_loss_limit to be set in your profile.
If not set, it falls back to 5% of trading_capital.
Run Script 00 first to check your settings.

Expected alerts:
  SHADOW (BehaviorEngine): session_meltdown — 'Session P&L: ₹-X. Used Y% of limit.'
  PRODUCTION: no direct equivalent (this is a new pattern in BehaviorEngine)

What to check:
  Backend logs: [shadow] session_meltdown event
  shadow_behavioral_events table in Supabase (SELECT * to view)
  Dashboard: session P&L card should show large negative number

This is the LAST scenario script. After observing, run cleanup.

Usage:
    cd backend
    python scripts/validate/07_session_meltdown.py
"""

import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scenario_utils import *
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def main():
    print_banner(7, "Session Meltdown — catastrophic loss crosses daily limit")

    broker_account_id = await get_broker_account_id()

    # Check what limit is configured
    engine = make_engine()
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    daily_loss_limit = None
    async with Session() as db:
        from app.models.user_profile import UserProfile
        from sqlalchemy import select
        result = await db.execute(
            select(UserProfile).where(UserProfile.broker_account_id == broker_account_id)
        )
        profile = result.scalar_one_or_none()
        if profile:
            daily_loss_limit = profile.daily_loss_limit or (
                (profile.trading_capital or 0) * 0.05 if profile.trading_capital else None
            )

    if not daily_loss_limit:
        print("\n⚠️   No daily_loss_limit or trading_capital set in profile.")
        print("    session_meltdown requires a limit to compare against.")
        print("    Set it in Settings → Trading Limits, then re-run this script.")
        await engine.dispose()
        return

    # We want to push session_pnl below -80% of daily_loss_limit
    # Current session loss is ~₹27,605. Target: exceed 80% of limit.
    target_loss = float(daily_loss_limit) * 0.85  # 85% of limit
    current_loss = 27605  # approximate from previous scripts
    additional_loss_needed = max(0, target_loss - current_loss)

    print(f"\n    Your daily_loss_limit: ₹{daily_loss_limit:,.0f}")
    print(f"    Current session loss:  ~₹{current_loss:,.0f}")
    print(f"    Target (85% of limit): ₹{target_loss:,.0f}")
    print(f"    Additional loss to insert: ₹{additional_loss_needed:,.0f}")

    if additional_loss_needed <= 0:
        print("\n✅  Session loss already exceeds 80% of daily limit from previous scripts!")
        print("    session_meltdown should already have fired. Check logs.")
        await engine.dispose()
        return

    # Add a big loss to push over the threshold
    pnl = -(additional_loss_needed + 1000)  # slightly over threshold
    qty = max(50, int(abs(pnl) / 200))      # calculate qty to produce this loss

    async with Session() as db:
        ct = await insert_completed_trade(
            db, broker_account_id,
            symbol="BANKNIFTY25APRFUT",
            exchange="NFO",
            instrument_type="FUT",
            direction="LONG",
            qty=qty,
            avg_entry=48000.0,
            avg_exit=48000.0 - (abs(pnl) / qty),
            pnl=pnl,
            entry_offset_min=-2,
            duration_min=1,
        )
        await insert_trade(
            db, broker_account_id,
            symbol="BANKNIFTY25APRFUT",
            exchange="NFO",
            transaction_type="SELL",
            qty=qty,
            price=48000.0 - (abs(pnl) / qty),
            pnl=pnl,
            offset_min=-1,
        )
        await db.commit()

    await engine.dispose()

    print_done(f"BANKNIFTY LONG → loss ₹{abs(pnl):,.0f} (session meltdown triggered)")
    print()
    print("━" * 60)
    print_expect("🚨  session_meltdown alert (SHADOW)")
    print(f"    'Session P&L: ₹{-(current_loss + abs(pnl)):,.0f}. Used 85%+ of daily limit.'")
    print("━" * 60)
    print_check("Backend logs: [shadow] session_meltdown event")
    print_check("Run in Supabase: SELECT event_type, severity, message, behavior_state")
    print_check("                 FROM shadow_behavioral_events ORDER BY detected_at DESC LIMIT 20")
    print_check("Dashboard: total session loss visible on dashboard P&L card")
    print()
    print("━" * 60)
    print("  SCENARIO COMPLETE — All 7 patterns tested")
    print("━" * 60)
    print()
    print("📊 Summary of what should have fired:")
    print("   Script 03 → consecutive_loss_streak (CAUTION)   [production + shadow]")
    print("   Script 04 → revenge_trade                        [shadow]")
    print("   Script 05 → overtrading_burst                    [shadow]")
    print("   Script 06 → size_escalation + DANGER streak      [production + shadow]")
    print("   Script 07 → session_meltdown                     [shadow only]")
    print()
    print("📝 Compare production alerts (risk_alerts table)")
    print("   vs shadow events (shadow_behavioral_events table)")
    print("   to validate BehaviorEngine match rate before cutover.")
    print()
    print("When done observing:")
    print("→  Run: python scripts/validate/cleanup.py")


if __name__ == "__main__":
    asyncio.run(main())
