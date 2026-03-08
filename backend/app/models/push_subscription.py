"""
Push Subscription Model

Stores Web Push API subscriptions for browser notifications.
"""

from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean, Text, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class PushSubscription(Base):
    """
    Stores push notification subscriptions.

    Each browser/device gets a unique subscription endpoint.
    One user can have multiple subscriptions (desktop + mobile).
    """
    __tablename__ = "push_subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    broker_account_id = Column(
        UUID(as_uuid=True),
        ForeignKey("broker_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Web Push subscription data
    endpoint = Column(Text, nullable=False, unique=True)
    p256dh_key = Column(String(255), nullable=False)  # Public key
    auth_key = Column(String(255), nullable=False)    # Auth secret

    # Device info (optional)
    user_agent = Column(String(500), nullable=True)
    device_type = Column(String(50), nullable=True)  # 'desktop', 'mobile', 'tablet'

    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    failed_count = Column(Integer, default=0)  # Track failed deliveries

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    broker_account = relationship("BrokerAccount", back_populates="push_subscriptions")

    def __repr__(self):
        return f"<PushSubscription {self.id} account={self.broker_account_id}>"

    def to_dict(self):
        """Convert to dictionary for web-push library."""
        return {
            "endpoint": self.endpoint,
            "keys": {
                "p256dh": self.p256dh_key,
                "auth": self.auth_key
            }
        }
