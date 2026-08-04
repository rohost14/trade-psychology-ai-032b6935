"""
Last-traded-price cache — one Redis hash, one command per tick batch.

WHY THIS EXISTS. The ticker used to write one `SET ltp:{token}` per instrument per
tick, inside a pipeline. Pipelining saves round-trips, NOT commands — and Upstash
bills per command. At ~2,500 watched instruments ticking once a second across a
~470,000-second trading month, that is roughly 1.2 BILLION Redis commands a month
purely to cache prices. Zerodha already delivers ticks in batches; the old code
unpacked each batch and issued one command per instrument inside it.

Writing the whole batch into a single hash makes that one command instead of N —
about a 1000× reduction for identical data and identical latency.

STALENESS. The old design leaned on a 2-second per-key TTL: an instrument that
stopped ticking simply vanished from the cache, and callers correctly treated it as
"no live price". A hash cannot expire individual fields, so the timestamp is stored
alongside the price and freshness is checked on read. Same semantics, one command.

Without that, an illiquid option that stopped trading would keep serving its last
price forever, and every P&L and alert built on it would silently drift.
"""

import logging
import time
from typing import Dict, Optional

logger = logging.getLogger(__name__)

LTP_HASH = "ltp:all"

# Matches the old per-key TTL: a price older than this is "no live price".
STALE_MS = 2_000

# Garbage collection only — freshness is decided by the embedded timestamp, not by
# this. Long enough to survive a quiet spell, short enough that the hash cannot grow
# forever across expiries and instrument rollovers.
HASH_TTL_SECONDS = 300


def _encode(price: float, now_ms: int) -> str:
    return f"{price}:{now_ms}"


def _decode(raw: Optional[str], now_ms: int) -> Optional[float]:
    if not raw:
        return None
    try:
        price_s, ts_s = raw.rsplit(":", 1)
        if now_ms - int(ts_s) > STALE_MS:
            return None
        return float(price_s)
    except (ValueError, AttributeError):
        return None


def write_batch(redis_client, prices: Dict[int, float]) -> None:
    """
    Write a whole tick batch as ONE hash write. Never raises — a dropped price
    cache entry is replaced by the next tick; an exception would kill the ticker.
    """
    if not prices:
        return
    try:
        now_ms = int(time.time() * 1000)
        mapping = {str(token): _encode(price, now_ms) for token, price in prices.items()}
        pipe = redis_client.pipeline(transaction=False)
        pipe.hset(LTP_HASH, mapping=mapping)
        pipe.expire(LTP_HASH, HASH_TTL_SECONDS)
        pipe.execute()
    except Exception as e:
        logger.debug(f"[ltp_cache] batch write failed ({len(prices)} instruments): {e}")


def read(redis_client, instrument_token: int) -> Optional[float]:
    """Last price for one instrument, or None if missing or stale."""
    try:
        raw = redis_client.hget(LTP_HASH, str(instrument_token))
        return _decode(raw, int(time.time() * 1000))
    except Exception:
        return None
