"""
Cooldown Model

Tracks cooling-off periods after risky behavior is detected.
Traders can optionally skip cooldowns after acknowledgment.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4
from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.core.database import Base


class Cooldown(Base):
    """
    Active cooldown period for a trader.

    Created when:
    - Pattern detected (revenge trading, loss spiral)
    - Daily loss limit hit
    - Manual request (trader wants a break)
    """
    __tablename__ = "cooldowns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    broker_account_id = Column(
        UUID(as_uuid=True),
        ForeignKey("broker_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Cooldown details
    reason = Column(String(50), nullable=False)  # 'revenge_pattern', 'loss_limit', 'consecutive_loss', 'manual', 'overtrading'
    duration_minutes = Column(Integer, nullable=False, default=15)

    # Timing
    started_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)

    # Can trader skip this cooldown?
    can_skip = Column(Boolean, default=True)
    skipped = Column(Boolean, default=False)
    skipped_at = Column(DateTime(timezone=True), nullable=True)

    # Acknowledgment
    acknowledged = Column(Boolean, default=False)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)

    # Context
    trigger_alert_id = Column(UUID(as_uuid=True), nullable=True)  # Alert that triggered this
    message = Column(String(500), nullable=True)  # Custom message to show
    meta_data = Column(JSONB, default=dict)  # Additional context

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    def __repr__(self):
        return f"<Cooldown {self.id} reason={self.reason}>"

    @property
    def is_active(self) -> bool:
        """Check if cooldown is still active."""
        if self.skipped:
            return False
        return datetime.now(timezone.utc) < self.expires_at

    @property
    def remaining_minutes(self) -> int:
        """Get remaining minutes in cooldown."""
        if not self.is_active:
            return 0
        remaining = self.expires_at - datetime.now(timezone.utc)
        return max(0, int(remaining.total_seconds() / 60))

    @property
    def remaining_seconds(self) -> int:
        """Get remaining seconds in cooldown."""
        if not self.is_active:
            return 0
        remaining = self.expires_at - datetime.now(timezone.utc)
        return max(0, int(remaining.total_seconds()))

    def to_dict(self):
        return {
            "id": str(self.id),
            "broker_account_id": str(self.broker_account_id),
            "reason": self.reason,
            "duration_minutes": self.duration_minutes,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_active": self.is_active,
            "remaining_minutes": self.remaining_minutes,
            "remaining_seconds": self.remaining_seconds,
            "can_skip": self.can_skip,
            "skipped": self.skipped,
            "acknowledged": self.acknowledged,
            "message": self.message,
            "meta_data": self.meta_data or {},
        }


def create_cooldown(
    broker_account_id,
    reason: str,
    duration_minutes: int = 15,
    can_skip: bool = True,
    message: str = None,
    trigger_alert_id = None,
    meta_data: dict = None
) -> Cooldown:
    """Factory function to create a cooldown with proper expiry."""
    return Cooldown(
        broker_account_id=broker_account_id,
        reason=reason,
        duration_minutes=duration_minutes,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=duration_minutes),
        can_skip=can_skip,
        message=message or get_default_message(reason),
        trigger_alert_id=trigger_alert_id,
        meta_data=meta_data or {}
    )


def get_default_message(reason: str) -> str:
    """Get default cooldown message for a reason."""
    messages = {
        "revenge_pattern": "Take a breather. Revenge trading detected. Wait before your next trade.",
        "loss_limit": "You've hit your daily loss limit. Consider stopping for today.",
        "consecutive_loss": "3+ consecutive losses. Step back and reassess.",
        "overtrading": "You're trading too frequently. Quality over quantity.",
        "manual": "You requested a trading break. Take this time to review.",
        "tilt": "Signs of emotional trading detected. Clear your head first.",
        "fomo": "FOMO detected. The market will still be there later.",
    }
    return messages.get(reason, "Taking a short break can help you trade better.")
