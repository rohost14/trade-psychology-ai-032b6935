"""
Cross-worker admin runtime state — maintenance mode + announcement banner.

Previously these lived in the Settings singleton (`settings.MAINTENANCE_MODE`) and a
module global (`config_api._announcement`), so a toggle only affected the ONE uvicorn
worker that served the request. With >1 worker the toggle half-applied with no obvious
cause. This module persists the state in Redis so every worker — and the public
announcement poll — observes the same value.

Reads fall back to the env-configured `settings.MAINTENANCE_MODE` / `_MESSAGE` when Redis
holds no override or is unavailable: the deploy-time `.env` maintenance path still works,
and Redis being down never forces the whole site into 503.

The maintenance flag is read on EVERY request (middleware), so it is cached in-process for
`MAINT_CACHE_TTL` seconds to bound Redis load; cross-worker changes converge within that
window (a toggle on the serving worker is reflected immediately — its cache is invalidated).
"""
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

_K_MAINT     = "admin_cfg:maintenance_mode"       # "1" / "0"
_K_MAINT_MSG = "admin_cfg:maintenance_message"
_K_ANNOUNCE  = "admin_cfg:announcement"

MAINT_CACHE_TTL = 5.0  # seconds

# process-local cache: (enabled, message, fetched_at_monotonic)
_maint_cache: Optional[tuple[bool, str, float]] = None


async def _aredis():
    from app.core.redis_pool import get_async_redis
    return await get_async_redis()


async def get_maintenance() -> tuple[bool, str]:
    """Return (enabled, message). A Redis override wins; otherwise fall back to env settings.
    Cached in-process for MAINT_CACHE_TTL to keep the request hot-path cheap."""
    global _maint_cache
    now = time.monotonic()
    if _maint_cache is not None and (now - _maint_cache[2]) < MAINT_CACHE_TTL:
        return _maint_cache[0], _maint_cache[1]

    from app.core.config import settings
    enabled = settings.MAINTENANCE_MODE
    message = settings.MAINTENANCE_MESSAGE
    try:
        r = await _aredis()
        raw = await r.get(_K_MAINT)
        if raw is not None:
            enabled = raw == "1"
        msg = await r.get(_K_MAINT_MSG)
        if msg:
            message = msg
    except Exception as e:
        logger.warning(f"[admin_state] maintenance read fell back to env (Redis error): {e}")

    _maint_cache = (enabled, message, now)
    return enabled, message


async def set_maintenance(enabled: bool, message: Optional[str] = None) -> None:
    """Persist maintenance state to Redis. Only overwrites the message when one is given."""
    global _maint_cache
    r = await _aredis()
    await r.set(_K_MAINT, "1" if enabled else "0")
    if message:
        await r.set(_K_MAINT_MSG, message)
    _maint_cache = None  # invalidate so THIS worker reflects the change on the next read


async def get_announcement() -> Optional[str]:
    try:
        r = await _aredis()
        val = await r.get(_K_ANNOUNCE)
        return val or None
    except Exception as e:
        logger.warning(f"[admin_state] announcement read failed (Redis error): {e}")
        return None


async def set_announcement(message: Optional[str]) -> None:
    """Set the announcement banner, or clear it when message is falsy."""
    r = await _aredis()
    if message:
        await r.set(_K_ANNOUNCE, message)
    else:
        await r.delete(_K_ANNOUNCE)
