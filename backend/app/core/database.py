from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings

# Connection pool for Supabase via Transaction Pooler (PgBouncer, port 6543).
#
# pool_size=5 / max_overflow=10 → up to 15 connections per process.
# With 50 Celery workers + 1 FastAPI process ≈ 800 connections to PgBouncer,
# which multiplexes to a small set of real Postgres connections — fine at scale.
#
# statement_cache_size=0 is REQUIRED for PgBouncer Transaction Mode: prepared
# statements are session-scoped in Postgres but PgBouncer may route consecutive
# queries to different backend connections, causing "unknown prepared statement" errors.
#
# pool_pre_ping=True: test connection health before use to handle idle-connection
# timeouts from PgBouncer or Supabase's connection limits.
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.ENVIRONMENT == "development",
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_pre_ping=True,
    connect_args={
        "server_settings": {
            "application_name": "tradementor_backend"
        },
        "statement_cache_size": 0,
    }
)

# Create async session factory
SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

class Base(DeclarativeBase):
    pass

async def get_db():
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
