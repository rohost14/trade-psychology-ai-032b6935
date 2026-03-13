"""
Abstract Broker Interface

Defines the contract that all broker implementations must follow.
This enables multi-broker support (Zerodha, AngelOne, Upstox, etc.)

Usage:
    from app.services.broker_interface import BrokerInterface
    from app.services.zerodha_service import ZerodhaService

    broker: BrokerInterface = ZerodhaService()
    trades = await broker.get_trades(access_token)
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass
from enum import Enum


class BrokerType(Enum):
    """Supported broker types."""
    ZERODHA = "zerodha"
    DHAN = "dhan"
    ANGELONE = "angelone"
    UPSTOX = "upstox"
    FYERS = "fyers"
    IIFL = "iifl"


@dataclass
class BrokerConfig:
    """Configuration for a broker."""
    broker_type: BrokerType
    api_key: str
    api_secret: str
    redirect_uri: Optional[str] = None
    base_url: Optional[str] = None


@dataclass
class NormalizedTrade:
    """
    Normalized trade structure across all brokers.

    All broker implementations should convert their response to this format.
    """
    order_id: str
    exchange_order_id: Optional[str]
    tradingsymbol: str
    exchange: str
    transaction_type: str  # BUY or SELL
    order_type: str  # MARKET, LIMIT, SL, SL-M
    product: str  # CNC, MIS, NRML
    quantity: int
    filled_quantity: int
    pending_quantity: int
    price: float
    average_price: float
    trigger_price: Optional[float]
    status: str
    status_message: Optional[str]
    order_timestamp: Optional[datetime]
    exchange_timestamp: Optional[datetime]
    fill_timestamp: Optional[datetime]
    validity: str  # DAY, IOC
    variety: str  # regular, amo, co
    tag: Optional[str]
    instrument_token: Optional[int]
    raw_data: Dict  # Original broker response


@dataclass
class NormalizedPosition:
    """Normalized position structure across all brokers."""
    tradingsymbol: str
    exchange: str
    product: str
    quantity: int
    overnight_quantity: int
    multiplier: float
    average_price: float
    last_price: float
    pnl: float
    m2m: float
    buy_quantity: int
    sell_quantity: int
    buy_price: float
    sell_price: float
    buy_value: float
    sell_value: float
    instrument_token: Optional[int]
    raw_data: Dict


@dataclass
class NormalizedHolding:
    """Normalized holding structure across all brokers."""
    tradingsymbol: str
    exchange: str
    isin: Optional[str]
    quantity: int
    t1_quantity: int
    average_price: float
    last_price: float
    close_price: float
    pnl: float
    day_change: float
    day_change_percentage: float
    instrument_token: Optional[int]
    raw_data: Dict


@dataclass
class NormalizedProfile:
    """Normalized user profile across all brokers."""
    user_id: str
    user_name: str
    email: Optional[str]
    user_type: Optional[str]
    broker: str
    exchanges: List[str]
    products: List[str]
    order_types: List[str]
    avatar_url: Optional[str]
    raw_data: Dict


class BrokerInterface(ABC):
    """
    Abstract interface for broker integrations.

    All broker implementations (Zerodha, AngelOne, etc.) must implement this interface.
    This ensures consistent behavior across different brokers.
    """

    @property
    @abstractmethod
    def broker_type(self) -> BrokerType:
        """Return the broker type."""
        pass

    @property
    @abstractmethod
    def broker_name(self) -> str:
        """Return human-readable broker name."""
        pass

    # ==========================================================================
    # Authentication
    # ==========================================================================

    @abstractmethod
    def generate_login_url(self, redirect_uri: str, state: Optional[str] = None) -> str:
        """Generate OAuth login URL for the broker."""
        pass

    @abstractmethod
    async def exchange_token(self, request_token: str) -> Dict:
        """Exchange request token for access token."""
        pass

    @abstractmethod
    async def revoke_token(self, access_token: str) -> bool:
        """Revoke/invalidate an access token."""
        pass

    @abstractmethod
    async def validate_token(self, access_token: str) -> bool:
        """Check if access token is still valid."""
        pass

    # ==========================================================================
    # User Data
    # ==========================================================================

    @abstractmethod
    async def get_profile(self, access_token: str) -> NormalizedProfile:
        """Get user profile."""
        pass

    @abstractmethod
    async def get_margins(self, access_token: str) -> Dict:
        """Get account margins."""
        pass

    # ==========================================================================
    # Trading Data
    # ==========================================================================

    @abstractmethod
    async def get_trades(self, access_token: str) -> List[NormalizedTrade]:
        """Get today's executed trades."""
        pass

    @abstractmethod
    async def get_orders(self, access_token: str) -> List[Dict]:
        """Get all orders (including pending, cancelled, rejected)."""
        pass

    @abstractmethod
    async def get_positions(self, access_token: str) -> List[NormalizedPosition]:
        """Get current positions."""
        pass

    @abstractmethod
    async def get_holdings(self, access_token: str) -> List[NormalizedHolding]:
        """Get equity holdings (CNC/delivery)."""
        pass

    # ==========================================================================
    # Instruments
    # ==========================================================================

    @abstractmethod
    async def get_instruments(self, exchange: Optional[str] = None, access_token: Optional[str] = None) -> List[Dict]:
        """
        Get instrument master data.
        access_token is optional — some brokers (Kite) don't require auth for instruments.
        """
        pass

    # ==========================================================================
    # Order History
    # ==========================================================================

    @abstractmethod
    async def get_order_history(self, access_token: str, order_id: str) -> List[Dict]:
        """Get history/states of a specific order."""
        pass

    # ==========================================================================
    # Optional: Live Prices
    # ==========================================================================

    async def get_ltp(self, access_token: str, instruments: List[str]) -> Dict[str, float]:
        """
        Get last traded price for a list of instruments.
        instruments: list of "EXCHANGE:SYMBOL" strings e.g. ["NSE:INFY", "NFO:NIFTY24JANFUT"]
        Returns dict of {"EXCHANGE:SYMBOL": last_price}.

        Optional — only brokers with LTP endpoints need to implement this.
        Default raises NotImplementedError.
        """
        raise NotImplementedError(f"{self.broker_name} does not support get_ltp")

    # ==========================================================================
    # Optional: Order Placement (for future)
    # ==========================================================================

    async def place_order(self, access_token: str, order_params: Dict) -> Dict:
        """Place an order. Optional — default raises NotImplementedError."""
        raise NotImplementedError(f"{self.broker_name} does not support order placement")

    async def modify_order(self, access_token: str, order_id: str, order_params: Dict) -> Dict:
        """Modify an existing order. Optional."""
        raise NotImplementedError(f"{self.broker_name} does not support order modification")

    async def cancel_order(self, access_token: str, order_id: str) -> Dict:
        """Cancel an order. Optional."""
        raise NotImplementedError(f"{self.broker_name} does not support order cancellation")


