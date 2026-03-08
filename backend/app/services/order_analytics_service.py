"""
Analyze order patterns for trading psychology insights.
"""

from typing import Dict, List
from datetime import datetime, timedelta, timezone
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import logging

from app.models.order import Order

logger = logging.getLogger(__name__)


class OrderAnalyticsService:
    """
    Analyze order patterns for behavioral insights.

    Patterns detected:
    1. Order modification frequency (indecision)
    2. Cancel ratio (hesitation)
    3. Rejected orders (margin/price issues)
    4. Order timing patterns
    """

    async def get_order_patterns(
        self,
        broker_account_id: UUID,
        db: AsyncSession,
        days: int = 30
    ) -> Dict:
        """Analyze order patterns over specified period"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        # Get all orders in period
        result = await db.execute(
            select(Order).where(
                Order.broker_account_id == broker_account_id,
                Order.order_timestamp >= cutoff
            )
        )
        orders = result.scalars().all()

        if not orders:
            return {"has_data": False, "message": "No orders found in the specified period"}

        # Calculate metrics
        total_orders = len(orders)
        completed = [o for o in orders if o.status == "COMPLETE"]
        cancelled = [o for o in orders if o.status == "CANCELLED"]
        rejected = [o for o in orders if o.status == "REJECTED"]

        # Cancel ratio
        cancel_ratio = len(cancelled) / total_orders if total_orders > 0 else 0

        # Rejection reasons
        rejection_reasons = {}
        for order in rejected:
            reason = order.status_message or "Unknown"
            # Simplify common reasons
            if "margin" in reason.lower():
                reason = "Insufficient margin"
            elif "price" in reason.lower():
                reason = "Price out of range"
            rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1

        # Order timing analysis
        hourly_distribution = {}
        for order in orders:
            if order.order_timestamp:
                hour = order.order_timestamp.hour
                hourly_distribution[hour] = hourly_distribution.get(hour, 0) + 1

        # Find peak trading hour
        peak_hour = None
        if hourly_distribution:
            peak_hour = max(hourly_distribution.items(), key=lambda x: x[1])[0]

        # Modification frequency (orders with pending != quantity and not fully filled)
        modified_orders = [
            o for o in orders
            if o.pending_quantity > 0 and o.pending_quantity != o.quantity and o.status not in ["COMPLETE", "CANCELLED"]
        ]
        modification_rate = len(modified_orders) / total_orders if total_orders > 0 else 0

        # Calculate fill rate
        total_filled = sum(o.filled_quantity or 0 for o in orders)
        total_quantity = sum(o.quantity or 0 for o in orders)
        fill_rate = total_filled / total_quantity if total_quantity > 0 else 0

        return {
            "has_data": True,
            "period_days": days,
            "summary": {
                "total_orders": total_orders,
                "completed": len(completed),
                "cancelled": len(cancelled),
                "rejected": len(rejected),
                "fill_rate_pct": round(fill_rate * 100, 1)
            },
            "metrics": {
                "cancel_ratio_pct": round(cancel_ratio * 100, 1),
                "modification_rate_pct": round(modification_rate * 100, 1),
                "rejection_reasons": rejection_reasons
            },
            "timing": {
                "hourly_distribution": hourly_distribution,
                "peak_trading_hour": peak_hour,
                "peak_hour_formatted": f"{peak_hour}:00" if peak_hour is not None else None
            },
            "insights": self._generate_insights(cancel_ratio, modification_rate, rejection_reasons, len(rejected))
        }

    def _generate_insights(
        self,
        cancel_ratio: float,
        modification_rate: float,
        rejection_reasons: Dict,
        rejected_count: int
    ) -> List[Dict]:
        """Generate behavioral insights from order patterns"""
        insights = []

        # High cancellation rate
        if cancel_ratio > 0.3:
            insights.append({
                "type": "warning",
                "pattern": "high_cancellation",
                "title": "High Order Cancellation",
                "message": f"You cancelled {cancel_ratio*100:.0f}% of your orders. This may indicate hesitation or lack of conviction.",
                "suggestion": "Consider using limit orders with realistic prices, or take time to analyze before placing orders.",
                "severity": "medium"
            })
        elif cancel_ratio > 0.15:
            insights.append({
                "type": "info",
                "pattern": "moderate_cancellation",
                "title": "Moderate Cancellations",
                "message": f"Your cancellation rate is {cancel_ratio*100:.0f}%. Room for improvement.",
                "suggestion": "Review why you're cancelling orders. Is it price movement or change of mind?",
                "severity": "low"
            })

        # Frequent modifications
        if modification_rate > 0.2:
            insights.append({
                "type": "warning",
                "pattern": "frequent_modification",
                "title": "Order Modification Pattern",
                "message": f"You modified {modification_rate*100:.0f}% of your orders. This suggests indecision during execution.",
                "suggestion": "Define your entry/exit prices before market hours. Stick to your plan.",
                "severity": "medium"
            })

        # Margin issues
        margin_rejections = sum(v for k, v in rejection_reasons.items() if "margin" in k.lower())
        if margin_rejections > 3:
            insights.append({
                "type": "danger",
                "pattern": "margin_issues",
                "title": "Insufficient Margin Pattern",
                "message": f"{margin_rejections} orders rejected due to insufficient margin.",
                "suggestion": "You're trading larger than your capital allows. Reduce position sizes or add funds.",
                "severity": "high"
            })

        # Many rejections overall
        if rejected_count > 10:
            insights.append({
                "type": "warning",
                "pattern": "high_rejections",
                "title": "High Rejection Rate",
                "message": f"{rejected_count} orders were rejected. This affects your execution.",
                "suggestion": "Review rejection reasons and adjust your order parameters.",
                "severity": "medium"
            })

        # Good behavior - low cancellation
        if cancel_ratio < 0.05 and modification_rate < 0.05:
            insights.append({
                "type": "positive",
                "pattern": "disciplined_execution",
                "title": "Disciplined Order Execution",
                "message": "Your order execution is disciplined with low cancellation and modification rates.",
                "suggestion": "Keep up the good work! This indicates clear decision-making.",
                "severity": "positive"
            })

        return insights

    async def get_daily_order_summary(
        self,
        broker_account_id: UUID,
        db: AsyncSession,
        target_date: datetime.date = None
    ) -> Dict:
        """Get order summary for a specific day"""
        if target_date is None:
            target_date = datetime.now(timezone.utc).date()

        start = datetime.combine(target_date, datetime.min.time())
        end = datetime.combine(target_date, datetime.max.time())

        result = await db.execute(
            select(Order).where(
                Order.broker_account_id == broker_account_id,
                Order.order_timestamp >= start,
                Order.order_timestamp <= end
            ).order_by(Order.order_timestamp)
        )
        orders = result.scalars().all()

        if not orders:
            return {"has_data": False, "date": target_date.isoformat()}

        # Group by symbol
        by_symbol = {}
        for order in orders:
            symbol = order.tradingsymbol
            if symbol not in by_symbol:
                by_symbol[symbol] = {"buy": 0, "sell": 0, "orders": 0}
            by_symbol[symbol]["orders"] += 1
            if order.transaction_type == "BUY":
                by_symbol[symbol]["buy"] += order.filled_quantity or 0
            else:
                by_symbol[symbol]["sell"] += order.filled_quantity or 0

        return {
            "has_data": True,
            "date": target_date.isoformat(),
            "total_orders": len(orders),
            "by_status": {
                "complete": len([o for o in orders if o.status == "COMPLETE"]),
                "cancelled": len([o for o in orders if o.status == "CANCELLED"]),
                "rejected": len([o for o in orders if o.status == "REJECTED"]),
                "open": len([o for o in orders if o.status == "OPEN"])
            },
            "by_symbol": by_symbol,
            "first_order_time": orders[0].order_timestamp.isoformat() if orders else None,
            "last_order_time": orders[-1].order_timestamp.isoformat() if orders else None
        }


# Singleton instance
order_analytics_service = OrderAnalyticsService()
