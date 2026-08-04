"""
Per-account response cache for expensive analytics aggregates.

api/analytics.py had ZERO caching: every Dashboard and Analytics load recomputed
multi-day Postgres aggregates from scratch — behaviour cost, edge stats, habits,
session log, the lot. Fine for one user. At scale it is N uncached aggregate
queries per page view, and the Analytics page fires several at once.

INVALIDATION IS THE HARD PART, and getting it wrong is worse than not caching. A
trader closes a position and immediately opens Analytics; showing them stale
numbers breaks the one thing the product promises. So this does not use a plain
TTL and hope.

Every key embeds a per-account VERSION:

    analytics:{account_id}:v{version}:{path}:{query}

`bump_account_version()` is called whenever a CompletedTrade is written. That makes
every previously cached key for that account unreachable in one INCR — no key
enumeration, no SCAN, no delete-by-pattern. Stale entries are never read again and
expire on their own TTL.

The TTL is therefore a backstop, not the invalidation mechanism. It only bounds
staleness for things that change WITHOUT a new completed trade.

Fail-open everywhere: Redis down means compute live, never error. A cache that can
break the page is not worth having.
"""

import hashlib
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_VERSION_PREFIX = "analytics_ver:"
_CACHE_PREFIX = "analytics:"
DEFAULT_TTL = 180  # seconds


def _version_key(account_id) -> str:
    return f"{_VERSION_PREFIX}{account_id}"


async def get_account_version(account_id) -> int:
    """Current cache generation for an account. Missing/unavailable → 1."""
    try:
        from app.core.redis_pool import get_async_redis
        r = await get_async_redis()
        raw = await r.get(_version_key(account_id))
        return int(raw) if raw else 1
    except Exception:
        return 1


def bump_account_version_sync(account_id) -> None:
    """
    Invalidate every cached analytics response for one account.

    Sync because the callers are Celery tasks. Best-effort: if this fails the worst
    case is a stale read for up to one TTL, which is why the TTL exists.
    """
    try:
        from app.core.redis_pool import get_sync_redis
        r = get_sync_redis()
        r.incr(_version_key(account_id))
        r.expire(_version_key(account_id), 86400 * 7)
    except Exception as e:
        logger.debug(f"[response_cache] version bump failed for {account_id}: {e}")


def make_key(account_id, version: int, name: str, params: dict) -> str:
    """
    Build a cache key. Params are hashed so a long query string cannot produce an
    unbounded key, and sorted so argument order never splits the cache.
    """
    blob = json.dumps(params, sort_keys=True, default=str)
    digest = hashlib.sha1(blob.encode()).hexdigest()[:16]
    return f"{_CACHE_PREFIX}{account_id}:v{version}:{name}:{digest}"


async def cache_get(key: str) -> Optional[dict]:
    try:
        from app.core.redis_pool import get_async_redis
        r = await get_async_redis()
        raw = await r.get(key)
        return json.loads(raw) if raw else None
    except Exception:
        return None


async def cache_set(key: str, value, ttl: int) -> None:
    try:
        from app.core.redis_pool import get_async_redis
        r = await get_async_redis()
        await r.setex(key, ttl, json.dumps(value, default=str))
    except Exception as e:
        logger.debug(f"[response_cache] set failed {key}: {e}")


def cached_analytics(ttl: int = DEFAULT_TTL):
    """
    Cache an analytics endpoint's JSON response per account.

    Usage — the router decorator stays OUTERMOST so FastAPI registers the wrapper
    and still sees the original signature for dependency injection:

        @router.get("/overview")
        @cached_analytics(ttl=180)
        async def get_overview(days: int = 30, broker_account_id: UUID = Depends(...)):

    Only endpoints that take `broker_account_id` are cacheable — without it there is
    no account to scope the key to, and a shared key would leak one trader's numbers
    to another. Such a handler is passed through uncached rather than guessed at.
    """
    import functools

    def decorator(fn):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            account_id = kwargs.get("broker_account_id")
            if account_id is None:
                # No account in scope — never risk a cross-account key.
                return await fn(*args, **kwargs)

            # Only the plain query params identify the result. db sessions, request
            # objects and other injected dependencies are not part of the identity
            # and are not JSON-serialisable anyway.
            params = {
                k: v for k, v in kwargs.items()
                if k != "broker_account_id" and isinstance(v, (str, int, float, bool, type(None)))
            }

            # Belt and braces. cache_get/cache_set/get_account_version each swallow
            # their own errors, but the endpoint must survive even if a future change
            # to one of them starts raising. A caching layer is never a good enough
            # reason to 500 a page that could have been computed.
            key = None
            try:
                version = await get_account_version(account_id)
                key = make_key(account_id, version, fn.__name__, params)
                hit = await cache_get(key)
                if hit is not None:
                    return hit
            except Exception as e:
                logger.debug(f"[response_cache] lookup failed for {fn.__name__}: {e}")

            result = await fn(*args, **kwargs)

            if key is not None:
                try:
                    await cache_set(key, result, ttl)
                except Exception as e:
                    logger.debug(f"[response_cache] store failed for {fn.__name__}: {e}")
            return result

        return wrapper

    return decorator
