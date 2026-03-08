"""
Trade Journal Entry Model

Stores trader's notes, emotions, and lessons for individual trades.
Optional feature - traders can add context to their trades for later review.
"""

from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
import enum

from app.core.database import Base


class EmotionTag(str, enum.Enum):
    """Pre-defined emotion tags for quick selection."""
    CONFIDENT = "confident"
    ANXIOUS = "anxious"
    FOMO = "fomo"
    GREEDY = "greedy"
    FEARFUL = "fearful"
    REVENGE = "revenge"
    CALM = "calm"
    IMPATIENT = "impatient"
    EXCITED = "excited"
    FRUSTRATED = "frustrated"
    NEUTRAL = "neutral"


class JournalEntry(Base):
    """
    Trade journal entry - optional notes/reflections on trades.

    Can be attached to:
    - A specific trade (trade_id)
    - A specific position (position_id)
    - Or stand-alone (daily reflection)
    """
    __tablename__ = "journal_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    broker_account_id = Column(
        UUID(as_uuid=True),
        ForeignKey("broker_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Links to completed_trades.id (or trades.id for legacy entries).
    # Stored as a plain UUID — no FK constraint so either table's ID works.
    trade_id = Column(
        UUID(as_uuid=True),
        nullable=True,
        index=True
    )

    # Journal content
    notes = Column(Text, nullable=True)  # General trade notes/thesis
    emotions = Column(Text, nullable=True)  # Free-text emotional state
    lessons = Column(Text, nullable=True)  # Key lessons learned

    # Quick emotion tags (for analytics)
    emotion_tags = Column(JSONB, default=list)  # List of EmotionTag values

    # Trade context (captured at time of journal entry)
    trade_symbol = Column(String(100), nullable=True)
    trade_type = Column(String(10), nullable=True)  # BUY/SELL
    trade_pnl = Column(String(50), nullable=True)  # Stored as string for flexibility

    # Entry type
    entry_type = Column(
        String(20),
        default="trade",
        nullable=False
    )  # 'trade', 'daily', 'weekly', 'custom'

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<JournalEntry {self.id} trade={self.trade_id}>"

    def to_dict(self):
        """Convert to dictionary for API response."""
        return {
            "id": str(self.id),
            "broker_account_id": str(self.broker_account_id),
            "trade_id": str(self.trade_id) if self.trade_id else None,
            "notes": self.notes,
            "emotions": self.emotions,
            "lessons": self.lessons,
            "emotion_tags": self.emotion_tags or [],
            "trade_symbol": self.trade_symbol,
            "trade_type": self.trade_type,
            "trade_pnl": self.trade_pnl,
            "entry_type": self.entry_type,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
