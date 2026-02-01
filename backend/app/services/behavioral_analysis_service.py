from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
import statistics
import logging

from app.models.trade import Trade

logger = logging.getLogger(__name__)

class BehavioralPattern:
    """Base class for behavioral pattern detection."""
    
    def __init__(self):
        self.name = ""
        self.severity = "medium"  # low, medium, high, critical
        self.is_positive = False  # True for positive patterns
        self.category = ""  # impulse, fear, overconfidence, discipline
    
    def detect(self, trades: List[Trade]) -> Dict:
        """
        Returns: {
            "detected": bool,
            "frequency": int,
            "severity": str,
            "pnl_impact": float,
            "description": str,
            "recommendation": str,
            "affected_trades": List[str]
        }
        """
        raise NotImplementedError
        
    def _calculate_pnl(self, trade: Trade) -> float:
        """Estimate P&L from trade."""
        if hasattr(trade, 'pnl') and trade.pnl is not None:
            return float(trade.pnl)
        return 0.0

    def _no_detection(self) -> Dict:
        return {
            "detected": False,
            "frequency": 0,
            "severity": "none",
            "pnl_impact": 0,
            "description": "",
            "recommendation": "",
            "affected_trades": []
        }

class RevengeTradingPattern(BehavioralPattern):
    """Detects trades taken immediately after losses."""
    
    def __init__(self):
        super().__init__()
        self.name = "Revenge Trading"
        self.severity = "high"
        self.category = "impulse"
    
    def detect(self, trades: List[Trade]) -> Dict:
        if len(trades) < 2:
            return self._no_detection()
        
        sorted_trades = sorted(trades, key=lambda t: t.order_timestamp)
        revenge_trades = []
        total_impact = 0
        
        for i in range(1, len(sorted_trades)):
            prev_trade = sorted_trades[i-1]
            curr_trade = sorted_trades[i]
            
            prev_pnl = self._calculate_pnl(prev_trade)
            if prev_pnl >= 0:
                continue
            
            # Check time gap (within 15 minutes)
            time_gap = (curr_trade.order_timestamp - prev_trade.order_timestamp).total_seconds() / 60
            
            if time_gap < 15:
                revenge_trades.append(curr_trade.order_id)
                curr_pnl = self._calculate_pnl(curr_trade)
                if curr_pnl < 0:
                    total_impact += abs(curr_pnl)
        
        if not revenge_trades:
            return self._no_detection()
        
        return {
            "detected": True,
            "frequency": len(revenge_trades),
            "severity": "high" if len(revenge_trades) >= 3 else "medium",
            "pnl_impact": total_impact,
            "description": f"Entered {len(revenge_trades)} trades within 15 minutes of losses",
            "recommendation": "Wait 15 minutes after any loss before re-entering",
            "affected_trades": revenge_trades
        }

class EmotionalExitPattern(BehavioralPattern):
    """Detects cutting winners early and holding losers long."""
    
    def __init__(self):
        super().__init__()
        self.name = "Emotional Exit"
        self.severity = "medium"
        self.category = "fear"
    
    def detect(self, trades: List[Trade]) -> Dict:
        # Note: This pattern ideally needs 'duration' which we don't strictly have without entry/exit linkage
        # We will use a simplified assumption or placeholder logic until trade linkage is robust
        return self._no_detection() 

class NoCooldownPattern(BehavioralPattern):
    """Detects trading immediately after losses without pause."""
    
    def __init__(self):
        super().__init__()
        self.name = "No Cooldown After Loss"
        self.severity = "high"
        self.category = "impulse"
    
    def detect(self, trades: List[Trade]) -> Dict:
        if len(trades) < 2:
            return self._no_detection()
        
        sorted_trades = sorted(trades, key=lambda t: t.order_timestamp)
        violations = 0
        
        for i in range(1, len(sorted_trades)):
            prev_trade = sorted_trades[i-1]
            curr_trade = sorted_trades[i]
            
            prev_pnl = self._calculate_pnl(prev_trade)
            if prev_pnl >= 0:
                continue
            
            time_gap = (curr_trade.order_timestamp - prev_trade.order_timestamp).total_seconds() / 60
            
            if time_gap < 5:
                violations += 1
        
        if violations == 0:
            return self._no_detection()
        
        return {
            "detected": True,
            "frequency": violations,
            "severity": "critical" if violations >= 5 else "high",
            "pnl_impact": 0,
            "description": f"Traded within 5 minutes of loss {violations} times",
            "recommendation": "Implement mandatory 15-minute cooldown after losses",
            "affected_trades": []
        }

