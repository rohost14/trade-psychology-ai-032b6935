import sys, asyncio
sys.path.insert(0, '.')
from app.core.config import settings
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

async def main():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        await session.execute(text(
            "ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS eod_report_time VARCHAR(5) DEFAULT '16:00';"
        ))
        await session.execute(text(
            "ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS morning_brief_time VARCHAR(5) DEFAULT '08:30';"
        ))
        await session.commit()
        print('Migration 027 applied: eod_report_time and morning_brief_time columns added')

        result = await session.execute(text(
            "SELECT column_name FROM information_schema.columns WHERE table_name='user_profiles' AND column_name IN ('eod_report_time','morning_brief_time')"
        ))
        cols = [r[0] for r in result.fetchall()]
        print('Verified:', cols)
    await engine.dispose()

asyncio.run(main())
