from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID

class CooldownBase(BaseModel):
    reason: str
    duration_minutes: int = 15
    can_skip: bool = True
    message: Optional[str] = None
    meta_data: Optional[Dict[str, Any]] = None
    trigger_alert_id: Optional[UUID] = None

class CooldownCreate(CooldownBase):
    pass

class CooldownUpdate(BaseModel):
    skipped: Optional[bool] = None
    acknowledged: Optional[bool] = None

class Cooldown(CooldownBase):
    id: UUID
    broker_account_id: UUID
    started_at: datetime
    expires_at: datetime
    skipped: bool
    skipped_at: Optional[datetime]
    acknowledged: bool
    acknowledged_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True