class AfterProfitOverconfidencePattern(BehavioralPattern):
    """Detects increased risk-taking after wins."""
    
    def __init__(self):
        super().__init__()
        self.name = "After-Profit Overconfidence"
        self.severity = "medium"
        self.category = "overconfidence"
    
    def detect(self, trades: List[Trade]) -> Dict:
        if len(trades) < 3:
            return self._no_detection()
        
        sorted_trades = sorted(trades, key=lambda t: t.order_timestamp)
        violations = 0
        
        all_quantities = [t.quantity for t in trades if t.quantity]
        if not all_quantities:
            return self._no_detection()
        
        baseline_qty = statistics.median(all_quantities)
        if baseline_qty == 0: return self._no_detection()

        for i in range(1, len(sorted_trades)):
            prev_trade = sorted_trades[i-1]
            curr_trade = sorted_trades[i]
            
            prev_pnl = self._calculate_pnl(prev_trade)
            if prev_pnl <= 0:
                continue
            
            if curr_trade.quantity > baseline_qty * 1.5:
                violations += 1
        
        if violations == 0:
            return self._no_detection()
        
        return {
            "detected": True,
            "frequency": violations,
            "severity": "medium",
            "pnl_impact": 0,
            "description": f"Increased position size after wins {violations} times",
            "recommendation": "Maintain consistent position sizing regardless of outcomes",
            "affected_trades": []
        }

class StopLossDisciplinePattern(BehavioralPattern):
    """POSITIVE PATTERN: Detects good stop loss usage."""
    
    def __init__(self):
        super().__init__()
        self.name = "Stop Loss Discipline"
        self.severity = "low"
        self.is_positive = True
        self.category = "discipline"
    
    def detect(self, trades: List[Trade]) -> Dict:
        if len(trades) < 5:
            return self._no_detection()
        
        losing_trades = [t for t in trades if self._calculate_pnl(t) < 0]
        if not losing_trades:
            return self._no_detection()
        
        loss_amounts = [abs(self._calculate_pnl(t)) for t in losing_trades]
        
        avg_loss = statistics.mean(loss_amounts)
        max_loss = max(loss_amounts)
        
        if avg_loss == 0: return self._no_detection()

        discipline_ratio = max_loss / avg_loss
        
        if discipline_ratio < 2.5:
            return {
                "detected": True,
                "frequency": len(losing_trades),
                "severity": "positive",
                "pnl_impact": 0,
                "description": f"Consistent loss limiting detected",
                "recommendation": "Excellent risk management. Keep it up!",
                "affected_trades": []
            }
        
        return self._no_detection()

class OvertradingPattern(BehavioralPattern):
    """Detects excessive trading frequency beyond baseline."""
    
    def __init__(self):
        super().__init__()
        self.name = "Overtrading"
        self.severity = "high"
        self.category = "compulsion"
    
    def detect(self, trades: List[Trade]) -> Dict:
        if len(trades) < 10:
            return self._no_detection()
        
        # Calculate trades per day
        if not trades:
            return self._no_detection()
        
        first_trade = min(trades, key=lambda t: t.order_timestamp)
        last_trade = max(trades, key=lambda t: t.order_timestamp)
        
        days = (last_trade.order_timestamp - first_trade.order_timestamp).days + 1
        trades_per_day = len(trades) / days if days > 0 else 0
        
        # Overtrading: >10 trades/day or >5 trades in 1 hour
        if trades_per_day > 10:
            return {
                "detected": True,
                "frequency": len(trades),
                "severity": "high" if trades_per_day > 15 else "medium",
                "pnl_impact": 0,  # Calculate from transaction costs
                "description": f"Average {trades_per_day:.1f} trades/day (baseline: 3-5)",
                "recommendation": "Set max 5 trades per day. Focus on quality over quantity.",
                "affected_trades": []
            }
        
        # Check for clustering (5+ trades in 1 hour)
        sorted_trades = sorted(trades, key=lambda t: t.order_timestamp)
        for i in range(len(sorted_trades) - 4):
            window_trades = sorted_trades[i:i+5]
            time_span = (window_trades[-1].order_timestamp - window_trades[0].order_timestamp).total_seconds() / 3600
            
            if time_span < 1:  # 5 trades in under 1 hour
                return {
                    "detected": True,
                    "frequency": len([t for group in self._find_clusters(sorted_trades) for t in group]),
                    "severity": "high",
                    "pnl_impact": 0,
                    "description": "Multiple trade clusters detected (5+ trades in 1 hour)",
                    "recommendation": "Wait 15 minutes between trades. Avoid impulse entries.",
                    "affected_trades": []
                }
        
        return self._no_detection()
    
    def _find_clusters(self, trades):
        """Find clusters of rapid trades."""
        clusters = []
        # Simplified clustering logic placeholder
        return clusters
    
    def _no_detection(self) -> Dict:
        return {"detected": False, "frequency": 0, "severity": "none", "pnl_impact": 0, "description": "", "recommendation": "", "affected_trades": []}

