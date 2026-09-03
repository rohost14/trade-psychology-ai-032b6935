"""
Build the immutable monthly summary that must exist before a month's orders
may be dropped.

WHAT THIS PROTECTS, PRECISELY

Dropping an `orders` partition does not touch trades, P&L, rule violations or
detector events — those live in completed_trades, risk_alerts and
behavior_events, none of which is under retention. So the part of a snapshot
that genuinely rescues something is the ORDER-LEVEL record: how many orders
were placed, how many were cancelled or rejected, and the protective-stop
evidence F4 reads (SL/SL-M placement, trigger prices, modifications). That has
no other home.

The trade and behaviour aggregates are stored alongside it anyway, so a month
can be rendered from one row instead of fanning out across four tables — and so
the summary stays readable long after the code that produced it has changed.

IMMUTABLE. A snapshot is written once per (account, month) and never rewritten.
A summary that can change after the raw data is gone is not a record of
anything, so re-running is a verified no-op rather than an overwrite.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.monthly_snapshot import MonthlySnapshot

logger = logging.getLogger(__name__)

IST_OFFSET = timedelta(hours=5, minutes=30)

#: Bump when the meaning of a field changes, never when a field is added.
SNAPSHOT_VERSION = 1


def month_bounds_utc(month: date) -> tuple[datetime, datetime]:
    """[start, end) of an IST calendar month, expressed in UTC."""
    start_ist = datetime(month.year, month.month, 1)
    ny, nm = (month.year + 1, 1) if month.month == 12 else (month.year, month.month + 1)
    end_ist = datetime(ny, nm, 1)
    return (
        (start_ist - IST_OFFSET).replace(tzinfo=timezone.utc),
        (end_ist - IST_OFFSET).replace(tzinfo=timezone.utc),
    )


async def accounts_with_orders_in_month(db: AsyncSession, month: date) -> List[UUID]:
    """Every account holding orders in the month — the set that must be snapshotted."""
    start, end = month_bounds_utc(month)
    rows = await db.execute(
        text(
            "SELECT DISTINCT broker_account_id FROM orders "
            " WHERE order_timestamp >= :s AND order_timestamp < :e"
        ),
        {"s": start, "e": end},
    )
    return [r[0] for r in rows]


async def build_metrics(db: AsyncSession, account_id: UUID, month: date) -> Dict[str, Any]:
    """
    One query per source table, all scalar aggregates.

    Deliberately NOT a per-trade loop: this runs for every account with activity
    in a month, and a snapshot job that costs O(trades) round trips would be a
    worse problem than the storage it exists to reclaim.
    """
    start, end = month_bounds_utc(month)
    params = {"aid": str(account_id), "s": start, "e": end}

    # ── the part that is actually lost with the partition ─────────────────
    orders = (await db.execute(text(
        "SELECT count(*)                                              AS total,"
        "       count(*) FILTER (WHERE status = 'CANCELLED')           AS cancelled,"
        "       count(*) FILTER (WHERE status = 'REJECTED')            AS rejected,"
        "       count(*) FILTER (WHERE order_type IN ('SL','SL-M'))    AS protective,"
        "       count(*) FILTER (WHERE order_type IN ('SL','SL-M')"
        "                          AND status = 'CANCELLED')           AS protective_cancelled,"
        "       count(*) FILTER (WHERE exchange_update_timestamp IS NOT NULL"
        "                          AND exchange_update_timestamp > order_timestamp) AS modified"
        "  FROM orders"
        " WHERE broker_account_id = :aid AND order_timestamp >= :s AND order_timestamp < :e"
    ), params)).one()

    # ── durable aggregates, kept for rendering rather than for rescue ──────
    trades = (await db.execute(text(
        "SELECT count(*)                                        AS total,"
        "       count(DISTINCT date(exit_time))                  AS trading_days,"
        "       coalesce(sum(realized_pnl), 0)                   AS pnl,"
        "       count(*) FILTER (WHERE realized_pnl > 0)          AS wins,"
        "       count(*) FILTER (WHERE realized_pnl < 0)          AS losses"
        "  FROM completed_trades"
        " WHERE broker_account_id = :aid AND exit_time >= :s AND exit_time < :e"
    ), params)).one()

    alert_rows = await db.execute(text(
        "SELECT pattern_type, count(*) FROM risk_alerts"
        " WHERE broker_account_id = :aid AND detected_at >= :s AND detected_at < :e"
        " GROUP BY 1"
    ), params)
    alerts = {r[0]: r[1] for r in alert_rows}

    total_trades = int(trades.total or 0)
    wins = int(trades.wins or 0)
    losses = int(trades.losses or 0)

    return {
        # what the partition drop destroys
        "orders": {
            "total": int(orders.total or 0),
            "cancelled": int(orders.cancelled or 0),
            "rejected": int(orders.rejected or 0),
            "protective_placed": int(orders.protective or 0),
            "protective_cancelled": int(orders.protective_cancelled or 0),
            "modified": int(orders.modified or 0),
        },
        # what survives anyway, stored so one row renders the month
        "trades": {
            "total": total_trades,
            "trading_days": int(trades.trading_days or 0),
            "realized_pnl": float(trades.pnl or 0),
            "wins": wins,
            "losses": losses,
            "win_rate": round(wins / total_trades * 100, 1) if total_trades else None,
        },
        "alerts": {
            "total": sum(alerts.values()),
            "by_pattern": alerts,
            "rule_violations": alerts.get("constitution_violation", 0),
        },
    }


def _is_valid(metrics: Optional[Dict[str, Any]]) -> bool:
    """
    A snapshot counts as generated only if it actually describes the month.

    An empty dict, or one missing a section, means the build half-failed — and
    the whole point is that a partition is not dropped on the strength of a
    snapshot that says nothing.
    """
    if not metrics:
        return False
    return all(k in metrics for k in ("orders", "trades", "alerts"))


async def ensure_snapshot(
    db: AsyncSession, account_id: UUID, month: date
) -> Optional[MonthlySnapshot]:
    """
    Write the month's snapshot if it does not exist. Returns it, or None if it
    could not be produced — in which case the caller must NOT drop anything.

    Idempotent: an existing valid snapshot is returned untouched. Immutability
    is the point, so a second run never overwrites the first.
    """
    existing = (await db.execute(
        select(MonthlySnapshot).where(
            MonthlySnapshot.broker_account_id == account_id,
            MonthlySnapshot.month == month,
        )
    )).scalar_one_or_none()
    if existing is not None and _is_valid(existing.metrics):
        return existing

    try:
        metrics = await build_metrics(db, account_id, month)
    except Exception as err:                       # noqa: BLE001 - retained
        logger.error(f"[snapshot] build failed for {account_id} {month}: {err}")
        return None

    if not _is_valid(metrics):
        logger.error(f"[snapshot] built an empty snapshot for {account_id} {month}")
        return None

    try:
        from app.services.behavior_engine import ENGINE_VERSION as _EV
        detector_version = str(_EV)
    except Exception:                              # noqa: BLE001
        detector_version = None

    await db.execute(
        pg_insert(MonthlySnapshot)
        .values(
            broker_account_id=account_id,
            month=month,
            metrics=metrics,
            snapshot_version=SNAPSHOT_VERSION,
            detector_version=detector_version,
        )
        .on_conflict_do_nothing(constraint="uq_monthly_snapshot_account_month")
    )
    await db.flush()

    return (await db.execute(
        select(MonthlySnapshot).where(
            MonthlySnapshot.broker_account_id == account_id,
            MonthlySnapshot.month == month,
        )
    )).scalar_one_or_none()


async def snapshots_complete_for_month(db: AsyncSession, month: date) -> bool:
    """
    THE DELETION GATE.

    True only when every account with orders in this month has a snapshot whose
    metrics verify. Anything short of that and the partition stays: a month is
    never traded away for storage on the assumption the summary probably worked.
    """
    account_ids = await accounts_with_orders_in_month(db, month)
    if not account_ids:
        return True                                # nothing to preserve

    for account_id in account_ids:
        snap = await ensure_snapshot(db, account_id, month)
        if snap is None or not _is_valid(snap.metrics):
            logger.warning(
                f"[snapshot] {month} not fully snapshotted "
                f"(account {account_id}) — partition retained"
            )
            return False
    return True


async def mark_pruned(db: AsyncSession, month: date) -> None:
    """Record that the raw orders for this month are gone, so the UI can say so."""
    await db.execute(text(
        "UPDATE monthly_snapshots SET orders_pruned_at = now()"
        " WHERE month = :m AND orders_pruned_at IS NULL"
    ), {"m": month})


async def snapshot_status_for_month(db: AsyncSession, month: date) -> Dict[str, Any]:
    """
    READ-ONLY report of where a month stands. Never writes.

    `snapshots_complete_for_month` is the deletion gate and BUILDS what is
    missing as a side effect, which is right for the job and wrong for an admin
    looking at a screen: inspecting a system must not change it. This answers
    the same question without touching anything.
    """
    account_ids = await accounts_with_orders_in_month(db, month)
    rows = (await db.execute(
        select(MonthlySnapshot).where(MonthlySnapshot.month == month)
    )).scalars().all()

    by_account = {r.broker_account_id: r for r in rows}
    verified = [a for a in account_ids if _is_valid(getattr(by_account.get(a), "metrics", None))]
    missing = [str(a) for a in account_ids if a not in by_account]
    invalid = [
        str(a) for a in account_ids
        if a in by_account and not _is_valid(by_account[a].metrics)
    ]

    return {
        "month": month.isoformat(),
        "accounts_with_orders": len(account_ids),
        "snapshots_present": len([a for a in account_ids if a in by_account]),
        "snapshots_verified": len(verified),
        "missing_accounts": missing,
        "invalid_accounts": invalid,
        # The gate's answer, computed without invoking the gate. A month nobody
        # traded in is complete: there is nothing to preserve, and treating it
        # as blocked would retain empty partitions forever.
        "complete": not missing and not invalid,
        "pruned_at": next(
            (r.orders_pruned_at.isoformat() for r in rows if r.orders_pruned_at), None
        ),
        # Rows can outlive the accounts that produced them being re-snapshotted
        # for other months, so this counts the table, not just this month's set.
        "snapshot_rows": len(rows),
    }
