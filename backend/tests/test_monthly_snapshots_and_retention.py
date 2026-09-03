"""
Retention must never be able to delete a month it did not first preserve.

THE RULE, IN ONE LINE

    an `orders` partition is dropped only when every account with orders in
    that month has a snapshot whose contents verify

Everything here defends some part of that sentence. The gate is the whole
safety argument for shortening retention from thirteen months to six, so it is
tested as a gate — including the failure paths, because a gate that only works
when the snapshot builder succeeds is not a gate.

WHAT IS ACTUALLY AT RISK, stated precisely so these tests are not read as
protecting more than they do:

Dropping an `orders` partition does NOT delete trades, P&L, rule violations or
detector events. Those live in completed_trades, risk_alerts and
behavior_events, and none of them is under retention. What the partition drop
destroys is the order-level record — order counts, cancellations, rejections,
and the SL/SL-M placement evidence F4 reads. That is the part the snapshot
genuinely rescues; the trade and behaviour aggregates ride along so one row can
render a month.
"""
from __future__ import annotations

import inspect
import re
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
APP = BACKEND / "app"


def _src(rel: str) -> str:
    return (APP / rel).read_text(encoding="utf-8")


# ── the retention window itself ────────────────────────────────────────────

def test_orders_retention_is_six_months():
    from app.tasks.maintenance_tasks import RETENTION_MONTHS

    assert RETENTION_MONTHS["orders"] == 6


def test_behavior_events_is_never_dropped():
    """
    Deliberately None. It is the trader's own behavioural history and what
    analytics renders back to them, so deleting it is a product decision and
    not a maintenance one.
    """
    from app.tasks.maintenance_tasks import RETENTION_MONTHS

    assert RETENTION_MONTHS["behavior_events"] is None


def test_the_drop_cap_still_stands():
    """
    Shortening the window makes a wrong clock more expensive, not less. The cap
    is what keeps a mistake to one month rather than the whole table.
    """
    from app.tasks.maintenance_tasks import MAX_DROPS_PER_RUN, MONTHS_AHEAD

    assert MAX_DROPS_PER_RUN == 3
    assert MONTHS_AHEAD == 12


# ── month arithmetic ───────────────────────────────────────────────────────

def test_month_bounds_are_ist_months_expressed_in_utc():
    """
    A trading month is an IST month. Naively using UTC midnight would put the
    first five and a half hours of the 1st into the previous month's snapshot.
    """
    from app.services.monthly_snapshot_service import month_bounds_utc

    start, end = month_bounds_utc(date(2026, 1, 1))
    assert start == datetime(2025, 12, 31, 18, 30, tzinfo=timezone.utc)
    assert end == datetime(2026, 1, 31, 18, 30, tzinfo=timezone.utc)


def test_month_bounds_roll_the_year():
    from app.services.monthly_snapshot_service import month_bounds_utc

    start, end = month_bounds_utc(date(2026, 12, 1))
    assert start.year == 2026 and start.month == 11
    assert end.year == 2026 and end.month == 12
    assert end > start


@pytest.mark.parametrize("month", [date(y, m, 1)
                                   for y in (2026, 2027) for m in range(1, 13)])
def test_every_month_is_a_half_open_range(month):
    """[start, end) with no gaps and no overlaps — a row must land in exactly
    one month, or a snapshot double-counts or misses it."""
    from app.services.monthly_snapshot_service import month_bounds_utc

    start, end = month_bounds_utc(month)
    assert start < end
    nxt = date(month.year + 1, 1, 1) if month.month == 12 \
        else date(month.year, month.month + 1, 1)
    assert month_bounds_utc(nxt)[0] == end


# ── what counts as a valid snapshot ────────────────────────────────────────

@pytest.mark.parametrize("metrics", [
    None,
    {},
    {"orders": {}},
    {"orders": {}, "trades": {}},
    {"trades": {}, "alerts": {}},
])
def test_an_incomplete_snapshot_does_not_count_as_generated(metrics):
    """
    The gate asks "was this month preserved", and a half-built summary is not a
    yes. Failing open here would be the whole defect this design exists to
    avoid.
    """
    from app.services.monthly_snapshot_service import _is_valid

    assert _is_valid(metrics) is False


def test_a_complete_snapshot_counts():
    from app.services.monthly_snapshot_service import _is_valid

    assert _is_valid({"orders": {}, "trades": {}, "alerts": {}}) is True


