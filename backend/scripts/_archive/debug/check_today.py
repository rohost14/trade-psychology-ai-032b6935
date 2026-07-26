"""Check today's trades and why alerts might not have fired."""
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
        # Latest completed trades
        r = await conn.execute(text("""
            SELECT tradingsymbol, direction, total_quantity,
                   avg_entry_price, avg_exit_price, realized_pnl,
                   entry_time, exit_time, duration_minutes, exchange
            FROM completed_trades
            ORDER BY exit_time DESC
            LIMIT 15
        """))
        rows = r.fetchall()
        print(f"Latest 15 completed trades:")
        for row in rows:
            print(f"  {row.tradingsymbol:25s} pnl={row.realized_pnl:+.0f}  exit={str(row.exit_time)[:16]}")

        # Latest alerts
        print()
        r2 = await conn.execute(text("""
            SELECT pattern_type, severity, message, created_at
            FROM risk_alerts
            ORDER BY created_at DESC
            LIMIT 10
        """))
        alerts = r2.fetchall()
        print(f"Latest alerts ({len(alerts)}):")
        for a in alerts:
            print(f"  [{a.severity:8s}] {a.pattern_type:30s} at {str(a.created_at)[:16]}")

        # Raw trades (order fills) today
        r3 = await conn.execute(text("""
            SELECT tradingsymbol, transaction_type, quantity, price, exchange_timestamp
            FROM trades
            ORDER BY exchange_timestamp DESC
            LIMIT 20
        """))
        print("\nLatest raw order fills:")
        for row in r3.fetchall():
            print(f"  {row.tradingsymbol:25s} {row.transaction_type:4s} qty={row.quantity:4d} px={row.price:.1f} at {str(row.exchange_timestamp)[:16]}")

    await engine.dispose()

asyncio.run(main())
