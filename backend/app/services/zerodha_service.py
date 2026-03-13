import hashlib
import httpx
import asyncio
import time
import csv
from io import StringIO
import logging
from functools import wraps
from typing import Dict, Any, List, Optional
from urllib.parse import urlencode
from app.core.config import settings
from app.services.broker_interface import BrokerInterface, BrokerType, BrokerFactory

logger = logging.getLogger(__name__)


# =============================================================================
# Custom Exceptions
# =============================================================================

class KiteAPIError(Exception):
    """Base exception for Kite API errors"""
    def __init__(self, message: str, status_code: int = None, error_type: str = None):
        self.message = message
        self.status_code = status_code
        self.error_type = error_type
        super().__init__(self.message)


class KiteRateLimitError(KiteAPIError):
    """Raised when API rate limit is exceeded"""
    pass


class KiteTokenExpiredError(KiteAPIError):
    """Raised when access token has expired"""
    pass


class KiteAuthError(KiteAPIError):
    """Raised for authentication failures"""
    pass


class KiteNetworkError(KiteAPIError):
    """Raised for network-related failures"""
    pass


# =============================================================================
# Rate Limiter
# =============================================================================

class RateLimiter:
    """
    Simple rate limiter for Kite API.
    Kite allows 3 requests/second.
    """
    def __init__(self, calls_per_second: float = 3.0):
        self.calls_per_second = calls_per_second
        self.min_interval = 1.0 / calls_per_second
        self.last_call_time = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self):
        """Wait if necessary to respect rate limit"""
        async with self._lock:
            now = time.time()
            elapsed = now - self.last_call_time
            if elapsed < self.min_interval:
                wait_time = self.min_interval - elapsed
                await asyncio.sleep(wait_time)
            self.last_call_time = time.time()


# Global rate limiter instance
_rate_limiter = RateLimiter(calls_per_second=3.0)


