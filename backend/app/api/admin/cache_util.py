"""Tiny best-effort Redis cache for expensive admin AGGREGATE endpoints.

Admin dashboards (overview, insights) run many heavy cross-table aggregates. They
tolerate a few seconds of staleness, and several admins hammering refresh should not
re-run the same full-table scans against the prod DB. Cache the whole JSON response for
a short TTL. Redis down → transparently falls back to computing live (never blocks).
"""
import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


async def _redis():
    from app.core.redis_pool import get_async_redis
    return await get_async_redis()


async def cache_get(key: str) -> Optional[Any]:
    try:
        raw = await (await _redis()).get(key)
        return json.loads(raw) if raw else None
    except Exception as e:
        logger.debug(f"[admin cache] get miss/err {key}: {e}")
        return None


async def cache_set(key: str, value: Any, ttl: int) -> None:
    try:
        await (await _redis()).setex(key, ttl, json.dumps(value, default=str))
    except Exception as e:
        logger.debug(f"[admin cache] set err {key}: {e}")
