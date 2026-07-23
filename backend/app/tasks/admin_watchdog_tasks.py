"""Admin health watchdog — periodic infra check that emails superadmins on trouble.

Runs on Celery Beat. Checks DB reachability, Redis reachability, and the recent
application-error rate. On a problem it emails all active superadmins, guarded by a
Redis cooldown so a sustained outage does not spam.
"""
import asyncio
import logging
import time

from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)

COOLDOWN_KEY = "admin:watchdog:cooldown"
COOLDOWN_SEC = 30 * 60          # at most one alert email per 30 min
ERROR_SPIKE_WINDOW = 600        # 10 minutes
ERROR_SPIKE_THRESHOLD = 25      # >25 errors in 10 min = spike


def _sync_redis():
    from app.core.redis_pool import get_sync_redis
    return get_sync_redis()


async def _check_db() -> bool:
    try:
        from sqlalchemy import text
        from app.core.database import SessionLocal
        async with SessionLocal() as db:
            await db.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.warning(f"[watchdog] DB check failed: {e}")
        return False


def _check_redis() -> bool:
    try:
        _sync_redis().ping()
        return True
    except Exception as e:
        logger.warning(f"[watchdog] Redis check failed: {e}")
        return False


def _recent_error_count() -> int:
    try:
        import json
        from app.core.error_feed import FEED_KEY
        cutoff = time.time() - ERROR_SPIKE_WINDOW
        n = 0
        for item in _sync_redis().lrange(FEED_KEY, 0, 199):
            try:
                if json.loads(item).get("ts", 0) >= cutoff:
                    n += 1
            except Exception:
                continue
        return n
    except Exception:
        return 0


async def _superadmin_emails() -> list[str]:
    try:
        from sqlalchemy import select
        from app.core.database import SessionLocal
        from app.models.admin_user import AdminUser
        async with SessionLocal() as db:
            rows = (await db.execute(
                select(AdminUser.email).where(
                    AdminUser.role == "superadmin", AdminUser.is_active == True
                )
            )).scalars().all()
        return list(rows)
    except Exception as e:
        logger.warning(f"[watchdog] superadmin lookup failed: {e}")
        return []


async def _notify(problems: list[str]) -> int:
    emails = await _superadmin_emails()
    if not emails:
        return 0
    from app.services.email_service import email_service
    subject = "⚠ TradeMentor infrastructure alert"
    body = (
        "<div style='font-family:monospace;padding:24px;'>"
        "<h2 style='color:#e15a4d;'>Infrastructure alert</h2>"
        "<p>The admin watchdog detected:</p><ul>"
        + "".join(f"<li>{p}</li>" for p in problems)
        + "</ul><p style='color:#888;font-size:0.85rem;'>Check Admin → System.</p></div>"
    )
    sent = 0
    for e in emails:
        try:
            await email_service.send_email(e, subject, body)
            sent += 1
        except Exception as ex:
            logger.warning(f"[watchdog] alert email to {e} failed: {ex}")
    return sent


@celery_app.task(name="app.tasks.admin_watchdog_tasks.admin_health_watchdog")
def admin_health_watchdog():
    async def _run():
        problems: list[str] = []
        if not await _check_db():
            problems.append("Database is unreachable.")
        if not _check_redis():
            problems.append("Redis is unreachable.")
        spike = _recent_error_count()
        if spike > ERROR_SPIKE_THRESHOLD:
            problems.append(f"Error spike: {spike} errors in the last 10 minutes.")

        if not problems:
            return {"ok": True}

        # Cooldown so a sustained problem emails at most once / COOLDOWN_SEC.
        try:
            r = _sync_redis()
            if not r.set(COOLDOWN_KEY, "1", nx=True, ex=COOLDOWN_SEC):
                return {"ok": False, "problems": problems, "notified": 0, "cooldown": True}
        except Exception:
            pass

        sent = await _notify(problems)
        logger.error(f"[watchdog] ALERT: {'; '.join(problems)} (emailed {sent} superadmins)")
        return {"ok": False, "problems": problems, "notified": sent}

    return asyncio.run(_run())
