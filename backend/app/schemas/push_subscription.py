from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime
from uuid import UUID


class PushSubscriptionCreate(BaseModel):
    endpoint: str
    p256dh_key: str
    auth_key: str
    user_agent: Optional[str] = None
    device_type: Optional[str] = None


class PushSubscriptionResponse(BaseModel):
    id: UUID
    broker_account_id: UUID
    endpoint: str
    p256dh_key: str
    auth_key: str
    user_agent: Optional[str] = None
    device_type: Optional[str] = None
    is_active: bool = True
    last_used_at: Optional[datetime] = None
    failed_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
