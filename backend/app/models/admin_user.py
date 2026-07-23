from sqlalchemy import Column, String, Boolean, DateTime, Text, Integer
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

    # ── IAM (migration 071) ──────────────────────────────────────────────────
    # Bumped to invalidate ALL of this admin's JWTs (force-logout / deactivate /
    # role change / password reset). Embedded in the JWT as `sv`; deps rejects a
    # mismatch. Default 0 == tokens issued before this column existed still valid.
    session_epoch        = Column(Integer, nullable=False, default=0, server_default="0")
    must_change_password = Column(Boolean, nullable=False, default=False, server_default="false")
    totp_required        = Column(Boolean, nullable=False, default=False, server_default="false")
    created_by           = Column(String(255), nullable=True)
