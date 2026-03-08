from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from zoneinfo import ZoneInfo
from uuid import UUID
import statistics
import logging

IST = ZoneInfo("Asia/Kolkata")

from app.models.trade import Trade
from app.models.completed_trade import CompletedTrade

logger = logging.getLogger(__name__)


class CompletedTradeAdapter:
    """Wraps CompletedTrade to look like Trade for pattern detectors.

    All 27 pattern classes call _calculate_pnl(trade) which reads trade.pnl.
    Trade.pnl is always 0 (raw fills don't carry P&L). Real P&L lives in
    CompletedTrade.realized_pnl. This adapter bridges the gap so all pattern
    classes work without modification.
    """
    def __init__(self, ct: CompletedTrade):
        self.id = ct.id
        self.order_id = str(ct.id)
        self.broker_account_id = ct.broker_account_id
        self.tradingsymbol = ct.tradingsymbol
        self.exchange = ct.exchange
        self.transaction_type = "SELL" if ct.direction == "LONG" else "BUY"
        self.order_timestamp = ct.exit_time
        self.quantity = ct.total_quantity
        self.filled_quantity = ct.total_quantity
        self.price = float(ct.avg_exit_price or 0)
        self.average_price = float(ct.avg_entry_price or 0)
        self.pnl = float(ct.realized_pnl or 0)
        self.product = ct.product
        self.status = "COMPLETE"
        self.status_message = None
        self.duration_minutes = ct.duration_minutes
        self.entry_time = ct.entry_time
        self.exit_time = ct.exit_time
        self.direction = ct.direction
        self.instrument_type = ct.instrument_type

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
    """Detects cutting winners early and holding losers long.

    Uses CompletedTrade.duration_minutes to compare hold time for winners vs losers.
    If losers are held 2x+ longer than winners, that's loss aversion / emotional holding.
    """

    def __init__(self):
        super().__init__()
        self.name = "Emotional Exit"
        self.severity = "medium"
        self.category = "fear"

    def detect(self, trades: List[Trade]) -> Dict:
        # Requires duration_minutes — only available on CompletedTradeAdapter-wrapped trades
        completed = [
            t for t in trades
            if hasattr(t, 'duration_minutes') and t.duration_minutes is not None
        ]
        if len(completed) < 6:
            return self._no_detection()

        winners = [t for t in completed if self._calculate_pnl(t) > 0]
        losers  = [t for t in completed if self._calculate_pnl(t) < 0]
        if len(winners) < 3 or len(losers) < 3:
            return self._no_detection()

        avg_win_dur  = statistics.mean([t.duration_minutes for t in winners])
        avg_loss_dur = statistics.mean([t.duration_minutes for t in losers])

        if avg_win_dur <= 0:
            return self._no_detection()

        ratio = avg_loss_dur / avg_win_dur
        if ratio < 2.0:
            return self._no_detection()

        return {
            "detected": True,
            "frequency": len(losers),
            "severity": "high" if ratio >= 3.0 else "medium",
            "pnl_impact": 0,
            "description": (
                f"Losers held {ratio:.1f}x longer than winners "
                f"(avg winner: {avg_win_dur:.0f}min, avg loser: {avg_loss_dur:.0f}min)"
            ),
            "recommendation": "Set a fixed stop-loss rule. Exit losers faster than winners.",
            "affected_trades": [t.id for t in losers[:5]] if hasattr(losers[0], 'id') else [],
        }

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
                    "frequency": len(window_trades),  # actual count from the window above
                    "severity": "high",
                    "pnl_impact": 0,
                    "description": "Multiple trade clusters detected (5+ trades in 1 hour)",
                    "recommendation": "Wait 15 minutes between trades. Avoid impulse entries.",
                    "affected_trades": []
                }

        return self._no_detection()

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
        val = getattr(trade, 'pnl', 0)
        return float(val) if val is not None else 0.0
    
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
        # Severity: higher CV = higher severity (was inverted before)
        if cv > 0.5:  # 50% variance
            return {
                "detected": True,
                "frequency": len(trades),
                "severity": "high" if cv > 0.8 else ("medium" if cv > 0.6 else "low"),
                "pnl_impact": 0,
                "description": f"Position size varies by {cv*100:.0f}% (should be <30%)",
                "recommendation": "Define fixed position size rules. Use 1-2% of capital per trade consistently.",
                "affected_trades": []
            }
        
        return self._no_detection()
    
    def _no_detection(self) -> Dict:
        return {"detected": False, "frequency": 0, "severity": "none", "pnl_impact": 0, "description": "", "recommendation": "", "affected_trades": []}

