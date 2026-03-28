"""Admin system health — Redis metrics, Celery, integrations, DB pool, online users."""
from fastapi import APIRouter, Depends
from app.api.admin.deps import get_current_admin
from app.core.config import settings
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/system")
async def get_system_health(_: dict = Depends(get_current_admin)):
    health = {}

    # ── Redis ────────────────────────────────────────────────────────────────
    try:
        import redis as redis_lib
        r = redis_lib.from_url(settings.REDIS_URL, decode_responses=True, socket_timeout=2)
        r.ping()
        info     = r.info("all")
        keyspace = r.info("keyspace")

        total_keys = sum(
            v.get("keys", 0)
            for v in keyspace.values()
            if isinstance(v, dict)
        )
        hits   = info.get("keyspace_hits",   0)
        misses = info.get("keyspace_misses", 0)
        hit_rate = round(hits / (hits + misses) * 100, 1) if (hits + misses) > 0 else None

        health["redis"] = {
            "status":            "ok",
            "version":           info.get("redis_version"),
            "uptime_days":       round(info.get("uptime_in_seconds", 0) / 86400, 1),
            "connected_clients": info.get("connected_clients"),
            "memory_used_mb":    round(info.get("used_memory", 0) / 1024 / 1024, 1),
            "memory_peak_mb":    round(info.get("used_memory_peak", 0) / 1024 / 1024, 1),
            "memory_max_mb":     round(info.get("maxmemory", 0) / 1024 / 1024, 1) or None,
            "total_keys":        total_keys,
            "hit_rate_pct":      hit_rate,
            "evicted_keys":      info.get("evicted_keys", 0),
            "keyspace_hits":     hits,
            "keyspace_misses":   misses,
            "ops_per_sec":       info.get("instantaneous_ops_per_sec"),
        }
    except Exception as e:
        health["redis"] = {"status": "error", "detail": str(e)[:120]}

    # ── Celery queues ─────────────────────────────────────────────────────────
    try:
        import redis as redis_lib
        r = redis_lib.from_url(settings.REDIS_URL, decode_responses=True, socket_timeout=2)
        health["celery"] = {
            "status":      "ok",
            "queue_depth": r.llen("celery"),
            "ai_queue":    r.llen("ai_worker"),
        }
    except Exception as e:
        health["celery"] = {"status": "unknown", "detail": str(e)[:120]}

    # ── Online users (in-memory WebSocket manager) ─────────────────────────
    try:
        from app.api.websocket import manager
        health["online_users"] = len(manager.active_connections)
    except Exception:
        health["online_users"] = None

    # ── WhatsApp / Gupshup ────────────────────────────────────────────────
    try:
        from app.services.whatsapp_service import whatsapp_service
        health["whatsapp"] = {
            "configured": whatsapp_service.is_configured,
            "provider":   whatsapp_service.provider,
        }
    except Exception:
        health["whatsapp"] = {"configured": False, "provider": "unknown"}

    # ── DB pool ───────────────────────────────────────────────────────────
    try:
        from app.core.database import engine
        pool = engine.pool
        health["db_pool"] = {
            "pool_size":       pool.size(),
            "checked_in":      pool.checkedin(),
            "checked_out":     pool.checkedout(),
            "overflow":        pool.overflow(),
        }
    except Exception:
        health["db_pool"] = None

    # ── Config flags ──────────────────────────────────────────────────────
    health["config"] = {
        "maintenance_mode": settings.MAINTENANCE_MODE,
        "environment":      settings.ENVIRONMENT,
        "sentry_enabled":   bool(settings.SENTRY_DSN),
    }

    return health


@router.post("/test-email")
async def test_email_delivery(admin: dict = Depends(get_current_admin)):
    """
    Send a test email to the authenticated admin's own address.
    Use this to verify SMTP configuration is correct.
    Returns success/error without exposing SMTP credentials.
    """
    to_email = admin.get("email")
    if not to_email:
        return {"success": False, "error": "No email address in admin token"}

    if not settings.SMTP_HOST:
        return {
            "success": False,
            "error": "SMTP_HOST is not configured. Set SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS in environment.",
        }

    try:
        from app.services.email_service import email_service
        subject = "TradeMentor Admin — SMTP test"
        html = (
            "<div style='font-family:monospace;padding:24px;background:#0a0a0f;color:#e2e8f0;border-radius:8px;'>"
            "<h2 style='color:#f59e0b;'>SMTP configuration OK</h2>"
            "<p>This test email was sent from the TradeMentor admin panel.</p>"
            f"<p style='color:#64748b;font-size:0.85rem;'>Sent to: {to_email}</p>"
            "</div>"
        )
        await email_service.send_email(to_email, subject, html)
        logger.info(f"Admin test email sent to {to_email} by {admin.get('email')}")
        return {"success": True, "sent_to": to_email}
    except Exception as e:
        logger.warning(f"Admin test email failed: {e}")
        return {"success": False, "error": str(e)[:200]}
