from pydantic import BaseModel, UUID4, ConfigDict
from datetime import datetime
from decimal import Decimal
from typing import Optional, List

class PositionBase(BaseModel):
    tradingsymbol: str
    exchange: Optional[str] = None
    instrument_type: Optional[str] = None
    product: Optional[str] = None
    total_quantity: Optional[int] = None
    average_entry_price: Optional[Decimal] = None
    average_exit_price: Optional[Decimal] = None

    # Kite-specific fields
    instrument_token: Optional[int] = None
    overnight_quantity: Optional[int] = None
    multiplier: Optional[Decimal] = None

    # P&L fields
    pnl: Optional[Decimal] = None
    unrealized_pnl: Optional[Decimal] = None
    realized_pnl: Optional[Decimal] = None
    day_pnl: Optional[Decimal] = None
    m2m: Optional[Decimal] = None

    # Price fields
    last_price: Optional[Decimal] = None
    close_price: Optional[Decimal] = None

    # Value fields
    value: Optional[Decimal] = None
    buy_value: Optional[Decimal] = None
    sell_value: Optional[Decimal] = None

    # Day trading fields
    day_buy_quantity: Optional[int] = None
    day_sell_quantity: Optional[int] = None
    day_buy_price: Optional[Decimal] = None
    day_sell_price: Optional[Decimal] = None
    day_buy_value: Optional[Decimal] = None
    day_sell_value: Optional[Decimal] = None

    status: Optional[str] = None

class PositionResponse(PositionBase):
    id: UUID4
    broker_account_id: UUID4
    first_entry_time: Optional[datetime] = None
    last_exit_time: Optional[datetime] = None
    holding_duration_minutes: Optional[int] = None
    order_ids: Optional[List[str]] = None
    synced_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class PositionListResponse(BaseModel):
    positions: List[PositionResponse]
    total_count: int
    total_value: Decimal
    total_pnl: Decimal

class ExposureMetrics(BaseModel):
    total_positions: int
    total_value: Decimal
    total_pnl: Decimal
    largest_position_value: Decimal
    concentration_pct: float