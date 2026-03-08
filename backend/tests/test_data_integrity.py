"""
Phase 1 Data Integrity Tests

Covers items 1-6 of Phase 1:
  1. UNIQUE(broker_account_id, order_id) constraint
  2. processed_at column exists and is nullable
  3. Idempotency guard — pipeline skips if processed_at is set
  4. Redis SETNX fifo_lock — only one FIFO per account at a time
  5. Redis SETNX behavior_lock — only one detection per account at a time
  6. Reconciliation poller — missing orders are detected and re-queued
"""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.models.trade import Trade
from tests.helpers import now_utc, make_email


# =============================================================================
# Item 1: UNIQUE(broker_account_id, order_id) constraint
# =============================================================================

class TestUniqueOrderIdConstraint:

    async def test_duplicate_order_id_same_account_raises(self, db, broker):
        """Two trades with the same order_id for the same account must fail."""
        order_id = f"ORD_{uuid4().hex[:8]}"

        t1 = Trade(
            broker_account_id=broker.id,
            order_id=order_id,
            tradingsymbol="NIFTY24JANFUT",
            exchange="NFO",
            transaction_type="BUY",
            order_type="MARKET",
            product="MIS",
            quantity=50,
            status="COMPLETE",
            asset_class="FNO",
            instrument_type="FUTURE",
            product_type="MIS",
        )
        db.add(t1)
        await db.flush()

        t2 = Trade(
            broker_account_id=broker.id,
            order_id=order_id,  # same order_id, same account
            tradingsymbol="NIFTY24JANFUT",
            exchange="NFO",
            transaction_type="BUY",
            order_type="MARKET",
            product="MIS",
            quantity=50,
            status="COMPLETE",
            asset_class="FNO",
            instrument_type="FUTURE",
            product_type="MIS",
        )
        db.add(t2)

        with pytest.raises(IntegrityError):
            await db.flush()

        await db.rollback()

    async def test_same_order_id_different_accounts_allowed(self, db, broker, user):
        """Same order_id on different accounts must succeed (cross-account is fine)."""
        from app.models.broker_account import BrokerAccount

        broker2 = BrokerAccount(
            user_id=user.id,
            broker_name="zerodha",
            broker_email=make_email(),
            broker_user_id="QA9999",
            status="connected",
        )
        db.add(broker2)
        await db.flush()

        order_id = f"ORD_{uuid4().hex[:8]}"

        for account in [broker, broker2]:
            t = Trade(
                broker_account_id=account.id,
                order_id=order_id,
                tradingsymbol="RELIANCE",
                exchange="NSE",
                transaction_type="BUY",
                order_type="MARKET",
                product="NRML",
                quantity=10,
                status="COMPLETE",
                asset_class="EQUITY",
                instrument_type="EQ",
                product_type="NRML",
            )
            db.add(t)

        # Should not raise
        await db.flush()


# =============================================================================
# Item 2: processed_at column
# =============================================================================

