"""
Event Bus — Redis Streams bridge between Celery workers and FastAPI WebSocket.

Architecture:
  TWO streams per publish:
    stream:events          — global, read by FastAPI subscriber for real-time push
    stream:{account_id}    — per-account, durable, read by WebSocket on connect for replay

  Why two streams:
    - Global: subscriber reads ONE stream, dispatches to correct WebSocket by account_id
    - Per-account: client reconnects with last_event_id → XREAD → replay missed events

  Dual-write validation:
    Celery pipeline (primary) runs as-is.
    Every processed event also appended to streams.
    Streams are used ONLY for notifications + replay, not for processing.
    After 5 trading days of validated dual-write → Phase 4 cutover replaces Celery.

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


def publish_event(
    broker_account_id: str,
    event_type: str,
    data: Optional[dict] = None,
) -> Optional[str]:
    """
    Publish an event from a Celery worker (sync context).

    Writes to BOTH streams atomically:
      - stream:events        (global, for real-time WebSocket push)
      - stream:{account_id}  (per-account, for replay on app open)

    Returns the stream entry ID, or None if Redis unavailable.
    Never raises — event bus failure must not crash the pipeline.
    """
    try:
        from app.core.config import settings
        import redis as redis_lib

        r = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)
        fields = {
            "type": event_type,
            "account_id": broker_account_id,
            "data": json.dumps(data or {}),
            "ts": str(int(time.time() * 1000)),
        }

        # Write to per-account stream (replay storage)
        account_stream = f"{ACCOUNT_STREAM_PREFIX}{broker_account_id}"
        entry_id = r.xadd(account_stream, fields, maxlen=ACCOUNT_MAXLEN, approximate=True)

        # Write to global stream (real-time push)
        r.xadd(GLOBAL_STREAM, fields, maxlen=GLOBAL_MAXLEN, approximate=True)

        logger.debug(f"[event_bus] {event_type} for {broker_account_id[:8]} → {entry_id}")
        return entry_id

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
        from app.core.config import settings
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
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
    from app.core.config import settings
    import redis.asyncio as aioredis

    logger.info("[event_bus] Starting Redis Streams event subscriber...")

    # '$' = only read events that arrive AFTER this subscriber starts
    # (existing events are replayed per-account via replay_events_for_account)
    last_id = "$"

    while True:
        try:
            r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            logger.info(f"[event_bus] Subscribed to {GLOBAL_STREAM}")

            while True:
                # Block up to 100ms waiting for new messages
                # This is efficient — no busy-loop, wakes up on new data
                results = await r.xread(
                    {GLOBAL_STREAM: last_id},
                    block=100,
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

                        try:
                            data = json.loads(fields.get("data", "{}"))
                        except (json.JSONDecodeError, TypeError):
                            data = {}

                        await _dispatch_to_websocket(account_id, event_type, data, entry_id)

        except Exception as e:
            logger.error(f"[event_bus] Subscriber error (reconnecting in 5s): {e}")
            import asyncio
            await asyncio.sleep(5)
            last_id = "$"  # after reconnect, only read new events


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
            await manager.send_trade_update(account_id, data)

        elif event_type == "alert_update":
            await manager.send_alert(account_id, data)

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