class MartingaleBehaviorPattern(BehavioralPattern):
    """Detects position doubling after losses."""
    
    def __init__(self):
        super().__init__()
        self.name = "Martingale Behavior"
        self.severity = "critical"
        self.category = "impulse"
    
    def detect(self, trades: List[Trade]) -> Dict:
        if len(trades) < 2:
            return self._no_detection()
        
        sorted_trades = sorted(trades, key=lambda t: t.order_timestamp)
        martingale_instances = 0
        total_impact = 0
        
        for i in range(1, len(sorted_trades)):
            prev_trade = sorted_trades[i-1]
            curr_trade = sorted_trades[i]
            
            prev_pnl = self._calculate_pnl(prev_trade)
            if prev_pnl >= 0:
                continue
            
            # Check if position doubled or increased significantly
            if hasattr(prev_trade, 'quantity') and hasattr(curr_trade, 'quantity') and prev_trade.quantity:
                size_increase = curr_trade.quantity / prev_trade.quantity
                
                if size_increase >= 1.8:  # ~doubled
                    martingale_instances += 1
                    curr_pnl = self._calculate_pnl(curr_trade)
                    if curr_pnl < 0:
                        total_impact += abs(curr_pnl)
        
        if martingale_instances == 0:
            return self._no_detection()
        
        return {
            "detected": True,
            "frequency": martingale_instances,
            "severity": "critical",
            "pnl_impact": total_impact,
            "description": f"Doubled position size after losses {martingale_instances} times",
            "recommendation": "NEVER double down after losses. This is the fastest path to account blow-up.",
            "affected_trades": []
        }
    
    def _calculate_pnl(self, trade: Trade) -> float:
        return getattr(trade, 'pnl', 0) or 0
    
    def _no_detection(self) -> Dict:
        return {"detected": False, "frequency": 0, "severity": "none", "pnl_impact": 0, "description": "", "recommendation": "", "affected_trades": []}

class InconsistentSizingPattern(BehavioralPattern):
    """Detects lack of stable position sizing."""
    
    def __init__(self):
        super().__init__()
        self.name = "Inconsistent Sizing"
        self.severity = "medium"
        self.category = "discipline"
    
    def detect(self, trades: List[Trade]) -> Dict:
        if len(trades) < 5:
            return self._no_detection()
        
        quantities = [t.quantity for t in trades if hasattr(t, 'quantity') and t.quantity]
        
        if not quantities or len(quantities) < 5:
            return self._no_detection()
        
        # Calculate coefficient of variation
        mean_qty = statistics.mean(quantities)
        std_qty = statistics.stdev(quantities)
        
        cv = (std_qty / mean_qty) if mean_qty > 0 else 0
        
        # High variance = inconsistent sizing
        if cv > 0.5:  # 50% variance
            return {
                "detected": True,
                "frequency": len(trades),
                "severity": "medium" if cv > 0.7 else "low",
                "pnl_impact": 0,
                "description": f"Position size varies by {cv*100:.0f}% (should be <30%)",
                "recommendation": "Define fixed position size rules. Use 1-2% of capital per trade consistently.",
                "affected_trades": []
            }
        
        return self._no_detection()
    
    def _no_detection(self) -> Dict:
        return {"detected": False, "frequency": 0, "severity": "none", "pnl_impact": 0, "description": "", "recommendation": "", "affected_trades": []}

