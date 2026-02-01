from uuid import UUID
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict

class TradeBase(BaseModel):
    order_id: Optional[str] = None
    tradingsymbol: str
    exchange: str
    transaction_type: str
    order_type: str
    product: str
    quantity: int
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
    user_id: Optional[UUID] = None
    broker_account_id: UUID
    asset_class: Optional[str] = None
    instrument_type: Optional[str] = None
    product_type: Optional[str] = None
    pnl: Optional[float] = None
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
