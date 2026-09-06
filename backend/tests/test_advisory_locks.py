"""
The advisory lock that closes the check-then-insert race, proved by racing it.

WHY A REAL RACE AND NOT A MOCK

The bug this guards against only appears under genuine concurrency: two workers
read "this does not exist yet", both insert, and the duplicate lands. A test
that mocks the lock proves the call was made, not that it works — and "the call
was made" is exactly the kind of claim that has been wrong twice in this phase.

So these run two REAL transactions on two REAL connections, interleaved so the
second one's read lands after the first one's read and before its commit. That
is the window the lock exists to close. Without it the second transaction sees
nothing and writes; with it, it waits and then sees the row.

The first test deliberately runs the race WITHOUT the lock and asserts the
duplicate happens, because a guard whose failure mode has never been observed
is a guard nobody can trust.

WHY THE TRANSACTION-SCOPED VARIANT IS THE ONLY CORRECT ONE HERE

This database is reached through the Supabase transaction pooler (port 6543,
PgBouncer in transaction mode). A session-scoped `pg_advisory_lock` would be
handed back to the pool at COMMIT while still held, and later inherited by an
unrelated client. `pg_advisory_xact_lock` is released by the server at COMMIT,
the same boundary PgBouncer recycles on, so the two agree exactly.

These tests write and delete their own rows in a table nothing else uses for
this purpose, and clean up in a finally.
"""
from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.locks import advisory_xact_lock

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def two_sessions():
    """
    Two independent committing sessions on separate connections, plus a
    throwaway account the raced rows can belong to.

    The suite's shared `db` fixture holds one connection inside one outer
    transaction, so it cannot express a race at all - both "workers" would be
    the same transaction and would never contend.

    The race runs on `behavior_events` deliberately: it is the table this
    whole problem is about, and the ONLY one where no constraint could stand in
    for the lock. `data_quality_events` was tried first and cannot demonstrate
    the bug at all - it carries `uq_dq_events_daily`, so the database rejects
    the second insert by itself. That is the difference this test exists to
    show: where a unique constraint is possible it should be used, and on a
    partitioned table keyed by an observation timestamp it is not possible.

    `broker_account_id` is NOT NULL behind a foreign key, so the race needs a
    real account. It is created here, committed so both connections can see it,
    and deleted in the teardown - the same discipline `synthetic_pipeline`
    uses, and for the same reason: 12,010 test users once leaked into this
    database because a fixture committed and nothing removed the rows.
    """
    from app.models.broker_account import BrokerAccount
    from app.models.user import User
    from tests.conftest import make_engine

    engine = make_engine()
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    marker = uuid4().hex[:8]
    async with Session() as setup:
        user = User(email=f"locktest+{marker}@tests.invalid",
                    display_name="Advisory Lock Test")
        setup.add(user)
        await setup.flush()
        account = BrokerAccount(user_id=user.id, broker_name="zerodha",
                                broker_email=user.email,
                                broker_user_id=f"LK{marker[:6].upper()}",
                                status="connected")
        setup.add(account)
        await setup.flush()
        await setup.commit()
        account_id, user_id = account.id, user.id

    try:
        async with Session() as a, Session() as b:
            yield a, b, account_id
            for s in (a, b):
                try:
                    await s.rollback()
                except Exception:
                    pass
    finally:
        async with Session() as teardown:
            await teardown.execute(
                text("DELETE FROM behavior_events WHERE broker_account_id = :a"),
                {"a": str(account_id)})
            await teardown.execute(
                text("DELETE FROM broker_accounts WHERE id = :a"), {"a": str(account_id)})
            await teardown.execute(
                text("DELETE FROM users WHERE id = :u"), {"u": str(user_id)})
            await teardown.commit()
        await engine.dispose()


async def _count(db: AsyncSession, marker: str) -> int:
    """How many events this marker has - the read a writer does before inserting."""
    return (await db.execute(
        text("SELECT count(*) FROM behavior_events WHERE detector = :m"),
        {"m": marker},
    )).scalar()


async def _insert(db: AsyncSession, marker: str, account_id) -> None:
    """
    One event, shaped like the unkeyed writers this protects.

    No `idempotency_key`, and `detected_at` from the clock - exactly what
    `tilt_recovery` and the position-alert writer do, and the reason the
    partial unique index cannot catch a duplicate here.
    """
    await db.execute(
        text("INSERT INTO behavior_events "
             "  (id, broker_account_id, detector, detector_version, severity, "
             "   data_quality, message, detected_at) "
             "VALUES (:i, :a, :m, '1.0.0', 'info', 'GOOD', "
             "        'advisory lock race test', now())"),
        {"i": str(uuid4()), "a": str(account_id), "m": marker},
    )


