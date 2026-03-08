from pydantic import BaseModel
from typing import Optional
from datetime import date
from uuid import UUID

class InstrumentBase(BaseModel):
    instrument_token: int
    exchange_token: Optional[int] = None
    tradingsymbol: str
    name: Optional[str] = None
    last_price: Optional[float] = None
    expiry: Optional[date] = None
    strike: Optional[float] = None
    tick_size: Optional[float] = None
    lot_size: int
    instrument_type: Optional[str] = None
    segment: Optional[str] = None
    exchange: str

class InstrumentCreate(InstrumentBase):
    pass

class InstrumentUpdate(InstrumentBase):
    pass

class Instrument(InstrumentBase):
    id: UUID

    class Config:
        from_attributes = True
