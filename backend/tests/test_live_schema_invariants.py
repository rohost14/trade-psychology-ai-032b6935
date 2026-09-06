"""
Structural invariants of the LIVE database, pinned to measured numbers.

WHY THIS FILE EXISTS

`test_live_partitions.py` proved the pattern - assert against the real database,
not against migration file text - but it only covers partitions. The database
audit found several more invariants that nothing was watching, each one a place
where damage accumulates silently:

  * a `uuid` column with no foreign key, quietly collecting references to rows
    that no longer exist (H2: 7 of 20 journal entries point at nothing)
  * the ON DELETE topology, where one FK changed from CASCADE to NO ACTION
    would leave orphans behind on every account deletion
  * duplicate indexes, which cost write throughput and storage for nothing

EVERY NUMBER HERE WAS MEASURED, NOT QUOTED

Each figure below came from a query run against the live database on
2026-09-06, and the query is in the test that uses it so it can be re-run. Two
of them disagree with the audit prose and the measurement is what is recorded:

  * FKs into `broker_accounts`: 37, matching the audit - but ONLY when
    partition children are excluded. Counting them gives 80, because each of
    `orders`' partitions carries its own copy of the parent's FK.
  * duplicate index groups: 14, where the audit prose says 21. Grouping here is
    by (table, columns, uniqueness, partial predicate, expression), which is
    the definition under which two indexes are genuinely interchangeable. A
    partial index is NOT a duplicate of a full one on the same column, and
    three of these tables have exactly that pair.

A NUMBER CHANGING IS NOT AUTOMATICALLY A FAILURE - it is a thing that has to be
looked at and then written down. These assert equality in both directions on
purpose: a count going DOWN because a phase fixed something must update this
file, or the improvement is invisible and the next change re-hides it.

Nothing here writes. Every query reads a catalog or counts rows.
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

pytestmark = pytest.mark.asyncio


# ── measured 2026-09-06 against the live database ──────────────────────────

#: H2. `journal_entries.trade_id` is a uuid with no FK, and is polymorphic in
#: practice: it points at `completed_trades` for some rows and `positions` for
#: others, at `trades` - the table its name implies - for none, and at nothing
#: at all for these. Phase 2 owns driving it to zero.
DANGLING_JOURNAL_TRADE_IDS = 7

#: Every FK pointing AT `broker_accounts`, and how many of them cascade. All of
#: them do, which is what makes account deletion leave nothing behind. One
#: dropping to NO ACTION is a silent orphan generator.
FKS_INTO_BROKER_ACCOUNTS = 37

#: M2, Phase 5. Groups of two or more indexes that are genuinely
#: interchangeable. Every write to these tables maintains all of them.
DUPLICATE_INDEX_GROUPS = 14

#: uuid columns named `*_id` that no foreign key protects. Each one can go
#: dangling exactly the way `journal_entries.trade_id` did, and nothing would
#: report it. Listed by name so a NEW one is a visible diff, not a number.
UNPROTECTED_UUID_REFERENCES = {
    "cooldowns.trigger_alert_id",
    "journal_entries.trade_id",
    "risk_alerts.trigger_position_id",
    "shadow_behavioral_events.trigger_completed_trade_id",
}


def _engine():
    return create_async_engine(
        settings.DATABASE_URL, echo=False, poolclass=NullPool,
        connect_args={"statement_cache_size": 0,
                      "prepared_statement_cache_size": 0},
    )


async def _fetch(sql: str, **params):
    """
    One read against the live database.

    Skips ONLY when the database is unreachable; a `ProgrammingError` is our
    own broken SQL and is re-raised as one. Catching it too would report a
    typo as "no database" and silently disable the test.
    """
    engine = _engine()
    try:
        async with engine.connect() as conn:
            return (await conn.execute(text(sql), params)).all()
    except (OperationalError, InterfaceError, DBAPIError) as err:
        if isinstance(err, ProgrammingError):
            raise
        pytest.skip(f"database unreachable: {type(err).__name__}: {err}")
    finally:
        await engine.dispose()


# ── H2: references nothing protects ────────────────────────────────────────

async def test_the_dangling_journal_references_do_not_grow():
    """
    H2. `journal_entries.trade_id` has no foreign key, so the database will
    accept any uuid at all and has been doing so. A journal entry is the
    trader's own written record; a dangling one cannot be tied back to
    anything.

    Pinned rather than asserted-zero because the damage already exists and
    Phase 2 owns the repair. What this catches is the count GROWING, which
    means the write path is still producing them.
    """
    rows = await _fetch("""
        SELECT count(*)
          FROM journal_entries j
         WHERE j.trade_id IS NOT NULL
           AND NOT EXISTS (SELECT 1 FROM trades           t WHERE t.id = j.trade_id)
           AND NOT EXISTS (SELECT 1 FROM completed_trades c WHERE c.id = j.trade_id)
           AND NOT EXISTS (SELECT 1 FROM positions        p WHERE p.id = j.trade_id)
    """)
    dangling = rows[0][0]

    assert dangling <= DANGLING_JOURNAL_TRADE_IDS, (
        f"{dangling} journal entries reference a row that exists in none of "
        f"trades, completed_trades or positions - up from "
        f"{DANGLING_JOURNAL_TRADE_IDS}. The write path is still creating "
        "dangling references."
    )
    assert dangling == DANGLING_JOURNAL_TRADE_IDS, (
        f"dangling journal references dropped to {dangling} from "
        f"{DANGLING_JOURNAL_TRADE_IDS}. Good - now update "
        "DANGLING_JOURNAL_TRADE_IDS in this file, or the improvement is "
        "invisible and the next regression re-hides it."
    )


async def test_no_new_uuid_column_is_left_without_a_foreign_key():
    """
    The generalisation of H2. A `*_id` uuid column with no FK is a dangling
    reference waiting to happen, and the database will never complain.

    Asserted as a SET, not a count: a new unprotected column appearing while
    an old one is fixed nets to zero and would pass a count check silently.
    """
    rows = await _fetch(r"""
        SELECT t.relname, a.attname
          FROM pg_attribute a
          JOIN pg_class t     ON t.oid = a.attrelid
          JOIN pg_namespace n ON n.oid = t.relnamespace AND n.nspname = 'public'
          JOIN pg_type ty     ON ty.oid = a.atttypid AND ty.typname = 'uuid'
         WHERE t.relkind IN ('r', 'p')
           AND t.relispartition IS FALSE
           AND a.attnum > 0
           AND NOT a.attisdropped
           AND a.attname LIKE '%\_id'
           AND a.attname <> 'id'
           AND NOT EXISTS (
                 SELECT 1 FROM pg_constraint con
                  WHERE con.conrelid = t.oid AND con.contype = 'f'
                    AND a.attnum = ANY (con.conkey))
    """)
    found = {f"{table}.{column}" for table, column in rows}

    new = sorted(found - UNPROTECTED_UUID_REFERENCES)
    assert not new, (
        f"uuid reference column(s) with no foreign key: {new}. Nothing stops "
        "these from pointing at a deleted row - the same defect as H2. Either "
        "add the foreign key, or add the column to "
        "UNPROTECTED_UUID_REFERENCES with a reason."
    )

    fixed = sorted(UNPROTECTED_UUID_REFERENCES - found)
    assert not fixed, (
        f"{fixed} now has a foreign key. Remove it from "
        "UNPROTECTED_UUID_REFERENCES so the list keeps shrinking."
    )


# ── the deletion topology ──────────────────────────────────────────────────

async def test_every_foreign_key_into_broker_accounts_still_cascades():
    """
    Account deletion is a hard `DELETE FROM users` relying entirely on FK
    cascade. One FK at NO ACTION would block the delete; one at SET NULL would
    leave the row behind with a null owner - a data-rights problem, not just
    an untidy one.

    Partition children are excluded: each of `orders`' partitions carries its
    own copy of the parent's FK, so counting them reports 80 for the same 37
    logical constraints and the number drifts every time a partition is added.
    """
    rows = await _fetch("""
        SELECT con.conname, con.confdeltype::text
          FROM pg_constraint con
          JOIN pg_class ref ON ref.oid = con.confrelid
          JOIN pg_class src ON src.oid = con.conrelid
         WHERE con.contype = 'f'
           AND ref.relname = 'broker_accounts'
           AND src.relispartition IS FALSE
    """)

    not_cascade = sorted(name for name, ondelete in rows if ondelete != "c")
    assert not not_cascade, (
        "foreign key(s) into broker_accounts that do NOT cascade on delete: "
        f"{not_cascade}. Account deletion would leave rows behind."
    )
    assert len(rows) == FKS_INTO_BROKER_ACCOUNTS, (
        f"{len(rows)} foreign keys into broker_accounts, expected "
        f"{FKS_INTO_BROKER_ACCOUNTS}. A new table referencing an account is "
        "fine - update the number here so the next change is visible."
    )


# ── write cost nobody is paying attention to ───────────────────────────────

async def test_no_new_duplicate_index_groups():
    """
    M2, Phase 5. Two indexes on the same columns, with the same uniqueness and
    the same partial predicate, are interchangeable: every write maintains
    both and only one is ever used.

    The predicate is part of the grouping key deliberately. `idx_positions_open`
    is a PARTIAL index on the same column as `idx_positions_broker`, and
    calling those two a duplicate pair would be wrong - they answer different
    questions.
    """
    rows = await _fetch("""
        SELECT t.relname,
               string_agg(c.relname, ' | ' ORDER BY c.relname)
          FROM pg_index idx
          JOIN pg_class c     ON c.oid = idx.indexrelid
          JOIN pg_class t     ON t.oid = idx.indrelid
          JOIN pg_namespace n ON n.oid = t.relnamespace AND n.nspname = 'public'
         WHERE t.relispartition IS FALSE
         GROUP BY t.relname, idx.indkey::text, idx.indisunique,
                  COALESCE(pg_get_expr(idx.indpred,   idx.indrelid), ''),
                  COALESCE(pg_get_expr(idx.indexprs, idx.indrelid), '')
        HAVING count(*) > 1
    """)

    assert len(rows) <= DUPLICATE_INDEX_GROUPS, (
        f"{len(rows)} groups of duplicate indexes, up from "
        f"{DUPLICATE_INDEX_GROUPS}. Every write to these tables maintains all "
        "of them:\n"
        + "\n".join(f"  {table}: {members}" for table, members in sorted(rows))
    )
    assert len(rows) == DUPLICATE_INDEX_GROUPS, (
        f"duplicate index groups dropped to {len(rows)} from "
        f"{DUPLICATE_INDEX_GROUPS}. Update DUPLICATE_INDEX_GROUPS so Phase 5's "
        "progress stays measurable."
    )