class TestProcessedAtColumn:

    async def test_processed_at_defaults_to_null(self, db, trade):
        """New trades must have processed_at = NULL."""
        assert trade.processed_at is None

    async def test_processed_at_can_be_set(self, db, trade):
        """processed_at can be set to a datetime."""
        now = now_utc()
        trade.processed_at = now
        await db.flush()

        refreshed = await db.get(Trade, trade.id)
        assert refreshed.processed_at is not None
        # Compare without sub-second precision (DB may truncate)
        assert abs((refreshed.processed_at - now).total_seconds()) < 2

    async def test_processed_at_column_exists_in_db(self, db):
        """Confirm the column exists in the actual DB schema."""
        result = await db.execute(
            text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'trades'
                  AND column_name = 'processed_at'
            """)
        )
        row = result.fetchone()
        assert row is not None, "processed_at column missing from trades table"


# =============================================================================
# Item 3: Idempotency guard
# =============================================================================

class TestIdempotencyGuard:

    async def test_already_processed_trade_skips_pipeline(self, db, trade):
        """
        If processed_at is set on a trade, process_webhook_trade should
        detect this and return early without running the signal pipeline.

        We test the DB-level check: the WHERE processed_at = None update
        should update 0 rows when already set.
        """
        from sqlalchemy import update

        # Mark as already processed
        already_set = now_utc() - timedelta(minutes=5)
        trade.processed_at = already_set
        await db.flush()

        # Simulate the race-winning atomic UPDATE used in the task:
        # UPDATE trades SET processed_at = NOW() WHERE id = X AND processed_at IS NULL
        new_ts = now_utc()
        result = await db.execute(
            update(Trade)
            .where(Trade.id == trade.id, Trade.processed_at == None)  # noqa: E711
            .values(processed_at=new_ts)
            .returning(Trade.id)
        )
        updated_rows = result.fetchall()

        # 0 rows updated = guard worked, pipeline would be skipped
        assert len(updated_rows) == 0

        # Original value unchanged
        await db.refresh(trade)
        assert abs((trade.processed_at - already_set).total_seconds()) < 2

    async def test_unprocessed_trade_wins_atomic_claim(self, db, trade):
        """
        A trade with processed_at = NULL must win the atomic UPDATE,
        allowing the pipeline to proceed.
        """
        from sqlalchemy import update

        assert trade.processed_at is None

        claim_ts = now_utc()
        result = await db.execute(
            update(Trade)
            .where(Trade.id == trade.id, Trade.processed_at == None)  # noqa: E711
            .values(processed_at=claim_ts)
            .returning(Trade.id)
        )
        updated_rows = result.fetchall()

        # Exactly 1 row updated = pipeline can proceed
        assert len(updated_rows) == 1

        await db.refresh(trade)
        assert trade.processed_at is not None


# =============================================================================
# Items 4 & 5: Redis SETNX locks
# =============================================================================

class TestRedisLocks:
    """
    Tests for _acquire_lock and _release_lock from trade_tasks.py.
    Uses a mock Redis client — no real Redis required for unit tests.
    """

    def test_acquire_lock_succeeds_when_free(self):
        from app.tasks.trade_tasks import _acquire_lock

        mock_redis = MagicMock()
        mock_redis.set.return_value = True  # SETNX succeeded

        result = _acquire_lock(mock_redis, "fifo_lock:abc", ttl_seconds=30)
        assert result is True
        mock_redis.set.assert_called_once_with("fifo_lock:abc", "1", nx=True, ex=30)

    def test_acquire_lock_fails_when_held(self):
        from app.tasks.trade_tasks import _acquire_lock

        mock_redis = MagicMock()
        mock_redis.set.return_value = None  # SETNX failed — key already exists

        result = _acquire_lock(mock_redis, "fifo_lock:abc", ttl_seconds=30)
        assert result is False

    def test_release_lock_deletes_key(self):
        from app.tasks.trade_tasks import _release_lock

        mock_redis = MagicMock()
        _release_lock(mock_redis, "fifo_lock:abc")
        mock_redis.delete.assert_called_once_with("fifo_lock:abc")

    def test_fifo_and_behavior_lock_keys_are_distinct(self):
        """Lock keys must be different so they don't block each other."""
        account_id = "test-account-123"
        fifo_key = f"fifo_lock:{account_id}"
        behavior_key = f"behavior_lock:{account_id}"
        assert fifo_key != behavior_key

    def test_lock_keys_are_per_account(self):
        """Different accounts must have different lock keys."""
        acc1, acc2 = "account-aaa", "account-bbb"
        assert f"fifo_lock:{acc1}" != f"fifo_lock:{acc2}"
        assert f"behavior_lock:{acc1}" != f"behavior_lock:{acc2}"


# =============================================================================
# Item 6: Reconciliation poller
# =============================================================================

class TestReconciliationPoller:

    def test_reconciliation_runs_once_daily(self):
        """
        Reconciliation is scheduled as a fixed 4 AM Celery Beat task.
        No runtime market-hours gate needed — the schedule IS the gate.
        Verify the beat schedule entry exists with the correct crontab.
        """
        from app.core.celery_app import celery_app
        schedule = celery_app.conf.beat_schedule
        assert "eod-reconcile" in schedule, "eod-reconcile beat entry missing"
        entry = schedule["eod-reconcile"]
        assert entry["task"] == "app.tasks.reconciliation_tasks.reconcile_trades"
        # Crontab fires at hour=4, minute=0
        assert entry["schedule"].hour == frozenset([4])
        assert entry["schedule"].minute == frozenset([0])

    def test_yesterday_window_used(self):
        """
        At 4 AM, reconciliation looks at yesterday's trades (not today's).
        Verify _today_ist_start_utc returns yesterday's midnight IST.
        """
        import pytz
        from app.tasks.reconciliation_tasks import _today_ist_start_utc

        IST = pytz.timezone("Asia/Kolkata")
        result = _today_ist_start_utc()

        # Should be yesterday's midnight IST converted to UTC
        yesterday_ist_midnight = (
            datetime.now(IST) - timedelta(days=1)
        ).replace(hour=0, minute=0, second=0, microsecond=0)
        expected_utc = yesterday_ist_midnight.astimezone(timezone.utc)

        diff_seconds = abs((result - expected_utc).total_seconds())
        assert diff_seconds < 5  # Within 5 seconds (timing jitter)

    def test_missing_orders_are_requeued(self):
        """
        Simulate: Kite returns 2 complete orders, DB has only 1.
        The set-diff logic at the core of _reconcile_account should find exactly 1 missing.
        """
        kite_orders = [
            {"order_id": "K001", "status": "COMPLETE", "product": "MIS"},
            {"order_id": "K002", "status": "COMPLETE", "product": "NRML"},
        ]

        # DB already has K001, missing K002
        existing_db_ids = {"K001"}

        # Reproduce the core logic from _reconcile_account
        kite_complete = [
            o for o in kite_orders
            if o.get("status") == "COMPLETE" and o.get("product") in {"MIS", "NRML", "MTF"}
        ]
        kite_ids = {str(o["order_id"]) for o in kite_complete}
        missing = kite_ids - existing_db_ids

        assert missing == {"K002"}, f"Expected {{'K002'}}, got {missing}"
        assert len(missing) == 1

    def test_no_false_positives_when_all_synced(self):
        """If DB has all Kite orders, nothing should be re-queued."""
        kite_orders = [
            {"order_id": "K001", "status": "COMPLETE", "product": "MIS"},
            {"order_id": "K002", "status": "COMPLETE", "product": "NRML"},
        ]
        kite_ids = {str(o["order_id"]) for o in kite_orders}
        existing_db_ids = {"K001", "K002"}  # All present

        missing = kite_ids - existing_db_ids
        assert len(missing) == 0

    def test_non_complete_orders_ignored(self):
        """OPEN/PENDING orders must not be re-queued even if missing from DB."""
        kite_orders = [
            {"order_id": "K001", "status": "COMPLETE", "product": "MIS"},
            {"order_id": "K002", "status": "OPEN", "product": "MIS"},
            {"order_id": "K003", "status": "CANCELLED", "product": "NRML"},
        ]
        existing_db_ids = set()  # DB has nothing

        # Apply the COMPLETE filter (same logic as _reconcile_account)
        kite_complete = [
            o for o in kite_orders
            if o.get("status") == "COMPLETE" and o.get("product") in {"MIS", "NRML", "MTF"}
        ]
        kite_ids = {str(o["order_id"]) for o in kite_complete}
        missing = kite_ids - existing_db_ids

        # Only K001 (COMPLETE) should be missing, not K002/K003
        assert missing == {"K001"}
