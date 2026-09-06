"""
Guard for tests that assert on state only MIGRATIONS create.

WHY THIS EXISTS

Some tests in this suite deliberately assert against the real database:
partitions, the drop guard from migration 093, the foreign-key topology, the
model-vs-schema drift baseline. Those are the tests that catch what a
model-built schema cannot show — `behavior_events` has no primary key in
production and has one in every `create_all` database, which is exactly why
that defect survived.

But CI does not run against that database. `.github/workflows/ci.yml` starts a
throwaway Postgres and `conftest.py` builds the schema with
`Base.metadata.create_all` — no migrations. In that database there are no
partitions, no drop guard, no drift, and no dangling references, so every one
of those assertions fails. Correctly: the objects genuinely are not there.

The workflow already knew about this class and handled it by excluding
`tests/test_db_schema.py` by name. That works, and it is invisible - a reader
of the test file has no idea it never runs in CI, and the exclusion list is a
place where a test can quietly go to die.

So these skip instead, at the point of use, with a reason printed in the pytest
output. A skip is visible. An exclusion in a YAML file is not.

WHAT COUNTS AS "MIGRATED"

The presence of a populated `schema_migrations` ledger. `create_all` never
creates that table - only `085_schema_migrations_ledger.sql` does, and only the
runner writes rows into it. It is therefore the one honest signal for "this
database was built the way production was built".
"""
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import (
    DBAPIError, InterfaceError, OperationalError, ProgrammingError,
)
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings

#: Cached across a session - the answer cannot change mid-run, and asking once
#: per test would add a connection to every one of them.
_MIGRATED: bool | None = None


def live_engine():
    """An engine for reading the live database, with pgbouncer-safe settings."""
    return create_async_engine(
        settings.DATABASE_URL, echo=False, poolclass=NullPool,
        connect_args={"statement_cache_size": 0,
                      "prepared_statement_cache_size": 0},
    )


async def _database_was_built_by_migrations() -> bool:
    engine = live_engine()
    try:
        async with engine.connect() as conn:
            rows = (await conn.execute(text(
                "SELECT count(*) FROM information_schema.tables "
                " WHERE table_schema = 'public' AND table_name = 'schema_migrations'"
            ))).scalar()
            if not rows:
                return False
            applied = (await conn.execute(
                text("SELECT count(*) FROM schema_migrations"))).scalar()
            return bool(applied)
    except (OperationalError, InterfaceError, DBAPIError, ProgrammingError):
        # Unreachable or unreadable. `skip_unless_migrated` turns this into a
        # visible skip; it is not this function's job to decide.
        return False
    finally:
        await engine.dispose()


async def skip_unless_migrated() -> None:
    """
    Skip the calling test unless the database was built by the migrations.

    Use it for assertions about objects a migration creates. Do NOT use it to
    make an inconvenient failure go away: a test that fails against the REAL
    database is telling you something, and this only silences the case where
    the schema was never built that way in the first place.
    """
    global _MIGRATED
    if _MIGRATED is None:
        _MIGRATED = await _database_was_built_by_migrations()
    if not _MIGRATED:
        pytest.skip(
            "database was not built by migrations (no populated "
            "schema_migrations ledger) - partitions, the drop guard, the FK "
            "topology and the drift baseline do not exist in a "
            "create_all schema, so asserting on them here would be asserting "
            "on the wrong database"
        )
