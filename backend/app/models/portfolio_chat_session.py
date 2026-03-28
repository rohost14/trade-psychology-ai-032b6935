import uuid
from sqlalchemy import Column, String, Integer, TIMESTAMP, text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base


class PortfolioChatSession(Base):
    """
    Portfolio AI Chat conversation history.

    One row per conversation session.
    On next visit: inject last messages as context + show flashback card.
    Messages capped at 30 to keep storage bounded.
    """
    __tablename__ = "portfolio_chat_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    broker_account_id = Column(
        UUID(as_uuid=True),
        ForeignKey("broker_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Short human-readable description of the conversation topics
    summary = Column(String(500), nullable=True)

    # [{role: "user"|"assistant", content: str, timestamp: ISO str}]
    messages = Column(JSONB, nullable=False, default=list)

    message_count = Column(Integer, nullable=False, default=0)

    started_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))
    ended_at = Column(TIMESTAMP(timezone=True), nullable=True)

    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))

    broker_account = relationship("BrokerAccount")
