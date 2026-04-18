"""
User model — the stable identity above broker accounts.

One user can have multiple broker accounts (Zerodha, ICICI, etc.).
Identity key is email (from broker OAuth profile, KYC-verified).
Guardian contact lives here — it belongs to the human, not the broker connection.
"""

from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import String, TIMESTAMP, Boolean, Numeric, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.broker_account import BrokerAccount


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Primary identity — KYC-verified email from broker OAuth
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)

    # Profile display fields (populated from broker profile at OAuth time)
    display_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Guardian contact — belongs to the human, survives broker reconnects
    guardian_phone: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    guardian_name:  Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # Guardian confirmed (migration 056): True after guardian replies YES to consent WhatsApp
    guardian_confirmed:    Mapped[Optional[bool]]     = mapped_column(Boolean, nullable=True, default=False)
    guardian_confirmed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    guardian_loss_limit:   Mapped[Optional[float]]    = mapped_column(Numeric(15, 4), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )

    # Relationships
    broker_accounts: Mapped[List["BrokerAccount"]] = relationship(
        "BrokerAccount", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User {self.id} email={self.email}>"
