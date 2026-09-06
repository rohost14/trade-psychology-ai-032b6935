"""
Order Stream Service — real-time ingestion of the user's Zerodha orders.

WHY THIS EXISTS
───────────────
TradeMentor is a "mirror" — users place orders in the Kite app / Kite web, NOT
through TradeMentor. Zerodha's postback webhook only fires for orders placed
through the KiteConnect app that registered the postback URL, so for the app's
primary usage mode NO postback is ever delivered. Without this service, fills
reach the DB only on manual sync / page-load sync / EOD sync — the source of the
"random 3–5 minute" delay users experience.

Zerodha's designed answer is the KiteTicker WebSocket `on_order_update` callback:
it pushes an order update for EVERY order of the authenticated user, regardless of
where the order was placed. This service opens ONE per-user KiteTicker connection
(authenticated with that user's own api_key + access_token) while the user's app
session is active, and routes each COMPLETE fill straight into the existing
`process_webhook_trade` Celery pipeline — the same pipeline the postback uses.

ARCHITECTURE
────────────
  Per online user:
    ZerodhaOrderTicker(api_key=user.api_key, access_token=user.token)
      ↓ on_order_update (COMPLETE fills only)
    process_webhook_trade.delay(trade_data, account_id)   # existing pipeline
      → DB upsert → ledger → CompletedTrade → BehaviorEngine → event bus → browser

  Lifecycle:
    - start_account(): called from the WebSocket handler when a browser connects
      and sends `subscribe_positions`. Idempotent.
    - stop_account(): called on WebSocket disconnect. Reference-counted so a second
      browser tab does not tear down the first tab's stream.
    - Token expiry (daily ~6 AM): on_noreconnect marks the connection dead; it is
      rebuilt automatically the next time the user connects (fresh token from OAuth).

SCALE NOTE
──────────
This is genuinely one outbound WebSocket per ONLINE user (not per registered user).
Order updates are per-account and cannot be shared like market data. This is the
same shape Sensibull-class products run; a Zerodha partnership raises the connection
limits but does not remove the need. Connections are torn down as soon as the user's
browser disconnects, so the count tracks concurrent active sessions, not signups.

IDEMPOTENCY
───────────
Order updates carry the Kite `order_id`. `process_webhook_trade` dedupes on
order_id (upsert), `processed_at` atomic claim, and the ledger's unique
idempotency_key `{order_id}:ledger`. If a postback AND an order-stream update both
arrive for the same order, they share the same key and are processed exactly once.
"""

import asyncio
import logging
import threading
import time
from typing import Any, Dict, Optional, Set
from uuid import UUID

logger = logging.getLogger(__name__)

# The status that carries a completed fill and drives the TRADE pipeline.
# Every OTHER status is still persisted as an order-lifecycle event (see
# _on_order_update) - it is only the trade/ledger/detector path that is gated,
# because an order that has filled nothing is not a position.
_FILL_STATUS = "COMPLETE"

# Products TradeMentor tracks (matches TRACKED_PRODUCTS in trade_sync_service).
_TRACKED_PRODUCTS = {"MIS", "NRML", "MTF"}

# Bound the per-connection dedup set so a long session cannot grow it without limit.
_DEDUP_MAX = 2000

# CONFIRMED against Zerodha's own documentation (kite.trade/docs/connect/v3/
# websocket/, checked 2026-09-03): "Single API key can have upto 3 websocket
# connections." The limit is PER API KEY, not per authenticated user or
# access_token. This was an open question for a long time and the pessimistic
# branch is the true one.
#
# WHAT THAT MEANS HERE. Every account resolves to one platform api_key
# (`account.api_key or settings.ZERODHA_API_KEY`), so the realtime order stream
# has THREE connection slots for the entire deployment - not three per user.
# Beyond that, `start_account` skips and the account falls back to sync-only
# ingestion. More users do not get more slots; only more api_keys would.
#
# F4 IS NOT BROKEN BY THIS, and that is worth stating because it looks fatal.
# The absence claim is licensed by the daily `sync_orders_to_db` order-book
# snapshot, not by the stream. Every user therefore gets correct stop-loss
# evidence once a day at EOD; the stream only makes it same-minute for whoever
# holds a slot. Overflow users abstain until the snapshot, which is the honest
# behaviour rather than a degraded one.
#
# Kept at 2, one below the documented 3, to leave headroom for the market-data
# fallback ticker which may also consume a connection on the same key.
_MAX_CONN_PER_API_KEY = 2


def _safe_int(v, default=0):
    try:
        return int(v) if v not in (None, "", "None") else default
    except (ValueError, TypeError):
        return default