class TimeOfDayPattern(BehavioralPattern):
    """Detects high-risk trading during specific times - segment aware."""

    def __init__(self):
        super().__init__()
        self.name = "Time-of-Day Risk"
        self.severity = "medium"
        self.category = "timing"

    def detect(self, trades: List[Trade]) -> Dict:
        if len(trades) < 10:
            return self._no_detection()

        from app.core.market_hours import (
            MarketSegment, get_segment_from_exchange,
            is_high_risk_window
        )

        # Group trades by segment for proper analysis
        segment_trades = {}
        for trade in trades:
            segment = get_segment_from_exchange(trade.exchange or "NSE")
            if segment not in segment_trades:
                segment_trades[segment] = []
            segment_trades[segment].append(trade)

        # Analyze each segment separately
        for segment, seg_trades in segment_trades.items():
            if len(seg_trades) < 5:
                continue

            high_risk_trades = []
            for trade in seg_trades:
                if trade.order_timestamp:
                    is_risky, window_name = is_high_risk_window(segment, trade.order_timestamp)
                    if is_risky:
                        high_risk_trades.append((trade, window_name))

            if len(high_risk_trades) >= 3:
                wins = sum(1 for t, _ in high_risk_trades if self._calculate_pnl(t[0] if isinstance(t, tuple) else t) > 0)
                wr = (wins / len(high_risk_trades)) * 100

                if wr < 40:
                    window_names = list(set(w for _, w in high_risk_trades))
                    segment_name = segment.value

                    # Segment-specific recommendations
                    if segment == MarketSegment.COMMODITY:
                        rec = "Avoid trading during commodity market open (9:00) and close (23:00-23:30)."
                    elif segment == MarketSegment.CURRENCY:
                        rec = "Avoid trading during currency market open (9:00) and close (16:30-17:00)."
                    else:
                        rec = "Avoid trading in first 15 mins and last hour. Wait for volatility to settle."

                    return {
                        "detected": True,
                        "frequency": len(high_risk_trades),
                        "severity": "medium",
                        "pnl_impact": 0,
                        "description": f"{segment_name}: Win rate {wr:.0f}% during {', '.join(window_names)}",
                        "recommendation": rec,
                        "affected_trades": []
                    }

        return self._no_detection()
    
    def _calculate_pnl(self, trade: Trade) -> float:
        val = getattr(trade, 'pnl', 0)
        return float(val) if val is not None else 0.0
    
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
        val = getattr(trade, 'pnl', 0)
        return float(val) if val is not None else 0.0
    
    def _no_detection(self) -> Dict:
        return {"detected": False, "frequency": 0, "severity": "none", "pnl_impact": 0, "description": "", "recommendation": "", "affected_trades": []}

class RecencyBiasPattern(BehavioralPattern):
    """Detects assuming recent outcomes will repeat."""

    def __init__(self):
        super().__init__()
        self.name = "Recency Bias"
        self.severity = "medium"
        self.category = "overconfidence"

    def detect(self, trades: List[Trade]) -> Dict:
        if len(trades) < 10:
            return self._no_detection()

        sorted_trades = sorted(trades, key=lambda t: t.order_timestamp)

        # Check for same-direction persistence after wins
        direction_persistence = 0
        strategy_rigidity = 0

        for i in range(2, len(sorted_trades)):
            prev_prev = sorted_trades[i-2]
            prev = sorted_trades[i-1]
            curr = sorted_trades[i]

            prev_pnl = self._calculate_pnl(prev)
            prev_prev_pnl = self._calculate_pnl(prev_prev)

            # Same direction after consecutive wins
            if prev_pnl > 0 and prev_prev_pnl > 0:
                if (hasattr(curr, 'transaction_type') and hasattr(prev, 'transaction_type')
                    and curr.transaction_type == prev.transaction_type):
                    direction_persistence += 1

                # Same symbol after wins (strategy rigidity)
                if curr.tradingsymbol == prev.tradingsymbol == prev_prev.tradingsymbol:
                    strategy_rigidity += 1

        if direction_persistence >= 3 or strategy_rigidity >= 3:
            return {
                "detected": True,
                "frequency": max(direction_persistence, strategy_rigidity),
                "severity": "medium",
                "pnl_impact": 0,
                "description": f"Repeating same patterns after wins ({direction_persistence} direction repeats, {strategy_rigidity} symbol repeats)",
                "recommendation": "Past wins don't guarantee future success. Evaluate each trade independently.",
                "affected_trades": []
            }

        return self._no_detection()

    def _calculate_pnl(self, trade: Trade) -> float:
        val = getattr(trade, 'pnl', 0)
        return float(val) if val is not None else 0.0

    def _no_detection(self) -> Dict:
        return {"detected": False, "frequency": 0, "severity": "none", "pnl_impact": 0, "description": "", "recommendation": "", "affected_trades": []}


class LossNormalizationPattern(BehavioralPattern):
    """Detects death by a thousand cuts - many small losses accumulating."""

    def __init__(self):
        super().__init__()
        self.name = "Loss Normalization (Death by Cuts)"
        self.severity = "high"
        self.category = "fear"

    def detect(self, trades: List[Trade]) -> Dict:
        if len(trades) < 15:
            return self._no_detection()

        # Calculate P&L distribution
        pnls = [self._calculate_pnl(t) for t in trades]
        losses = [p for p in pnls if p < 0]
        wins = [p for p in pnls if p > 0]

        if len(losses) < 5 or len(wins) < 3:
            return self._no_detection()

        # Check for high frequency small losses
        avg_loss = abs(statistics.mean(losses))
        loss_variance = statistics.stdev(losses) if len(losses) > 1 else 0

        # Low variance = consistent small losses
        # High loss count = frequent losses
        loss_ratio = len(losses) / len(trades)

        # Check if cumulative is negative despite many trades
        total_pnl = sum(pnls)
        avg_win = statistics.mean(wins) if wins else 0

        # Death by cuts: Many small consistent losses, few wins don't compensate
        if (loss_ratio > 0.55  # More than 55% losing trades
            and avg_loss < avg_win * 0.5  # Losses are small individually
            and total_pnl < 0  # Net negative
            and loss_variance < avg_loss):  # Low variance = consistent small losses

            return {
                "detected": True,
                "frequency": len(losses),
                "severity": "high",
                "pnl_impact": abs(total_pnl),
                "description": f"Accumulating {len(losses)} small losses (avg ₹{avg_loss:.0f}) silently draining capital",
                "recommendation": "Small losses add up. Review if your strategy has positive expectancy. Consider tighter entry criteria.",
                "affected_trades": []
            }

        return self._no_detection()

    def _calculate_pnl(self, trade: Trade) -> float:
        val = getattr(trade, 'pnl', 0)
        return float(val) if val is not None else 0.0

    def _no_detection(self) -> Dict:
        return {"detected": False, "frequency": 0, "severity": "none", "pnl_impact": 0, "description": "", "recommendation": "", "affected_trades": []}


