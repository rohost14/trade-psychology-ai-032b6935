from sqlalchemy import Column, String, DateTime, ForeignKey, ARRAY
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid

from app.core.database import Base

class RiskAlert(Base):
    __tablename__ = "risk_alerts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    broker_account_id = Column(UUID(as_uuid=True), ForeignKey("broker_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    
    pattern_type = Column(String, nullable=False)
    severity = Column(String, nullable=False)
    
    message = Column(String, nullable=False)
    details = Column(JSONB)
    
    trigger_trade_id = Column(UUID(as_uuid=True), ForeignKey("trades.id", ondelete="SET NULL"))
    related_trade_ids = Column(ARRAY(UUID(as_uuid=True)))
    
    detected_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    acknowledged_at = Column(DateTime(timezone=True))
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    broker_account = relationship("BrokerAccount")
    trigger_trade = relationship("Trade", foreign_keys=[trigger_trade_id])
