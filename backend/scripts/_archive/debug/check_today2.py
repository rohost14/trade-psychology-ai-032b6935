"""Check broker_account_id on seed vs real trades."""
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

    engine = create_async_engine(
        settings.DATABASE_URL, echo=False,
        connect_args={"statement_cache_size": 0},
    )
    async with engine.connect() as conn:
        # broker_account_id distribution
        r = await conn.execute(text("""
            SELECT broker_account_id, COUNT(*) as cnt,
                   ROUND(AVG(duration_minutes)) as avg_dur,
                   MIN(tradingsymbol) as sample
            FROM completed_trades
            GROUP BY broker_account_id
            ORDER BY cnt DESC
        """))
        print("Trades by broker_account_id:")
        for row in r.fetchall():
            print(f"  broker_account_id={row.broker_account_id}  cnt={row.cnt}  avg_dur={row.avg_dur}m  sample={row.sample}")

        # Today's alerts with full details
        r2 = await conn.execute(text("""
            SELECT pattern_type, severity, message, created_at
            FROM risk_alerts
            WHERE created_at >= NOW() - INTERVAL '24 hours'
            ORDER BY created_at
        """))
        print("\nAlerts in last 24h:")
        for a in r2.fetchall():
            import pytz
            IST = pytz.timezone('Asia/Kolkata')
            t_ist = a.created_at.astimezone(IST).strftime('%H:%M IST') if hasattr(a.created_at, 'astimezone') else str(a.created_at)
            print(f"  [{a.severity:8s}] {a.pattern_type:30s} at {t_ist}")
            print(f"    {a.message[:100]}")

    await engine.dispose()

asyncio.run(main())
