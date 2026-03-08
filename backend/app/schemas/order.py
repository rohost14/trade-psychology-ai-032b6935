from pydantic import BaseModel
from typing import Optional, Dict, Any
from decimal import Decimal
from datetime import datetime
from uuid import UUID

class OrderBase(BaseModel):
    kite_order_id: str
    exchange_order_id: Optional[str] = None
    status: str
    status_message: Optional[str] = None
    status_message_raw: Optional[str] = None
    tradingsymbol: str
    exchange: str
    transaction_type: str
    order_type: str
    product: str
    variety: str
    validity: str
    quantity: int
    disclosed_quantity: int = 0
    pending_quantity: int = 0
    cancelled_quantity: int = 0
    filled_quantity: int = 0
    price: Optional[float] = None
    trigger_price: Optional[float] = None
    average_price: Optional[float] = None
    order_timestamp: Optional[datetime] = None
    exchange_timestamp: Optional[datetime] = None
    exchange_update_timestamp: Optional[datetime] = None
    tag: Optional[str] = None
    guid: Optional[str] = None
    parent_order_id: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None

class OrderCreate(OrderBase):
    broker_account_id: UUID

class OrderUpdate(OrderBase):
    pass

class Order(OrderBase):
    id: UUID
    broker_account_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
