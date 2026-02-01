from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from uuid import UUID
from datetime import datetime, timedelta, timezone

from app.core.database import get_db
from app.models.risk_alert import RiskAlert
from app.schemas.risk_alert import RiskAlertListResponse, RiskStateResponse
from app.services.risk_detector import RiskDetector

router = APIRouter()

@router.get("/state", response_model=RiskStateResponse)
async def get_risk_state(
    broker_account_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get current risk state for account"""
    risk_detector = RiskDetector()
    state_data = await risk_detector.calculate_risk_state(UUID(broker_account_id), db)
    
    # Get recent alerts for response
    cutoff = datetime.now(timezone.utc) - timedelta(hours=4)
    result = await db.execute(
        select(RiskAlert)
        .where(
            and_(
                RiskAlert.broker_account_id == UUID(broker_account_id),
                RiskAlert.detected_at >= cutoff
            )
        )
        .order_by(desc(RiskAlert.detected_at))
        .limit(5)
    )
    recent_alerts = result.scalars().all()
    
    return RiskStateResponse(
        risk_state=state_data["risk_state"],
        active_patterns=state_data["active_patterns"],
        active_alerts=[], # Add this as placeholder or adjust Schema if 'recent_alerts' covers it? Schema has 'recent_alerts'.
        # Wait, Schema `RiskStateResponse` has: risk_state, active_patterns, recent_alerts, recommendations.
        # My return below matches the schema.
        recent_alerts=recent_alerts,
        recommendations=state_data["recommendations"]
    )

@router.get("/alerts", response_model=RiskAlertListResponse)
async def get_risk_alerts(
    broker_account_id: str,
    hours: int = 24,
    db: AsyncSession = Depends(get_db)
):
    """Get risk alerts for account"""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    
    result = await db.execute(
        select(RiskAlert)
        .where(
            and_(
                RiskAlert.broker_account_id == UUID(broker_account_id),
                RiskAlert.detected_at >= cutoff
            )
        )
        .order_by(desc(RiskAlert.detected_at))
    )
    alerts = result.scalars().all()
    
    unacknowledged = [a for a in alerts if a.acknowledged_at is None]
    
    return RiskAlertListResponse(
        alerts=alerts,
        total_count=len(alerts),
        unacknowledged_count=len(unacknowledged)
    )

@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Mark alert as acknowledged"""
    result = await db.execute(
        select(RiskAlert).where(RiskAlert.id == UUID(alert_id))
    )
    alert = result.scalar_one_or_none()
    
    if not alert:
        raise HTTPException(404, "Alert not found")
    
    alert.acknowledged_at = datetime.now(timezone.utc)
    await db.commit()
    
    return {"success": True}
