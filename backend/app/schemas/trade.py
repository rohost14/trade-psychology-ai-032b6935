from uuid import UUID
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict

class TradeBase(BaseModel):
    order_id: Optional[str] = None
    tradingsymbol: Optional[str] = None
    exchange: Optional[str] = None
    transaction_type: Optional[str] = None
    order_type: Optional[str] = None
    product: Optional[str] = None
    quantity: Optional[int] = 0
    filled_quantity: Optional[int] = 0
    pending_quantity: Optional[int] = 0
    cancelled_quantity: Optional[int] = 0
    price: Optional[float] = None
    trigger_price: Optional[float] = None
    average_price: Optional[float] = None
    status: Optional[str] = None
    status_message: Optional[str] = None
    order_timestamp: Optional[datetime] = None
    exchange_timestamp: Optional[datetime] = None

class TradeCreate(TradeBase):
    broker_account_id: UUID
    asset_class: Optional[str] = None
    instrument_type: Optional[str] = None
    product_type: Optional[str] = None
    pnl: Optional[float] = 0.0
    raw_payload: Optional[Dict[str, Any]] = None

class TradeUpdate(BaseModel):
    filled_quantity: Optional[int] = None
    pending_quantity: Optional[int] = None
    cancelled_quantity: Optional[int] = None
    average_price: Optional[float] = None
    status: Optional[str] = None
    status_message: Optional[str] = None
    pnl: Optional[float] = None
    updated_at: datetime = Field(default_factory=datetime.now)

class TradeResponse(TradeBase):
    id: UUID
    broker_account_id: UUID
    asset_class: Optional[str] = None
    instrument_type: Optional[str] = None
    product_type: Optional[str] = None
    pnl: Optional[float] = None

    # Kite-specific identifiers
    kite_order_id: Optional[str] = None
    exchange_order_id: Optional[str] = None
    instrument_token: Optional[int] = None

    # Order attributes
    validity: Optional[str] = None
    variety: Optional[str] = None
    disclosed_quantity: Optional[int] = None
    parent_order_id: Optional[str] = None
    tag: Optional[str] = None
    guid: Optional[str] = None
    market_protection: Optional[float] = None

    # Timestamps
    fill_timestamp: Optional[datetime] = None

    raw_payload: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class TradeListResponse(BaseModel):
    trades: List[TradeResponse]
    total: int
    page: int
    limit: int

class TradeStatsResponse(BaseModel):
    total_trades: int
    winning_trades: int
    losing_trades: int
    total_pnl: float
    avg_pnl: float


# ------------------------------------------------------------------
# CompletedTrade (flat-to-flat round) schemas
# ------------------------------------------------------------------

class CompletedTradeResponse(BaseModel):
    id: UUID
    broker_account_id: UUID
    tradingsymbol: str
    exchange: str
    instrument_type: Optional[str] = None
    product: Optional[str] = None
    direction: Optional[str] = None
    total_quantity: Optional[int] = None
    num_entries: Optional[int] = None
    num_exits: Optional[int] = None
    avg_entry_price: Optional[float] = None
    avg_exit_price: Optional[float] = None
    realized_pnl: Optional[float] = None
    entry_time: Optional[datetime] = None
    exit_time: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    closed_by_flip: Optional[bool] = False
    entry_trade_ids: Optional[List[str]] = None
    exit_trade_ids: Optional[List[str]] = None
    status: Optional[str] = "closed"
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class CompletedTradeListResponse(BaseModel):
    trades: List[CompletedTradeResponse]
    total: int


# ------------------------------------------------------------------
# IncompletePosition (sync gap) schemas
# ------------------------------------------------------------------

class IncompletePositionResponse(BaseModel):
    id: UUID
    broker_account_id: UUID
    tradingsymbol: str
    exchange: str
    product: Optional[str] = None
    direction: Optional[str] = None
    unmatched_quantity: Optional[int] = None
    avg_entry_price: Optional[float] = None
    entry_time: Optional[datetime] = None
    reason: str
    detected_at: Optional[datetime] = None
    details: Optional[str] = None
    resolution_status: Optional[str] = "PENDING"
    resolved_at: Optional[datetime] = None
    resolution_method: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class IncompletePositionListResponse(BaseModel):
    positions: List[IncompletePositionResponse]
    total: int
