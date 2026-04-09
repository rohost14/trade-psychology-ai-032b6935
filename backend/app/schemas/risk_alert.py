from pydantic import BaseModel, ConfigDict, computed_field
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID

class RiskAlertBase(BaseModel):
    pattern_type: str
    severity: str
    message: str
    details: Optional[Dict[str, Any]] = None

class RiskAlertResponse(RiskAlertBase):
    id: UUID
    broker_account_id: UUID
    trigger_trade_id: Optional[UUID] = None
    related_trade_ids: Optional[List[UUID]] = None
    detected_at: datetime
    acknowledged_at: Optional[datetime] = None

    # Computed aliases for frontend compatibility
    @computed_field
    @property
    def pattern_name(self) -> str:
        return self.pattern_type

    @computed_field
    @property
    def timestamp(self) -> datetime:
        return self.detected_at

    model_config = ConfigDict(from_attributes=True)

class RiskAlertListResponse(BaseModel):
    alerts: List[RiskAlertResponse]
    total_count: int
    unacknowledged_count: int

class RiskStateResponse(BaseModel):
    risk_state: str  # 'safe', 'caution', 'danger'
    active_patterns: List[str]
    recent_alerts: List[RiskAlertResponse]
    recommendations: List[str]
