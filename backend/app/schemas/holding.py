from pydantic import BaseModel, Field
from typing import Optional
from decimal import Decimal
from datetime import datetime
from uuid import UUID

class HoldingBase(BaseModel):
    tradingsymbol: str
    exchange: str
    isin: Optional[str] = None
    quantity: int
    authorised_quantity: int = 0
    t1_quantity: int = 0
    collateral_quantity: int = 0
    collateral_type: Optional[str] = None
    average_price: Optional[float] = None
    last_price: Optional[float] = None
    close_price: Optional[float] = None
    pnl: Optional[float] = None
    day_change: Optional[float] = None
    day_change_percentage: Optional[float] = None
    instrument_token: Optional[int] = None
    product: str = "CNC"

class HoldingCreate(HoldingBase):
    pass

class HoldingUpdate(HoldingBase):
    pass

class Holding(HoldingBase):
    id: UUID
    broker_account_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
