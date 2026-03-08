"""
Track margin utilization for risk management.
"""

from typing import Dict, List, Optional
from uuid import UUID
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import logging

from app.services.zerodha_service import zerodha_client, KiteAPIError
from app.models.broker_account import BrokerAccount
from app.models.margin_snapshot import MarginSnapshot

logger = logging.getLogger(__name__)


class MarginService:
    """
    Monitor margin utilization for trading psychology insights.

    Use cases:
    1. Detect over-leveraging patterns
    2. Pre-trade margin checks
    3. Risk exposure alerts
    """

    # Thresholds for alerts
    MARGIN_WARNING_THRESHOLD = 0.7  # 70% utilization
    MARGIN_DANGER_THRESHOLD = 0.9   # 90% utilization

    async def get_margin_status(
        self,
        broker_account_id: UUID,
        db: AsyncSession
    ) -> Dict:
        """
        Get current margin status and utilization.

        Returns comprehensive margin information with risk assessment.
        """
        # Get broker account
        account = await db.get(BrokerAccount, broker_account_id)
        if not account or not account.access_token:
            return {"error": "Broker account not connected"}

        try:
            access_token = account.decrypt_token(account.access_token)
            margins = await zerodha_client.get_margins(access_token)

            return self._analyze_margins(margins)

        except KiteAPIError as e:
            logger.error(f"Failed to fetch margins: {e}")
            return {"error": str(e)}

    def _analyze_margins(self, margins: Dict) -> Dict:
        """Analyze margin data and calculate utilization"""
        result = {
            "equity": self._analyze_segment(margins.get("equity", {})),
            "commodity": self._analyze_segment(margins.get("commodity", {})),
        }
        
        logger.info(f"Analyzed Margins - Equity: {result['equity']['utilization_pct']}%, Commodity: {result['commodity']['utilization_pct']}%")
        logger.debug(f"Raw Margin Data: {margins}")

        # Calculate overall risk
        max_utilization = max(
            result["equity"]["utilization_pct"],
            result["commodity"]["utilization_pct"]
        )

        if max_utilization >= self.MARGIN_DANGER_THRESHOLD * 100:
            risk_level = "danger"
            risk_message = "Critical margin utilization! Reduce positions immediately."
        elif max_utilization >= self.MARGIN_WARNING_THRESHOLD * 100:
            risk_level = "warning"
            risk_message = "High margin utilization. Consider reducing exposure."
        else:
            risk_level = "safe"
            risk_message = "Margin levels are healthy."

        result["overall"] = {
            "max_utilization_pct": round(max_utilization, 2),
            "risk_level": risk_level,
            "risk_message": risk_message
        }

        return result

    def _analyze_segment(self, segment_data: Dict) -> Dict:
        """Analyze a single segment (equity/commodity)"""
        if not segment_data:
            return {
                "available": 0,
                "used": 0,
                "total": 0,
                "utilization_pct": 0
            }

        available = segment_data.get("available", {})
        utilised = segment_data.get("utilised", {})

        # Calculate totals
        live_balance = float(available.get("live_balance", 0))
        cash = float(available.get("cash", 0))
        collateral = float(available.get("collateral", 0))
        intraday_payin = float(available.get("intraday_payin", 0))

        total_available = live_balance

        # Calculate used margin
        exposure = float(utilised.get("exposure", 0))
        span = float(utilised.get("span", 0))
        option_premium = float(utilised.get("option_premium", 0))
        holding_sales = float(utilised.get("holding_sales", 0))
        turnover = float(utilised.get("turnover", 0))

        total_used = exposure + span + option_premium

        # Total margin = available + used
        total_margin = total_available + total_used

        # Calculate utilization percentage
        utilization_pct = (total_used / total_margin * 100) if total_margin > 0 else 0

        return {
            "available": round(total_available, 2),
            "used": round(total_used, 2),
            "total": round(total_margin, 2),
            "utilization_pct": round(utilization_pct, 2),
            "breakdown": {
                "cash": cash,
                "collateral": collateral,
                "intraday_payin": intraday_payin,
                "exposure": exposure,
                "span": span,
                "option_premium": option_premium
            }
        }

    async def check_margin_for_order(
        self,
        broker_account_id: UUID,
        db: AsyncSession,
        estimated_margin_required: float
    ) -> Dict:
        """
        Check if there's sufficient margin for a new order.

        Args:
            estimated_margin_required: Estimated margin needed for the order

        Returns:
            Dict with sufficiency check and recommendations
        """
        status = await self.get_margin_status(broker_account_id, db)

        if "error" in status:
            return status

        equity = status["equity"]
        available = equity["available"]

        sufficient = available >= estimated_margin_required
        buffer_pct = ((available - estimated_margin_required) / available * 100) if available > 0 else 0

        result = {
            "sufficient": sufficient,
            "available_margin": available,
            "required_margin": estimated_margin_required,
            "remaining_after_order": available - estimated_margin_required,
            "buffer_percentage": round(buffer_pct, 2)
        }

        if not sufficient:
            result["message"] = f"Insufficient margin. Need ₹{estimated_margin_required:,.2f}, have ₹{available:,.2f}"
            result["shortfall"] = estimated_margin_required - available
        elif buffer_pct < 20:
            result["message"] = "Order would leave very low margin buffer. Consider reducing size."
            result["warning"] = True
        else:
            result["message"] = "Sufficient margin available."

        return result

    async def get_margin_history_insight(
        self,
        broker_account_id: UUID,
        db: AsyncSession
    ) -> Dict:
        """
        Generate insights about margin usage patterns with historical trends.
        """
        current = await self.get_margin_status(broker_account_id, db)

        if "error" in current:
            return current

        # Save current snapshot
        await self.save_margin_snapshot(broker_account_id, current, db)

        # Get historical data
        history = await self.get_margin_history(broker_account_id, db, days=7)

        insights = []

        # Generate insights based on current state
        overall = current.get("overall", {})
        risk_level = overall.get("risk_level", "safe")

        if risk_level == "danger":
            insights.append({
                "type": "danger",
                "title": "Over-leveraged Position",
                "message": "Your margin utilization is critically high. This increases risk of margin calls.",
                "action": "Consider closing some positions to reduce exposure."
            })
        elif risk_level == "warning":
            insights.append({
                "type": "warning",
                "title": "High Margin Utilization",
                "message": "You're using most of your available margin. Market moves against you could trigger margin calls.",
                "action": "Avoid adding new positions. Consider setting stop losses."
            })
        else:
            insights.append({
                "type": "positive",
                "title": "Healthy Margin Levels",
                "message": "Your margin utilization is within safe limits.",
                "action": "Continue maintaining disciplined position sizing."
            })

        # Add trend-based insights
        if history["has_data"] and len(history["snapshots"]) >= 3:
            trend_insight = self._analyze_margin_trend(history["snapshots"])
            if trend_insight:
                insights.append(trend_insight)

        return {
            "current_status": current,
            "history": history,
            "insights": insights
        }

    async def save_margin_snapshot(
        self,
        broker_account_id: UUID,
        margin_data: Dict,
        db: AsyncSession
    ) -> MarginSnapshot:
        """
        Save a margin snapshot for historical tracking.
        Called automatically during margin status checks.
        """
        equity = margin_data.get("equity", {})
        commodity = margin_data.get("commodity", {})
        overall = margin_data.get("overall", {})

        snapshot = MarginSnapshot(
            broker_account_id=broker_account_id,
            snapshot_at=datetime.now(timezone.utc),
            equity_available=equity.get("available"),
            equity_used=equity.get("used"),
            equity_total=equity.get("total"),
            equity_utilization_pct=equity.get("utilization_pct"),
            commodity_available=commodity.get("available"),
            commodity_used=commodity.get("used"),
            commodity_total=commodity.get("total"),
            commodity_utilization_pct=commodity.get("utilization_pct"),
            max_utilization_pct=overall.get("max_utilization_pct"),
            risk_level=overall.get("risk_level"),
            equity_breakdown=equity.get("breakdown", {}),
            commodity_breakdown=commodity.get("breakdown", {}),
        )

        db.add(snapshot)
        await db.commit()
        await db.refresh(snapshot)

        logger.debug(f"Saved margin snapshot: {snapshot.id}")
        return snapshot

    async def get_margin_history(
        self,
        broker_account_id: UUID,
        db: AsyncSession,
        days: int = 7
    ) -> Dict:
        """
        Get historical margin snapshots for trend analysis.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        result = await db.execute(
            select(MarginSnapshot).where(
                MarginSnapshot.broker_account_id == broker_account_id,
                MarginSnapshot.snapshot_at >= cutoff
            ).order_by(MarginSnapshot.snapshot_at.desc())
        )
        snapshots = result.scalars().all()

        if not snapshots:
            return {"has_data": False, "snapshots": [], "period_days": days}

        # Calculate statistics
        utilizations = [s.max_utilization_pct or 0 for s in snapshots]
        danger_count = sum(1 for s in snapshots if s.risk_level == "danger")
        warning_count = sum(1 for s in snapshots if s.risk_level == "warning")

        return {
            "has_data": True,
            "period_days": days,
            "snapshot_count": len(snapshots),
            "statistics": {
                "avg_utilization": float(round(sum(utilizations) / len(utilizations), 2)) if utilizations else 0.0,
                "max_utilization": float(round(max(utilizations), 2)) if utilizations else 0.0,
                "min_utilization": float(round(min(utilizations), 2)) if utilizations else 0.0,
                "danger_occurrences": danger_count,
                "warning_occurrences": warning_count,
            },
            "snapshots": [
                {
                    "timestamp": s.snapshot_at.isoformat(),
                    "equity_utilization": float(s.equity_utilization_pct) if s.equity_utilization_pct else 0,
                    "commodity_utilization": float(s.commodity_utilization_pct) if s.commodity_utilization_pct else 0,
                    "max_utilization": float(s.max_utilization_pct) if s.max_utilization_pct else 0,
                    "risk_level": s.risk_level,
                }
                for s in snapshots[:50]  # Limit to 50 for response size
            ]
        }

    def _analyze_margin_trend(self, snapshots: List[Dict]) -> Optional[Dict]:
        """Analyze margin utilization trend from snapshots."""
        if len(snapshots) < 3:
            return None

        # Get recent vs older utilization
        recent = snapshots[:len(snapshots)//2]
        older = snapshots[len(snapshots)//2:]

        recent_avg = sum(s["max_utilization"] for s in recent) / len(recent)
        older_avg = sum(s["max_utilization"] for s in older) / len(older)

        change = recent_avg - older_avg

        if change > 10:
            return {
                "type": "warning",
                "title": "Rising Margin Utilization",
                "message": f"Your margin usage has increased by {change:.1f}% recently. You may be taking on more risk.",
                "action": "Review your position sizes and ensure you have adequate buffer."
            }
        elif change < -10:
            return {
                "type": "positive",
                "title": "Improving Margin Buffer",
                "message": f"Your margin utilization has decreased by {abs(change):.1f}%. Good risk management!",
                "action": "Keep maintaining disciplined position sizing."
            }

        return None


# Singleton instance
margin_service = MarginService()
