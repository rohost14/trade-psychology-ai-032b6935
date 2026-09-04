"""
`get_or_create_session` must never destroy its caller's transaction.

WHAT WENT WRONG

The helper ended with:

    try:
        await db.flush()
    except Exception:
        # Race condition: another request already inserted this row.
        await db.rollback()

Two defects in four lines.

`flush()` flushes EVERYTHING pending on the session, not just the TradingSession
row, so the exception it caught was frequently nothing to do with a duplicate.
And `db.rollback()` discards the CALLER'S transaction — a session this service
does not own. On the engine path that transaction holds the CompletedTrade being
analysed and whatever else the caller staged.

Reproduced by forcing a single flush inside the helper to raise a statement
timeout: the next insert died with

    ForeignKeyViolationError: Key (broker_account_id)=(...) is not present
    in table "broker_accounts"

because the broker account had been rolled back out from under the test. That is
how four tests failed together in one slow full-suite run and passed in every
other, and it is a production hazard too — the live path runs analyze() inside a
session that may hold other pending work.

THE CONTRACT THESE TESTS PIN

  * a genuine duplicate is still handled, and still returns the existing row
  * anything that is NOT a duplicate propagates as itself
  * in both cases the caller's transaction survives

The point is the third line. A helper that "recovers" by throwing away work it
did not create is worse than one that fails.
"""
from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.models.trading_session import TradingSession
from app.services.trading_session_service import (
    TradingSessionService, _is_duplicate,
)

pytestmark = pytest.mark.asyncio


# ── which errors count as a race ───────────────────────────────────────────

class _Orig:
    def __init__(self, sqlstate):
        self.sqlstate = sqlstate


def _integrity(sqlstate):
    return IntegrityError("stmt", {}, _Orig(sqlstate))


async def test_a_unique_violation_is_a_race():
    """23505 is the only error that means someone else created it first."""
    assert _is_duplicate(_integrity("23505")) is True


async def test_a_foreign_key_violation_is_not_a_race():
    """
    23503 means the caller handed us an account that does not exist. Treating
    that as a race would hide a real bug behind a silent retry — and it is an
    IntegrityError too, so a bare `except IntegrityError` would have caught it.
    """
    assert _is_duplicate(_integrity("23503")) is False


@pytest.mark.parametrize("err", [
    TimeoutError("canceling statement due to statement timeout"),
    ConnectionResetError("connection lost"),
    RuntimeError("something else entirely"),
])
async def test_an_unrelated_failure_is_not_a_race(err):
    """
    THE ONE THAT MATTERS. A statement timeout under connection pressure was
    being read as "another request inserted this row" and answered with a
    rollback of the caller's transaction.
    """
    assert _is_duplicate(err) is False


async def test_an_unrecognised_driver_errs_towards_raising():
    """
    No SQLSTATE means we cannot tell. Guessing "race" would silently swallow;
    guessing "real error" merely propagates. Only one of those is recoverable.
    """
    class _NoCode:
        pass

    assert _is_duplicate(IntegrityError("stmt", {}, _NoCode())) is False


# ── the caller's transaction survives ──────────────────────────────────────

async def test_a_duplicate_does_not_destroy_the_callers_work(db, broker):
    """
    The race path, end to end. A second call for the same (account, date) must
    return the existing row AND leave everything the caller staged intact.

    Before the fix this path called db.rollback(), which would have taken the
    broker account and the user with it.
    """
    day = date(2026, 1, 15)

    first = await TradingSessionService.get_or_create_session(broker.id, day, db)
    assert first is not None

    # Force the race: a second in-flight row for the same key. Without the
    # savepoint this raises and rolls back the caller.
    second = await TradingSessionService.get_or_create_session(broker.id, day, db)
    assert second.id == first.id, "the existing session should be returned"

    # The caller's rows are still here. This is the whole point.
    still_there = (await db.execute(
        text("SELECT count(*) FROM broker_accounts WHERE id = :i"), {"i": broker.id}
    )).scalar_one()
    assert still_there == 1, "the caller's broker account was rolled back"


async def test_the_session_row_is_actually_created(db, broker):
    """The happy path still works — a savepoint that swallowed the insert
    would pass every other test here."""
    day = date(2026, 2, 20)
    created = await TradingSessionService.get_or_create_session(broker.id, day, db)

    found = (await db.execute(
        select(TradingSession).where(
            TradingSession.broker_account_id == broker.id,
            TradingSession.session_date == day,
        )
    )).scalar_one_or_none()

    assert found is not None and found.id == created.id


async def test_a_foreign_key_violation_propagates_and_is_recoverable(db):
    """
    An account that does not exist must raise, not be retried into a confusing
    "session not found". The savepoint means the caller's transaction is still
    usable afterwards — before the fix the rollback left it unusable.
    """
    ghost = uuid.uuid4()

    with pytest.raises(IntegrityError):
        await TradingSessionService.get_or_create_session(
            ghost, date(2026, 3, 10), db)

    await db.rollback()          # the caller decides how to recover, not us
    alive = (await db.execute(text("SELECT 1"))).scalar_one()
    assert alive == 1, "the session was left unusable"


# ── the shape of the fix, so it cannot regress into the old one ───────────

async def test_the_helper_uses_a_savepoint_and_never_rolls_back_the_caller():
    """
    Structural, because the failure mode is invisible until something else
    fails at the same time. `db.rollback()` inside this helper is the exact
    defect: it is not this service's transaction to end.
    """
    import inspect

    raw = inspect.getsource(TradingSessionService.get_or_create_session)
    # The comments explain the OLD code and legitimately quote it, so matching
    # against them would make this test pass or fail on its own rationale.
    # Assert on executable lines only.
    src = chr(10).join(
        line for line in raw.splitlines()
        if not line.strip().startswith("#")
    )

    assert "begin_nested()" in src, "the insert must be confined to a SAVEPOINT"
    assert "await db.rollback()" not in src, (
        "this service does not own the caller's transaction and must never "
        "roll it back"
    )

    # Only the INSERT block is in scope. The `except Exception` around
    # get_session_boundaries is unrelated and legitimate — it defaults market
    # hours to None — so asserting across the whole function would be testing
    # the wrong line.
    insert_block = src[src.index("begin_nested()"):]
    assert "except IntegrityError" in insert_block
    assert "except Exception" not in insert_block, (
        "a bare except on the insert is what reinterpreted timeouts as races"
    )