class StrategyDriftPattern(BehavioralPattern):
    """Detects unintentional shifts in trading behavior within a session."""

    def __init__(self):
        super().__init__()
        self.name = "Strategy Drift"
        self.severity = "medium"
        self.category = "discipline"

    def detect(self, trades: List[Trade]) -> Dict:
        if len(trades) < 10:
            return self._no_detection()

        # Group trades by day
        from collections import defaultdict
        daily_trades = defaultdict(list)

        for trade in trades:
            if trade.order_timestamp:
                day = trade.order_timestamp.date()
                daily_trades[day].append(trade)

        drift_days = 0
        drift_descriptions = []

        for day, day_trades in daily_trades.items():
            if len(day_trades) < 4:
                continue

            sorted_day = sorted(day_trades, key=lambda t: t.order_timestamp)

            # Split into first half and second half of session
            mid = len(sorted_day) // 2
            first_half = sorted_day[:mid]
            second_half = sorted_day[mid:]

            if len(first_half) < 2 or len(second_half) < 2:
                continue

            # Check for size drift
            first_avg_qty = statistics.mean([t.quantity for t in first_half if t.quantity])
            second_avg_qty = statistics.mean([t.quantity for t in second_half if t.quantity])

            if first_avg_qty > 0:
                size_change = abs(second_avg_qty - first_avg_qty) / first_avg_qty

                if size_change > 0.5:  # 50%+ change in avg size
                    drift_days += 1
                    drift_descriptions.append("position size")

            # Check for frequency drift (trades per hour)
            if len(first_half) >= 2 and len(second_half) >= 2:
                first_duration = (first_half[-1].order_timestamp - first_half[0].order_timestamp).total_seconds() / 3600
                second_duration = (second_half[-1].order_timestamp - second_half[0].order_timestamp).total_seconds() / 3600

                first_rate = len(first_half) / first_duration if first_duration > 0 else 0
                second_rate = len(second_half) / second_duration if second_duration > 0 else 0

                if first_rate > 0 and abs(second_rate - first_rate) / first_rate > 0.5:
                    drift_days += 1
                    drift_descriptions.append("trade frequency")

        if drift_days >= 2:
            return {
                "detected": True,
                "frequency": drift_days,
                "severity": "medium",
                "pnl_impact": 0,
                "description": f"Behavior changed mid-session on {drift_days} days ({', '.join(set(drift_descriptions))})",
                "recommendation": "Stick to your pre-session plan. Don't let emotions change your strategy mid-day.",
                "affected_trades": []
            }

        return self._no_detection()

    def _no_detection(self) -> Dict:
        return {"detected": False, "frequency": 0, "severity": "none", "pnl_impact": 0, "description": "", "recommendation": "", "affected_trades": []}


class EmotionalExitPatternEnhanced(BehavioralPattern):
    """Detects exiting based on emotion rather than structure."""

    def __init__(self):
        super().__init__()
        self.name = "Emotional Exit"
        self.severity = "medium"
        self.category = "fear"

    def detect(self, trades: List[Trade]) -> Dict:
        if len(trades) < 10:
            return self._no_detection()

        # We'll use trade duration as a proxy
        # Winners exited too early, losers held too long

        winners = []
        losers = []

        for trade in trades:
            pnl = self._calculate_pnl(trade)
            # Use filled_quantity * average_price as rough trade value
            trade_value = float((trade.filled_quantity or 0) * (trade.average_price or 0))

            if pnl > 0:
                winners.append({
                    "pnl": pnl,
                    "pnl_percent": (pnl / trade_value * 100) if trade_value > 0 else 0
                })
            elif pnl < 0:
                losers.append({
                    "pnl": abs(pnl),
                    "pnl_percent": (abs(pnl) / trade_value * 100) if trade_value > 0 else 0
                })

        if len(winners) < 3 or len(losers) < 3:
            return self._no_detection()

        # Compare average % gain on winners vs % loss on losers
        avg_win_pct = statistics.mean([w["pnl_percent"] for w in winners])
        avg_loss_pct = statistics.mean([l["pnl_percent"] for l in losers])

        # Emotional exit: Small wins, big losses (cutting winners early, holding losers)
        if avg_loss_pct > avg_win_pct * 1.5 and avg_win_pct < 2:  # Avg win < 2%, losses 1.5x bigger
            return {
                "detected": True,
                "frequency": len(winners) + len(losers),
                "severity": "medium",
                "pnl_impact": 0,
                "description": f"Cutting winners at {avg_win_pct:.1f}% but holding losers to {avg_loss_pct:.1f}%",
                "recommendation": "Let winners run longer. Cut losers faster. Use trailing stops.",
                "affected_trades": []
            }

        return self._no_detection()

    def _calculate_pnl(self, trade: Trade) -> float:
        val = getattr(trade, 'pnl', 0)
        return float(val) if val is not None else 0.0

    def _no_detection(self) -> Dict:
        return {"detected": False, "frequency": 0, "severity": "none", "pnl_impact": 0, "description": "", "recommendation": "", "affected_trades": []}


