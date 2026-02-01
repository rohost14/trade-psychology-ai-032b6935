import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)

async def check_connection():
    with open('connection_info.txt', 'w', encoding='utf-8') as f:
        f.write("=== DATABASE CONNECTION INFO ===\n\n")
        
        # Show DATABASE_URL (partially obscured)
        db_url = str(settings.DATABASE_URL)
        f.write(f"1. DATABASE_URL from .env:\n")
        if '@' in db_url:
            protocol_user = db_url.split('@')[0]
            host_db = db_url.split('@')[1]
            protocol = protocol_user.split(':')[0]
            f.write(f"   Protocol: {protocol}\n")
            f.write(f"   Host/DB: {host_db}\n")
        else:
            f.write(f"   {db_url}\n")
        
        f.write(f"\n2. Connection test:\n")
        try:
            async with engine.connect() as conn:
                # Get PostgreSQL version
                result = await conn.execute(text("SELECT version()"))
                version = result.scalar()
                f.write(f"   PostgreSQL version: {version[:80]}...\n\n")
                
                # Get current database name
                result = await conn.execute(text("SELECT current_database()"))
                db_name = result.scalar()
                f.write(f"   Current database: {db_name}\n\n")
                
                # List all tables
                result = await conn.execute(text("""
                    SELECT table_name FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    ORDER BY table_name
                """))
                tables = [row[0] for row in result.fetchall()]
                f.write(f"   Tables in this database: {tables}\n\n")
                
                # Count positions
                result = await conn.execute(text("SELECT COUNT(*) FROM positions"))
                count = result.scalar()
                f.write(f"   Total positions in this DB: {count}\n")
                
                if count > 0:
                    result = await conn.execute(text("SELECT broker_account_id, COUNT(*) FROM positions GROUP BY broker_account_id"))
                    f.write(f"\n   Positions by broker_account_id:\n")
                    for row in result.fetchall():
                        f.write(f"     - {row[0]}: {row[1]} positions\n")
                
        except Exception as e:
            f.write(f"   ERROR: {e}\n")

if __name__ == "__main__":
    asyncio.run(check_connection())