def test_the_snapshot_records_the_order_facts_that_have_no_other_home():
    """
    The order-level columns are the reason this table exists. If a future edit
    drops them the snapshot still validates, but it stops preserving anything —
    every remaining field is available from tables that are never dropped.
    """
    src = _src("services/monthly_snapshot_service.py")
    body = src[src.index("async def build_metrics"):src.index("def _is_valid")]

    for field in ("cancelled", "rejected", "protective_placed",
                  "protective_cancelled", "modified"):
        assert f'"{field}"' in body, f"snapshot no longer records {field}"
    # SL/SL-M is the protective-stop evidence F4 reads.
    assert "'SL','SL-M'" in body or "'SL', 'SL-M'" in body


def test_building_a_snapshot_is_a_fixed_number_of_queries():
    """
    Not O(trades). This runs for every account with activity in a month, so a
    per-trade loop would cost more than the storage it reclaims.
    """
    src = _src("services/monthly_snapshot_service.py")
    body = src[src.index("async def build_metrics"):src.index("def _is_valid")]

    assert body.count("db.execute") == 3
    for forbidden in ("for trade in", "while ", "await ensure"):
        assert forbidden not in body


# ── the gate ───────────────────────────────────────────────────────────────

class _FakeSession:
    """Enough AsyncSession to drive the gate. Not a DB — the point of these
    tests is the decision, not the SQL."""

    def __init__(self):
        self.committed = 0

    async def execute(self, *a, **kw):        # pragma: no cover - unused paths
        raise AssertionError("the gate must not query directly")

    async def commit(self):
        self.committed += 1


@pytest.mark.asyncio
async def test_a_month_with_no_orders_is_droppable():
    """Nothing to preserve, so nothing blocks. Otherwise a quiet month would be
    retained forever and retention would never reclaim anything."""
    import app.services.monthly_snapshot_service as svc

    async def _none(db, month):
        return []

    orig = svc.accounts_with_orders_in_month
    svc.accounts_with_orders_in_month = _none
    try:
        assert await svc.snapshots_complete_for_month(_FakeSession(),
                                                      date(2026, 1, 1)) is True
    finally:
        svc.accounts_with_orders_in_month = orig


@pytest.mark.asyncio
async def test_one_failed_account_blocks_the_whole_month():
    """
    The partition is shared. If a single account's snapshot could not be built,
    dropping the month would delete that account's only record of it — so the
    month stays, and is retried on the next run.
    """
    import app.services.monthly_snapshot_service as svc

    class _Snap:
        metrics = {"orders": {}, "trades": {}, "alerts": {}}

    calls = []

    async def _accounts(db, month):
        return ["a", "b", "c"]

    async def _ensure(db, account_id, month):
        calls.append(account_id)
        return None if account_id == "b" else _Snap()

    orig_a, orig_e = svc.accounts_with_orders_in_month, svc.ensure_snapshot
    svc.accounts_with_orders_in_month, svc.ensure_snapshot = _accounts, _ensure
    try:
        ok = await svc.snapshots_complete_for_month(_FakeSession(),
                                                    date(2026, 1, 1))
    finally:
        svc.accounts_with_orders_in_month = orig_a
        svc.ensure_snapshot = orig_e

    assert ok is False
    assert calls == ["a", "b"], "the gate should stop at the first failure"


@pytest.mark.asyncio
async def test_a_snapshot_that_exists_but_is_empty_still_blocks():
    """
    A row is not a record. If the persisted metrics do not verify, the month is
    no more preserved than if the row were missing.
    """
    import app.services.monthly_snapshot_service as svc

    class _Empty:
        metrics = {}

    async def _accounts(db, month):
        return ["a"]

    async def _ensure(db, account_id, month):
        return _Empty()

    orig_a, orig_e = svc.accounts_with_orders_in_month, svc.ensure_snapshot
    svc.accounts_with_orders_in_month, svc.ensure_snapshot = _accounts, _ensure
    try:
        assert await svc.snapshots_complete_for_month(
            _FakeSession(), date(2026, 1, 1)) is False
    finally:
        svc.accounts_with_orders_in_month = orig_a
        svc.ensure_snapshot = orig_e


# ── the gate is actually wired into the drop ───────────────────────────────

def _drop_loop() -> str:
    src = _src("tasks/maintenance_tasks.py")
    body = src[src.index("for name in doomed:"):]
    return body[:body.index("if skipped:")]