class TimeOfDayPattern(BehavioralPattern):
    """Detects high-risk trading during specific times."""
    
    def __init__(self):
        super().__init__()
        self.name = "Time-of-Day Risk"
        self.severity = "medium"
        self.category = "timing"
    
    def detect(self, trades: List[Trade]) -> Dict:
        if len(trades) < 10:
            return self._no_detection()
        
        # Analyze first 15 minutes after open
        first_15_trades = []
        last_hour_trades = []
        
        for trade in trades:
            hour = trade.order_timestamp.hour
            minute = trade.order_timestamp.minute
            
            # First 15 mins (9:15-9:30)
            if hour == 9 and minute < 30:
                first_15_trades.append(trade)
            
            # Last hour (14:30-15:30)
            if hour >= 14 and hour < 15.5:
                last_hour_trades.append(trade)
        
        # Calculate win rates
        if len(first_15_trades) >= 5:
            first_15_wins = sum(1 for t in first_15_trades if self._calculate_pnl(t) > 0)
            first_15_wr = (first_15_wins / len(first_15_trades)) * 100
            
            if first_15_wr < 40:  # Poor win rate
                return {
                    "detected": True,
                    "frequency": len(first_15_trades),
                    "severity": "medium",
                    "pnl_impact": 0,
                    "description": f"Win rate drops to {first_15_wr:.0f}% in first 15 minutes",
                    "recommendation": "Avoid trading first 15 minutes. Wait for volatility to settle.",
                    "affected_trades": []
                }
        
        if len(last_hour_trades) >= 5:
            last_hour_wins = sum(1 for t in last_hour_trades if self._calculate_pnl(t) > 0)
            last_hour_wr = (last_hour_wins / len(last_hour_trades)) * 100
            
            if last_hour_wr < 40:
                return {
                    "detected": True,
                    "frequency": len(last_hour_trades),
                    "severity": "medium",
                    "pnl_impact": 0,
                    "description": f"Win rate drops to {last_hour_wr:.0f}% in last hour",
                    "recommendation": "Stop trading after 2:30 PM. Avoid end-of-day panic.",
                    "affected_trades": []
                }
        
        return self._no_detection()
    
    def _calculate_pnl(self, trade: Trade) -> float:
        return getattr(trade, 'pnl', 0) or 0
    
    def _no_detection(self) -> Dict:
        return {"detected": False, "frequency": 0, "severity": "none", "pnl_impact": 0, "description": "", "recommendation": "", "affected_trades": []}

class HopeDenialPattern(BehavioralPattern):
    """Detects holding losers hoping for reversal."""
    
    def __init__(self):
        super().__init__()
        self.name = "Hope & Denial"
        self.severity = "high"
        self.category = "fear"
    
    def detect(self, trades: List[Trade]) -> Dict:
        # Simplified: detect if average loss is much larger than average win
        # (suggests holding losers, cutting winners)
        
        if len(trades) < 10:
            return self._no_detection()
        
        wins = [abs(self._calculate_pnl(t)) for t in trades if self._calculate_pnl(t) > 0]
        losses = [abs(self._calculate_pnl(t)) for t in trades if self._calculate_pnl(t) < 0]
        
        if not wins or not losses:
            return self._no_detection()
        
        avg_win = statistics.mean(wins)
        avg_loss = statistics.mean(losses)
        
        # If average loss > average win = holding losers
        loss_win_ratio = avg_loss / avg_win if avg_win > 0 else 0
        
        if loss_win_ratio > 1.5:
            return {
                "detected": True,
                "frequency": len(losses),
                "severity": "high",
                "pnl_impact": 0,
                "description": f"Average loss is {loss_win_ratio:.1f}x larger than average win",
                "recommendation": "Cut losses fast at stop loss. Don't hope for reversal.",
                "affected_trades": []
            }
        
        return self._no_detection()
    
    def _calculate_pnl(self, trade: Trade) -> float:
        return getattr(trade, 'pnl', 0) or 0
    
    def _no_detection(self) -> Dict:
        return {"detected": False, "frequency": 0, "severity": "none", "pnl_impact": 0, "description": "", "recommendation": "", "affected_trades": []}