async def test_without_the_lock_two_workers_both_insert(two_sessions):
    """
    THE BUG, REPRODUCED. Both transactions read "nothing there", both write.

    This is what the three unkeyed BehaviorEvent writers were exposed to, and
    what no unique constraint can prevent on `behavior_events`: that table is
    partitioned on detected_at, Postgres requires the partition key in any
    unique index, and those writers set detected_at from the clock - so two
    runs produce two different keys and never collide.
    """
    a, b, account_id = two_sessions
    marker = f"lock_race_{uuid4().hex[:8]}"
    try:
        # Both read first - the interleaving that makes the race
        assert await _count(a, marker) == 0
        assert await _count(b, marker) == 0

        await _insert(a, marker, account_id)
        await a.commit()
        await _insert(b, marker, account_id)
        await b.commit()

        assert await _count(a, marker) == 2, (
            "the unprotected race did NOT produce a duplicate - the setup no "
            "longer reproduces the bug, so the next test proves nothing"
        )
    finally:
        await a.rollback()


async def test_with_the_lock_the_second_worker_waits_and_sees_the_first(two_sessions):
    """
    THE FIX. The same interleaving, with the lock taken before each read.

    B's lock acquisition blocks until A commits. Its read then sees A's row and
    it declines to insert - which is precisely what the existing
    application-level dedup checks already assume, and what was not true before.
    """
    a, b, account_id = two_sessions
    marker = f"lock_race_{uuid4().hex[:8]}"
    b_wrote = None
    try:
        await advisory_xact_lock(a, "test", marker)
        assert await _count(a, marker) == 0

        async def worker_b():
            # Blocks inside the lock until A commits, then reads.
            await advisory_xact_lock(b, "test", marker)
            seen = await _count(b, marker)
            if seen == 0:
                await _insert(b, marker, account_id)
            await b.commit()
            return seen

        task = asyncio.create_task(worker_b())
        await asyncio.sleep(0.4)

        assert not task.done(), (
            "worker B did not block on the advisory lock. Either the lock was "
            "not taken, or it is session-scoped and shared the connection"
        )

        await _insert(a, marker, account_id)
        await a.commit()

        b_saw = await asyncio.wait_for(task, timeout=15)
        b_wrote = b_saw == 0

        assert b_saw == 1, (
            f"worker B read {b_saw} rows after acquiring the lock; it should "
            "have seen exactly the one worker A committed"
        )
        assert await _count(a, marker) == 1, "a duplicate was written despite the lock"
    finally:
        await a.rollback()
        assert b_wrote is not True, "B inserted despite seeing A's row"


async def test_the_lock_is_released_by_a_rollback(two_sessions):
    """
    A failing task must not strand the lock.

    `pg_advisory_xact_lock` is released by the server on ROLLBACK as well as
    COMMIT, so an exception between the lock and the write frees it. If this
    ever regressed, one crashed task would block that key until the connection
    died.
    """
    a, b, _account_id = two_sessions
    key = f"rollback-{uuid4().hex[:10]}"

    await advisory_xact_lock(a, "test", key)
    await a.rollback()

    # B must acquire immediately; a stranded lock would hang until the timeout.
    await asyncio.wait_for(advisory_xact_lock(b, "test", key), timeout=10)
    await b.rollback()


async def test_the_same_key_hashes_the_same_way_every_time():
    """
    The key is derived from the parts, so two callers naming the same thing
    must contend. A key that varied per call would take a different lock each
    time and serialise nothing at all.
    """
    from tests.conftest import make_engine

    engine = make_engine()
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as db:
        first = (await db.execute(
            text("SELECT hashtextextended(:k, 0)"), {"k": "tilt_recovery:abc"})).scalar()
        second = (await db.execute(
            text("SELECT hashtextextended(:k, 0)"), {"k": "tilt_recovery:abc"})).scalar()
        other = (await db.execute(
            text("SELECT hashtextextended(:k, 0)"), {"k": "tilt_recovery:xyz"})).scalar()
        await db.rollback()
    await engine.dispose()

    assert first == second, "the same key hashed differently between calls"
    assert first != other, "two different keys collided"
