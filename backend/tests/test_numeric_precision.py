"""
Every Numeric column a model declares must match the live Postgres column.

This drift was silent and it cost real money precision: `positions` and `trades`
declared Numeric(15, 4) while the database held 2dp, so a 4-decimal value was
rounded on write and nothing in the code said so. It surfaced only because a test
asserted 9.3075 round-tripped and got back 9.31.

Two decimals is the intended precision for those tables — NSE/NFO tick sizes are
0.05, so a fill price is exact at 2dp. The point of this test is not the number,
it is that the model and the column can never disagree again without failing.

NOTE ON CI: the CI database is built by `Base.metadata.create_all` from these very
models, so there the comparison is tautological and always passes. Its real value
is when run against live Supabase, where the schema came from the migration files.
Anything the live DB does not have yet is reported as informational, not failed —
a model can legitimately be ahead of an unapplied migration.
"""

from sqlalchemy import Numeric, text

from app.core.database import Base
import app.models  # noqa: F401  — populates Base.metadata


# Known, deliberate mismatches. Each needs a reason, not just an entry.
ALLOWED_MISMATCHES = {
    # Percentage, not money, and stored as double precision. Aligning the model to
    # Float would flip every consumer's value from Decimal to float, which is a
    # wider change than the drift justifies. Logged in docs/PENDING.md.
    ("completed_trades", "pnl_pct"),
}

LIVE_NUMERIC_COLUMNS = """
SELECT table_name, column_name, numeric_precision, numeric_scale
FROM information_schema.columns
WHERE table_schema = 'public' AND data_type = 'numeric'
"""


async def test_declared_numeric_precision_matches_the_database(db):
    rows = (await db.execute(text(LIVE_NUMERIC_COLUMNS))).mappings().all()
    live = {
        (r["table_name"], r["column_name"]): (r["numeric_precision"], r["numeric_scale"])
        for r in rows
    }

    drift = []
    for table in Base.metadata.tables.values():
        for col in table.columns:
            if not isinstance(col.type, Numeric):
                continue
            key = (table.name, col.name)
            if key in ALLOWED_MISMATCHES:
                continue

            declared = (col.type.precision, col.type.scale)
            actual = live.get(key)
            if actual is None:
                # Not a numeric column in the live DB: either the table/column is not
                # there yet (unapplied migration) or it is a different type. The
                # allow-list above covers the type mismatches we know about.
                continue
            if declared != actual:
                drift.append(
                    f"{table.name}.{col.name}: model declares Numeric{declared}, "
                    f"database has numeric{actual}"
                )

    assert not drift, (
        "Model/database numeric precision drift — a value written through the model "
        "will be silently rounded to the database's scale:\n  "
        + "\n  ".join(sorted(drift))
    )
