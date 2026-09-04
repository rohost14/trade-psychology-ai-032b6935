"""
Maintenance tasks — Engine v2 P2.

ensure_behavior_event_partitions: monthly beat task that idempotently
creates the next N monthly partitions of behavior_events. Answers the
"what happens after June 2027?" problem — nobody creates partitions by
hand, ever. The DEFAULT partition remains only as a safety net if this
task somehow fails for months in a row (its rows can be re-homed later).
"""
import logging
import re
from datetime import date

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.services.monthly_snapshot_service import (
    mark_pruned,
    snapshots_complete_for_month,
)
from app.services.retention_policy_service import (  # noqa: F401 - re-exported
    RETENTION_MONTHS,
)

logger = logging.getLogger(__name__)

#: How far ahead partitions are pre-created. Was 3, which is thin: the beat
#: runs on the 1st and 15th, so three months of runway means a worker outage of
#: about a quarter is enough to fall into the DEFAULT partition silently. Empty
#: monthly partitions cost essentially nothing, so a year of runway turns a
#: three-month failure window into a twelve-month one for no storage.
MONTHS_AHEAD = 12

#: Automatic retention, per partitioned parent. None = never drop.
#:
#: The values themselves now live in `retention_policy_service`, because an
#: admin may lengthen a window (or deliberately shorten one) without a
#: redeploy. Imported under the original name so this stays the obvious place
#: to look, and so the CODE value is what any caller without a DB session gets.
#:
#: Dropping a partition is instantaneous and reclaims the space outright, which
#: is the entire reason the tables are partitioned - the alternative is a mass
#: DELETE that bloats and needs a full vacuum to give anything back.
#:
#: `orders` is EVIDENCE, not history. F4 reads protective orders only within a
#: position's own lifetime, so six months is already far past anything a
#: detector can reach. Nothing is lost silently: a month's summary is written
#: and VERIFIED before its partition may be dropped (see the gate below), so
#: the trader keeps the shape of every month forever and loses only the
#: order-by-order detail.
#:
#: `behavior_events` is deliberately None. It is the trader's own behavioural
#: history and what analytics renders back to them; silently deleting it is a
#: PRODUCT decision, not a maintenance one, and an admin turning it on is a
#: separate explicit act guarded in the policy service.

#: Refuse to drop more than this many partitions in a single run. A wrong clock,
#: a bad timezone or a mistyped retention value should cost one month of data at
#: worst, not the whole table. Hitting the cap logs loudly and drops nothing.
MAX_DROPS_PER_RUN = 3

#: Where the last maintenance outcome is recorded for the admin panel.
PARTITION_RUN_KEY = "partitions:last_run"


