import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)

async def investigate():
    with open('investigation.txt', 'w', encoding='utf-8') as f:
        try:
            async with engine.connect() as conn:
                f.write("=== DATABASE INVESTIGATION ===\n\n")
                
                # 1. List all tables
                f.write("1. ALL TABLES IN DATABASE:\n")
                result = await conn.execute(text("""
                    SELECT table_name FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    ORDER BY table_name
                """))
                tables = [row[0] for row in result.fetchall()]
                f.write(f"   Tables found: {tables}\n\n")
                
                # 2. Check positions table columns
                f.write("2. COLUMNS IN 'positions' TABLE:\n")
                result = await conn.execute(text("""
                    SELECT column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_name = 'positions'
                    ORDER BY ordinal_position
                """))
                columns = result.fetchall()
                for col in columns:
                    f.write(f"   - {col[0]} ({col[1]})\n")
                
                # 3. Check if total_quantity exists
                has_total_quantity = any(col[0] == 'total_quantity' for col in columns)
                f.write(f"\n   ✓ Has 'total_quantity' column: {has_total_quantity}\n")
                
                # 4. Show DATABASE_URL (obscured)
                f.write(f"\n3. DATABASE URL:\n")
                db_url = settings.DATABASE_URL
                # Hide password
                if '@' in db_url:
                    parts = db_url.split('@')
                    f.write(f"   {parts[0].split(':')[0]}://***@{parts[1]}\n")
                else:
                    f.write(f"   {db_url}\n")
                
                # 5. Count positions records
                f.write(f"\n4. POSITIONS TABLE DATA:\n")
                result = await conn.execute(text("SELECT COUNT(*) FROM positions"))
                count = result.scalar()
                f.write(f"   Total records: {count}\n")
                
                if count > 0:
                    result = await conn.execute(text("SELECT status, COUNT(*) FROM positions GROUP BY status"))
                    f.write(f"\n   Breakdown by status:\n")
                    for row in result.fetchall():
                        f.write(f"     - {row[0]}: {row[1]}\n")
                
        except Exception as e:
            f.write(f"\nERROR: {e}\n")

if __name__ == "__main__":
    asyncio.run(investigate())
