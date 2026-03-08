from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from uuid import UUID


class JournalEntryBase(BaseModel):
    """Base fields for creating/updating a journal entry."""
    notes: Optional[str] = None
    emotions: Optional[str] = None
    lessons: Optional[str] = None
    emotion_tags: Optional[List[str]] = []
    trade_symbol: Optional[str] = None
    trade_type: Optional[str] = None
    trade_pnl: Optional[str] = None
    entry_type: str = "trade"


class JournalEntryCreate(JournalEntryBase):
    """Fields for creating a journal entry."""
    trade_id: Optional[UUID] = None


class JournalEntryUpdate(BaseModel):
    """Fields for updating a journal entry (all optional)."""
    notes: Optional[str] = None
    emotions: Optional[str] = None
    lessons: Optional[str] = None
    emotion_tags: Optional[List[str]] = None
    entry_type: Optional[str] = None


class JournalEntryResponse(JournalEntryBase):
    """Response model for a journal entry."""
    id: UUID
    broker_account_id: UUID
    trade_id: Optional[UUID] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