def _month_bounds(anchor: date, offset: int):
    """(first day of anchor's month + offset months, first day of the next)."""
    y = anchor.year + (anchor.month - 1 + offset) // 12
    m = (anchor.month - 1 + offset) % 12 + 1
    start = date(y, m, 1)
    ny = y + (m // 12)
    nm = m % 12 + 1
    end = date(ny, nm, 1)
    return start, end


#: The partitioned parents this job manages, in the order it walks them.
PARTITIONED_PARENTS = ("behavior_events", "orders")


def partition_name_pattern(parent: str) -> str:
    """The regex a partition of `parent` must match to be considered for a drop.

    Deliberately anchored and parent-scoped: DEFAULT must never match, and one
    parent's regex must never reach another parent's partitions.
    """
    return rf"{parent}_y(\d{{4}})m(\d{{2}})"


def partition_month(parent: str, name: str):
    """The month a partition covers, or None if the name is not one of ours."""
    m = re.fullmatch(partition_name_pattern(parent), name)
    return date(int(m.group(1)), int(m.group(2)), 1) if m else None


async def list_partitions(db, parent: str) -> list[str]:
    """Every attached partition of `parent`, DEFAULT included, name-ordered."""
    from sqlalchemy import text

    rows = await db.execute(text(
        "SELECT c.relname FROM pg_class c "
        " JOIN pg_inherits i ON i.inhrelid = c.oid "
        " JOIN pg_class p ON p.oid = i.inhparent "
        " WHERE p.relname = :parent ORDER BY c.relname"
    ), {"parent": parent})
    return [r[0] for r in rows]


async def missing_partition_months(db, parent: str) -> list[date]:
    """Months inside the forward window that have no partition yet."""
    existing = set(await list_partitions(db, parent))
    missing = []
    for offset in range(MONTHS_AHEAD + 1):
        start, _ = _month_bounds(date.today(), offset)
        if f"{parent}_y{start.year}m{start.month:02d}" not in existing:
            missing.append(start)
    return missing


async def expired_partitions(db, parent: str, keep_months) -> list[str]:
    """
    Partitions whose ENTIRE range is older than the cutoff.

    Comparing the START would delete the month a trader is still trading in.
    Read-only: this is what both the job and the admin preview ask.
    """
    if not keep_months:
        return []                          # None = never drop
    cutoff, _ = _month_bounds(date.today(), -keep_months)
    doomed = []
    for name in await list_partitions(db, parent):
        month = partition_month(parent, name)
        if month is None:
            continue                       # DEFAULT and anything odd
        _, end = _month_bounds(month, 0)
        if end <= cutoff:
            doomed.append(name)
    return doomed


async def _ensure_partitions(db) -> list[str]:
    """
    Create any missing partition inside the forward window.

    A partitioned table whose window runs out does not error - it silently
    routes everything into the DEFAULT partition and stops being partitioned in
    practice, which is how the behavior_events window came within eight weeks
    of expiring unnoticed.
    """
    from sqlalchemy import text

    created = []
    for parent in PARTITIONED_PARENTS:
        for offset in range(MONTHS_AHEAD + 1):     # current month + N ahead
            start, end = _month_bounds(date.today(), offset)
            name = f"{parent}_y{start.year}m{start.month:02d}"
            exists = await db.execute(text(
                "SELECT 1 FROM pg_tables WHERE schemaname='public' AND tablename=:t"
            ), {"t": name})
            if exists.scalar_one_or_none():
                continue
            await db.execute(text(
                f"CREATE TABLE {name} PARTITION OF {parent} "
                f"FOR VALUES FROM ('{start.isoformat()}') TO ('{end.isoformat()}')"
            ))
            created.append(name)
    return created


async def _apply_retention(db, retention: dict) -> tuple[list[str], list[str]]:
    """
    Drop partitions wholly older than the window. Returns (dropped, skipped).

    This is the half that was never automated. Creating partitions forever
    without ever dropping one just means the table grows and someone deals with
    it later, by hand, under pressure.

    Safe by construction: a partition is only ever dropped when its ENTIRE
    range is older than the cutoff, the DEFAULT partition is never touched, no
    run may drop more than MAX_DROPS_PER_RUN, and for `orders` the month must
    already be summarised and verified.
    """
    from sqlalchemy import text

    dropped, skipped = [], []
    for parent, keep_months in retention.items():
        if not keep_months:
            continue                       # None = never drop
        doomed = await expired_partitions(db, parent, keep_months)

        if len(doomed) > MAX_DROPS_PER_RUN:
            logger.error(
                f"[partitions] REFUSING to drop {len(doomed)} {parent} "
                f"partitions in one run (cap {MAX_DROPS_PER_RUN}): "
                f"{doomed}. Check the clock and RETENTION_MONTHS."
            )
            continue
        for name in doomed:
            # ── THE GATE ───────────────────────────────────────────────────
            #
            # A month is never traded away for storage on the assumption its
            # summary probably worked. The snapshot for every account with
            # orders in that month must exist AND verify; anything short of
            # that and the partition simply stays and is retried on the next
            # run. Retention that cannot prove what it preserved is just
            # deletion.
            month = partition_month(parent, name)
            if parent == "orders":
                try:
                    ok = await snapshots_complete_for_month(db, month)
                except Exception as err:   # noqa: BLE001 - retained
                    logger.error(
                        f"[partitions] snapshot check failed for {month}: "
                        f"{err} - {name} retained"
                    )
                    ok = False
                if not ok:
                    skipped.append(name)
                    continue
                # Commit the snapshots BEFORE the drop. If the drop then fails
                # we still hold both the summaries and the data; sharing one
                # transaction would roll the snapshots back with the failed
                # drop and lose the work.
                await db.commit()

            # Announce the drop to the event-trigger guard from migration 093,
            # which otherwise refuses any DROP on these tables. SET LOCAL dies
            # with the transaction, so the permission cannot leak past this
            # statement. This is the ONLY place in the codebase that sets it.
            await db.execute(text("SET LOCAL tm.allow_drop = 'on'"))
            await db.execute(text(f"DROP TABLE IF EXISTS {name}"))
            if parent == "orders":
                # AFTER the drop, in the drop's own transaction: the flag says
                # "the raw orders are gone", so it must not be able to survive
                # a drop that did not happen.
                await mark_pruned(db, month)
            dropped.append(name)

    if skipped:
        logger.warning(f"[partitions] retained pending snapshots: {skipped}")
    return dropped, skipped


def record_last_run(result: dict) -> None:
    """
    Best-effort record of the last maintenance outcome, for the admin panel.

    Redis, not a table: it is a health signal, not a fact about a trader, and
    losing it costs a status badge rather than any data. The admin view says
    "unknown" if it is not there rather than implying the job ran cleanly.
    """
    import json
    from datetime import datetime, timezone

    try:
        _get_redis().set(
            PARTITION_RUN_KEY,
            json.dumps({**result, "at": datetime.now(timezone.utc).isoformat()}),
        )
    except Exception as err:                       # noqa: BLE001 - best effort
        logger.warning(f"[partitions] could not record last run: {err}")


def read_last_run() -> dict | None:
    import json

    try:
        raw = _get_redis().get(PARTITION_RUN_KEY)
        return json.loads(raw) if raw else None
    except Exception as err:                       # noqa: BLE001 - best effort
        logger.warning(f"[partitions] could not read last run: {err}")
        return None


@celery_app.task(name="app.tasks.maintenance_tasks.ensure_behavior_event_partitions",
                 bind=True, max_retries=2, default_retry_delay=300)
def ensure_behavior_event_partitions(self):
    import asyncio

    async def _run():
        from app.services.retention_policy_service import get_effective_months

        async with SessionLocal() as db:
            created = await _ensure_partitions(db)
            # The window is read per run, so an admin lengthening it takes
            # effect on the next beat without a redeploy. Fail-safe: an
            # unreadable settings store resolves to the code values.
            retention = await get_effective_months(db)
            dropped, skipped = await _apply_retention(db, retention)

            if created or dropped:
                await db.commit()
                if created:
                    logger.info(f"[partitions] created: {created}")
                if dropped:
                    logger.warning(f"[partitions] dropped past retention: {dropped}")
        return {"created": created, "dropped": dropped, "skipped": skipped}

    try:
        result = asyncio.run(_run())
        record_last_run({**result, "ok": True})
        return result
    except Exception as exc:
        logger.error(f"[partitions] creation failed: {exc}")
        record_last_run({"ok": False, "error": str(exc)})
        raise self.retry(exc=exc)


@celery_app.task(name="app.tasks.maintenance_tasks.snapshot_previous_month",
                 bind=True, max_retries=2, default_retry_delay=600)
def snapshot_previous_month(self):
    """
    Write last month's summary for every account that traded in it.

    WHY THIS RUNS MONTHLY AND NOT AT DELETION TIME

    The deletion gate would build a snapshot on demand, six months late. Two
    reasons not to rely on that. First, a trader should be able to see "August:
    147 orders, 12 cancelled" in September, not only once August is being
    deleted. Second, building six months of snapshots for every account inside
    the partition-drop run turns a fast maintenance task into a long one, and a
    long one that fails halfway leaves the gate closed for reasons nobody can
    see.

    Idempotent: an existing valid snapshot is returned untouched, never
    rewritten. Re-running is a no-op, which is what makes it safe to schedule
    twice for redundancy.
    """
    import asyncio

    async def _run():
        from app.services.monthly_snapshot_service import (
            accounts_with_orders_in_month, ensure_snapshot,
        )
        month, _ = _month_bounds(date.today(), -1)
        written, failed = [], []
        async with SessionLocal() as db:
            for account_id in await accounts_with_orders_in_month(db, month):
                snap = await ensure_snapshot(db, account_id, month)
                (written if snap is not None else failed).append(str(account_id))
            await db.commit()
        if failed:
            # Not fatal: the gate will refuse to drop the month, which is the
            # correct outcome. Loud because a persistent failure means a month
            # is being retained indefinitely and someone should know why.
            logger.error(
                f"[snapshot] {month}: {len(failed)} accounts could not be "
                f"snapshotted: {failed}"
            )
        logger.info(f"[snapshot] {month}: wrote/verified {len(written)} accounts")
        return {"month": month.isoformat(), "written": written, "failed": failed}

    try:
        return asyncio.run(_run())
    except Exception as exc:
        logger.error(f"[snapshot] monthly run failed: {exc}")
        raise self.retry(exc=exc)


def _get_redis():
    from app.core.redis_pool import get_sync_redis
    return get_sync_redis()


@celery_app.task(name="app.tasks.maintenance_tasks.check_capital_reality",
                 bind=True, max_retries=1)
def check_capital_reality(self):
    """
    Capital-vs-margin validation (user gap, docsreview/03 Part 2 section 4).
    Declared trading_capital drives every %-of-capital rule; if it is 4x the
    real account, every rule is 4x too loose. Compare declared vs actual
    deployable (latest margin snapshot), nudge on PERSISTENT discrepancy
    (>1.5x for 3+ consecutive daily checks). NEVER auto-overwrite - capital
    drives rule psychology; nudge + one-tap update only.
    """
    import asyncio
    return asyncio.run(_capital_reality())


async def _capital_reality():
    from datetime import datetime, timedelta, timezone
    from uuid import uuid4
    from sqlalchemy import select, and_, desc
    from app.models.user_profile import UserProfile
    from app.models.margin_snapshot import MarginSnapshot
    from app.models.risk_alert import RiskAlert
    from app.core.metrics import incr

    BAND = 1.5
    STREAK_NEEDED = 3
    nudged = []

    async with SessionLocal() as db:
        profiles = (await db.execute(
            select(UserProfile).where(UserProfile.trading_capital.isnot(None))
        )).scalars().all()

        for prof in profiles:
            declared = float(prof.trading_capital or 0)
            if declared <= 0:
                continue
            snap = (await db.execute(
                select(MarginSnapshot)
                .where(MarginSnapshot.broker_account_id == prof.broker_account_id)
                .order_by(desc(MarginSnapshot.snapshot_at))
                .limit(1)
            )).scalar_one_or_none()
            if not snap:
                continue
            actual = float(snap.equity_available or 0) + float(snap.equity_used or 0)
            if actual <= 0:
                continue

            streak_key = f"capital_mismatch_streak:{prof.broker_account_id}"
            try:
                r = _get_redis()
                if declared > actual * BAND:
                    streak = int(r.incr(streak_key))
                    r.expire(streak_key, 14 * 86400)
                else:
                    r.delete(streak_key)
                    continue
            except Exception:
                continue

            if streak < STREAK_NEEDED:
                continue

            recent = (await db.execute(
                select(RiskAlert).where(and_(
                    RiskAlert.broker_account_id == prof.broker_account_id,
                    RiskAlert.pattern_type == "capital_mismatch",
                    RiskAlert.detected_at >= datetime.now(timezone.utc) - timedelta(days=7),
                ))
            )).scalars().first()
            if recent:
                continue

            ratio = declared / actual
            db.add(RiskAlert(
                id=uuid4(),
                broker_account_id=prof.broker_account_id,
                pattern_type="capital_mismatch",
                severity="caution",
                message=(
                    f"Your rules assume Rs {declared:,.0f} capital, but your account "
                    f"shows about Rs {actual:,.0f}. Your percent-of-capital rules are "
                    f"effectively {ratio:.1f}x looser than you set them. "
                    f"Update your capital in My Rules."
                ),
                details={"declared_capital": declared, "actual_deployable": round(actual),
                         "ratio": round(ratio, 2), "rule": "capital_reality"},
                detector_version="1.0.0",
                confidence=90.0,
                detected_at=datetime.now(timezone.utc),
            ))
            await db.commit()
            incr("capital_mismatch_nudges")
            nudged.append(str(prof.broker_account_id))
            logger.warning(f"[capital] mismatch nudge: declared {declared} vs actual {actual}")

    return {"nudged": nudged}


@celery_app.task(name="app.tasks.maintenance_tasks.recognize_tilt_recovery",
                 bind=True, max_retries=1)
def recognize_tilt_recovery(self):
    """
    Tilt Recovery (user gap #3): the only positive-reinforcement signal in
    the system. EOD: danger+ alert fired today AND zero trades after it ->
    tell the trader the system worked. Push nudge + evidence row (info).
    Deliberately NOT a score credit (user V4: no positive credits in v1).
    """
    import asyncio
    return asyncio.run(_tilt_recovery())


async def _tilt_recovery():
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo
    from sqlalchemy import select, and_, desc, func
    from app.models.risk_alert import RiskAlert
    from app.models.completed_trade import CompletedTrade
    from app.models.behavior_event import BehaviorEvent
    from app.core.metrics import incr

    IST = ZoneInfo("Asia/Kolkata")
    now = datetime.now(timezone.utc)
    day_start = datetime.now(IST).replace(hour=0, minute=0, second=0,
                                          microsecond=0).astimezone(timezone.utc)
    recognized = []

    async with SessionLocal() as db:
        accounts = (await db.execute(
            select(RiskAlert.broker_account_id).where(and_(
                RiskAlert.detected_at >= day_start,
                RiskAlert.severity.in_(("danger", "critical")),
            )).distinct()
        )).scalars().all()

        for acc in accounts:
            last_alert = (await db.execute(
                select(RiskAlert).where(and_(
                    RiskAlert.broker_account_id == acc,
                    RiskAlert.detected_at >= day_start,
                    RiskAlert.severity.in_(("danger", "critical")),
                )).order_by(desc(RiskAlert.detected_at)).limit(1)
            )).scalar_one_or_none()
            if not last_alert or not last_alert.detected_at:
                continue

            after = (await db.execute(
                select(func.count()).select_from(CompletedTrade).where(and_(
                    CompletedTrade.broker_account_id == acc,
                    CompletedTrade.entry_time > last_alert.detected_at,
                ))
            )).scalar()
            if after and after > 0:
                continue  # kept trading - no recognition

            already = (await db.execute(
                select(BehaviorEvent).where(and_(
                    BehaviorEvent.broker_account_id == acc,
                    BehaviorEvent.detector == "tilt_recovery",
                    BehaviorEvent.detected_at >= day_start,
                ))
            )).scalars().first()
            if already:
                continue

            pattern_name = (last_alert.pattern_type or "risk").replace("_", " ")
            msg = (f"You stopped trading after the {pattern_name} alert today. "
                   f"No trades since. That is the discipline working.")
            db.add(BehaviorEvent(
                broker_account_id=acc,
                detector="tilt_recovery",
                detector_version="1.0.0",
                severity="info",
                confidence=100.0,
                data_quality="GOOD",
                message=msg,
                evidence={"after_alert": str(last_alert.pattern_type),
                          "alert_at": last_alert.detected_at.isoformat(),
                          "trades_after": 0, "positive": True},
                input_snapshot=None,
                detected_at=now,
            ))
            await db.commit()

            try:
                from app.services.push_notification_service import push_service
                await push_service.send_notification(
                    broker_account_id=acc,
                    title="You stopped. That counts.",
                    body=msg, db=db,
                    data={"type": "tilt_recovery"},
                    severity="info", tag="tilt-recovery",
                )
            except Exception as _p:
                logger.warning(f"[tilt_recovery] push failed: {_p}")
            incr("tilt_recovery_recognitions")
            recognized.append(str(acc))

    return {"recognized": recognized}
