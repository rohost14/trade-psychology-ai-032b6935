"""
A transient database error must not permanently disable margin capture.

WHY THIS FILE EXISTS

`broker_margin_service` keeps a process-lifetime latch, `_TABLE_AVAILABLE`.
Once it is False both the writer and the reader return before their `try`, and
nothing ever sets it back — there is no recovery path short of restarting the
process. That is correct for the case it was written for: migration 081 was
never applied, the table does not exist, so stop asking on every fill.

It was decided by a substring test:

    if "position_margin_observations" in str(exc):
        _TABLE_AVAILABLE = False

which is true of far more than a missing table. A unique or not-null violation
on that table, a serialization failure, a statement timeout, a connection
dropped mid-query — every one of them mentions the relation by name. Any single
transient error therefore switched margin capture off for good.

That is not cosmetic. `max_trade_risk` abstains when the capital requirement is
unavailable, and since `excess_exposure` was retired it is the ONLY exposure
guard left. A trader would breach the per-trade risk limit they set for
themselves and be told nothing, while the reason sat at `logger.debug`.

The fix tests SQLSTATE 42P01 (undefined_table) instead of the message text.
These tests pin both halves: the latch still fires for a genuinely missing
table, and no longer fires for anything else.
"""
from __future__ import annotations

import pytest

from app.services import broker_margin_service as bms


class _PGError(Exception):
    """Stands in for asyncpg's exception, which carries `sqlstate`."""

    def __init__(self, message: str, sqlstate: str | None):
        super().__init__(message)
        self.sqlstate = sqlstate


class _Wrapped(Exception):
    """Stands in for SQLAlchemy's wrapper, which exposes the original as `.orig`."""

    def __init__(self, message: str, orig: Exception | None):
        super().__init__(message)
        self.orig = orig


@pytest.fixture(autouse=True)
def _reset_latch():
    """The latch is module state; a leaked value would corrupt other tests."""
    before = bms._TABLE_AVAILABLE
    bms._TABLE_AVAILABLE = None
    yield
    bms._TABLE_AVAILABLE = before


# ── the case the latch exists for ──────────────────────────────────────────

def test_a_genuinely_missing_table_still_latches():
    """
    Migration 081 not applied. Asking again on every fill is pure cost, so
    this must still be recognised.
    """
    exc = _Wrapped(
        'relation "position_margin_observations" does not exist',
        _PGError('relation "position_margin_observations" does not exist', "42P01"),
    )
    assert bms._is_missing_table(exc) is True


def test_the_message_is_enough_when_the_driver_gives_no_sqlstate():
    """Fallback for a driver that exposes no SQLSTATE. Deliberately narrow."""
    exc = Exception('relation "position_margin_observations" does not exist')
    assert bms._is_missing_table(exc) is True


# ── THE REGRESSION: everything that must NOT latch ─────────────────────────

@pytest.mark.parametrize("sqlstate,message", [
    ("23505", 'duplicate key value violates unique constraint on "position_margin_observations"'),
    ("23502", 'null value in column "total" of relation "position_margin_observations"'),
    ("40001", 'could not serialize access due to concurrent update of position_margin_observations'),
    ("57014", 'canceling statement due to statement timeout on position_margin_observations'),
    ("08006", 'connection failure while reading position_margin_observations'),
    ("42703", 'column "total" of relation "position_margin_observations" does not exist'),
])
def test_a_transient_error_mentioning_the_table_does_not_latch(sqlstate, message):
    """
    Every one of these names the table, so the old substring test switched
    margin capture off permanently for all of them. A duplicate key or a
    statement timeout is a passing condition; a dead exposure guard is not.

    42703 is the sharpest case: an undefined COLUMN, whose message also
    contains "does not exist". The table is right there.
    """
    exc = _Wrapped(message, _PGError(message, sqlstate))
    assert bms._is_missing_table(exc) is False, (
        f"SQLSTATE {sqlstate} would permanently disable margin capture, and "
        "with it the only remaining per-trade exposure guard"
    )


def test_an_unrelated_error_does_not_latch():
    exc = _Wrapped("some other failure entirely", _PGError("boom", "XX000"))
    assert bms._is_missing_table(exc) is False


def test_the_latch_is_checked_before_the_try_so_it_really_is_permanent():
    """
    Documents WHY the detection has to be exact: there is no recovery path.
    Both entry points return early on a False latch, and the only assignment
    back to True lives inside the `try` those returns skip.
    """
    import inspect

    source = inspect.getsource(bms)
    assert source.count("_TABLE_AVAILABLE is False:\n        return None") == 2, (
        "the early-return guard changed shape; if a recovery path was added, "
        "this file's premise needs revisiting"
    )
    assert "_TABLE_AVAILABLE = True" in source
