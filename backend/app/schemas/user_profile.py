from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID


class UserProfileBase(BaseModel):
    # Onboarding
    onboarding_completed: bool = False
    onboarding_step: int = 0

    # Basic info
    display_name: Optional[str] = None
    trading_since: Optional[int] = None

    # Trading profile
    experience_level: str = "beginner"
    trading_style: str = "intraday"
    risk_tolerance: str = "moderate"

    # Preferences
    preferred_instruments: Optional[List[str]] = []
    preferred_segments: Optional[List[str]] = []
    trading_hours_start: str = "09:15"
    trading_hours_end: str = "15:30"

    # Risk management
    daily_loss_limit: Optional[float] = None
    daily_trade_limit: Optional[int] = None
    max_position_size: Optional[float] = None
    cooldown_after_loss: int = 15
    trading_capital: Optional[float] = None
    sl_percent_futures: Optional[float] = None
    sl_percent_options: Optional[float] = None

    # Known weaknesses
    known_weaknesses: Optional[List[str]] = []

    # Notification preferences
    push_enabled: bool = True
    whatsapp_enabled: bool = False
    email_enabled: bool = False
    alert_sensitivity: str = "medium"

    # Guardian settings
    guardian_enabled: bool = False
    guardian_alert_threshold: str = "danger"
    guardian_daily_summary: bool = False

    # AI personalization
    ai_persona: str = "coach"
    detected_patterns: Optional[Dict[str, Any]] = {}


class UserProfileCreate(UserProfileBase):
    pass


class UserProfileUpdate(BaseModel):
    display_name: Optional[str] = None
    trading_since: Optional[int] = None
    experience_level: Optional[str] = None
    trading_style: Optional[str] = None
    risk_tolerance: Optional[str] = None
    preferred_instruments: Optional[List[str]] = None
    preferred_segments: Optional[List[str]] = None
    trading_hours_start: Optional[str] = None
    trading_hours_end: Optional[str] = None
    daily_loss_limit: Optional[float] = None
    daily_trade_limit: Optional[int] = None
    max_position_size: Optional[float] = None
    cooldown_after_loss: Optional[int] = None
    trading_capital: Optional[float] = None
    sl_percent_futures: Optional[float] = None
    sl_percent_options: Optional[float] = None
    known_weaknesses: Optional[List[str]] = None
    push_enabled: Optional[bool] = None
    whatsapp_enabled: Optional[bool] = None
    email_enabled: Optional[bool] = None
    alert_sensitivity: Optional[str] = None
    guardian_enabled: Optional[bool] = None
    guardian_alert_threshold: Optional[str] = None
    guardian_daily_summary: Optional[bool] = None
    ai_persona: Optional[str] = None


class UserProfileResponse(UserProfileBase):
    id: UUID
    broker_account_id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
