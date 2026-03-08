"""
Price Streaming Service

Connects to Zerodha Kite Ticker WebSocket for live prices.
Broadcasts updates to connected clients via our WebSocket.

Architecture:
- Single shared connection to Zerodha per active token
- Multiple clients can subscribe to instruments
- Rate limiting: 1 update per second per instrument
- Automatic reconnection on disconnect
"""

import asyncio
import logging
from typing import Dict, Set, Optional, Callable
from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.core.config import settings

logger = logging.getLogger(__name__)

# Rate limiting: Track last update time per instrument
last_update_times: Dict[str, datetime] = {}
MIN_UPDATE_INTERVAL = timedelta(seconds=1)  # Max 1 update per second


class ZerodhaTicker:
    """
    Wrapper for Zerodha Kite Ticker WebSocket.

    Note: kiteconnect library uses a sync WebSocket.
    This class provides async interface for our FastAPI app.
    """

    def __init__(self, api_key: str, access_token: str):
        self.api_key = api_key
        self.access_token = access_token
        self.kws = None
        self.subscribed_tokens: Set[int] = set()
        self.on_tick_callback: Optional[Callable] = None
        self._connected = False
        self._running = False

    async def connect(self):
        """Initialize and connect to Zerodha WebSocket."""
        try:
            from kiteconnect import KiteTicker

            self.kws = KiteTicker(self.api_key, self.access_token)

            # Set up callbacks
            self.kws.on_ticks = self._on_ticks
            self.kws.on_connect = self._on_connect
            self.kws.on_close = self._on_close
            self.kws.on_error = self._on_error

            # Connect in a separate thread (kiteconnect is sync)
            self._running = True
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.kws.connect, True)

        except ImportError:
            logger.warning("kiteconnect not installed. Using mock price stream.")
            self._connected = True
        except Exception as e:
            logger.error(f"Failed to connect to Zerodha ticker: {e}")
            raise

    def _on_connect(self, ws, response):
        """Called when WebSocket connects."""
        logger.info("Connected to Zerodha ticker")
        self._connected = True

        # Resubscribe to previously subscribed tokens
        if self.subscribed_tokens:
            self.kws.subscribe(list(self.subscribed_tokens))
            self.kws.set_mode(self.kws.MODE_FULL, list(self.subscribed_tokens))

    def _on_close(self, ws, code, reason):
        """Called when WebSocket closes."""
        logger.warning(f"Zerodha ticker closed: {code} - {reason}")
        self._connected = False

    def _on_error(self, ws, code, reason):
        """Called on WebSocket error."""
        logger.error(f"Zerodha ticker error: {code} - {reason}")

    def _on_ticks(self, ws, ticks):
        """
        Called when price ticks arrive.
        Rate limited and forwarded to callback.
        """
        now = datetime.now(timezone.utc)

        for tick in ticks:
            instrument_token = tick.get("instrument_token")
            tradingsymbol = tick.get("tradingsymbol", str(instrument_token))

            # Rate limiting
            last_update = last_update_times.get(tradingsymbol)
            if last_update and (now - last_update) < MIN_UPDATE_INTERVAL:
                continue

            last_update_times[tradingsymbol] = now

            # Format tick data
            price_data = {
                "last_price": tick.get("last_price"),
                "open": tick.get("ohlc", {}).get("open"),
                "high": tick.get("ohlc", {}).get("high"),
                "low": tick.get("ohlc", {}).get("low"),
                "close": tick.get("ohlc", {}).get("close"),
                "volume": tick.get("volume"),
                "change": tick.get("change"),
                "change_percent": tick.get("change_percent"),
                "bid": tick.get("depth", {}).get("buy", [{}])[0].get("price"),
                "ask": tick.get("depth", {}).get("sell", [{}])[0].get("price"),
                "oi": tick.get("oi"),
                "oi_change": tick.get("oi_day_high", 0) - tick.get("oi_day_low", 0),
            }

            # Call callback if set
            if self.on_tick_callback:
                asyncio.create_task(
                    self.on_tick_callback(tradingsymbol, price_data)
                )

    async def subscribe(self, instrument_tokens: list):
        """Subscribe to instrument tokens."""
        self.subscribed_tokens.update(instrument_tokens)

        if self.kws and self._connected:
            self.kws.subscribe(instrument_tokens)
            self.kws.set_mode(self.kws.MODE_FULL, instrument_tokens)
            logger.info(f"Subscribed to {len(instrument_tokens)} instruments")

    async def unsubscribe(self, instrument_tokens: list):
        """Unsubscribe from instrument tokens."""
        self.subscribed_tokens -= set(instrument_tokens)

        if self.kws and self._connected:
            self.kws.unsubscribe(instrument_tokens)

    async def close(self):
        """Close the WebSocket connection."""
        self._running = False
        if self.kws:
            self.kws.close()


