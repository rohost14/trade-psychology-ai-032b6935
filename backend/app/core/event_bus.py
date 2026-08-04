"""
Event Bus — Redis Streams bridge between Celery workers and FastAPI WebSocket.

Architecture:
  TWO streams per publish:
    stream:events          — global, read by FastAPI subscriber for real-time push
    stream:{account_id}    — per-account, durable, read by WebSocket on connect for replay

  Why two streams:
    - Global: subscriber reads ONE stream, dispatches to correct WebSocket by account_id
    - Per-account: client reconnects with last_event_id → XREAD → replay missed events

  Design:
    Celery pipeline = primary (processes trades, saves to DB, runs BehaviorEngine).
    Redis Streams = notifications + replay only. Never used for processing.
    Celery fails → stream not written (correct — don't record failed events).
    Redis fails → Celery still processes (publish_event is fail-silent).

  Multi-instance scaling (when using multiple backend processes):
    Each FastAPI instance runs its own start_event_subscriber() reading the same global
    stream, and dispatches to whichever clients it happens to hold locally. Because
    EVERY instance sees EVERY event, a client connected to any instance gets its own
    events. Sticky sessions are therefore NOT required for correctness here — an
    earlier version of this note claimed they were, which was wrong and made the
    deployment look more fragile than it is. They are still worth having so a
    reconnecting client resumes replay against the same cursor.

    The cost of that fan-out is that every instance reads every event (N× read
    amplification), which is the thing consumer groups would fix — see below.

    NOT covered by this: the KiteTicker in price_stream_service, whose subscription
    state is per-process in-memory. Two instances means two tickers and duplicate
    ticks. That is a genuine split brain and needs an owner lease, not this bus.

  At 50+ users:
    Replace per-call sync connection with ConnectionPool (already done — see _get_sync_redis).
    Add XREADGROUP consumer groups for guaranteed delivery (XACK + dead letter handling).

  Stream limits (MAXLEN with ~ = approximate trimming):
    stream:events:       MAXLEN ~50000  (global, all accounts)
    stream:{account_id}: MAXLEN ~500    (per account, last ~500 events)

Event schema (Redis Hash fields):
  type:       'trade_update' | 'alert_update' | 'position_update' | 'margin_update'
  account_id: broker_account_id as string
  data:       JSON string of event payload
  ts:         unix ms timestamp as string

Usage (from Celery tasks — sync context):
    from app.core.event_bus import publish_event
    publish_event(str(broker_account_id), "trade_update", {"order_id": "..."})

Usage (FastAPI startup):
    from app.core.event_bus import start_event_subscriber
    asyncio.create_task(start_event_subscriber())

Usage (WebSocket endpoint — replay on connect):
    from app.core.event_bus import replay_events_for_account
    events = await replay_events_for_account(account_id, since_event_id, limit=200)
"""

import json
import logging
import time
from typing import Optional, List, Tuple

logger = logging.getLogger(__name__)

GLOBAL_STREAM = "stream:events"
ACCOUNT_STREAM_PREFIX = "stream:"
GLOBAL_MAXLEN = 50000
ACCOUNT_MAXLEN = 500


def _get_sync_redis():
    """Return a Redis client from the shared sync pool (redis_pool module)."""
    from app.core.redis_pool import get_sync_redis
    return get_sync_redis()


async def _get_async_redis():
    """Return an async Redis client from the shared async pool (redis_pool module)."""
    from app.core.redis_pool import get_async_redis
    return await get_async_redis()


# Internal server-side event types: consumed by the FastAPI event subscriber to
# perform a server action (NOT forwarded to the browser). These are published with
# replay=False so they never pollute the per-account replay stream.
INTERNAL_EVENT_TYPES = {"subscription_refresh"}


def publish_event(
    broker_account_id: str,
    event_type: str,
    data: Optional[dict] = None,
    replay: bool = True,
) -> Optional[str]:
    """
    Publish an event from a Celery worker (sync context).

    Writes to the global stream (real-time push) and, when replay=True, also to the
    per-account stream (durable replay on app open).

    replay=False is used for INTERNAL server-side events (e.g. subscription_refresh)
    that trigger a FastAPI-process action but must never be replayed to a browser.

    Returns the stream entry ID, or None if Redis unavailable.
    Never raises — event bus failure must not crash the pipeline.
    Uses a shared connection pool — no new TCP connection per call.
    """
    try:
        r = _get_sync_redis()
        fields = {
            "type": event_type,
            "account_id": broker_account_id,
            "data": json.dumps(data or {}),
            "ts": str(int(time.time() * 1000)),
        }

        entry_id = None
        # Write to per-account stream (replay storage) unless this is internal-only
        if replay:
            account_stream = f"{ACCOUNT_STREAM_PREFIX}{broker_account_id}"
            entry_id = r.xadd(account_stream, fields, maxlen=ACCOUNT_MAXLEN, approximate=True)

        # Write to global stream (real-time push / server-side dispatch)
        global_id = r.xadd(GLOBAL_STREAM, fields, maxlen=GLOBAL_MAXLEN, approximate=True)

        logger.debug(f"[event_bus] {event_type} for {broker_account_id[:8]} → {entry_id or global_id}")
        return entry_id or global_id

    except Exception as e:
        logger.warning(f"[event_bus] publish_event failed (non-fatal): {e}")
        return None


