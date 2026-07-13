"""
ConstitutionHistory — audit of every constitution rule change (Q18, migration 065).

Answers: which rule version was active when violation N happened, and whether
a change was a mid-session loosening (itself a behavioral signal — §1C.3).
"""
import uuid
from sqlalchemy import Column, String, Boolean, TIMESTAMP, text, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.core.database import Base


class ConstitutionHistory(Base):
    __tablename__ = "constitution_history"
    __table_args__ = (
        Index("idx_constitution_history_broker", "broker_account_id", "changed_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    broker_account_id = Column(
        UUID(as_uuid=True),
        ForeignKey("broker_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )

    changed_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False)
    change_type = Column(String(20), nullable=False)  # initial | accept | tighten | loosen | pending_applied
    changes = Column(JSONB, nullable=False)           # {"field": {"old": x, "new": y}}
    effective_at = Column(TIMESTAMP(timezone=True), nullable=False)
    during_market_hours = Column(Boolean, nullable=False, default=False)
    override_flag = Column(Boolean, nullable=False, default=False)
