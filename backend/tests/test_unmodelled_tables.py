"""
Tables the app queries but no model declares must be created for the test schema.

WHY THIS FILE EXISTS

CI builds its database with `Base.metadata.create_all`, which only creates what
the SQLAlchemy models describe. Three tables in production are raw-SQL tables
with no model: `gtt_tracking`, `detector_flags`, `oauth_temp_store`. In CI they
simply did not exist, and every query against them failed.

That is not a hypothetical. On 2026-09-06, `behavior_engine._load_context` read
`gtt_tracking` inside a scalar subquery. The query failed, the failure was
swallowed at `behavior_engine.py:923` with a `logger.warning` — below the level
the error feed captures — and `account_risk` silently became None. The session
was left in a rolled-back state, and 13 tests across FOUR unrelated files then
failed with `PendingRollbackError`, plus 5 assertion failures in the file that
actually cared. **18 of that day's 20 CI failures came from one missing table**,
and none of the 18 error messages named it.

`conftest.UNMODELLED_TABLES` now creates them. This file stops a fourth from
arriving unnoticed: it fails when the set of unmodelled-but-referenced tables
changes, so the next one is a named test failure rather than a cascade of
misleading ones.

WHY NOT JUST ADD MODELS

That is the better long-term answer and it is a deliberate decision, not an
oversight — `behavior_engine.py:473` records that `gtt_tracking` is queried as a
raw table on purpose. Adding models would change what `create_all` builds and
what the drift baseline compares, which belongs in Phase 6, not in a CI fix.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from sqlalchemy import text

from app.core.database import Base
from tests.conftest import UNMODELLED_TABLES
from tests.live_db import live_engine, skip_unless_migrated
from tests.schema_diff import load_all_models

BACKEND = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.asyncio


def test_the_declared_ddl_covers_exactly_the_known_unmodelled_tables():
    """
    No database needed. Pins the set so a change is deliberate.
    """
    assert set(UNMODELLED_TABLES) == {
        "gtt_tracking", "detector_flags", "oauth_temp_store"
    }, (
        f"UNMODELLED_TABLES changed to {sorted(UNMODELLED_TABLES)}. If a table "
        "gained a model, remove it here; if a new raw-SQL table appeared, the "
        "next test explains what to check."
    )


def test_none_of_the_declared_tables_has_quietly_gained_a_model():
    """
    A table with both a model and a hand-written CREATE in conftest would be
    created twice - harmlessly today because of IF NOT EXISTS, but the DDL here
    would then silently diverge from the model and nobody would notice.
    """
    load_all_models()
    overlap = sorted(set(UNMODELLED_TABLES) & set(Base.metadata.tables))
    assert not overlap, (
        f"{overlap} now has a SQLAlchemy model. Remove it from "
        "conftest.UNMODELLED_TABLES so create_all owns it."
    )


async def test_no_fourth_unmodelled_table_is_referenced_by_app_code():
    """
    THE REGRESSION.

    Any table that exists in the real database, has no model, and is named in
    application code is invisible to CI. Finding it here costs one clear
    failure; finding it the other way cost 18 misleading ones.

    Needs the migrated database, because only there is the true table list
    knowable - CI's own schema is exactly the thing under suspicion.
    """
    await skip_unless_migrated()
    load_all_models()

    engine = live_engine()
    try:
        async with engine.connect() as conn:
            live = {r[0] for r in (await conn.execute(text(
                "SELECT c.relname FROM pg_class c "
                "  JOIN pg_namespace n ON n.oid = c.relnamespace "
                " WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p') "
                "   AND c.relispartition IS FALSE"
            ))).all()}
    finally:
        await engine.dispose()

    referenced = []
    for table in sorted(live - set(Base.metadata.tables)):
        found = subprocess.run(
            ["grep", "-rlw", table, "app/", "--include=*.py"],
            capture_output=True, text=True, cwd=BACKEND,
        ).stdout.split()
        if [f for f in found if "_archive" not in f]:
            referenced.append(table)

    unhandled = sorted(set(referenced) - set(UNMODELLED_TABLES))
    assert not unhandled, (
        f"table(s) with no model, referenced by app code, and NOT created for "
        f"the test schema: {unhandled}.\n"
        "CI builds its database from the models, so every query against these "
        "fails there - and if the failure is swallowed, it surfaces as "
        "unrelated errors in other files. Add the CREATE TABLE to "
        "conftest.UNMODELLED_TABLES, copied from the migration that owns it."
    )

    stale = sorted(set(UNMODELLED_TABLES) - set(referenced))
    assert not stale, (
        f"{stale} is created for tests but no app code references it any more. "
        "Remove it, or the test schema keeps growing objects nothing needs."
    )
