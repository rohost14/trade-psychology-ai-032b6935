"""
Danger Zone API

Endpoints for monitoring and managing danger zone states.
Integrates cooldowns, notifications, and interventions.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from uuid import UUID
from typing import Optional, List, Dict
from datetime import datetime, timezone
import logging

from app.core.database import get_db
from app.api.deps import get_verified_broker_account_id
from app.services.danger_zone_service import (
    danger_zone_service,
    DangerZoneStatus,
    DangerLevel,
)
from app.services.cooldown_service import cooldown_service
from app.services.notification_rate_limiter import notification_rate_limiter

router = APIRouter()
logger = logging.getLogger(__name__)





class DangerZoneResponse(BaseModel):
    """Response model for danger zone status."""
    level: str
    intervention: str
    triggers: List[str]
    message: str
    cooldown_active: bool
    cooldown_remaining_minutes: int
    daily_loss_used_percent: float
    trade_count_today: int
    consecutive_losses: int
    patterns_active: List[str]
    recommendations: List[str]
    checked_at: str


class InterventionResponse(BaseModel):
    """Response for intervention trigger."""
    success: bool
    cooldown_started: bool
    notification_sent: bool
    whatsapp_sent: bool
    alert_created: bool


class EscalationStatus(BaseModel):
    """Response model for escalation status."""
    trigger: str
    violation_count_24h: int
    current_escalation_level: int
    max_escalation_level: int
    current_duration_minutes: int
    next_duration_minutes: int
    at_max_escalation: bool


class NotificationStatsResponse(BaseModel):
    """Response model for notification statistics."""
    total_24h: int
    by_tier: Dict
    by_type: Dict


@router.get("/status")
async def get_danger_zone_status(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
) -> DangerZoneResponse:
    """
    Get current danger zone status for an account.

    This is the primary endpoint to check before/after trades.
    Returns current danger level, active cooldowns, and recommendations.
    """
    try:
        status = await danger_zone_service.assess_danger_level(
            db=db,
            broker_account_id=broker_account_id
        )

        return DangerZoneResponse(
            level=status.level.value,
            intervention=status.intervention.value,
            triggers=status.triggers,
            message=status.message,
            cooldown_active=status.cooldown_active,
            cooldown_remaining_minutes=status.cooldown_remaining_minutes,
            daily_loss_used_percent=status.daily_loss_used_percent,
            trade_count_today=status.trade_count_today,
            consecutive_losses=status.consecutive_losses,
            patterns_active=status.patterns_active,
            recommendations=status.recommendations,
            checked_at=datetime.now(timezone.utc).isoformat()
        )

    except Exception as e:
        logger.error(f"Failed to get danger zone status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/trigger-intervention")
async def trigger_intervention(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
) -> InterventionResponse:
    """
    Trigger intervention based on current danger level.

    Call this when you want to actively enforce interventions
    (cooldowns, notifications) based on current status.
    """
    try:
        # First assess the current level
        status = await danger_zone_service.assess_danger_level(
            db=db,
            broker_account_id=broker_account_id
        )

        # Then trigger appropriate intervention
        actions = await danger_zone_service.trigger_intervention(
            db=db,
            broker_account_id=broker_account_id,
            status=status
        )

        return InterventionResponse(
            success=True,
            cooldown_started=actions["cooldown_started"],
            notification_sent=actions["notification_sent"],
            whatsapp_sent=actions["whatsapp_sent"],
            alert_created=actions["alert_created"]
        )

    except Exception as e:
        logger.error(f"Failed to trigger intervention: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/escalation-status")
async def get_escalation_status(
    trigger_reason: str,
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
) -> EscalationStatus:
    """
    Get current escalation status for a specific trigger.

    Shows how many violations have occurred and what the next
    cooldown duration will be.
    """
    try:
        status = await cooldown_service.get_escalation_status(
            account_id=str(broker_account_id),
            trigger_reason=trigger_reason
        )

        return EscalationStatus(**status)

    except Exception as e:
        logger.error(f"Failed to get escalation status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/reset-escalation")
async def reset_escalation(
    trigger_reason: Optional[str] = None,
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
):
    """
    Reset escalation level for the authenticated account.
    """
    try:
        cooldown_service.reset_violations(str(broker_account_id), trigger_reason)

        return {
            "success": True,
            "message": "Escalation reset" +
                       (f" for trigger: {trigger_reason}" if trigger_reason else " (all triggers)")
        }

    except Exception as e:
        logger.error(f"Failed to reset escalation: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/notification-stats")
async def get_notification_stats(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
) -> NotificationStatsResponse:
    """
    Get notification statistics for the authenticated account.

    Shows how many notifications have been sent and remaining limits.
    """
    try:
        stats = notification_rate_limiter.get_notification_stats(str(broker_account_id))

        return NotificationStatsResponse(
            total_24h=stats["total_24h"],
            by_tier=stats["by_tier"],
            by_type=stats["by_type"]
        )

    except Exception as e:
        logger.error(f"Failed to get notification stats: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/reset-notification-limits")
async def reset_notification_limits(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
):
    """
    Reset notification rate limits for the authenticated account.
    """
    try:
        notification_rate_limiter.reset_user_limits(str(broker_account_id))

        return {
            "success": True,
            "message": "Notification limits reset"
        }

    except Exception as e:
        logger.error(f"Failed to reset notification limits: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/summary")
async def get_danger_zone_summary(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Get comprehensive danger zone summary.

    Combines status, cooldown info, and notification stats
    for a complete picture.
    """
    try:
        # Get current status
        status = await danger_zone_service.assess_danger_level(
            db=db,
            broker_account_id=broker_account_id
        )

        # Get cooldown history
        cooldown_history = await cooldown_service.get_cooldown_history(
            db=db,
            broker_account_id=broker_account_id,
            days=7
        )

        # Get notification stats
        notification_stats = notification_rate_limiter.get_notification_stats(str(broker_account_id))

        return {
            "current_status": {
                "level": status.level.value,
                "intervention": status.intervention.value,
                "triggers": status.triggers,
                "message": status.message,
                "cooldown_active": status.cooldown_active,
                "cooldown_remaining_minutes": status.cooldown_remaining_minutes,
            },
            "metrics": {
                "daily_loss_used_percent": status.daily_loss_used_percent,
                "trade_count_today": status.trade_count_today,
                "consecutive_losses": status.consecutive_losses,
                "patterns_active": status.patterns_active,
            },
            "cooldown_history_7d": cooldown_history[:10],  # Last 10
            "notification_stats_24h": notification_stats,
            "recommendations": status.recommendations,
            "checked_at": datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        logger.error(f"Failed to get danger zone summary: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
