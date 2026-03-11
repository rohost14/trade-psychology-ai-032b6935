from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from uuid import UUID
from datetime import datetime, timezone
from typing import List
import logging

from app.core.database import get_db
from app.api.deps import get_verified_broker_account_id
from app.models.goal import Goal, CommitmentLog, StreakData


from app.schemas.goal import (
    TradingGoalResponse,
    TradingGoalUpdate,
    CommitmentLogEntry,
    CommitmentLogResponse,
    StreakDataResponse,
    GoalsFullResponse,
)

router = APIRouter()

logger = logging.getLogger(__name__)


async def _sync_goals_to_profile(broker_account_id: UUID, goals: Goal, db: AsyncSession):
    """
    P-03: Sync goal limits → UserProfile thresholds so BehaviorEngine uses
    the user's stated goals instead of cold-start defaults.

    Mapping:
      Goal.max_daily_loss          → UserProfile.daily_loss_limit
      Goal.max_trades_per_day      → UserProfile.daily_trade_limit
      Goal.max_position_size_pct   → UserProfile.max_position_size
      Goal.starting_capital        → UserProfile.trading_capital (only if profile has none)
      Goal.min_time_between_trades → UserProfile.cooldown_after_loss
    """
    try:
        from app.models.user_profile import UserProfile
        from datetime import datetime, timezone

        result = await db.execute(
            select(UserProfile).where(UserProfile.broker_account_id == broker_account_id)
        )
        profile = result.scalar_one_or_none()
        if not profile:
            return

        changed = False

        if goals.max_daily_loss is not None:
            profile.daily_loss_limit = goals.max_daily_loss
            changed = True

        if goals.max_trades_per_day is not None:
            profile.daily_trade_limit = goals.max_trades_per_day
            changed = True

        if goals.max_position_size_percent is not None:
            profile.max_position_size = goals.max_position_size_percent
            changed = True

        if goals.min_time_between_trades_minutes is not None:
            profile.cooldown_after_loss = goals.min_time_between_trades_minutes
            changed = True

        # Only set trading_capital from goals if profile doesn't already have one
        if goals.starting_capital and not profile.trading_capital:
            profile.trading_capital = goals.starting_capital
            changed = True

        if changed:
            profile.updated_at = datetime.now(timezone.utc)
            await db.commit()
            logger.info(f"[goals→profile] Synced thresholds for {broker_account_id}")

    except Exception as e:
        logger.warning(f"[goals→profile] Sync failed (non-fatal): {e}")


class StreakIncrementRequest(BaseModel):
    all_goals_followed: bool = True
    goals_broken: List[str] = []


def get_days_until_review() -> int:
    """Calculate days until next monthly review window (1st-3rd of month)."""
    now = datetime.now(timezone.utc)
    if now.day <= 3:
        return 0  # In review window
    # Days until 1st of next month
    if now.month == 12:
        next_review = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        next_review = datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)
    return (next_review - now).days


def is_review_window_open() -> bool:
    """Check if monthly review window is open (1st-3rd)."""
    return datetime.now(timezone.utc).day <= 3


@router.get("/", response_model=GoalsFullResponse)
async def get_goals(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
):
    """Get all goals data for a broker account."""
    # Get or create goals
    result = await db.execute(
        select(Goal).where(Goal.broker_account_id == broker_account_id)
    )
    goals = result.scalar_one_or_none()

    if not goals:
        # Create default goals
        goals = Goal(broker_account_id=broker_account_id)
        db.add(goals)
        await db.commit()
        await db.refresh(goals)

    # Get commitment log (last 50 entries)
    log_result = await db.execute(
        select(CommitmentLog)
        .where(CommitmentLog.broker_account_id == broker_account_id)
        .order_by(desc(CommitmentLog.timestamp))
        .limit(50)
    )
    logs = log_result.scalars().all()

    # Get or create streak data
    streak_result = await db.execute(
        select(StreakData).where(StreakData.broker_account_id == broker_account_id)
    )
    streak = streak_result.scalar_one_or_none()

    if not streak:
        streak = StreakData(broker_account_id=broker_account_id)
        db.add(streak)
        await db.commit()
        await db.refresh(streak)

    return GoalsFullResponse(
        goals=goals,
        commitment_log=[CommitmentLogEntry.model_validate(log) for log in logs],
        streak=StreakDataResponse(
            current_streak_days=streak.current_streak_days,
            longest_streak_days=streak.longest_streak_days,
            streak_start_date=streak.streak_start_date.isoformat() if streak.streak_start_date else None,
            daily_status=streak.daily_status or [],
            milestones_achieved=streak.milestones_achieved or [],
        ),
        is_review_open=is_review_window_open(),
        days_until_review=get_days_until_review(),
    )


