import uuid
from datetime import datetime
from sqlalchemy import String, Numeric, Integer, JSON, TIMESTAMP, text, ForeignKey, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.broker_account import BrokerAccount

class Trade(Base):
    __tablename__ = "trades"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=True) # Can be linked later
    broker_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("broker_accounts.id"), nullable=False)
    
    # Core Identity
    order_id: Mapped[str] = mapped_column(String, index=True) 
    tradingsymbol: Mapped[str] = mapped_column(String)
    exchange: Mapped[str] = mapped_column(String)
    transaction_type: Mapped[str] = mapped_column(String) # BUY/SELL
    order_type: Mapped[str] = mapped_column(String) # LIMIT, MARKET, SL
    product: Mapped[str] = mapped_column(String) # CNC, MIS, etc
    
    # Quantities
    quantity: Mapped[int] = mapped_column(Integer)
    filled_quantity: Mapped[int] = mapped_column(Integer, default=0)
    pending_quantity: Mapped[int] = mapped_column(Integer, default=0)
    cancelled_quantity: Mapped[int] = mapped_column(Integer, default=0)
    
    # Prices
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=True) # Limit Price
    trigger_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=True)
    average_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=True)
    
    # Status
    status: Mapped[str] = mapped_column(String)
    status_message: Mapped[str] = mapped_column(String, nullable=True)
    
    # Classification (Computed)
    asset_class: Mapped[str] = mapped_column(String) # EQUITY, COMMODITY, etc.
    instrument_type: Mapped[str] = mapped_column(String) # SPOT, FUTURE, OPTION
    product_type: Mapped[str] = mapped_column(String) # CNC, NRML, MIS
    
    # Financials
    pnl: Mapped[float] = mapped_column(Numeric(10, 2), nullable=True)
    
    # Timestamps
    order_timestamp: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    exchange_timestamp: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    
    # Meta
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    
    # Relationship
    broker_account = relationship("BrokerAccount")
