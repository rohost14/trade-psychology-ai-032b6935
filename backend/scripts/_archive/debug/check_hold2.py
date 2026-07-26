"""Investigate trade data quality and hold time calculation."""
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

    url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(
        url, echo=False,
        connect_args={"statement_cache_size": 0},
    )
    async with engine.connect() as conn:

        # 1. Trades by exchange
        r = await conn.execute(text("""
            SELECT exchange, COUNT(*) as cnt, ROUND(AVG(duration_minutes)) as avg_dur
            FROM completed_trades
            WHERE duration_minutes > 0
            GROUP BY exchange ORDER BY cnt DESC
        """))
        print("Trades by exchange:")
        for row in r.fetchall():
            print(f"  {str(row.exchange or 'NULL'):10s}: {row.cnt} trades, avg {row.avg_dur} min")

        # 2. Possible seed data
        r2 = await conn.execute(text("""
            SELECT tradingsymbol, COUNT(*) as cnt, MIN(entry_time) as first_entry, SUM(realized_pnl) as total_pnl
            FROM completed_trades
            WHERE tradingsymbol IN ('INFY', 'ULTRACEMCO')
            GROUP BY tradingsymbol
        """))
        print("\nINFY / ULTRACEMCO (likely seed data):")
        for row in r2.fetchall():
            print(f"  {row.tradingsymbol}: {row.cnt} trades, first={str(row.first_entry)[:16]}, total_pnl={row.total_pnl}")

        # 3. Avg hold time excluding suspected seed data and 1-min minimum-clamped
        r3 = await conn.execute(text("""
            SELECT
                COUNT(*) FILTER (WHERE exit_time >= NOW() - INTERVAL '7 days')  AS cnt_7d,
                ROUND(AVG(duration_minutes) FILTER (WHERE exit_time >= NOW() - INTERVAL '7 days' AND duration_minutes > 1)) AS avg_7d,
                COUNT(*) FILTER (WHERE exit_time >= NOW() - INTERVAL '30 days') AS cnt_30d,
                ROUND(AVG(duration_minutes) FILTER (WHERE exit_time >= NOW() - INTERVAL '30 days' AND duration_minutes > 1)) AS avg_30d,
                COUNT(*) FILTER (WHERE duration_minutes > 1) AS cnt_all,
                ROUND(AVG(duration_minutes) FILTER (WHERE duration_minutes > 1)) AS avg_all
            FROM completed_trades
            WHERE tradingsymbol NOT IN ('INFY', 'ULTRACEMCO')
        """))
        row = r3.fetchone()
        print(f"\nAvg hold (excl seed data, excl duration=1 min-clamp):")
        print(f"  7-day  : {row.cnt_7d} trades, avg {row.avg_7d} min")
        print(f"  30-day : {row.cnt_30d} trades, avg {row.avg_30d} min")
        print(f"  All    : {row.cnt_all} trades, avg {row.avg_all} min")

        # 4. True short trades (NIFTY/SENSEX options, <5min, real timestamps)
        r4 = await conn.execute(text("""
            SELECT tradingsymbol, entry_time, exit_time, duration_minutes, realized_pnl
            FROM completed_trades
            WHERE duration_minutes <= 5
              AND tradingsymbol NOT IN ('INFY', 'ULTRACEMCO')
              AND (entry_time AT TIME ZONE 'Asia/Kolkata')::time BETWEEN '09:00' AND '23:35'
            ORDER BY exit_time DESC
            LIMIT 15
        """))
        print("\nLegitimate short trades (<=5m, during market hours):")
        for row in r4.fetchall():
            import pytz
            IST = pytz.timezone('Asia/Kolkata')
            e = row.entry_time.astimezone(IST).strftime('%H:%M') if row.entry_time.tzinfo else str(row.entry_time)
            x = row.exit_time.astimezone(IST).strftime('%H:%M') if row.exit_time.tzinfo else str(row.exit_time)
            print(f"  {row.tradingsymbol:25s} {e}->{x} dur={row.duration_minutes}m pnl={row.realized_pnl:.0f}")

    await engine.dispose()

asyncio.run(main())
