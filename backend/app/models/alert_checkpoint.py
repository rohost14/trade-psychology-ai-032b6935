"""
AlertCheckpoint Model

Stores real counterfactual P&L data for danger/critical alerts.
When an alert fires, we snapshot the trigger instrument's open position + LTP.
At T+5, T+30, and T+60 minutes we fetch live prices to compute:
  money_saved = user_actual_pnl - counterfactual_pnl_at_t30
"""

from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import Column, String, DateTime, ForeignKey, Numeric, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.core.database import Base


class AlertCheckpoint(Base):
    __tablename__ = "alert_checkpoints"
    __table_args__ = (
        Index('idx_ac_alert_id', 'alert_id'),
        Index('idx_ac_broker_created', 'broker_account_id', 'created_at'),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    alert_id = Column(
        UUID(as_uuid=True),
        ForeignKey("risk_alerts.id", ondelete="CASCADE"),
        nullable=False,
    )
    broker_account_id = Column(
        UUID(as_uuid=True),
        ForeignKey("broker_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Snapshot at alert time (single trigger instrument position)
    positions_snapshot = Column(JSONB, default=list)
    total_unrealized_pnl = Column(Numeric(15, 4), default=0)

    # T+5 check
    prices_at_t5 = Column(JSONB, nullable=True)
    pnl_at_t5 = Column(Numeric(15, 4), nullable=True)
    checked_at_t5 = Column(DateTime(timezone=True), nullable=True)

    # T+30 check (primary counterfactual)
    prices_at_t30 = Column(JSONB, nullable=True)
    pnl_at_t30 = Column(Numeric(15, 4), nullable=True)
    checked_at_t30 = Column(DateTime(timezone=True), nullable=True)

    # T+60 check (final)
    prices_at_t60 = Column(JSONB, nullable=True)
    pnl_at_t60 = Column(Numeric(15, 4), nullable=True)
    checked_at_t60 = Column(DateTime(timezone=True), nullable=True)

    # Outcome
    user_actual_pnl = Column(Numeric(15, 4), nullable=True)
    money_saved = Column(Numeric(15, 4), nullable=True)

    # pending | calculating | complete | no_positions | error
    calculation_status = Column(String(20), default="pending", nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    def __repr__(self):
        return f"<AlertCheckpoint {self.id} alert={self.alert_id} status={self.calculation_status}>"

    def to_dict(self):
        return {
            "id": str(self.id),
            "alert_id": str(self.alert_id),
            "broker_account_id": str(self.broker_account_id),
            "positions_snapshot": self.positions_snapshot or [],
            "total_unrealized_pnl": float(self.total_unrealized_pnl or 0),
            "prices_at_t5": self.prices_at_t5,
            "pnl_at_t5": float(self.pnl_at_t5) if self.pnl_at_t5 is not None else None,
            "checked_at_t5": self.checked_at_t5.isoformat() if self.checked_at_t5 else None,
            "prices_at_t30": self.prices_at_t30,
            "pnl_at_t30": float(self.pnl_at_t30) if self.pnl_at_t30 is not None else None,
            "checked_at_t30": self.checked_at_t30.isoformat() if self.checked_at_t30 else None,
            "prices_at_t60": self.prices_at_t60,
            "pnl_at_t60": float(self.pnl_at_t60) if self.pnl_at_t60 is not None else None,
            "checked_at_t60": self.checked_at_t60.isoformat() if self.checked_at_t60 else None,
            "user_actual_pnl": float(self.user_actual_pnl) if self.user_actual_pnl is not None else None,
            "money_saved": float(self.money_saved) if self.money_saved is not None else None,
            "calculation_status": self.calculation_status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
