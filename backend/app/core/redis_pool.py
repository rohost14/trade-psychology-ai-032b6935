"""
Shared Redis connection pools — module-level singletons.

All code that needs Redis should get a client from here instead of calling
redis.from_url() or aioredis.from_url() directly. That pattern creates a new
ConnectionPool per call, exhausting Upstash's max-connection limit under load.

Usage (sync, from Celery tasks):
    from app.core.redis_pool import get_sync_redis
    r = get_sync_redis()
    r.set("key", "val")

Usage (async, from FastAPI handlers and services):
    from app.core.redis_pool import get_async_redis
    r = await get_async_redis()
    await r.get("key")
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ── Sync pool (Celery workers) ─────────────────────────────────────────────────
# One pool per process (Celery prefork). max_connections=20 means up to 20
# concurrent borrows before the pool blocks. With worker_concurrency=4 and
# 4 pools → 80 potential sync connections. Upstash Pro supports 1000.
_sync_pool = None


def get_sync_redis():
    """Return a sync Redis client from the shared pool. Thread-safe (redis-py pool is)."""
    global _sync_pool
    if _sync_pool is None:
        import redis as redis_lib
        from app.core.config import settings
        _sync_pool = redis_lib.ConnectionPool.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            max_connections=20,
        )
        logger.debug("[redis_pool] sync pool initialized")
    import redis as redis_lib
    return redis_lib.Redis(connection_pool=_sync_pool)


# ── Async pool (FastAPI process) ──────────────────────────────────────────────
# One pool for the entire FastAPI process. max_connections=50 handles
# concurrent WebSocket replays, VIX fetches, analytics requests.
# Created once on first use; never closed (lives for process lifetime).
_async_pool = None


async def get_async_redis():
    """Return an async Redis client from the shared async pool."""
    global _async_pool
    if _async_pool is None:
        import redis.asyncio as aioredis
        from app.core.config import settings
        _async_pool = aioredis.ConnectionPool.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            max_connections=50,
        )
        logger.debug("[redis_pool] async pool initialized")
    import redis.asyncio as aioredis
    return aioredis.Redis(connection_pool=_async_pool)


def get_sync_redis_optional() -> Optional[object]:
    """Return sync Redis client, or None if Redis is unavailable. Never raises."""
    try:
        return get_sync_redis()
    except Exception as e:
        logger.warning(f"[redis_pool] sync Redis unavailable: {e}")
        return None
