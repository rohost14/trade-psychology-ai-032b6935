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
    realized_pnl: Optional[Decimal] = None
    status: Optional[str] = None

class PositionResponse(PositionBase):
    id: UUID4
    broker_account_id: UUID4
    first_entry_time: Optional[datetime] = None
    
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