"""
Shared fixtures for DB schema tests.

Each test gets a completely fresh engine + session with NullPool.
This avoids asyncpg connection-loop binding issues entirely.
All writes are rolled back after each test.
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from decimal import Decimal
from datetime import timedelta
from uuid import uuid4

from app.core.config import settings
from app.models.user import User
from app.models.broker_account import BrokerAccount
from app.models.trade import Trade
from app.models.completed_trade import CompletedTrade
from app.models.risk_alert import RiskAlert
from tests.helpers import now_utc, make_email


def make_engine():
    """Fresh engine per test. NullPool = no connection reuse across async contexts."""
    return create_async_engine(
        settings.DATABASE_URL,
        poolclass=NullPool,
        connect_args={"statement_cache_size": 0},
        echo=False,
    )


@pytest_asyncio.fixture
async def db():
    """
    Yields a fresh AsyncSession for each test.
    Rolls back all changes on teardown — nothing persists to the DB.
    """
    engine = make_engine()
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        yield session
        await session.rollback()
    await engine.dispose()


# ── Object fixtures ───────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def user(db):
    u = User(
        email=make_email(),
        display_name="QA Trader",
        guardian_phone="+919999000001",
    )
    db.add(u)
    await db.flush()
    return u


@pytest_asyncio.fixture
async def broker(db, user):
    ba = BrokerAccount(
        user_id=user.id,
        broker_name="zerodha",
        broker_email=user.email,
        broker_user_id="QA1234",
        status="connected",
    )
    db.add(ba)
    await db.flush()
    return ba


@pytest_asyncio.fixture
async def trade(db, broker):
    t = Trade(
        broker_account_id=broker.id,
        order_id=f"TEST_{uuid4().hex[:8]}",
        tradingsymbol="INFY",
        exchange="NSE",
        transaction_type="BUY",
        order_type="MARKET",
        product="MIS",
        quantity=10,
        status="COMPLETE",
        asset_class="EQUITY",
        instrument_type="EQ",
        product_type="MIS",
    )
    db.add(t)
    await db.flush()
    return t


@pytest_asyncio.fixture
async def completed_trade(db, broker):
    ct = CompletedTrade(
        broker_account_id=broker.id,
        tradingsymbol="INFY",
        exchange="NSE",
        instrument_type="EQ",
        product="MIS",
        direction="LONG",
        total_quantity=10,
        num_entries=1,
        num_exits=1,
        avg_entry_price=Decimal("1500.00"),
        avg_exit_price=Decimal("1520.00"),
        realized_pnl=Decimal("200.00"),
        entry_time=now_utc() - timedelta(hours=2),
        exit_time=now_utc() - timedelta(hours=1),
        duration_minutes=60,
        status="closed",
    )
    db.add(ct)
    await db.flush()
    return ct


@pytest_asyncio.fixture
async def risk_alert(db, broker, trade):
    ra = RiskAlert(
        broker_account_id=broker.id,
        pattern_type="revenge_trading",
        severity="danger",
        message="TEST: Revenge trading detected",
        trigger_trade_id=trade.id,
    )
    db.add(ra)
    await db.flush()
    return ra
