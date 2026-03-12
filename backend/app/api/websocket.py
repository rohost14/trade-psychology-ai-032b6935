"""
WebSocket API for Real-Time Price Streaming

Provides:
- Live price updates for subscribed instruments
- Position P&L updates
- Trade notifications
- Risk alerts

Architecture:
- Client connects via WebSocket with JWT token
- Subscribes to specific instruments or all positions
- Server pushes price updates from Zerodha WebSocket
- Rate limited: 1 update per second per instrument
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from sqlalchemy import select
from typing import Dict, Optional, Set
from uuid import UUID
import asyncio
import json
import logging
from datetime import datetime, timezone

from app.models.position import Position
from app.api.deps import get_current_user_ws

router = APIRouter()
logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections and subscriptions."""

    def __init__(self):
        # account_id -> WebSocket connection
        self.active_connections: Dict[str, WebSocket] = {}
        # account_id -> set of subscribed instruments
        self.subscriptions: Dict[str, Set[str]] = {}
        # instrument -> latest price data (cache)
        self.price_cache: Dict[str, dict] = {}
        # Lock for thread safety
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, account_id: str):
        """Accept new WebSocket connection."""
        await websocket.accept()
        async with self._lock:
            self.active_connections[account_id] = websocket
            self.subscriptions[account_id] = set()
        logger.info(f"WebSocket connected: {account_id[:8]}...")

    async def disconnect(self, account_id: str):
        """Remove disconnected client."""
        async with self._lock:
            self.active_connections.pop(account_id, None)
            self.subscriptions.pop(account_id, None)
        logger.info(f"WebSocket disconnected: {account_id[:8]}...")

    async def subscribe(self, account_id: str, instruments: Set[str]):
        """Subscribe to instrument price updates."""
        async with self._lock:
            if account_id in self.subscriptions:
                self.subscriptions[account_id].update(instruments)
                logger.info(f"Subscribed {account_id[:8]}... to {instruments}")

    async def unsubscribe(self, account_id: str, instruments: Set[str]):
        """Unsubscribe from instrument price updates."""
        async with self._lock:
            if account_id in self.subscriptions:
                self.subscriptions[account_id] -= instruments

    async def send_to_account(self, account_id: str, message: dict):
        """Send message to specific account."""
        websocket = self.active_connections.get(account_id)
        if websocket:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Send failed for {account_id[:8]}...: {e}")
                await self.disconnect(account_id)

    async def broadcast_price(self, instrument: str, price_data: dict):
        """
        Broadcast price update to all subscribed clients.
        Rate limited: updates cached, broadcast once per second.
        """
        self.price_cache[instrument] = price_data

        # Find all accounts subscribed to this instrument
        subscribers = []
        async with self._lock:
            for account_id, subs in self.subscriptions.items():
                if instrument in subs or "*" in subs:  # * means all instruments
                    subscribers.append(account_id)

        # Send to all subscribers
        message = {
            "type": "price",
            "instrument": instrument,
            "data": price_data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        for account_id in subscribers:
            await self.send_to_account(account_id, message)

    async def send_alert(self, account_id: str, alert_data: dict):
        """Send risk alert to specific account."""
        await self.send_to_account(account_id, {
            "type": "alert",
            "data": alert_data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    async def send_trade_update(self, account_id: str, trade_data: dict):
        """Send trade update notification."""
        await self.send_to_account(account_id, {
            "type": "trade",
            "data": trade_data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    async def push_behavioral_event(self, account_id: str, event):
        """
        Push behavioral event to connected client.
        Only called AFTER event is persisted in DB.
        """
        await self.send_to_account(account_id, {
            "type": "behavioral_event",
            "data": {
                "event_type": event.event_type,
                "severity": event.severity,
                "message": event.message,
                "confidence": float(event.confidence),
                "detected_at": event.detected_at.isoformat() if event.detected_at else None,
                "trigger_position_key": event.trigger_position_key,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })


# Global connection manager
manager = ConnectionManager()


@router.websocket("/ws/prices")
async def websocket_prices(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
    since: Optional[str] = Query(None),  # last_event_id for replay on reconnect
):
    """
    WebSocket endpoint for real-time price updates.

    Connection:
        ws://host/api/ws/prices?token=JWT_TOKEN

    Messages from client:
        {"action": "subscribe", "instruments": ["RELIANCE", "NIFTY 50"]}
        {"action": "unsubscribe", "instruments": ["RELIANCE"]}
        {"action": "subscribe_positions"}  # Subscribe to all position instruments

    Messages from server:
        {"type": "price", "instrument": "RELIANCE", "data": {...}}
        {"type": "trade", "data": {...}}
        {"type": "alert", "data": {...}}
        {"type": "pong"}  # Response to ping
    """
    # Authenticate via JWT token
    account_uuid = None
    if token:
        account_uuid = await get_current_user_ws(token)

    if not account_uuid:
        await websocket.close(code=4001, reason="Authentication required")
        return

    account_id = str(account_uuid)
    await manager.connect(websocket, account_id)

    # Event replay — send all events missed since last connection
    # Client sends ?since=last_event_id on reconnect.
    # '0-0' = replay all stored events (up to ACCOUNT_MAXLEN=500).
    # Missing/empty since = skip replay (first connection).
    if since is not None:
        try:
            from app.core.event_bus import replay_events_for_account
            replay_since = since if since else "0-0"
            missed_events = await replay_events_for_account(account_id, replay_since, limit=200)

            for event_id, fields in missed_events:
                try:
                    import json as _json
                    await websocket.send_json({
                        "type": "replay",
                        "event_id": event_id,
                        "event_type": fields.get("type"),
                        "data": _json.loads(fields.get("data", "{}")),
                    })
                except Exception:
                    break  # client disconnected during replay

            # Signal replay complete so client knows it has full context
            last_replay_id = missed_events[-1][0] if missed_events else since
            await websocket.send_json({
                "type": "replay_complete",
                "last_event_id": last_replay_id,
                "replayed": len(missed_events),
            })
            logger.info(f"[ws] Replayed {len(missed_events)} events for {account_id[:8]}")
        except Exception as e:
            logger.warning(f"[ws] Event replay failed (non-fatal): {e}")

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                action = message.get("action")

                if action == "ping":
                    await websocket.send_json({"type": "pong"})

                elif action == "subscribe":
                    instruments = set(message.get("instruments", []))
                    await manager.subscribe(account_id, instruments)
                    await websocket.send_json({
                        "type": "subscribed",
                        "instruments": list(instruments),
                    })

                elif action == "unsubscribe":
                    instruments = set(message.get("instruments", []))
                    await manager.unsubscribe(account_id, instruments)
                    await websocket.send_json({
                        "type": "unsubscribed",
                        "instruments": list(instruments),
                    })

                elif action == "subscribe_positions":
                    # 1. Subscribe this frontend connection to position symbols
                    instruments = await get_position_instruments(account_id)
                    await manager.subscribe(account_id, instruments)

                    # 2. Start/connect the KiteTicker for live Kite prices.
                    #    This is the missing link — without this, the frontend
                    #    is listening but nobody is pulling prices from Kite.
                    try:
                        from app.services.price_stream_service import price_stream
                        from app.core.database import SessionLocal
                        async with SessionLocal() as db:
                            await price_stream.start_account(UUID(account_id), db)
                    except Exception as e:
                        logger.error(f"Failed to start price stream for {account_id[:8]}: {e}")

                    await websocket.send_json({
                        "type": "subscribed",
                        "instruments": list(instruments),
                        "live": True,
                    })

                else:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Unknown action: {action}",
                    })

            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON",
                })

    except WebSocketDisconnect:
        await manager.disconnect(account_id)
    except Exception as e:
        logger.error(f"WebSocket error for {account_id[:8]}...: {e}")
        await manager.disconnect(account_id)


async def get_position_instruments(account_id: str) -> Set[str]:
    """Get all instruments from open positions for an account."""
    from app.core.database import SessionLocal

    async with SessionLocal() as db:
        result = await db.execute(
            select(Position.tradingsymbol).where(
                Position.broker_account_id == UUID(account_id),
                Position.total_quantity != 0
            )
        )
        symbols = result.scalars().all()
        return set(symbols)


# Helper function to be called from other parts of the app
async def notify_price_update(instrument: str, price_data: dict):
    """Called by price service to broadcast updates."""
    await manager.broadcast_price(instrument, price_data)


async def notify_trade_update(account_id: str, trade_data: dict):
    """Called when a new trade is processed."""
    await manager.send_trade_update(account_id, trade_data)


async def notify_risk_alert(account_id: str, alert_data: dict):
    """Called when a risk alert is triggered."""
    await manager.send_alert(account_id, alert_data)
