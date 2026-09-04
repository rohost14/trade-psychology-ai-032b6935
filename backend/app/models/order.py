import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    String, Integer, Numeric, TIMESTAMP, UniqueConstraint, text, ForeignKey, UUID,
)
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

    PARTITIONED. Migration 090 made this table RANGE-partitioned by month on
    `order_timestamp`, which forces three things this class has to mirror:

      * `order_timestamp` is NOT NULL - it is the partition key, and a row with
        no key belongs to no partition
      * the primary key is COMPOSITE, (id, order_timestamp), because Postgres
        requires the partition key in every unique constraint
      * so is the natural key, (broker_account_id, kite_order_id,
        order_timestamp), which is what both ON CONFLICT sites in
        trade_sync_service name

    The partitioning itself is deliberately NOT declared here. SQLAlchemy can
    emit `PARTITION BY` via a dialect argument, but `create_all` would then
    build a partitioned table with no partitions and no DEFAULT - a table that
    accepts no rows at all, which is exactly the production failure migration
    092 had to repair. Partitions are the migrations' job; this class describes
    the columns and keys.
    """
    __tablename__ = "orders"
    __table_args__ = (
        # Mirrors migration 090. The partition key is part of it because
        # Postgres requires it, not because the identity of an order includes
        # its timestamp - `order_timestamp` is the order's PLACEMENT time and
        # does not change across its lifecycle, so a modify still upserts onto
        # the same row.
        UniqueConstraint("broker_account_id", "kite_order_id", "order_timestamp",
                         name="uq_orders_account_kite_id"),
    )

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
    # Nullable in the database, not an oversight: migration 010 declared these
    # with DEFAULT 0 and no NOT NULL, so a row written by anything other than
    # this model can legally hold nulls. The model has to say so, or
    # `create_all` in CI builds a stricter table than production and tests
    # reject rows the real database accepts.
    disclosed_quantity: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    pending_quantity: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    cancelled_quantity: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    filled_quantity: Mapped[Optional[int]] = mapped_column(Integer, default=0)

    # Prices
    price: Mapped[Optional[float]] = mapped_column(Numeric(15, 4), nullable=True)
    trigger_price: Mapped[Optional[float]] = mapped_column(Numeric(15, 4), nullable=True)
    average_price: Mapped[Optional[float]] = mapped_column(Numeric(15, 4), nullable=True)

    # Timestamps
    #: The partition key, and half of the primary key. NOT NULL: a row whose
    #: partition key is null belongs to no partition and cannot be inserted.
    #: The write path guarantees a value - `upsert_order` falls back
    #: order_timestamp -> exchange_timestamp -> now().
    order_timestamp: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), primary_key=True, nullable=False
    )
    exchange_timestamp: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    exchange_update_timestamp: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    # Metadata
    tag: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    guid: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    parent_order_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    meta: Mapped[Optional[dict]] = mapped_column(JSONB, default={})

    # System timestamps
    # Same: DEFAULT NOW() without NOT NULL in 010. The server default fills
    # them on every insert this app makes, but the COLUMN permits null.
    created_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))

    # Relationship
    broker_account = relationship("BrokerAccount")
