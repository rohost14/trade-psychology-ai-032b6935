import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, Numeric, Integer, TIMESTAMP, text, ForeignKey, ARRAY
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


class GuardrailRule(Base):
    """
    User-defined alert rule on open positions.

    Fires once when condition is met (status → 'triggered').
    Never re-arms — create a new rule if needed.
    Expires at 15:30 IST on creation day.
    """
    __tablename__ = "guardrail_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    broker_account_id = Column(
        UUID(as_uuid=True),
        ForeignKey("broker_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    name = Column(String(100), nullable=False)

    # NULL = watch all open positions for this account
    target_symbols = Column(ARRAY(String), nullable=True)

    # loss_threshold | loss_range_time | total_pnl_drop | profit_target
    condition_type = Column(String(50), nullable=False)
    condition_value = Column(Numeric(15, 2), nullable=False)

    notify_whatsapp = Column(Boolean, nullable=False, default=True)
    notify_push = Column(Boolean, nullable=False, default=True)

    # active → triggered (once, done) | active → paused → active
    status = Column(String(20), nullable=False, default="active")
    triggered_at = Column(TIMESTAMP(timezone=True), nullable=True)
    trigger_count = Column(Integer, nullable=False, default=0)

    expires_at = Column(TIMESTAMP(timezone=True), nullable=False)

    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))

    broker_account = relationship("BrokerAccount")
