import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool
from app.core.config import settings

# Connection pool for Supabase via Transaction Pooler (PgBouncer, port 6543).
#
# statement_cache_size=0 is REQUIRED for PgBouncer Transaction Mode: prepared
# statements are session-scoped in Postgres but PgBouncer may route consecutive
# queries to different backend connections, causing "unknown prepared statement" errors.
#
# pool_pre_ping=True: test connection health before use to handle idle-connection
# timeouts from PgBouncer or Supabase's connection limits.
#
# R1: the Celery worker (prefork) runs each task via asyncio.run() — a FRESH event
# loop per task. asyncpg connections are bound to the loop that created them, so a
# pooled connection from a previous task's loop is invalid in the next ("attached to
# a different loop"). In the worker we therefore use NullPool (open+close per
# checkout, no cross-loop reuse, no pool_timeout starvation under burst). The
# web/FastAPI process keeps a real pool (one long-lived loop). Selected via the
# CELERY_WORKER env flag set in the Procfile worker command.
_IS_CELERY_WORKER = os.environ.get("CELERY_WORKER") == "1"

_engine_kwargs = dict(
    echo=settings.ENVIRONMENT == "development",
    pool_pre_ping=True,
    connect_args={
        "server_settings": {"application_name": "tradementor_backend"},
        "statement_cache_size": 0,
    },
)
if _IS_CELERY_WORKER:
    _engine_kwargs["poolclass"] = NullPool
else:
    # pool_size=5 / max_overflow=10 → up to 15 connections per web process.
    _engine_kwargs.update(pool_size=5, max_overflow=10, pool_timeout=30)

engine = create_async_engine(settings.DATABASE_URL, **_engine_kwargs)

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
