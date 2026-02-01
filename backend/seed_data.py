import asyncio
import os
import sys
from datetime import datetime, timedelta
import random
from uuid import UUID

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.database import SessionLocal
from app.models.trade import Trade

BROKER_ACCOUNT_ID = UUID('4c42235d-bfe0-4f54-902c-c5dfb04f669a')  # Updated to match actual DB value
USER_ID = None  # user_id is nullable

async def seed_trades():
    print(f"🌱 Seeding trades for account: {BROKER_ACCOUNT_ID}")
    
    async with SessionLocal() as db:
        trades = []
        now = datetime.now()
        
        # Create 50 trades over last 30 days
        for i in range(50):
            days_ago = random.randint(0, 30)
            trade_time = now - timedelta(days=days_ago, hours=random.randint(9, 15), minutes=random.randint(0, 59))
            
            # 60% win rate
            is_win = random.random() > 0.4
            pnl = random.randint(500, 5000) if is_win else random.randint(-3000, -500)
            
            trade = Trade(
                user_id=USER_ID,
                broker_account_id=BROKER_ACCOUNT_ID,
                order_id=f"ORD{i}",
                tradingsymbol=random.choice(["NIFTY24JANFUT", "BANKNIFTY24JANFUT", "RELIANCE", "INFY"]),
                exchange="NFO",
                transaction_type="BUY" if random.random() > 0.5 else "SELL",
                order_type="MARKET",
                product="MIS",
                quantity=50,
                filled_quantity=50,
                average_price=random.uniform(100, 2000),
                status="COMPLETE",
                pnl=pnl,
                order_timestamp=trade_time,
                exchange_timestamp=trade_time,
                asset_class="EQUITY",
                instrument_type="FUT"
            )
            trades.append(trade)
        
        db.add_all(trades)
        await db.commit()
        print(f"✅ inserted {len(trades)} trades")

if __name__ == "__main__":
    asyncio.run(seed_trades())
