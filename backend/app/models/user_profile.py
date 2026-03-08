"""
User Profile Model

Stores trader preferences, experience level, and personalization settings.
Used for adaptive experience and onboarding.
"""

from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean, Integer, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base


class ExperienceLevel(str, enum.Enum):
    BEGINNER = "beginner"        # < 1 year, learning basics
    INTERMEDIATE = "intermediate" # 1-3 years, consistent but improving
    EXPERIENCED = "experienced"   # 3+ years, knows their patterns
    PROFESSIONAL = "professional" # Full-time trader


class TradingStyle(str, enum.Enum):
    SCALPER = "scalper"           # Multiple trades per day, quick exits
    INTRADAY = "intraday"         # Day trader, no overnight positions
    SWING = "swing"               # Hold for days/weeks
    POSITIONAL = "positional"     # Hold for weeks/months
    MIXED = "mixed"               # Combination of styles


class RiskTolerance(str, enum.Enum):
    CONSERVATIVE = "conservative"  # Small positions, tight stops
    MODERATE = "moderate"          # Balanced approach
    AGGRESSIVE = "aggressive"      # Larger positions, wider stops


class UserProfile(Base):
    """
    User profile with trading preferences and personalization.
    Created during onboarding, updated as we learn more.
    """
    __tablename__ = "user_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    broker_account_id = Column(
        UUID(as_uuid=True),
        ForeignKey("broker_accounts.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True
    )

    # Onboarding status
    onboarding_completed = Column(Boolean, default=False)
    onboarding_step = Column(Integer, default=0)  # Current step if incomplete

    # Basic info
    display_name = Column(String(100), nullable=True)
    trading_since = Column(Integer, nullable=True)  # Year started trading

    # Trading profile (from quiz or detected)
    experience_level = Column(String(20), default="beginner")
    trading_style = Column(String(20), default="intraday")
    risk_tolerance = Column(String(20), default="moderate")

    # Preferences
    preferred_instruments = Column(JSONB, default=list)  # ['NIFTY', 'BANKNIFTY', 'STOCKS']
    preferred_segments = Column(JSONB, default=list)     # ['OPTIONS', 'FUTURES', 'EQUITY']
    trading_hours_start = Column(String(5), default="09:15")  # HH:MM
    trading_hours_end = Column(String(5), default="15:30")

    # Risk management settings
    daily_loss_limit = Column(Float, nullable=True)       # Max loss per day
    daily_trade_limit = Column(Integer, nullable=True)    # Max trades per day
    max_position_size = Column(Float, nullable=True)      # Max position size (% of capital as decimal, e.g. 10.0 = 10%)
    cooldown_after_loss = Column(Integer, default=15)     # Minutes to wait after loss
    trading_capital = Column(Float, nullable=True)        # Rs amount of capital deployed for trading
    sl_percent_futures = Column(Float, nullable=True)     # Typical SL % of notional for futures (e.g., 1.0)
    sl_percent_options = Column(Float, nullable=True)     # % of premium to exit losing options (e.g., 50.0)

    # Known weaknesses (from analysis or self-reported)
    known_weaknesses = Column(JSONB, default=list)  # ['revenge_trading', 'fomo', 'overtrading']

    # Notification preferences
    push_enabled = Column(Boolean, default=True)
    whatsapp_enabled = Column(Boolean, default=False)
    email_enabled = Column(Boolean, default=False)
    alert_sensitivity = Column(String(20), default="medium")  # low, medium, high

    # Guardian settings
    guardian_enabled = Column(Boolean, default=False)
    guardian_alert_threshold = Column(String(20), default="danger")  # danger, caution, all
    guardian_daily_summary = Column(Boolean, default=False)  # Send daily summary to guardian

    # Report delivery times (IST, HH:MM)
    eod_report_time = Column(String(5), default="16:00")     # Post-market report (default 4:00 PM)
    morning_brief_time = Column(String(5), default="08:30")  # Morning brief (default 8:30 AM)

    # AI personalization
    ai_persona = Column(String(50), default="coach")  # coach, mentor, friend, strict
    detected_patterns = Column(JSONB, default=dict)   # Auto-detected behavior patterns
    ai_cache = Column(JSONB, default=dict)             # Cached AI responses with timestamps

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<UserProfile {self.id} account={self.broker_account_id}>"

    def to_dict(self):
        return {
            "id": str(self.id),
            "broker_account_id": str(self.broker_account_id),
            "onboarding_completed": self.onboarding_completed,
            "onboarding_step": self.onboarding_step,
            "display_name": self.display_name,
            "trading_since": self.trading_since,
            "experience_level": self.experience_level,
            "trading_style": self.trading_style,
            "risk_tolerance": self.risk_tolerance,
            "preferred_instruments": self.preferred_instruments or [],
            "preferred_segments": self.preferred_segments or [],
            "trading_hours_start": self.trading_hours_start,
            "trading_hours_end": self.trading_hours_end,
            "daily_loss_limit": self.daily_loss_limit,
            "daily_trade_limit": self.daily_trade_limit,
            "max_position_size": self.max_position_size,
            "cooldown_after_loss": self.cooldown_after_loss,
            "trading_capital": self.trading_capital,
            "sl_percent_futures": self.sl_percent_futures,
            "sl_percent_options": self.sl_percent_options,
            "known_weaknesses": self.known_weaknesses or [],
            "push_enabled": self.push_enabled,
            "whatsapp_enabled": self.whatsapp_enabled,
            "email_enabled": self.email_enabled,
            "alert_sensitivity": self.alert_sensitivity,
            "guardian_enabled": self.guardian_enabled,
            "guardian_alert_threshold": self.guardian_alert_threshold,
            "guardian_daily_summary": self.guardian_daily_summary,
            "eod_report_time": self.eod_report_time or "16:00",
            "morning_brief_time": self.morning_brief_time or "08:30",
            "ai_persona": self.ai_persona,
            "detected_patterns": self.detected_patterns or {},
            "ai_cache": self.ai_cache or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
