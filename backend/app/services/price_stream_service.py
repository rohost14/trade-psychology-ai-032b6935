"""
Price Streaming Service

Connects to Zerodha KiteTicker WebSocket for live prices.
Broadcasts updates to connected frontend clients via our own WebSocket.

Architecture (current — per-user API keys):
──────────────────────────────────────────
  One KiteTicker connection per active broker account.
  "Active" = account is connected + has at least one open position.
  When the last open position closes, the KiteTicker is kept alive
  (cheap) until the user disconnects — avoids reconnect cost on rapid
  open/close cycles.

  KiteTicker (thread)
    ↓ on_ticks (via run_coroutine_threadsafe)
  _on_tick_received()
    ↓ asyncio event loop
  websocket.notify_price_update()
    ↓
  Frontend WebSocket (per connected browser tab)

Migration path (post-Zerodha partnership):
──────────────────────────────────────────
  Swap PerUserPriceStream for SharedPriceStream.
  SharedPriceStream maintains ONE KiteTicker for all users,
  subscribes to union of all open position instruments,
  and distributes via Redis pub/sub.

  Nothing outside this file needs to change — callers use the
  `price_stream` singleton which is typed as PriceStreamProvider.

  To migrate: change the last line of this file from
      price_stream: PriceStreamProvider = PerUserPriceStream()
  to
      price_stream: PriceStreamProvider = SharedPriceStream()
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, Set, Optional
from uuid import UUID

logger = logging.getLogger(__name__)

# Max 1 price broadcast per second per instrument to avoid flooding frontend.
# KiteTicker sends multiple ticks/second — we throttle here.
_TICK_THROTTLE_SECONDS = 1.0


# ─────────────────────────────────────────────────────────────────────────────
# Abstract interface — the only contract callers depend on
# ─────────────────────────────────────────────────────────────────────────────

class PriceStreamProvider(ABC):
    """
    Interface for live price streaming.

    PerUserPriceStream: one KiteTicker per account (current, per-user API keys).
    SharedPriceStream:  one KiteTicker for all accounts (future, partnership API).
    """

    @abstractmethod
    async def start_account(self, broker_account_id: UUID, db) -> None:
        """
        Start price streaming for a broker account.
        Connects KiteTicker if not already connected.
        Subscribes to all instruments with open positions.
        """

    @abstractmethod
    async def refresh_subscriptions(self, broker_account_id: UUID, db) -> None:
        """
        Re-check open positions and subscribe to any new instruments.
        Call this after a trade fills and a new position opens.
        """

    @abstractmethod
    async def stop_account(self, broker_account_id: UUID) -> None:
        """
        Disconnect KiteTicker for an account.
        Call on token revoke or explicit disconnect.
        """

    @abstractmethod
    async def restart_all(self, db) -> None:
        """
        On server startup: reconnect KiteTicker for all active accounts.
        Prevents stale data after a server restart during market hours.
        """


# ─────────────────────────────────────────────────────────────────────────────
# ZerodhaTicker: thin wrapper around kiteconnect.KiteTicker
# ─────────────────────────────────────────────────────────────────────────────

class ZerodhaTicker:
    """
    Wraps the synchronous kiteconnect.KiteTicker in a thread so our
    async FastAPI app can interact with it without blocking.

    Key design points:
    - KiteTicker runs in a daemon thread (threaded=True).
    - Price ticks arrive in that thread via on_ticks callback.
    - We use asyncio.run_coroutine_threadsafe() to hand ticks back
      to the main event loop safely.
    - Throttle: at most one broadcast per instrument per second.
    """

    def __init__(
        self,
        api_key: str,
        access_token: str,
        broker_account_id: UUID,
        on_tick_callback,   # async callable(tradingsymbol: str, price_data: dict)
    ):
        self.api_key = api_key
        self.access_token = access_token
        self.broker_account_id = broker_account_id
        self.on_tick_callback = on_tick_callback

        self.kws = None
        self.subscribed_tokens: Set[int] = set()
        self._connected = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._last_tick_times: Dict[str, float] = {}   # symbol → monotonic timestamp

    async def connect(self) -> None:
        """Connect to Kite WebSocket in a background thread."""
        try:
            from kiteconnect import KiteTicker
        except ImportError:
            logger.warning(
                f"[ticker:{self.broker_account_id}] kiteconnect not installed — "
                "price streaming disabled."
            )
            return

        # Capture the running event loop BEFORE entering the thread.
        self._loop = asyncio.get_running_loop()

        self.kws = KiteTicker(self.api_key, self.access_token)
        self.kws.on_connect = self._on_connect
        self.kws.on_ticks = self._on_ticks
        self.kws.on_close = self._on_close
        self.kws.on_error = self._on_error
        self.kws.on_reconnect = self._on_reconnect
        self.kws.on_noreconnect = self._on_noreconnect

        # threaded=True: KiteTicker runs its own event loop in a daemon thread.
        # We don't await here — the thread starts and returns immediately.
        await self._loop.run_in_executor(None, lambda: self.kws.connect(threaded=True))
        logger.info(f"[ticker:{self.broker_account_id}] KiteTicker thread started.")

    # ── KiteTicker callbacks (called from KiteTicker thread) ──────────────────

    def _on_connect(self, ws, response):
        self._connected = True
        logger.info(f"[ticker:{self.broker_account_id}] Connected to Kite WebSocket.")

        # Resubscribe after reconnect (tokens are preserved across reconnects).
        if self.subscribed_tokens:
            tokens = list(self.subscribed_tokens)
            ws.subscribe(tokens)
            ws.set_mode(ws.MODE_LTP, tokens)   # LTP = last traded price, lightest mode

    def _on_ticks(self, ws, ticks):
        """
        Called by KiteTicker thread for every price update.
        Throttled to 1 broadcast/sec/instrument, then:
          1. Written to Redis LTP cache (TTL=2s) — for position monitor
          2. Forwarded to asyncio event loop for WebSocket broadcast
        """
        if not self._loop:
            return

        import time
        now = time.monotonic()

        for tick in ticks:
            instrument_token = tick.get("instrument_token")
            symbol = tick.get("tradingsymbol") or str(instrument_token)
            last_price = tick.get("last_price")

            # Throttle: skip if updated within the last second
            last = self._last_tick_times.get(symbol, 0.0)
            if (now - last) < _TICK_THROTTLE_SECONDS:
                continue
            self._last_tick_times[symbol] = now

            price_data = {
                "last_price": last_price,
                "change": tick.get("change"),
                "change_percent": tick.get("change_percent"),
                "instrument_token": instrument_token,
            }

            # 1. Write to Redis LTP cache (TTL=2s)
            # Key: ltp:{instrument_token}  Value: price
            # Position monitor reads from here — no REST API polling needed.
            if last_price is not None:
                try:
                    from app.core.config import settings
                    import redis as redis_lib
                    r = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)
                    r.set(f"ltp:{instrument_token}", str(last_price), ex=2)
                except Exception:
                    pass  # Redis write failure never blocks the tick pipeline

            # 2. Broadcast to frontend via WebSocket (if callback set)
            if self.on_tick_callback:
                asyncio.run_coroutine_threadsafe(
                    self.on_tick_callback(symbol, price_data),
                    self._loop,
                )

    def _on_close(self, ws, code, reason):
        self._connected = False
        logger.warning(
            f"[ticker:{self.broker_account_id}] Connection closed: {code} — {reason}"
        )

    def _on_error(self, ws, code, reason):
        logger.error(
            f"[ticker:{self.broker_account_id}] Error: {code} — {reason}"
        )

    def _on_reconnect(self, ws, attempts):
        logger.info(
            f"[ticker:{self.broker_account_id}] Reconnecting (attempt {attempts})…"
        )

    def _on_noreconnect(self, ws):
        logger.error(
            f"[ticker:{self.broker_account_id}] Max reconnect attempts exceeded. "
            "Manual intervention required."
        )
        self._connected = False

    # ── Subscription management ───────────────────────────────────────────────

    def subscribe(self, tokens: list) -> None:
        """Subscribe to instrument tokens (sync — called from event loop)."""
        new_tokens = [t for t in tokens if t not in self.subscribed_tokens]
        if not new_tokens:
            return

        self.subscribed_tokens.update(new_tokens)
        if self.kws and self._connected:
            self.kws.subscribe(new_tokens)
            self.kws.set_mode(self.kws.MODE_LTP, new_tokens)
            logger.info(
                f"[ticker:{self.broker_account_id}] Subscribed to {len(new_tokens)} tokens "
                f"(total: {len(self.subscribed_tokens)})"
            )

    def unsubscribe(self, tokens: list) -> None:
        """Unsubscribe from instrument tokens."""
        self.subscribed_tokens -= set(tokens)
        if self.kws and self._connected:
            self.kws.unsubscribe(tokens)

    def stop(self) -> None:
        """Close the WebSocket connection and stop the ticker thread."""
        self._connected = False
        if self.kws:
            try:
                self.kws.stop()
                self.kws.close()
            except Exception:
                pass
        logger.info(f"[ticker:{self.broker_account_id}] Ticker stopped.")


# ─────────────────────────────────────────────────────────────────────────────
# PerUserPriceStream — Phase 1 implementation (per-user API keys)
# ─────────────────────────────────────────────────────────────────────────────

class PerUserPriceStream(PriceStreamProvider):
    """
    One KiteTicker connection per active broker account.

    Works with per-user Zerodha API keys (current setup).
    Swap to SharedPriceStream when Zerodha partnership provides a single API key.
    """

    def __init__(self):
        # broker_account_id (str) → ZerodhaTicker
        self._tickers: Dict[str, ZerodhaTicker] = {}
        self._lock = asyncio.Lock()

    async def start_account(self, broker_account_id: UUID, db) -> None:
        """
        Connect KiteTicker for this account and subscribe to open positions.
        Safe to call multiple times — idempotent.
        """
        from app.core.config import settings
        from app.models.broker_account import BrokerAccount

        account_id_str = str(broker_account_id)

        async with self._lock:
            if account_id_str in self._tickers:
                # Already connected — just refresh subscriptions
                pass
            else:
                # Load account + decrypt token
                account = await db.get(BrokerAccount, broker_account_id)
                if not account or not account.access_token or account.token_revoked_at:
                    logger.warning(
                        f"[price_stream] Cannot start account {broker_account_id}: "
                        "no valid token."
                    )
                    return

                try:
                    access_token = account.decrypt_token(account.access_token)
                except ValueError as e:
                    logger.error(f"[price_stream] Token decrypt failed for {broker_account_id}: {e}")
                    return

                if not settings.ZERODHA_API_KEY:
                    logger.warning(
                        "[price_stream] ZERODHA_API_KEY not set — "
                        "live price streaming disabled."
                    )
                    return

                from app.api.websocket import notify_price_update

                ticker = ZerodhaTicker(
                    api_key=settings.ZERODHA_API_KEY,
                    access_token=access_token,
                    broker_account_id=broker_account_id,
                    on_tick_callback=notify_price_update,
                )
                await ticker.connect()
                self._tickers[account_id_str] = ticker

        # Subscribe to open positions (outside lock to avoid deadlock with db)
        await self.refresh_subscriptions(broker_account_id, db)

    async def refresh_subscriptions(self, broker_account_id: UUID, db) -> None:
        """
        Subscribe to all instruments where user has open positions.
        Call after every trade fill.
        """
        account_id_str = str(broker_account_id)
        ticker = self._tickers.get(account_id_str)
        if not ticker:
            return

        tokens = await self._get_open_position_tokens(broker_account_id, db)
        if tokens:
            ticker.subscribe(tokens)

    async def stop_account(self, broker_account_id: UUID) -> None:
        """Stop and remove the KiteTicker for this account."""
        account_id_str = str(broker_account_id)
        async with self._lock:
            ticker = self._tickers.pop(account_id_str, None)
        if ticker:
            ticker.stop()

    async def restart_all(self, db) -> None:
        """
        On server restart: reconnect KiteTicker for all connected accounts
        that have open positions.
        """
        from app.models.broker_account import BrokerAccount
        from app.models.position import Position
        from sqlalchemy import select, and_

        # Find accounts that are connected, not revoked, and have open positions
        result = await db.execute(
            select(BrokerAccount.id).where(
                and_(
                    BrokerAccount.status == "connected",
                    BrokerAccount.token_revoked_at == None,  # noqa: E711
                    BrokerAccount.access_token != None,       # noqa: E711
                )
            ).join(
                Position,
                and_(
                    Position.broker_account_id == BrokerAccount.id,
                    Position.total_quantity != 0,
                ),
                isouter=False,
            ).distinct()
        )
        account_ids = result.scalars().all()

        if not account_ids:
            logger.info("[price_stream] No active accounts to reconnect on startup.")
            return

        logger.info(
            f"[price_stream] Reconnecting {len(account_ids)} account(s) on startup."
        )
        for account_id in account_ids:
            try:
                await self.start_account(account_id, db)
            except Exception as e:
                logger.error(f"[price_stream] Failed to restart account {account_id}: {e}")

    async def _get_open_position_tokens(
        self, broker_account_id: UUID, db
    ) -> list:
        """
        Return instrument_tokens for all open positions on this account.
        Uses Position.instrument_token (integer) which KiteTicker requires.
        Falls back to Instrument table lookup if Position lacks the token.
        """
        from app.models.position import Position
        from app.models.instrument import Instrument
        from sqlalchemy import select, and_

        # Primary: get tokens directly from positions table
        pos_result = await db.execute(
            select(Position.tradingsymbol, Position.instrument_token).where(
                and_(
                    Position.broker_account_id == broker_account_id,
                    Position.total_quantity != 0,
                )
            )
        )
        rows = pos_result.all()

        tokens = []
        symbols_missing_token = []

        for tradingsymbol, instrument_token in rows:
            if instrument_token:
                tokens.append(int(instrument_token))
            else:
                symbols_missing_token.append(tradingsymbol)

        # Fallback: look up missing tokens from instruments table
        if symbols_missing_token:
            inst_result = await db.execute(
                select(Instrument.instrument_token).where(
                    Instrument.tradingsymbol.in_(symbols_missing_token)
                )
            )
            for (token,) in inst_result.all():
                if token:
                    tokens.append(int(token))

        return tokens


# ─────────────────────────────────────────────────────────────────────────────
# SharedPriceStream — Phase 2 placeholder (Zerodha partnership)
# ─────────────────────────────────────────────────────────────────────────────

class SharedPriceStream(PriceStreamProvider):
    """
    ONE KiteTicker connection for ALL users. Use after Zerodha partnership
    provides a single shared API key.

    Architecture:
    - Subscribe to union of all users' open position instruments.
    - Distribute via Redis pub/sub: channel = price:{instrument_token}
    - Each account's WebSocket handler subscribes only to its instruments.

    TODO: Implement when partnership API key is available.
    """

    async def start_account(self, broker_account_id: UUID, db) -> None:
        raise NotImplementedError("SharedPriceStream: implement after partnership API key.")

    async def refresh_subscriptions(self, broker_account_id: UUID, db) -> None:
        raise NotImplementedError

    async def stop_account(self, broker_account_id: UUID) -> None:
        raise NotImplementedError

    async def restart_all(self, db) -> None:
        raise NotImplementedError


# ─────────────────────────────────────────────────────────────────────────────
# Singleton — the only object the rest of the app imports
# ─────────────────────────────────────────────────────────────────────────────

# MIGRATION: change PerUserPriceStream() → SharedPriceStream() when partnership arrives.
price_stream: PriceStreamProvider = PerUserPriceStream()


def get_cached_ltp(instrument_token: int) -> Optional[float]:
    """
    Read last traded price from Redis cache.
    Returns None if cache miss (price not yet received or TTL expired).

    Used by:
    - Position monitor (avoid REST API polling)
    - Position P&L calculations during market hours
    TTL is 2 seconds — stale after that, treat as unavailable.
    """
    try:
        from app.core.config import settings
        import redis as redis_lib
        r = redis_lib.from_url(settings.REDIS_URL, decode_responses=True, socket_timeout=1)
        val = r.get(f"ltp:{instrument_token}")
        return float(val) if val is not None else None
    except Exception:
        return None