class ChopZoneAddictionPattern(BehavioralPattern):
    """Detects repeatedly trading without directional conviction."""

    def __init__(self):
        super().__init__()
        self.name = "Chop Zone Addiction"
        self.severity = "medium"
        self.category = "compulsion"

    def detect(self, trades: List[Trade]) -> Dict:
        if len(trades) < 15:
            return self._no_detection()

        # Look for: many small trades, short holding, low variance P&L, no net progress
        pnls = [self._calculate_pnl(t) for t in trades]

        if not pnls:
            return self._no_detection()

        abs_pnls = [abs(p) for p in pnls]
        avg_abs_pnl = statistics.mean(abs_pnls)
        pnl_variance = statistics.stdev(pnls) if len(pnls) > 1 else 0
        total_pnl = sum(pnls)

        # Check for alternating directions
        direction_changes = 0
        for i in range(1, len(trades)):
            prev = trades[i-1]
            curr = trades[i]
            if (hasattr(prev, 'transaction_type') and hasattr(curr, 'transaction_type')
                and prev.transaction_type != curr.transaction_type):
                direction_changes += 1

        direction_change_ratio = direction_changes / (len(trades) - 1) if len(trades) > 1 else 0

        # Chop zone: High frequency, low P&L variance, many direction changes, flat total
        if (len(trades) >= 15
            and pnl_variance < avg_abs_pnl  # Low variance relative to trade size
            and direction_change_ratio > 0.4  # 40%+ trades are direction changes
            and abs(total_pnl) < avg_abs_pnl * 3):  # Net P&L is small relative to activity

            return {
                "detected": True,
                "frequency": len(trades),
                "severity": "medium",
                "pnl_impact": sum(abs_pnls) * 0.1,  # Transaction costs eating capital
                "description": f"Churning: {len(trades)} trades with {direction_changes} direction changes, net P&L only ₹{total_pnl:.0f}",
                "recommendation": "You're trading noise, not trend. Wait for clear setups. Reduce trade frequency.",
                "affected_trades": []
            }

        return self._no_detection()

    def _calculate_pnl(self, trade: Trade) -> float:
        return getattr(trade, 'pnl', 0) or 0

    def _no_detection(self) -> Dict:
        return {"detected": False, "frequency": 0, "severity": "none", "pnl_impact": 0, "description": "", "recommendation": "", "affected_trades": []}


class FalseRecoveryChasePattern(BehavioralPattern):
    """COMPOUND STATE: Attempting to 'get back to zero' emotionally."""

    def __init__(self):
        super().__init__()
        self.name = "False Recovery Chase"
        self.severity = "critical"
        self.category = "compound"

    def detect(self, trades: List[Trade]) -> Dict:
        if len(trades) < 10:
            return self._no_detection()

        sorted_trades = sorted(trades, key=lambda t: t.order_timestamp)

        # Track cumulative P&L and behavior after drawdown
        cumulative_pnl = 0
        max_pnl = 0
        recovery_attempts = 0

        for i, trade in enumerate(sorted_trades):
            pnl = self._calculate_pnl(trade)
            cumulative_pnl += pnl

            if cumulative_pnl > max_pnl:
                max_pnl = cumulative_pnl

            # In drawdown
            drawdown = max_pnl - cumulative_pnl

            if drawdown > 0 and i > 0:
                # Check for recovery chase behavior:
                # - Increased frequency after drawdown
                # - Larger size to recover faster
                # - Worse risk-reward acceptance

                prev_trade = sorted_trades[i-1]
                time_gap = (trade.order_timestamp - prev_trade.order_timestamp).total_seconds() / 60

                # Quick trades during drawdown
                if time_gap < 10 and pnl < 0:
                    # Check if size increased
                    if (trade.quantity and prev_trade.quantity
                        and trade.quantity > prev_trade.quantity):
                        recovery_attempts += 1

        if recovery_attempts >= 3:
            return {
                "detected": True,
                "frequency": recovery_attempts,
                "severity": "critical",
                "pnl_impact": 0,
                "description": f"Chasing recovery: {recovery_attempts} instances of larger, faster trades during drawdown",
                "recommendation": "STOP trying to 'get back to zero'. Accept the loss. Tomorrow is a new day.",
                "affected_trades": []
            }

        return self._no_detection()

    def _calculate_pnl(self, trade: Trade) -> float:
        return getattr(trade, 'pnl', 0) or 0

    def _no_detection(self) -> Dict:
        return {"detected": False, "frequency": 0, "severity": "none", "pnl_impact": 0, "description": "", "recommendation": "", "affected_trades": []}


