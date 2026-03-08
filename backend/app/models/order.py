import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, Numeric, TIMESTAMP, text, ForeignKey, UUID
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class Order(Base):
    """
    Track all orders (not just executed trades).

    Used for:
    - Order flow analysis (cancellation rate, modification patterns)
    - Behavioral insights (hesitation, indecision)
    - Complete audit trail
    """
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    broker_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("broker_accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Kite identifiers
    kite_order_id: Mapped[str] = mapped_column(String(50), nullable=False)
    exchange_order_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Status
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # OPEN, COMPLETE, CANCELLED, REJECTED
    status_message: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status_message_raw: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Order details
    tradingsymbol: Mapped[str] = mapped_column(String(50), nullable=False)
    exchange: Mapped[str] = mapped_column(String(10), nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(10), nullable=False)  # BUY, SELL
    order_type: Mapped[str] = mapped_column(String(10), nullable=False)  # MARKET, LIMIT, SL, SL-M
    product: Mapped[str] = mapped_column(String(10), nullable=False)  # CNC, MIS, NRML
    variety: Mapped[str] = mapped_column(String(20), nullable=False)  # regular, amo, co, iceberg
    validity: Mapped[str] = mapped_column(String(10), default="DAY")  # DAY, IOC, TTL

    # Quantities
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    disclosed_quantity: Mapped[int] = mapped_column(Integer, default=0)
    pending_quantity: Mapped[int] = mapped_column(Integer, default=0)
    cancelled_quantity: Mapped[int] = mapped_column(Integer, default=0)
    filled_quantity: Mapped[int] = mapped_column(Integer, default=0)

    # Prices
    price: Mapped[Optional[float]] = mapped_column(Numeric(15, 4), nullable=True)
    trigger_price: Mapped[Optional[float]] = mapped_column(Numeric(15, 4), nullable=True)
    average_price: Mapped[Optional[float]] = mapped_column(Numeric(15, 4), nullable=True)

    # Timestamps
    order_timestamp: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    exchange_timestamp: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    exchange_update_timestamp: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    # Metadata
    tag: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    guid: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    parent_order_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    meta: Mapped[Optional[dict]] = mapped_column(JSONB, default={})

    # System timestamps
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))

    # Relationship
    broker_account = relationship("BrokerAccount")
