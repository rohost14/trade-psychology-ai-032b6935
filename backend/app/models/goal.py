from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid
from datetime import datetime

from app.core.database import Base


class TradingGoal(Base):
    __tablename__ = "trading_goals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    broker_account_id = Column(UUID(as_uuid=True), ForeignKey("broker_accounts.id"), nullable=False, unique=True)

    # Risk limits
    max_risk_per_trade_percent = Column(Float, default=2.0)
    max_daily_loss = Column(Float, default=5000.0)
    max_trades_per_day = Column(Integer, default=10)
    require_stoploss = Column(Boolean, default=True)
    min_time_between_trades_minutes = Column(Integer, default=5)
    max_position_size_percent = Column(Float, default=5.0)

    # Trading hours
    allowed_trading_start = Column(String(10), default="09:15")
    allowed_trading_end = Column(String(10), default="15:30")

    # Capital tracking
    starting_capital = Column(Float, default=100000.0)
    current_capital = Column(Float, default=100000.0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    last_modified_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class CommitmentLog(Base):
    __tablename__ = "commitment_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    broker_account_id = Column(UUID(as_uuid=True), ForeignKey("broker_accounts.id"), nullable=False)

    log_type = Column(String(50), nullable=False)  # goal_set, goal_modified, goal_broken, streak_milestone
    description = Column(Text, nullable=False)
    reason = Column(Text)
    cost = Column(Float)  # For goal_broken entries

    timestamp = Column(DateTime(timezone=True), default=datetime.utcnow)


class StreakData(Base):
    __tablename__ = "streak_data"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    broker_account_id = Column(UUID(as_uuid=True), ForeignKey("broker_accounts.id"), nullable=False, unique=True)

    current_streak_days = Column(Integer, default=0)
    longest_streak_days = Column(Integer, default=0)
    streak_start_date = Column(DateTime(timezone=True))

    # Store daily status as JSON array
    daily_status = Column(JSONB, default=list)

    # Store milestones as JSON array
    milestones_achieved = Column(JSONB, default=list)

    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
