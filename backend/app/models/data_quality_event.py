"""
DataQualityEvent — stored data-quality observations (migration 070).

First producer: the FIFO-vs-broker P&L reconciliation in
trade_sync_service._reconcile_pnl_with_zerodha(). A >10% divergence between
our FIFO P&L and Zerodha's own position P&L (MCX/CDS) almost always means a
contract multiplier is missing from mcx_contract_specs.py — previously this
was a log line that vanished with the pod; now it is queryable.

Deduplication: a unique index on (broker_account_id, kind, tradingsymbol,
IST-date of detected_at) means one row per divergence per day, no matter how
many syncs run. Writers insert with ON CONFLICT DO NOTHING.

The table is generic (kind column) so future data-quality signals reuse it.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.core.database import Base


class DataQualityEvent(Base):
    __tablename__ = "data_quality_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    broker_account_id = Column(
        UUID(as_uuid=True),
        ForeignKey("broker_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind = Column(String(50), nullable=False)     # 'fifo_broker_divergence' | future kinds
    tradingsymbol = Column(String(100))
    exchange = Column(String(10))
    fifo_pnl = Column(Numeric(15, 4))
    broker_pnl = Column(Numeric(15, 4))
    ratio = Column(Numeric(10, 4))                # fifo_pnl / broker_pnl
    details = Column(JSONB, default=dict)
    detected_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "broker_account_id": str(self.broker_account_id),
            "kind": self.kind,
            "tradingsymbol": self.tradingsymbol,
            "exchange": self.exchange,
            "fifo_pnl": float(self.fifo_pnl) if self.fifo_pnl is not None else None,
            "broker_pnl": float(self.broker_pnl) if self.broker_pnl is not None else None,
            "ratio": float(self.ratio) if self.ratio is not None else None,
            "details": self.details or {},
            "detected_at": self.detected_at.isoformat() if self.detected_at else None,
        }
