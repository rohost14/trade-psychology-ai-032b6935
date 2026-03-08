import asyncio
import uuid
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select, insert

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

IST = ZoneInfo("Asia/Kolkata")
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

async def create_sandbox(db):
    user_id = uuid.uuid4()
    broker_id = uuid.uuid4()
    
    # 1. Insert User directly
    await db.execute(insert(User).values(
        id=user_id,
        email=f"sandbox_{user_id}@test.com",
        display_name="Tester"
    ))
    
    # 2. Insert Broker Account
    await db.execute(insert(BrokerAccount).values(
        id=broker_id,
        user_id=user_id,
        broker_name="mock_broker",
        status="connected",
        api_key="mock",
        broker_user_id="MB100",
        exchanges=["NSE"],
        order_types=["MARKET"]
    ))
    
    # 3. Insert Profile
    await db.execute(insert(UserProfile).values(
        id=uuid.uuid4(),
        broker_account_id=broker_id,
        cooldown_after_loss=15
    ))

    # We need the Profile object for RiskDetector()
    res = await db.execute(select(UserProfile).where(UserProfile.broker_account_id == broker_id))
    profile = res.scalar_one_or_none()
    
    await db.flush()
    return user_id, broker_id, profile

async def test_revenge_sizing():
    print("\n--- Testing Revenge Sizing DB Escalation ---")
    async with SessionLocal() as db:
        user_id, broker_id, profile = await create_sandbox(db)
        now = datetime.now(timezone.utc)
        
        # 1. A losing completed trade
        losing_ct = CompletedTrade(
            id=uuid.uuid4(),
            broker_account_id=broker_id,
            tradingsymbol="NIFTY",
            exchange="NSE",
            product="MIS",
            direction="LONG",
            total_quantity=50,
            entry_time=now - timedelta(minutes=20),
            exit_time=now - timedelta(minutes=5),
            avg_entry_price=100.0,
            avg_exit_price=90.0,
            realized_pnl=-500.0,
            duration_minutes=15,
            instrument_type="EQ"
        )
        db.add(losing_ct)
        await db.flush()
        
        # 2. Massive revenge trade taken
        trigger_trade = Trade(
            id=uuid.uuid4(),
            broker_account_id=broker_id,
            order_id="R123",
            tradingsymbol="NIFTY",
            exchange="NSE",
            transaction_type="BUY",
            quantity=150,  # 3x the losing size
            filled_quantity=150,
            order_timestamp=now,
            status="COMPLETE",
            average_price=90.0
        )
        db.add(trigger_trade)
        await db.flush()
        
        detector = RiskDetector()
        alerts = await detector.detect_patterns(broker_id, db, trigger_trade, profile)
        
        revenge_alerts = [a for a in alerts if a.pattern_type == "revenge_sizing"]
        assert len(revenge_alerts) == 1, f"Expected 1 revenge alert, got {len(revenge_alerts)}"
        print("[SUCCESS] Detected Revenge Sizing correctly.")
        
        # Check cooldown
        res = await db.execute(select(Cooldown).where(Cooldown.broker_account_id == broker_id))
        cooldowns = res.scalars().all()
        assert len(cooldowns) == 1, "Expected 1 DB Cooldown to be generated"
        print("[SUCCESS] Database Cooldown applied.")
        
        await db.rollback()

async def run_all():
    await test_revenge_sizing()
    print("\n[COMPLETE] Sandbox E2E Tests successfully validated DB behavior.")

if __name__ == "__main__":
    asyncio.run(run_all())
