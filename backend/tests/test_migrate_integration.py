"""
The migration runner, exercised against a real database.

WHY THIS FILE EXISTS

`tests/test_migration_ledger.py` asserts on the runner's SOURCE TEXT —
`inspect.getsource(...)`, `assert "REFUSING to apply" in src`. Those tests
passed, and the runner still could not apply a single migration: the first real
use failed with "cannot insert multiple commands into a prepared statement",
because `conn.execute(text(sql))` hands the whole file to asyncpg's
prepared-statement path, which accepts exactly one command.

A source-text test cannot catch "this does not work". These do.

WHAT THEY COVER

  * a multi-statement file actually applies
  * CREATE INDEX CONCURRENTLY actually applies, which needs a real connection
    outside a transaction — asyncpg wraps a multi-statement script in an
    implicit transaction, so the whole file cannot be sent at once
  * a SKIP row actually stops `apply`, including when the file is named
    explicitly
  * the ledger row records what really happened

Everything created here is namespaced `zz_test_migrate_*` and dropped in a
finally block. The tests skip rather than fail when no database is reachable,
so they stay usable outside CI.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from scripts import migrate

pytestmark = pytest.mark.asyncio


def _engine():
    return create_async_engine(
        settings.DATABASE_URL, echo=False, poolclass=NullPool,
        connect_args={"statement_cache_size": 0,
                      "prepared_statement_cache_size": 0},
    )


async def _reachable(engine) -> bool:
    try:
        async with engine.connect() as conn:
            return await migrate._ledger_exists(conn)
    except Exception:
        return False


async def _drop(engine, table: str, filename: str):
    async with engine.connect() as conn:
        raw = await conn.get_raw_connection()
        await raw.driver_connection.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
        await conn.execute(
            text("DELETE FROM schema_migrations WHERE filename = :f"),
            {"f": filename},
        )
        await conn.commit()


def _write(tmp_name: str, body: str):
    path = migrate.MIGRATIONS / tmp_name
    path.write_text(body, encoding="utf-8")
    return path


async def test_a_multi_statement_migration_actually_applies():
    """
    The exact defect that shipped: several statements in one file. Two tables
    and a comment, which is what an ordinary migration looks like.
    """
    engine = _engine()
    if not await _reachable(engine):
        await engine.dispose()
        pytest.skip("no database")

    name = f"999_zz_test_multi_{uuid.uuid4().hex[:6]}.sql"
    table = "zz_test_migrate_multi"
    _write(name, f"""
-- a comment, because real migrations have them
CREATE TABLE IF NOT EXISTS {table} (id INT PRIMARY KEY);
ALTER TABLE {table} ADD COLUMN IF NOT EXISTS label TEXT;
COMMENT ON TABLE {table} IS 'temporary; dropped by the test';
""")
    try:
        rc = await migrate.cmd_apply(engine, [name])
        assert rc == 0, "multi-statement migration failed to apply"

        async with engine.connect() as conn:
            got = await conn.execute(
                text("SELECT column_name FROM information_schema.columns "
                     "WHERE table_name = :t ORDER BY 1"), {"t": table})
            assert [r[0] for r in got] == ["id", "label"]

            got = await conn.execute(
                text("SELECT applied_by FROM schema_migrations WHERE filename = :f"),
                {"f": name})
            assert got.scalar() == "runner"
    finally:
        await _drop(engine, table, name)
        (migrate.MIGRATIONS / name).unlink(missing_ok=True)
        await engine.dispose()


async def test_create_index_concurrently_actually_applies():
    """
    CONCURRENTLY cannot run inside a transaction, and asyncpg wraps any
    multi-statement script in an implicit one — so this only passes if the
    runner both sets autocommit AND sends statements individually.
    """
    engine = _engine()
    if not await _reachable(engine):
        await engine.dispose()
        pytest.skip("no database")

    name = f"999_zz_test_conc_{uuid.uuid4().hex[:6]}.sql"
    table = "zz_test_migrate_conc"
    index = f"{table}_idx"
    async with engine.connect() as conn:
        raw = await conn.get_raw_connection()
        await raw.driver_connection.execute(
            f"CREATE TABLE IF NOT EXISTS {table} (id INT, tag TEXT)")
        await conn.commit()

    _write(name, f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {index} ON {table} (tag);\n")
    try:
        rc = await migrate.cmd_apply(engine, [name])
        assert rc == 0, "CONCURRENTLY migration failed to apply"
        async with engine.connect() as conn:
            got = await conn.execute(
                text("SELECT indexname FROM pg_indexes WHERE indexname = :i"),
                {"i": index})
            assert got.scalar() == index
    finally:
        await _drop(engine, table, name)
        (migrate.MIGRATIONS / name).unlink(missing_ok=True)
        await engine.dispose()


async def test_a_skipped_migration_is_not_run_even_when_named():
    """
    The 2026-09-03 incident: a bare `apply` ran 012, which was pending as a
    DECISION rather than as a backlog item. A skip must hold against both a
    bare apply and an explicit one.
    """
    engine = _engine()
    if not await _reachable(engine):
        await engine.dispose()
        pytest.skip("no database")

    name = f"999_zz_test_skip_{uuid.uuid4().hex[:6]}.sql"
    table = "zz_test_migrate_skipped"
    _write(name, f"CREATE TABLE IF NOT EXISTS {table} (id INT);\n")
    try:
        assert await migrate.cmd_skip(engine, [name], "test") == 0

        # named explicitly — must refuse
        assert await migrate.cmd_apply(engine, [name]) == 1
        # and a bare apply must not pick it up either
        await migrate.cmd_apply(engine, [])

        async with engine.connect() as conn:
            got = await conn.execute(
                text("SELECT to_regclass(:t)"), {"t": f"public.{table}"})
            assert got.scalar() is None, "a skipped migration was executed"
    finally:
        await _drop(engine, table, name)
        (migrate.MIGRATIONS / name).unlink(missing_ok=True)
        await engine.dispose()


async def test_skip_requires_a_reason():
    """A skip without a note is indistinguishable from a forgotten migration."""
    engine = _engine()
    try:
        assert await migrate.cmd_skip(engine, ["085_schema_migrations_ledger.sql"], "") == 1
        assert await migrate.cmd_skip(engine, ["085_schema_migrations_ledger.sql"], "   ") == 1
    finally:
        await engine.dispose()


async def test_status_runs_against_the_real_ledger():
    """End to end: the command a human actually types must not raise."""
    engine = _engine()
    if not await _reachable(engine):
        await engine.dispose()
        pytest.skip("no database")
    try:
        assert await migrate.cmd_status(engine) in (0, 2)
    finally:
        await engine.dispose()


@pytest.mark.filterwarnings("ignore::pytest.PytestWarning")
def test_concurrently_migrations_stay_plain_ddl():
    """
    `_split_statements` splits on `;`, which is only safe while the
    CONCURRENTLY files contain no function bodies or DO blocks. If one ever
    does, the splitter needs a real parser and this says so first.
    """
    for path in migrate._files():
        sql = path.read_text(encoding="utf-8", errors="ignore")
        if "CONCURRENTLY" not in sql.upper():
            continue
        upper = sql.upper()
        assert "DO $$" not in upper and "CREATE FUNCTION" not in upper, (
            f"{path.name} mixes CONCURRENTLY with a block body; the naive "
            f"statement splitter cannot handle it"
        )