async def replay_events_for_account(
    broker_account_id: str,
    since_event_id: str,
    limit: int = 200,
) -> List[Tuple[str, dict]]:
    """
    Fetch all events for an account since a given event ID.
    Called by the WebSocket endpoint when a client reconnects with ?since=...

    Returns list of (event_id, fields_dict) tuples, ordered oldest→newest.
    Returns empty list if no events or Redis unavailable.

    since_event_id = '0-0' means return up to `limit` most recent events.
    """
    try:
        r = await _get_async_redis()
        account_stream = f"{ACCOUNT_STREAM_PREFIX}{broker_account_id}"

        # XREAD is exclusive of since_event_id — returns only events AFTER it
        results = await r.xread(
            {account_stream: since_event_id},
            count=limit,
        )

        if not results:
            return []

        events = []
        for _stream_name, messages in results:
            for entry_id, fields in messages:
                events.append((entry_id, fields))

        return events

    except Exception as e:
        logger.warning(f"[event_bus] replay_events failed: {e}")
        return []


async def start_event_subscriber() -> None:
    """
    Long-running async task — reads from global stream and forwards
    new events to the correct WebSocket client.

    Replaces the Redis pub/sub pattern. Key advantages over pub/sub:
    - Durable: events stored even if no subscriber
    - Replay: new workers can catch up from last processed ID
    - No message loss on subscriber restart

    Uses XREAD BLOCK to wait efficiently for new messages.
    Reconnects automatically on Redis error.
    """
    logger.info("[event_bus] Starting Redis Streams event subscriber...")

    # '$' = only read events that arrive AFTER this subscriber starts
    # (existing events are replayed per-account via replay_events_for_account)
    last_id = "$"

    while True:
        try:
            r = await _get_async_redis()
            logger.info(f"[event_bus] Subscribed to {GLOBAL_STREAM}")

            while True:
                # Skip XREAD when no WebSocket clients are connected — avoids burning
                # Upstash free-tier commands (block=100 was 10 XREAD/s = 26M cmds/month).
                # On reconnect the client sends ?since=<last_event_id> and gets replay.
                try:
                    from app.api.websocket import manager
                    has_clients = bool(manager.active_connections)
                except Exception:
                    has_clients = True  # unknown — proceed normally

                if not has_clients:
                    import asyncio as _asyncio
                    await _asyncio.sleep(5)
                    continue

                # Block up to 2s waiting for new messages (was 100ms).
                # 0.5 XREAD/s vs 10/s — reduces idle command count 20×.
                results = await r.xread(
                    {GLOBAL_STREAM: last_id},
                    block=2000,
                    count=20,
                )

                if not results:
                    continue

                for _stream_name, messages in results:
                    for entry_id, fields in messages:
                        last_id = entry_id  # advance cursor

                        account_id = fields.get("account_id")
                        event_type = fields.get("type")
                        if not account_id or not event_type:
                            continue

                        # Internal server-side events act on the FastAPI process itself
                        # (e.g. refresh the shared ticker's subscriptions) and are NOT
                        # forwarded to any browser WebSocket.
                        if event_type in INTERNAL_EVENT_TYPES:
                            await _handle_internal_event(account_id, event_type)
                            continue

                        try:
                            data = json.loads(fields.get("data", "{}"))
                        except (json.JSONDecodeError, TypeError):
                            data = {}

                        await _dispatch_to_websocket(account_id, event_type, data, entry_id)

        except Exception as e:
            logger.error(f"[event_bus] Subscriber error (reconnecting in 5s): {e}")
            import asyncio
            await asyncio.sleep(5)
            # Do NOT reset last_id to "$" here — keep the cursor at the last
            # successfully-processed entry so events that arrived during the
            # disconnect window are replayed. If Redis trimmed that ID from the
            # stream, XREAD will start from the oldest available entry (safe).
            # Only the initial startup uses "$" (line above the outer while loop).


async def _handle_internal_event(account_id: str, event_type: str) -> None:
    """
    Execute a server-side action requested by a Celery worker.

    Celery workers run in separate processes and cannot reach the FastAPI process's
    in-memory SharedPriceStream ticker. When a worker opens a new position it publishes
    a `subscription_refresh` internal event; the FastAPI event subscriber (this process,
    which owns the live ticker + browser WebSockets) handles it here by refreshing the
    ticker's instrument subscriptions locally.
    """
    if event_type == "subscription_refresh":
        try:
            from uuid import UUID
            from app.services.price_stream_service import price_stream
            from app.core.database import SessionLocal
            async with SessionLocal() as db:
                await price_stream.refresh_subscriptions(UUID(account_id), db)
            logger.info(f"[event_bus] Refreshed price subscriptions for {account_id[:8]}")
        except Exception as e:
            logger.warning(f"[event_bus] subscription_refresh failed for {account_id[:8]}: {e}")


async def _dispatch_to_websocket(
    account_id: str,
    event_type: str,
    data: dict,
    event_id: str,
) -> None:
    """Forward a stream event to the connected WebSocket client for this account."""
    try:
        from app.api.websocket import manager

        message = {
            "type": event_type,
            "event_id": event_id,
            "data": data,
        }

        if event_type in ("trade_update", "position_update"):
            await manager.send_trade_update(account_id, data, event_id=event_id)

        elif event_type == "alert_update":
            await manager.send_alert(account_id, data, event_id=event_id)

        elif event_type == "margin_update":
            await manager.send_to_account(account_id, {
                "type": "margin_update",
                "event_id": event_id,
                "data": data,
            })

        else:
            await manager.send_to_account(account_id, message)

    except Exception as e:
        logger.debug(f"[event_bus] dispatch failed for {account_id[:8]}: {e}")
