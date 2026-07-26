"""
Database Connection Test Script
Run with: python test_db_connection.py
"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

async def test_connection():
    print("=" * 50)
    print("DATABASE CONNECTION TEST")
    print("=" * 50)

    # 1. Load config
    print("\n[1] Loading configuration...")
    try:
        from app.core.config import settings

        # Mask password in URL for display
        db_url = settings.DATABASE_URL
        if "@" in db_url:
            parts = db_url.split("@")
            masked = parts[0].rsplit(":", 1)[0] + ":****@" + parts[1]
        else:
            masked = db_url
        print(f"    DATABASE_URL: {masked}")
        print("    ✓ Config loaded")
    except Exception as e:
        print(f"    ✗ Config error: {e}")
        return False

    # 2. Test asyncpg directly (bypasses SQLAlchemy)
    print("\n[2] Testing direct asyncpg connection...")
    try:
        import asyncpg

        # Convert SQLAlchemy URL to asyncpg format
        url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

        conn = await asyncpg.connect(url, timeout=10)
        version = await conn.fetchval("SELECT version()")
        print(f"    PostgreSQL: {version[:50]}...")
        await conn.close()
        print("    ✓ Direct connection works")
    except Exception as e:
        print(f"    ✗ Direct connection failed: {e}")
        print("\n    TROUBLESHOOTING:")
        print("    - Use Supabase 'Session pooler' connection string (port 5432)")
        print("    - Or try 'Transaction pooler' (port 6543)")
        print("    - Make sure password has no special chars or URL-encode them")
        print("    - Check if your IP is allowed in Supabase dashboard")
        return False

    # 3. Test SQLAlchemy engine
    print("\n[3] Testing SQLAlchemy async engine...")
    try:
        from sqlalchemy import text
        from app.core.database import engine

        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT current_database(), current_user"))
            row = result.fetchone()
            print(f"    Database: {row[0]}, User: {row[1]}")
        print("    ✓ SQLAlchemy engine works")
    except Exception as e:
        print(f"    ✗ SQLAlchemy error: {e}")
        return False

    # 4. Test tables exist
    print("\n[4] Checking tables...")
    try:
        from sqlalchemy import text
        from app.core.database import engine

        async with engine.connect() as conn:
            result = await conn.execute(text("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_type = 'BASE TABLE'
            """))
            tables = [row[0] for row in result.fetchall()]

        required = ['broker_accounts', 'trades', 'positions', 'risk_alerts']
        missing = [t for t in required if t not in tables]

        print(f"    Found tables: {tables}")
        if missing:
            print(f"    ✗ Missing tables: {missing}")
            print("    Run the SQL schema in Supabase SQL Editor")
            return False
        else:
            print("    ✓ All required tables exist")
    except Exception as e:
        print(f"    ✗ Table check error: {e}")
        return False

    # 5. Test write operation
    print("\n[5] Testing write operation...")
    try:
        from sqlalchemy import text
        from app.core.database import SessionLocal

        async with SessionLocal() as session:
            # Try to insert and rollback
            await session.execute(text("""
                INSERT INTO broker_accounts (id, status)
                VALUES (gen_random_uuid(), 'test')
            """))
            await session.rollback()  # Don't actually save
        print("    ✓ Write permission OK")
    except Exception as e:
        print(f"    ✗ Write error: {e}")
        print("    Check RLS is disabled on tables")
        return False

    print("\n" + "=" * 50)
    print("ALL TESTS PASSED ✓")
    print("=" * 50)
    return True

if __name__ == "__main__":
    success = asyncio.run(test_connection())
    sys.exit(0 if success else 1)
