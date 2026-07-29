"""
Price Streaming Service

Connects to Zerodha KiteTicker WebSocket for live prices.
Broadcasts updates to connected frontend clients via our own WebSocket.

Architecture (current — SharedPriceStream):
──────────────────────────────────────────
  ONE KiteTicker connection for ALL active broker accounts.

  KiteTicker is a market data feed — prices are public (NIFTY50 LTP is the
  same for everyone). There is no need to run N connections for N users.
  Any connected user's access_token is sufficient for KiteTicker auth.

  SharedPriceStream picks any valid access_token from the DB, creates one
  ZerodhaTicker, and subscribes to the union of all users' open position
  instruments. When a tick arrives, ConnectionManager.broadcast_price()
  already fans it out to every frontend WebSocket subscribed to that
  instrument — no per-user routing needed.

  ZerodhaTicker (ONE, shared)
    ↓ on_ticks → Redis LTP cache (ltp:{token}, TTL=2s)
    ↓ on_ticks → notify_price_update(symbol, price_data)
  ConnectionManager.broadcast_price(instrument)
    ↓ fans out to all account_id WebSockets subscribed to that instrument
  Frontend WebSocket (per connected browser tab)

  Token expiry: Zerodha access_tokens expire at 6 AM daily.
  On noreconnect (max retries exceeded), SharedPriceStream picks a new
  token from DB and rebuilds the ticker transparently.

  No Zerodha partnership required. No special API key setup required.
  Works with the existing per-user OAuth flow (each user still authenticates
  with their own credentials — we just borrow any one token for market data).

Migration from PerUserPriceStream (legacy):
──────────────────────────────────────────
  Already done. The singleton at the bottom of this file is SharedPriceStream.
  PerUserPriceStream is kept for rollback — switch the last line to roll back.
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

# KiteTicker runs on Twisted's GLOBAL reactor, which can be started exactly ONCE
# per process (a second start raises twisted ReactorNotRestartable and kills the
# thread). So we start the reactor once and NEVER rebuild the ticker in-process:
# dropped connections self-heal via KiteTicker's own reconnect on the same reactor;
# a new market-data token only takes effect on a PROCESS restart.
_REACTOR_STARTED = False


# ─────────────────────────────────────────────────────────────────────────────
# Abstract interface — the only contract callers depend on
# ─────────────────────────────────────────────────────────────────────────────

class PriceStreamProvider(ABC):
    """
    Interface for live price streaming.

    SharedPriceStream:  one KiteTicker for all accounts (current).
    PerUserPriceStream: one KiteTicker per account (legacy, kept for rollback).
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
# Shared helper — used by both stream implementations
# ─────────────────────────────────────────────────────────────────────────────