def _safe_float(v, default=0.0):
    try:
        return float(v) if v not in (None, "", "None") else default
    except (ValueError, TypeError):
        return default


def _to_iso(ts) -> Optional[str]:
    """Order-update timestamps may be datetime objects or strings — normalise to str."""
    if ts is None:
        return None
    try:
        # datetime → ISO; str → itself
        return ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
    except Exception:
        return str(ts)


def _json_safe(value):
    """
    Recursively coerce a value into something Celery's JSON serializer accepts.
    KiteTicker order-update dicts can contain datetime objects (nested in `meta`,
    timestamps, etc.); an unserialisable payload would make .delay() raise and drop
    the fill, so we stringify anything that isn't a JSON-native type.
    """
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


class ZerodhaOrderTicker:
    """
    Thin wrapper around kiteconnect.KiteTicker used ONLY for order updates.

    Unlike the market-data ticker, this subscribes to no instruments — Kite pushes
    order updates for the authenticated user automatically once connected. Runs the
    KiteTicker in its own daemon thread; the order-update callback enqueues a Celery
    task (a sync Redis operation, safe to call from the callback thread).
    """

    def __init__(self, api_key: str, access_token: str, broker_account_id: UUID):
        self.api_key = api_key
        self.access_token = access_token
        self.broker_account_id = broker_account_id
        # Annotated: without it mypy infers the attribute's type as `None`
        # from this assignment alone, and then every `self.kws.on_*`
        # below is an attribute error on None - twelve findings across
        # the two stream services. `Any` rather than KiteTicker because
        # kiteconnect is an optional import guarded by ImportError.
        self.kws: Optional[Any] = None
        self._connected = False
        self._dead = False  # set on noreconnect (token expiry) — triggers rebuild
        self._dedup: "OrderedDedup" = OrderedDedup(_DEDUP_MAX)
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    async def connect(self) -> bool:
        try:
            from kiteconnect import KiteTicker
        except ImportError:
            logger.warning("[order_ticker] kiteconnect not installed — order streaming disabled.")
            return False

        self._loop = asyncio.get_running_loop()
        try:
            self.kws = KiteTicker(self.api_key, self.access_token)
        except Exception as e:
            logger.error(f"[order_ticker:{self.broker_account_id}] KiteTicker init failed: {e}")
            return False

        self.kws.on_connect = self._on_connect
        self.kws.on_order_update = self._on_order_update
        self.kws.on_close = self._on_close
        self.kws.on_error = self._on_error
        self.kws.on_noreconnect = self._on_noreconnect

        # threaded=True: KiteTicker runs its own loop in a daemon thread.
        await self._loop.run_in_executor(None, lambda: self.kws.connect(threaded=True))
        logger.info(f"[order_ticker:{self.broker_account_id}] order-update thread started.")
        return True

    # ── KiteTicker callbacks (run in the KiteTicker thread) ───────────────────

    def _on_connect(self, ws, response):
        self._connected = True
        self._dead = False
        logger.info(f"[order_ticker:{self.broker_account_id}] connected — receiving order updates.")

    def _on_order_update(self, ws, data):
        """
        Fired for every order status change of the authenticated user.
        Routes COMPLETE fills into the existing process_webhook_trade pipeline.
        """
        try:
            status = (data.get("status") or "").upper()

            product = (data.get("product") or "").upper()
            if product and product not in _TRACKED_PRODUCTS:
                return

            order_id = data.get("order_id")
            if not order_id:
                return

            order_data = self._build_trade_data(data)

            # ── 1. EVERY lifecycle state is recorded ───────────────────────
            #
            # This used to `return` on anything that was not COMPLETE, so a
            # resting stop-loss arrived here several times and was discarded
            # every time. TRIGGER PENDING is protection; the same order
            # CANCELLED before the loss ran is not; REJECTED never was. None of
            # that is recoverable from fills, and Kite's orders() is today-only
            # so it cannot be backfilled later either.
            #
            # Deduped on (order_id, status, filled_quantity): a status that has
            # not moved is a resend, a status that HAS moved is new evidence.
            state_key = f"{order_id}:{status}:{_safe_int(data.get('filled_quantity'))}"
            if self._dedup.add(state_key):
                self._enqueue_order_event(order_data)

            # ── 2. Only a FILL drives the trade pipeline ───────────────────
            #
            # An order is not a position. Routing a TRIGGER PENDING stop into
            # process_webhook_trade would manufacture a CompletedTrade out of
            # something that has filled nothing.
            if status != _FILL_STATUS:
                return

            filled = _safe_int(data.get("filled_quantity"))
            fill_key = f"fill:{order_id}:{filled}"
            if not self._dedup.add(fill_key):
                return

            self._enqueue(order_data)

        except Exception as e:
            logger.error(
                f"[order_ticker:{self.broker_account_id}] on_order_update failed: {e}",
                exc_info=True,
            )

    def _build_trade_data(self, data: dict) -> dict:
        """Map a KiteTicker order-update dict to the trade_data shape the webhook
        pipeline expects (identical keys to webhooks.zerodha_postback)."""
        return {
            "order_id": data.get("order_id"),
            "exchange_order_id": data.get("exchange_order_id"),
            "status": data.get("status"),
            "tradingsymbol": data.get("tradingsymbol"),
            "exchange": data.get("exchange"),
            "transaction_type": data.get("transaction_type"),
            "order_type": data.get("order_type"),
            "product": data.get("product"),
            "quantity": _safe_int(data.get("quantity")),
            "filled_quantity": _safe_int(data.get("filled_quantity")),
            "pending_quantity": _safe_int(data.get("pending_quantity")),
            "cancelled_quantity": _safe_int(data.get("cancelled_quantity")),
            "price": _safe_float(data.get("price")),
            "average_price": _safe_float(data.get("average_price")),
            "trigger_price": _safe_float(data.get("trigger_price")),
            "status_message": data.get("status_message"),
            "order_timestamp": _to_iso(data.get("order_timestamp")),
            "exchange_timestamp": _to_iso(data.get("exchange_timestamp")),
            "fill_timestamp": _to_iso(data.get("exchange_update_timestamp")),
            "validity": data.get("validity", "DAY"),
            "variety": data.get("variety", "regular"),
            "disclosed_quantity": _safe_int(data.get("disclosed_quantity")),
            "parent_order_id": data.get("parent_order_id"),
            "tag": data.get("tag"),
            "guid": data.get("guid"),
            "instrument_token": _safe_int(data.get("instrument_token")) or None,
            "raw_payload": _json_safe(dict(data)),
        }

    def _enqueue_order_event(self, order_data: dict):
        """Order-lifecycle event -> `orders` table. Never creates a trade."""
        try:
            from app.tasks.trade_tasks import persist_order_event
            persist_order_event.delay(order_data, str(self.broker_account_id))
            try:
                from app.core.metrics import incr
                incr("order_stream_events")
            except Exception:
                pass
        except Exception as e:
            logger.error(
                f"[order_ticker:{self.broker_account_id}] order-event enqueue "
                f"failed for {order_data.get('order_id')}: {e}"
            )

    def _enqueue(self, trade_data: dict):
        """Hand the fill to the Celery pipeline (same path as the postback webhook)."""
        try:
            from app.tasks.trade_tasks import process_webhook_trade
            import uuid as _uuid
            task = process_webhook_trade.delay(
                trade_data, str(self.broker_account_id), f"orderstream-{_uuid.uuid4().hex[:8]}"
            )
            try:
                from app.core.metrics import incr
                incr("order_stream_fills")
            except Exception:
                pass
            logger.info(
                f"[order_ticker:{self.broker_account_id}] COMPLETE fill "
                f"{trade_data.get('tradingsymbol')} order={trade_data.get('order_id')} "
                f"→ queued {task.id}"
            )
        except Exception as e:
            # If Celery is unreachable the fill is still recovered by the next
            # manual/EOD sync (replay_missed_fills_into_ledger) — never lost.
            logger.error(
                f"[order_ticker:{self.broker_account_id}] failed to enqueue order "
                f"{trade_data.get('order_id')}: {e}"
            )

    def _on_close(self, ws, code, reason):
        self._connected = False
        logger.warning(f"[order_ticker:{self.broker_account_id}] closed: {code} — {reason}")

    def _on_error(self, ws, code, reason):
        logger.error(f"[order_ticker:{self.broker_account_id}] error: {code} — {reason}")

    def _on_noreconnect(self, ws):
        self._connected = False
        self._dead = True
        logger.error(
            f"[order_ticker:{self.broker_account_id}] max reconnects exceeded — "
            "token likely expired. Will rebuild on next session."
        )

    def stop(self):
        self._connected = False
        if self.kws:
            try:
                self.kws.stop()
                self.kws.close()
            except Exception:
                pass
        logger.info(f"[order_ticker:{self.broker_account_id}] stopped.")


