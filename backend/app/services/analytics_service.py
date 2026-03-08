"""
Analytics Service

Calculate user analytics:
- Weekly Risk Score (0-10 discipline metric)
- Money Saved (estimated losses prevented)
"""
from datetime import datetime, timedelta, timezone
from typing import Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
import logging

from app.models.risk_alert import RiskAlert

logger = logging.getLogger(__name__)

class AnalyticsService:
    """
    Calculate user analytics for dashboard display.
    """
    
    async def calculate_weekly_risk_score(
        self,
        broker_account_id: UUID,
        db: AsyncSession
    ) -> Dict:
        """
        Calculate discipline score for last 7 days.
        
        Score based on:
        - Number of risk violations
        - Severity of violations
        
        Returns: {
            "current_score": 7.5,
            "previous_score": 6.8,
            "trend": "improving",
            "factors": {
                "danger_alerts": 2,
                "caution_alerts": 5,
                "clean_days": 4
            }
        }
        """
        try:
            # Get last 7 days and previous 7 days
            now = datetime.now(timezone.utc)
            week_start = now - timedelta(days=7)
            prev_week_start = now - timedelta(days=14)
            
            # Current week alerts
            current_alerts_result = await db.execute(
                select(RiskAlert).where(
                    RiskAlert.broker_account_id == broker_account_id,
                    RiskAlert.detected_at >= week_start
                )
            )
            current_alerts = current_alerts_result.scalars().all()
            
            # Previous week alerts
            prev_alerts_result = await db.execute(
                select(RiskAlert).where(
                    RiskAlert.broker_account_id == broker_account_id,
                    RiskAlert.detected_at >= prev_week_start,
                    RiskAlert.detected_at < week_start
                )
            )
            prev_alerts = prev_alerts_result.scalars().all()
            
            # Calculate scores
            current_score = self._calculate_score_from_alerts(current_alerts)
            previous_score = self._calculate_score_from_alerts(prev_alerts)
            
            # Determine trend
            if current_score > previous_score + 0.5:
                trend = "improving"
            elif current_score < previous_score - 0.5:
                trend = "declining"
            else:
                trend = "stable"
            
            # Calculate factors
            danger_count = len([a for a in current_alerts if a.severity and str(a.severity).lower() == "danger"])
            caution_count = len([a for a in current_alerts if a.severity and str(a.severity).lower() == "caution"])
            
            # Clean days = days without any alerts
            alert_dates = set(a.detected_at.date() for a in current_alerts)
            clean_days = 7 - len(alert_dates)
            
            return {
                "current_score": round(current_score, 1),
                "previous_score": round(previous_score, 1),
                "trend": trend,
                "factors": {
                    "danger_alerts": danger_count,
                    "caution_alerts": caution_count,
                    "clean_days": clean_days
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to calculate risk score: {e}", exc_info=True)
            return {
                "current_score": 5.0,
                "previous_score": 5.0,
                "trend": "unknown",
                "factors": {
                    "danger_alerts": 0,
                    "caution_alerts": 0,
                    "clean_days": 0
                }
            }
    
    def _calculate_score_from_alerts(self, alerts: list) -> float:
        """
        Calculate score (0-10) using logarithmic decay.
        
        Philosophy:
        - 0 alerts = 10/10 (perfect)
        - First few alerts hurt most (wake-up call)
        - Diminishing penalty for better gradient
        - Never go below 0.5 (always room to get worse)
        """
        import math
        
        # Weight alerts
        danger_count = len([a for a in alerts if a.severity and str(a.severity).lower() == "danger"])
        caution_count = len([a for a in alerts if a.severity and str(a.severity).lower() == "caution"])
        
        # Calculate weighted impact
        weighted_alerts = (danger_count * 2.0) + (caution_count * 0.5)
        
        if weighted_alerts == 0:
            return 10.0
            
        # Logarithmic decay formula: score = 10 / (1 + log2(1 + weighted_impact))
        score = 10.0 / (1.0 + math.log(1.0 + weighted_alerts, 2))
        
        # Ensure minimum score of 0.5 so it's never completely zero
        return max(0.5, round(score, 1))
    
