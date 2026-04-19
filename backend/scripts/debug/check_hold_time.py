"""Query avg hold times from DB."""
import asyncio
import logging
logging.disable(logging.CRITICAL)

async def main():
    import sys
    sys.path.insert(0, '.')
    from dotenv import load_dotenv
    load_dotenv('.env')
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text
    from app.core.config import settings

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        r = await conn.execute(text("""
            SELECT
                COUNT(*) FILTER (WHERE exit_time >= NOW() - INTERVAL '7 days')  AS cnt_7d,
                ROUND(AVG(duration_minutes) FILTER (WHERE exit_time >= NOW() - INTERVAL '7 days' AND duration_minutes > 0)) AS avg_7d,
                COUNT(*) FILTER (WHERE exit_time >= NOW() - INTERVAL '30 days') AS cnt_30d,
                ROUND(AVG(duration_minutes) FILTER (WHERE exit_time >= NOW() - INTERVAL '30 days' AND duration_minutes > 0)) AS avg_30d,
                COUNT(*) FILTER (WHERE duration_minutes > 0) AS cnt_all,
                ROUND(AVG(duration_minutes) FILTER (WHERE duration_minutes > 0)) AS avg_all
            FROM completed_trades
        """))
        row = r.fetchone()
        print(f"7-day  : {row.cnt_7d} trades, avg {row.avg_7d} min")
        print(f"30-day : {row.cnt_30d} trades, avg {row.avg_30d} min")
        print(f"All    : {row.cnt_all} trades, avg {row.avg_all} min")
        print()

        r2 = await conn.execute(text("""
            SELECT
                CASE
                    WHEN duration_minutes <= 5  THEN 'scalp (<=5m)'
                    WHEN duration_minutes <= 30 THEN 'quick (6-30m)'
                    WHEN duration_minutes <= 120 THEN 'intraday (31-120m)'
                    WHEN duration_minutes <= 375 THEN 'full-day (2-6h)'
                    ELSE 'multi-day (>6h)'
                END as bucket,
                COUNT(*) as cnt,
                ROUND(AVG(duration_minutes)) as avg_min
            FROM completed_trades
            WHERE duration_minutes > 0
            GROUP BY 1
            ORDER BY MIN(duration_minutes)
        """))
        print("Hold time distribution (all trades):")
        for row in r2.fetchall():
            print(f"  {row.bucket:25s}  {row.cnt:4d} trades  avg {row.avg_min} min")

    await engine.dispose()

asyncio.run(main())
