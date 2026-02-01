from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
import logging

from app.core.database import get_db
from app.services.analytics_service import AnalyticsService

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/risk-score")
async def get_weekly_risk_score(
    broker_account_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get weekly risk/discipline score."""
    try:
        account_id = UUID(broker_account_id)
        analytics = AnalyticsService()
        score_data = await analytics.calculate_weekly_risk_score(account_id, db)
        return score_data
    except Exception as e:
        logger.error(f"Failed to get risk score: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/money-saved")
async def get_money_saved(
    broker_account_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get estimated money saved by risk prevention."""
    try:
        account_id = UUID(broker_account_id)
        analytics = AnalyticsService()
        money_data = await analytics.calculate_money_saved(account_id, db)
        return money_data
    except Exception as e:
        logger.error(f"Failed to get money saved: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/dashboard-stats")
async def get_dashboard_stats(
    broker_account_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get all analytics for dashboard."""
    try:
        account_id = UUID(broker_account_id)
        analytics = AnalyticsService()
        
        score_data = await analytics.calculate_weekly_risk_score(account_id, db)
        money_data = await analytics.calculate_money_saved(account_id, db)
        
        return {
            "risk_score": score_data,
            "money_saved": money_data
        }
    except Exception as e:
        logger.error(f"Failed to get dashboard stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
