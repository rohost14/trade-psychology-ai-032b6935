"""
India VIX fetcher from NSE public API.

NSE's allIndices endpoint is public and unauthenticated but:
- Rate-limits scrapers aggressively
- Changes structure periodically
- Requires browser-like headers

Cache policy: 15-minute Redis TTL.  If fetch fails 3× consecutive,
set a back-off flag for 1 hour and stop requesting — the VIX strip
simply disappears from the UI, no error shown.
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Regime thresholds (established in Indian options literature)
VIX_LOW_THRESHOLD    = 13.0
VIX_HIGH_THRESHOLD   = 18.0

CACHE_KEY        = "india_vix:value"
FAIL_COUNT_KEY   = "india_vix:fail_count"
BACKOFF_KEY      = "india_vix:backoff"
CACHE_TTL        = 900    # 15 min
BACKOFF_TTL      = 3600   # 1 hour after 3 consecutive failures


async def get_india_vix() -> Optional[float]:
    """
    Return current India VIX value or None if unavailable.
    Caches in Redis. Silently returns None on any failure.
    """
    try:
        import redis.asyncio as aioredis
        from app.core.config import settings

        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)

        # Back-off guard
        if await r.exists(BACKOFF_KEY):
            await r.aclose()
            return None

        # Cache hit
        cached = await r.get(CACHE_KEY)
        if cached:
            await r.aclose()
            return float(cached)

        # Fetch from NSE
        vix = await _fetch_vix_from_nse()

        if vix is not None:
            await r.set(CACHE_KEY, str(vix), ex=CACHE_TTL)
            await r.delete(FAIL_COUNT_KEY)
        else:
            fail_count = await r.incr(FAIL_COUNT_KEY)
            if int(fail_count) >= 3:
                await r.set(BACKOFF_KEY, "1", ex=BACKOFF_TTL)
                await r.delete(FAIL_COUNT_KEY)
                logger.warning("India VIX: 3 consecutive failures — backing off for 1h")

        await r.aclose()
        return vix

    except Exception as e:
        logger.warning(f"India VIX cache layer failed: {e}")
        # Attempt direct fetch without caching
        try:
            return await _fetch_vix_from_nse()
        except Exception:
            return None


async def _fetch_vix_from_nse() -> Optional[float]:
    """Direct HTTP fetch from NSE. Returns None on any error."""
    try:
        import httpx

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.nseindia.com/",
            "Origin": "https://www.nseindia.com",
        }

        async with httpx.AsyncClient(
            headers=headers,
            timeout=8.0,
            follow_redirects=True,
        ) as client:
            # First hit NSE homepage to get session cookies
            await client.get("https://www.nseindia.com/", timeout=5.0)
            resp = await client.get(
                "https://www.nseindia.com/api/allIndices",
                timeout=8.0,
            )

        if resp.status_code != 200:
            logger.warning(f"NSE allIndices returned {resp.status_code}")
            return None

        data = resp.json()
        for index in data.get("data", []):
            if index.get("index") == "INDIA VIX":
                return float(index["last"])

        logger.warning("INDIA VIX not found in NSE allIndices response")
        return None

    except Exception as e:
        logger.warning(f"NSE VIX fetch failed: {e}")
        return None


def classify_vix_regime(vix: float) -> str:
    """Classify VIX into low / normal / high regime."""
    if vix < VIX_LOW_THRESHOLD:
        return "low"
    if vix < VIX_HIGH_THRESHOLD:
        return "normal"
    return "high"


def regime_label(regime: str) -> str:
    return {
        "low":    "Low volatility",
        "normal": "Normal volatility",
        "high":   "High volatility",
    }.get(regime, "Unknown")


def regime_color(regime: str) -> str:
    """Return a tailwind-compatible color identifier for the UI."""
    return {
        "low":    "profit",   # green
        "normal": "obs",      # amber
        "high":   "loss",     # red
    }.get(regime, "muted")