class TiltLossSpiralPattern(BehavioralPattern):
    """COMPOUND STATE: Detects cascading poor decisions."""
    
    def __init__(self):
        super().__init__()
        self.name = "Tilt / Loss Spiral"
        self.severity = "critical"
        self.category = "compound"
    
    def detect(self, trades: List[Trade]) -> Dict:
        if len(trades) < 5:
            return self._no_detection()
        
        sorted_trades = sorted(trades, key=lambda t: t.order_timestamp)
        
        # Find sessions with 4+ consecutive losses
        consecutive_losses = 0
        max_loss_streak = 0
        
        for trade in sorted_trades:
            pnl = self._calculate_pnl(trade)
            if pnl < 0:
                consecutive_losses += 1
                max_loss_streak = max(max_loss_streak, consecutive_losses)
            else:
                consecutive_losses = 0
        
        # Tilt detected if 4+ consecutive losses
        if max_loss_streak >= 4:
            return {
                "detected": True,
                "frequency": 1,
                "severity": "critical",
                "pnl_impact": 0,
                "description": f"Loss spiral detected: {max_loss_streak} consecutive losses",
                "recommendation": "STOP TRADING IMMEDIATELY. Take a day off. This is tilt.",
                "affected_trades": []
            }
        
        return self._no_detection()
    
    def _calculate_pnl(self, trade: Trade) -> float:
        return getattr(trade, 'pnl', 0) or 0
    
    def _no_detection(self) -> Dict:
        return {"detected": False, "frequency": 0, "severity": "none", "pnl_impact": 0, "description": "", "recommendation": "", "affected_trades": []}

from app.services.ai_service import ai_service

