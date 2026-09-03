"""
The admin partition panel, and the limits on what an admin may do from it.

THE POINT OF THE PAGE

A partitioned table whose forward window runs out does not fail loudly. Rows
land in the DEFAULT partition and the table stops being partitioned in practice
— which is how the `behavior_events` window came within eight weeks of expiring
unnoticed. So the tests about VISIBILITY here are not cosmetic: the health
signal is the whole product.

THE POINT OF THE LIMITS

Retention became configurable at runtime, which is a new way to destroy data.
Everything guarding that is tested as a guard, including the paths where it
should refuse:

  * no endpoint drops a named partition, at any role
  * every mutation is superadmin or ops, and audited
  * shortening a window, or turning one on, needs a typed phrase
  * the floor cannot be crossed even WITH the phrase
  * the snapshot gate is not reachable from here at all

The gate itself is covered in test_monthly_snapshots_and_retention.py; what is
tested here is that the admin surface cannot get around it.
"""
from __future__ import annotations

import inspect
import re
from datetime import date
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.api.admin import partitions as ap
from app.services import retention_policy_service as policy

BACKEND = Path(__file__).resolve().parents[1]
APP = BACKEND / "app"

SUPERADMIN = {"email": "root@test", "role": "superadmin"}


def _src(rel: str) -> str:
    return (APP / rel).read_text(encoding="utf-8")


# ── nothing here can delete a partition directly ───────────────────────────

def test_no_endpoint_drops_a_named_partition():
    """
    THE LOAD-BEARING ONE. The safety argument for six-month retention is that
    the snapshot gate stands between a month and its deletion. An admin route
    taking a partition name and dropping it would walk straight past that, so
    there must not be one.
    """
    src = _src("api/admin/partitions.py")

    assert "DROP TABLE" not in src
    for verb in ("router.delete",):
        assert verb not in src, "the partition panel must expose no delete route"


def test_the_only_deletion_path_is_the_gated_job():
    """
    The manual run calls the same function the beat calls. If it ever grew its
    own drop loop, the gate would have two implementations and only one would
    be tested.
    """
    src = inspect.getsource(ap.run_maintenance)

    assert "_apply_retention" in src
    # No raw SQL at all in the route: the drop belongs to the job, and a route
    # that could compose its own statement could compose one past the gate.
    assert "DROP TABLE" not in src.upper()
    assert "text(" not in src


def test_inspecting_the_archive_does_not_change_it():
    """
    `snapshots_complete_for_month` BUILDS what is missing as a side effect,
    which is right for the job and wrong for a screen. The admin view must use
    the read-only report.
    """
    src = inspect.getsource(ap.snapshot_overview)

    assert "snapshot_status_for_month" in src
    assert "snapshots_complete_for_month" not in src


def test_the_readonly_status_agrees_with_the_gate_on_completeness():
    """
    Two functions answering the same question is a drift risk. Both call
    `_is_valid` on the same rows, and this pins the shape rather than trusting
    that they stay aligned by inspection.
    """
    from app.services.monthly_snapshot_service import snapshot_status_for_month

    src = inspect.getsource(snapshot_status_for_month)
    assert "_is_valid" in src
    assert "db.execute" in src
    for forbidden in ("ensure_snapshot", "pg_insert", "db.add", "mark_pruned"):
        assert forbidden not in src, "the inspection path must not write"


# ── permissions ────────────────────────────────────────────────────────────

def _role_dep(fn):
    """The roles a route's dependency accepts, read off the signature."""
    for p in inspect.signature(fn).parameters.values():
        dep = getattr(p.default, "dependency", None)
        if dep is None:
            continue
        closure = inspect.getclosurevars(dep).nonlocals
        if "roles" in closure:
            return set(closure["roles"])
        if dep.__name__ == "get_current_admin":
            return {"*"}
    return set()