@router.put("/", response_model=TradingGoalResponse)
async def update_goals(
    updates: TradingGoalUpdate,
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
):
    """Update trading goals."""
    try:
        result = await db.execute(
            select(Goal).where(Goal.broker_account_id == broker_account_id)
        )
        goals = result.scalar_one_or_none()

        if not goals:
            goals = Goal(broker_account_id=broker_account_id)
            db.add(goals)

        # Track changes for commitment log
        changes = []
        update_data = updates.model_dump(exclude_unset=True, exclude={'reason'})

        for field, new_value in update_data.items():
            old_value = getattr(goals, field)
            if old_value != new_value:
                changes.append(f"{field}: {old_value} -> {new_value}")
                setattr(goals, field, new_value)

        goals.last_modified_at = datetime.now(timezone.utc)

        # Log the change
        if changes:
            log_entry = CommitmentLog(
                broker_account_id=broker_account_id,
                log_type="goal_modified",
                description="; ".join(changes),
                reason=updates.reason or "User modified goals",
            )
            db.add(log_entry)

        await db.commit()
        await db.refresh(goals)

        # P-03: Sync goal limits → UserProfile thresholds
        # BehaviorEngine reads from UserProfile, so this wires goals to detection.
        await _sync_goals_to_profile(broker_account_id, goals, db)

        return goals
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to update goals: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/commitment-log", response_model=CommitmentLogResponse)
async def get_commitment_log(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """Get commitment log entries."""
    result = await db.execute(
        select(CommitmentLog)
        .where(CommitmentLog.broker_account_id == broker_account_id)
        .order_by(desc(CommitmentLog.timestamp))
        .limit(limit)
    )
    logs = result.scalars().all()

    return CommitmentLogResponse(
        logs=[CommitmentLogEntry.model_validate(log) for log in logs],
        total=len(logs)
    )


@router.post("/log-broken")
async def log_goal_broken(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    goal_name: str = "",
    cost: float = 0,
    db: AsyncSession = Depends(get_db)
):
    """Log when a goal is broken."""
    try:
        log_entry = CommitmentLog(
            broker_account_id=broker_account_id,
            log_type="goal_broken",
            description=f"{goal_name} was not followed",
            cost=cost,
        )
        db.add(log_entry)

        # Reset streak
        streak_result = await db.execute(
            select(StreakData).where(StreakData.broker_account_id == broker_account_id)
        )
        streak = streak_result.scalar_one_or_none()

        if streak:
            streak.current_streak_days = 0
            streak.streak_start_date = None

        await db.commit()

        return {"status": "logged", "goal": goal_name, "cost": cost}
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to log broken goal: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/streak", response_model=StreakDataResponse)
async def get_streak(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
):
    """Get streak data."""
    result = await db.execute(
        select(StreakData).where(StreakData.broker_account_id == broker_account_id)
    )
    streak = result.scalar_one_or_none()

    if not streak:
        streak = StreakData(broker_account_id=broker_account_id)
        db.add(streak)
        await db.commit()
        await db.refresh(streak)

    return StreakDataResponse(
        current_streak_days=streak.current_streak_days,
        longest_streak_days=streak.longest_streak_days,
        streak_start_date=streak.streak_start_date.isoformat() if streak.streak_start_date else None,
        daily_status=streak.daily_status or [],
        milestones_achieved=streak.milestones_achieved or [],
    )


@router.post("/streak/increment")
async def increment_streak(
    body: StreakIncrementRequest,
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
):
    """Update streak for today."""
    try:
        result = await db.execute(
            select(StreakData).where(StreakData.broker_account_id == broker_account_id)
        )
        streak = result.scalar_one_or_none()

        if not streak:
            streak = StreakData(broker_account_id=broker_account_id)
            db.add(streak)

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Check if already recorded today
        daily_status = streak.daily_status or []
        if daily_status and daily_status[0].get("date") == today:
            return {"status": "already_recorded", "streak": streak.current_streak_days}

        # Add today's status
        daily_status.insert(0, {
            "date": today,
            "all_goals_followed": body.all_goals_followed,
            "goals_broken": body.goals_broken,
            "trading_day": True,
        })

        # Keep last 60 days
        streak.daily_status = daily_status[:60]

        # Update streak count
        if body.all_goals_followed:
            streak.current_streak_days += 1
            if not streak.streak_start_date:
                streak.streak_start_date = datetime.now(timezone.utc)
            if streak.current_streak_days > streak.longest_streak_days:
                streak.longest_streak_days = streak.current_streak_days

            # Check milestones
            milestones = streak.milestones_achieved or []
            milestone_thresholds = [
                (7, "7-Day Discipline"),
                (14, "2-Week Warrior"),
                (30, "Monthly Master"),
                (60, "Trading Zen"),
            ]
            for days, label in milestone_thresholds:
                if streak.current_streak_days == days:
                    if not any(m.get("days") == days for m in milestones):
                        milestones.append({
                            "days": days,
                            "achieved_at": datetime.now(timezone.utc).isoformat(),
                            "label": label,
                        })
                        # Log milestone
                        log_entry = CommitmentLog(
                            broker_account_id=broker_account_id,
                            log_type="streak_milestone",
                            description=f"Achieved {label} streak!",
                        )
                        db.add(log_entry)
            streak.milestones_achieved = milestones
        else:
            streak.current_streak_days = 0
            streak.streak_start_date = None

        await db.commit()

        return {
            "status": "updated",
            "streak": streak.current_streak_days,
            "longest": streak.longest_streak_days,
        }
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to increment streak: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
