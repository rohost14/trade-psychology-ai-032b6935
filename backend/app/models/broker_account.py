from sqlalchemy import String, TIMESTAMP, text, UUID, ARRAY, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from cryptography.fernet import Fernet, InvalidToken
import uuid
from datetime import datetime, timezone
from typing import List, Optional, TYPE_CHECKING
from app.core.database import Base
from app.core.config import settings

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.push_subscription import PushSubscription

class BrokerAccount(Base):
    __tablename__ = "broker_accounts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # FK to users.id — NOT NULL after migration 032
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    broker_name: Mapped[str] = mapped_column(String, default="zerodha")
    access_token: Mapped[str] = mapped_column(String, nullable=True)
    refresh_token: Mapped[str] = mapped_column(String, nullable=True)
    api_key: Mapped[str] = mapped_column(String, nullable=True)
    api_secret_enc: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String)
    connected_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    last_sync_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    broker_user_id: Mapped[str] = mapped_column(String, nullable=True)
    broker_email: Mapped[str] = mapped_column(String, nullable=True)

    # Kite-specific fields
    user_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    exchanges: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)
    products: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)
    order_types: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)
    meta: Mapped[Optional[dict]] = mapped_column(JSONB, default={})
    avatar_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    demat_consent: Mapped[bool] = mapped_column(default=False)
    sync_status: Mapped[str] = mapped_column(String(20), default="pending")
    token_revoked_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="broker_accounts")
    push_subscriptions: Mapped[List["PushSubscription"]] = relationship(
        "PushSubscription", back_populates="broker_account", cascade="all, delete-orphan"
    )

    @staticmethod
    def _get_fernet():
        return Fernet(settings.ENCRYPTION_KEY.encode())

    def encrypt_token(self, token: str) -> str:
        f = self._get_fernet()
        return f.encrypt(token.encode()).decode()

    def decrypt_token(self, encrypted_token: str) -> str:
        try:
            f = self._get_fernet()
            return f.decrypt(encrypted_token.encode()).decode()
        except (InvalidToken, Exception) as e:
            raise ValueError(
                "Failed to decrypt access token — ENCRYPTION_KEY may have changed or token is corrupted. "
                "Please reconnect your Zerodha account."
            ) from e

    def decrypt_api_secret(self) -> Optional[str]:
        """Return plaintext api_secret, or None if not stored (use global credentials)."""
        if not self.api_secret_enc:
            return None
        try:
            f = self._get_fernet()
            return f.decrypt(self.api_secret_enc.encode()).decode()
        except (InvalidToken, Exception):
            return None

    @staticmethod
    def encrypt_api_secret(api_secret: str) -> str:
        f = Fernet(settings.ENCRYPTION_KEY.encode())
        return f.encrypt(api_secret.encode()).decode()
