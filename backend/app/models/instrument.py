import uuid
from datetime import datetime, date
from typing import Optional
from sqlalchemy import String, Integer, BigInteger, Numeric, Date, TIMESTAMP, text, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class Instrument(Base):
    """
    Kite instrument master cache.

    Used for:
    - Symbol to instrument_token mapping (WebSocket subscriptions)
    - Lot size lookups (F&O P&L calculation)
    - Option chain data (strike, expiry)
    """
    __tablename__ = "instruments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Kite identifiers
    instrument_token: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    exchange_token: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    # Symbol info
    tradingsymbol: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Market data
    last_price: Mapped[Optional[float]] = mapped_column(Numeric(15, 4), nullable=True)

    # F&O specific
    expiry: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    strike: Mapped[Optional[float]] = mapped_column(Numeric(15, 4), nullable=True)
    tick_size: Mapped[float] = mapped_column(Numeric(10, 4), default=0.05)
    lot_size: Mapped[int] = mapped_column(Integer, default=1)

    # Classification
    instrument_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # EQ, FUT, CE, PE
    segment: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # NSE, NFO, BSE, BFO, MCX
    exchange: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