@pytest.mark.parametrize("fn,expected", [
    (ap.partition_overview, {"*"}),          # read: any admin
    (ap.snapshot_overview,  {"*"}),          # read: any admin
    (ap.ensure_partitions,  {"superadmin", "ops"}),
    (ap.snapshot_month,     {"superadmin", "ops"}),
    (ap.run_maintenance,    {"superadmin"}),
    (ap.set_retention,      {"superadmin"}),
])
def test_each_route_requires_the_right_role(fn, expected):
    """
    Reads are open because seeing the state is never dangerous. Creating
    partitions and building snapshots only ever ADD, so ops may do them.
    Running maintenance and changing retention can destroy data, so both are
    superadmin.
    """
    assert _role_dep(fn) == expected


def test_every_mutating_route_is_audited():
    """
    An admin action that deletes a month of a trader's orders and leaves no
    record of who did it is not an accountable system.
    """
    for fn in (ap.ensure_partitions, ap.snapshot_month,
               ap.run_maintenance, ap.set_retention):
        src = inspect.getsource(fn)
        assert "await audit(" in src, f"{fn.__name__} writes no audit row"


def test_read_routes_write_no_audit_row():
    """Auditing reads would bury the actions that matter in noise."""
    for fn in (ap.partition_overview, ap.snapshot_overview):
        assert "await audit(" not in inspect.getsource(fn)


# ── retention policy validation ────────────────────────────────────────────

def test_the_code_defaults_are_the_settled_ones():
    """This panel configures the window; it does not get to redefine it."""
    assert policy.RETENTION_MONTHS == {"orders": 6, "behavior_events": None}


def test_maintenance_still_reads_the_same_names():
    """The task's public constant is the policy service's, re-exported, so
    there is exactly one definition of the window in the codebase."""
    from app.tasks.maintenance_tasks import RETENTION_MONTHS

    assert RETENTION_MONTHS is policy.RETENTION_MONTHS


@pytest.mark.parametrize("months", [0, 1, 2, -6])
def test_below_the_floor_is_refused(months):
    """
    Detectors read inside the window. A shorter one would mean the gate is
    preserving summaries of data the engine still wanted.
    """
    with pytest.raises(policy.RetentionPolicyError, match="below"):
        policy.validate("orders", months)


def test_an_absurd_window_is_refused():
    with pytest.raises(policy.RetentionPolicyError, match="typo"):
        policy.validate("orders", 6000)


@pytest.mark.parametrize("bad", ["6", 6.5, True, [6]])
def test_a_non_integer_window_is_refused(bad):
    """`True` is an int in Python and would silently mean one month."""
    with pytest.raises(policy.RetentionPolicyError):
        policy.validate("orders", bad)


def test_keeping_forever_is_always_allowed():
    """None can only ever retain more data than the alternative."""
    assert policy.validate("orders", None) is None
    assert policy.validate("behavior_events", None) is None


def test_an_unknown_table_is_refused():
    with pytest.raises(policy.RetentionPolicyError, match="unknown"):
        policy.validate("trades", 6)


# ── which changes count as dangerous ───────────────────────────────────────

@pytest.mark.parametrize("current,proposed,narrowing", [
    (6, 12, False),        # lengthening
    (6, 6, False),         # no change
    (12, 6, True),         # shortening
    (6, None, False),      # keep forever
    (None, 24, True),      # turning retention ON is the sharpest case
    (None, None, False),
])
def test_narrowing_is_exactly_the_direction_that_can_destroy_data(
    current, proposed, narrowing,
):
    assert policy.is_narrowing("orders", current, proposed) is narrowing


def test_the_confirmation_is_a_phrase_not_a_boolean():
    """
    A yes/no dialog gets clicked through by muscle memory. Typing the sentence
    is the point.
    """
    assert " " in ap.CONFIRM_PHRASE
    assert ap.CONFIRM_PHRASE.isupper()


# ── the API guards, exercised ──────────────────────────────────────────────

