"""
Maintenance tasks — Engine v2 P2.

ensure_behavior_event_partitions: monthly beat task that idempotently
creates the next N monthly partitions of behavior_events. Answers the
"what happens after June 2027?" problem — nobody creates partitions by
hand, ever. The DEFAULT partition remains only as a safety net if this
task somehow fails for months in a row (its rows can be re-homed later).
"""
import logging
from datetime import date

from app.core.celery_app import celery_app
from app.core.database import SessionLocal

logger = logging.getLogger(__name__)

MONTHS_AHEAD = 3


def _month_bounds(anchor: date, offset: int):
    """(first day of anchor's month + offset months, first day of the next)."""
    y = anchor.year + (anchor.month - 1 + offset) // 12
    m = (anchor.month - 1 + offset) % 12 + 1
    start = date(y, m, 1)
    ny = y + (m // 12)
    nm = m % 12 + 1
    end = date(ny, nm, 1)
    return start, end


@celery_app.task(name="app.tasks.maintenance_tasks.ensure_behavior_event_partitions",
                 bind=True, max_retries=2, default_retry_delay=300)
def ensure_behavior_event_partitions(self):
    import asyncio

    async def _run():
        from sqlalchemy import text
        created = []
        async with SessionLocal() as db:
            for offset in range(MONTHS_AHEAD + 1):  # current month + N ahead
                start, end = _month_bounds(date.today(), offset)
                name = f"behavior_events_y{start.year}m{start.month:02d}"
                exists = await db.execute(text(
                    "SELECT 1 FROM pg_tables WHERE schemaname='public' AND tablename=:t"
                ), {"t": name})
                if exists.scalar_one_or_none():
                    continue
                await db.execute(text(
                    f"CREATE TABLE {name} PARTITION OF behavior_events "
                    f"FOR VALUES FROM ('{start.isoformat()}') TO ('{end.isoformat()}')"
                ))
                created.append(name)
            if created:
                await db.commit()
                logger.info(f"[partitions] created: {created}")
        return created

    try:
        return {"created": asyncio.run(_run())}
    except Exception as exc:
        logger.error(f"[partitions] creation failed: {exc}")
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
