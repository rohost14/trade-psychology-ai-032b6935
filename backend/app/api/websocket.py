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
    """Manages WebSocket connections for alerts, trades, and behavioral events.

    An account may have MULTIPLE live connections (several browser tabs / devices),
    so connections are stored as a set per account. A message is fanned out to every
    live socket for the account; dead sockets are pruned individually.
    """

    #: Outbound queue depth per account. A client this far behind is not going
    #: to catch up, and buffering more of its backlog only spends memory to
    #: deliver alerts it will read long after they mattered.
    QUEUE_MAXSIZE = 100

    def __init__(self):
        # account_id -> set of WebSocket connections
        self.active_connections: Dict[str, "set[WebSocket]"] = {}
        # Lock for thread safety
        self._lock = asyncio.Lock()
        # account_id -> outbound queue, and the single task draining it.
        #
        # WHY THIS EXISTS. The event subscriber used to `await` delivery for one
        # account before reading the next event, and delivery awaits each socket
        # with a 2-second timeout. So one trader on a stalled connection delayed
        # EVERY other trader's alerts by up to two seconds per socket. At one
        # user that is invisible; with a few thousand it is the difference
        # between a mirror and a report.
        #
        # One queue and one drain task per account: accounts are isolated from
        # each other, and ordering WITHIN an account is preserved because its
        # drain task is strictly sequential.
        self._queues: Dict[str, asyncio.Queue] = {}
        self._drainers: Dict[str, asyncio.Task] = {}

    async def connect(self, account_id: str, websocket: WebSocket):
        """Register a live connection for an account (additive — does not evict tabs)."""
        async with self._lock:
            self.active_connections.setdefault(account_id, set()).add(websocket)

    async def disconnect(self, account_id: str, websocket: Optional[WebSocket] = None):
        """Remove a specific connection, or all connections for the account when
        websocket is None. The account entry is dropped once no sockets remain."""
        async with self._lock:
            if websocket is None:
                self.active_connections.pop(account_id, None)
            else:
                conns = self.active_connections.get(account_id)
                if conns is not None:
                    conns.discard(websocket)
                    if not conns:
                        self.active_connections.pop(account_id, None)
                        # Nothing left to deliver to: drop the queue and let the
                        # drain task finish, so a disconnected account does not
                        # leak a queue and a task for the process lifetime.
                        self._queues.pop(account_id, None)
                        task = self._drainers.pop(account_id, None)
                        if task is not None and not task.done():
                            task.cancel()
        logger.info(f"WebSocket disconnected: {account_id[:8]}...")

    async def send_to_account(self, account_id: str, message: dict):
        """Fan a message out to every live socket for this account."""
        async with self._lock:
            conns = list(self.active_connections.get(account_id, ()))
        if not conns:
            return
        # Concurrently, not one after another: these are separate devices for the
        # same trader and nothing orders them relative to each other, so a stalled
        # phone must not hold up the desktop it is sitting next to.
        async def _send(ws):
            try:
                await asyncio.wait_for(ws.send_json(message), timeout=2.0)
                return None
            except Exception as e:
                logger.error(f"Send failed for {account_id[:8]}...: {e}")
                return ws

        results = await asyncio.gather(*(_send(ws) for ws in conns))
        for websocket in [ws for ws in results if ws is not None]:
            await self.disconnect(account_id, websocket)

    def deliver(self, account_id: str, message: dict) -> bool:
        """
        Hand a message off for delivery WITHOUT waiting for the sockets.

        This is what the event subscriber calls. It returns immediately, so the
        time one account's sockets take is paid by that account's drain task and
        by nobody else.

        Ordering within an account is preserved: one queue, one drain task,
        strictly sequential. Ordering ACROSS accounts was never meaningful and is
        now explicitly independent.

        Returns False when the account's queue is full - a client that far behind
        is dropped rather than allowed to consume unbounded memory.
        """
        if account_id not in self.active_connections:
            return False

        q = self._queues.get(account_id)
        if q is None:
            q = asyncio.Queue(maxsize=self.QUEUE_MAXSIZE)
            self._queues[account_id] = q

        try:
            q.put_nowait(message)
        except asyncio.QueueFull:
            logger.warning(
                "[ws] %s... outbound queue full (%d) - dropping message",
                account_id[:8], self.QUEUE_MAXSIZE,
            )
            return False

        task = self._drainers.get(account_id)
        if task is None or task.done():
            self._drainers[account_id] = asyncio.create_task(self._drain(account_id))
        return True

    async def _drain(self, account_id: str) -> None:
        """
        Deliver one account's queued messages, in order, until it is empty.

        Exceptions are contained here on purpose: a failure delivering to one
        account must not kill the subscriber or any other account's drain.
        """
        q = self._queues.get(account_id)
        if q is None:
            return
        while True:
            try:
                message = q.get_nowait()
            except asyncio.QueueEmpty:
                return
            try:
                await self.send_to_account(account_id, message)
            except Exception as e:
                logger.error("[ws] drain failed for %s...: %s", account_id[:8], e)
            finally:
                q.task_done()

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
        # Close ONLY when the account definitively has a revoked token. A missing row
        # or a query error is treated as fail-OPEN: the JWT was already verified above,
        # and this DB lookup is a secondary defence — a transient hiccup here must not
        # lock out a valid user (that was silently killing every price WS).
        if row is not None and row[0] is not None:
            await websocket.close(code=4001, reason="Token revoked")
            return
    except Exception as e:
        # Fail-OPEN: the JWT was already verified; this secondary lookup must never
        # lock out a valid user on a transient error (kept as a safety net even though
        # the SessionLocal shadow that caused it is now fixed).
        logger.error(f"WS revocation check errored (allowing; JWT already valid): {e!r}")

    account_id = str(account_uuid)

    # Register in manager (already accepted above — skip the accept() in connect())
    await manager.connect(account_id, websocket)
    logger.info(f"WebSocket connected: {account_id[:8]}...")

    # Confirm auth to client so it can proceed with subscriptions
    await asyncio.wait_for(websocket.send_json({"type": "auth_ok"}), timeout=2.0)

    # Start real-time order ingestion for this session.
    # TradeMentor is a mirror — users place orders in the Kite app, so Zerodha
    # postbacks never fire for them. A per-user KiteTicker order-update stream is
    # the only real-time source of those fills. Reference-counted, so multiple tabs
    # share one connection; torn down when the last tab disconnects (finally block).
    try:
        from app.services.order_stream_service import order_stream
        async with SessionLocal() as db:
            await order_stream.start_account(account_uuid, db)
    except Exception as e:
        logger.warning(f"Failed to start order stream for {account_id[:8]}: {e}")

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
                        # SessionLocal is imported at module scope (line 20). A local
                        # re-import here made it function-local, so the revocation check
                        # above hit UnboundLocalError and closed every price WS (4001).
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
        pass
    except Exception as e:
        logger.error(f"WebSocket error for {account_id[:8]}...: {e}")
    finally:
        # Prune only THIS socket (other tabs for the account stay live).
        await manager.disconnect(account_id, websocket)
        # Release this session's hold on the per-user order stream. Reference-counted:
        # the underlying KiteTicker is torn down only when the last tab disconnects.
        try:
            from app.services.order_stream_service import order_stream
            await order_stream.stop_account(account_uuid)
        except Exception as e:
            logger.warning(f"Failed to stop order stream for {account_id[:8]}: {e}")


async def notify_price_update(instrument: str, price_data: dict):
    """Unused stub — fan-out handled by SharedPriceStream.broadcast_ltp."""
    pass


async def notify_trade_update(account_id: str, trade_data: dict):
    """Called when a new trade is processed."""
    await manager.send_trade_update(account_id, trade_data)


async def notify_risk_alert(account_id: str, alert_data: dict):
    """Called when a risk alert is triggered."""
    await manager.send_alert(account_id, alert_data)
