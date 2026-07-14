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
