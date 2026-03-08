import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import String, Numeric, Integer, TIMESTAMP, text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

# Valid entry types
ENTRY_TYPES = frozenset({"OPEN", "INCREASE", "DECREASE", "CLOSE", "FLIP"})


class PositionLedger(Base):
    """
    Append-only ledger of every fill that changes a position.

    One row per fill. Never updated after insert.
    idempotency_key prevents duplicate entries from webhook retries.

    entry_type meaning:
        OPEN     — first fill for this symbol (position goes 0 → N)
        INCREASE — adds to existing position (same direction)
        DECREASE — partial close (opposite direction, position stays open)
        CLOSE    — full close (position goes to 0)
        FLIP     — closes current position AND opens opposite direction

    realized_pnl is non-zero only on DECREASE / CLOSE / FLIP entries.

    Phase 2: built and tested in isolation.
    Phase 3: replaces the application-code FIFO calculator.
    """
    __tablename__ = "position_ledger"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    broker_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("broker_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Instrument
    tradingsymbol: Mapped[str] = mapped_column(String, nullable=False)
    exchange: Mapped[str] = mapped_column(String, nullable=False)

    # Fill details
    entry_type: Mapped[str] = mapped_column(String(10), nullable=False)
    fill_order_id: Mapped[str] = mapped_column(String, nullable=False)
    fill_qty: Mapped[int] = mapped_column(Integer, nullable=False)     # +buy / -sell
    fill_price: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)

    # Running position state after this fill
    position_qty_after: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_entry_price_after: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 4), nullable=True)

    # P&L — non-zero only on DECREASE / CLOSE / FLIP
    realized_pnl: Mapped[Decimal] = mapped_column(
        Numeric(15, 4), nullable=False, default=Decimal("0")
    )

    # Session linkage
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("trading_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Timestamps
    occurred_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )

    # Idempotency
    idempotency_key: Mapped[str] = mapped_column(String, nullable=False, unique=True)

    # Relationships
    broker_account = relationship("BrokerAccount")
    session = relationship("TradingSession")
