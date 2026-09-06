"""
Write the initial `_schema_baseline.json` from the live database.

Run once, at the point the drift check is introduced:

    cd backend && PYTHONPATH=. python tests/generate_schema_baseline.py

IT REFUSES TO OVERWRITE AN EXISTING BASELINE, and that is the important part.
A one-button "re-baseline" would turn a red drift check green by accepting
whatever the database happens to look like today - which is precisely the
failure the check exists to prevent. After this file exists, a new entry is
added BY HAND, in the commit that causes it, with a reason a reviewer reads.

Pass `--print` to see what it would write without touching anything.

Every entry it generates carries the phase that owns the fix. Those come from
`docs/database/REMEDIATION_INDEX.md` §2b and the Phase 0 decisions, not from
guesswork - see `_PHASE_RULES` below.
"""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.database import Base  # noqa: E402
from tests.schema_diff import (  # noqa: E402
    BASELINE_PATH, Finding, compare, load_all_models,
)

load_all_models()  # every model module, not only what app/models exports

#: (table, kind) -> (owning phase, why it is accepted for now).
#:
#: Matched most-specific first: an exact (table, kind) beats a (None, kind)
#: catch-all. Nothing falls through unlabelled - an unmatched finding is a
#: finding nobody has decided about, and the generator says so rather than
#: inventing a reason.
_PHASE_RULES: list[tuple[str | None, str, int, str]] = [
    (
        "alert_checkpoints", "column_missing_from_model", 8,
        "Phase 0 decision D3: alert_checkpoints is RETIRED - table, model and "
        "service. These 23 columns are the first-generation money-saved "
        "design; no migration or code anywhere in the repo creates them, and "
        "the counterfactual measure they encode was replaced by the factual "
        "behaviour-cost endpoint. Fixing the model would preserve a table that "
        "is being removed.",
    ),
    (
        "alert_checkpoints", "type_mismatch", 8,
        "Phase 0 decision D3: alert_checkpoints is RETIRED. Not worth a "
        "migration on a table scheduled for removal.",
    ),
    (
        "alert_checkpoints", "nullable_db_permissive", 8,
        "Phase 0 decision D3: alert_checkpoints is RETIRED.",
    ),
    (
        None, "primary_key_mismatch", 2,
        "Audit finding H1. The database has no primary key where the model "
        "declares one, so nothing rejects a duplicate row. Phase 2 adds it "
        "after de-duplicating the existing rows.",
    ),
    (
        None, "column_missing_from_model", 6,
        "Audit finding M11 - a live column the model does not know about. "
        "Phase 6 either adds it to the model or drops it, once its consumers "
        "are established.",
    ),
    (
        None, "column_missing_from_db", 6,
        "Audit finding M11 - the model declares a column the database does "
        "not have. Any write touching it fails at runtime.",
    ),
    (
        None, "nullable_db_strict", 6,
        "The model is LOOSER than the database: it believes NULL is "
        "acceptable where the database rejects it, so the failure surfaces at "
        "runtime as a failed INSERT. Phase 6 tightens the model, which is a "
        "model-only change with no schema risk.",
    ),
    (
        None, "nullable_db_permissive", 6,
        "The database is LOOSER than the model: the ORM refuses a NULL the "
        "database would accept, so no ORM write can corrupt anything - but a "
        "migration, script or console write can leave a NULL the application "
        "then breaks on. Phase 6 adds NOT NULL after checking for existing "
        "NULLs.",
    ),
    (
        None, "type_mismatch", 6,
        "Audit finding M11. Phase 6 resolves each one individually: the "
        "text-versus-String(n) group is a length ceiling the model believes "
        "in and the database does not enforce.",
    ),
    (
        None, "table_missing_from_db", 6,
        "The model declares a table the database does not have.",
    ),
]


def _classify(finding: Finding) -> tuple[int, str]:
    for table, kind, phase, why in _PHASE_RULES:
        if kind == finding.kind and (table is None or table == finding.table):
            return phase, why
    raise SystemExit(
        f"no phase rule matches {finding.key!r}. Add one to _PHASE_RULES with "
        "a reason - an entry with no owner is indistinguishable from a "
        "silenced failure."
    )


