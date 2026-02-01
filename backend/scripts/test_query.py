import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=True)

async def test_query():
    broker_id = '550e8400-e29b-41d4-a716-446655440000'
    
    with open('query_test.txt', 'w', encoding='utf-8') as f:
        async with engine.connect() as conn:
            # Test 1: Count all positions for this broker
            f.write("Test 1: Count all positions for broker_account_id\n")
            result = await conn.execute(text("""
                SELECT COUNT(*) FROM positions 
                WHERE broker_account_id = :id
            """), {'id': broker_id})
            count = result.scalar()
            f.write(f"  Total positions: {count}\n\n")
            
            # Test 2: Count by status
            f.write("Test 2: Count by status\n")
            result = await conn.execute(text("""
                SELECT status, COUNT(*) FROM positions 
                WHERE broker_account_id = :id
                GROUP BY status
            """), {'id': broker_id})
            for row in result.fetchall():
                f.write(f"  status='{row[0]}': {row[1]}\n")
            f.write("\n")
            
            # Test 3: Query with status='open'
            f.write("Test 3: Query with status='open' (exact match)\n")
            result = await conn.execute(text("""
                SELECT id, tradingsymbol, status FROM positions 
                WHERE broker_account_id = :id AND status = 'open'
            """), {'id': broker_id})
            rows = result.fetchall()
            f.write(f"  Found {len(rows)} records\n")
            for row in rows:
                f.write(f"    - {row[1]} (status='{row[2]}')\n")
            f.write("\n")
            
            # Test 4: Using SQLAlchemy ORM
            f.write("Test 4: Using SQLAlchemy ORM (like the API does)\n")
            from app.models.position import Position
            from sqlalchemy import select
            from sqlalchemy.ext.asyncio import AsyncSession
            
            async with AsyncSession(engine) as session:
                result = await session.execute(
                    select(Position).where(
                        Position.broker_account_id == broker_id,
                        Position.status == 'open'
                    )
                )
                positions = result.scalars().all()
                f.write(f"  Found {len(positions)} positions\n")
                for p in positions:
                    f.write(f"    - {p.tradingsymbol} (status='{p.status}')\n")

if __name__ == "__main__":
    asyncio.run(test_query())
