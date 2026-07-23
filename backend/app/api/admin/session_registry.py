"""Admin session registry + login recording.

Two complementary records of admin auth:
  - Redis registry of LIVE sessions (`admin_sess:{admin_id}:{jti}`), TTL = token life.
    Powers the "active sessions" view and per-session revoke. Cleared wholesale when an
    admin's session_epoch is bumped (force-logout / deactivate / reset / password change).
  - A durable `admin_login_events` DB row per successful login (who/when/where/how).

Best-effort: Redis/registry failures never block login.
"""
import json
import logging
import time

from fastapi import Request

logger = logging.getLogger(__name__)

SESS_PREFIX = "admin_sess:"   # admin_sess:{admin_id}:{jti} -> json


def _r():
    from app.core.redis_pool import get_sync_redis
    return get_sync_redis()


def client_ip(request: Request) -> str:
    from app.api.admin.deps import _get_client_ip
    return _get_client_ip(request)


def user_agent(request: Request) -> str:
    return (request.headers.get("User-Agent") or "")[:400]


def register(admin_id: str, jti: str, exp_ts: int, ip: str, ua: str, sv: int) -> None:
    try:
        ttl = int(exp_ts - time.time())
        if ttl <= 0:
            return
        payload = json.dumps({"jti": jti, "ip": ip, "ua": ua, "iat": int(time.time()), "sv": sv})
        _r().setex(f"{SESS_PREFIX}{admin_id}:{jti}", ttl, payload)
    except Exception as e:
        logger.warning(f"[admin session] register failed (non-fatal): {e}")


def unregister(admin_id: str, jti: str) -> None:
    try:
        _r().delete(f"{SESS_PREFIX}{admin_id}:{jti}")
    except Exception as e:
        logger.warning(f"[admin session] unregister failed (non-fatal): {e}")


def clear(admin_id: str) -> int:
    """Drop every live session for an admin (used on epoch bump). Returns count cleared."""
    try:
        r = _r()
        keys = list(r.scan_iter(match=f"{SESS_PREFIX}{admin_id}:*", count=200))
        if keys:
            r.delete(*keys)
        return len(keys)
    except Exception as e:
        logger.warning(f"[admin session] clear failed (non-fatal): {e}")
        return 0


def list_active(admin_id: str, current_jti: str | None = None) -> list[dict]:
    try:
        r = _r()
        out = []
        for key in r.scan_iter(match=f"{SESS_PREFIX}{admin_id}:*", count=200):
            raw = r.get(key)
            if not raw:
                continue
            try:
                d = json.loads(raw)
            except Exception:
                continue
            ttl = r.ttl(key)
            d["expires_in"] = ttl if ttl and ttl > 0 else None
            d["is_current"] = (current_jti is not None and d.get("jti") == current_jti)
            out.append(d)
        out.sort(key=lambda x: x.get("iat", 0), reverse=True)
        return out
    except Exception as e:
        logger.warning(f"[admin session] list failed (non-fatal): {e}")
        return []


async def record_login(db, admin, request: Request, method: str) -> None:
    """Best-effort durable login-history row."""
    try:
        from app.models.admin_login_event import AdminLoginEvent
        db.add(AdminLoginEvent(
            admin_id=admin.id, admin_email=admin.email,
            ip=client_ip(request), user_agent=user_agent(request), method=method,
        ))
        await db.commit()
    except Exception as e:
        logger.warning(f"[admin login-history] record failed (non-fatal): {e}")
