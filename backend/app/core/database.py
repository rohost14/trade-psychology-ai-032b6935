from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool
from app.core.config import settings

# Create async engine with settings optimized for Supabase
# Using NullPool to avoid connection pooling issues with Supabase's pooler
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.ENVIRONMENT == "development",  # Only log SQL in dev
    poolclass=NullPool,  # Supabase has its own pooler, avoid double-pooling
    connect_args={
        "server_settings": {
            "application_name": "tradementor_backend"
        },
        "statement_cache_size": 0  # REQUIRED for Supabase Transaction Pooler (PgBouncer)
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