async def _live_schema():
    engine = create_async_engine(
        settings.DATABASE_URL, echo=False, poolclass=NullPool,
        connect_args={"statement_cache_size": 0,
                      "prepared_statement_cache_size": 0},
    )
    try:
        async with engine.connect() as conn:
            columns = (await conn.execute(text("""
                SELECT c.table_name, c.column_name, c.data_type, c.is_nullable,
                       c.character_maximum_length, c.numeric_precision,
                       c.numeric_scale, c.datetime_precision, c.udt_name
                  FROM information_schema.columns c
                  JOIN pg_class pc     ON pc.relname = c.table_name
                  JOIN pg_namespace pn ON pn.oid = pc.relnamespace
                                      AND pn.nspname = 'public'
                 WHERE c.table_schema = 'public'
                   AND pc.relispartition IS FALSE
            """))).mappings().all()

            pk_rows = (await conn.execute(text("""
                SELECT rel.relname AS table_name, att.attname AS column_name,
                       array_position(con.conkey, att.attnum) AS ordinal
                  FROM pg_constraint con
                  JOIN pg_class rel     ON rel.oid = con.conrelid
                  JOIN pg_namespace ns  ON ns.oid = rel.relnamespace
                                       AND ns.nspname = 'public'
                  JOIN pg_attribute att ON att.attrelid = rel.oid
                                       AND att.attnum = ANY (con.conkey)
                 WHERE con.contype = 'p'
                   AND rel.relispartition IS FALSE
            """))).mappings().all()
    finally:
        await engine.dispose()

    by_table: dict[str, dict[str, dict]] = {}
    for row in columns:
        by_table.setdefault(row["table_name"], {})[row["column_name"]] = dict(row)

    primary_keys: dict[str, list[str]] = {}
    for row in sorted(pk_rows, key=lambda r: (r["table_name"], r["ordinal"] or 0)):
        primary_keys.setdefault(row["table_name"], []).append(row["column_name"])

    return by_table, primary_keys


async def main() -> int:
    dry_run = "--print" in sys.argv

    if BASELINE_PATH.exists() and not dry_run:
        print(
            f"{BASELINE_PATH.name} already exists and will NOT be "
            "regenerated.\n\n"
            "Regenerating would accept whatever the database looks like "
            "today, which is how a real drift gets silenced. Add the new "
            "entry by hand, in the commit that causes it, with a reason.\n\n"
            "Use --print to see the current full diff.",
            file=sys.stderr,
        )
        return 1

    db_columns, db_primary_keys = await _live_schema()
    findings = compare(Base.metadata, db_columns, db_primary_keys)

    accepted: dict[str, dict] = {}
    for finding in sorted(findings, key=lambda f: f.key):
        phase, why = _classify(finding)
        accepted[finding.key] = {
            "db": finding.db,
            "model": finding.model,
            "phase": phase,
            "why": why,
        }

    document = {
        "_what_this_is": (
            "Divergences between the SQLAlchemy models and the live database "
            "that were already found by the database audit and assigned to a "
            "remediation phase. tests/test_schema_drift.py subtracts these, "
            "so it is green today and red only for a difference nobody "
            "recorded."
        ),
        "_how_to_add_an_entry": (
            "By hand, in the commit that causes the change, with a 'why' and "
            "the phase that owns it. Never by regenerating this file."
        ),
        "_this_file_must_shrink": (
            "Phase 6 fixes these. test_no_stale_baseline_entries fails if an "
            "entry is fixed and left here, so the burn-down stays measurable."
        ),
        "generated": date.today().isoformat(),
        "accepted": accepted,
    }

    rendered = json.dumps(document, indent=2, sort_keys=False) + "\n"
    if dry_run:
        print(rendered)
    else:
        BASELINE_PATH.write_text(rendered, encoding="utf-8")
        print(f"wrote {BASELINE_PATH} with {len(accepted)} accepted divergences")

    by_phase: dict[int, int] = {}
    for entry in accepted.values():
        by_phase[entry["phase"]] = by_phase.get(entry["phase"], 0) + 1
    print("by owning phase: "
          + ", ".join(f"phase {p}: {n}" for p, n in sorted(by_phase.items())),
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
