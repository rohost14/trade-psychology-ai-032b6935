"""
Single-owner lease for the shared KiteTicker.

The problem it solves: SharedPriceStream keeps its ticker and its subscription
bookkeeping in PROCESS memory. Run two FastAPI instances and you get two
KiteTicker connections to Zerodha, two subscription sets, duplicate ticks, and a
`subscription_refresh` event that lands on whichever instance happened to read it
— so instance A can be told to refresh a position that lives on instance B. That
is a genuine split brain, and it is the one thing the Redis Streams event bus does
NOT already handle (see event_bus.py: alerts fan out to every instance, so those
are fine).

The fix is ordinary leader election, using the same SETNX+TTL pattern already used
for the FIFO and behaviour locks:

  - Exactly one instance holds `price_stream:owner` and is the only one that opens
    a KiteTicker. It renews the lease on a timer.
  - If the owner dies, the lease simply expires and another instance takes it on
    its next attempt. Worst-case feed gap is one LEASE_TTL.
  - The owner subscribes to the union of open-position instruments across ALL
    accounts (read from the database), not just the accounts whose WebSockets
    happen to be connected to it.
  - Ticks are published to a Redis pub/sub channel; every instance forwards them
    to its own local WebSocket clients.

Pub/sub, not a stream, is deliberate for ticks: a three-second-old price is
worthless, so there is nothing to replay and nothing worth storing. Alerts are the
opposite — a missed alert matters forever — which is why those stay on Streams.

DORMANT BY DEFAULT. With PRICE_STREAM_MULTI_INSTANCE off (the default) none of
this runs and behaviour is exactly as before: one process, one ticker, in-process
fan-out, no extra Redis traffic. Turn it on only when actually running more than
one backend instance — on a per-command Redis plan, tick fan-out at scale is
billions of commands a month, and it buys nothing on a single instance.
"""

import asyncio
import logging
import os
import socket
import uuid

logger = logging.getLogger(__name__)

LEASE_KEY = "price_stream:owner"
LEASE_TTL = 30           # seconds — how long a dead owner blocks a takeover
RENEW_INTERVAL = 10      # seconds — must be comfortably under LEASE_TTL

TICK_CHANNEL = "ticks"

# Stable within a process, unique across them. Host+pid makes it readable in logs;
# the uuid suffix keeps it unique if a pid is recycled inside a container.
INSTANCE_ID = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"

# Renew only if we still hold it. Without the owner check, a process that stalled
# past its TTL would happily overwrite the new owner's lease and you would be back
# to two tickers — the exact failure this module exists to prevent.
_RENEW_LUA = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('EXPIRE', KEYS[1], ARGV[2])
end
return 0
"""

_is_owner = False
_renew_task = None


def is_owner() -> bool:
    """Whether THIS process currently believes it holds the ticker lease."""
    return _is_owner


async def try_acquire() -> bool:
    """
    Claim the lease if it is free, or confirm we already hold it.

    Never raises: if Redis is unreachable we report False, which means this
    instance simply does not run a ticker. Failing closed is right — the wrong
    answer here is two tickers, not zero.
    """
    global _is_owner
    try:
        from app.core.redis_pool import get_async_redis
        r = await get_async_redis()

        acquired = await r.set(LEASE_KEY, INSTANCE_ID, nx=True, ex=LEASE_TTL)
        if acquired:
            if not _is_owner:
                logger.info(f"[ticker_lease] Acquired ticker ownership ({INSTANCE_ID})")
            _is_owner = True
            return True

        holder = await r.get(LEASE_KEY)
        _is_owner = (holder == INSTANCE_ID)
        return _is_owner

    except Exception as e:
        logger.warning(f"[ticker_lease] acquire failed, not taking ownership: {e}")
        _is_owner = False
        return False


async def renew() -> bool:
    """Extend the lease, but only while we are still the recorded owner."""
    global _is_owner
    if not _is_owner:
        return False
    try:
        from app.core.redis_pool import get_async_redis
        r = await get_async_redis()
        ok = await r.eval(_RENEW_LUA, 1, LEASE_KEY, INSTANCE_ID, LEASE_TTL)
        if not ok:
            # Someone else owns it now — most likely we stalled past the TTL.
            logger.warning("[ticker_lease] Lost ticker ownership (lease taken over)")
            _is_owner = False
        return bool(ok)
    except Exception as e:
        logger.warning(f"[ticker_lease] renew failed: {e}")
        return False


async def release() -> None:
    """Give up the lease on clean shutdown so failover is immediate, not TTL-bound."""
    global _is_owner
    if not _is_owner:
        return
    try:
        from app.core.redis_pool import get_async_redis
        r = await get_async_redis()
        # Delete only if still ours.
        await r.eval(
            "if redis.call('GET', KEYS[1]) == ARGV[1] then return redis.call('DEL', KEYS[1]) end return 0",
            1, LEASE_KEY, INSTANCE_ID,
        )
        logger.info("[ticker_lease] Released ticker ownership")
    except Exception as e:
        logger.warning(f"[ticker_lease] release failed (lease will expire): {e}")
    finally:
        _is_owner = False


async def run_tick_subscriber() -> None:
    """
    Forward ticks published by the lease owner to THIS instance's WebSocket clients.

    Every instance runs this, including the owner — the owner publishes rather than
    delivering locally so there is exactly one code path for a tick, instead of two
    that can drift apart.

    Reconnects on error. Never lets a bad payload kill the loop: a dropped tick is
    replaced by the next one a second later, but a dead subscriber is silent forever.
    """
    import json

    logger.info(f"[ticker_lease] Tick subscriber started ({INSTANCE_ID})")
    while True:
        try:
            from app.core.redis_pool import get_async_redis
            from app.services.price_stream_service import price_stream

            r = await get_async_redis()
            pubsub = r.pubsub(ignore_subscribe_messages=True)
            await pubsub.subscribe(TICK_CHANNEL)

            async for message in pubsub.listen():
                if not message or message.get("type") != "message":
                    continue
                try:
                    payload = json.loads(message["data"])
                    await price_stream.deliver_ltp_locally(
                        payload["symbol"],
                        payload.get("last_price"),
                        int(payload["instrument_token"]),
                    )
                except Exception as e:
                    logger.debug(f"[ticker_lease] bad tick payload: {e}")

        except Exception as e:
            logger.error(f"[ticker_lease] tick subscriber error (retry in 5s): {e}")
            await asyncio.sleep(5)


async def run_lease_loop() -> None:
    """
    Background task: hold the lease if we have it, try to take it if we do not.

    Started at app startup only when PRICE_STREAM_MULTI_INSTANCE is on.
    """
    logger.info(f"[ticker_lease] Lease loop started ({INSTANCE_ID})")
    while True:
        try:
            if _is_owner:
                await renew()
            else:
                await try_acquire()
        except Exception as e:
            logger.error(f"[ticker_lease] loop error: {e}")
        await asyncio.sleep(RENEW_INTERVAL)