class EmotionalLoopingPattern(BehavioralPattern):
    """COMPOUND STATE: Cycling between fear, regret, and impulse repeatedly."""

    def __init__(self):
        super().__init__()
        self.name = "Emotional Looping"
        self.severity = "critical"
        self.category = "compound"

    def detect(self, trades: List[Trade]) -> Dict:
        if len(trades) < 20:
            return self._no_detection()

        # Look for repeating behavioral patterns across days
        from collections import defaultdict
        daily_patterns = defaultdict(list)

        for trade in trades:
            if not trade.order_timestamp:
                continue
            day = trade.order_timestamp.date()
            daily_patterns[day].append(trade)

        # Analyze each day's pattern
        day_signatures = []

        for day, day_trades in sorted(daily_patterns.items()):
            if len(day_trades) < 3:
                continue

            sorted_day = sorted(day_trades, key=lambda t: t.order_timestamp)

            # Calculate day signature: start P&L, end P&L, trade count, direction changes
            pnls = [self._calculate_pnl(t) for t in sorted_day]
            total_pnl = sum(pnls)

            # Pattern: start positive, end negative (or vice versa)
            first_half_pnl = sum(pnls[:len(pnls)//2])
            second_half_pnl = sum(pnls[len(pnls)//2:])

            if first_half_pnl > 0 and second_half_pnl < 0:
                signature = "gave_back_gains"
            elif first_half_pnl < 0 and second_half_pnl > 0:
                signature = "recovered"
            elif total_pnl < 0 and len(day_trades) > 5:
                signature = "loss_spiral"
            else:
                signature = "neutral"

            day_signatures.append(signature)

        if len(day_signatures) < 5:
            return self._no_detection()

        # Check for looping: repeating "gave_back_gains" pattern
        gave_back_count = day_signatures.count("gave_back_gains")
        loss_spiral_count = day_signatures.count("loss_spiral")

        if gave_back_count >= 3 or (gave_back_count >= 2 and loss_spiral_count >= 2):
            return {
                "detected": True,
                "frequency": gave_back_count + loss_spiral_count,
                "severity": "critical",
                "pnl_impact": 0,
                "description": f"Emotional loop: {gave_back_count} days of giving back gains, {loss_spiral_count} loss spirals",
                "recommendation": "You're stuck in a cycle. Take 2-3 days off. Journal your emotions. Consider smaller size.",
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

class DispositionEffectPattern(BehavioralPattern):
    """A1: Cutting winners early, holding losers long — measured by hold duration."""

    def __init__(self):
        super().__init__()
        self.name = "Disposition Effect"
        self.severity = "high"
        self.category = "fear"

    def detect(self, trades: List[Trade]) -> Dict:
        if len(trades) < 10:
            return self._no_detection()

        winners = []
        losers = []
        for t in trades:
            pnl = self._calculate_pnl(t)
            dur = getattr(t, 'duration_minutes', None)
            if dur is None or dur <= 0:
                continue
            if pnl > 0:
                winners.append(dur)
            elif pnl < 0:
                losers.append(dur)

        if len(winners) < 5 or len(losers) < 5:
            return self._no_detection()

        avg_win_dur = statistics.mean(winners)
        avg_loss_dur = statistics.mean(losers)

        if avg_loss_dur == 0:
            return self._no_detection()

        ratio = avg_win_dur / avg_loss_dur

        if ratio < 0.5:
            return {
                "detected": True,
                "frequency": len(winners) + len(losers),
                "severity": "high",
                "pnl_impact": 0,
                "description": f"Winners held {avg_win_dur:.0f}min vs losers {avg_loss_dur:.0f}min (ratio: {ratio:.2f}x)",
                "recommendation": "You're cutting winners too early and holding losers too long. Use trailing stops to let winners run.",
                "affected_trades": [],
            }
        return self._no_detection()


class BreakevenObsessionPattern(BehavioralPattern):
    """A2: Frequently exiting trades near breakeven (±0.5% of entry)."""

    def __init__(self):
        super().__init__()
        self.name = "Breakeven Obsession"
        self.severity = "medium"
        self.category = "fear"

    def detect(self, trades: List[Trade]) -> Dict:
        if len(trades) < 10:
            return self._no_detection()

        near_breakeven = 0
        for t in trades:
            avg_price = getattr(t, 'average_price', None) or 0
            pnl = self._calculate_pnl(t)
            qty = getattr(t, 'quantity', 0) or 1
            if avg_price > 0:
                pnl_pct = abs(pnl) / (avg_price * qty) * 100
                if pnl_pct < 0.5:
                    near_breakeven += 1

        if near_breakeven >= 3:
            ratio = round(near_breakeven / len(trades) * 100, 1)
            return {
                "detected": True,
                "frequency": near_breakeven,
                "severity": "medium" if near_breakeven >= 5 else "low",
                "pnl_impact": 0,
                "description": f"{near_breakeven} trades ({ratio}%) closed within ±0.5% of entry — breakeven obsession",
                "recommendation": "Stop anchoring to your entry price. Focus on whether the setup is still valid, not on getting back to breakeven.",
                "affected_trades": [],
            }
        return self._no_detection()


class AddingToLosersPattern(BehavioralPattern):
    """A3: Adding to a losing position (same symbol, additional entry while underwater)."""

    def __init__(self):
        super().__init__()
        self.name = "Adding to Losers"
        self.severity = "critical"
        self.category = "impulse"

    def detect(self, trades: List[Trade]) -> Dict:
        if len(trades) < 3:
            return self._no_detection()

        sorted_trades = sorted(trades, key=lambda t: t.order_timestamp)
        adding_count = 0
        total_impact = 0

        # Track running P&L per symbol
        symbol_running = {}
        for t in sorted_trades:
            sym = t.tradingsymbol
            pnl = self._calculate_pnl(t)
            direction = getattr(t, 'transaction_type', 'BUY')

            if sym in symbol_running:
                prev_pnl, prev_dir = symbol_running[sym]
                # Same direction entry while position is losing
                if prev_pnl < 0 and direction == prev_dir:
                    adding_count += 1
                    if pnl < 0:
                        total_impact += abs(pnl)
                symbol_running[sym] = (prev_pnl + pnl, prev_dir)
            else:
                symbol_running[sym] = (pnl, direction)

        if adding_count >= 2:
            return {
                "detected": True,
                "frequency": adding_count,
                "severity": "critical",
                "pnl_impact": total_impact,
                "description": f"Added to losing positions {adding_count} times — averaging down without edge",
                "recommendation": "NEVER add to a losing position. If your thesis was wrong, exit. Don't compound the mistake.",
                "affected_trades": [],
            }
        return self._no_detection()


class ProfitGiveBackPattern(BehavioralPattern):
    """A4: Session peak P&L significantly higher than session close P&L."""

    def __init__(self):
        super().__init__()
        self.name = "Profit Give-Back"
        self.severity = "high"
        self.category = "discipline"

    def detect(self, trades: List[Trade]) -> Dict:
        if len(trades) < 5:
            return self._no_detection()

        from collections import defaultdict
        daily_trades = defaultdict(list)
        for t in trades:
            if t.order_timestamp:
                day = t.order_timestamp.date()
                daily_trades[day].append(t)

        giveback_days = 0
        total_given_back = 0

        for day, day_trades in daily_trades.items():
            if len(day_trades) < 3:
                continue
            sorted_day = sorted(day_trades, key=lambda t: t.order_timestamp)
            cumulative = 0
            peak = 0
            for t in sorted_day:
                cumulative += self._calculate_pnl(t)
                peak = max(peak, cumulative)

            # Give-back: peak was positive, ended at ≤30% of peak
            if peak > 100 and cumulative <= peak * 0.3:
                giveback_days += 1
                total_given_back += (peak - cumulative)

        if giveback_days >= 2:
            return {
                "detected": True,
                "frequency": giveback_days,
                "severity": "high",
                "pnl_impact": total_given_back,
                "description": f"Gave back profits on {giveback_days} days (total ₹{total_given_back:,.0f} given back)",
                "recommendation": "Set a 'profit lock' rule: once up 50%+ of your daily target, tighten stops or reduce size. Don't let winners become losers.",
                "affected_trades": [],
            }
        return self._no_detection()


class EndOfDayRushPattern(BehavioralPattern):
    """A5: Disproportionate trades in last 30 minutes (after 3PM IST)."""

    def __init__(self):
        super().__init__()
        self.name = "End-of-Day Rush"
        self.severity = "medium"
        self.category = "impulse"

    def detect(self, trades: List[Trade]) -> Dict:
        if len(trades) < 10:
            return self._no_detection()

        from collections import defaultdict
        daily_trades = defaultdict(list)
        for t in trades:
            if t.order_timestamp:
                # Group by IST date (not UTC date)
                ist_time = t.order_timestamp.astimezone(IST)
                daily_trades[ist_time.date()].append(t)

        rush_days = 0
        for day, day_trades in daily_trades.items():
            if len(day_trades) < 3:
                continue
            # Check entry hour in IST
            late_count = 0
            for t in day_trades:
                ist_time = t.order_timestamp.astimezone(IST)
                if ist_time.hour >= 15:
                    late_count += 1

            if late_count / len(day_trades) >= 0.30:
                rush_days += 1

        if rush_days >= 2:
            return {
                "detected": True,
                "frequency": rush_days,
                "severity": "medium",
                "pnl_impact": 0,
                "description": f"30%+ of trades placed after 3PM IST on {rush_days} days — end-of-day rush",
                "recommendation": "Last-hour trades have higher volatility and wider spreads. Set a cutoff at 3:00 PM for new entries.",
                "affected_trades": [],
            }
        return self._no_detection()


class ExpiryDayGamblingPattern(BehavioralPattern):
    """A6: Significantly higher activity on expiry days (Thursdays / monthly expiry)."""

    def __init__(self):
        super().__init__()
        self.name = "Expiry Day Gambling"
        self.severity = "high"
        self.category = "impulse"

    def detect(self, trades: List[Trade]) -> Dict:
        if len(trades) < 10:
            return self._no_detection()

        from collections import defaultdict
        daily_counts = defaultdict(int)
        daily_sizes = defaultdict(list)
        is_expiry = {}

        for t in trades:
            if not t.order_timestamp:
                continue
            # Use IST date to correctly identify expiry Thursdays
            ist_time = t.order_timestamp.astimezone(IST)
            day = ist_time.date()
            daily_counts[day] += 1
            daily_sizes[day].append(t.quantity or 0)
            # Check if it's a Thursday (weekly expiry) or feature flag
            feat = getattr(t, 'feature', None)
            if feat and hasattr(feat, 'is_expiry_day') and feat.is_expiry_day:
                is_expiry[day] = True
            elif ist_time.weekday() == 3:  # Thursday in IST
                is_expiry[day] = True

        if not is_expiry:
            return self._no_detection()

        expiry_counts = [daily_counts[d] for d in is_expiry]
        non_expiry_counts = [c for d, c in daily_counts.items() if d not in is_expiry]

        if not non_expiry_counts:
            return self._no_detection()

        avg_normal = statistics.mean(non_expiry_counts)
        avg_expiry = statistics.mean(expiry_counts)

        if avg_normal == 0:
            return self._no_detection()

        ratio = avg_expiry / avg_normal

        if ratio >= 1.5:
            return {
                "detected": True,
                "frequency": len(expiry_counts),
                "severity": "high" if ratio >= 2 else "medium",
                "pnl_impact": 0,
                "description": f"Expiry days: {avg_expiry:.0f} trades/day vs normal {avg_normal:.0f}/day ({ratio:.1f}x increase)",
                "recommendation": "Expiry day volatility is not an edge — it's noise. Reduce size by 50% on expiry or skip it entirely.",
                "affected_trades": [],
            }
        return self._no_detection()


class BoredomTradingPattern(BehavioralPattern):
    """A7: Small-size, short-duration trades with near-zero P&L (trading for the sake of it)."""

    def __init__(self):
        super().__init__()
        self.name = "Boredom Trading"
        self.severity = "medium"
        self.category = "compulsion"

    def detect(self, trades: List[Trade]) -> Dict:
        if len(trades) < 15:
            return self._no_detection()

        all_qty = [t.quantity for t in trades if t.quantity and t.quantity > 0]
        if not all_qty:
            return self._no_detection()

        median_qty = statistics.median(all_qty)
        all_durations = [getattr(t, 'duration_minutes', None) or 0 for t in trades]
        median_dur = statistics.median(all_durations) if all_durations else 30

        boredom_count = 0
        for t in trades:
            pnl = abs(self._calculate_pnl(t))
            qty = t.quantity or 0
            dur = getattr(t, 'duration_minutes', None) or 0

            # Small size, short duration, near-zero P&L
            is_small = qty <= median_qty * 0.5 if median_qty > 0 else False
            is_short = dur < max(median_dur * 0.3, 5) if median_dur > 0 else dur < 5
            price = getattr(t, 'average_price', 0) or 1
            is_tiny_pnl = pnl < price * qty * 0.003 if qty > 0 and price > 0 else pnl < 50

            if is_small and is_short and is_tiny_pnl:
                boredom_count += 1

        if boredom_count >= 5:
            ratio = round(boredom_count / len(trades) * 100, 1)
            return {
                "detected": True,
                "frequency": boredom_count,
                "severity": "medium",
                "pnl_impact": 0,
                "description": f"{boredom_count} boredom trades ({ratio}%) — small size, quick exit, negligible P&L",
                "recommendation": "These trades have no edge. If you're bored, close the terminal. Go for a walk. Boredom is not a signal.",
                "affected_trades": [],
            }
        return self._no_detection()


class ConcentrationRiskPattern(BehavioralPattern):
    """A8: Over 60% of trades concentrated in a single instrument."""

    def __init__(self):
        super().__init__()
        self.name = "Concentration Risk"
        self.severity = "medium"
        self.category = "discipline"

    def detect(self, trades: List[Trade]) -> Dict:
        if len(trades) < 10:
            return self._no_detection()

        from collections import Counter
        symbol_counts = Counter(t.tradingsymbol for t in trades if t.tradingsymbol)

        if not symbol_counts:
            return self._no_detection()

        top_symbol, top_count = symbol_counts.most_common(1)[0]
        concentration = top_count / len(trades) * 100

        if concentration > 60:
            return {
                "detected": True,
                "frequency": top_count,
                "severity": "medium" if concentration > 75 else "low",
                "pnl_impact": 0,
                "description": f"{concentration:.0f}% of trades in {top_symbol} — high concentration risk",
                "recommendation": f"Diversify across instruments. Over-concentrating in {top_symbol} amplifies both gains and losses. Trade 2-3 instruments.",
                "affected_trades": [],
            }
        return self._no_detection()


class MaxDailyLossBreachPattern(BehavioralPattern):
    """A9: Any day where loss exceeds 2x average daily loss."""

    def __init__(self):
        super().__init__()
        self.name = "Max Daily Loss Breach"
        self.severity = "critical"
        self.category = "discipline"

    def detect(self, trades: List[Trade]) -> Dict:
        if len(trades) < 10:
            return self._no_detection()

        from collections import defaultdict
        daily_pnl = defaultdict(float)
        for t in trades:
            if t.order_timestamp:
                day = t.order_timestamp.date()
                daily_pnl[day] += self._calculate_pnl(t)

        daily_losses = [abs(v) for v in daily_pnl.values() if v < 0]

        if len(daily_losses) < 3:
            return self._no_detection()

        avg_daily_loss = statistics.mean(daily_losses)
        breach_days = [(d, v) for d, v in daily_pnl.items() if v < 0 and abs(v) > avg_daily_loss * 2]

        if breach_days:
            worst_day = min(breach_days, key=lambda x: x[1])
            total_breach_loss = sum(abs(v) for _, v in breach_days)
            return {
                "detected": True,
                "frequency": len(breach_days),
                "severity": "critical",
                "pnl_impact": total_breach_loss,
                "description": f"{len(breach_days)} days exceeded 2x avg daily loss (avg: ₹{avg_daily_loss:,.0f}, worst: ₹{abs(worst_day[1]):,.0f})",
                "recommendation": "Set a hard daily loss limit at 2x your average loss. When hit, STOP trading for the day. No exceptions.",
                "affected_trades": [],
            }
        return self._no_detection()


class GamblersFallacyPattern(BehavioralPattern):
    """A10: Same direction entry 3+ times after consecutive same-direction losses."""

    def __init__(self):
        super().__init__()
        self.name = "Gambler's Fallacy"
        self.severity = "high"
        self.category = "impulse"

    def detect(self, trades: List[Trade]) -> Dict:
        if len(trades) < 6:
            return self._no_detection()

        sorted_trades = sorted(trades, key=lambda t: t.order_timestamp)
        fallacy_count = 0

        for i in range(3, len(sorted_trades)):
            # Look back at last 3 trades
            prev_3 = sorted_trades[i-3:i]
            current = sorted_trades[i]

            # Check if last 3 were same direction and all losses
            prev_dirs = [getattr(t, 'transaction_type', '') for t in prev_3]
            prev_pnls = [self._calculate_pnl(t) for t in prev_3]

            if (len(set(prev_dirs)) == 1  # All same direction
                and all(p < 0 for p in prev_pnls)  # All losses
                and getattr(current, 'transaction_type', '') == prev_dirs[0]):  # Repeating same direction
                fallacy_count += 1

        if fallacy_count >= 2:
            return {
                "detected": True,
                "frequency": fallacy_count,
                "severity": "high",
                "pnl_impact": 0,
                "description": f"Repeated same direction {fallacy_count} times after 3+ consecutive losses in that direction",
                "recommendation": "Past losses don't make the next trade more likely to win. After 3 same-direction losses, switch to observation mode.",
                "affected_trades": [],
            }
        return self._no_detection()


from app.services.ai_service import ai_service

class BehavioralAnalysisService:
    # ... existing pattern detection code ...
    """
    Main service for comprehensive behavioral analysis.
    """
    
    def __init__(self):
        self.patterns = [
            # PRIMARY BIASES
            RevengeTradingPattern(),
            NoCooldownPattern(),
            AfterProfitOverconfidencePattern(),
            StopLossDisciplinePattern(),  # Positive pattern

            # BEHAVIORAL PATTERNS
            OvertradingPattern(),
            MartingaleBehaviorPattern(),
            InconsistentSizingPattern(),
            TimeOfDayPattern(),
            HopeDenialPattern(),

            # NEW PATTERNS FROM BEHAVIORAL DOC
            RecencyBiasPattern(),           # Same direction after wins
            LossNormalizationPattern(),     # Death by small cuts
            StrategyDriftPattern(),         # Mid-session behavior change
            EmotionalExitPatternEnhanced(), # Winners cut early, losers held
            ChopZoneAddictionPattern(),     # Directionless trading

            # COMPOUND STATES
            TiltLossSpiralPattern(),
            FalseRecoveryChasePattern(),    # Trying to get back to zero
            EmotionalLoopingPattern(),      # Cycling patterns

            # PHASE A: 10 NEW PATTERNS (25 → 35)
            DispositionEffectPattern(),      # A1: Cut winners early, hold losers
            BreakevenObsessionPattern(),     # A2: Exiting at ±0.5% of entry
            AddingToLosersPattern(),         # A3: Averaging down without edge
            ProfitGiveBackPattern(),         # A4: Session peak → give back gains
            EndOfDayRushPattern(),           # A5: 30%+ trades after 3PM IST
            ExpiryDayGamblingPattern(),      # A6: 1.5x activity on expiry days
            BoredomTradingPattern(),         # A7: Small, quick, pointless trades
            ConcentrationRiskPattern(),      # A8: >60% in one instrument
            MaxDailyLossBreachPattern(),     # A9: Day loss > 2x avg
            GamblersFallacyPattern(),        # A10: Same direction after 3 losses
        ]
    
    async def analyze_behavior(
        self,
        broker_account_id: UUID,
        db: AsyncSession,
        time_window_days: int = 30
    ) -> Dict:
        """Enhanced comprehensive behavioral analysis WITH AI."""
        
        # Fetch completed trades (real P&L lives here, not in Trade table)
        cutoff = datetime.now() - timedelta(days=time_window_days)

        ct_result = await db.execute(
            select(CompletedTrade).where(
                CompletedTrade.broker_account_id == broker_account_id,
                CompletedTrade.exit_time >= cutoff
            ).order_by(CompletedTrade.exit_time)
        )
        completed_trades = [CompletedTradeAdapter(ct) for ct in ct_result.scalars().all()]
        
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

        # 🤖 AI CALL - Generate trading persona (with 24hr cache)
        persona = None
        try:
            from app.models.user_profile import UserProfile
            from sqlalchemy import select as sa_select
            profile_result = await db.execute(
                sa_select(UserProfile).where(UserProfile.broker_account_id == broker_account_id)
            )
            profile = profile_result.scalar_one_or_none()

            # Check cache first
            if profile and profile.ai_cache:
                cached_persona = profile.ai_cache.get("persona")
                if cached_persona:
                    cached_at = cached_persona.get("generated_at", "")
                    try:
                        from datetime import timezone as tz
                        gen_time = datetime.fromisoformat(cached_at)
                        if datetime.now(tz.utc) - gen_time < timedelta(hours=24):
                            persona = cached_persona.get("data")
                            logger.info("Using cached AI persona (< 24hr old)")
                    except (ValueError, TypeError):
                        pass

            if persona is None:
                persona = await ai_service.generate_trading_persona(
                    patterns_detected=detected_patterns,
                    total_trades=len(completed_trades),
                    emotional_tax=emotional_tax,
                    time_performance=time_performance
                )
                # Cache the result
                if profile and persona:
                    from datetime import timezone as tz
                    current_cache = dict(profile.ai_cache or {})
                    current_cache["persona"] = {
                        "data": persona,
                        "generated_at": datetime.now(tz.utc).isoformat(),
                    }
                    profile.ai_cache = current_cache
                    await db.commit()
                    logger.info("Cached AI persona for 24hr reuse")
        except Exception as persona_err:
            logger.warning(f"Persona generation/caching failed: {persona_err}")
            if persona is None:
                persona = ai_service._fallback_persona(
                    [p for p in detected_patterns if not p.get("is_positive")],
                    [p for p in detected_patterns if p.get("is_positive")]
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
        
        # Fetch recent completed trades (real P&L in CompletedTrade, not Trade)
        ct_result = await db.execute(
            select(CompletedTrade).where(
                CompletedTrade.broker_account_id == broker_account_id,
            ).order_by(CompletedTrade.exit_time.desc())
            .limit(100)
        )
        trades = [CompletedTradeAdapter(ct) for ct in ct_result.scalars().all()]
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

