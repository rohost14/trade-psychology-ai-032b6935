from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, List, Any
from uuid import UUID


class TradingGoalBase(BaseModel):
    max_risk_per_trade_percent: float = 2.0
    max_daily_loss: float = 5000.0
    max_trades_per_day: int = 10
    require_stoploss: bool = True
    min_time_between_trades_minutes: int = 5
    max_position_size_percent: float = 5.0
    allowed_trading_start: str = "09:15"
    allowed_trading_end: str = "15:30"
    starting_capital: float = 100000.0
    current_capital: float = 100000.0


class TradingGoalCreate(TradingGoalBase):
    broker_account_id: UUID


class TradingGoalUpdate(BaseModel):
    max_risk_per_trade_percent: Optional[float] = None
    max_daily_loss: Optional[float] = None
    max_trades_per_day: Optional[int] = None
    require_stoploss: Optional[bool] = None
    min_time_between_trades_minutes: Optional[int] = None
    max_position_size_percent: Optional[float] = None
    allowed_trading_start: Optional[str] = None
    allowed_trading_end: Optional[str] = None
    starting_capital: Optional[float] = None
    current_capital: Optional[float] = None
    reason: Optional[str] = None  # Reason for the change


class TradingGoalResponse(TradingGoalBase):
    id: UUID
    broker_account_id: UUID
    created_at: datetime
    last_modified_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CommitmentLogEntry(BaseModel):
    id: UUID
    log_type: str
    description: str
    reason: Optional[str] = None
    cost: Optional[float] = None
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)


class CommitmentLogResponse(BaseModel):
    logs: List[CommitmentLogEntry]
    total: int


class DailyStatus(BaseModel):
    date: str
    all_goals_followed: bool
    goals_broken: List[str] = []
    trading_day: bool = True


class Milestone(BaseModel):
    days: int
    achieved_at: str
    label: str


class StreakDataResponse(BaseModel):
    current_streak_days: int = 0
    longest_streak_days: int = 0
    streak_start_date: Optional[str] = None
    daily_status: List[DailyStatus] = []
    milestones_achieved: List[Milestone] = []


class GoalAdherenceItem(BaseModel):
    goal_name: str
    times_broken: int
    adherence_percent: float


class GoalsFullResponse(BaseModel):
    goals: TradingGoalResponse
    commitment_log: List[CommitmentLogEntry]
    streak: StreakDataResponse
    is_review_open: bool
    days_until_review: int