def test_the_drop_is_gated_on_the_snapshot():
    """The check has to sit BEFORE the DROP, and its failure has to `continue`
    rather than fall through."""
    body = _drop_loop()

    gate = body.index("snapshots_complete_for_month")
    drop = body.index("DROP TABLE")
    assert gate < drop, "the snapshot check must precede the drop"
    assert "if not ok:" in body and "continue" in body


def test_a_snapshot_error_retains_the_partition():
    """
    Fail closed. An exception while checking must mean "do not drop", never
    "assume it is fine" — the cost of being wrong is asymmetric and permanent.
    """
    body = _drop_loop()

    assert "except Exception" in body
    err = body.index("except Exception")
    assert "ok = False" in body[err:err + 400]


def test_the_pruned_marker_is_written_after_the_drop():
    """
    `orders_pruned_at` asserts the raw orders are gone. Setting it before the
    DROP would let a failed drop leave the UI claiming data was deleted while
    it is still there.
    """
    body = _drop_loop()

    assert body.index("DROP TABLE") < body.index("mark_pruned")


def test_only_orders_is_gated():
    """
    `behavior_events` has no retention, so the gate must not accidentally apply
    to it — a snapshot check on a table that is never dropped would be dead
    code that looks like protection.
    """
    body = _drop_loop()

    assert 'if parent == "orders":' in body


def test_the_run_reports_what_it_retained():
    """A silently skipped month is indistinguishable from a month that had
    nothing to drop. The return value has to say."""
    from app.tasks.maintenance_tasks import ensure_behavior_event_partitions  # noqa: F401

    src = _src("tasks/maintenance_tasks.py")
    assert '"skipped": skipped' in src
    assert "retained pending snapshots" in src


# ── snapshots are written on their own beat, not only at deletion time ─────

def test_a_monthly_beat_writes_snapshots_ahead_of_any_deletion():
    """
    Waiting until the drop would mean a trader cannot see last month's summary
    for six months, and would push six months of snapshot building into the
    partition run.
    """
    from app.core.celery_app import celery_app

    entry = celery_app.conf.beat_schedule["snapshot-previous-month"]
    assert entry["task"] == "app.tasks.maintenance_tasks.snapshot_previous_month"

    # crontab stores each field as a set of matching values.
    def _first(sched):
        return (min(sched.hour), min(sched.minute))

    partitions = celery_app.conf.beat_schedule[
        "ensure-behavior-event-partitions"]["schedule"]
    # It must land before the partition beat, or a first-ever run could reach
    # the gate with nothing written.
    assert _first(entry["schedule"]) < _first(partitions)


def test_the_snapshot_task_is_idempotent_by_construction():
    """
    Scheduled twice for redundancy, so the second run has to be a verified
    no-op. Immutability is the reason: a summary that can change after the raw
    data is gone is not a record of anything.
    """
    from app.services.monthly_snapshot_service import ensure_snapshot

    src = inspect.getsource(ensure_snapshot)
    assert "on_conflict_do_nothing" in src
    assert "return existing" in src
    for forbidden in ("on_conflict_do_update", "db.merge", "existing.metrics ="):
        assert forbidden not in src, "a snapshot must never be rewritten"


def test_the_snapshot_is_stamped_with_what_produced_it():
    """
    The numbers are only interpretable against the code that made them. A
    detector retired next year must make an old month look OLD, not wrong.
    """
    from app.services.monthly_snapshot_service import SNAPSHOT_VERSION

    assert SNAPSHOT_VERSION >= 1
    src = _src("services/monthly_snapshot_service.py")
    assert "detector_version=detector_version" in src
    assert "from app.services.behavior_engine import ENGINE_VERSION" in src


def test_the_engine_version_import_actually_resolves():
    """
    It is inside a bare try/except, so a wrong module would silently stamp
    None and nobody would notice until a month needed interpreting.
    """
    from app.services.behavior_engine import ENGINE_VERSION

    assert isinstance(ENGINE_VERSION, str) and ENGINE_VERSION


# ── export: the way a trader keeps the detail before it ages out ───────────

def test_the_export_includes_the_data_that_gets_deleted():
    """
    Six-month retention is only acceptable if a trader can take the detail
    first. `orders` was the one section the DPDP export omitted.
    """
    src = _src("api/account_data.py")
    body = src[src.index("async def export_account_data"):]
    body = body[:body.index("@router.get(\"/export/download\")")] \
        if '@router.get("/export/download")' in body else body

    assert "_dump(db, Order, broker_account_id)" in body
    assert '"orders": orders' in body
    assert '"monthly_snapshots": snapshots' in body


