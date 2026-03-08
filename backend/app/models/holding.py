import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, BigInteger, Numeric, TIMESTAMP, text, ForeignKey, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class Holding(Base):
    """
    CNC/delivery holdings separate from intraday positions.

    Used for:
    - Portfolio tracking
    - Long-term investment vs trading separation
    - Collateral tracking (for F&O margin)
    """
    __tablename__ = "holdings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    broker_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("broker_accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Identity
    tradingsymbol: Mapped[str] = mapped_column(String(50), nullable=False)
    exchange: Mapped[str] = mapped_column(String(10), nullable=False)
    isin: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Quantities
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    authorised_quantity: Mapped[int] = mapped_column(Integer, default=0)  # CDSL TPIN authorized
    t1_quantity: Mapped[int] = mapped_column(Integer, default=0)  # T+1 not yet settled
    collateral_quantity: Mapped[int] = mapped_column(Integer, default=0)
    collateral_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Prices
    average_price: Mapped[Optional[float]] = mapped_column(Numeric(15, 4), nullable=True)
    last_price: Mapped[Optional[float]] = mapped_column(Numeric(15, 4), nullable=True)
    close_price: Mapped[Optional[float]] = mapped_column(Numeric(15, 4), nullable=True)

    # P&L
    pnl: Mapped[Optional[float]] = mapped_column(Numeric(15, 4), nullable=True)
    day_change: Mapped[Optional[float]] = mapped_column(Numeric(15, 4), nullable=True)
    day_change_percentage: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)

    # Metadata
    instrument_token: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    product: Mapped[str] = mapped_column(String(10), default="CNC")

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))

    # Relationship
    broker_account = relationship("BrokerAccount")
