from sqlalchemy import Column, String, Integer, BigInteger, Numeric, DateTime, ARRAY, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime, timezone

from app.core.database import Base

class Position(Base):
    __tablename__ = "positions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    broker_account_id = Column(UUID(as_uuid=True), ForeignKey("broker_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    tradingsymbol = Column(String(100), nullable=False)
    exchange = Column(String(20))
    instrument_type = Column(String(20))
    product = Column(String(20))
    segment = Column(String(20), nullable=True)
    total_quantity = Column(Integer)
    average_entry_price = Column(Numeric(15, 4))
    average_exit_price = Column(Numeric(15, 4))

    # Kite-specific fields
    instrument_token = Column(BigInteger, nullable=True)
    overnight_quantity = Column(Integer, default=0)
    multiplier = Column(Numeric(10, 4), default=1)

    # P&L fields from Zerodha
    realized_pnl = Column(Numeric(15, 4))
    unrealized_pnl = Column(Numeric(15, 4))
    pnl = Column(Numeric(15, 4))
    day_pnl = Column(Numeric(15, 4))
    m2m = Column(Numeric(15, 4))

    # Price fields
    last_price = Column(Numeric(15, 4))
    close_price = Column(Numeric(15, 4))

    # Value fields
    value = Column(Numeric(15, 4))
    buy_value = Column(Numeric(15, 4))
    sell_value = Column(Numeric(15, 4))

    # Day trading fields
    day_buy_quantity = Column(Integer, default=0)
    day_sell_quantity = Column(Integer, default=0)
    day_buy_price = Column(Numeric(15, 4))
    day_sell_price = Column(Numeric(15, 4))
    day_buy_value = Column(Numeric(15, 4))
    day_sell_value = Column(Numeric(15, 4))

    first_entry_time = Column(DateTime(timezone=True))
    last_exit_time = Column(DateTime(timezone=True))
    holding_duration_minutes = Column(Integer)
    order_ids = Column(ARRAY(String))
    status = Column(String(20), default='open')
    synced_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))