class ZerodhaClient(BrokerInterface):
    LOGIN_URL = "https://kite.zerodha.com/connect/login"
    TOKEN_URL = "https://api.kite.trade/session/token"
    BASE_URL = "https://api.kite.trade"

    def __init__(self):
        self.api_key = settings.ZERODHA_API_KEY
        self.api_secret = settings.ZERODHA_API_SECRET
        self.rate_limiter = _rate_limiter

    @property
    def broker_type(self) -> BrokerType:
        return BrokerType.ZERODHA

    @property
    def broker_name(self) -> str:
        return "Zerodha Kite"

    def _get_headers(self, access_token: str) -> Dict[str, str]:
        """Build authorization headers"""
        return {
            "Authorization": f"token {self.api_key}:{access_token}",
            "X-Kite-Version": "3"
        }

    def _handle_response(self, response: httpx.Response) -> Dict[str, Any]:
        """Handle Kite API response and raise appropriate errors"""
        try:
            data = response.json()
        except Exception:
            if response.status_code >= 400:
                raise KiteAPIError(
                    f"API error: {response.text[:200]}",
                    status_code=response.status_code
                )
            return {}

        if response.status_code == 429:
            raise KiteRateLimitError(
                "Rate limit exceeded. Please slow down.",
                status_code=429
            )

        if response.status_code == 403:
            error_type = data.get("error_type", "")
            message = data.get("message", "Authentication failed")

            if error_type == "TokenException":
                raise KiteTokenExpiredError(
                    "Access token has expired. Please reconnect.",
                    status_code=403,
                    error_type=error_type
                )
            raise KiteAuthError(message, status_code=403, error_type=error_type)

        if response.status_code >= 400:
            raise KiteAPIError(
                data.get("message", f"API error: {response.status_code}"),
                status_code=response.status_code,
                error_type=data.get("error_type")
            )

        return data

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create singleton httpx client."""
        if not hasattr(self, "_client") or self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client

    async def close(self):
        """Close the persistent client."""
        if hasattr(self, "_client") and self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _request(
        self,
        method: str,
        url: str,
        access_token: str = None,
        data: Dict = None,
        params=None,
        timeout: float = 10.0,
        broker_account_id=None,   # Optional — enables circuit breaker when provided
    ) -> Dict[str, Any]:
        """Make rate-limited API request using persistent client."""
        from app.services.circuit_breaker_service import circuit_breaker

        # Circuit breaker check — only when broker_account_id is provided
        if broker_account_id:
            allowed = await circuit_breaker.allow_request(broker_account_id)
            if not allowed:
                raise KiteAPIError(
                    "Kite API circuit breaker is OPEN — service temporarily degraded.",
                    status_code=503,
                    error_type="CircuitOpen",
                )

        await self.rate_limiter.acquire()

        headers = self._get_headers(access_token) if access_token else {"X-Kite-Version": "3"}
        client = await self._get_client()

        try:
            if method == "GET":
                response = await client.get(url, headers=headers, params=params, timeout=timeout)
            elif method == "POST":
                response = await client.post(url, data=data, headers=headers, timeout=timeout)
            elif method == "DELETE":
                response = await client.delete(url, headers=headers, timeout=timeout)
            else:
                raise ValueError(f"Unsupported method: {method}")

            result = self._handle_response(response)

            # Record success for circuit breaker
            if broker_account_id:
                await circuit_breaker.record_success(broker_account_id)

            return result

        except (KiteTokenExpiredError, KiteAuthError):
            # Auth errors are not infrastructure failures — don't trip the circuit
            raise
        except (httpx.TimeoutException, KiteNetworkError, KiteAPIError) as e:
            # Infrastructure failures — record for circuit breaker
            if broker_account_id:
                await circuit_breaker.record_failure(broker_account_id)

            if isinstance(e, httpx.TimeoutException):
                raise KiteNetworkError("Request timed out", status_code=408)
            raise
        except httpx.RequestError as e:
            if broker_account_id:
                await circuit_breaker.record_failure(broker_account_id)
            if isinstance(e, httpx.PoolTimeout):
                await self.close()
                self._client = httpx.AsyncClient(timeout=10.0)
                return await self._request(method, url, access_token, data, params, timeout,
                                           broker_account_id)
            raise KiteNetworkError(f"Network error: {str(e)}")
        



    def generate_login_url(self, redirect_uri: str, state: Optional[str] = None) -> str:
        """Constructs the login URL for OAuth flow."""
        params = {
            "v": "3",
            "api_key": self.api_key,
            "redirect_uri": redirect_uri
        }
        if state:
            params["state"] = state

        return f"{self.LOGIN_URL}?{urlencode(params)}"

    async def exchange_token(self, request_token: str) -> Dict[str, Any]:
        """
        Exchanges request_token for access_token.

        Returns dict with:
        - user_id: Kite user ID
        - access_token: Access token for API calls
        - refresh_token: Token for refreshing session (if available)
        """
        if not self.api_key or not self.api_secret:
            raise KiteAuthError("Zerodha API credentials not configured")

        checksum = hashlib.sha256(
            (self.api_key + request_token + self.api_secret).encode("utf-8")
        ).hexdigest()

        data = {
            "api_key": self.api_key,
            "request_token": request_token,
            "checksum": checksum
        }

        await self.rate_limiter.acquire()

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.TOKEN_URL,
                    data=data,
                    headers={"X-Kite-Version": "3"},
                    timeout=10.0
                )
                result = self._handle_response(response)

                if result.get("status") != "success":
                    raise KiteAuthError(f"Token exchange failed: {result.get('message')}")

                return result["data"]

            except httpx.HTTPError as e:
                logger.error(f"HTTP Error exchanging token: {e}")
                raise KiteNetworkError("Failed to connect to Zerodha")

    async def get_profile(self, access_token: str) -> Dict[str, Any]:
        """
        Fetches user profile.

        Returns:
        - user_id, user_name, user_shortname
        - email, user_type, broker
        - exchanges, products, order_types
        - avatar_url (if available)
        """
        url = f"{self.BASE_URL}/user/profile"
        result = await self._request("GET", url, access_token)
        return result.get("data", {})

    async def get_trades(self, access_token: str) -> List[Dict[str, Any]]:
        """
        Fetch executed trades from tradebook.

        Returns list of trades with fields:
        - trade_id, order_id, exchange_order_id
        - tradingsymbol, exchange, instrument_token
        - transaction_type, quantity, average_price
        - product, order_type, exchange_timestamp, fill_timestamp
        """
        url = f"{self.BASE_URL}/trades"
        logger.info(f"Fetching trades from Kite API")

        result = await self._request("GET", url, access_token)
        return result.get("data", [])

    async def get_positions(self, access_token: str) -> Dict[str, Any]:
        """
        Fetch current open positions.

        Returns dict with:
        - net: List of net positions
        - day: List of day positions (intraday)

        Each position contains:
        - tradingsymbol, exchange, instrument_token, product
        - quantity, overnight_quantity, multiplier
        - average_price, last_price, close_price
        - pnl, m2m, unrealised, realised
        - buy_quantity, sell_quantity, buy_price, sell_price
        - buy_value, sell_value, buy_m2m, sell_m2m
        """
        url = f"{self.BASE_URL}/portfolio/positions"
        logger.info("Fetching positions from Kite API")

        result = await self._request("GET", url, access_token)
        return result.get("data", {"net": [], "day": []})

    async def get_orders(self, access_token: str) -> List[Dict[str, Any]]:
        """
        Fetch all orders for the day.

        Returns list of orders with fields:
        - order_id, exchange_order_id, status, status_message
        - tradingsymbol, exchange, transaction_type
        - order_type, product, variety, validity
        - quantity, pending_quantity, filled_quantity, cancelled_quantity
        - price, trigger_price, average_price
        - order_timestamp, exchange_timestamp
        - tag, guid, parent_order_id
        """
        url = f"{self.BASE_URL}/orders"
        logger.info("Fetching orders from Kite API")

        result = await self._request("GET", url, access_token)
        return result.get("data", [])

    async def get_order_history(self, access_token: str, order_id: str) -> List[Dict[str, Any]]:
        """
        Fetch history of a specific order.

        Returns list of order state changes over time.
        Useful for tracking order modifications and status changes.
        """
        url = f"{self.BASE_URL}/orders/{order_id}"
        logger.info(f"Fetching order history for {order_id}")

        result = await self._request("GET", url, access_token)
        return result.get("data", [])

    async def get_order_trades(self, access_token: str, order_id: str) -> List[Dict[str, Any]]:
        """
        Fetch trades for a specific order.

        An order can result in multiple trades (partial fills).
        """
        url = f"{self.BASE_URL}/orders/{order_id}/trades"
        logger.info(f"Fetching trades for order {order_id}")

        result = await self._request("GET", url, access_token)
        return result.get("data", [])

    async def get_holdings(self, access_token: str) -> List[Dict[str, Any]]:
        """
        Fetch equity holdings (CNC/delivery).

        Returns list of holdings with:
        - tradingsymbol, exchange, isin, instrument_token
        - quantity, t1_quantity, authorised_quantity
        - average_price, last_price, close_price
        - pnl, day_change, day_change_percentage
        - collateral_quantity, collateral_type
        """
        url = f"{self.BASE_URL}/portfolio/holdings"
        logger.info("Fetching holdings from Kite API")

        result = await self._request("GET", url, access_token)
        return result.get("data", [])

    async def get_margins(self, access_token: str, segment: str = None) -> Dict[str, Any]:
        """
        Fetch account margins.

        Args:
            segment: Optional - 'equity' or 'commodity'. If None, returns both.

        Returns dict with:
        - equity: Equity segment margins
        - commodity: Commodity segment margins

        Each segment contains:
        - available: {adhoc_margin, cash, collateral, intraday_payin, live_balance}
        - utilised: {debits, exposure, holding_sales, m2m_realised, m2m_unrealised, option_premium, payout, span, turnover}
        """
        url = f"{self.BASE_URL}/user/margins"
        if segment:
            url += f"/{segment}"

        logger.info(f"Fetching margins from Kite API (segment: {segment or 'all'})")

        result = await self._request("GET", url, access_token)
        return result.get("data", {})

    async def get_instruments(self, exchange: str = None, access_token: str = None) -> List[Dict[str, Any]]:
        """
        Fetch instrument master (CSV format).

        Args:
            exchange: Optional - 'NSE', 'NFO', 'BSE', 'BFO', 'MCX'

        Returns list of instruments with:
        - instrument_token, exchange_token
        - tradingsymbol, name
        - last_price, expiry, strike
        - tick_size, lot_size
        - instrument_type, segment, exchange
        """
        url = f"{self.BASE_URL}/instruments"
        if exchange:
            url += f"/{exchange}"

        logger.info(f"Fetching instruments from Kite API (exchange: {exchange or 'all'})")

        await self.rate_limiter.acquire()

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, timeout=60.0)  # Longer timeout for CSV

                if response.status_code >= 400:
                    raise KiteAPIError(
                        f"Failed to fetch instruments: {response.status_code}",
                        status_code=response.status_code
                    )

                # Parse CSV response
                return self._parse_instruments_csv(response.text)

            except httpx.TimeoutException:
                raise KiteNetworkError("Instruments request timed out", status_code=408)
            except httpx.NetworkError as e:
                raise KiteNetworkError(f"Network error: {str(e)}")

    def _parse_instruments_csv(self, csv_text: str) -> List[Dict[str, Any]]:
        """Parse Kite instruments CSV into list of dicts"""
        reader = csv.DictReader(StringIO(csv_text))
        instruments = []

        for row in reader:
            instruments.append({
                "instrument_token": int(row.get("instrument_token", 0)),
                "exchange_token": int(row.get("exchange_token", 0)) if row.get("exchange_token") else None,
                "tradingsymbol": row.get("tradingsymbol", ""),
                "name": row.get("name", ""),
                "last_price": float(row.get("last_price", 0)) if row.get("last_price") else None,
                "expiry": row.get("expiry") if row.get("expiry") else None,
                "strike": float(row.get("strike", 0)) if row.get("strike") else None,
                "tick_size": float(row.get("tick_size", 0.05)),
                "lot_size": int(row.get("lot_size", 1)),
                "instrument_type": row.get("instrument_type", ""),
                "segment": row.get("segment", ""),
                "exchange": row.get("exchange", ""),
            })

        return instruments

    async def get_ltp(self, access_token: str, instruments: List[str]) -> Dict[str, float]:
        """
        Get last traded price for instruments.

        Args:
            instruments: list of "EXCHANGE:SYMBOL" strings, e.g. ["NSE:INFY", "NFO:NIFTY24JANFUT"]

        Returns:
            dict of {"NSE:INFY": 1430.15, ...}
        """
        if not instruments:
            return {}
        url = f"{self.BASE_URL}/quote/ltp"
        # Kite expects repeated ?i= params
        params = [("i", instr) for instr in instruments]
        result = await self._request("GET", url, access_token, params=params)
        prices: Dict[str, float] = {}
        for key, data in result.get("data", {}).items():
            prices[key] = float(data.get("last_price", 0))
        return prices

    async def revoke_token(self, access_token: str) -> bool:
        """Revokes the access token (logout)."""
        url = f"{self.TOKEN_URL}?api_key={self.api_key}&access_token={access_token}"

        try:
            await self.rate_limiter.acquire()
            client = await self._get_client()
            response = await client.delete(
                url,
                headers=self._get_headers(access_token),
                timeout=10.0
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to revoke token: {e}")
            return False

    async def validate_token(self, access_token: str) -> bool:
        """
        Check if an access token is still valid by making a cheap profile API call.
        Returns True if valid, False if expired or invalid.
        """
        try:
            await self.get_profile(access_token)
            return True
        except (KiteTokenExpiredError, KiteAuthError):
            return False
        except Exception:
            # Network error etc. — don't assume token is invalid
            return True

    def validate_postback_checksum(self, payload: Dict, checksum: str) -> bool:
        """
        Validate Kite postback checksum for webhook security.

        Kite sends: SHA-256(order_id + order_timestamp + api_secret)
        """
        order_id = payload.get("order_id", "")
        timestamp = payload.get("order_timestamp", "")

        expected = hashlib.sha256(
            f"{order_id}{timestamp}{self.api_secret}".encode()
        ).hexdigest()

        return expected == checksum


# Singleton instance — used directly by existing routes (backward-compatible).
# New code should prefer: get_broker_service(account.broker_name)
zerodha_client = ZerodhaClient()

# Register with factory so get_broker_service("zerodha") returns ZerodhaClient
BrokerFactory.register(BrokerType.ZERODHA, ZerodhaClient)
