"""
AI Personalization API

Endpoints for learning and retrieving personalized trading insights.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel

import logging

from app.core.database import get_db
from app.api.deps import get_verified_broker_account_id
from app.services.ai_personalization_service import ai_personalization_service

router = APIRouter()
logger = logging.getLogger(__name__)


class PredictiveCheckRequest(BaseModel):
    """Request for predictive alert check"""
    proposed_symbol: Optional[str] = None


@router.post("/learn")
async def learn_patterns(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    days_back: int = 90,
    db: AsyncSession = Depends(get_db)
):
    """
    Trigger pattern learning for a trader.
    Analyzes past trades to learn:
    - Personal danger hours/days
    - Problem symbols
    - Optimal cooldown duration
    - Predictive alert windows
    """
    try:
        result = await ai_personalization_service.learn_patterns(
            broker_account_id=broker_account_id,
            db=db,
            days_back=days_back
        )
        return {
            "success": True,
            "learned_patterns": result
        }
    except Exception as e:
        logger.error(f"Failed to learn patterns: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/insights")
async def get_insights(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Get personalized insights summary for dashboard display.
    Returns:
    - Your danger hours
    - Your best hours
    - Problem symbols to avoid
    - Strong symbols to focus on
    - Your revenge trading window
    - Predictive alerts
    """
    insights = await ai_personalization_service.get_personalized_insights(
        broker_account_id=broker_account_id,
        db=db
    )
    return insights


@router.post("/predictive-check")
async def predictive_check(
    request: PredictiveCheckRequest,
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Check for predictive alerts based on current context.
    Call this:
    - On app open (to warn about danger day/hour)
    - Before placing a trade (to warn about problem symbol)

    Returns alert if trader is in a historically bad window.
    """
    alert = await ai_personalization_service.get_predictive_alert(
        broker_account_id=broker_account_id,
        db=db,
        context={
            "current_time": datetime.now(timezone.utc),
            "proposed_symbol": request.proposed_symbol
        }
    )

    if alert:
        return {
            "has_warning": True,
            "alert": alert
        }
    return {
        "has_warning": False,
        "alert": None
    }


@router.get("/time-analysis")
async def get_time_analysis(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Get detailed time-based performance analysis.
    Shows win rate by hour and day of week.
    """
    insights = await ai_personalization_service.get_personalized_insights(
        broker_account_id=broker_account_id,
        db=db
    )

    if not insights.get("has_data"):
        return {"has_data": False, "message": insights.get("message")}

    # Re-learn to get fresh breakdown
    patterns = await ai_personalization_service.learn_patterns(
        broker_account_id=broker_account_id,
        db=db,
        days_back=90
    )

    time_patterns = patterns.get("time_patterns", {})

    return {
        "has_data": True,
        "hourly_breakdown": time_patterns.get("hourly_breakdown", {}),
        "daily_breakdown": time_patterns.get("daily_breakdown", {}),
        "danger_hours": time_patterns.get("danger_hours", []),
        "danger_days": time_patterns.get("danger_days", []),
        "best_hours": time_patterns.get("best_hours", []),
        "best_days": time_patterns.get("best_days", [])
    }


@router.get("/symbol-analysis")
async def get_symbol_analysis(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Get detailed symbol-based performance analysis.
    Shows which symbols to avoid and which to focus on.
    """
    insights = await ai_personalization_service.get_personalized_insights(
        broker_account_id=broker_account_id,
        db=db
    )

    if not insights.get("has_data"):
        return {"has_data": False, "message": insights.get("message")}

    # Re-learn to get fresh breakdown
    patterns = await ai_personalization_service.learn_patterns(
        broker_account_id=broker_account_id,
        db=db,
        days_back=90
    )

    symbol_patterns = patterns.get("symbol_patterns", {})

    return {
        "has_data": True,
        "problem_symbols": symbol_patterns.get("problem_symbols", []),
        "strong_symbols": symbol_patterns.get("strong_symbols", []),
        "symbol_breakdown": symbol_patterns.get("symbol_breakdown", {})
    }


@router.get("/intervention-timing")
async def get_intervention_timing(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Get personalized intervention timing recommendations.
    Returns:
    - Your optimal cooldown duration
    - Your typical revenge trading window
    - Whether you should skip or complete cooldowns
    """
    insights = await ai_personalization_service.get_personalized_insights(
        broker_account_id=broker_account_id,
        db=db
    )

    if not insights.get("has_data"):
        return {"has_data": False, "message": insights.get("message")}

    # Re-learn to get fresh data
    patterns = await ai_personalization_service.learn_patterns(
        broker_account_id=broker_account_id,
        db=db,
        days_back=90
    )

    timing = patterns.get("intervention_timing", {})

    return {
        "has_data": True,
        "optimal_cooldown_minutes": timing.get("optimal_cooldown_minutes", 15),
        "personal_revenge_window_minutes": timing.get("personal_revenge_window_minutes", 12),
        "skip_vs_complete": timing.get("skip_vs_complete", {}),
        "confidence": timing.get("confidence", "low"),
        "recommendation": _generate_timing_recommendation(timing)
    }


def _generate_timing_recommendation(timing: dict) -> str:
    """Generate human-readable recommendation."""
    optimal = timing.get("optimal_cooldown_minutes", 15)
    revenge_window = timing.get("personal_revenge_window_minutes", 12)
    skip_data = timing.get("skip_vs_complete", {})

    parts = []

    # Cooldown recommendation
    if revenge_window:
        suggested = int(revenge_window * 1.5)
        parts.append(f"Your typical revenge window is {revenge_window} minutes.")
        parts.append(f"Set your cooldown to at least {suggested} minutes to break the pattern.")

    # Skip vs complete
    if skip_data.get("recommendation") == "complete":
        parts.append("Data shows you perform better when you complete cooldowns rather than skipping them.")
    elif skip_data.get("recommendation") == "skip_cautiously":
        parts.append("You can sometimes skip cooldowns if you feel mentally ready, but use caution.")

    return " ".join(parts) if parts else "Keep trading to build more data for personalized recommendations."
