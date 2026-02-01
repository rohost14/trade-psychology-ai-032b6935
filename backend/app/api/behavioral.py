from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.core.database import get_db
from app.services.behavioral_analysis_service import BehavioralAnalysisService

router = APIRouter()

@router.get("/analysis")
async def get_behavioral_analysis(
    broker_account_id: UUID,
    time_window_days: int = 30,
    db: AsyncSession = Depends(get_db)
):
    """Get comprehensive behavioral analysis."""
    
    service = BehavioralAnalysisService()
    analysis = await service.analyze_behavior(
        broker_account_id, 
        db, 
        time_window_days
    )
    
    return analysis

@router.get("/patterns")
async def get_detected_patterns(
    broker_account_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get list of detected behavioral patterns."""
    
    service = BehavioralAnalysisService()
    analysis = await service.analyze_behavior(broker_account_id, db)
    
    return {
        "patterns": analysis["patterns_detected"],
        "behavior_score": analysis["behavior_score"],
        "top_strength": analysis["top_strength"],
        "focus_area": analysis["focus_area"]
    }

@router.get("/trade-tags")
async def get_trade_tags(
    broker_account_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get behavioral tags for all trades."""
    
    service = BehavioralAnalysisService()
    tags = await service.tag_trades(broker_account_id, db)
    
    return {"trade_tags": tags}