class _FakeDb:
    """A session that answers only what these paths ask of it."""

    def __init__(self):
        self.committed = 0
        self.added = []

    async def execute(self, *a, **kw):
        raise AssertionError("this test must not reach SQL")

    async def commit(self):
        self.committed += 1

    def add(self, obj):
        self.added.append(obj)


def _stub_effective(monkeypatch, orders=6, behavior=None):
    async def _eff(db):
        return {
            "orders": {"months": orders, "source": "code", "code_default": 6,
                       "updated_by": None, "updated_at": None},
            "behavior_events": {"months": behavior, "source": "code",
                                "code_default": None, "updated_by": None,
                                "updated_at": None},
        }
    monkeypatch.setattr(policy, "get_effective", _eff)


@pytest.mark.asyncio
async def test_shortening_without_the_phrase_is_refused(monkeypatch):
    _stub_effective(monkeypatch, orders=12)

    with pytest.raises(HTTPException) as e:
        await ap.set_retention(
            ap.RetentionRequest(table="orders", months=6),
            admin=SUPERADMIN, db=_FakeDb())
    assert e.value.status_code == 400
    assert ap.CONFIRM_PHRASE in e.value.detail


@pytest.mark.asyncio
async def test_a_near_miss_phrase_is_refused(monkeypatch):
    """Case and wording must match. "Almost right" is how a confirmation
    becomes a formality."""
    _stub_effective(monkeypatch, orders=12)

    for attempt in ("delete old partitions", "DELETE OLD PARTITION",
                    "DELETE  OLD  PARTITIONS", "yes", ""):
        with pytest.raises(HTTPException):
            await ap.set_retention(
                ap.RetentionRequest(table="orders", months=6, confirm=attempt),
                admin=SUPERADMIN, db=_FakeDb())


@pytest.mark.asyncio
async def test_the_floor_holds_even_with_the_phrase(monkeypatch):
    """
    The confirmation is for a decision that is dangerous but legitimate. Going
    below the floor is not legitimate, so no phrase unlocks it.
    """
    _stub_effective(monkeypatch)

    with pytest.raises(HTTPException) as e:
        await ap.set_retention(
            ap.RetentionRequest(table="orders", months=1, confirm=ap.CONFIRM_PHRASE),
            admin=SUPERADMIN, db=_FakeDb())
    assert "below" in e.value.detail


@pytest.mark.asyncio
async def test_turning_on_behaviour_retention_needs_the_phrase(monkeypatch):
    """
    `behavior_events` is the trader's own behavioural history and is NOT
    snapshot-gated — dropping a month there loses it outright. Enabling
    retention on it must never be a quiet default.
    """
    _stub_effective(monkeypatch)

    with pytest.raises(HTTPException) as e:
        await ap.set_retention(
            ap.RetentionRequest(table="behavior_events", months=24),
            admin=SUPERADMIN, db=_FakeDb())
    # The message must name what is happening, not call it "shortening".
    assert "enabling retention" in e.value.detail
    assert "indefinitely" in e.value.detail


@pytest.mark.asyncio
async def test_an_unknown_table_is_rejected_at_the_api(monkeypatch):
    _stub_effective(monkeypatch)

    with pytest.raises(HTTPException) as e:
        await ap.set_retention(
            ap.RetentionRequest(table="completed_trades", months=6),
            admin=SUPERADMIN, db=_FakeDb())
    assert e.value.status_code == 400


@pytest.mark.asyncio
async def test_a_reset_back_to_a_shorter_default_still_needs_the_phrase(monkeypatch):
    """
    "Reset to default" sounds harmless and is not: going back to 6 from an
    admin-set 24 makes eighteen months of data eligible in one click.
    """
    _stub_effective(monkeypatch, orders=24)

    with pytest.raises(HTTPException) as e:
        await ap.set_retention(
            ap.RetentionRequest(table="orders", reset=True),
            admin=SUPERADMIN, db=_FakeDb())
    assert ap.CONFIRM_PHRASE in e.value.detail


