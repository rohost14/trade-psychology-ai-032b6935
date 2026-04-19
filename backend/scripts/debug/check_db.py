import asyncio
from app.core.database import SessionLocal
from sqlalchemy import text

async def check():
    async with SessionLocal() as db:
        # Check users
        res = await db.execute(text("SELECT id FROM users LIMIT 1"))
        user = res.first()
        print(f"First user_id: {user}")
        
        # Check broker accounts
        res2 = await db.execute(text("SELECT id, user_id FROM broker_accounts LIMIT 1"))
        broker = res2.first()
        print(f"First broker account: {broker}")

asyncio.run(check())
