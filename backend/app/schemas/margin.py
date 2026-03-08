from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID


class MarginSnapshotBase(BaseModel):
    # Equity segment
    equity_available: Optional[float] = None
    equity_used: Optional[float] = None
    equity_total: Optional[float] = None
    equity_utilization_pct: Optional[float] = None

    # Commodity segment
    commodity_available: Optional[float] = None
    commodity_used: Optional[float] = None
    commodity_total: Optional[float] = None
    commodity_utilization_pct: Optional[float] = None

    # Overall metrics
    max_utilization_pct: Optional[float] = None
    risk_level: Optional[str] = None

    # Breakdown (JSONB)
    equity_breakdown: Optional[Dict[str, Any]] = {}
    commodity_breakdown: Optional[Dict[str, Any]] = {}


class MarginSnapshotCreate(MarginSnapshotBase):
    broker_account_id: UUID


class MarginSnapshotResponse(MarginSnapshotBase):
    id: UUID
    broker_account_id: UUID
    snapshot_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
