"""
The partitioned tables must actually be partitioned IN THE DATABASE.

WHY THIS FILE EXISTS

On 2026-09-03 migration 090 was re-run outside the runner against an
already-partitioned `orders`. The rename moved the real table aside with its 24
partitions and 344 rows, every CREATE ... PARTITION OF failed on a name still
held by the legacy table's children, and `DROP TABLE orders_legacy` then
succeeded. What was left was a partitioned table with NO partitions and no
DEFAULT - a table Postgres cannot route a single row into.

Every order write failed for the next eleven hours with "no partition of
relation orders found for row", and failed silently, because both call sites
swallow it: webhooks.py logs it non-fatal and trade_tasks.py retries then gives
up. The 344 rows are unrecoverable - Kite serves no order history beyond the
current day, and the project is on a Supabase plan with no backups.

THE SUITE WAS GREEN THROUGH ALL OF IT.

`test_partition_runway.py` and `test_admin_partitions.py` both assert against
migration FILE TEXT and regexes. They answer "does the repo declare the right
partitions", which is a real question and stays worth asking - a file-based
test works in CI with no database, and the file is what a fix has to change.
But it is not the same question as "does the database HAVE them", and only the
second one would have caught this.

So this file is the complement, not the replacement: the files say what SHOULD
exist, these tests say what DOES.

WHAT THEY WILL NOT DO

Silently pass when there is no database. A skip is visible in pytest output; a
test that quietly asserts nothing is how a table that accepted no rows stayed
green for eleven hours. Nothing here writes: partition routing for a RANGE
table is decided entirely by the declared bounds, so asking whether a bound
contains `now()` answers the same question an INSERT would, without touching
production data.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import (
    DBAPIError, InterfaceError, OperationalError, ProgrammingError,
)
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings

pytestmark = pytest.mark.asyncio

#: Every RANGE-partitioned parent, with the key it is partitioned on.
PARTITIONED = {
    "orders": "RANGE (order_timestamp)",
    "behavior_events": "RANGE (detected_at)",
}

#: Same threshold the file-based runway test and the admin panel use. Three
#: numbers for "how much warning do we want" would mean CI red while the panel
#: says healthy, or the reverse.
MIN_RUNWAY_MONTHS = 6


def _engine():
    return create_async_engine(
        settings.DATABASE_URL, echo=False, poolclass=NullPool,
        connect_args={"statement_cache_size": 0,
                      "prepared_statement_cache_size": 0},
    )


async def _fetch(sql: str, **params):
    """
    One query against the live database.

    Skips ONLY when the database is unreachable. A bad query is a defect in
    this file and must fail as one — the first version of this helper caught
    every exception and reported a SQL syntax error as "no database", which
    silently disabled a test. That is the same failure shape the whole file
    exists to prevent, so the two cases are separated deliberately.
    """
    engine = _engine()
    try:
        async with engine.connect() as conn:
            return (await conn.execute(text(sql), params)).all()
    except (OperationalError, InterfaceError, DBAPIError) as err:
        # DBAPIError covers driver-level failures, but a ProgrammingError is a
        # DBAPIError too and is OUR bug, so it is re-raised rather than skipped.
        if isinstance(err, ProgrammingError):
            raise
        pytest.skip(f"database unreachable: {type(err).__name__}: {err}")
    finally:
        await engine.dispose()


async def _partitions(parent: str) -> dict[str, str]:
    """{partition name: declared bound expression} for one parent."""
    rows = await _fetch(
        "SELECT c.relname, pg_get_expr(c.relpartbound, c.oid) "
        "  FROM pg_class c "
        "  JOIN pg_inherits i ON i.inhrelid = c.oid "
        "  JOIN pg_class p ON p.oid = i.inhparent "
        " WHERE p.relname = :parent",
        parent=parent,
    )
    return {name: bound for name, bound in rows}


def _months_from(start: date, count: int):
    for offset in range(count):
        y = start.year + (start.month - 1 + offset) // 12
        m = (start.month - 1 + offset) % 12 + 1
        yield date(y, m, 1)


# ── the parent is what we think it is ──────────────────────────────────────

@pytest.mark.parametrize("parent,key", PARTITIONED.items())
async def test_the_parent_is_actually_partitioned(parent, key):
    rows = await _fetch(
        "SELECT relkind, pg_get_partkeydef(oid) FROM pg_class WHERE relname = :p",
        p=parent,
    )
    assert rows, f"{parent} does not exist"
    relkind, partkey = rows[0]
    relkind = relkind.decode() if isinstance(relkind, bytes) else relkind

    assert relkind == "p", (
        f"{parent} has relkind {relkind!r}, not 'p' - it is not a partitioned "
        f"table any more"
    )
    assert partkey == key, f"{parent} is partitioned on {partkey!r}, expected {key!r}"


# ── THE ONE THAT WOULD HAVE CAUGHT IT ──────────────────────────────────────

@pytest.mark.parametrize("parent", PARTITIONED)
async def test_the_parent_has_any_partitions_at_all(parent):
    """
    THE REGRESSION. `orders` sat with zero partitions and no DEFAULT for eleven
    hours. A partitioned table with no partitions accepts no rows — every
    INSERT fails with "no partition of relation ... found for row" — and both
    order-write call sites swallow that exception, so nothing surfaced.
    """
    parts = await _partitions(parent)
    assert parts, (
        f"{parent} is partitioned but has NO partitions. It cannot accept a "
        f"single row. Every write to it is failing right now."
    )


@pytest.mark.parametrize("parent", PARTITIONED)
async def test_a_default_partition_exists(parent):
    """
    DEFAULT is what turns "the window lapsed" from silent data loss into a
    counted signal: a row belonging to no declared month lands there and the
    admin panel reports it, instead of raising an error nobody sees. It is also
    what lets a back-dated tradebook import land at all.
    """
    parts = await _partitions(parent)
    assert f"{parent}_default" in parts, (
        f"{parent} has no DEFAULT partition — a row outside every declared "
        f"month will raise instead of being caught and counted"
    )


@pytest.mark.parametrize("parent", PARTITIONED)
async def test_a_partition_covers_right_now(parent):
    """
    Routing for a RANGE table is decided entirely by the declared bounds, so
    this asks exactly what an INSERT would ask, without writing anything: is
    there a month that contains this instant?
    """
    today = date.today()
    expected = f"{parent}_y{today.year}m{today.month:02d}"
    parts = await _partitions(parent)

    assert expected in parts, (
        f"no partition covers today: {expected} is missing from {parent}. "
        f"Writes are landing in DEFAULT at best."
    )


@pytest.mark.parametrize("parent", PARTITIONED)
async def test_there_is_forward_runway(parent):
    """
    A partitioned table whose window runs out does not error — it silently
    routes everything into DEFAULT and stops being partitioned in practice.
    This goes red while there is still half a year to act.
    """
    parts = await _partitions(parent)
    runway = 0
    for month in _months_from(date.today(), MIN_RUNWAY_MONTHS + 1):
        if f"{parent}_y{month.year}m{month.month:02d}" not in parts:
            break
        runway += 1

    assert runway >= MIN_RUNWAY_MONTHS, (
        f"{parent} has only {runway} months of partition runway "
        f"(want >= {MIN_RUNWAY_MONTHS}). The maintenance beat is not keeping up."
    )


@pytest.mark.parametrize("parent", PARTITIONED)
async def test_the_runway_has_no_gaps(parent):
    """
    A partition beyond a hole does not help the rows that fall in the hole, so
    a gap inside the window is as bad as a short window.
    """
    parts = await _partitions(parent)
    missing = [
        m.isoformat() for m in _months_from(date.today(), MIN_RUNWAY_MONTHS)
        if f"{parent}_y{m.year}m{m.month:02d}" not in parts
    ]
    assert not missing, f"{parent} is missing partitions for {missing}"


@pytest.mark.parametrize("parent", PARTITIONED)
async def test_nothing_has_landed_in_the_default_partition(parent):
    """
    DEFAULT existing is protection; DEFAULT being OCCUPIED means the protection
    was needed — the declared window already lapsed, or something is writing
    back-dated rows nobody planned for. Either way it wants a human.
    """
    rows = await _fetch(f"SELECT count(*) FROM ONLY {parent}_default")
    count = rows[0][0]
    assert count == 0, (
        f"{count} rows are sitting in {parent}_default. They are not lost, but "
        f"the table has stopped being partitioned for them."
    )


@pytest.mark.parametrize("parent", PARTITIONED)
async def test_partition_bounds_do_not_overlap_or_gap(parent):
    """
    Declared bounds must tile the range end to end. Postgres rejects an
    overlapping partition at creation, so this is really a guard on the seam:
    one month's upper bound is the next one's lower bound, with nothing between.
    """
    parts = {k: v for k, v in (await _partitions(parent)).items()
             if not k.endswith("_default")}
    bounds = []
    for name, expr in parts.items():
        # FOR VALUES FROM ('...') TO ('...')
        lo, hi = expr.split("FROM (")[1].split(") TO (")
        bounds.append((lo.strip("'), "), hi.strip("'), "), name))
    bounds.sort()

    for (_, prev_hi, prev_name), (next_lo, _, next_name) in zip(bounds, bounds[1:]):
        assert prev_hi == next_lo, (
            f"seam between {prev_name} and {next_name}: {prev_hi} != {next_lo}"
        )


# ── the structure `LIKE` silently dropped ──────────────────────────────────

async def test_orders_still_cascades_from_broker_accounts():
    """
    `CREATE TABLE ... (LIKE ...)` copies no foreign keys, not even with
    INCLUDING CONSTRAINTS. 090 used LIKE, so the FK from migration 017 vanished
    and `orders` became the only table in the database with a
    broker_account_id and no FK to broker_accounts.

    That matters: a user-initiated erasure issues a hard DELETE FROM users and
    relies on ON DELETE CASCADE to reach every child table. Without it those
    rows are orphaned by a deletion that reports success — a data-rights defect,
    not just an integrity one.
    """
    rows = await _fetch(
        "SELECT conname, confdeltype FROM pg_constraint "
        " WHERE conrelid = 'orders'::regclass AND contype = 'f'"
    )
    assert rows, "orders has no foreign key to broker_accounts"
    _, deltype = rows[0]
    deltype = deltype.decode() if isinstance(deltype, bytes) else deltype
    assert deltype == "c", f"FK delete action is {deltype!r}, expected 'c' (CASCADE)"


async def test_orders_still_has_its_updated_at_trigger():
    """Lost the same way the FK was: LIKE copies no triggers."""
    rows = await _fetch(
        "SELECT tgname FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid "
        " WHERE c.relname = 'orders' AND NOT t.tgisinternal"
    )
    assert [r[0] for r in rows] == ["update_orders_updated_at"]


async def test_the_natural_key_includes_the_partition_key():
    """
    Postgres requires the partition key in every unique constraint, so the
    2-column key became 3. Both ON CONFLICT sites in trade_sync_service name
    the 3-column form; if this constraint ever reverted, every order upsert
    would fail at runtime rather than in review.
    """
    rows = await _fetch(
        "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint "
        " WHERE conrelid = 'orders'::regclass AND contype = 'u'"
    )
    assert len(rows) == 1, f"expected exactly one unique constraint, got {rows}"
    name, definition = rows[0]
    assert name == "uq_orders_account_kite_id"
    assert "order_timestamp" in definition, definition


async def test_the_partition_key_is_not_nullable():
    """A row whose partition key is null belongs to no partition."""
    rows = await _fetch(
        "SELECT is_nullable FROM information_schema.columns "
        " WHERE table_name = 'orders' AND column_name = 'order_timestamp'"
    )
    assert rows[0][0] == "NO"


# ── the model must describe the table it actually maps to ──────────────────

async def test_the_orm_model_matches_the_live_primary_key():
    """
    The model declared an `id`-only primary key and a nullable
    `order_timestamp` for a day after 090 changed both. Nothing broke, because
    the app never inserts by PK — which is precisely why it could drift
    unnoticed, and why `Base.metadata.create_all` in CI was building a table
    shaped unlike production.
    """
    from app.models.order import Order

    rows = await _fetch(
        "SELECT a.attname FROM pg_index i "
        "  JOIN pg_attribute a ON a.attrelid = i.indrelid "
        "                     AND a.attnum = ANY(i.indkey) "
        " WHERE i.indrelid = 'orders'::regclass AND i.indisprimary"
    )
    live_pk = {r[0] for r in rows}
    model_pk = {c.name for c in Order.__table__.primary_key.columns}

    assert model_pk == live_pk, (
        f"models/order.py declares PK {sorted(model_pk)} but the database has "
        f"{sorted(live_pk)}"
    )


async def test_the_orm_model_matches_the_live_nullability():
    from app.models.order import Order

    rows = await _fetch(
        "SELECT column_name, is_nullable FROM information_schema.columns "
        " WHERE table_name = 'orders'"
    )
    live = {name: (nullable == "YES") for name, nullable in rows}

    mismatched = {
        c.name: (c.nullable, live[c.name])
        for c in Order.__table__.columns
        if c.name in live and c.nullable != live[c.name]
    }
    assert not mismatched, (
        f"model/DB nullability drift (model, db): {mismatched}"
    )


# ── indexes have to reach the partitions, not just the parent ──────────────

async def test_indexes_are_attached_to_every_partition():
    """
    An index on a partitioned parent is a template: Postgres creates and
    attaches a child index per partition. Right after the failed 090 re-run all
    six existed on the parent with ZERO children, which looks fine in
    `\\d orders` and indexes nothing.
    """
    parts = await _partitions("orders")
    monthly = [p for p in parts if not p.endswith("_default")]
    assert monthly, "no monthly partitions to check"

    parent_count = (await _fetch(
        "SELECT count(*) FROM pg_index WHERE indrelid = 'orders'::regclass"
    ))[0][0]

    sample = sorted(monthly)[-1]
    child_count = (await _fetch(
        "SELECT count(*) FROM pg_index WHERE indrelid = CAST(:p AS regclass)", p=sample
    ))[0][0]

    assert child_count == parent_count, (
        f"{sample} carries {child_count} indexes but the parent declares "
        f"{parent_count} — queries against that month are unindexed"
    )


# ── the drop guard (migration 093) ─────────────────────────────────────────
#
# 344 order rows were destroyed by a single unguarded `DROP TABLE
# orders_legacy` run by hand. Nothing we had could have stopped it: the runner
# was bypassed, 090's BEGIN/COMMIT was defeated by statement-by-statement
# execution, the retention gate was not involved, and the suite only reads
# migration file text. An event trigger is the only layer that sees the
# statement itself, whatever tool issued it.

async def test_the_drop_guard_is_installed_and_enabled():
    rows = await _fetch(
        "SELECT evtname, evtenabled, evtevent FROM pg_event_trigger "
        " WHERE evtname = 'tm_protect_partitioned_tables'"
    )
    assert rows, "the drop guard from migration 093 is not installed"
    name, enabled, event = rows[0]
    enabled = enabled.decode() if isinstance(enabled, bytes) else enabled
    assert enabled == "O", f"guard is disabled (evtenabled={enabled!r})"
    assert event == "sql_drop"


@pytest.mark.parametrize("target", [
    "orders",                      # the parent
    "orders_y2026m02",             # a monthly partition
    "orders_default",              # the safety net itself
    "behavior_events_y2026m07",    # behaviour history, which has no retention
])
async def test_dropping_a_protected_table_is_refused(target):
    """
    Every one of these is unrecoverable on this plan. The guard must refuse
    without the transaction announcing itself, whatever the caller is.
    """
    engine = _engine()
    try:
        async with engine.connect() as conn:
            with pytest.raises(Exception) as exc:
                await conn.execute(text(f"DROP TABLE {target}"))
            assert "REFUSING to drop protected table" in str(exc.value)
            await conn.rollback()
    finally:
        await engine.dispose()


async def test_an_announced_drop_is_allowed():
    """
    Retention drops a partition a month and must keep working. The escape hatch
    is SET LOCAL, so it dies with the transaction and cannot leak into the next
    statement — proven here by dropping and rolling back.
    """
    engine = _engine()
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SET LOCAL tm.allow_drop = 'on'"))
            await conn.execute(text("DROP TABLE orders_y2026m02"))
            await conn.rollback()
    finally:
        await engine.dispose()

    # and it is still there, because the transaction rolled back
    assert "orders_y2026m02" in await _partitions("orders")


async def test_the_guard_does_not_touch_unrelated_tables():
    """A guard that blocked every drop would be turned off within a week."""
    engine = _engine()
    try:
        async with engine.connect() as conn:
            await conn.execute(text("CREATE TABLE zz_guard_probe (id int)"))
            await conn.execute(text("DROP TABLE zz_guard_probe"))
            await conn.rollback()
    finally:
        await engine.dispose()


@pytest.mark.filterwarnings("ignore")
async def test_only_the_retention_job_announces_a_drop():
    """
    The escape hatch is only as good as how rarely it is used. If a second
    caller ever sets it, the guard has quietly become advisory.
    """
    from pathlib import Path

    app_dir = Path(__file__).resolve().parents[1] / "app"
    setters = [
        p.relative_to(app_dir).as_posix()
        for p in app_dir.rglob("*.py")
        if "_archive" not in p.parts and "tm.allow_drop" in p.read_text(
            encoding="utf-8", errors="ignore")
    ]
    assert setters == ["tasks/maintenance_tasks.py"], (
        f"tm.allow_drop is set in {setters} — it must be the retention job only"
    )
