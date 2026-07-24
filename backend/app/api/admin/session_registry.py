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

SESS_PREFIX = "admin_sess:"      # admin_sess:{admin_id}:{jti} -> json (TTL = token life)
IX_PREFIX   = "admin_sess_ix:"   # admin_sess_ix:{admin_id} -> SET of jtis (index; no keyspace SCAN)


def _r():
    from app.core.redis_pool import get_sync_redis
    return get_sync_redis()


def _skey(admin_id: str, jti: str) -> str:
    return f"{SESS_PREFIX}{admin_id}:{jti}"


def _ixkey(admin_id: str) -> str:
    return f"{IX_PREFIX}{admin_id}"


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
        pipe = _r().pipeline()
        pipe.setex(_skey(admin_id, jti), ttl, payload)
        pipe.sadd(_ixkey(admin_id), jti)
        pipe.expire(_ixkey(admin_id), ttl)  # index outlives the newest session at most
        pipe.execute()
    except Exception as e:
        logger.warning(f"[admin session] register failed (non-fatal): {e}")


def unregister(admin_id: str, jti: str) -> None:
    try:
        pipe = _r().pipeline()
        pipe.delete(_skey(admin_id, jti))
        pipe.srem(_ixkey(admin_id), jti)
        pipe.execute()
    except Exception as e:
        logger.warning(f"[admin session] unregister failed (non-fatal): {e}")


def clear(admin_id: str) -> int:
    """Drop every live session for an admin (used on epoch bump). Returns count cleared.
    Uses the per-admin index SET — no keyspace SCAN."""
    try:
        r = _r()
        jtis = r.smembers(_ixkey(admin_id)) or []
        keys = [_skey(admin_id, j) for j in jtis]
        pipe = r.pipeline()
        if keys:
            pipe.delete(*keys)
        pipe.delete(_ixkey(admin_id))
        pipe.execute()
        return len(keys)
    except Exception as e:
        logger.warning(f"[admin session] clear failed (non-fatal): {e}")
        return 0


def list_active(admin_id: str, current_jti: str | None = None) -> list[dict]:
    """List live sessions via the index SET, pruning any whose session key has expired."""
    try:
        r = _r()
        jtis = list(r.smembers(_ixkey(admin_id)) or [])
        out, stale = [], []
        for jti in jtis:
            raw = r.get(_skey(admin_id, jti))
            if not raw:
                stale.append(jti)  # session key expired — drop from the index
                continue
            try:
                d = json.loads(raw)
            except Exception:
                continue
            ttl = r.ttl(_skey(admin_id, jti))
            d["expires_in"] = ttl if ttl and ttl > 0 else None
            d["is_current"] = (current_jti is not None and d.get("jti") == current_jti)
            out.append(d)
        if stale:
            r.srem(_ixkey(admin_id), *stale)
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
