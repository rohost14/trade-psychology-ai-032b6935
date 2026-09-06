"""
The LIVE database must still look like the models say it does.

WHY THIS FILE EXISTS

Every other test in this suite runs against a schema built by
`Base.metadata.create_all`, where the models and the schema agree because one
was made from the other. None of them can see a divergence that exists only in
production. `behavior_events` has no primary key in the real database and has a
primary key in every test run, which is why the defect survived.

This is the complement to that, not a replacement: the model-built suite says
what the code believes, this says what the database actually has.

HOW IT STAYS USEFUL

It starts from `_schema_baseline.json`, a file of divergences already found by
the database audit and already assigned to a remediation phase. Those are
subtracted, so this test is GREEN on the day it is written. Red therefore means
one thing only: a difference nobody wrote down - a model changed without a
migration, or a schema changed without a model.

Intentional changes are not blocked, they are recorded: add the entry to the
baseline in the same commit, with a reason and the phase that owns it. That is
a line in a diff a reviewer can see, which is the entire point.

The file must SHRINK. Phase 6 fixes these, and a fixed entry left behind is
reported by `test_no_stale_baseline_entries`.

WHAT IT WILL NOT DO

Silently pass with no database. A skip is visible in pytest output; a test that
quietly asserts nothing is how a broken `orders` table stayed green for eleven
hours. And it never writes: every query here reads a catalog.
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
from app.core.database import Base
from tests.schema_diff import (
    compare, load_all_models, load_baseline, split_against_baseline,
)

# Import EVERY model module, not just the ones app/models/__init__ exports.
# Two are missing from it, so relying on the package made this check pass alone
# and fail in the full suite - see `load_all_models`.
load_all_models()

pytestmark = pytest.mark.asyncio


def _engine():
    return create_async_engine(
        settings.DATABASE_URL, echo=False, poolclass=NullPool,
        connect_args={"statement_cache_size": 0,
                      "prepared_statement_cache_size": 0},
    )


async def _fetch(sql: str, **params):
    """
    One read against the live database.

    Skips ONLY when the database is unreachable. A `ProgrammingError` is a bug
    in the SQL above and is re-raised as one - catching it too would report our
    own broken query as "no database" and silently disable the test, which is
    the exact failure shape this file exists to prevent.
    """
    engine = _engine()
    try:
        async with engine.connect() as conn:
            return (await conn.execute(text(sql), params)).mappings().all()
    except (OperationalError, InterfaceError, DBAPIError) as err:
        if isinstance(err, ProgrammingError):
            raise
        pytest.skip(f"database unreachable: {type(err).__name__}: {err}")
    finally:
        await engine.dispose()


async def _live_schema():
    """
    `({table: {column: row}}, {table: [pk column, ...]})` for the public schema.

    Partition children are excluded. They inherit their parent's columns, so
    including them would report the same drift once per partition - 24 copies
    for `orders` - and bury the parent's own finding.
    """
    columns = await _fetch("""
        SELECT c.table_name, c.column_name, c.data_type, c.is_nullable,
               c.character_maximum_length, c.numeric_precision,
               c.numeric_scale, c.datetime_precision, c.udt_name
          FROM information_schema.columns c
          JOIN pg_class pc      ON pc.relname = c.table_name
          JOIN pg_namespace pn  ON pn.oid = pc.relnamespace AND pn.nspname = 'public'
         WHERE c.table_schema = 'public'
           AND pc.relispartition IS FALSE
    """)

    by_table: dict[str, dict[str, dict]] = {}
    for row in columns:
        by_table.setdefault(row["table_name"], {})[row["column_name"]] = dict(row)

    pk_rows = await _fetch("""
        SELECT rel.relname AS table_name, att.attname AS column_name,
               array_position(con.conkey, att.attnum) AS ordinal
          FROM pg_constraint con
          JOIN pg_class rel     ON rel.oid = con.conrelid
          JOIN pg_namespace ns  ON ns.oid = rel.relnamespace AND ns.nspname = 'public'
          JOIN pg_attribute att ON att.attrelid = rel.oid
                               AND att.attnum = ANY (con.conkey)
         WHERE con.contype = 'p'
           AND rel.relispartition IS FALSE
    """)

    primary_keys: dict[str, list[str]] = {}
    for row in sorted(pk_rows, key=lambda r: (r["table_name"], r["ordinal"] or 0)):
        primary_keys.setdefault(row["table_name"], []).append(row["column_name"])

    return by_table, primary_keys


# The baseline file's own validity is checked in `test_schema_diff_rules.py`,
# which needs no database - a malformed hand-edit should fail everywhere, not
# only where the live database happens to be reachable.


# -- THE ONE THAT WOULD HAVE CAUGHT IT -------------------------------------

async def test_no_new_schema_drift():
    """
    THE REGRESSION. Everything in the baseline is a known, owned finding.
    Anything else is a change nobody recorded.
    """
    db_columns, db_primary_keys = await _live_schema()
    findings = compare(Base.metadata, db_columns, db_primary_keys)
    new, _stale = split_against_baseline(findings, load_baseline())

    assert not new, (
        f"{len(new)} schema difference(s) not in the baseline.\n\n"
        "Either the model changed without a migration, or the database "
        "changed without a model. If the change is intentional, add it to "
        "backend/tests/_schema_baseline.json in this commit with a reason "
        "and the phase that owns it.\n\n"
        + "\n".join("  - " + f.describe() for f in new)
    )


async def test_no_stale_baseline_entries():
    """
    The baseline must shrink as Phase 6 fixes things.

    Left unpruned it becomes a permanent allowlist and the burn-down stops
    being measurable, so an entry whose divergence no longer occurs is a
    failure here - the fix landed and the file did not follow it.
    """
    db_columns, db_primary_keys = await _live_schema()
    findings = compare(Base.metadata, db_columns, db_primary_keys)
    _new, stale = split_against_baseline(findings, load_baseline())

    assert not stale, (
        f"{len(stale)} baseline entr(y/ies) no longer occur - the divergence "
        "was fixed but the baseline still lists it. Remove these lines:\n"
        + "\n".join(f"  - {key}" for key in stale)
    )


# -- the specific invariants the audit found unguarded ----------------------

async def test_every_modelled_table_has_a_primary_key_in_the_database():
    """
    H1. `behavior_events` had `id` as a primary key in the model and NO
    primary key in the database, so nothing could reject a duplicate id. A
    model-built test cannot see this: `create_all` makes the key it declares.
    """
    _db_columns, db_primary_keys = await _live_schema()

    missing = sorted(
        name for name in Base.metadata.tables
        if not db_primary_keys.get(name)
    )
    baselined = {
        key.split(".", 1)[0] for key in load_baseline()
        if key.endswith(":primary_key_mismatch")
    }
    unexpected = [name for name in missing if name not in baselined]

    assert not unexpected, (
        "table(s) with a model but no primary key in the database - nothing "
        f"can reject a duplicate row: {unexpected}"
    )
