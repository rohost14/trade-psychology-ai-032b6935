import asyncio
from app.core.database import SessionLocal
from sqlalchemy import text

async def check():
    async with SessionLocal() as db:
        # List all tables
        res = await db.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """))
        tables = res.fetchall()
        print("Available tables:")
        for t in tables:
            print(f"  - {t[0]}")
        
        # Check broker_accounts structure
        print("\nChecking broker_accounts...")
        res2 = await db.execute(text("SELECT * FROM broker_accounts LIMIT 1"))
        broker = res2.first()
        if broker:
            print(f"Sample broker account: {dict(broker._mapping)}")
        else:
            print("No broker accounts found")

asyncio.run(check())