class BrokerFactory:
    """
    Factory for creating broker instances.

    Usage:
        broker = BrokerFactory.create(BrokerType.ZERODHA, config)
    """

    _implementations: Dict[BrokerType, type] = {}

    @classmethod
    def register(cls, broker_type: BrokerType, implementation: type):
        """Register a broker implementation."""
        cls._implementations[broker_type] = implementation

    @classmethod
    def create(cls, broker_type: BrokerType, config: Optional[BrokerConfig] = None) -> BrokerInterface:
        """Create a broker instance."""
        if broker_type not in cls._implementations:
            raise ValueError(f"No implementation registered for {broker_type}")

        implementation = cls._implementations[broker_type]

        if config:
            return implementation(config)
        return implementation()

    @classmethod
    def get_supported_brokers(cls) -> List[BrokerType]:
        """Get list of supported broker types."""
        return list(cls._implementations.keys())


# ==========================================================================
# Broker-specific exceptions
# ==========================================================================

def get_broker_service(broker_name: str) -> "BrokerInterface":
    """
    Return the correct broker service for a given broker_account.broker_name string.

    Usage (in routes or tasks):
        from app.services.broker_interface import get_broker_service
        service = get_broker_service(account.broker_name)
        trades = await service.get_trades(access_token)

    To add a new broker (e.g. Dhan):
        1. Create backend/app/services/dhan_service.py implementing BrokerInterface
        2. Register it: BrokerFactory.register(BrokerType.DHAN, DhanClient)
        3. Ensure registration runs at import time (bottom of dhan_service.py)
        4. Add "dhan" to the broker_name_map below
        5. Update zerodha.py OAuth callback to handle Dhan's OAuth flow
    """
    # Import here to avoid circular imports — registrations happen at import time
    import app.services.zerodha_service  # noqa: F401 — registers ZerodhaClient

    broker_name_map: Dict[str, BrokerType] = {
        "zerodha": BrokerType.ZERODHA,
        "dhan": BrokerType.DHAN,
        "angelone": BrokerType.ANGELONE,
        "upstox": BrokerType.UPSTOX,
        "fyers": BrokerType.FYERS,
    }

    broker_type = broker_name_map.get(broker_name.lower())
    if not broker_type:
        raise ValueError(f"Unsupported broker: '{broker_name}'. Supported: {list(broker_name_map)}")

    return BrokerFactory.create(broker_type)


class BrokerError(Exception):
    """Base exception for broker errors."""
    def __init__(self, message: str, broker: str, code: Optional[str] = None):
        self.message = message
        self.broker = broker
        self.code = code
        super().__init__(f"[{broker}] {message}")


class BrokerAuthError(BrokerError):
    """Authentication/token error."""
    pass


class BrokerRateLimitError(BrokerError):
    """Rate limit exceeded."""
    pass


class BrokerAPIError(BrokerError):
    """General API error."""
    pass