def test_the_download_is_gated_exactly_like_the_json_export():
    """
    A friendlier format must not be a weaker door. Same auth dependency, same
    account resolution, same rate limiter.
    """
    from app.api.account_data import download_account_data, export_account_data

    def _deps(fn):
        return {p.name for p in inspect.signature(fn).parameters.values()}

    assert _deps(download_account_data) >= _deps(export_account_data) - {"user_id"}
    src = inspect.getsource(download_account_data)
    assert "get_verified_broker_account_id" in src
    assert "export_limiter" in src, "the download must share the export's cap"


def test_the_download_never_takes_an_account_id_from_the_caller():
    """The account comes from the verified token. A query parameter here would
    be an IDOR."""
    from app.api.account_data import download_account_data

    src = inspect.getsource(download_account_data)
    assert "Query(" not in src
    sig = inspect.signature(download_account_data)
    assert "Depends" in str(sig.parameters["broker_account_id"].default)


def test_the_download_excludes_credentials():
    """
    The ZIP sections are explicit, and none of them is the broker account row —
    which is where the access token and API secret live.
    """
    from app.api.account_data import _CSV_SECTIONS, download_account_data

    names = {n for n, _, _ in _CSV_SECTIONS}
    assert "orders" in names
    assert "monthly_snapshots" in names
    assert "broker_accounts" not in names

    body = inspect.getsource(download_account_data)
    for secret in ("access_token", "api_secret_enc", "refresh_token"):
        assert secret not in body


def test_the_download_is_not_cached():
    """It names the user's own trades; a shared cache holding it is a
    disclosure bug."""
    from app.api.account_data import download_account_data

    assert "no-store" in inspect.getsource(download_account_data)


def test_csv_of_an_empty_section_is_empty_not_missing():
    """
    A missing file reads as an error; an empty one reads as "nothing
    happened". Those are different facts about an account.
    """
    from app.api.account_data import _rows_to_csv

    assert _rows_to_csv([]) == ""


def test_csv_serialises_nested_values_rather_than_stringifying_them():
    """
    `metrics` and alert `details` are JSONB. Python's repr would produce single
    quotes and `None`, which no spreadsheet or parser reads back.
    """
    from app.api.account_data import _rows_to_csv

    out = _rows_to_csv([{"month": "2026-01-01",
                         "metrics": {"orders": {"total": 147}}}])
    assert '""total"": 147' in out or '"total": 147' in out
    assert "'orders'" not in out


def test_csv_serialises_values_nested_inside_a_json_column():
    """
    REGRESSION. `_jsonable` converts the COLUMN value; it does not walk inside
    a JSONB payload, and alert `details` really does carry nested UUIDs and
    datetimes. The first live run of the ZIP export raised
    "Object of type UUID is not JSON serializable" and returned a 500.
    """
    from uuid import uuid4
    from datetime import datetime

    from app.api.account_data import _rows_to_csv

    out = _rows_to_csv([{
        "details": {"trigger_completed_trade_id": uuid4(),
                    "at": datetime(2026, 1, 1)},
    }])
    assert "trigger_completed_trade_id" in out


def test_the_export_states_the_retention_window():
    """
    A trader deciding whether to download needs to know the detail expires.
    Both the JSON and the ZIP manifest say so.
    """
    from app.api.account_data import _RETENTION_MONTHS_ORDERS
    from app.tasks.maintenance_tasks import RETENTION_MONTHS

    assert _RETENTION_MONTHS_ORDERS == RETENTION_MONTHS["orders"], \
        "the number shown to the user has drifted from the one enforced"

    src = _src("api/account_data.py")
    assert src.count("orders_retention_months") >= 3


def test_a_pruned_month_is_reported_as_pruned():
    """
    Once the partition is gone the UI must say so rather than leaving someone
    to wonder why an old month will not open.
    """
    src = _src("api/account_data.py")
    body = src[src.index("async def monthly_summary"):]
    assert "orders_available" in body
    assert "orders_pruned_at is None" in body


# ── migration ──────────────────────────────────────────────────────────────

def test_the_snapshot_table_is_keyed_and_cascades():
    sql = (BACKEND / "migrations" / "091_monthly_snapshots.sql").read_text(
        encoding="utf-8")

    assert re.search(r"UNIQUE\s*\(broker_account_id,\s*month\)", sql)
    assert "ON DELETE CASCADE" in sql, \
        "a deleted account must not leave its summaries behind"
    assert "orders_pruned_at" in sql
    assert "snapshot_version" in sql
