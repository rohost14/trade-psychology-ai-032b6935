import asyncio
from app.core.database import SessionLocal
from sqlalchemy import text

async def get_broker_accounts():
    async with SessionLocal() as db:
        res = await db.execute(text("SELECT id FROM broker_accounts LIMIT 5"))
        accounts = res.fetchall()
        if accounts:
            print("Found broker accounts:")
            for acc in accounts:
                print(f"  {acc[0]}")
        else:
            print("No broker accounts found! Creating one...")
            # Create a broker account
            res = await db.execute(text("""
                INSERT INTO broker_accounts (id, broker_name, access_token)
                VALUES ('4c42235d-007f-449e-b873-1383de93fe52', 'zerodha', 'mock_token')
                RETURNING id
            """))
            await db.commit()
            new_id = res.first()[0]
            print(f"Created broker account: {new_id}")

asyncio.run(get_broker_accounts())
