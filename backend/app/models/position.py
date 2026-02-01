from sqlalchemy import Column, String, Integer, Numeric, DateTime, ARRAY, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime

from app.core.database import Base

class Position(Base):
    __tablename__ = "positions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    broker_account_id = Column(UUID(as_uuid=True), ForeignKey("broker_accounts.id"), nullable=False)
    tradingsymbol = Column(String(100), nullable=False)
    exchange = Column(String(20))
    instrument_type = Column(String(20))
    product = Column(String(20))
    total_quantity = Column(Integer)
    average_entry_price = Column(Numeric(10, 2))
    average_exit_price = Column(Numeric(10, 2))
    realized_pnl = Column(Numeric(10, 2))
    first_entry_time = Column(DateTime(timezone=True))
    last_exit_time = Column(DateTime(timezone=True))
    holding_duration_minutes = Column(Integer)
    order_ids = Column(ARRAY(String))
    status = Column(String(20), default='open')
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)