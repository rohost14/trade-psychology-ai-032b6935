"""
Admin view and controls for partitioning and retention.

WHAT THIS IS FOR

`orders` and `behavior_events` are RANGE-partitioned by month. A partitioned
table whose window runs out does not fail loudly — it silently routes every row
into the DEFAULT partition and stops being partitioned in practice. That is
exactly how the `behavior_events` window came within eight weeks of expiring
unnoticed, and it was caught only because someone happened to be verifying the
migration ledger. So the point of this page is that the state is VISIBLE before
it is a problem, not that it is fixable afterwards.

WHAT IT DELIBERATELY DOES NOT OFFER

There is no endpoint that drops a named partition. The only path that deletes
anything is the maintenance job, and it goes through the snapshot gate: for
`orders`, every account with orders in a month must have a verified summary
before that month may go. An admin can RUN that job, and can retry a month's
snapshots so a blocked month unblocks, but cannot reach past the gate — which
means the safety argument for six-month retention does not depend on anybody's
restraint.

Reads are open to any admin. Anything that mutates is superadmin-only, audited,
and — where it can destroy data — requires a typed confirmation phrase.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin.audit_writer import audit
from app.api.admin.deps import get_current_admin, require_role
from app.core.database import get_db
from app.services import retention_policy_service as policy

router = APIRouter()
logger = logging.getLogger(__name__)

#: Typed by an admin before anything can delete data. Not a yes/no dialog: the
#: point is that it cannot be clicked through by muscle memory.
CONFIRM_PHRASE = "DELETE OLD PARTITIONS"

#: Below this many months of forward partitions, the job is not keeping up and
#: the table is heading for the DEFAULT partition. Same threshold the CI runway
#: test uses, for the same reason: half a year is enough to notice and act
#: without any of it being urgent.
MIN_RUNWAY_MONTHS = 6


def _month_key(d: date) -> str:
    return f"y{d.year}m{d.month:02d}"


async def _partition_rows(db: AsyncSession, parent: str) -> List[Dict[str, Any]]:
    """
    Every partition of `parent`, with its declared range and what it costs.

    Row counts come from `pg_class.reltuples`, which is an ESTIMATE maintained
    by ANALYZE, and is labelled as one. An exact count(*) per partition would
    mean a full scan of every month on every page load — the wrong trade for a
    status screen, and a habit that gets worse exactly as the table gets big.
    """
    from app.tasks.maintenance_tasks import partition_month

    rows = await db.execute(text(
        "SELECT c.relname,"
        "       pg_get_expr(c.relpartbound, c.oid)      AS bounds,"
        "       c.reltuples::bigint                     AS est_rows,"
        "       pg_total_relation_size(c.oid)           AS total_bytes,"
        "       GREATEST(c.relpages, 0)                 AS pages"
        "  FROM pg_class c"
        "  JOIN pg_inherits i ON i.inhrelid = c.oid"
        "  JOIN pg_class p ON p.oid = i.inhparent"
        " WHERE p.relname = :parent"
        " ORDER BY c.relname"
    ), {"parent": parent})

    today = date.today()
    this_month = _month_key(today)
    out: List[Dict[str, Any]] = []
    for name, bounds, est_rows, total_bytes, _pages in rows:
        month = partition_month(parent, name)
        is_default = month is None
        if is_default:
            state = "default"
        elif _month_key(month) == this_month:
            state = "current"
        elif month > today:
            state = "future"
        else:
            state = "past"
        out.append({
            "name": name,
            "month": month.isoformat() if month else None,
            "bounds": bounds,
            # Negative reltuples means "never analysed", which is not zero rows.
            "estimated_rows": max(int(est_rows or 0), 0),
            "rows_are_estimated": True,
            "size_bytes": int(total_bytes or 0),
            "state": state,
            "is_default": is_default,
        })
    return out


async def _default_partition_occupancy(db: AsyncSession, parent: str) -> Optional[int]:
    """
    Rows sitting in DEFAULT. Anything but zero means the window lapsed and rows
    are landing outside every declared month — the silent failure this whole
    page exists to surface, so it is worth an exact count.
    """
    try:
        return (await db.execute(
            text(f"SELECT count(*) FROM ONLY {parent}_default")
        )).scalar_one()
    except Exception as err:                       # noqa: BLE001
        logger.warning(f"[admin/partitions] no DEFAULT for {parent}: {err}")
        return None


@router.get("/partitions")
async def partition_overview(
    _: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Full state of both partitioned tables: what exists, what is missing, what
    the retention window is, and whether the job that maintains it is healthy.
    """
    from app.tasks.maintenance_tasks import (
        MAX_DROPS_PER_RUN, MONTHS_AHEAD, PARTITIONED_PARENTS,
        expired_partitions, missing_partition_months, read_last_run,
    )

    effective = await policy.get_effective(db)
    today = date.today()
    tables = []

    for parent in PARTITIONED_PARENTS:
        parts = await _partition_rows(db, parent)
        months = sorted(p["month"] for p in parts if p["month"])
        missing = await missing_partition_months(db, parent)
        keep = effective[parent]["months"]

        # Runway = consecutive months from this one that already have a
        # partition. A gap ends it: a partition beyond a hole does not help the
        # rows that fall in the hole.
        runway = 0
        have = {p["month"] for p in parts if p["month"]}
        for offset in range(MONTHS_AHEAD + 1):
            y = today.year + (today.month - 1 + offset) // 12
            m = (today.month - 1 + offset) % 12 + 1
            if date(y, m, 1).isoformat() not in have:
                break
            runway += 1

        default_rows = await _default_partition_occupancy(db, parent)
        eligible = await expired_partitions(db, parent, keep)

        if default_rows:
            health, reason = "critical", (
                f"{default_rows} rows have landed in {parent}_default - the "
                f"declared window has already lapsed"
            )
        elif runway == 0:
            health, reason = "critical", "no partition exists for the current month"
        elif runway < MIN_RUNWAY_MONTHS:
            health, reason = "warning", (
                f"only {runway} months of runway left (want {MIN_RUNWAY_MONTHS})"
            )
        elif missing:
            health, reason = "warning", f"{len(missing)} month(s) missing inside the window"
        else:
            health, reason = "healthy", None

        tables.append({
            "table": parent,
            "retention": {
                **effective[parent],
                "floor_months": policy.RETENTION_FLOOR_MONTHS,
                "ceiling_months": policy.RETENTION_CEILING_MONTHS,
                # Only `orders` passes the snapshot gate. Saying so stops
                # anyone assuming behaviour history has the same protection.
                "snapshot_gated": parent == "orders",
            },
            "partition_count": len([p for p in parts if not p["is_default"]]),
            "first_month": months[0] if months else None,
            "last_month": months[-1] if months else None,
            "current_partition": next(
                (p["name"] for p in parts if p["state"] == "current"), None),
            "next_partition": next(
                (p["name"] for p in parts if p["state"] == "future"), None),
            "runway_months": runway,
            "min_runway_months": MIN_RUNWAY_MONTHS,
            "missing_months": [m.isoformat() for m in missing],
            "default_partition_rows": default_rows,
            "eligible_for_deletion": eligible,
            "total_size_bytes": sum(p["size_bytes"] for p in parts),
            "estimated_rows": sum(p["estimated_rows"] for p in parts),
            "health": health,
            "health_reason": reason,
            "partitions": parts,
        })

    return {
        "tables": tables,
        "months_ahead": MONTHS_AHEAD,
        "max_drops_per_run": MAX_DROPS_PER_RUN,
        "confirm_phrase": CONFIRM_PHRASE,
        # None when Redis has no record - which is NOT the same as a clean run,
        # and is rendered as "unknown" rather than as success.
        "last_run": read_last_run(),
    }


