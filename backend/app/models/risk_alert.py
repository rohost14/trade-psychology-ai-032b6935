from sqlalchemy import Column, String, DateTime, ForeignKey, ARRAY, Index, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid

from app.core.database import Base

class RiskAlert(Base):
    __tablename__ = "risk_alerts"
    __table_args__ = (
        Index('idx_risk_alerts_broker_detected', 'broker_account_id', 'detected_at'),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    broker_account_id = Column(UUID(as_uuid=True), ForeignKey("broker_accounts.id", ondelete="CASCADE"), nullable=False)

    pattern_type = Column(String, nullable=False)
    # severity ∈ ('info', 'caution', 'danger', 'critical') — migration 063
    severity = Column(String, nullable=False)

    message = Column(String, nullable=False)
    details = Column(JSONB)

    # Legacy: FKs trades(id) (raw fills), was never populated. Kept for old rows.
    trigger_trade_id = Column(UUID(as_uuid=True), ForeignKey("trades.id", ondelete="SET NULL"))
    related_trade_ids = Column(ARRAY(UUID(as_uuid=True)))

    # Engine v2 Phase 0 (migration 063)
    trigger_completed_trade_id = Column(UUID(as_uuid=True), ForeignKey("completed_trades.id", ondelete="SET NULL"))
    detector_version = Column(String(20), nullable=False, default="1.0.0")
    confidence = Column(Numeric(5, 2))  # 0-100 detection certainty, independent of severity

    # detected_at = the TRADE's time (exit_time of the triggering CompletedTrade),
    # never the sync/processing time. created_at records when the row was written.
    detected_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    acknowledged_at = Column(DateTime(timezone=True))

    # Feedback loop (migration 069): what the user actually did about this alert.
    # outcome ∈ ('stopped', 'took_anyway', 'not_useful'); NULL = no feedback yet.
    # Enables a real "alerts that changed behaviour" metric (vs merely "seen").
    outcome = Column(String, nullable=True)
    outcome_at = Column(DateTime(timezone=True), nullable=True)

    # Delivery state machine (migration 038)
    delivered_push_at = Column(DateTime(timezone=True), nullable=True)
    delivered_whatsapp_at = Column(DateTime(timezone=True), nullable=True)
    expired_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    broker_account = relationship("BrokerAccount")
    trigger_trade = relationship("Trade", foreign_keys=[trigger_trade_id])
