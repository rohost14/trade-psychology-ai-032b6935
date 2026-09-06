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
    ↓ on_ticks → Redis LTP cache (single hash `ltp:all`, one write per tick batch)
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
from typing import Any, Dict, Set, Optional
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


async def _refresh_risk_state(broker_account_id: UUID, db) -> None:
    """
    Reload the tick-path premium-loss state for one account.

    This is the ONLY moment the live premium check reads the database. It hangs
    off `refresh_subscriptions` deliberately rather than inventing a trigger:
    that already runs on a fill (via the event bus), on a manual sync and at
    startup, which is exactly the set of moments an account's open positions or
    rules can change. Failure is non-fatal — the price stream matters more than
    the risk state, and the next refresh will pick it up.
    """
    try:
        from app.tasks.position_monitor_tasks import rebuild_account_risk_state
        await rebuild_account_risk_state(broker_account_id, db)
    except Exception as e:
        logger.debug(f"[live_risk] state refresh skipped for {broker_account_id}: {e}")


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

        # Annotated: without it mypy infers the attribute's type as `None`
        # from this assignment alone, and then every `self.kws.on_*`
        # below is an attribute error on None - twelve findings across
        # the two stream services. `Any` rather than KiteTicker because
        # kiteconnect is an optional import guarded by ImportError.
        self.kws: Optional[Any] = None
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

        # 1. Write the whole batch as ONE hash write. This used to be one SET per
        # instrument inside a pipeline — a pipeline saves round-trips, not commands,
        # and a per-command Redis plan bills each one. See core/ltp_cache.py.
        if ltp_updates:
            try:
                from app.core.ltp_cache import write_batch
                from app.core.redis_pool import get_sync_redis
                write_batch(get_sync_redis(), ltp_updates)
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
            # Drop the tick-time entry with the token it belongs to. It is keyed by
            # SYMBOL, so it has to be resolved before _token_to_symbol forgets the
            # mapping — otherwise the entry is stranded until the ticker resets.
            symbol = self._token_to_symbol.pop(t, None)
            if symbol:
                self._last_tick_times.pop(symbol, None)
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

