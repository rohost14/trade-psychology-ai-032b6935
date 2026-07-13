"""
WebSocket API — Real-Time Event Push

Pushes behavioral alerts, trade events, and replay events to connected clients.
Price data is NOT redistributed via this WebSocket (exchange data compliance).
KiteTicker runs server-side for Redis LTP cache used by Celery behavioral checks only.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from sqlalchemy import select
from typing import Dict, Optional
from uuid import UUID
import asyncio
import json
import logging
from datetime import datetime, timezone

from app.models.broker_account import BrokerAccount
from app.api.deps import get_current_user_ws
from app.core.database import SessionLocal

router = APIRouter()
logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections for alerts, trades, and behavioral events."""

    def __init__(self):
        # account_id -> WebSocket connection
        self.active_connections: Dict[str, WebSocket] = {}
        # Lock for thread safety
        self._lock = asyncio.Lock()

    async def disconnect(self, account_id: str):
        """Remove disconnected client."""
        async with self._lock:
            self.active_connections.pop(account_id, None)
        logger.info(f"WebSocket disconnected: {account_id[:8]}...")

    async def send_to_account(self, account_id: str, message: dict):
        """Send message to specific account."""
        websocket = self.active_connections.get(account_id)
        if websocket:
            try:
                import asyncio
                await asyncio.wait_for(websocket.send_json(message), timeout=2.0)
            except Exception as e:
                logger.error(f"Send failed for {account_id[:8]}...: {e}")
                await self.disconnect(account_id)

    async def send_alert(self, account_id: str, alert_data: dict, event_id: str = ""):
        """Send risk alert to specific account."""
        await self.send_to_account(account_id, {
            "type": "alert_update",
            "event_id": event_id,
            "data": alert_data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    async def send_trade_update(self, account_id: str, trade_data: dict, event_id: str = ""):
        """Send trade update notification."""
        await self.send_to_account(account_id, {
            "type": "trade_update",
            "event_id": event_id,
            "data": trade_data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })


# Global connection manager
manager = ConnectionManager()


@router.websocket("/ws/prices")
async def websocket_prices(
    websocket: WebSocket,
    since: Optional[str] = Query(None),  # last_event_id for replay on reconnect
):
    """
    WebSocket endpoint for real-time price updates.

    Connection:
        ws://host/api/ws/prices?since=LAST_EVENT_ID

    Auth: first message from client MUST be:
        {"action": "auth", "token": "JWT_TOKEN"}
    Server closes with code 4001 if auth is missing, invalid, or times out (5s).
    This prevents the JWT from appearing in proxy logs / browser DevTools history.

    Messages from client (after auth):
        {"action": "subscribe", "instruments": ["RELIANCE", "NIFTY 50"]}
        {"action": "unsubscribe", "instruments": ["RELIANCE"]}
        {"action": "subscribe_positions"}  # Subscribe to all position instruments

    Messages from server:
        {"type": "auth_ok"}  # Confirms authentication succeeded
        {"type": "price", "instrument": "RELIANCE", "data": {...}}
        {"type": "trade", "data": {...}}
        {"type": "alert", "data": {...}}
        {"type": "pong"}  # Response to ping
    """
    # Accept the HTTP→WS upgrade before any auth (required by protocol)
    await websocket.accept()

    # First message must arrive within 5s and must be {"action":"auth","token":"..."}
    account_uuid = None
    try:
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
        first_msg = json.loads(raw)
        if first_msg.get("action") == "auth":
            token = first_msg.get("token", "")
            if token:
                account_uuid = await get_current_user_ws(token)
    except (asyncio.TimeoutError, Exception):
        pass

    if not account_uuid:
        await websocket.close(code=4001, reason="Authentication required")
        return

    # Check token revocation — prevents use of old JWTs after disconnect.
    # One lightweight DB query at connect time; not repeated during the session.
    try:
        async with SessionLocal() as db:
            result = await db.execute(
                select(BrokerAccount.token_revoked_at).where(BrokerAccount.id == account_uuid)
            )
            row = result.first()
            if not row or row[0] is not None:
                await websocket.close(code=4001, reason="Token revoked")
                return
    except Exception as e:
        logger.warning(f"WebSocket revocation check failed: {e} — closing connection")
        await websocket.close(code=4001, reason="Authentication error")
        return

    account_id = str(account_uuid)

    # Register in manager (already accepted above — skip the accept() in connect())
    async with manager._lock:
        manager.active_connections[account_id] = websocket
    logger.info(f"WebSocket connected: {account_id[:8]}...")

    # Confirm auth to client so it can proceed with subscriptions
    await asyncio.wait_for(websocket.send_json({"type": "auth_ok"}), timeout=2.0)

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

            # Signal replay complete so client knows it has full context.
            # truncated=True means the replay limit was hit — client should trigger
            # a full data refresh (e.g. re-fetch trades/positions) rather than
            # assuming it has a complete event log.
            last_replay_id = missed_events[-1][0] if missed_events else since
            await websocket.send_json({
                "type": "replay_complete",
                "last_event_id": last_replay_id,
                "replayed": len(missed_events),
                "truncated": len(missed_events) == 200,
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

                elif action == "subscribe_positions":
                    # Starts the shared KiteTicker for this account's instruments.
                    # Ticks: → Redis LTP cache (behavioral Celery tasks)
                    #        → broadcast_ltp() → ltp_update WebSocket event (live P&L)
                    try:
                        from app.services.price_stream_service import price_stream
                        from app.core.database import SessionLocal
                        async with SessionLocal() as db:
                            await price_stream.start_account(UUID(account_id), db)
                    except Exception as e:
                        logger.error(f"Failed to start price stream for {account_id[:8]}: {e}")
                    await websocket.send_json({"type": "subscribed"})

                elif action in ("subscribe", "unsubscribe"):
                    # Price fan-out removed — price data is not redistributed via this WebSocket.
                    # Acknowledge silently so existing frontend code doesn't error.
                    await websocket.send_json({"type": "subscribed", "instruments": message.get("instruments", [])})

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


async def notify_price_update(instrument: str, price_data: dict):
    """Unused stub — fan-out handled by SharedPriceStream.broadcast_ltp."""
    pass


async def notify_trade_update(account_id: str, trade_data: dict):
    """Called when a new trade is processed."""
    await manager.send_trade_update(account_id, trade_data)


async def notify_risk_alert(account_id: str, alert_data: dict):
    """Called when a risk alert is triggered."""
    await manager.send_alert(account_id, alert_data)
