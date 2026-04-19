"""
Clean up all seed/test data from the DB.
Real broker account: d5cf0bf0-f664-460d-a2b7-4606466e4530
"""
import asyncio
import logging
logging.disable(logging.CRITICAL)

REAL_BROKER_ID = 'd5cf0bf0-f664-460d-a2b7-4606466e4530'

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
        async with conn.begin():
            tables = ['completed_trades', 'trades', 'positions', 'risk_alerts']
            for table in tables:
                try:
                    r = await conn.execute(text(
                        f"DELETE FROM {table} WHERE broker_account_id != :real_id"
                    ), {"real_id": REAL_BROKER_ID})
                    print(f"Deleted {r.rowcount:3d} rows from {table}")
                except Exception as e:
                    print(f"{table}: ERROR — {e}")

            try:
                r = await conn.execute(text(
                    "DELETE FROM broker_accounts WHERE id != :real_id"
                ), {"real_id": REAL_BROKER_ID})
                print(f"Deleted {r.rowcount:3d} rows from broker_accounts")
            except Exception as e:
                print(f"broker_accounts: ERROR — {e}")

        print("\nVerification — rows remaining:")
        for table in ['completed_trades', 'trades', 'positions', 'risk_alerts', 'broker_accounts']:
            try:
                r = await conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                print(f"  {table:20s}: {r.scalar()}")
            except Exception as e:
                print(f"  {table:20s}: {e}")

    await engine.dispose()

asyncio.run(main())
