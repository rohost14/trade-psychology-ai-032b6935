import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import settings

# Create local engine
engine = create_async_engine(settings.DATABASE_URL, echo=False)

async def inspect_columns():
    async with engine.connect() as conn:
        print("Inspecting 'positions' table columns...")
        try:
            with open('data_check.txt', 'w') as f:
                f.write("Checking positions_history...\n")
                # Check metrics
                res = await conn.execute(text("SELECT status, count(*) FROM positions_history GROUP BY status"))
                rows = res.fetchall()
                f.write(f"Status breakdown: {rows}\n")
                
                # Check for specific broker account
                res = await conn.execute(text("SELECT count(*) FROM positions_history WHERE broker_account_id = '550e8400-e29b-41d4-a716-446655440000'"))
                count = res.scalar()
                f.write(f"Count for target broker_id: {count}\n")
                
                if count > 0:
                     res = await conn.execute(text("SELECT * FROM positions_history WHERE broker_account_id = '550e8400-e29b-41d4-a716-446655440000' LIMIT 2"))
                     f.write(f"Sample rows: {res.fetchall()}\n")

        except Exception as e:
            print(f"Error: {e}")


        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(inspect_columns())
