"""
Shared utilities for validation scenario scripts.
Connects to the same DB as the app using settings from .env
"""

import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

# Add backend root to path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy import select, text

from app.core.config import settings
from app.models.broker_account import BrokerAccount
from app.models.trade import Trade
from app.models.completed_trade import CompletedTrade

# All test data is tagged for easy cleanup
TEST_TAG = "TEST_SCENARIO_VALIDATE"


def make_engine():
    return create_async_engine(
        settings.DATABASE_URL,
        poolclass=NullPool,
        connect_args={"statement_cache_size": 0},
    )


async def get_broker_account_id() -> uuid.UUID:
    """Get the first connected broker account (your real account)."""
    engine = make_engine()
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as db:
        result = await db.execute(
            select(BrokerAccount).where(BrokerAccount.status == "connected")
        )
        account = result.scalars().first()
        if not account:
            print("\n❌  No connected broker account found.")
            print("    Connect Zerodha in the app first, then re-run this script.")
            sys.exit(1)
        print(f"✅  Using broker account: {account.broker_email or account.broker_user_id}")
        print(f"    Account ID: {account.id}")
        await engine.dispose()
        return account.id


def now_ist():
    """Current time as IST-aware datetime."""
    import pytz
    return datetime.now(pytz.timezone("Asia/Kolkata"))


def utc_offset(minutes: int = 0) -> datetime:
    """Return a UTC datetime offset by N minutes from now."""
    return datetime.now(timezone.utc) + timedelta(minutes=minutes)


async def insert_completed_trade(
    db: AsyncSession,
    broker_account_id: uuid.UUID,
    symbol: str,
    exchange: str,
    instrument_type: str,
    direction: str,
    qty: int,
    avg_entry: float,
    avg_exit: float,
    pnl: float,
    entry_offset_min: int,   # minutes ago for entry
    duration_min: int,       # how long the trade lasted
) -> CompletedTrade:
    """Insert one CompletedTrade record. Returns the inserted object."""
    now = datetime.now(timezone.utc)
    entry_time = now + timedelta(minutes=entry_offset_min)
    exit_time = entry_time + timedelta(minutes=duration_min)

    ct = CompletedTrade(
        broker_account_id=broker_account_id,
        tradingsymbol=symbol,
        exchange=exchange,
        instrument_type=instrument_type,
        product="MIS",
        direction=direction,
        total_quantity=qty,
        num_entries=1,
        num_exits=1,
        avg_entry_price=Decimal(str(avg_entry)),
        avg_exit_price=Decimal(str(avg_exit)),
        realized_pnl=Decimal(str(pnl)),
        entry_time=entry_time,
        exit_time=exit_time,
        duration_minutes=duration_min,
        status="closed",
    )
    db.add(ct)
    await db.flush()
    return ct


async def insert_trade(
    db: AsyncSession,
    broker_account_id: uuid.UUID,
    symbol: str,
    exchange: str,
    transaction_type: str,
    qty: int,
    price: float,
    pnl: float,
    offset_min: int,
) -> Trade:
    """
    Insert a Trade record (needed for RiskDetector production pipeline).
    Uses a unique test order_id so it doesn't conflict with real trades.
    """
    order_id = f"TEST_{uuid.uuid4().hex[:12].upper()}"
    order_time = datetime.now(timezone.utc) + timedelta(minutes=offset_min)

    t = Trade(
        broker_account_id=broker_account_id,
        order_id=order_id,
        tradingsymbol=symbol,
        exchange=exchange,
        transaction_type=transaction_type,
        order_type="MARKET",
        product="MIS",
        quantity=qty,
        filled_quantity=qty,
        pending_quantity=0,
        cancelled_quantity=0,
        price=price,
        average_price=price,
        pnl=pnl,
        status="COMPLETE",
        asset_class="FNO",
        instrument_type="FUT",
        product_type="MIS",
        order_timestamp=order_time,
        tag=TEST_TAG,       # ← marks it as test data
        guid=TEST_TAG,      # ← secondary marker
    )
    db.add(t)
    await db.flush()
    return t


def print_banner(script_num: int, title: str):
    print("\n" + "=" * 60)
    print(f"  Script {script_num:02d}: {title}")
    print("=" * 60)


def print_expect(what: str):
    print(f"\n🔔  EXPECT:  {what}")


def print_check(where: str):
    print(f"👁️   CHECK:  {where}")


def print_wait(minutes: int, reason: str = ""):
    msg = f"⏳  WAIT:   {minutes} minute(s) before running next script"
    if reason:
        msg += f" — {reason}"
    print(msg)


def print_done(what_inserted: str):
    print(f"\n✅  INSERTED: {what_inserted}")
