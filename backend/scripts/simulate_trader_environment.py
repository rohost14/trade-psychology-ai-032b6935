import asyncio
import uuid
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from sqlalchemy import select, insert, delete

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.database import SessionLocal
from app.models.user import User
from app.models.broker_account import BrokerAccount
from app.models.trade import Trade
from app.models.completed_trade import CompletedTrade
from app.models.risk_alert import RiskAlert
from app.models.cooldown import Cooldown
from app.services.risk_detector import RiskDetector
from app.models.user_profile import UserProfile
from app.services import behavioral_analysis_service as bas

IST = ZoneInfo("Asia/Kolkata")
logger = logging.getLogger(__name__)

async def setup_trader(db):
    user_id = uuid.uuid4()
    broker_id = uuid.uuid4()
    
    await db.execute(insert(User).values(
        id=user_id, email=f"trader_{user_id}@test.com", display_name="AutoTester"
    ))
    await db.execute(insert(BrokerAccount).values(
        id=broker_id, user_id=user_id, broker_name="mock_broker", status="connected",
        api_key="mock", broker_user_id="MBTEST", exchanges=["NSE"], order_types=["MARKET"]
    ))
    await db.execute(insert(UserProfile).values(
        id=uuid.uuid4(), broker_account_id=broker_id, cooldown_after_loss=15
    ))
    
    res = await db.execute(select(UserProfile).where(UserProfile.broker_account_id == broker_id))
    profile = res.scalar_one_or_none()
    await db.flush()
    return user_id, broker_id, profile

async def build_trade(db, broker_id, offset_min, sym, qty, price, transaction_type, status="COMPLETE"):
    """Inserts a raw Trade"""
    now = datetime.now(timezone.utc)
    t = Trade(
        id=uuid.uuid4(),
        broker_account_id=broker_id,
        order_id=f"O_{uuid.uuid4()}",
        tradingsymbol=sym,
        exchange="NSE",
        transaction_type=transaction_type,
        quantity=qty,
        filled_quantity=qty,
        average_price=price,
        order_timestamp=now + timedelta(minutes=offset_min),
        status=status
    )
    db.add(t)
    await db.flush()
    return t

async def build_completed_trade(db, broker_id, offset_entry_min, offset_exit_min, sym, qty, entry_pr, exit_pr, is_long=True):
    """Inserts a CompletedTrade representing a closed round trip"""
    now = datetime.now(timezone.utc)
    pnl = (exit_pr - entry_pr) * qty if is_long else (entry_pr - exit_pr) * qty
    
    ct = CompletedTrade(
        id=uuid.uuid4(),
        broker_account_id=broker_id,
        tradingsymbol=sym,
        exchange="NSE",
        instrument_type="EQ",
        product="MIS",
        direction="LONG" if is_long else "SHORT",
        total_quantity=qty,
        avg_entry_price=entry_pr,
        avg_exit_price=exit_pr,
        realized_pnl=pnl,
        entry_time=now + timedelta(minutes=offset_entry_min),
        exit_time=now + timedelta(minutes=offset_exit_min),
        duration_minutes=abs(offset_exit_min - offset_entry_min)
    )
    db.add(ct)
    await db.flush()
    return ct


