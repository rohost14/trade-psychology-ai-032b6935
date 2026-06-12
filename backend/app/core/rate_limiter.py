"""
Redis-backed sliding-window rate limiter for expensive and unauthenticated endpoints.

Replaces the previous in-memory defaultdict implementation that was not shared across
gunicorn/uvicorn workers (effective limit was N× the configured value with N workers).
Fails open on Redis unavailability — never blocks users due to infrastructure issues.

Usage:
    from app.core.rate_limiter import RateLimiter

    sync_limiter = RateLimiter(max_requests=3, window_seconds=60)

    @router.post("/sync/all")
    async def sync_all(
        _rate_limit=Depends(sync_limiter),
        ...
    ):
"""

import time
import logging

from fastapi import HTTPException, Request, Depends

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Redis sliding-window rate limiter implemented as a FastAPI dependency.

    Args:
        max_requests: Maximum requests allowed within the window.
        window_seconds: Time window in seconds.
        key_func: Optional callable to extract the rate-limit key from request.
                  Defaults to broker_account_id (if authed) or client IP.
    """

    def __init__(self, max_requests: int, window_seconds: int, key_func=None):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.key_func = key_func

    def _default_key(self, request: Request) -> str:
        """
        Extract rate-limit key from request.
        Prefers broker_account_id from request.state (set by auth middleware)
        so limits are per-account, not per-IP. Falls back to IP if not authed.
        """
        account_id = getattr(request.state, "broker_account_id", None)
        if account_id:
            return str(account_id)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def __call__(self, request: Request):
        key = self.key_func(request) if self.key_func else self._default_key(request)
        redis_key = f"rl:{key}:{request.url.path}"
        now = time.time()
        window_start = now - self.window_seconds

        try:
            from app.core.redis_pool import get_sync_redis
            r = get_sync_redis()
            pipe = r.pipeline()
            pipe.zremrangebyscore(redis_key, "-inf", window_start)
            pipe.zcard(redis_key)
            # Use high-precision timestamp as member to avoid collisions under burst traffic
            pipe.zadd(redis_key, {f"{now:.9f}": now})
            pipe.expire(redis_key, self.window_seconds + 1)
            results = pipe.execute()
            r.close()

            call_count = results[1]
            if call_count >= self.max_requests:
                retry_after = self.window_seconds
                logger.warning(
                    f"Rate limit exceeded for {key} on {request.url.path} "
                    f"({call_count}/{self.max_requests} in {self.window_seconds}s)"
                )
                raise HTTPException(
                    status_code=429,
                    detail=f"Too many requests. Try again in {retry_after}s.",
                    headers={"Retry-After": str(retry_after)},
                )
        except HTTPException:
            raise
        except Exception as exc:
            # Redis unavailable — fail open (don't block users for infra issues)
            logger.warning(f"Rate limit check skipped (Redis error): {exc}")


# Pre-configured limiters for expensive endpoints
sync_limiter      = RateLimiter(max_requests=10, window_seconds=60)   # 10 syncs/min (tab-switch + page loads)
coach_limiter     = RateLimiter(max_requests=10, window_seconds=60)   # 10 chat msgs/min
analytics_limiter = RateLimiter(max_requests=20, window_seconds=60)   # 20 analytics/min
general_limiter   = RateLimiter(max_requests=20, window_seconds=60)   # unauthenticated public endpoints

# Admin auth — strict brute-force protection
admin_login_limiter = RateLimiter(max_requests=5, window_seconds=900)  # 5 attempts/15 min per IP
admin_otp_limiter   = RateLimiter(max_requests=5, window_seconds=300)  # 5 OTP guesses/5 min per IP
