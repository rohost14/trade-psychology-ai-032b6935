import asyncio
from app.core.database import SessionLocal
from sqlalchemy import text

async def show_table_schema():
    async with SessionLocal() as db:
        # Show column definitions for trades table
        res = await db.execute(text("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = 'trades'
            ORDER BY ordinal_position
        """))
        
        print("Trades table structure:")
        print(f"{'Column':<25} {'Type':<20} {'Nullable':<10} {'Default'}")
        print("-" * 80)
        for row in res.fetchall():
            print(f"{row[0]:<25} {row[1]:<20} {row[2]:<10} {row[3] or ''}")

asyncio.run(show_table_schema())