@pytest.mark.asyncio
async def test_a_real_maintenance_run_without_the_phrase_is_refused(monkeypatch):
    async def _months(db):
        return {"orders": 6, "behavior_events": None}
    monkeypatch.setattr(policy, "get_effective_months", _months)

    with pytest.raises(HTTPException) as e:
        await ap.run_maintenance(
            ap.MaintenanceRequest(dry_run=False), admin=SUPERADMIN, db=_FakeDb())
    assert e.value.status_code == 400
    assert ap.CONFIRM_PHRASE in e.value.detail


def test_the_dry_run_is_the_default():
    """
    The safe option should be the one you get by not thinking about it. A
    request body with no `dry_run` must not delete anything.
    """
    assert ap.MaintenanceRequest().dry_run is True
    assert ap.MaintenanceRequest(confirm=ap.CONFIRM_PHRASE).dry_run is True


def test_the_dry_run_reports_what_the_gate_would_refuse():
    """
    A preview that showed only what WOULD be dropped, and stayed silent about
    what the gate would hold back, would be the most misleading version of this
    screen.
    """
    src = inspect.getsource(ap.run_maintenance)
    assert "would_skip" in src
    assert "snapshot_status_for_month" in src


# ── the health signal ──────────────────────────────────────────────────────

def test_a_missing_last_run_record_is_not_reported_as_success():
    """
    The record lives in Redis and is lost on a flush. "No record" must read as
    unknown; treating it as a clean run would make the panel actively
    misleading exactly when something is wrong.
    """
    src = inspect.getsource(ap.partition_overview)
    assert "read_last_run()" in src
    assert '"last_run": read_last_run()' in src

    page = (BACKEND.parent / "src" / "pages" / "admin" / "AdminPartitions.tsx").read_text(
        encoding="utf-8")
    assert "No run recorded" in page
    assert "means unknown" in page


def test_row_counts_are_labelled_as_estimates():
    """
    They come from `reltuples`, which ANALYZE maintains and which is wrong
    between runs. Presenting an estimate as a count is how someone concludes
    the wrong thing about a table they are about to prune.
    """
    src = inspect.getsource(ap._partition_rows)
    assert "reltuples" in src
    assert '"rows_are_estimated": True' in src

    page = (BACKEND.parent / "src" / "pages" / "admin" / "AdminPartitions.tsx").read_text(
        encoding="utf-8")
    assert "estimated" in page


def test_a_never_analysed_partition_does_not_report_negative_rows():
    """`reltuples` is -1 for a table that has never been analysed."""
    src = inspect.getsource(ap._partition_rows)
    assert "max(int(est_rows or 0), 0)" in src


def test_rows_in_the_default_partition_are_counted_exactly():
    """
    Anything but zero here means the window has already lapsed and rows are
    landing outside every declared month. That is the silent failure the page
    exists for, so it is worth an exact count rather than an estimate.
    """
    src = inspect.getsource(ap._default_partition_occupancy)
    assert "count(*)" in src
    assert "ONLY" in src, "without ONLY this would count the whole parent table"


def test_default_occupancy_drives_a_critical_health_state():
    src = inspect.getsource(ap.partition_overview)
    assert "if default_rows:" in src
    assert '"critical"' in src


def test_the_runway_stops_at_the_first_gap():
    """
    A partition beyond a hole does not help the rows that fall in the hole, so
    counting all future partitions would overstate the runway and hide exactly
    the state this is watching for.
    """
    src = inspect.getsource(ap.partition_overview)
    body = src[src.index("runway = 0"):src.index("default_rows")]
    assert "break" in body


