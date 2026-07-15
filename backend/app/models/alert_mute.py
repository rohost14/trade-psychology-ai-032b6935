"""
AlertMute — per-account muted behavioral patterns (migration 069).

A muted pattern STILL generates its RiskAlert (mirror philosophy — the evidence
is never hidden; it stays visible in History). Muting only suppresses the
real-time PUSH notification and the in-app TOAST for that pattern.

The number of simultaneously active mutes is capped in the API
(MAX_ACTIVE_MUTES) — a user must not be able to mute every pattern, which would
defeat the point of the app.
"""
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timezone

from app.core.database import Base


class AlertMute(Base):
    __tablename__ = "alert_mutes"

    broker_account_id = Column(
        UUID(as_uuid=True),
        ForeignKey("broker_accounts.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    pattern_type = Column(String, primary_key=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
