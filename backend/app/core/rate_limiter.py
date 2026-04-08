"""
In-memory rate limiter for expensive endpoints.

Uses a sliding window counter per (client_key, endpoint) pair.
No external dependencies — backed by a simple dict with TTL cleanup.

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
import asyncio
from collections import defaultdict
from fastapi import HTTPException, Request, Depends
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Sliding-window rate limiter implemented as a FastAPI dependency.

    Args:
        max_requests: Maximum requests allowed within the window.
        window_seconds: Time window in seconds.
        key_func: Optional callable to extract the rate-limit key from request.
                  Defaults to client IP.
    """

    def __init__(self, max_requests: int, window_seconds: int, key_func=None):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.key_func = key_func
        # key -> list of timestamps
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

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
        if self.key_func:
            key = self.key_func(request)
        else:
            key = self._default_key(request)

        now = time.monotonic()
        window_start = now - self.window_seconds

        async with self._lock:
            # Prune expired entries
            hits = self._hits[key]
            self._hits[key] = [t for t in hits if t > window_start]
            hits = self._hits[key]

            if len(hits) >= self.max_requests:
                retry_after = int(hits[0] - window_start) + 1
                logger.warning(
                    f"Rate limit exceeded for {key} on {request.url.path} "
                    f"({len(hits)}/{self.max_requests} in {self.window_seconds}s)"
                )
                raise HTTPException(
                    status_code=429,
                    detail=f"Too many requests. Try again in {retry_after}s.",
                    headers={"Retry-After": str(retry_after)},
                )

            hits.append(now)


# Pre-configured limiters for expensive endpoints
sync_limiter = RateLimiter(max_requests=10, window_seconds=60)      # 10 syncs/min (tab-switch + page loads)
coach_limiter = RateLimiter(max_requests=10, window_seconds=60)     # 10 chat msgs/min
analytics_limiter = RateLimiter(max_requests=20, window_seconds=60) # 20 analytics/min

# Admin auth — strict brute-force protection
admin_login_limiter = RateLimiter(max_requests=5, window_seconds=900)  # 5 attempts/15 min per IP
admin_otp_limiter   = RateLimiter(max_requests=5, window_seconds=300)  # 5 OTP guesses/5 min per IP