class AsyncKiteTicker:
    """
    aiohttp-based Kite market-data ticker. Runs entirely in the asyncio event loop —
    NO Twisted reactor — so it can reconnect with a FRESH token any time Zerodha rotates
    it (the KiteTicker ReactorNotRestartable problem is gone, and there is no login/restart
    ritual). Parses LTP-mode binary ticks and reuses the same Redis-LTP write + WS fan-out.

    token_provider: async callable returning (api_key, access_token) or None. Called on
    every (re)connect, so a fresh login is picked up automatically on the next reconnect.
    """
    _WS_ROOT = "wss://ws.kite.trade"

    def __init__(self, token_provider, on_tick_callback):
        self._token_provider = token_provider
        self.on_tick_callback = on_tick_callback
        self._token_to_symbol: Dict[int, str] = {}
        self.subscribed_tokens: Set[int] = set()
        self._last_tick_times: Dict[str, float] = {}
        self._ws = None
        self._task: Optional[asyncio.Task] = None
        self._stop = False
        self._connected = False

    async def start(self) -> None:
        self._stop = False
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run())

    async def _run(self) -> None:
        import aiohttp, struct, time
        backoff = 1
        while not self._stop:
            picked = await self._token_provider()
            if not picked:
                await asyncio.sleep(5)
                continue
            api_key, access_token = picked
            url = f"{self._WS_ROOT}?api_key={api_key}&access_token={access_token}"
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.ws_connect(url, timeout=10, heartbeat=30) as ws:
                        self._ws = ws
                        self._connected = True
                        backoff = 1
                        logger.info("[async_ticker] Connected to Kite WebSocket.")
                        if self.subscribed_tokens:
                            toks = list(self.subscribed_tokens)
                            await ws.send_json({"a": "subscribe", "v": toks})
                            await ws.send_json({"a": "mode", "v": ["ltp", toks]})
                        async for msg in ws:
                            if self._stop:
                                break
                            if msg.type == aiohttp.WSMsgType.BINARY:
                                await self._handle_binary(msg.data, struct, time)
                            elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                                break
            except Exception as e:
                logger.warning(f"[async_ticker] connection ended: {type(e).__name__}: {e}")
            self._connected = False
            self._ws = None
            if self._stop:
                break
            # Reconnect — the token_provider re-reads the CURRENT token, so a rotated /
            # freshly-logged-in token is picked up automatically here. No restart needed.
            await asyncio.sleep(min(backoff, 30))
            backoff = min(backoff * 2, 30)
        logger.info("[async_ticker] stopped.")

    async def _handle_binary(self, b, struct, time) -> None:
        if len(b) < 2:
            return
        npackets = struct.unpack(">H", b[0:2])[0]
        i = 2
        now = time.monotonic()
        ltp_updates: Dict[int, str] = {}
        for _ in range(npackets):
            if i + 2 > len(b):
                break
            plen = struct.unpack(">H", b[i:i + 2])[0]
            i += 2
            pkt = b[i:i + plen]
            i += plen
            if len(pkt) < 8:
                continue
            itok = struct.unpack(">I", pkt[0:4])[0]
            ltp = struct.unpack(">I", pkt[4:8])[0] / 100.0
            symbol = self._token_to_symbol.get(itok, str(itok))
            last = self._last_tick_times.get(symbol, 0.0)
            if (now - last) < _TICK_THROTTLE_SECONDS:
                continue
            self._last_tick_times[symbol] = now
            ltp_updates[itok] = str(ltp)
            if self.on_tick_callback:
                try:
                    await self.on_tick_callback(symbol, {"last_price": ltp, "instrument_token": itok})
                except Exception:
                    pass
        # One hash write for the whole batch — see core/ltp_cache.py.
        if ltp_updates:
            try:
                from app.core.ltp_cache import write_batch
                from app.core.redis_pool import get_sync_redis
                write_batch(get_sync_redis(), ltp_updates)
            except Exception:
                pass

            # Premium-loss risk state (Pattern #8). Pure in-memory evaluation -
            # no database, no Redis, no network - so it is safe to run on every
            # tick batch. It returns only CROSSINGS, which are rare, and the
            # alert write is handed to a separate task so nothing that touches
            # the database can ever block the price stream.
            try:
                from app.services.live_risk_state import live_risk_state
                crossings = live_risk_state.evaluate_batch(
                    {t: float(p) for t, p in ltp_updates.items()}
                )
                if crossings:
                    from app.tasks.position_monitor_tasks import dispatch_risk_crossings
                    asyncio.create_task(dispatch_risk_crossings(crossings))
            except Exception:
                pass

    async def subscribe_async(self, token_symbol_map: Dict[int, str]) -> None:
        for t, s in token_symbol_map.items():
            self._token_to_symbol[t] = s
            self.subscribed_tokens.add(t)
        if self._ws is not None and self._connected:
            toks = list(token_symbol_map)
            try:
                await self._ws.send_json({"a": "subscribe", "v": toks})
                await self._ws.send_json({"a": "mode", "v": ["ltp", toks]})
            except Exception:
                pass

    async def unsubscribe_async(self, tokens) -> None:
        toks = list(tokens)
        for t in toks:
            self.subscribed_tokens.discard(t)
            # Same ordering as the sync path: resolve the symbol before dropping
            # the mapping, or the symbol-keyed tick-time entry is stranded.
            symbol = self._token_to_symbol.pop(t, None)
            if symbol:
                self._last_tick_times.pop(symbol, None)
        if self._ws is not None and self._connected and toks:
            try:
                await self._ws.send_json({"a": "unsubscribe", "v": toks})
            except Exception:
                pass

    async def stop_async(self) -> None:
        self._stop = True
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
        if self._task is not None:
            self._task.cancel()


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
        # AsyncKiteTicker, not ZerodhaTicker: `_build_ticker` constructs an
        # AsyncKiteTicker and nothing else is ever assigned here.
        # ZerodhaTicker is PerUserPriceStream's, and it has no
        # subscribe_async/unsubscribe_async - which is what the wrong
        # annotation made every call to those look like an error.
        self._ticker: Optional["AsyncKiteTicker"] = None
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

    async def _build_ticker(self, db) -> Optional["AsyncKiteTicker"]:
        """
        Create and start the aiohttp AsyncKiteTicker.
        The ticker's token_provider re-reads the CURRENT token on every (re)connect, so
        token rotation / a fresh login is picked up automatically with no reactor restart
        and no login/restart ritual. Resubscribes all known instruments after connect.
        Caller must hold _ticker_lock.
        """
        ticker = AsyncKiteTicker(
            token_provider=self._provide_token,
            on_tick_callback=self.broadcast_ltp,
        )
        await ticker.start()

        # Resubscribe all instruments from the registry (after a server restart the
        # registry is repopulated by restart_all before/around this build).
        async with self._reg_lock:
            if self._token_symbol_map:
                await ticker.subscribe_async(dict(self._token_symbol_map))

        logger.info(
            f"[shared_ticker] AsyncKiteTicker started. "
            f"Subscribed to {len(self._token_symbol_map)} instruments."
        )
        return ticker

    async def _provide_token(self):
        """Token provider for AsyncKiteTicker — returns (api_key, access_token) or None.
        Called on every (re)connect with a fresh DB session, so the ticker always uses
        the latest token (the fix for daily token rotation / re-login)."""
        from app.core.database import SessionLocal
        try:
            async with SessionLocal() as db:
                picked = await self._pick_access_token(db)
            if not picked:
                return None
            access_token, api_key, _label = picked
            if not api_key or not access_token:
                return None
            return api_key, access_token
        except Exception as e:
            logger.warning(f"[shared_ticker] token provider failed: {e}")
            return None

    @staticmethod
    def _multi_instance() -> bool:
        try:
            from app.core.config import settings
            return bool(settings.PRICE_STREAM_MULTI_INSTANCE)
        except Exception:
            return False

    def _may_own_ticker(self) -> bool:
        """Single-instance: always. Multi-instance: only while holding the lease."""
        if not self._multi_instance():
            return True
        from app.services import ticker_lease
        return ticker_lease.is_owner()

    async def broadcast_ltp(self, symbol: str, price_data: dict) -> None:
        """
        Handle a tick produced by THIS process's ticker.

        Single instance: fan out locally, exactly as before.
        Multi-instance: publish to Redis so every instance can serve its own
        WebSocket clients — this process holds the ticker but not necessarily the
        clients. Publishing is fire-and-forget on purpose; a tick that misses its
        window is worthless, so there is nothing here worth retrying or storing.
        """
        token = price_data.get("instrument_token")
        if token is None:
            return

        if self._multi_instance():
            try:
                import json
                from app.core.redis_pool import get_async_redis
                from app.services.ticker_lease import TICK_CHANNEL

                r = await get_async_redis()
                await r.publish(TICK_CHANNEL, json.dumps({
                    "symbol": symbol,
                    "last_price": price_data.get("last_price"),
                    "instrument_token": token,
                }))
            except Exception as e:
                logger.debug(f"[shared_ticker] tick publish failed: {e}")
            return

        await self.deliver_ltp_locally(symbol, price_data.get("last_price"), token)

    async def deliver_ltp_locally(self, symbol: str, last_price, token: int) -> None:
        """
        Send a tick to this process's own WebSocket clients holding the instrument.

        Called directly by broadcast_ltp on a single instance, and by the pub/sub
        subscriber on every instance in multi-instance mode. The routing map
        (_token_holders) is local bookkeeping built when an account registers here,
        so each instance naturally reaches only its own clients.
        """
        from app.api.websocket import manager

        # Snapshot the holder set — asyncio is single-threaded so this is safe
        # between awaits, and we only hold a list reference after the snapshot.
        account_ids = list(self._token_holders.get(token, set()))
        if not account_ids:
            return

        msg = {
            "type": "ltp_update",
            "data": {
                "symbol": symbol,
                "last_price": last_price,
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

    async def _ensure_ticker(self, db) -> Optional["AsyncKiteTicker"]:
        """
        Return existing connected ticker, or build a new one.
        Caller must NOT hold _ticker_lock.

        In multi-instance mode only the lease holder opens a ticker. Everyone else
        returns None and gets its ticks from the pub/sub channel instead — two
        instances each running their own KiteTicker is the split brain this avoids.
        """
        if not self._may_own_ticker():
            return None

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
                await self._ticker.subscribe_async(token_symbol_map)

    async def refresh_subscriptions(self, broker_account_id: UUID, db) -> None:
        """Re-check positions and subscribe to newly opened instruments."""
        await self.start_account(broker_account_id, db)
        await _refresh_risk_state(broker_account_id, db)

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
                await self._ticker.unsubscribe_async(orphaned)
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
        await _refresh_risk_state(broker_account_id, db)

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
    Returns None if the price is missing or older than 2 seconds.

    Used by position monitor and P&L calculations during market hours. Staleness is
    now decided by a timestamp stored with the price rather than a per-key TTL — the
    cache is one hash so the whole batch costs a single write. Same semantics.
    """
    try:
        from app.core.ltp_cache import read
        from app.core.redis_pool import get_sync_redis
        return read(get_sync_redis(), instrument_token)
    except Exception:
        return None
