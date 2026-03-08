import uuid
from sqlalchemy import Column, String, Numeric, Text, TIMESTAMP, text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base


class BehavioralEvent(Base):
    """
    Durable, queryable behavioral detection signal (Signal Layer).

    Append-only table — no updates except delivery_status and acknowledged_at.
    Events below confidence 0.70 must NOT be inserted (enforced in code + DB CHECK).

    Created by BehavioralEvaluator service, which runs AFTER data pipeline
    and NEVER mutates trades, positions, or P&L.

    Used by: behavior timeline UI, alert delivery, escalation, AI training,
    daily summaries, alert fatigue tuning.
    """
    __tablename__ = "behavioral_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    broker_account_id = Column(UUID(as_uuid=True), ForeignKey("broker_accounts.id", ondelete="CASCADE"), nullable=False, index=True)

    # Event classification
    event_type = Column(String(50), nullable=False)
    # Types: REVENGE_TRADING, OVERTRADING, TILT_SPIRAL, FOMO_ENTRY,
    #        LOSS_CHASING, NO_STOPLOSS, EARLY_EXIT, POSITION_SIZING,
    #        WINNING_STREAK_OVERCONFIDENCE, NO_COOLDOWN_AFTER_LOSS

    severity = Column(String(10), nullable=False)   # LOW, MEDIUM, HIGH
    confidence = Column(Numeric(3, 2), nullable=False)
    # DB CHECK: confidence >= 0.70
    # Code enforcement: HIGH requires >= 0.85, MEDIUM >= 0.75, LOW >= 0.70

    # Context
    trigger_trade_id = Column(UUID(as_uuid=True), ForeignKey("trades.id"), nullable=True)
    trigger_position_key = Column(String(200))  # "NIFTY25000CE:NFO:NRML:LONG"
    message = Column(Text, nullable=False)      # Human-readable explanation
    context = Column(JSONB)                     # Structured detection context
    # e.g. {"consecutive_losses": 4, "session_pnl": -5200,
    #       "time_since_last_loss_minutes": 3, "position_size_increase_pct": 150}

    # Session context (migration 039)
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("trading_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    risk_score_at_event = Column(Numeric(5, 2), nullable=True)
    account_equity_at_event = Column(Numeric(15, 4), nullable=True)
    position_exposure_at_event = Column(Numeric(15, 4), nullable=True)

    # Timing
    detected_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))

    # Delivery tracking
    delivery_status = Column(String(20), default='PENDING')  # PENDING, SENT, ACKNOWLEDGED
    acknowledged_at = Column(TIMESTAMP(timezone=True))

    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))

    # Relationships
    broker_account = relationship("BrokerAccount")
    trigger_trade = relationship("Trade", foreign_keys=[trigger_trade_id])
