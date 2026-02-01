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
    
    async def calculate_money_saved(
        self,
        broker_account_id: UUID,
        db: AsyncSession
    ) -> Dict:
        """
        Calculate estimated losses prevented by risk intervention.
        
        Logic:
        - When DANGER alert fired, assume it prevented further loss
        - Conservative estimate: 3 prevented trades per DANGER alert
        - Average loss: ₹1,000 per trade
        
        Returns: {
            "this_week": 12000,
            "this_month": 45000,
            "all_time": 120000,
            "prevented_blowups": 2,
            "methodology": "..."
        }
        """
        try:
            # Get ALL alerts for account regardless of severity (to debug filtering)
            all_alerts_result = await db.execute(
                select(RiskAlert).where(
                    RiskAlert.broker_account_id == broker_account_id
                )
            )
            all_alerts = all_alerts_result.scalars().all()
            
            # Debug log severities found
            if all_alerts:
                severities = [a.severity for a in all_alerts]
                unique_severities = set(severities)
                logger.info(f"Found {len(all_alerts)} total alerts. Severities present: {unique_severities}")
                
            # Filter for DANGER in Python (case-insensitive for safety)
            all_danger_alerts = [
                a for a in all_alerts 
                if a.severity and str(a.severity).lower() == "danger"
            ]

            
            logger.info(f"Found {len(all_danger_alerts)} DANGER alerts for money saved calculation")
            
            # If no alerts, return zeros
            if not all_danger_alerts:
                return {
                    "this_week": 0,
                    "this_month": 0,
                    "all_time": 0,
                    "prevented_blowups": 0,
                    "methodology": "Conservative estimate: 3 trades prevented per DANGER alert at ₹1,000 avg loss per trade"
                }
            
            # Calculate time windows - USE TIMEZONE-AWARE DATETIMES
            now = datetime.now(timezone.utc)
            week_start = now - timedelta(days=7)
            month_start = now - timedelta(days=30)
            
            # Conservative estimation parameters
            trades_prevented_per_alert = 3
            avg_loss_per_trade = 1000  # ₹1,000 (conservative)
            loss_prevented_per_alert = avg_loss_per_trade * trades_prevented_per_alert
            
            # Calculate by period
            week_alerts = [a for a in all_danger_alerts if a.detected_at >= week_start]
            month_alerts = [a for a in all_danger_alerts if a.detected_at >= month_start]
            
            this_week_saved = len(week_alerts) * loss_prevented_per_alert
            this_month_saved = len(month_alerts) * loss_prevented_per_alert
            all_time_saved = len(all_danger_alerts) * loss_prevented_per_alert
            
            logger.info(f"Money saved calculation: week={len(week_alerts)}, month={len(month_alerts)}, all={len(all_danger_alerts)}")
            
            # Blowup prevention (5+ DANGER alerts in one day = prevented blowup)
            daily_danger_counts = {}
            for alert in all_danger_alerts:
                date_key = alert.detected_at.date()
                daily_danger_counts[date_key] = daily_danger_counts.get(date_key, 0) + 1
            
            prevented_blowups = sum(1 for count in daily_danger_counts.values() if count >= 5)
            
            result = {
                "this_week": this_week_saved,
                "this_month": this_month_saved,
                "all_time": all_time_saved,
                "prevented_blowups": prevented_blowups,
                "methodology": "Conservative estimate: 3 trades prevented per DANGER alert at ₹1,000 avg loss per trade"
            }
            
            logger.info(f"Money saved result: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to calculate money saved: {e}", exc_info=True)
            return {
                "this_week": 0,
                "this_month": 0,
                "all_time": 0,
                "prevented_blowups": 0,
                "methodology": "Conservative estimate: 3 trades prevented per DANGER alert at ₹1,000 avg loss per trade"
            }
