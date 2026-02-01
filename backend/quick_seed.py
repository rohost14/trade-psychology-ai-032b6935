"""
Quick fix: Ensure broker account exists, then seed trades
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta
import random
from uuid import UUID

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.database import SessionLocal
from sqlalchemy import text

BROKER_ACCOUNT_ID = UUID('4c42235d-bfe0-4f54-902c-c5dfb04f669a')

async def ensure_broker_and_seed():
    print("🔧 Ensuring broker account exists...")
    
    async with SessionLocal() as db:
        # Check if broker account exists
        result = await db.execute(
            text("SELECT id, status FROM broker_accounts WHERE id = :id"),
            {"id": BROKER_ACCOUNT_ID}
        )
        broker = result.first()
        
        if not broker:
            print(f"Creating broker account {BROKER_ACCOUNT_ID}...")
            await db.execute(text("""
                INSERT INTO broker_accounts (id, broker_name, status)
                VALUES (:id, 'zerodha', 'active')
            """), {"id": BROKER_ACCOUNT_ID})
            await db.commit()
            print("✅ Broker account created")
        else:
            print(f"✅ Broker account exists with status: {broker[1]}")
        
        # Now seed trades
        print("\n🌱 Seeding 50 trades...")
        
        now = datetime.now()
        for i in range(50):
            days_ago = random.randint(0, 30)
            trade_time = now - timedelta(
                days=days_ago,
                hours=random.randint(9, 15),
                minutes=random.randint(0, 59)
            )
            
            is_win = random.random() > 0.4
            pnl = random.randint(500, 5000) if is_win else random.randint(-3000, -500)
            
            await db.execute(text("""
                INSERT INTO trades (
                    broker_account_id, order_id, tradingsymbol, exchange,
                    transaction_type, order_type, product, quantity,
                    filled_quantity, average_price, status, pnl,
                    order_timestamp, exchange_timestamp,
                    asset_class, instrument_type
                ) VALUES (
                    :broker_id, :order_id, :symbol, :exchange,
                    :trans_type, :order_type, :product, :qty,
                    :filled_qty, :avg_price, :status, :pnl,
                    :order_ts, :exchange_ts,
                    :asset_class, :instrument_type
                )
            """), {
                "broker_id": BROKER_ACCOUNT_ID,
                "order_id": f"ORD{i:04d}",
                "symbol": random.choice(["NIFTY24JANFUT", "BANKNIFTY24JANFUT", "RELIANCE", "INFY"]),
                "exchange": "NFO",
                "trans_type": "BUY" if random.random() > 0.5 else "SELL",
                "order_type": "MARKET",
                "product": "MIS",
                "qty": 50,
                "filled_qty": 50,
                "avg_price": random.uniform(100, 2000),
                "status": "COMPLETE",
                "pnl": pnl,
                "order_ts": trade_time,
                "exchange_ts": trade_time,
                "asset_class": "EQUITY",
                "instrument_type": "FUT"
            })
        
        await db.commit()
        print(f"✅ Inserted 50 trades into database")

if __name__ == "__main__":
    asyncio.run(ensure_broker_and_seed())
