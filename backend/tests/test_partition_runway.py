"""
`behavior_events` must always have months of partition runway left.

WHAT THIS EXISTS TO PREVENT

067 partitioned the table and declared monthly partitions to 2027-06. Only four
were ever created — a live schema check on 2026-09-03 found y2026m07 through
y2026m10 and nothing after — so real coverage ended on 2026-10-31, eight weeks
away.

Nothing would have failed loudly. `behavior_events_default` exists and would
have quietly swallowed every row from November onwards. Partitioning would have
stopped working without a single error, which is the worst way for it to go,
and the only reason it was caught at all is that someone happened to be
verifying the migration ledger.

So the protection is a calendar, not an alarm: this goes red in CI while there
is still half a year to act, long before production degrades.

It reads the MIGRATION FILES, not the database. A test that needs a live
connection to tell you your partitions are running out is no use in CI, and the
files are the thing a fix has to change anyway.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"

#: How much warning we want. Six months is enough to notice, decide, write a
#: migration and get it applied without any of it being urgent.
MIN_MONTHS_OF_RUNWAY = 6

PARTITION = re.compile(
    r"behavior_events_y(\d{4})m(\d{2})\s+PARTITION\s+OF\s+behavior_events",
    re.I,
)


def _declared_months() -> set[tuple[int, int]]:
    months: set[tuple[int, int]] = set()
    for path in MIGRATIONS.glob("*.sql"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for year, month in PARTITION.findall(text):
            months.add((int(year), int(month)))
    return months


def _months_between(a: tuple[int, int], b: tuple[int, int]) -> int:
    return (b[0] - a[0]) * 12 + (b[1] - a[1])


def test_partitions_are_declared_at_all():
    """Guard against the regex silently matching nothing after a rename."""
    months = _declared_months()
    assert len(months) >= 12, f"only found {len(months)} declared partitions"


def test_the_declared_months_are_contiguous():
    """
    A missing month in the middle is worse than a short runway: rows for it
    fall into the default partition while the months either side look fine.
    """
    months = sorted(_declared_months())
    gaps = [
        (months[i], months[i + 1])
        for i in range(len(months) - 1)
        if _months_between(months[i], months[i + 1]) != 1
    ]
    assert not gaps, f"gap in declared partitions: {gaps}"


def test_there_is_at_least_six_months_of_runway_left():
    """
    Fails on a calendar. When it does, the fix is a new migration extending the
    range — see 086 for the shape, including why the bounds carry an explicit
    +05:30 offset and why an empty DEFAULT partition matters.
    """
    today = date.today()
    newest = max(_declared_months())
    runway = _months_between((today.year, today.month), newest)
    assert runway >= MIN_MONTHS_OF_RUNWAY, (
        f"behavior_events partitions are declared only to "
        f"{newest[0]}-{newest[1]:02d}, which is {runway} month(s) away. "
        f"Add a migration extending the range. Rows past the last partition do "
        f"not error - they fall into behavior_events_default and partitioning "
        f"quietly stops working."
    )


# ── orders (migration 090) ─────────────────────────────────────────────────

ORDERS_PARTITION = re.compile(
    r"orders_y(\d{4})m(\d{2})\s+PARTITION\s+OF\s+orders", re.I
)


def _declared_order_months() -> set[tuple[int, int]]:
    months: set[tuple[int, int]] = set()
    for path in MIGRATIONS.glob("*.sql"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for year, month in ORDERS_PARTITION.findall(text):
            months.add((int(year), int(month)))
    return months


def test_orders_partitions_are_declared():
    assert len(_declared_order_months()) >= 12


def test_orders_declared_months_are_contiguous():
    months = sorted(_declared_order_months())
    gaps = [
        (months[i], months[i + 1])
        for i in range(len(months) - 1)
        if _months_between(months[i], months[i + 1]) != 1
    ]
    assert not gaps, f"gap in declared orders partitions: {gaps}"


def test_orders_has_at_least_six_months_of_runway():
    """
    Same calendar guard as behavior_events. A partitioned table whose window
    runs out does not error — everything lands in DEFAULT and it quietly stops
    being partitioned.
    """
    today = date.today()
    newest = max(_declared_order_months())
    runway = _months_between((today.year, today.month), newest)
    assert runway >= MIN_MONTHS_OF_RUNWAY, (
        f"orders partitions are declared only to {newest[0]}-{newest[1]:02d}, "
        f"{runway} month(s) away."
    )


def test_the_maintenance_beat_rolls_both_partitioned_tables():
    """
    The beat is what keeps the window moving. If `orders` is not in it, the
    declared range simply expires.
    """
    src = (MIGRATIONS.parent / "app" / "tasks" / "maintenance_tasks.py").read_text(
        encoding="utf-8"
    )
    assert '("behavior_events", "orders")' in src


def test_the_orders_unique_key_includes_the_partition_key():
    """
    Postgres requires it, and the upsert targets must match or every order
    event would insert instead of update.
    """
    sql = (MIGRATIONS / "090_partition_orders.sql").read_text(encoding="utf-8")
    assert "UNIQUE (broker_account_id, kite_order_id, order_timestamp)" in sql

    svc = (MIGRATIONS.parent / "app" / "services" / "trade_sync_service.py").read_text(
        encoding="utf-8"
    )
    assert svc.count("kite_order_id', 'order_timestamp'") + \
           svc.count('kite_order_id", "order_timestamp"') == 2, (
        "both ON CONFLICT targets must include the partition key"
    )


def test_orders_has_a_default_partition_so_inserts_cannot_fail():
    sql = (MIGRATIONS / "090_partition_orders.sql").read_text(encoding="utf-8")
    assert "PARTITION OF orders DEFAULT" in sql
