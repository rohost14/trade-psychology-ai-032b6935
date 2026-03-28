"""
Per-account API rate limiting via Redis sliding window.

Usage:
    from app.core.rate_limit import rate_limit

    @router.post("/expensive-endpoint")
    async def handler(
        account_id: UUID = Depends(get_verified_broker_account_id),
        _: None = Depends(rate_limit(max_calls=5, window_seconds=60)),
    ):
        ...

Returns HTTP 429 with a Retry-After header when the limit is exceeded.
Fails open (allows the request) if Redis is unavailable — never blocks users
due to infrastructure issues.
"""

import time
import logging
from typing import Callable
from uuid import UUID

from fastapi import Depends, HTTPException, Request
from starlette.status import HTTP_429_TOO_MANY_REQUESTS

from app.api.deps import get_verified_broker_account_id

logger = logging.getLogger(__name__)


def rate_limit(max_calls: int = 10, window_seconds: int = 60) -> Callable:
    """
    FastAPI dependency factory for per-account sliding-window rate limiting.

    Args:
        max_calls: Maximum number of requests allowed per window.
        window_seconds: Length of the sliding window in seconds.

    The Redis key is scoped to (account_id, endpoint path) so different
    endpoints have independent limits.
    """

    async def _check_rate_limit(
        request: Request,
        account_id: UUID = Depends(get_verified_broker_account_id),
    ) -> None:
        try:
            import redis as redis_lib
            from app.core.config import settings

            r = redis_lib.from_url(settings.REDIS_URL, socket_connect_timeout=1)
            key = f"rl:{account_id}:{request.url.path}"
            now = time.time()
            window_start = now - window_seconds

            pipe = r.pipeline()
            # Remove entries outside the window
            pipe.zremrangebyscore(key, "-inf", window_start)
            # Count remaining entries
            pipe.zcard(key)
            # Add this request
            pipe.zadd(key, {str(now): now})
            # Set TTL so key self-cleans
            pipe.expire(key, window_seconds + 1)
            results = pipe.execute()
            r.close()

            call_count = results[1]
            if call_count >= max_calls:
                raise HTTPException(
                    status_code=HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded: {max_calls} requests per {window_seconds}s",
                    headers={"Retry-After": str(window_seconds)},
                )
        except HTTPException:
            raise
        except Exception as exc:
            # Redis unavailable — fail open (don't block users for infra issues)
            logger.warning(f"Rate limit check skipped (Redis error): {exc}")

    return _check_rate_limit
