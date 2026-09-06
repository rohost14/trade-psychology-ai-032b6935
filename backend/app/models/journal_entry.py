"""
Trade Journal Entry Model

Stores trader's notes and structured reflections on individual trades.
Optional feature - traders can add context to their trades for later review.
"""

from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Integer, SmallInteger
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
    - A specific position (source_position_id, added in migration 094)
    - Or stand-alone (daily reflection)

    Structured fields (migration 045) replace the old 3-textarea approach.
    Quick-select inputs = near-zero friction + machine-readable data for analytics.
    """
    __tablename__ = "journal_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    broker_account_id = Column(
        UUID(as_uuid=True),
        ForeignKey("broker_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # The journal KEY, not a foreign key — and deliberately so.
    #
    # For a CLOSED trade this is the CompletedTrade id. For an OPEN position it
    # is a SYNTHETIC per-episode id that exists in no table, derived in
    # src/lib/journalKey.ts from (position id + IST trading date): a Position
    # row is reused across episodes and keeps its id, so keying by the raw
    # position id would let a future unrelated position on the same contract
    # inherit an old entry.
    #
    # An FK here is therefore impossible, not merely absent. Use
    # source_position_id to reach the real position.
    trade_id = Column(
        UUID(as_uuid=True),
        nullable=True,
        index=True
    )

    # The real position an open-position entry was written about (migration
    # 094). The client sends it as `source_id` and the API already verified
    # ownership with it; before 094 it was then discarded, leaving the entry
    # joinable to nothing.
    #
    # ON DELETE SET NULL, never CASCADE: a journal entry is the trader's own
    # writing and deleting a position must not delete what they wrote about it.
    #
    # NULL for closed-trade entries and for everything written before 094 — the
    # value was never stored, so it cannot be recovered.
    source_position_id = Column(
        UUID(as_uuid=True),
        ForeignKey("positions.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # Quick emotion tags (for analytics)
    emotion_tags = Column(JSONB, default=list)  # List of EmotionTag values

    # ── Structured fields (migration 045) ─────────────────────────────────
    # Did the trader follow their plan?
    followed_plan = Column(String(20), nullable=True)     # 'yes' | 'partially' | 'no'
    # Why did they deviate? (populated when followed_plan != 'yes')
    deviation_reason = Column(String(50), nullable=True)  # 'fomo' | 'revenge' | 'overconfident' | 'bored' | 'impulse' | 'other'
    # How did the trade exit?
    exit_reason = Column(String(50), nullable=True)       # 'sl_hit' | 'target_hit' | 'trailed_stop' | 'manual' | 'panic' | 'news'
    # Subjective setup quality rating (1 = terrible, 5 = textbook)
    setup_quality = Column(SmallInteger, nullable=True)   # 1–5
    # Would they take this exact trade again?
    would_repeat = Column(String(10), nullable=True)      # 'yes' | 'maybe' | 'no'
    # Market condition at time of trade
    market_condition = Column(String(20), nullable=True)  # 'trending' | 'ranging' | 'volatile' | 'choppy' | 'news_driven'
    # ──────────────────────────────────────────────────────────────────────

    # Optional free-text notes (single field — replaces old notes/emotions/lessons trio)
    notes = Column(Text, nullable=True)

    # Trade context (captured at time of journal entry)
    trade_symbol = Column(String(100), nullable=True)
    trade_type = Column(String(10), nullable=True)   # BUY/SELL/LONG/SHORT
    trade_pnl = Column(String(50), nullable=True)    # Stored as string for flexibility

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
            "source_position_id": (str(self.source_position_id)
                                   if self.source_position_id else None),
            "emotion_tags": self.emotion_tags or [],
            "followed_plan": self.followed_plan,
            "deviation_reason": self.deviation_reason,
            "exit_reason": self.exit_reason,
            "setup_quality": self.setup_quality,
            "would_repeat": self.would_repeat,
            "market_condition": self.market_condition,
            "notes": self.notes,
            "trade_symbol": self.trade_symbol,
            "trade_type": self.trade_type,
            "trade_pnl": self.trade_pnl,
            "entry_type": self.entry_type,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
