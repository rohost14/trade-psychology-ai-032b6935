from sqlalchemy import Column, String, DateTime, Text, func
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base
import uuid


class AdminLoginEvent(Base):
    """Durable admin login history — one row per successful 2FA verify (migration 072)."""
    __tablename__ = "admin_login_events"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    admin_id    = Column(UUID(as_uuid=True), nullable=False, index=True)
    admin_email = Column(Text, nullable=False)
    ip          = Column(Text, nullable=True)
    user_agent  = Column(Text, nullable=True)
    method      = Column(Text, nullable=False)   # email_otp | totp | dev_bypass
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
