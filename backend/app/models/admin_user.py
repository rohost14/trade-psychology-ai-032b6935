from sqlalchemy import Column, String, Boolean, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base
import uuid


class AdminUser(Base):
    __tablename__ = "admin_users"

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email            = Column(String(255), unique=True, nullable=False, index=True)
    password_hash    = Column(String(255), nullable=False)
    name             = Column(String(255), nullable=False)
    role             = Column(String(50), nullable=False, default="superadmin")
    is_active        = Column(Boolean, default=True)
    totp_secret_enc  = Column(Text, nullable=True)  # Fernet-encrypted pyotp secret; NULL = email OTP
    created_at       = Column(DateTime(timezone=True))
    last_login_at    = Column(DateTime(timezone=True), nullable=True)
