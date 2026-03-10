"""
Shared utilities for validation scenario scripts.
Uses raw asyncpg (no ORM) — direct SQL, no mapping issues.
"""

import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

# Add backend root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import asyncpg
from app.core.config import settings

# All test data tagged for cleanup (must be <= 20 chars — trades.tag VARCHAR(20))
TEST_TAG = "TEST_SCENARIO"


def _pg_url() -> str:
    """Convert asyncpg-compatible URL from SQLAlchemy DATABASE_URL."""
    url = settings.DATABASE_URL
    # SQLAlchemy uses postgresql+asyncpg:// — asyncpg needs postgresql://
    url = url.replace("postgresql+asyncpg://", "postgresql://")
    return url


async def get_connection():
    """Get a raw asyncpg connection."""
    return await asyncpg.connect(_pg_url(), statement_cache_size=0)


async def get_broker_account_id() -> str:
    """
    Get the broker account ID to use for test data.
    Shows all connected accounts and asks you to pick — no wrong account inserts.
    Returns account ID as string.
    """
    conn = await get_connection()
    try:
        rows = await conn.fetch(
            """
            SELECT id, broker_user_id, broker_email, connected_at
            FROM broker_accounts
            WHERE status = 'connected'
            ORDER BY connected_at DESC
            """
        )
    finally:
        await conn.close()

    # Filter out test accounts from the test suite
    # Real Zerodha accounts have proper emails and user IDs, not qa.internal
    real_accounts = [
        r for r in rows
        if not (r['broker_email'] or '').endswith('@qa.internal')
        and not (r['broker_user_id'] or '').startswith('QA')
        and r['broker_user_id'] is not None
    ]

    if not real_accounts:
        print("\n❌  No real connected broker account found.")
        print("    Connect Zerodha in the app first.")
        sys.exit(1)

    if len(real_accounts) == 1:
        row = real_accounts[0]
        print(f"✅  Using: {row['broker_email'] or row['broker_user_id']}")
        print(f"    Account ID: {row['id']}")
        return str(row['id'])

    print(f"\n⚠️   Found {len(real_accounts)} real accounts. Pick your Zerodha account:")
    for i, row in enumerate(real_accounts):
        print(f"    [{i+1}] {row['broker_email'] or row['broker_user_id']}  (ID: {row['id']})")

    while True:
        choice = input(f"\nEnter number [1-{len(real_accounts)}]: ").strip()
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(real_accounts):
                row = real_accounts[idx]
                print(f"✅  Using: {row['broker_email'] or row['broker_user_id']}")
                return str(row['id'])
        except ValueError:
            pass
        print(f"    Enter a number between 1 and {len(real_accounts)}")


async def insert_completed_trade(
    conn,
    broker_account_id: str,
    symbol: str,
    exchange: str,
    instrument_type: str,
    direction: str,
    qty: int,
    avg_entry: float,
    avg_exit: float,
    pnl: float,
    entry_offset_min: int,
    duration_min: int,
) -> str:
    """Insert one CompletedTrade via raw SQL. Returns the new ID."""
    now = datetime.now(timezone.utc)
    entry_time = now + timedelta(minutes=entry_offset_min)
    exit_time = entry_time + timedelta(minutes=duration_min)
    ct_id = str(uuid.uuid4())

    await conn.execute(
        """
        INSERT INTO completed_trades (
            id, broker_account_id, tradingsymbol, exchange,
            instrument_type, product, direction,
            total_quantity, num_entries, num_exits,
            avg_entry_price, avg_exit_price, realized_pnl,
            entry_time, exit_time, duration_minutes,
            closed_by_flip, status, created_at, updated_at
        ) VALUES (
            $1, $2, $3, $4,
            $5, $6, $7,
            $8, $9, $10,
            $11, $12, $13,
            $14, $15, $16,
            false, 'closed', now(), now()
        )
        """,
        ct_id, broker_account_id, symbol, exchange,
        instrument_type, "MIS", direction,
        qty, 1, 1,
        avg_entry, avg_exit, pnl,
        entry_time, exit_time, duration_min,
    )
    print(f"   → CompletedTrade: {symbol} {direction} qty={qty} pnl=₹{pnl:,.0f}")
    return ct_id


async def insert_trade(
    conn,
    broker_account_id: str,
    symbol: str,
    exchange: str,
    transaction_type: str,
    qty: int,
    price: float,
    pnl: float,
    offset_min: int,
) -> str:
    """Insert one Trade (raw fill) via raw SQL. Returns the new ID."""
    order_id = f"TEST_{uuid.uuid4().hex[:12].upper()}"
    trade_id = str(uuid.uuid4())
    order_time = datetime.now(timezone.utc) + timedelta(minutes=offset_min)

    await conn.execute(
        """
        INSERT INTO trades (
            id, broker_account_id, order_id, tradingsymbol, exchange,
            transaction_type, order_type, product,
            quantity, filled_quantity, pending_quantity, cancelled_quantity,
            price, average_price, pnl,
            status, asset_class, instrument_type, product_type,
            tag, guid, order_timestamp, created_at, updated_at
        ) VALUES (
            $1, $2, $3, $4, $5,
            $6, $7, $8,
            $9, $9, 0, 0,
            $10, $10, $11,
            'COMPLETE', 'FNO', 'FUT', 'MIS',
            $12, $12, $13, now(), now()
        )
        """,
        trade_id, broker_account_id, order_id, symbol, exchange,
        transaction_type, "MARKET", "MIS",
        qty,
        price, pnl,
        TEST_TAG, order_time,
    )
    print(f"   → Trade: {symbol} {transaction_type} qty={qty} @ ₹{price:,.0f}")
    return trade_id


async def trigger_detection(broker_account_id: str):
    """
    Trigger backend risk detection after inserting test data.
    This is what webhooks normally do — runs RiskDetector + BehavioralEvaluator
    so alerts appear in the dashboard alerts panel.
    """
    from uuid import UUID
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from sqlalchemy.pool import NullPool

    engine = create_async_engine(
        settings.DATABASE_URL,
        poolclass=NullPool,
        connect_args={"statement_cache_size": 0},
    )
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as db:
        try:
            from app.tasks.trade_tasks import run_risk_detection_async
            print("   → Triggering backend behavioral detection...")
            await run_risk_detection_async(UUID(broker_account_id), db)
            print("   → Detection complete. Check Alerts panel.")
        except Exception as e:
            print(f"   ⚠️  Detection error (non-fatal): {e}")

    await engine.dispose()


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
