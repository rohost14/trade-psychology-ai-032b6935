"""
Per-position broker margin observation.

Append-only. A margin figure is an observation of a fact at a moment; it is
never updated and never recomputed, because volatility moves and a later
estimate would silently rewrite what the broker actually required.

Distinct from `MarginSnapshot`, which is ACCOUNT-level utilisation from
`kite.margins()` and cannot answer "what did this position require".

Migration 081. Every reader must tolerate the table being absent — see
`broker_margin_service`.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    TIMESTAMP, ForeignKey, Integer, Numeric, String, UUID, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PositionMarginObservation(Base):
    __tablename__ = "position_margin_observations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    broker_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("broker_accounts.id", ondelete="CASCADE"),
        nullable=False, index=True)

    #: When the broker was asked. The figure means nothing without it.
    captured_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"))

    exchange: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    underlying: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    product: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    leg_count: Mapped[int] = mapped_column(Integer, default=1)
    #: The exact payload sent to Kite, so the observation stays explainable.
    legs: Mapped[list] = mapped_column(JSONB, default=list)

    span: Mapped[Optional[float]] = mapped_column(Numeric(18, 4), nullable=True)
    exposure: Mapped[Optional[float]] = mapped_column(Numeric(18, 4), nullable=True)
    option_premium: Mapped[Optional[float]] = mapped_column(Numeric(18, 4), nullable=True)
    additional: Mapped[Optional[float]] = mapped_column(Numeric(18, 4), nullable=True)
    total: Mapped[Optional[float]] = mapped_column(Numeric(18, 4), nullable=True)

    #: Per-leg margins keyed by tradingsymbol. A detector reasons about ONE
    #: trade while margin is a property of the structure, so both are kept.
    per_leg: Mapped[dict] = mapped_column(JSONB, default=dict)

    #: 'basket' = spread benefit applied across legs; 'orders' = legs charged
    #: independently. On a hedged position these differ by a factor of three.
    basis: Mapped[str] = mapped_column(String(16), default="basket")
    margin_source: Mapped[str] = mapped_column(String(16), default="broker")

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"))
