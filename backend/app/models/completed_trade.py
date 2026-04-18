import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Boolean, Numeric, TIMESTAMP, text, ForeignKey, ARRAY, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


class CompletedTrade(Base):
    """
    Flat-to-flat trade round (Layer 3: Decision Lifecycle).

    Created ONLY when a position goes from non-zero to zero via FIFO matching.
    One row = one complete trading decision.

    Immutable once created — historical facts are never rewritten.
    """
    __tablename__ = "completed_trades"
    __table_args__ = (
        Index('idx_completed_trades_broker_exit', 'broker_account_id', 'exit_time'),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    broker_account_id = Column(UUID(as_uuid=True), ForeignKey("broker_accounts.id", ondelete="CASCADE"), nullable=False)

    # Instrument
    tradingsymbol = Column(String(100), nullable=False)
    exchange = Column(String(20), nullable=False)
    instrument_type = Column(String(20))       # EQ, FUT, CE, PE
    product = Column(String(20))               # MIS, NRML, MTF

    # Round
    direction = Column(String(10))             # LONG, SHORT
    total_quantity = Column(Integer)            # Peak position size (in units, lot_size already factored)
    num_entries = Column(Integer, default=1)    # Count of entry fills (not unique trade_ids)
    num_exits = Column(Integer, default=1)      # Count of exit fills (not unique trade_ids)

    # Prices (weighted averages from FIFO matching)
    avg_entry_price = Column(Numeric(15, 4))
    avg_exit_price = Column(Numeric(15, 4))

    # P&L
    realized_pnl = Column(Numeric(15, 4))
    # Percentage return on entry price: (exit-entry)/entry*100 for LONG, (entry-exit)/entry*100 for SHORT.
    # NULL for records created before migration 055; backfilled on server startup.
    pnl_pct = Column(Numeric(8, 2), nullable=True)

    # Timing
    entry_time = Column(TIMESTAMP(timezone=True))
    exit_time = Column(TIMESTAMP(timezone=True))
    duration_minutes = Column(Integer)

    # Direction flip: true when closing fill both closed this round
    # AND opened the reverse direction (psychologically significant)
    closed_by_flip = Column(Boolean, default=False)

    # Fill references — audit trail back to trades table ONLY (not for counting)
    entry_trade_ids = Column(ARRAY(String))
    exit_trade_ids = Column(ARRAY(String))

    # BTST analytics
    overnight_close_price = Column(Numeric(15, 4), nullable=True)
    # Set only for multi-day NRML holds: closing price of the instrument at EOD of entry day.
    # Sourced from Zerodha's close_price field at the moment the position is closed.
    # Used to detect "overnight reversals" (was profitable at EOD, closed at loss next day).

    # Status — always 'closed' (immutable once created)
    status = Column(String(20), default='closed')

    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))

    # Relationships
    broker_account = relationship("BrokerAccount")
    feature = relationship("CompletedTradeFeature", back_populates="completed_trade", uselist=False, cascade="all, delete-orphan")
