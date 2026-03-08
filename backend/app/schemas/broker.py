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
    user_id: Optional[UUID] = None
    broker_name: str = "zerodha"
    status: str
    connected_at: Optional[datetime] = None
    last_sync_at: Optional[datetime] = None
    broker_user_id: Optional[str] = None
    broker_email: Optional[str] = None

    # Kite-specific fields
    user_type: Optional[str] = None
    exchanges: Optional[list] = None
    products: Optional[list] = None
    order_types: Optional[list] = None
    avatar_url: Optional[str] = None
    demat_consent: bool = False
    sync_status: str = "pending"

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class BrokerStatusResponse(BaseModel):
    connected: bool
    broker_name: str
    broker_user_id: Optional[str] = None
    last_sync: Optional[datetime] = None
    # Guardian fields sourced from users table, not broker_accounts
    guardian_name: Optional[str] = None
    guardian_phone: Optional[str] = None
