import asyncio
import logging
logging.getLogger('sqlalchemy').setLevel(logging.ERROR)
from app.core.database import SessionLocal
from sqlalchemy import text

async def get_tables():
    async with SessionLocal() as db:
        res = await db.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"))
        tables = [r[0] for r in res.fetchall()]
        print("TABLES:", tables)

asyncio.run(get_tables())
