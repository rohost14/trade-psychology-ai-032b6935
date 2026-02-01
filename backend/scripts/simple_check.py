import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import settings

# Create local engine to avoid echo=True from main app
engine = create_async_engine(settings.DATABASE_URL, echo=False)

async def check_raw():
    async with engine.connect() as conn:
        with open('debug_output.txt', 'w') as f:
            f.write("Connected to DB\n")
            result = await conn.execute(text("SELECT count(*) FROM positions WHERE broker_account_id = '550e8400-e29b-41d4-a716-446655440000'"))
            count = result.scalar()
            f.write(f"Count for specified ID: {count}\n")
            
            result_all = await conn.execute(text("SELECT count(*) FROM positions"))
            f.write(f"Total positions in table: {result_all.scalar()}\n")
            
            res = await conn.execute(text("SELECT id, broker_account_id FROM positions"))
            rows = res.fetchall()
            f.write("All Rows:\n")
            for r in rows:
                f.write(f"{r}\n")

if __name__ == "__main__":
    asyncio.run(check_raw())
