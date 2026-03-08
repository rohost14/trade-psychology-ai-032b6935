"""
Pattern Prediction Engine

Predicts probability of behavioral patterns based on current state.
Uses historical data to calculate real-time risk probabilities.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from uuid import UUID
import statistics
import logging

from app.models.trade import Trade
from app.models.risk_alert import RiskAlert
from app.models.user_profile import UserProfile
from app.models.cooldown import Cooldown

logger = logging.getLogger(__name__)


class PatternPredictionService:
    """
    Predicts probability of behavioral patterns based on:
    1. Current session state (losses, time, trade count)
    2. Historical pattern frequencies
    3. Personal trigger conditions
    """

    async def predict_patterns(
        self,
        broker_account_id: UUID,
        db: AsyncSession,
        current_context: Optional[Dict] = None
    ) -> Dict:
        """
        Calculate real-time probabilities for behavioral patterns.

        Args:
            broker_account_id: User's account ID
            db: Database session
            current_context: Optional context override (for testing)
                - consecutive_losses: int
                - session_pnl: float
                - trades_today: int
                - last_trade_pnl: float
                - minutes_since_last_trade: int

        Returns:
            Predictions with probabilities and recommendations
        """
        now = datetime.now(timezone.utc)

        # Get current session state
        if current_context:
            state = current_context
        else:
            state = await self._get_current_state(broker_account_id, db, now)

        # Get historical patterns for this user
        historical = await self._get_historical_patterns(broker_account_id, db)

        # Calculate probabilities
        predictions = self._calculate_probabilities(state, historical)

        # Generate overall risk assessment
        risk_assessment = self._generate_risk_assessment(predictions, state)

        # Generate actionable recommendations
        recommendations = self._generate_recommendations(predictions, state)

        return {
            "timestamp": now.isoformat(),
            "current_state": state,
            "predictions": predictions,
            "risk_assessment": risk_assessment,
            "recommendations": recommendations,
            "should_alert": risk_assessment["overall_risk"] in ["high", "critical"]
        }

    async def _get_current_state(
        self,
        broker_account_id: UUID,
        db: AsyncSession,
        now: datetime
    ) -> Dict:
        """Extract current trading session state."""
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # Fetch today's trades
        result = await db.execute(
            select(Trade).where(
                and_(
                    Trade.broker_account_id == broker_account_id,
                    Trade.status == "COMPLETE",
                    Trade.order_timestamp >= today_start
                )
            ).order_by(Trade.order_timestamp.desc())
        )
        today_trades = list(result.scalars().all())

        if not today_trades:
            return {
                "consecutive_losses": 0,
                "session_pnl": 0,
                "trades_today": 0,
                "last_trade_pnl": 0,
                "minutes_since_last_trade": 999,
                "time_of_day": now.hour,
                "day_of_week": now.strftime("%A"),
                "is_first_hour": now.hour == 9 and now.minute < 60,
                "is_last_hour": now.hour >= 15,
                "drawdown_from_peak": 0
            }

        # Calculate consecutive losses
        consecutive_losses = 0
        for trade in today_trades:  # Already sorted desc
            if (trade.pnl or 0) < 0:
                consecutive_losses += 1
            else:
                break

        # Session P&L
        session_pnl = sum(float(t.pnl or 0) for t in today_trades)

        # Peak and drawdown
        cumulative = 0
        peak = 0
        for trade in reversed(today_trades):  # Chronological
            cumulative += float(trade.pnl or 0)
            peak = max(peak, cumulative)
        drawdown = peak - cumulative if peak > 0 else abs(min(0, cumulative))

        # Last trade info
        last_trade = today_trades[0]
        minutes_since = (now - last_trade.order_timestamp).total_seconds() / 60 if last_trade.order_timestamp else 999

        return {
            "consecutive_losses": consecutive_losses,
            "session_pnl": round(session_pnl, 2),
            "trades_today": len(today_trades),
            "last_trade_pnl": round(float(last_trade.pnl or 0), 2),
            "minutes_since_last_trade": round(minutes_since, 1),
            "time_of_day": now.hour,
            "day_of_week": now.strftime("%A"),
            "is_first_hour": now.hour == 9,
            "is_last_hour": now.hour >= 15,
            "drawdown_from_peak": round(drawdown, 2)
        }

    async def _get_historical_patterns(
        self,
        broker_account_id: UUID,
        db: AsyncSession
    ) -> Dict:
        """Get historical pattern frequencies and triggers."""
        # Fetch last 60 days of alerts
        cutoff = datetime.now(timezone.utc) - timedelta(days=60)

        result = await db.execute(
            select(RiskAlert).where(
                and_(
                    RiskAlert.broker_account_id == broker_account_id,
                    RiskAlert.detected_at >= cutoff
                )
            )
        )
        alerts = list(result.scalars().all())

        # Fetch trades for context
        trades_result = await db.execute(
            select(Trade).where(
                and_(
                    Trade.broker_account_id == broker_account_id,
                    Trade.status == "COMPLETE",
                    Trade.order_timestamp >= cutoff
                )
            ).order_by(Trade.order_timestamp)
        )
        trades = list(trades_result.scalars().all())

        # Calculate pattern frequencies
        pattern_counts = {}
        for alert in alerts:
            p = alert.pattern_type
            if p not in pattern_counts:
                pattern_counts[p] = {"total": 0, "after_loss": 0, "after_consecutive_loss": 0}
            pattern_counts[p]["total"] += 1

        # Calculate trigger conditions
        # Analyze when revenge trading typically occurs
        revenge_after_loss_count = 0
        revenge_total = pattern_counts.get("revenge_trading", {}).get("total", 0)

        # Calculate average time to revenge trade
        revenge_times = []
        sorted_trades = sorted(trades, key=lambda t: t.order_timestamp)
        for i in range(1, len(sorted_trades)):
            prev = sorted_trades[i-1]
            curr = sorted_trades[i]
            if (prev.pnl or 0) < 0 and (curr.pnl or 0) < 0:
                gap = (curr.order_timestamp - prev.order_timestamp).total_seconds() / 60
                if gap < 30:
                    revenge_times.append(gap)

        avg_revenge_time = statistics.mean(revenge_times) if revenge_times else 15

        # Get user profile for personalized thresholds
        profile_result = await db.execute(
            select(UserProfile).where(UserProfile.broker_account_id == broker_account_id)
        )
        profile = profile_result.scalar_one_or_none()

        return {
            "pattern_counts": pattern_counts,
            "total_alerts": len(alerts),
            "total_trades": len(trades),
            "avg_revenge_time_minutes": round(avg_revenge_time, 1),
            "profile": profile.detected_patterns if profile and profile.detected_patterns else {}
        }

    def _calculate_probabilities(self, state: Dict, historical: Dict) -> Dict:
        """Calculate probability for each pattern type."""
        predictions = {}

        # =========================================================================
        # REVENGE TRADING PROBABILITY
        # =========================================================================
        revenge_prob = 10  # Base probability

        # Factor: Consecutive losses
        if state["consecutive_losses"] >= 1:
            revenge_prob += 15
        if state["consecutive_losses"] >= 2:
            revenge_prob += 20
        if state["consecutive_losses"] >= 3:
            revenge_prob += 25

        # Factor: Time since last trade (shorter = higher risk)
        if state["minutes_since_last_trade"] < 5:
            revenge_prob += 25
        elif state["minutes_since_last_trade"] < 10:
            revenge_prob += 15
        elif state["minutes_since_last_trade"] < 15:
            revenge_prob += 10

        # Factor: Last trade was a loss
        if state["last_trade_pnl"] < 0:
            revenge_prob += 15

        # Factor: Historical pattern frequency
        revenge_history = historical["pattern_counts"].get("revenge_trading", {}).get("total", 0)
        if revenge_history > 10:
            revenge_prob += 10
        elif revenge_history > 5:
            revenge_prob += 5

        predictions["revenge_trading"] = {
            "probability": min(95, revenge_prob),
            "severity": "high",
            "triggers": self._get_active_triggers("revenge", state)
        }

        # =========================================================================
        # TILT / LOSS SPIRAL PROBABILITY
        # =========================================================================
        tilt_prob = 5  # Base

        # Factor: Consecutive losses
        if state["consecutive_losses"] >= 3:
            tilt_prob += 30
        if state["consecutive_losses"] >= 4:
            tilt_prob += 30

        # Factor: Session P&L deep in red
        if state["session_pnl"] < -2000:
            tilt_prob += 20
        elif state["session_pnl"] < -5000:
            tilt_prob += 30

        # Factor: High trade count with losses
        if state["trades_today"] > 7 and state["session_pnl"] < 0:
            tilt_prob += 20

        # Factor: Drawdown from peak
        if state["drawdown_from_peak"] > 2000:
            tilt_prob += 15

        predictions["tilt_loss_spiral"] = {
            "probability": min(95, tilt_prob),
            "severity": "critical",
            "triggers": self._get_active_triggers("tilt", state)
        }

        # =========================================================================
        # OVERTRADING PROBABILITY
        # =========================================================================
        overtrade_prob = 5  # Base

        # Factor: Trade count
        if state["trades_today"] >= 5:
            overtrade_prob += 15
        if state["trades_today"] >= 8:
            overtrade_prob += 25
        if state["trades_today"] >= 10:
            overtrade_prob += 30

        # Factor: Short time between trades
        if state["minutes_since_last_trade"] < 10 and state["trades_today"] > 3:
            overtrade_prob += 15

        # Factor: Time of day (more trading in afternoon = chasing)
        if state["time_of_day"] >= 14 and state["trades_today"] > 5:
            overtrade_prob += 10

        predictions["overtrading"] = {
            "probability": min(95, overtrade_prob),
            "severity": "medium",
            "triggers": self._get_active_triggers("overtrading", state)
        }

        # =========================================================================
        # FOMO PROBABILITY
        # =========================================================================
        fomo_prob = 10  # Base

        # Factor: First hour of market
        if state["is_first_hour"]:
            fomo_prob += 20

        # Factor: Quick successive trades
        if state["minutes_since_last_trade"] < 5 and state["trades_today"] > 2:
            fomo_prob += 15

        # Factor: Day of week (expiry = FOMO)
        if state["day_of_week"] == "Thursday":
            fomo_prob += 15

        predictions["fomo"] = {
            "probability": min(95, fomo_prob),
            "severity": "medium",
            "triggers": self._get_active_triggers("fomo", state)
        }

        # =========================================================================
        # RECOVERY CHASE PROBABILITY
        # =========================================================================
        chase_prob = 5  # Base

        # Factor: In drawdown
        if state["session_pnl"] < -1000:
            chase_prob += 20
        if state["session_pnl"] < -3000:
            chase_prob += 25

        # Factor: High activity while losing
        if state["session_pnl"] < 0 and state["trades_today"] > 5:
            chase_prob += 20

        # Factor: Last hour trading while in red
        if state["is_last_hour"] and state["session_pnl"] < -1000:
            chase_prob += 20

        predictions["recovery_chase"] = {
            "probability": min(95, chase_prob),
            "severity": "high",
            "triggers": self._get_active_triggers("recovery", state)
        }

        return predictions

    def _get_active_triggers(self, pattern_type: str, state: Dict) -> List[str]:
        """Get list of currently active triggers for a pattern."""
        triggers = []

        if pattern_type == "revenge":
            if state["consecutive_losses"] >= 2:
                triggers.append(f"{state['consecutive_losses']} consecutive losses")
            if state["last_trade_pnl"] < 0:
                triggers.append("Last trade was a loss")
            if state["minutes_since_last_trade"] < 15:
                triggers.append(f"Only {state['minutes_since_last_trade']:.0f} min since last trade")

        elif pattern_type == "tilt":
            if state["consecutive_losses"] >= 3:
                triggers.append(f"{state['consecutive_losses']} consecutive losses")
            if state["session_pnl"] < -2000:
                triggers.append(f"Session down ₹{abs(state['session_pnl']):.0f}")
            if state["trades_today"] > 7:
                triggers.append(f"High trade count ({state['trades_today']})")

        elif pattern_type == "overtrading":
            if state["trades_today"] >= 5:
                triggers.append(f"{state['trades_today']} trades today")
            if state["minutes_since_last_trade"] < 10:
                triggers.append("Trading too frequently")

        elif pattern_type == "fomo":
            if state["is_first_hour"]:
                triggers.append("First hour of market")
            if state["day_of_week"] == "Thursday":
                triggers.append("Expiry day volatility")

        elif pattern_type == "recovery":
            if state["session_pnl"] < -1000:
                triggers.append(f"In ₹{abs(state['session_pnl']):.0f} drawdown")
            if state["is_last_hour"]:
                triggers.append("Last hour - running out of time")

        return triggers

    def _generate_risk_assessment(self, predictions: Dict, state: Dict) -> Dict:
        """Generate overall risk assessment."""
        # Get highest probability patterns
        sorted_preds = sorted(
            predictions.items(),
            key=lambda x: x[1]["probability"],
            reverse=True
        )

        highest_prob = sorted_preds[0][1]["probability"] if sorted_preds else 0
        highest_pattern = sorted_preds[0][0] if sorted_preds else None

        # Calculate overall risk
        if highest_prob >= 70:
            overall_risk = "critical"
            color = "red"
            action = "stop_trading"
        elif highest_prob >= 50:
            overall_risk = "high"
            color = "orange"
            action = "take_break"
        elif highest_prob >= 30:
            overall_risk = "medium"
            color = "yellow"
            action = "proceed_cautiously"
        else:
            overall_risk = "low"
            color = "green"
            action = "trade_normally"

        # Count high-risk patterns
        high_risk_count = sum(1 for p in predictions.values() if p["probability"] >= 50)

        return {
            "overall_risk": overall_risk,
            "risk_score": highest_prob,
            "color": color,
            "action": action,
            "dominant_pattern": highest_pattern,
            "high_risk_patterns": high_risk_count,
            "message": self._get_risk_message(overall_risk, highest_pattern, highest_prob, state)
        }

    def _get_risk_message(
        self,
        risk_level: str,
        pattern: str,
        probability: int,
        state: Dict
    ) -> str:
        """Generate human-readable risk message."""
        if risk_level == "critical":
            return f"🛑 STOP TRADING. {probability}% chance of {pattern.replace('_', ' ')}. You're in a danger zone with {state['consecutive_losses']} losses."
        elif risk_level == "high":
            return f"⚠️ HIGH RISK. {probability}% chance of {pattern.replace('_', ' ')}. Take a 15-minute break before your next trade."
        elif risk_level == "medium":
            return f"⚡ Moderate risk. Watch for {pattern.replace('_', ' ')} patterns. Trade with smaller size."
        else:
            return "✅ Low risk. Trade your plan, stay disciplined."

    def _generate_recommendations(self, predictions: Dict, state: Dict) -> List[Dict]:
        """Generate actionable recommendations based on predictions."""
        recommendations = []

        # Sort by probability
        sorted_preds = sorted(
            predictions.items(),
            key=lambda x: x[1]["probability"],
            reverse=True
        )

        for pattern, data in sorted_preds[:3]:  # Top 3 patterns
            if data["probability"] < 30:
                continue

            if pattern == "revenge_trading":
                recommendations.append({
                    "pattern": pattern,
                    "priority": "high" if data["probability"] >= 50 else "medium",
                    "action": "Take a 15-minute break",
                    "specific": f"Set a timer. Your typical revenge window is within {state['minutes_since_last_trade']:.0f} minutes.",
                    "alternative": "Walk away from the screen. Check your phone, get water."
                })

            elif pattern == "tilt_loss_spiral":
                recommendations.append({
                    "pattern": pattern,
                    "priority": "critical",
                    "action": "STOP trading for today",
                    "specific": f"You're down ₹{abs(state['session_pnl']):.0f} with {state['consecutive_losses']} straight losses.",
                    "alternative": "The best trade right now is NO trade. Preserve your capital."
                })

            elif pattern == "overtrading":
                recommendations.append({
                    "pattern": pattern,
                    "priority": "medium",
                    "action": f"No more than {max(0, 5 - state['trades_today'])} more trades today",
                    "specific": f"You've taken {state['trades_today']} trades. Quality > Quantity.",
                    "alternative": "Review your existing trades instead of taking new ones."
                })

            elif pattern == "fomo":
                recommendations.append({
                    "pattern": pattern,
                    "priority": "medium",
                    "action": "Wait for your setup",
                    "specific": "The market will be here tomorrow. Missing one move won't end you.",
                    "alternative": "Use price alerts instead of watching every tick."
                })

            elif pattern == "recovery_chase":
                recommendations.append({
                    "pattern": pattern,
                    "priority": "high",
                    "action": "Accept today's loss",
                    "specific": f"Trying to recover ₹{abs(state['session_pnl']):.0f} usually leads to bigger losses.",
                    "alternative": "Book the loss. Tomorrow is a fresh start with full capital."
                })

        if not recommendations:
            recommendations.append({
                "pattern": None,
                "priority": "low",
                "action": "Trade your plan",
                "specific": "No major risk patterns detected.",
                "alternative": "Stay disciplined and follow your rules."
            })

        return recommendations


# Singleton instance
pattern_prediction_service = PatternPredictionService()