def test_the_runway_threshold_matches_the_ci_guard():
    """
    Two different numbers for "how much warning do we want" would mean CI going
    red while the panel says healthy, or the reverse.
    """
    import tests.test_partition_runway as runway

    assert ap.MIN_RUNWAY_MONTHS == runway.MIN_MONTHS_OF_RUNWAY


# ── partition naming, the thing that decides what can be dropped ───────────

def test_the_default_partition_is_never_a_deletion_candidate():
    from app.tasks.maintenance_tasks import partition_month

    assert partition_month("orders", "orders_y2026m02") == date(2026, 2, 1)
    assert partition_month("orders", "orders_default") is None


def test_one_parents_pattern_cannot_match_anothers_partitions():
    """
    Both parents roll on the same beat. A regex that reached across would let
    an `orders` retention window drop a `behavior_events` month.
    """
    from app.tasks.maintenance_tasks import partition_month

    assert partition_month("orders", "behavior_events_y2026m07") is None
    assert partition_month("behavior_events", "orders_y2026m07") is None


def test_a_none_window_yields_no_candidates():
    """`behavior_events` is None, so nothing about it is ever eligible."""
    src = inspect.getsource(
        __import__("app.tasks.maintenance_tasks", fromlist=["x"]).expired_partitions)
    assert "if not keep_months:" in src
    assert "return []" in src


# ── the split-out job pieces still behave like the original ────────────────

def test_creation_and_retention_are_separate_so_creation_can_be_safe():
    """
    The admin "create missing partitions" button must be incapable of dropping
    anything. That is only true because creation is its own function.
    """
    from app.tasks import maintenance_tasks as mt

    create_src = inspect.getsource(mt._ensure_partitions)
    assert "DROP" not in create_src.upper()
    assert "CREATE TABLE" in create_src

    assert inspect.getsource(ap.ensure_partitions).count("_ensure_partitions") >= 1
    assert "_apply_retention" not in inspect.getsource(ap.ensure_partitions)


def test_the_beat_still_does_both_halves():
    """Splitting them must not have quietly dropped one from the schedule."""
    from app.tasks import maintenance_tasks as mt

    src = inspect.getsource(mt.ensure_behavior_event_partitions)
    assert "_ensure_partitions" in src
    assert "_apply_retention" in src
    assert "get_effective_months" in src, "the beat must read the configured window"


def test_the_window_is_read_per_run_not_at_import():
    """
    An admin lengthening retention should take effect on the next beat. A
    module-level read would need a redeploy, which is the thing this replaced.
    """
    from app.tasks import maintenance_tasks as mt

    src = inspect.getsource(mt.ensure_behavior_event_partitions)
    assert src.index("get_effective_months") < src.index("_apply_retention")


def test_recording_the_run_never_breaks_the_run():
    """
    It is a status badge. Redis being down must not turn a successful
    maintenance run into a failed one.
    """
    from app.tasks import maintenance_tasks as mt

    src = inspect.getsource(mt.record_last_run)
    assert "except Exception" in src
    assert "raise" not in src


# ── fail-safe reads ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_an_unreadable_settings_store_falls_back_to_the_code_values():
    """
    THE DIRECTION MATTERS. A settings table that cannot be read must never
    resolve to a SHORTER window — a retention system whose failure mode is
    "delete more" is not a retention system.
    """
    class _Broken:
        async def execute(self, *a, **kw):
            raise RuntimeError("settings table is on fire")

    effective = await policy.get_effective(_Broken())

    assert effective["orders"]["months"] == 6
    assert effective["orders"]["source"] == "code"
    assert effective["behavior_events"]["months"] is None


@pytest.mark.asyncio
async def test_a_stored_value_that_no_longer_validates_is_ignored():
    """
    If the floor is ever raised, an older stored value below it must not keep
    taking effect. It falls back to the code value and says so loudly.
    """
    class _Row:
        key = policy.setting_key("orders")
        value = 1                        # below the floor
        updated_by = "someone@old"
        updated_at = None

    class _Db:
        async def execute(self, *a, **kw):
            class _R:
                @staticmethod
                def scalars():
                    class _S:
                        @staticmethod
                        def all():
                            return [_Row()]
                    return _S()
            return _R()

    effective = await policy.get_effective(_Db())
    assert effective["orders"]["months"] == 6
    assert effective["orders"]["source"] == "code"


