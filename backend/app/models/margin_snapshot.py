"""
Margin Snapshot Model

Stores historical margin utilization for trend analysis.
"""

import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Numeric, TIMESTAMP, text, ForeignKey, UUID
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class MarginSnapshot(Base):
    __tablename__ = "margin_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    broker_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("broker_accounts.id", ondelete="CASCADE"), nullable=False, index=True)

    # Timestamp
    snapshot_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))

    # Equity segment
    equity_available: Mapped[Optional[float]] = mapped_column(Numeric(15, 4), nullable=True)
    equity_used: Mapped[Optional[float]] = mapped_column(Numeric(15, 4), nullable=True)
    equity_total: Mapped[Optional[float]] = mapped_column(Numeric(15, 4), nullable=True)
    equity_utilization_pct: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)

    # Commodity segment
    commodity_available: Mapped[Optional[float]] = mapped_column(Numeric(15, 4), nullable=True)
    commodity_used: Mapped[Optional[float]] = mapped_column(Numeric(15, 4), nullable=True)
    commodity_total: Mapped[Optional[float]] = mapped_column(Numeric(15, 4), nullable=True)
    commodity_utilization_pct: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)

    # Overall metrics
    max_utilization_pct: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    risk_level: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Breakdown (JSONB for flexibility)
    equity_breakdown: Mapped[Optional[dict]] = mapped_column(JSONB, default={})
    commodity_breakdown: Mapped[Optional[dict]] = mapped_column(JSONB, default={})

    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))

    # Relationship
    broker_account = relationship("BrokerAccount")