async def run_environment_simulations():
    report = []
    report.append("# Behavioral AI Engine: E2E Simulation Report\n")
    report.append("This report documents the automated testing of the AI trading psychology engine. By spawning an isolated sandbox database user, we inject precise sequences of trades to verify that the RiskDetector correctly catches behavioral flaws like Revenge Trading and Overtrading, and escalates them to Database Cooldowns.\n")
    
    async with SessionLocal() as db:
        uid, bid, profile = await setup_trader(db)
        detector = RiskDetector()
        
        # ---------------------------------------------------------
        # SCENARIO 1: Revenge Trading & Overtrading Combo (As User Requested)
        # 4 Losses in a row, followed immediately by a massive trade
        # ---------------------------------------------------------
        report.append("## Scenario 1: The 4-Loss Revenge & Overtrade")
        report.append("**Action:** Trader takes 4 consecutive losing trades within 10 minutes. 2 minutes after the 4th loss, trader enters a 5th trade with triple the position size.")
        
        # Insert 4 losses
        for i in range(4):
            # Raw entry/exit trades to satisfy `len(trades) > x` heuristics
            await build_trade(db, bid, -20 + i, "NIFTY", 50, 100, "BUY")
            await build_trade(db, bid, -18 + i, "NIFTY", 50, 95, "SELL")
            
            # The finalized CompletedTrade representing the loss
            await build_completed_trade(db, bid, -20 + i, -18 + i, "NIFTY", 50, 100, 95)
            
        # The trigger trade (massive volume, tight time gap)
        trigger_trade = await build_trade(db, bid, -15, "NIFTY", 200, 95, "BUY")
        
        # Run Detection
        alerts_1 = await detector.detect_patterns(bid, db, trigger_trade, profile)
        alert_types = [a.pattern_type for a in alerts_1]
        
        passed_revenge = "revenge_sizing" in alert_types
        passed_spiral = "consecutive_loss" in alert_types or "tilt_loss_spiral" in alert_types
        # 5 trades in 5 mins might not be "Overtrading" depending on threshold (usually 7-10 trades)
        
        report.append(f"**Results:**")
        report.append(f"- Revenge Sizing Alert Triggered: {'✅ PASSED' if passed_revenge else '❌ FAILED'}")
        report.append(f"- Loss Spiral / Consecutive Loss Alert Triggered: {'✅ PASSED' if passed_spiral else '❌ FAILED'}")
        report.append(f"- Generated Alerts: {', '.join(alert_types)}")
        
        # ---------------------------------------------------------
        # SCENARIO 2: FOMO / Machine Gun Overtrading
        # 10 rapid entries in 3 minutes
        # ---------------------------------------------------------
        report.append("\n## Scenario 2: Severe Overtrading (Machine Gun)")
        report.append("**Action:** Trader opens and closes 8 positions in under 4 minutes.")
        
        for i in range(8):
            trigger_trade = await build_trade(db, bid, i*0.5, "BANKNIFTY", 15, 100, "BUY")
        
        alerts_2 = await detector.detect_patterns(bid, db, trigger_trade, profile)
        overtrade = [a for a in alerts_2 if a.pattern_type == "overtrading"]
        passed_overtrade = len(overtrade) > 0
        
        report.append(f"**Results:**")
        report.append(f"- Overtrading Alert Triggered: {'✅ PASSED' if passed_overtrade else '❌ FAILED'}")
        if passed_overtrade:
            report.append(f"- Severity Escalatation: {overtrade[0].severity}")

        # ---------------------------------------------------------
        # SCENARIO 3: Cooldown Effectiveness
        # ---------------------------------------------------------
        report.append("\n## Scenario 3: Database Cooldown Ingestion")
        res = await db.execute(select(Cooldown).where(Cooldown.broker_account_id == bid))
        cooldowns = res.scalars().all()
        passed_cooldown = len(cooldowns) > 0
        report.append(f"**Action:** Check if the above danger-level behaviors automatically locked the trader out via `cooldown_until`.")
        report.append(f"**Results:**")
        report.append(f"- Database Cooldowns Active: {'✅ PASSED' if passed_cooldown else '❌ FAILED'} (Count: {len(cooldowns)})")

        # Rollback so DB stays completely clean
        await db.rollback()
        
    with open("docs/BEHAVIORAL_QA_SIMULATION.md", "w", encoding='utf-8') as f:
        f.write("\n".join(report))
    
    print("Simulation complete. Wrote docs/BEHAVIORAL_QA_SIMULATION.md")

if __name__ == "__main__":
    asyncio.run(run_environment_simulations())
