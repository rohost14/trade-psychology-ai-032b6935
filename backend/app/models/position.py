from sqlalchemy import Column, String, Integer, BigInteger, Numeric, DateTime, ARRAY, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime, timezone

from app.core.database import Base

class Position(Base):
    __tablename__ = "positions"
    __table_args__ = (
        UniqueConstraint(
            'broker_account_id', 'tradingsymbol', 'exchange', 'product',
            name='uq_position_account_symbol_exchange_product'
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    broker_account_id = Column(UUID(as_uuid=True), ForeignKey("broker_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    tradingsymbol = Column(String(100), nullable=False)
    exchange = Column(String(20))
    instrument_type = Column(String(20))
    product = Column(String(20))
    segment = Column(String(20), nullable=True)
    # Precision below mirrors the live Postgres column types EXACTLY. These used to
    # be declared Numeric(15, 4) while the database held 2dp, so a 4-decimal value
    # was silently rounded on write and the model told you otherwise. Two decimals
    # is the intended precision here — NSE/NFO ticks are 0.05, so a fill price is
    # exact at 2dp. tests/test_numeric_precision.py fails if the two drift apart
    # again; change the column and the model together, never one alone.
    total_quantity = Column(Integer)
    average_entry_price = Column(Numeric(10, 2))
    average_exit_price = Column(Numeric(10, 2))

    # Where average_entry_price came from: 'ledger' = cost of the current open round,
    # derived from PositionLedger; 'broker' = Kite's day-cumulative average, which
    # still includes fills from rounds that already closed. See migration 077.
    entry_price_source = Column(String(10))

    # Kite-specific fields
    instrument_token = Column(BigInteger, nullable=True)
    overnight_quantity = Column(Integer, default=0)
    multiplier = Column(Numeric(10, 4), default=1)

    # P&L fields from Zerodha
    realized_pnl = Column(Numeric(12, 2))
    unrealized_pnl = Column(Numeric(12, 2))
    pnl = Column(Numeric(12, 2))
    day_pnl = Column(Numeric(12, 2))
    m2m = Column(Numeric(15, 4))

    # Price fields
    last_price = Column(Numeric(12, 2))
    close_price = Column(Numeric(12, 2))

    # Value fields
    value = Column(Numeric(14, 2))
    buy_value = Column(Numeric(14, 2))
    sell_value = Column(Numeric(14, 2))

    # Day trading fields
    day_buy_quantity = Column(Integer, default=0)
    day_sell_quantity = Column(Integer, default=0)
    day_buy_price = Column(Numeric(15, 4))
    day_sell_price = Column(Numeric(15, 4))
    day_buy_value = Column(Numeric(15, 4))
    day_sell_value = Column(Numeric(15, 4))

    first_entry_time = Column(DateTime(timezone=True))
    last_entry_time = Column(DateTime(timezone=True))   # most recent BUY — for averaged-up positions
    last_exit_time = Column(DateTime(timezone=True))
    holding_duration_minutes = Column(Integer)
    order_ids = Column(ARRAY(String))
    status = Column(String(20), default='open')
    synced_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))