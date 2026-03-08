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
    async def get_instruments(self, access_token: str, exchange: Optional[str] = None) -> List[Dict]:
        """Get instrument master data."""
        pass

    # ==========================================================================
    # Order History
    # ==========================================================================

    @abstractmethod
    async def get_order_history(self, access_token: str, order_id: str) -> List[Dict]:
        """Get history/states of a specific order."""
        pass

    # ==========================================================================
    # Optional: Order Placement (for future)
    # ==========================================================================

    async def place_order(self, access_token: str, order_params: Dict) -> Dict:
        """
        Place an order. Optional - not all implementations need this.

        Default implementation raises NotImplementedError.
        """
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