async def _get_open_position_tokens(
    broker_account_id: UUID, db
) -> Dict[int, str]:
    """
    Return {instrument_token: tradingsymbol} for all open positions of an account.

    The tradingsymbol is the broadcast key: ConnectionManager subscriptions
    store tradingsymbol strings, so price ticks must broadcast by symbol.
    Kite MODE_LTP ticks only return instrument_token — callers store this
    mapping in ZerodhaTicker._token_to_symbol so _on_ticks can resolve it.
    """
    from app.models.position import Position
    from app.models.instrument import Instrument
    from sqlalchemy import select, and_

    pos_result = await db.execute(
        select(Position.tradingsymbol, Position.instrument_token).where(
            and_(
                Position.broker_account_id == broker_account_id,
                Position.total_quantity != 0,
            )
        )
    )
    rows = pos_result.all()

    token_symbol_map: Dict[int, str] = {}
    symbols_missing_token = []

    for tradingsymbol, instrument_token in rows:
        if instrument_token:
            token_symbol_map[int(instrument_token)] = tradingsymbol
        else:
            symbols_missing_token.append(tradingsymbol)

    # Fallback: look up tokens from instruments table when positions lack them
    if symbols_missing_token:
        inst_result = await db.execute(
            select(Instrument.tradingsymbol, Instrument.instrument_token).where(
                Instrument.tradingsymbol.in_(symbols_missing_token)
            )
        )
        for sym, token in inst_result.all():
            if token:
                token_symbol_map[int(token)] = sym

    return token_symbol_map


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
    - on_noreconnect_callback: async callable fired when KiteTicker exhausts
      reconnect attempts (e.g. expired token). SharedPriceStream uses this
      to rebuild the ticker with a fresh token.
    """

    def __init__(
        self,
        api_key: str,
        access_token: str,
        broker_account_id,          # UUID or str label — used for logging only
        on_tick_callback,           # async callable(tradingsymbol: str, price_data: dict)
        on_noreconnect_callback=None,   # async callable() — fired on max reconnects exceeded
    ):
        self.api_key = api_key
        self.access_token = access_token
        self.broker_account_id = broker_account_id
        self.on_tick_callback = on_tick_callback
        self.on_noreconnect_callback = on_noreconnect_callback

        self.kws = None
        self.subscribed_tokens: Set[int] = set()
        self._token_to_symbol: Dict[int, str] = {}     # instrument_token → tradingsymbol
        self._connected = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._last_tick_times: Dict[str, float] = {}   # symbol → monotonic timestamp

    async def connect(self) -> None:
        """Connect to Kite WebSocket in a background thread."""
        try:
            from kiteconnect import KiteTicker
        except ImportError:
            logger.warning(
                "[ticker] kiteconnect not installed — price streaming disabled."
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

        # Guard: the Twisted reactor can only be started once per process. If it was
        # already started (by an earlier ticker), do NOT start a second one — that
        # raises ReactorNotRestartable and crashes the thread. The existing ticker
        # keeps streaming; picking up a new token needs a process restart.
        global _REACTOR_STARTED
        if _REACTOR_STARTED:
            logger.error(
                f"[ticker:{self.broker_account_id}] Twisted reactor already running in "
                "this process — refusing to start a second KiteTicker connection "
                "(ReactorNotRestartable). A new market-data token requires a process restart."
            )
            return

        # threaded=True: KiteTicker runs its own event loop in a daemon thread.
        await self._loop.run_in_executor(None, lambda: self.kws.connect(threaded=True))
        _REACTOR_STARTED = True
        logger.info(f"[ticker:{self.broker_account_id}] KiteTicker thread started.")

    # ── KiteTicker callbacks (called from KiteTicker thread) ──────────────────

    def _on_connect(self, ws, response):
        self._connected = True
        logger.info(f"[ticker:{self.broker_account_id}] Connected to Kite WebSocket.")

        # Resubscribe after reconnect (tokens preserved across reconnects).
        if self.subscribed_tokens:
            tokens = list(self.subscribed_tokens)
            ws.subscribe(tokens)
            ws.set_mode(ws.MODE_LTP, tokens)   # LTP = lightest mode

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

        ltp_updates: dict[int, str] = {}
        ws_updates: list[tuple[str, dict]] = []

        for tick in ticks:
            instrument_token = tick.get("instrument_token")
            symbol = (
                self._token_to_symbol.get(instrument_token)
                or tick.get("tradingsymbol")
                or str(instrument_token)
            )
            last_price = tick.get("last_price")

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

            if last_price is not None and instrument_token is not None:
                ltp_updates[instrument_token] = str(last_price)

            if self.on_tick_callback:
                ws_updates.append((symbol, price_data))

        # 1. Batch-write all LTP prices in a single Redis pipeline.
        if ltp_updates:
            try:
                from app.core.redis_pool import get_sync_redis
                r = get_sync_redis()
                pipe = r.pipeline(transaction=False)
                for token, price in ltp_updates.items():
                    pipe.set(f"ltp:{token}", price, ex=2)
                pipe.execute()
            except Exception:
                pass

        # 2. Broadcast to frontend via WebSocket (schedule on asyncio loop)
        for symbol, price_data in ws_updates:
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
            "Token likely expired."
        )
        self._connected = False
        if self.on_noreconnect_callback and self._loop:
            asyncio.run_coroutine_threadsafe(
                self.on_noreconnect_callback(),
                self._loop,
            )

    # ── Subscription management ───────────────────────────────────────────────

    def subscribe(self, token_symbol_map: Dict[int, str]) -> None:
        """
        Subscribe to instrument tokens.

        Args:
            token_symbol_map: {instrument_token → tradingsymbol}.
                              tradingsymbol is the broadcast key — frontend
                              looks up prices by position.tradingsymbol.
                              Kite MODE_LTP ticks only contain token, so we
                              store this map to resolve symbol in _on_ticks.
        """
        new_tokens = [t for t in token_symbol_map if t not in self.subscribed_tokens]
        if not new_tokens:
            return

        self._token_to_symbol.update(token_symbol_map)
        self.subscribed_tokens.update(new_tokens)
        if self.kws and self._connected:
            self.kws.subscribe(new_tokens)
            self.kws.set_mode(self.kws.MODE_LTP, new_tokens)
            logger.info(
                f"[ticker:{self.broker_account_id}] Subscribed to {len(new_tokens)} new tokens "
                f"(total: {len(self.subscribed_tokens)})"
            )

    def unsubscribe(self, tokens: list) -> None:
        """Unsubscribe from instrument tokens."""
        self.subscribed_tokens -= set(tokens)
        for t in tokens:
            self._token_to_symbol.pop(t, None)
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
# SharedPriceStream — ONE KiteTicker for all users (current implementation)
# ─────────────────────────────────────────────────────────────────────────────

class SharedPriceStream(PriceStreamProvider):
    """
    ONE KiteTicker connection shared across all broker accounts.

    Does NOT require Zerodha partnership or a dedicated service account.
    Uses any currently-connected user's access_token for KiteTicker auth —
    the token authenticates the WebSocket; the market data itself is public.

    When the token expires (daily at 6 AM), on_noreconnect fires and we
    pick a fresh token from the DB automatically.

    Scale characteristics:
    - 1 outbound WebSocket to Zerodha (vs N in PerUserPriceStream)
    - 1 copy of each instrument's tick data (vs N duplicate copies)
    - 1000 users holding NIFTY50 → still 1 subscription, 1 tick/second
    - Max 3000 instruments per KiteTicker connection (F&O universe fits in 1-3)
    """

    def __init__(self):
        self._ticker: Optional[ZerodhaTicker] = None
        # Serializes ticker creation/teardown only
        self._ticker_lock = asyncio.Lock()
        # Serializes the registration dicts
        self._reg_lock = asyncio.Lock()

        # account_id (str) → set of instrument_tokens subscribed for that account
        self._account_tokens: Dict[str, Set[int]] = {}
        # instrument_token → set of account_ids that need this token (reference count)
        self._token_holders: Dict[int, Set[str]] = {}
        # instrument_token → tradingsymbol (to resubscribe on ticker rebuild)
        self._token_symbol_map: Dict[int, str] = {}

    async def _pick_access_token(self, db) -> Optional[tuple]:
        """
        Return (access_token, api_key, label) for the market data connection.

        Priority:
          1. Dedicated market-data account (ZERODHA_MD_* in .env) — production grade.
             Token is pre-refreshed daily at 8:45 AM IST by the Celery beat task and
             stored in Redis. Never tied to any user's session.
          2. Any connected user's token — fallback for dev/early-stage use when
             ZERODHA_MD_* credentials are not configured.

        Returns (access_token: str, api_key: str, label: str) or None.
        """
        from app.core.config import settings

        # Priority 1: dedicated market-data account
        if settings.ZERODHA_MD_API_KEY:
            from app.services.zerodha_auth_service import (
                get_cached_market_data_token,
                refresh_market_data_token,
            )
            token = get_cached_market_data_token()
            if not token:
                # Cache miss (first run or Redis restart) — generate now synchronously
                logger.info("[shared_ticker] No cached MD token — refreshing now.")
                import asyncio
                token = await asyncio.get_event_loop().run_in_executor(
                    None, refresh_market_data_token
                )
            if token:
                return token, settings.ZERODHA_MD_API_KEY, "dedicated-md-account"

            # Configured but no token → the dedicated feed is DOWN (refresh/TOTP
            # failed). Do not silently borrow a customer's token without flagging it:
            # surface a loud error + metric so the admin watchdog alerts on it.
            logger.error(
                "[shared_ticker] ZERODHA_MD_* is configured but no market-data token "
                "is available — the dedicated feed is DOWN, degrading to a user token. "
                "Check the 8:45 AM refresh task and the TOTP secret."
            )
            try:
                from app.core import metrics
                metrics.incr("md_token_unavailable")
            except Exception:
                pass

        # Priority 2: fallback — any connected user's token.
        #
        # CRITICAL: KiteTicker authenticates with a (api_key, access_token) PAIR.
        # A token minted under one KiteConnect app (api_key) does NOT authenticate
        # against a different api_key. Accounts connected via the per-user
        # setup-credentials flow hold tokens issued under THEIR OWN api_key, not
        # the global ZERODHA_API_KEY. We must therefore pair each token with the
        # api_key stored on that account (BrokerAccount.api_key), falling back to
        # the global key only for legacy rows where api_key was never recorded.
        from app.models.broker_account import BrokerAccount
        from sqlalchemy import select, and_

        result = await db.execute(
            select(BrokerAccount).where(
                and_(
                    BrokerAccount.status == "connected",
                    BrokerAccount.token_revoked_at.is_(None),
                    BrokerAccount.access_token.isnot(None),
                )
            ).order_by(BrokerAccount.api_key.isnot(None).desc(), BrokerAccount.connected_at.desc())
        )
        accounts = result.scalars().all()
        if not accounts:
            logger.warning(
                "[shared_ticker] No ZERODHA_MD_* credentials and no connected users — "
                "ticker not started. Configure ZERODHA_MD_* in .env for production use."
            )
            return None

        for account in accounts:
            api_key = account.api_key or settings.ZERODHA_API_KEY
            if not api_key:
                continue
            try:
                token = account.decrypt_token(account.access_token)
            except ValueError as e:
                logger.warning(f"[shared_ticker] User token decrypt failed for {account.id}: {e}")
                continue
            return token, api_key, f"user-fallback:{account.id}"

        logger.warning("[shared_ticker] No connected account yielded a usable (api_key, token) pair.")
        return None

    async def _build_ticker(self, db) -> Optional[ZerodhaTicker]:
        """
        Create and connect a new ZerodhaTicker.
        Uses dedicated market-data credentials when available; falls back to any user token.
        Resubscribes all known instruments immediately after connect.
        Caller must hold _ticker_lock.
        """
        from app.api.websocket import notify_price_update

        picked = await self._pick_access_token(db)
        if not picked:
            return None

        access_token, api_key, label = picked

        if not api_key:
            logger.warning("[shared_ticker] No api_key available — streaming disabled.")
            return None

        ticker = ZerodhaTicker(
            api_key=api_key,
            access_token=access_token,
            broker_account_id=label,   # str label for logging, not a real UUID
            on_tick_callback=self.broadcast_ltp,
            on_noreconnect_callback=self._on_ticker_noreconnect,
        )
        await ticker.connect()

        # Resubscribe all instruments from previous session (after server restart
        # or token rebuild — registry is already populated).
        async with self._reg_lock:
            if self._token_symbol_map:
                ticker.subscribe(dict(self._token_symbol_map))

        logger.info(
            f"[shared_ticker] Built ticker via {label}. "
            f"Subscribed to {len(self._token_symbol_map)} instruments."
        )
        return ticker

    async def broadcast_ltp(self, symbol: str, price_data: dict) -> None:
        """Fan-out a KiteTicker tick to all WebSocket clients holding this instrument."""
        from app.api.websocket import manager

        token = price_data.get("instrument_token")
        if token is None:
            return

        # Snapshot the holder set — asyncio is single-threaded so this is safe
        # between awaits, and we only hold a list reference after the snapshot.
        account_ids = list(self._token_holders.get(token, set()))
        if not account_ids:
            return

        msg = {
            "type": "ltp_update",
            "data": {
                "symbol": symbol,
                "last_price": price_data.get("last_price"),
                "instrument_token": token,
            },
        }
        for account_id in account_ids:
            await manager.send_to_account(account_id, msg)

    async def _on_ticker_noreconnect(self) -> None:
        """
        Fired when KiteTicker exhausts reconnect attempts (token expired / invalid).

        We CANNOT rebuild the ticker here: KiteTicker runs on Twisted's global reactor,
        which cannot be restarted in-process (ReactorNotRestartable). A fresh token only
        takes effect after a PROCESS restart. In production the daily 08:45 refresh writes
        a valid token to Redis before market open, and the process (Fly/supervisor) picks
        it up on its next start; between refreshes KiteTicker's own reconnect keeps the
        connection alive. In dev with no valid market-data token this simply stays down —
        expected, not a crash.
        """
        logger.error(
            "[shared_ticker] Ticker exhausted reconnects (token expired/invalid). "
            "Cannot rebuild in-process (Twisted reactor is not restartable) — a new token "
            "needs a PROCESS restart. Set ZERODHA_MD_* for a durable auto-refreshed feed."
        )
        try:
            from app.core import metrics
            metrics.incr("md_token_unavailable")
        except Exception:
            pass

    async def _ensure_ticker(self, db) -> Optional[ZerodhaTicker]:
        """
        Return existing connected ticker, or build a new one.
        Caller must NOT hold _ticker_lock.
        """
        async with self._ticker_lock:
            # NEVER rebuild an existing ticker: KiteTicker's Twisted reactor cannot be
            # restarted in-process (ReactorNotRestartable). If a ticker object exists —
            # even if it is not currently connected (e.g. mid-reconnect, or a dev token
            # that 403s) — reuse it. KiteTicker auto-reconnects on the same reactor; new
            # subscriptions are queued and applied on (re)connect via _on_connect.
            if self._ticker is not None:
                return self._ticker
            self._ticker = await self._build_ticker(db)
            return self._ticker

    async def start_account(self, broker_account_id: UUID, db) -> None:
        """
        Register this account's open positions with the shared ticker.
        Creates the shared ticker if it doesn't exist yet.
        Safe to call multiple times (idempotent).
        """
        await self._ensure_ticker(db)

        token_symbol_map = await _get_open_position_tokens(broker_account_id, db)
        if not token_symbol_map:
            return

        account_id_str = str(broker_account_id)

        async with self._reg_lock:
            acct_tokens = self._account_tokens.setdefault(account_id_str, set())
            for token, symbol in token_symbol_map.items():
                acct_tokens.add(token)
                self._token_holders.setdefault(token, set()).add(account_id_str)
                self._token_symbol_map[token] = symbol

            if self._ticker:
                self._ticker.subscribe(token_symbol_map)

    async def refresh_subscriptions(self, broker_account_id: UUID, db) -> None:
        """Re-check positions and subscribe to newly opened instruments."""
        await self.start_account(broker_account_id, db)

    async def stop_account(self, broker_account_id: UUID) -> None:
        """
        Remove this account's subscriptions.
        Instruments with no remaining holders are unsubscribed from KiteTicker.
        The shared ticker itself keeps running for other accounts.
        """
        account_id_str = str(broker_account_id)

        async with self._reg_lock:
            tokens = self._account_tokens.pop(account_id_str, set())

            orphaned = []
            for token in tokens:
                holders = self._token_holders.get(token, set())
                holders.discard(account_id_str)
                if not holders:
                    self._token_holders.pop(token, None)
                    self._token_symbol_map.pop(token, None)
                    orphaned.append(token)

            if orphaned and self._ticker:
                self._ticker.unsubscribe(orphaned)
                logger.info(
                    f"[shared_ticker] Unsubscribed {len(orphaned)} instruments "
                    f"no longer held by any account."
                )

    async def restart_all(self, db) -> None:
        """
        On server startup: rebuild the shared ticker and resubscribe all accounts
        that have open positions. Recovers from server restarts during market hours.
        """
        from app.models.broker_account import BrokerAccount
        from app.models.position import Position
        from sqlalchemy import select, and_

        result = await db.execute(
            select(BrokerAccount.id).where(
                and_(
                    BrokerAccount.status == "connected",
                    BrokerAccount.token_revoked_at.is_(None),
                    BrokerAccount.access_token.isnot(None),
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
            logger.info("[shared_ticker] No active accounts with open positions on startup.")
            return

        logger.info(f"[shared_ticker] Registering {len(account_ids)} account(s) on startup.")
        for account_id in account_ids:
            try:
                await self.start_account(account_id, db)
            except Exception as e:
                logger.error(f"[shared_ticker] Failed to register {account_id}: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# PerUserPriceStream — legacy (kept for rollback)
# To roll back: change last line to `price_stream = PerUserPriceStream()`
# ─────────────────────────────────────────────────────────────────────────────

class PerUserPriceStream(PriceStreamProvider):
    """
    One KiteTicker connection per active broker account.
    LEGACY — replaced by SharedPriceStream. Kept for rollback.
    Problem: N users → N KiteTicker connections → N copies of same tick data.
    """

    def __init__(self):
        self._tickers: Dict[str, ZerodhaTicker] = {}
        self._lock = asyncio.Lock()

    async def start_account(self, broker_account_id: UUID, db) -> None:
        from app.core.config import settings
        from app.models.broker_account import BrokerAccount

        account_id_str = str(broker_account_id)

        async with self._lock:
            if account_id_str not in self._tickers:
                account = await db.get(BrokerAccount, broker_account_id)
                if not account or not account.access_token or account.token_revoked_at:
                    logger.warning(
                        f"[price_stream] Cannot start account {broker_account_id}: no valid token."
                    )
                    return

                try:
                    access_token = account.decrypt_token(account.access_token)
                except ValueError as e:
                    logger.error(f"[price_stream] Token decrypt failed for {broker_account_id}: {e}")
                    return

                if not settings.ZERODHA_API_KEY:
                    logger.warning("[price_stream] ZERODHA_API_KEY not set — streaming disabled.")
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

        await self.refresh_subscriptions(broker_account_id, db)

    async def refresh_subscriptions(self, broker_account_id: UUID, db) -> None:
        account_id_str = str(broker_account_id)
        ticker = self._tickers.get(account_id_str)
        if not ticker:
            return
        token_symbol_map = await _get_open_position_tokens(broker_account_id, db)
        if token_symbol_map:
            ticker.subscribe(token_symbol_map)

    async def stop_account(self, broker_account_id: UUID) -> None:
        account_id_str = str(broker_account_id)
        async with self._lock:
            ticker = self._tickers.pop(account_id_str, None)
        if ticker:
            ticker.stop()

    async def restart_all(self, db) -> None:
        from app.models.broker_account import BrokerAccount
        from app.models.position import Position
        from sqlalchemy import select, and_

        result = await db.execute(
            select(BrokerAccount.id).where(
                and_(
                    BrokerAccount.status == "connected",
                    BrokerAccount.token_revoked_at.is_(None),
                    BrokerAccount.access_token.isnot(None),
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
        for account_id in result.scalars().all():
            try:
                await self.start_account(account_id, db)
            except Exception as e:
                logger.error(f"[price_stream] Failed to restart account {account_id}: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Singleton — the only object the rest of the app imports
# ─────────────────────────────────────────────────────────────────────────────

# ROLLBACK: swap SharedPriceStream() → PerUserPriceStream() to revert.
#
# MULTI-PROCESS / HORIZONTAL SCALING NOTE
# ───────────────────────────────────────
# `price_stream` is a per-PROCESS singleton. Each FastAPI worker/replica builds its
# OWN KiteTicker covering the instruments of the browsers connected to THAT process,
# and delivers ticks to THAT process's local WebSocket clients (broadcast_ltp →
# ConnectionManager). So LTP delivery is self-contained per process — no cross-process
# relay is required, and running multiple workers is correct for delivery.
#
# The binding constraint is Zerodha's limit of ~3 KiteTicker connections per api_key.
# With the dedicated market-data account (ZERODHA_MD_*), every process authenticates
# the ticker with the SAME md api_key, so you may run at most ~3 FastAPI processes
# before hitting that cap. Beyond that, move market data to a single dedicated process
# that owns the ticker and relays ticks to web workers via Redis pub/sub (documented
# in docs/architecture/KITETICKER_SHARED_POOL.md §4). Do that at the scale where >3
# web processes are actually needed — not before.
price_stream: PriceStreamProvider = SharedPriceStream()


def get_cached_ltp(instrument_token: int) -> Optional[float]:
    """
    Read last traded price from Redis cache.
    Returns None if cache miss (price not yet received or TTL expired).

    TTL is 2 seconds — treat as unavailable if stale.
    Used by position monitor and P&L calculations during market hours.
    """
    try:
        from app.core.redis_pool import get_sync_redis
        r = get_sync_redis()
        val = r.get(f"ltp:{instrument_token}")
        return float(val) if val is not None else None
    except Exception:
        return None
