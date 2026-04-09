import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Numeric, Integer, BigInteger, JSON, TIMESTAMP, text, ForeignKey, UUID, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.broker_account import BrokerAccount

class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    broker_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("broker_accounts.id", ondelete="CASCADE"), nullable=False, index=True)

    # Core Identity
    order_id: Mapped[str] = mapped_column(String, index=True)
    tradingsymbol: Mapped[str] = mapped_column(String)
    exchange: Mapped[str] = mapped_column(String)
    transaction_type: Mapped[str] = mapped_column(String)
    order_type: Mapped[str] = mapped_column(String)
    product: Mapped[str] = mapped_column(String)

    # Kite-specific identifiers
    kite_order_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    exchange_order_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    instrument_token: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    # Order attributes
    validity: Mapped[Optional[str]] = mapped_column(String(10), default="DAY")
    variety: Mapped[Optional[str]] = mapped_column(String(20), default="regular")
    disclosed_quantity: Mapped[int] = mapped_column(Integer, default=0)
    parent_order_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    tag: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    guid: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Quantities
    quantity: Mapped[int] = mapped_column(Integer)
    filled_quantity: Mapped[int] = mapped_column(Integer, default=0)
    pending_quantity: Mapped[int] = mapped_column(Integer, default=0)
    cancelled_quantity: Mapped[int] = mapped_column(Integer, default=0)

    # Prices
    price: Mapped[float] = mapped_column(Numeric(15, 4), nullable=True)
    trigger_price: Mapped[float] = mapped_column(Numeric(15, 4), nullable=True)
    average_price: Mapped[float] = mapped_column(Numeric(15, 4), nullable=True)
    market_protection: Mapped[Optional[float]] = mapped_column(Numeric(15, 4), nullable=True)

    # Status
    status: Mapped[str] = mapped_column(String)
    status_message: Mapped[str] = mapped_column(String, nullable=True)

    # Classification (Computed)
    asset_class: Mapped[str] = mapped_column(String)
    instrument_type: Mapped[str] = mapped_column(String)
    product_type: Mapped[str] = mapped_column(String)
    segment: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Financials
    pnl: Mapped[float] = mapped_column(Numeric(15, 4), nullable=True)

    # Timestamps
    order_timestamp: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    exchange_timestamp: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    fill_timestamp: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    # Meta
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=True)

    # Idempotency guard: set at the START of the signal pipeline (FIFO + behavioral).
    # NULL = pipeline has not run yet. NOT NULL = pipeline already ran, skip on retry.
    processed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))

    __table_args__ = (
        UniqueConstraint('broker_account_id', 'order_id', name='uq_trades_broker_order'),
    )

    # Relationship
    broker_account = relationship("BrokerAccount")