class BehavioralAnalysisService:
    # ... existing pattern detection code ...
    """
    Main service for comprehensive behavioral analysis.
    """
    
    def __init__(self):
        self.patterns = [
            RevengeTradingPattern(),
            EmotionalExitPattern(),
            NoCooldownPattern(),
            AfterProfitOverconfidencePattern(),
            StopLossDisciplinePattern(),
            
            # NEW / ENHANCED
            OvertradingPattern(),
            MartingaleBehaviorPattern(),
            InconsistentSizingPattern(),
            TimeOfDayPattern(),
            HopeDenialPattern(),
            TiltLossSpiralPattern(),
        ]
    
    async def analyze_behavior(
        self,
        broker_account_id: UUID,
        db: AsyncSession,
        time_window_days: int = 30
    ) -> Dict:
        """Enhanced comprehensive behavioral analysis WITH AI."""
        
        # Fetch trades
        cutoff = datetime.now() - timedelta(days=time_window_days)
        
        result = await db.execute(
            select(Trade).where(
                Trade.broker_account_id == broker_account_id,
                Trade.order_timestamp >= cutoff
            ).order_by(Trade.order_timestamp)
        )
        all_trades = result.scalars().all()
        
        completed_trades = [t for t in all_trades if t.status == "COMPLETE"]
        
        if len(completed_trades) < 5:
            return self._insufficient_data()
        
        # Run all pattern detections
        detected_patterns = []
        for pattern in self.patterns:
            result = pattern.detect(completed_trades)
            if result["detected"]:
                detected_patterns.append({
                    "name": pattern.name,
                    "category": pattern.category,
                    "is_positive": pattern.is_positive,
                    "frequency": result["frequency"],
                    "severity": result["severity"],
                    "pnl_impact": result["pnl_impact"],
                    "description": result["description"],
                    "recommendation": result["recommendation"]
                })
        
        # Calculate behavioral score
        behavior_score = self._calculate_behavior_score(detected_patterns)
        
        # Determine top strength and focus area
        positive_patterns = [p for p in detected_patterns if p.get("is_positive")]
        negative_patterns = [p for p in detected_patterns if not p.get("is_positive")]
        
        top_strength = positive_patterns[0]["name"] if positive_patterns else "Building consistency"
        focus_area = negative_patterns[0]["name"] if negative_patterns else "None"
        
        # Calculate emotional tax
        emotional_tax = sum(p["pnl_impact"] for p in negative_patterns)
        
        # Time-based performance analysis
        time_performance = await self.calculate_time_performance(completed_trades)

        # 🤖 REAL AI CALL - Generate trading persona
        persona = await ai_service.generate_trading_persona(
            patterns_detected=detected_patterns,
            total_trades=len(completed_trades),
            emotional_tax=emotional_tax,
            time_performance=time_performance
        )
        
        # Emotional breakdown
        total_impact = emotional_tax if emotional_tax > 0 else 1
        emotional_breakdown = {
            p["name"]: round((p["pnl_impact"] / total_impact) * 100, 1)
            for p in negative_patterns
            if p["pnl_impact"] > 0
        }
        
        return {
            "behavior_score": behavior_score,
            "score_trend": "improving",
            "top_strength": top_strength,
            "focus_area": focus_area,
            "patterns_detected": detected_patterns,
            "emotional_tax": round(emotional_tax, 2),
            "emotional_breakdown": emotional_breakdown,
            "total_trades_analyzed": len(completed_trades),
            
            # NEW AI-powered features
            "trading_persona": persona,
            "time_performance": time_performance,
        }
    


    async def calculate_time_performance(
        self,
        trades: List[Trade]
    ) -> Dict:
        """
        Calculate win rate and P&L by time of day.
        """
        
        if len(trades) < 10:
            return {}
        
        # Group trades by hour
        hourly_stats = {}
        
        for trade in trades:
            hour = trade.order_timestamp.hour
            pnl = self._calculate_pnl(trade)
            
            if hour not in hourly_stats:
                hourly_stats[hour] = {"wins": 0, "total": 0, "pnl": 0}
            
            hourly_stats[hour]["total"] += 1
            hourly_stats[hour]["pnl"] += pnl
            if pnl > 0:
                hourly_stats[hour]["wins"] += 1
        
        # Calculate win rates
        for hour, stats in hourly_stats.items():
            stats["winrate"] = (stats["wins"] / stats["total"]) * 100 if stats["total"] > 0 else 0
        
        # Find best and worst
        if not hourly_stats:
            return {}
        
        best_hour = max(hourly_stats.items(), key=lambda x: x[1]["winrate"])
        worst_hour = min(hourly_stats.items(), key=lambda x: x[1]["winrate"])
        
        return {
            "best_hour": f"{best_hour[0]}:00-{best_hour[0]+1}:00",
            "best_hour_winrate": round(best_hour[1]["winrate"], 0),
            "worst_hour": f"{worst_hour[0]}:00-{worst_hour[0]+1}:00",
            "worst_hour_winrate": round(worst_hour[1]["winrate"], 0),
            "hourly_breakdown": {
                f"{h}:00": {
                    "winrate": round(stats["winrate"], 1),
                    "trades": stats["total"],
                    "pnl": round(stats["pnl"], 2)
                }
                for h, stats in sorted(hourly_stats.items())
            }
        }
    
    def _calculate_behavior_score(self, patterns: List[Dict]) -> int:
        """
        Calculate 0-100 behavior score.
        Start at 100, deduct points for negative patterns.
        """
        score = 100
        
        for p in patterns:
            if p.get("is_positive"):
                score += 5
            else:
                sev = p["severity"]
                if sev == "critical": score -= 15
                elif sev == "high": score -= 10
                elif sev == "medium": score -= 5
                elif sev == "low": score -= 2
        
        return max(0, min(100, score))
    
    def _insufficient_data(self) -> Dict:
        return {
            "behavior_score": None,
            "score_trend": "insufficient_data",
            "top_strength": None,
            "focus_area": None,
            "patterns_detected": [],
            "emotional_tax": 0,
            "emotional_breakdown": {},
            "total_trades_analyzed": 0,
            "trading_persona": None,
            "time_performance": None,
        }
    
    def _calculate_pnl(self, trade: Trade) -> float:
        return getattr(trade, 'pnl', 0) or 0.0

    async def tag_trades(
        self,
        broker_account_id: UUID,
        db: AsyncSession
    ) -> Dict[str, str]:
        """
        Tag each trade with behavioral labels.
        """
        
        # Fetch recent completed trades
        result = await db.execute(
            select(Trade).where(
                Trade.broker_account_id == broker_account_id,
                Trade.status == "COMPLETE"
            ).order_by(Trade.order_timestamp.desc())
            .limit(100)
        )
        trades = result.scalars().all()
        # Reverse to analyze chronologically for context
        trades_chron = trades[::-1]
        
        trade_tags = {}
        
        for i, trade in enumerate(trades_chron):
            tag = "Neutral"
            
            if i > 0:
                prev = trades_chron[i-1]
                prev_pnl = self._calculate_pnl(prev)
                time_gap = (trade.order_timestamp - prev.order_timestamp).total_seconds() / 60
                
                if prev_pnl < 0 and time_gap < 15:
                    tag = "Impulsive"
                    # Check for martingale
                    if hasattr(trade, 'quantity') and hasattr(prev, 'quantity') and prev.quantity:
                        if 1.8 <= (trade.quantity / prev.quantity) <= 2.2:
                            tag = "Martingale"

                elif prev_pnl > 0:
                    if hasattr(trade, 'quantity') and hasattr(prev, 'quantity') and trade.quantity > prev.quantity * 1.3:
                        tag = "Overconfident"
                    else:
                        tag = "Disciplined"
                else:
                    tag = "Patient"
            
            trade_tags[trade.order_id] = tag
        
        return trade_tags

