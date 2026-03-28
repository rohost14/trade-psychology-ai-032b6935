from sqlalchemy import Column, String, DateTime, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.core.database import Base
import uuid


class AdminAuditLog(Base):
    __tablename__ = "admin_audit_log"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    admin_email = Column(String(255), nullable=False, index=True)
    action      = Column(String(100), nullable=False, index=True)
    target_type = Column(String(50),  nullable=True)
    target_id   = Column(String(255), nullable=True)
    details     = Column(JSONB,       nullable=True)
    created_at  = Column(DateTime(timezone=True), server_default=text("now()"))
