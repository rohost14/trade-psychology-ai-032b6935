import uuid
from sqlalchemy import Column, Integer, Boolean, Numeric, TIMESTAMP, text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


class CompletedTradeFeature(Base):
    """
    ML-ready feature vector derived from a CompletedTrade.

    Computed post-FIFO as a separate step (not during FIFO matching).
    One-to-one with CompletedTrade. Rebuildable from completed_trades data.

    Used by: pattern_prediction_service, ai_personalization_service, clustering.
    """
    __tablename__ = "completed_trade_features"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    completed_trade_id = Column(
        UUID(as_uuid=True),
        ForeignKey("completed_trades.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    broker_account_id = Column(UUID(as_uuid=True), ForeignKey("broker_accounts.id", ondelete="CASCADE"), nullable=False, index=True)

    # Timing features
    holding_duration_minutes = Column(Integer)
    entry_hour_ist = Column(Integer)           # 0-23
    exit_hour_ist = Column(Integer)            # 0-23
    entry_day_of_week = Column(Integer)        # 0=Mon, 6=Sun
    is_expiry_day = Column(Boolean, default=False)

    # Sizing features
    size_relative_to_avg = Column(Numeric(10, 4))   # qty / avg of recent 20 rounds
    is_scaled_entry = Column(Boolean, default=False) # num_entries > 1
    is_scaled_exit = Column(Boolean, default=False)  # num_exits > 1

    # Context features
    entry_after_loss = Column(Boolean, default=False)        # previous round was a loss
    consecutive_loss_count = Column(Integer, default=0)      # losses in a row before this
    session_pnl_at_entry = Column(Numeric(15, 4), default=0) # session realized P&L at round start
    minutes_since_last_round = Column(Integer)               # gap from previous round exit

    # Outcome features
    is_winner = Column(Boolean, default=False)
    pnl_per_unit = Column(Numeric(15, 4))     # realized_pnl / total_quantity

    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))

    # Relationships
    completed_trade = relationship("CompletedTrade", back_populates="feature")
