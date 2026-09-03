"""
Immutable monthly summary, written before an `orders` partition may be dropped.

See migration 091 for why this exists and, more importantly, for what it does
and does not rescue: trades, P&L, violations and detector events live in tables
that are NOT under retention, so what this genuinely preserves is the
order-level record — order counts, cancellations, rejections, and the
protective-stop evidence F4 reads.
"""
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Column, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.core.database import Base


class MonthlySnapshot(Base):
    __tablename__ = "monthly_snapshots"
    __table_args__ = (
        UniqueConstraint("broker_account_id", "month",
                         name="uq_monthly_snapshot_account_month"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    broker_account_id = Column(
        UUID(as_uuid=True),
        ForeignKey("broker_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    #: First day of the month, IST.
    month = Column(Date, nullable=False)
    metrics = Column(JSONB, nullable=False, default=dict)
    snapshot_version = Column(Integer, nullable=False, default=1)
    detector_version = Column(String, nullable=True)
    #: Set once the month's orders partition has actually been dropped.
    orders_pruned_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))

    def to_dict(self) -> dict:
        return {
            "month": self.month.isoformat() if self.month else None,
            "metrics": self.metrics or {},
            "snapshot_version": self.snapshot_version,
            "detector_version": self.detector_version,
            "orders_pruned_at": (
                self.orders_pruned_at.isoformat() if self.orders_pruned_at else None
            ),
        }
