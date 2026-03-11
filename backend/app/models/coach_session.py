import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, TIMESTAMP, text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class CoachSession(Base):
    """
    One conversation session with the AI coach.
    Messages accumulate during the session.
    Summary is generated and stored for context injection in future sessions.
    """
    __tablename__ = "coach_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    broker_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("broker_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    messages: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    summary: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    started_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )

    broker_account = relationship("BrokerAccount")