class OrderedDedup:
    """Tiny bounded FIFO set — remembers the last N keys, O(1) add/contains."""

    def __init__(self, maxlen: int):
        self._maxlen = maxlen
        self._set: Set[str] = set()
        self._order: list = []
        self._lock = threading.Lock()

    def add(self, key: str) -> bool:
        """Return True if key is new (added), False if already seen."""
        with self._lock:
            if key in self._set:
                return False
            self._set.add(key)
            self._order.append(key)
            if len(self._order) > self._maxlen:
                old = self._order.pop(0)
                self._set.discard(old)
            return True


class OrderStreamService:
    """
    Manages per-user order-update KiteTicker connections.

    Reference-counted: multiple browser tabs for the same account share ONE
    connection; it is torn down only when the last tab disconnects.
    """

    def __init__(self):
        self._tickers: Dict[str, ZerodhaOrderTicker] = {}
        self._refcount: Dict[str, int] = {}
        # api_key -> number of live order-stream connections (Zerodha caps per key)
        self._api_key_conns: Dict[str, int] = {}
        # account_id -> api_key used by its live connection (so stop decrements the right key)
        self._account_key: Dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def start_account(self, broker_account_id: UUID, db) -> None:
        """
        Open (or reuse) the order-update stream for an account. Idempotent.
        Increments the reference count so concurrent tabs are handled correctly.
        """
        account_id_str = str(broker_account_id)

        async with self._lock:
            self._refcount[account_id_str] = self._refcount.get(account_id_str, 0) + 1

            existing = self._tickers.get(account_id_str)
            if existing and existing._connected and not existing._dead:
                return  # already streaming

            # Rebuild if the previous connection died (token expiry) or never existed
            if existing:
                self._teardown_ticker_locked(account_id_str)

            resolved = await self._resolve_credentials(broker_account_id, db)
            if not resolved:
                return
            api_key, access_token = resolved

            # Enforce Zerodha's per-api_key connection cap. Overflow users fall back
            # to sync-only ingestion (still recovered by manual/EOD sync) rather than
            # thrashing connections that Zerodha would drop.
            if self._api_key_conns.get(api_key, 0) >= _MAX_CONN_PER_API_KEY:
                logger.warning(
                    f"[order_stream] api_key connection cap ({_MAX_CONN_PER_API_KEY}) reached "
                    f"for {broker_account_id} — order stream skipped (sync fallback active). "
                    f"This only occurs when many users share ONE api_key; per-user keys avoid it."
                )
                return

            ticker = ZerodhaOrderTicker(api_key, access_token, broker_account_id)
            ok = await ticker.connect()
            if not ok:
                return
            self._tickers[account_id_str] = ticker
            self._account_key[account_id_str] = api_key
            self._api_key_conns[api_key] = self._api_key_conns.get(api_key, 0) + 1
            try:
                from app.core.metrics import incr
                incr("order_stream_started")
            except Exception:
                pass

    async def _resolve_credentials(self, broker_account_id: UUID, db):
        """Return (api_key, access_token) for this account, or None if unavailable."""
        from app.models.broker_account import BrokerAccount
        from app.core.config import settings

        account = await db.get(BrokerAccount, broker_account_id)
        if not account or not account.access_token or account.token_revoked_at:
            logger.warning(f"[order_stream] cannot start {broker_account_id}: no valid token.")
            return None

        # Order updates are per-account: the connection MUST use this account's own
        # (api_key, access_token) pair. api_key is recorded on every account at OAuth
        # time (per-user setup flow uses the user's key; global flow uses the global key).
        api_key = account.api_key or settings.ZERODHA_API_KEY
        if not api_key:
            logger.warning(f"[order_stream] no api_key for {broker_account_id} — cannot stream orders.")
            return None

        try:
            access_token = account.decrypt_token(account.access_token)
        except ValueError as e:
            logger.error(f"[order_stream] token decrypt failed for {broker_account_id}: {e}")
            return None

        return api_key, access_token

    def _teardown_ticker_locked(self, account_id_str: str) -> None:
        """Stop and unregister an account's ticker. Caller must hold self._lock."""
        ticker = self._tickers.pop(account_id_str, None)
        key = self._account_key.pop(account_id_str, None)
        if key and self._api_key_conns.get(key):
            self._api_key_conns[key] -= 1
            if self._api_key_conns[key] <= 0:
                self._api_key_conns.pop(key, None)
        if ticker:
            ticker.stop()

    async def stop_account(self, broker_account_id: UUID) -> None:
        """
        Decrement the reference count; tear the connection down only when no tab
        for this account remains connected.
        """
        account_id_str = str(broker_account_id)

        async with self._lock:
            remaining = self._refcount.get(account_id_str, 0) - 1
            if remaining > 0:
                self._refcount[account_id_str] = remaining
                return

            self._refcount.pop(account_id_str, None)
            self._teardown_ticker_locked(account_id_str)

    def is_streaming(self, broker_account_id: UUID) -> bool:
        t = self._tickers.get(str(broker_account_id))
        return bool(t and t._connected and not t._dead)


# Singleton — imported by the WebSocket handler.
order_stream = OrderStreamService()