@router.get("/partitions/snapshots")
async def snapshot_overview(
    months: int = Query(18, ge=1, le=60),
    _: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Archive status per month: who has a snapshot, whether it verifies, whether
    the month may be deleted, and whether it already was.

    READ-ONLY. The deletion gate builds missing snapshots as a side effect,
    which is right for the job and wrong here — inspecting a system must not
    change it.
    """
    from app.services.monthly_snapshot_service import snapshot_status_for_month
    from app.tasks.maintenance_tasks import _month_bounds, expired_partitions

    keep = (await policy.get_effective(db))["orders"]["months"]
    expired = set(await expired_partitions(db, "orders", keep))

    present = (await db.execute(text(
        "SELECT DISTINCT date_trunc('month', order_timestamp)::date"
        "  FROM orders ORDER BY 1 DESC"
    ))).scalars().all()

    # Months whose orders are already gone still have snapshots, and they are
    # the whole point - a month is not missing from this list just because its
    # partition was dropped.
    snapshotted = (await db.execute(text(
        "SELECT DISTINCT month FROM monthly_snapshots ORDER BY 1 DESC"
    ))).scalars().all()

    all_months = sorted(set(present) | set(snapshotted), reverse=True)[:months]

    out = []
    for month in all_months:
        status = await snapshot_status_for_month(db, month)
        name = f"orders_y{month.year}m{month.month:02d}"
        status["partition"] = name
        status["partition_expired"] = name in expired
        # Eligible means BOTH: old enough, and provably preserved. Either alone
        # is not a reason to delete anything.
        status["eligible_for_deletion"] = (name in expired) and status["complete"]
        status["blocked_reason"] = (
            None if status["complete"]
            else (f"{len(status['missing_accounts'])} account(s) without a snapshot, "
                  f"{len(status['invalid_accounts'])} unverified")
        )
        out.append(status)

    return {"months": out, "retention_months": keep}


# ── controlled actions ─────────────────────────────────────────────────────

@router.post("/partitions/ensure")
async def ensure_partitions(
    admin: dict = Depends(require_role("superadmin", "ops")),
    db: AsyncSession = Depends(get_db),
):
    """
    Create any missing partition inside the forward window. Creates only —
    this path cannot drop anything, which is why it does not need a
    confirmation and is available to ops.
    """
    from app.tasks.maintenance_tasks import _ensure_partitions

    created = await _ensure_partitions(db)
    if created:
        await db.commit()
    await audit(db, admin.get("email", "?"), "partitions.ensure",
                target_type="partitions", details={"created": created})
    return {"created": created}


class SnapshotMonthRequest(BaseModel):
    month: str            # YYYY-MM or YYYY-MM-DD


@router.post("/partitions/snapshot-month")
async def snapshot_month(
    body: SnapshotMonthRequest,
    admin: dict = Depends(require_role("superadmin", "ops")),
    db: AsyncSession = Depends(get_db),
):
    """
    Build the missing snapshots for one month — the retry path for a month the
    job skipped.

    Writes summaries, never deletes. An existing snapshot is returned untouched
    because snapshots are immutable, so re-running is a verified no-op.
    """
    from app.services.monthly_snapshot_service import (
        accounts_with_orders_in_month, ensure_snapshot, snapshot_status_for_month,
    )

    try:
        parts = body.month.split("-")
        month = date(int(parts[0]), int(parts[1]), 1)
    except Exception:
        raise HTTPException(status_code=400, detail="month must be YYYY-MM")

    written, failed = [], []
    for account_id in await accounts_with_orders_in_month(db, month):
        snap = await ensure_snapshot(db, account_id, month)
        (written if snap is not None else failed).append(str(account_id))
    await db.commit()

    await audit(db, admin.get("email", "?"), "partitions.snapshot_month",
                target_type="month", target_id=month.isoformat(),
                details={"written": len(written), "failed": len(failed)})

    return {"month": month.isoformat(), "written": written, "failed": failed,
            "status": await snapshot_status_for_month(db, month)}


class MaintenanceRequest(BaseModel):
    #: True = report what WOULD happen and change nothing.
    dry_run: bool = True
    #: Required verbatim for a real run. Ignored on a dry run.
    confirm: Optional[str] = None


@router.post("/partitions/maintenance")
async def run_maintenance(
    body: MaintenanceRequest,
    admin: dict = Depends(require_role("superadmin")),
    db: AsyncSession = Depends(get_db),
):
    """
    Run the maintenance job by hand: create missing partitions, then apply
    retention through the snapshot gate.

    A real run can delete a month's orders, so it is superadmin-only and needs
    the confirmation phrase typed exactly. The dry run is the default and takes
    no confirmation — the safe thing should be the easy thing.

    Even a confirmed run cannot reach past the gate. It calls the same code the
    beat calls, so a month without verified snapshots is retained here too.
    """
    from app.tasks.maintenance_tasks import (
        _apply_retention, _ensure_partitions, expired_partitions,
        missing_partition_months, record_last_run,
    )
    from app.services.monthly_snapshot_service import snapshot_status_for_month
    from app.tasks.maintenance_tasks import partition_month

    retention = await policy.get_effective_months(db)

    if body.dry_run:
        would_create, would_drop, would_skip = [], [], []
        for parent in retention:
            would_create += [
                f"{parent}_y{m.year}m{m.month:02d}"
                for m in await missing_partition_months(db, parent)
            ]
            for name in await expired_partitions(db, parent, retention[parent]):
                if parent != "orders":
                    would_drop.append(name)
                    continue
                status = await snapshot_status_for_month(
                    db, partition_month(parent, name))
                (would_drop if status["complete"] else would_skip).append(name)
        return {
            "dry_run": True,
            "would_create": would_create,
            "would_drop": would_drop,
            "would_skip": would_skip,
            "confirm_phrase": CONFIRM_PHRASE,
        }

    if (body.confirm or "").strip() != CONFIRM_PHRASE:
        raise HTTPException(
            status_code=400,
            detail=f'type "{CONFIRM_PHRASE}" to confirm a run that can delete data',
        )

    created = await _ensure_partitions(db)
    dropped, skipped = await _apply_retention(db, retention)
    if created or dropped:
        await db.commit()

    result = {"created": created, "dropped": dropped, "skipped": skipped}
    record_last_run({**result, "ok": True, "by": admin.get("email")})
    await audit(db, admin.get("email", "?"), "partitions.maintenance_run",
                target_type="partitions", details=result)
    return {"dry_run": False, **result}


class RetentionRequest(BaseModel):
    table: str
    #: None / null = keep indefinitely.
    months: Optional[int] = None
    #: Drop the admin override and go back to the code value.
    reset: bool = False
    confirm: Optional[str] = None


@router.put("/partitions/retention")
async def set_retention(
    body: RetentionRequest,
    admin: dict = Depends(require_role("superadmin")),
    db: AsyncSession = Depends(get_db),
):
    """
    Change a table's retention window.

    Lengthening it, or setting it to null, can only ever keep more data, so it
    goes through unremarkably. NARROWING is what makes more data eligible for
    deletion — including the sharpest case, turning retention on for
    `behavior_events`, which has none — and that requires the confirmation
    phrase.

    The floor is not negotiable from here: below it, detectors would still be
    reading data that had been deleted.
    """
    current = (await policy.get_effective(db)).get(body.table)
    if current is None:
        raise HTTPException(status_code=400,
                            detail=f"unknown partitioned table: {body.table}")

    # A reset lands on the code value, and that can itself be a narrowing -
    # going back to 6 from an admin-set 24 makes eighteen months of data
    # eligible - so it is checked the same way rather than waved through.
    proposed = current["code_default"] if body.reset else body.months
    if not body.reset:
        try:
            proposed = policy.validate(body.table, body.months)
        except policy.RetentionPolicyError as err:
            raise HTTPException(status_code=400, detail=str(err))

    narrowing = policy.is_narrowing(body.table, current["months"], proposed)
    if narrowing and (body.confirm or "").strip() != CONFIRM_PHRASE:
        # Turning retention ON for a table that had none is the sharpest form
        # of narrowing, and reads nothing like "shortening" to the person doing
        # it. Name what is actually about to happen.
        what = (
            f"enabling retention on {body.table}, which is currently kept "
            f"indefinitely," if current["months"] is None
            else f"shortening {body.table} retention from "
                 f"{current['months']} to {proposed} months"
        )
        raise HTTPException(
            status_code=400,
            detail=f'{what} makes more data eligible for deletion - '
                   f'type "{CONFIRM_PHRASE}" to confirm',
        )

    if body.reset:
        updated = await policy.clear_policy(db, body.table, admin.get("email", "?"))
    else:
        updated = await policy.set_policy(db, body.table, proposed,
                                          admin.get("email", "?"))
    await audit(db, admin.get("email", "?"), "partitions.retention_change",
                target_type="table", target_id=body.table,
                details={"from": current["months"], "to": proposed,
                         "reset": body.reset, "narrowing": narrowing})
    return {"table": body.table, "retention": updated, "narrowing": narrowing}
