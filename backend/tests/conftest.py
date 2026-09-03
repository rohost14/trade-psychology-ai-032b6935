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
from app.core.database import Base
from app.models.user import User
from app.models.broker_account import BrokerAccount
from app.models.trade import Trade
from app.models.completed_trade import CompletedTrade
from app.models.risk_alert import RiskAlert
# Import all models so Base.metadata is fully populated before create_all
import app.models  # noqa: F401
from tests.helpers import now_utc, make_email


#: Hosts/databases the suite must NEVER be pointed at. A test that issues a bad
#: DELETE or UPDATE against the real application database destroys real trader
#: data, and nothing in the suite currently prevents that - the tests use
#: `settings.DATABASE_URL`, the same URL the application runs on.
#:
#: FAIL CLOSED. This refuses to build an engine unless the target is explicitly
#: marked as a test database, rather than trying to enumerate every production
#: host. An unrecognised database is treated as production, because the failure
#: mode of guessing wrong in the other direction is unrecoverable.
#:
#: Opt in either by pointing TEST_DATABASE_URL at a dedicated database, or by
#: setting ALLOW_TESTS_ON_THIS_DB=1 when you genuinely mean the current one.
_TEST_DB_MARKERS = ("test", "_test", "localhost", "127.0.0.1")


def _assert_safe_test_database(url: str) -> None:
    import os

    if os.getenv("ALLOW_TESTS_ON_THIS_DB") == "1":
        return
    lowered = (url or "").lower()
    if any(marker in lowered for marker in _TEST_DB_MARKERS):
        return
    raise RuntimeError(
        chr(10).join((
            "REFUSING to run tests against this database.",
            "",
            "  The suite writes and deletes rows. The configured DATABASE_URL",
            "  is not recognisable as a test database, so it is treated as",
            "  production.",
            "",
            "  Fix one of:",
            "    * set TEST_DATABASE_URL to a dedicated test database",
            "    * name the database with a 'test' marker",
            "    * export ALLOW_TESTS_ON_THIS_DB=1 if you really mean this one",
        ))
    )


def test_database_url() -> str:
    """The URL the suite runs against — TEST_DATABASE_URL wins when present."""
    import os

    url = os.getenv("TEST_DATABASE_URL") or settings.DATABASE_URL
    _assert_safe_test_database(url)
    return url


def make_engine():
    """Fresh engine per test. NullPool = no connection reuse across async contexts."""
    return create_async_engine(
        test_database_url(),
        poolclass=NullPool,
        connect_args={"statement_cache_size": 0},
        echo=False,
    )


@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_tables():
    """Create all tables once per test session from SQLAlchemy models.

    CI starts with a blank database — migrations are Supabase-only.
    This replaces the migration step for the test environment.
    """
    # This fixture exists ONLY to bootstrap a BLANK CI database (migrations are
    # Supabase-only). Local dev runs against live Supabase where the schema
    # already exists — and this fixture's dedicated NullPool engine has been
    # observed to hang into the 2-min statement timeout there, erroring every
    # test at setup. Skip it entirely unless we are actually in CI.
    import os
    if os.getenv("CI", "").lower() not in ("1", "true"):
        return

    engine = create_async_engine(
        test_database_url(),
        poolclass=NullPool,
        connect_args={"statement_cache_size": 0},
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()


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
