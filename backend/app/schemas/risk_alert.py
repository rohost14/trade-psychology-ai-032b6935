from pydantic import BaseModel, UUID4
from datetime import datetime
from typing import Optional, List, Dict, Any

class RiskAlertBase(BaseModel):
    pattern_type: str
    severity: str
    message: str
    details: Optional[Dict[str, Any]] = None

class RiskAlertResponse(RiskAlertBase):
    id: UUID4
    broker_account_id: UUID4
    trigger_trade_id: Optional[UUID4]
    related_trade_ids: Optional[List[UUID4]]
    detected_at: datetime
    acknowledged_at: Optional[datetime]
    
    class Config:
        from_attributes = True

class RiskAlertListResponse(BaseModel):
    alerts: List[RiskAlertResponse]
    total_count: int
    unacknowledged_count: int

class RiskStateResponse(BaseModel):
    risk_state: str  # 'safe', 'caution', 'danger'
    active_patterns: List[str]
    recent_alerts: List[RiskAlertResponse]
    recommendations: List[str]