def test_the_retention_keys_are_not_reachable_from_the_generic_config_endpoint():
    """
    /config/global validates against admin_settings_service.DEFAULTS. Keeping
    the retention keys out of it means this validated path — with its floor and
    its confirmation — is the only way to set them.
    """
    from app.services import admin_settings_service as settings_svc

    for parent in policy.RETENTION_MONTHS:
        assert policy.setting_key(parent) not in settings_svc.DEFAULTS


def test_the_policy_reuses_the_existing_settings_table():
    """No new table for two integers."""
    src = _src("services/retention_policy_service.py")
    assert "AdminSetting" in src
    assert "CREATE TABLE" not in src


def test_a_null_window_is_stored_as_json_null_not_sql_null():
    """
    `admin_settings.value` is JSONB NOT NULL. Writing Python None would violate
    the constraint and the save would fail at runtime, not in review.
    """
    src = inspect.getsource(policy.set_policy)
    assert "JSON.NULL" in src


def test_clearing_an_override_deletes_the_row():
    """
    Writing the code value back would leave `source` reading "admin" forever,
    which misreports who decided the window.
    """
    src = inspect.getsource(policy.clear_policy)
    assert "delete(AdminSetting)" in src


# ── the frontend surfaces the dangerous facts ──────────────────────────────

def _page() -> str:
    return (BACKEND.parent / "src" / "pages" / "admin" / "AdminPartitions.tsx").read_text(
        encoding="utf-8")


def test_the_page_has_no_delete_control():
    page = _page()
    for forbidden in ("deletePartition", "dropPartition", "method: 'DELETE'"):
        assert forbidden not in page


def test_the_page_says_which_table_is_not_snapshot_gated():
    """
    `orders` loses only order-level detail; `behavior_events` would lose the
    month outright. An admin setting a window needs to know which one they are
    looking at.
    """
    page = _page()
    assert "NOT snapshot-gated" in page
    assert "loses it outright" in page


def test_the_page_shows_a_retained_month_and_why():
    """A month held back by the gate must not look the same as one that is
    simply young."""
    page = _page()
    assert "RETAINED" in page
    assert "blocked_reason" in page


def test_the_confirmation_phrase_comes_from_the_server():
    """
    Hardcoding it in the UI would let the two drift, and the drift would only
    show up as an admin unable to confirm anything.
    """
    page = _page()
    assert "confirm_phrase" in page
    assert re.search(r"confirm !== data\?\.confirm_phrase", page)


def test_the_api_client_exposes_no_deletion_call():
    api = (BACKEND.parent / "src" / "lib" / "adminApi.ts").read_text(encoding="utf-8")
    section = api[api.index("Partitions & retention"):api.index("Admin IAM")]
    assert "DELETE" not in section
    for expected in ("partitions:", "partitionSnapshots:", "ensurePartitions:",
                     "snapshotMonth:", "runPartitionMaintenance:",
                     "setPartitionRetention:"):
        assert expected in section


def test_the_page_is_routed_and_reachable():
    app_src = (BACKEND.parent / "src" / "App.tsx").read_text(encoding="utf-8")
    assert 'path="partitions"' in app_src
    assert "AdminPartitions" in app_src

    layout = (BACKEND.parent / "src" / "pages" / "admin" / "AdminLayout.tsx").read_text(
        encoding="utf-8")
    assert "/admin/partitions" in layout
    # Support staff cannot act on any of it, so the entry is not shown to them.
    nav = layout[layout.index("/admin/partitions"):]
    nav = nav[:nav.index("\n")]
    assert "support" not in nav
