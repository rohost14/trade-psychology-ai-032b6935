"""
Event Bus — Redis pub/sub bridge between Celery workers and FastAPI WebSocket.

Problem this solves:
  Celery workers process trades in a separate process from FastAPI.
  FastAPI holds WebSocket connections in-memory (ConnectionManager).
  Celery cannot directly call FastAPI's ConnectionManager.

Solution:
  Celery publishes events to Redis channel: events:{broker_account_id}
  FastAPI background task subscribes to Redis, forwards to WebSocket clients.

Event schema (JSON):
  {
    "type": "trade_update" | "alert_update" | "position_update",
    "broker_account_id": "uuid-string",
    "data": { ... }  -- optional payload
  }

Usage (from Celery tasks):
    from app.core.event_bus import publish_event
    publish_event(str(broker_account_id), "trade_update", {"trades_count": 5})

Usage (FastAPI startup):
    from app.core.event_bus import start_event_subscriber
    asyncio.create_task(start_event_subscriber())
"""

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Redis channel prefix — one channel per broker account
_CHANNEL_PREFIX = "events:"


def publish_event(
    broker_account_id: str,
    event_type: str,
    data: Optional[dict] = None,
) -> None:
    """
    Publish an event from a Celery worker (sync context).
    The FastAPI subscriber picks it up and forwards to the WebSocket.

    Fails silently — a Redis pub/sub failure must never crash the pipeline.
    """
    try:
        from app.core.config import settings
        import redis as redis_lib

        r = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)
        payload = json.dumps({
            "type": event_type,
            "broker_account_id": broker_account_id,
            "data": data or {},
        })
        channel = f"{_CHANNEL_PREFIX}{broker_account_id}"
        r.publish(channel, payload)
        logger.debug(f"[event_bus] Published {event_type} for {broker_account_id[:8]}")
    except Exception as e:
        # Never crash the caller — event bus is best-effort
        logger.warning(f"[event_bus] publish_event failed (non-fatal): {e}")


async def start_event_subscriber() -> None:
    """
    Long-running async task — subscribes to ALL account event channels
    and forwards incoming events to the FastAPI WebSocket manager.

    Run as an asyncio task from main.py lifespan.
    Uses pattern subscribe so one connection handles all accounts.

    Reconnects automatically on Redis disconnect.
    """
    from app.core.config import settings
    import redis.asyncio as aioredis

    logger.info("[event_bus] Starting Redis event subscriber...")

    while True:
        try:
            r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            pubsub = r.pubsub()

            # Subscribe to ALL account event channels with pattern
            await pubsub.psubscribe(f"{_CHANNEL_PREFIX}*")
            logger.info("[event_bus] Subscribed to Redis event channels.")

            async for message in pubsub.listen():
                if message["type"] not in ("pmessage", "message"):
                    continue

                try:
                    payload = json.loads(message["data"])
                    event_type = payload.get("type")
                    account_id = payload.get("broker_account_id")

                    if not account_id or not event_type:
                        continue

                    # Forward to WebSocket manager
                    await _dispatch_to_websocket(account_id, event_type, payload.get("data", {}))

                except Exception as e:
                    logger.warning(f"[event_bus] Failed to process message: {e}")

        except Exception as e:
            logger.error(f"[event_bus] Subscriber error (will reconnect in 5s): {e}")
            import asyncio
            await asyncio.sleep(5)  # reconnect backoff


async def _dispatch_to_websocket(
    account_id: str,
    event_type: str,
    data: dict,
) -> None:
    """
    Forward a received event to the WebSocket client for this account.
    The ConnectionManager sends to the specific connected browser tab.
    """
    try:
        from app.api.websocket import manager

        if event_type == "trade_update":
            await manager.send_trade_update(account_id, data)

        elif event_type == "alert_update":
            await manager.send_alert(account_id, data)

        elif event_type == "position_update":
            await manager.send_to_account(account_id, {
                "type": "position_update",
                "data": data,
            })

        else:
            # Unknown event type — forward as-is
            await manager.send_to_account(account_id, {
                "type": event_type,
                "data": data,
            })

    except Exception as e:
        logger.warning(f"[event_bus] WebSocket dispatch failed for {account_id[:8]}: {e}")