class PriceStreamManager:
    """
    Manages price streaming connections for multiple broker accounts.

    One Zerodha connection per access_token (can serve multiple clients).
    """

    def __init__(self):
        # token_hash -> ZerodhaTicker
        self.tickers: Dict[str, ZerodhaTicker] = {}
        # tradingsymbol -> instrument_token mapping
        self.symbol_to_token: Dict[str, int] = {}
        # Lock for thread safety
        self._lock = asyncio.Lock()

    async def get_or_create_ticker(self, access_token: str) -> ZerodhaTicker:
        """Get existing ticker or create new one for access token."""
        token_hash = hash(access_token)

        async with self._lock:
            if token_hash not in self.tickers:
                ticker = ZerodhaTicker(
                    api_key=settings.ZERODHA_API_KEY,
                    access_token=access_token
                )

                # Set callback to broadcast prices
                from app.api.websocket import notify_price_update
                ticker.on_tick_callback = notify_price_update

                await ticker.connect()
                self.tickers[token_hash] = ticker

            return self.tickers[token_hash]

    async def subscribe_symbols(
        self,
        access_token: str,
        symbols: Set[str],
        db
    ):
        """
        Subscribe to symbols for an account.
        Resolves symbols to instrument tokens.
        """
        ticker = await self.get_or_create_ticker(access_token)

        # Get instrument tokens for symbols
        tokens = await self._resolve_instrument_tokens(symbols, db)

        if tokens:
            await ticker.subscribe(list(tokens))

    async def _resolve_instrument_tokens(self, symbols: Set[str], db) -> Set[int]:
        """
        Resolve trading symbols to Zerodha instrument tokens.

        Uses cached mapping or fetches from instruments table or positions.
        """
        from app.models.instrument import Instrument
        from app.models.position import Position
        from sqlalchemy import select, or_

        tokens = set()
        symbols_to_lookup = set()

        # Check cache first
        for symbol in symbols:
            if symbol in self.symbol_to_token:
                tokens.add(self.symbol_to_token[symbol])
            else:
                symbols_to_lookup.add(symbol)

        if not symbols_to_lookup:
            return tokens

        # Try to find in instruments table
        result = await db.execute(
            select(Instrument.tradingsymbol, Instrument.instrument_token).where(
                Instrument.tradingsymbol.in_(symbols_to_lookup)
            )
        )
        instrument_rows = result.all()

        for tradingsymbol, instrument_token in instrument_rows:
            self.symbol_to_token[tradingsymbol] = instrument_token
            tokens.add(instrument_token)
            symbols_to_lookup.discard(tradingsymbol)

        # If still missing, try positions table (might have instrument_token)
        if symbols_to_lookup:
            result = await db.execute(
                select(Position.tradingsymbol, Position.instrument_token).where(
                    Position.tradingsymbol.in_(symbols_to_lookup),
                    Position.instrument_token.isnot(None)
                )
            )
            position_rows = result.all()

            for tradingsymbol, instrument_token in position_rows:
                if instrument_token:
                    self.symbol_to_token[tradingsymbol] = instrument_token
                    tokens.add(instrument_token)
                    symbols_to_lookup.discard(tradingsymbol)

        # Log any symbols we couldn't resolve
        if symbols_to_lookup:
            logger.warning(f"Could not resolve instrument tokens for: {symbols_to_lookup}")

        return tokens

    async def cleanup_ticker(self, access_token: str):
        """Clean up ticker when no longer needed."""
        token_hash = hash(access_token)

        async with self._lock:
            ticker = self.tickers.pop(token_hash, None)
            if ticker:
                await ticker.close()


# Global price stream manager
price_stream_manager = PriceStreamManager()


async def start_price_stream(broker_account_id: UUID, db):
    """
    Start price streaming for a broker account.

    Called when user connects to WebSocket and subscribes to positions.
    """
    from app.models.broker_account import BrokerAccount
    from app.models.position import Position
    from sqlalchemy import select

    # Get broker account with access token
    result = await db.execute(
        select(BrokerAccount).where(BrokerAccount.id == broker_account_id)
    )
    account = result.scalar_one_or_none()

    if not account or not account.access_token:
        logger.warning(f"No access token for account {broker_account_id}")
        return

    # Get open position symbols
    pos_result = await db.execute(
        select(Position.tradingsymbol).where(
            Position.broker_account_id == broker_account_id,
            Position.total_quantity != 0
        )
    )
    symbols = set(pos_result.scalars().all())

    if symbols:
        # Decrypt access token
        access_token = account.decrypt_token(account.access_token)

        await price_stream_manager.subscribe_symbols(
            access_token=access_token,
            symbols=symbols,
            db=db
        )
        logger.info(f"Started price stream for {len(symbols)} symbols")
