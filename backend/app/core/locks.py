"""
Serialising a check-then-insert across workers.

THE PROBLEM THIS SOLVES

Several writers follow the shape "read to see whether this already exists, and
write it if not". That is safe against a Celery RETRY — the retry re-reads and
sees the committed row — but not against two workers running the same check at
the same instant. Both read "nothing there", both insert, and the duplicate
lands.

The usual database answer is a unique constraint, and for `behavior_events` it
is not available. That table is partitioned by `detected_at`, and PostgreSQL
requires a unique index on a partitioned table to include the partition key. So
any uniqueness rule there must include the timestamp — and the writers this
module protects set that timestamp from the processing clock, meaning two runs
produce two different values and never collide however the rest of the key is
built. A constraint cannot express "one of these per account per day" when the
day is not part of the row's identity.

An advisory lock can. It serialises the two racers so the second one's read
sees the first one's committed row, which is exactly what the existing
application-level checks already assume.

WHY THE `_xact_` VARIANT SPECIFICALLY, AND NOT `pg_advisory_lock`

This database is reached through the Supabase transaction pooler (port 6543,
PgBouncer in transaction mode). A SESSION-scoped advisory lock is actively
dangerous there: the server connection is handed back to the pool at COMMIT
while the lock is still held, so the lock outlives the work it was protecting
and is later inherited by an unrelated client.

`pg_advisory_xact_lock` is released by the server at COMMIT or ROLLBACK — the
same boundary PgBouncer recycles the connection on. The two agree exactly, so
it is safe under transaction pooling and cannot leak. Never substitute the
session-scoped call here.

USAGE

Take the lock BEFORE the read whose result you are about to act on, inside the
same transaction as the write:

    await advisory_xact_lock(db, "tilt_recovery", account_id)
    if await _already_exists(db, account_id):
        return
    db.add(...)
    await db.commit()          # lock releases here

The lock key should be at least as COARSE as the check it protects. A key finer
than the check lets two racers take different locks and both proceed, which is
no protection at all; a coarser key only costs a little concurrency.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def advisory_xact_lock(db: AsyncSession, *parts: object) -> None:
    """
    Hold a transaction-scoped advisory lock on the given key parts.

    Blocks until the lock is free, then returns. Released automatically when
    the surrounding transaction commits or rolls back — including when it rolls
    back because of an error, so a failing task cannot strand it.

    `hashtextextended` gives a 64-bit key from the joined parts, so distinct
    keys are very unlikely to share a lock. A collision would only cost
    concurrency, never correctness: two unrelated writers would serialise
    against each other, and both would still do the right thing.
    """
    key = ":".join("" if p is None else str(p) for p in parts)
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {"key": key},
    )
