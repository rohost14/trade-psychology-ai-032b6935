import uuid
from sqlalchemy import Column, String, Integer, Numeric, Text, TIMESTAMP, text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


class IncompletePosition(Base):
    """
    Flags sync gaps where FIFO has unmatched fills but broker says position is flat.

    Detected automatically during FIFO processing. Prompts the user to resolve
    via manual entry or CSV upload.

    Reports exclude incomplete positions but reference them in narrative insights.
    """
    __tablename__ = "incomplete_positions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    broker_account_id = Column(UUID(as_uuid=True), ForeignKey("broker_accounts.id", ondelete="CASCADE"), nullable=False, index=True)

    # Instrument
    tradingsymbol = Column(String(100), nullable=False)
    exchange = Column(String(20), nullable=False)
    product = Column(String(20))

    # What we know from unmatched fills
    direction = Column(String(10))             # LONG or SHORT
    unmatched_quantity = Column(Integer)        # Qty in FIFO queue with no closing fills
    avg_entry_price = Column(Numeric(15, 4))   # From unmatched opening fills
    entry_time = Column(TIMESTAMP(timezone=True))  # Earliest unmatched fill

    # Detection
    reason = Column(String(50), nullable=False)    # SYNC_GAP, POSITION_MISMATCH
    detected_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))
    details = Column(Text)                         # Human-readable explanation

    # Resolution
    resolution_status = Column(String(20), default='PENDING')  # PENDING, RESOLVED, IGNORED
    resolved_at = Column(TIMESTAMP(timezone=True))
    resolution_method = Column(String(50))         # MANUAL_ENTRY, CSV_IMPORT, IGNORED

    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))

    # Relationships
    broker_account = relationship("BrokerAccount")
