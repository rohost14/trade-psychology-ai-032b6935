from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID

class BrokerConnectRequest(BaseModel):
    redirect_uri: str

class BrokerCallbackRequest(BaseModel):
    request_token: str
    status: str

class DisconnectRequest(BaseModel):
    broker_account_id: str

class BrokerAccountResponse(BaseModel):
    id: UUID
    user_id: UUID
    status: str
    connected_at: Optional[datetime] = None
    last_sync_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class BrokerStatusResponse(BaseModel):
    connected: bool
    broker_name: str
    broker_user_id: Optional[str] = None
    last_sync: Optional[datetime] = None
    guardian_name: Optional[str] = None
    guardian_phone: Optional[str] = None
