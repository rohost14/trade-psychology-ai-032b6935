"""
AI Personalization Service

Learns individual trader patterns and provides personalized insights:
1. Personal Pattern Learning (time-based) - YOUR specific danger hours/days
2. Symbol-specific Weakness Detection - YOUR problem symbols
3. Predictive Alerts - Alert BEFORE your typical danger windows
4. AI-based Intervention Timing - Learn YOUR optimal cooldown duration
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from uuid import UUID
import statistics
import logging

from app.models.trade import Trade
from app.models.risk_alert import RiskAlert
from app.models.cooldown import Cooldown
from app.models.user_profile import UserProfile

logger = logging.getLogger(__name__)


class AIPersonalizationService:
    """
    Learns trader-specific patterns for personalized intervention.
    """

    async def learn_patterns(
        self,
        broker_account_id: UUID,
        db: AsyncSession,
        days_back: int = 90
    ) -> Dict:
        """
        Comprehensive pattern learning for a trader.
        Returns learned insights to be stored in user_profile.detected_patterns
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)

        # Fetch trades
        result = await db.execute(
            select(Trade).where(
                Trade.broker_account_id == broker_account_id,
                Trade.status == "COMPLETE",
                Trade.order_timestamp >= cutoff
            ).order_by(Trade.order_timestamp)
        )
        trades = list(result.scalars().all())

        if len(trades) < 20:
            return {"insufficient_data": True, "trades_analyzed": len(trades)}

        # Learn all patterns
        time_patterns = self._learn_time_patterns(trades)
        symbol_patterns = self._learn_symbol_patterns(trades)
        intervention_timing = await self._learn_intervention_timing(broker_account_id, db, trades)
        predictive_windows = self._calculate_predictive_windows(time_patterns, symbol_patterns)

        learned_patterns = {
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "trades_analyzed": len(trades),
            "time_patterns": time_patterns,
            "symbol_patterns": symbol_patterns,
            "intervention_timing": intervention_timing,
            "predictive_windows": predictive_windows,
        }

        # Store in user profile
        await self._store_learned_patterns(broker_account_id, db, learned_patterns)

        return learned_patterns

    def _learn_time_patterns(self, trades: List[Trade]) -> Dict:
        """
        Learn trader's performance by time of day and day of week.
        Returns YOUR specific danger windows.
        """
        # Hourly analysis
        hourly_stats = {}
        for trade in trades:
            if not trade.order_timestamp:
                continue
            hour = trade.order_timestamp.hour
            pnl = float(trade.pnl or 0)

            if hour not in hourly_stats:
                hourly_stats[hour] = {"wins": 0, "losses": 0, "total_pnl": 0, "trades": 0}

            hourly_stats[hour]["trades"] += 1
            hourly_stats[hour]["total_pnl"] += pnl
            if pnl > 0:
                hourly_stats[hour]["wins"] += 1
            elif pnl < 0:
                hourly_stats[hour]["losses"] += 1

        # Day of week analysis
        daily_stats = {}
        for trade in trades:
            if not trade.order_timestamp:
                continue
            day = trade.order_timestamp.strftime("%A")  # Monday, Tuesday, etc.
            pnl = float(trade.pnl or 0)

            if day not in daily_stats:
                daily_stats[day] = {"wins": 0, "losses": 0, "total_pnl": 0, "trades": 0}

            daily_stats[day]["trades"] += 1
            daily_stats[day]["total_pnl"] += pnl
            if pnl > 0:
                daily_stats[day]["wins"] += 1
            elif pnl < 0:
                daily_stats[day]["losses"] += 1

        # Calculate win rates
        for hour, stats in hourly_stats.items():
            total = stats["wins"] + stats["losses"]
            stats["win_rate"] = round((stats["wins"] / total) * 100, 1) if total > 0 else 50

        for day, stats in daily_stats.items():
            total = stats["wins"] + stats["losses"]
            stats["win_rate"] = round((stats["wins"] / total) * 100, 1) if total > 0 else 50

        # Find danger windows (win rate < 35% with at least 5 trades)
        danger_hours = [
            {"hour": h, "win_rate": s["win_rate"], "trades": s["trades"], "avg_pnl": round(s["total_pnl"] / s["trades"], 2)}
            for h, s in hourly_stats.items()
            if s["win_rate"] < 35 and s["trades"] >= 5
        ]

        danger_days = [
            {"day": d, "win_rate": s["win_rate"], "trades": s["trades"], "avg_pnl": round(s["total_pnl"] / s["trades"], 2)}
            for d, s in daily_stats.items()
            if s["win_rate"] < 35 and s["trades"] >= 5
        ]

        # Find best windows (win rate > 55% with at least 5 trades)
        best_hours = [
            {"hour": h, "win_rate": s["win_rate"], "trades": s["trades"], "avg_pnl": round(s["total_pnl"] / s["trades"], 2)}
            for h, s in hourly_stats.items()
            if s["win_rate"] > 55 and s["trades"] >= 5
        ]

        best_days = [
            {"day": d, "win_rate": s["win_rate"], "trades": s["trades"], "avg_pnl": round(s["total_pnl"] / s["trades"], 2)}
            for d, s in daily_stats.items()
            if s["win_rate"] > 55 and s["trades"] >= 5
        ]

        # Sort by severity
        danger_hours.sort(key=lambda x: x["win_rate"])
        danger_days.sort(key=lambda x: x["win_rate"])
        best_hours.sort(key=lambda x: x["win_rate"], reverse=True)
        best_days.sort(key=lambda x: x["win_rate"], reverse=True)

        return {
            "danger_hours": danger_hours[:3],  # Top 3 worst hours
            "danger_days": danger_days[:2],    # Top 2 worst days
            "best_hours": best_hours[:3],      # Top 3 best hours
            "best_days": best_days[:2],        # Top 2 best days
            "hourly_breakdown": {
                str(h): {
                    "win_rate": s["win_rate"],
                    "trades": s["trades"],
                    "pnl": round(s["total_pnl"], 2)
                }
                for h, s in hourly_stats.items()
            },
            "daily_breakdown": {
                d: {
                    "win_rate": s["win_rate"],
                    "trades": s["trades"],
                    "pnl": round(s["total_pnl"], 2)
                }
                for d, s in daily_stats.items()
            }
        }

    def _learn_symbol_patterns(self, trades: List[Trade]) -> Dict:
        """
        Learn which symbols the trader performs well/poorly on.
        """
        symbol_stats = {}

        for trade in trades:
            symbol = trade.tradingsymbol
            if not symbol:
                continue

            # Normalize symbol (remove expiry dates for options/futures)
            base_symbol = self._normalize_symbol(symbol)
            pnl = float(trade.pnl or 0)

            if base_symbol not in symbol_stats:
                symbol_stats[base_symbol] = {
                    "wins": 0, "losses": 0, "total_pnl": 0,
                    "trades": 0, "variants": set()
                }

            symbol_stats[base_symbol]["trades"] += 1
            symbol_stats[base_symbol]["total_pnl"] += pnl
            symbol_stats[base_symbol]["variants"].add(symbol)
            if pnl > 0:
                symbol_stats[base_symbol]["wins"] += 1
            elif pnl < 0:
                symbol_stats[base_symbol]["losses"] += 1

        # Calculate win rates
        for symbol, stats in symbol_stats.items():
            total = stats["wins"] + stats["losses"]
            stats["win_rate"] = round((stats["wins"] / total) * 100, 1) if total > 0 else 50
            stats["avg_pnl"] = round(stats["total_pnl"] / stats["trades"], 2) if stats["trades"] > 0 else 0
            stats["variants"] = len(stats["variants"])

        # Find problem symbols (win rate < 35% with at least 5 trades)
        problem_symbols = [
            {
                "symbol": s,
                "win_rate": stats["win_rate"],
                "trades": stats["trades"],
                "total_loss": abs(stats["total_pnl"]) if stats["total_pnl"] < 0 else 0,
                "avg_pnl": stats["avg_pnl"]
            }
            for s, stats in symbol_stats.items()
            if stats["win_rate"] < 35 and stats["trades"] >= 5
        ]

        # Find strong symbols (win rate > 55% with at least 5 trades)
        strong_symbols = [
            {
                "symbol": s,
                "win_rate": stats["win_rate"],
                "trades": stats["trades"],
                "total_profit": stats["total_pnl"] if stats["total_pnl"] > 0 else 0,
                "avg_pnl": stats["avg_pnl"]
            }
            for s, stats in symbol_stats.items()
            if stats["win_rate"] > 55 and stats["trades"] >= 5
        ]

        # Sort by impact
        problem_symbols.sort(key=lambda x: x.get("total_loss", 0), reverse=True)
        strong_symbols.sort(key=lambda x: x.get("total_profit", 0), reverse=True)

        return {
            "problem_symbols": problem_symbols[:5],  # Top 5 money losers
            "strong_symbols": strong_symbols[:5],    # Top 5 money makers
            "symbol_breakdown": {
                s: {
                    "win_rate": stats["win_rate"],
                    "trades": stats["trades"],
                    "total_pnl": round(stats["total_pnl"], 2),
                    "avg_pnl": stats["avg_pnl"]
                }
                for s, stats in symbol_stats.items()
                if stats["trades"] >= 3  # Only symbols with at least 3 trades
            }
        }

    def _normalize_symbol(self, symbol: str) -> str:
        """
        Normalize symbol to base instrument.
        NIFTY24FEB22000CE -> NIFTY
        BANKNIFTY24125 -> BANKNIFTY
        RELIANCE -> RELIANCE
        """
        # Common index names
        if symbol.startswith("NIFTY"):
            if "BANK" in symbol:
                return "BANKNIFTY"
            elif "FIN" in symbol:
                return "FINNIFTY"
            elif "MIDCAP" in symbol:
                return "MIDCPNIFTY"
            else:
                return "NIFTY"

        # For stocks, remove any expiry/option suffix
        # Most stock symbols are simple (RELIANCE, TCS, etc.)
        # F&O symbols have expiry dates
        import re
        # Remove digits and common option suffixes
        base = re.sub(r'\d+', '', symbol)
        base = re.sub(r'(CE|PE|FUT)$', '', base)
        return base.strip() if base else symbol

    async def _learn_intervention_timing(
        self,
        broker_account_id: UUID,
        db: AsyncSession,
        trades: List[Trade]
    ) -> Dict:
        """
        Learn the optimal cooldown duration for this trader.
        Analyze what happens after alerts - do shorter or longer cooldowns work better?
        """
        # Fetch past cooldowns
        result = await db.execute(
            select(Cooldown).where(
                Cooldown.broker_account_id == broker_account_id
            ).order_by(Cooldown.started_at.desc()).limit(50)
        )
        cooldowns = list(result.scalars().all())

        if len(cooldowns) < 5:
            return {
                "optimal_cooldown_minutes": 15,  # Default
                "confidence": "low",
                "reason": "Not enough cooldown history"
            }

        # Analyze cooldown outcomes
        skipped_outcomes = []
        completed_outcomes = []

        for cooldown in cooldowns:
            # Find trades in 2 hours after cooldown ended/was skipped
            end_time = cooldown.skipped_at if cooldown.skipped else cooldown.expires_at
            if not end_time:
                continue

            window_start = end_time
            window_end = end_time + timedelta(hours=2)

            post_cooldown_trades = [
                t for t in trades
                if t.order_timestamp and window_start <= t.order_timestamp <= window_end
            ]

            if not post_cooldown_trades:
                continue

            # Calculate P&L in window
            window_pnl = sum(float(t.pnl or 0) for t in post_cooldown_trades)

            if cooldown.skipped:
                skipped_outcomes.append({
                    "duration": cooldown.duration_minutes,
                    "pnl_after": window_pnl,
                    "trades_after": len(post_cooldown_trades)
                })
            else:
                completed_outcomes.append({
                    "duration": cooldown.duration_minutes,
                    "pnl_after": window_pnl,
                    "trades_after": len(post_cooldown_trades)
                })

        # Analyze results
        skipped_avg_pnl = statistics.mean([o["pnl_after"] for o in skipped_outcomes]) if skipped_outcomes else 0
        completed_avg_pnl = statistics.mean([o["pnl_after"] for o in completed_outcomes]) if completed_outcomes else 0

        # Determine optimal duration
        optimal_duration = 15  # Default

        if completed_outcomes:
            # Group by duration and find best performing
            duration_pnl = {}
            for outcome in completed_outcomes:
                d = outcome["duration"]
                if d not in duration_pnl:
                    duration_pnl[d] = []
                duration_pnl[d].append(outcome["pnl_after"])

            # Find duration with best average outcome
            best_duration = max(
                duration_pnl.keys(),
                key=lambda d: statistics.mean(duration_pnl[d])
            )
            optimal_duration = best_duration

        # Calculate YOUR revenge window (time between loss and revenge trade)
        revenge_windows = []
        sorted_trades = sorted(trades, key=lambda t: t.order_timestamp)
        for i in range(1, len(sorted_trades)):
            prev = sorted_trades[i - 1]
            curr = sorted_trades[i]

            if float(prev.pnl or 0) < 0 and float(curr.pnl or 0) < 0:
                gap = (curr.order_timestamp - prev.order_timestamp).total_seconds() / 60
                if gap < 30:  # Only count if within 30 min
                    revenge_windows.append(gap)

        personal_revenge_window = round(statistics.median(revenge_windows), 1) if revenge_windows else 12

        return {
            "optimal_cooldown_minutes": optimal_duration,
            "personal_revenge_window_minutes": personal_revenge_window,
            "skip_vs_complete": {
                "skipped_avg_pnl": round(skipped_avg_pnl, 2),
                "completed_avg_pnl": round(completed_avg_pnl, 2),
                "recommendation": "complete" if completed_avg_pnl > skipped_avg_pnl else "skip_cautiously"
            },
            "confidence": "high" if len(cooldowns) >= 10 else "medium",
            "data_points": len(cooldowns)
        }

    def _calculate_predictive_windows(
        self,
        time_patterns: Dict,
        symbol_patterns: Dict
    ) -> Dict:
        """
        Calculate when to send predictive alerts.
        Alert BEFORE the trader's typical danger windows.
        """
        predictive_alerts = []

        # Time-based predictions
        for danger_hour in time_patterns.get("danger_hours", []):
            hour = danger_hour["hour"]
            predictive_alerts.append({
                "type": "time_warning",
                "trigger_time": f"{(hour - 1) % 24}:45",  # 15 min before danger hour
                "message": f"Heads up: {hour}:00-{hour+1}:00 is historically your weakest hour ({danger_hour['win_rate']}% win rate)",
                "severity": "caution" if danger_hour["win_rate"] > 25 else "danger"
            })

        for danger_day in time_patterns.get("danger_days", []):
            predictive_alerts.append({
                "type": "day_warning",
                "trigger_time": "09:10",  # Just before market open
                "trigger_day": danger_day["day"],
                "message": f"{danger_day['day']} is historically your worst trading day ({danger_day['win_rate']}% win rate). Consider trading smaller.",
                "severity": "caution"
            })

        # Symbol-based predictions
        for problem in symbol_patterns.get("problem_symbols", []):
            predictive_alerts.append({
                "type": "symbol_warning",
                "trigger_symbol": problem["symbol"],
                "message": f"Warning: Your win rate on {problem['symbol']} is only {problem['win_rate']}%. Consider avoiding or reducing size.",
                "severity": "caution" if problem["win_rate"] > 25 else "danger"
            })

        return {
            "alerts": predictive_alerts,
            "total_warnings": len(predictive_alerts)
        }

    async def _store_learned_patterns(
        self,
        broker_account_id: UUID,
        db: AsyncSession,
        patterns: Dict
    ) -> None:
        """Store learned patterns in user profile."""
        result = await db.execute(
            select(UserProfile).where(UserProfile.broker_account_id == broker_account_id)
        )
        profile = result.scalar_one_or_none()

        if profile:
            profile.detected_patterns = patterns
            await db.commit()

    async def get_predictive_alert(
        self,
        broker_account_id: UUID,
        db: AsyncSession,
        context: Dict = None
    ) -> Optional[Dict]:
        """
        Check if a predictive alert should be shown right now.

        Context can include:
        - current_time: datetime
        - proposed_symbol: str (if about to trade)
        """
        # Get stored patterns
        result = await db.execute(
            select(UserProfile).where(UserProfile.broker_account_id == broker_account_id)
        )
        profile = result.scalar_one_or_none()

        if not profile or not profile.detected_patterns:
            return None

        patterns = profile.detected_patterns
        if patterns.get("insufficient_data"):
            return None

        now = context.get("current_time", datetime.now(timezone.utc)) if context else datetime.now(timezone.utc)
        current_hour = now.hour
        current_day = now.strftime("%A")
        proposed_symbol = context.get("proposed_symbol") if context else None

        alerts = []

        # Check time-based warnings
        time_patterns = patterns.get("time_patterns", {})
        for danger in time_patterns.get("danger_hours", []):
            if danger["hour"] == current_hour or danger["hour"] == current_hour + 1:
                alerts.append({
                    "type": "time_warning",
                    "message": f"⚠️ {danger['hour']}:00 is YOUR danger hour ({danger['win_rate']}% win rate). Trade carefully!",
                    "severity": "caution",
                    "data": danger
                })

        for danger in time_patterns.get("danger_days", []):
            if danger["day"] == current_day:
                alerts.append({
                    "type": "day_warning",
                    "message": f"⚠️ {current_day} is YOUR worst day ({danger['win_rate']}% win rate). Consider smaller positions.",
                    "severity": "caution",
                    "data": danger
                })

        # Check symbol-based warnings
        if proposed_symbol:
            base_symbol = self._normalize_symbol(proposed_symbol)
            symbol_patterns = patterns.get("symbol_patterns", {})

            for problem in symbol_patterns.get("problem_symbols", []):
                if problem["symbol"] == base_symbol:
                    alerts.append({
                        "type": "symbol_warning",
                        "message": f"⚠️ Your win rate on {base_symbol} is only {problem['win_rate']}%. Consider avoiding.",
                        "severity": "danger" if problem["win_rate"] < 25 else "caution",
                        "data": problem
                    })

        return alerts[0] if alerts else None

    async def get_personalized_insights(
        self,
        broker_account_id: UUID,
        db: AsyncSession
    ) -> Dict:
        """
        Get a summary of personalized insights for dashboard display.
        """
        result = await db.execute(
            select(UserProfile).where(UserProfile.broker_account_id == broker_account_id)
        )
        profile = result.scalar_one_or_none()

        if not profile or not profile.detected_patterns:
            return {
                "has_data": False,
                "message": "We need more trading data to learn your patterns. Keep trading!"
            }

        patterns = profile.detected_patterns
        if patterns.get("insufficient_data"):
            return {
                "has_data": False,
                "trades_analyzed": patterns.get("trades_analyzed", 0),
                "message": f"Analyzed {patterns.get('trades_analyzed', 0)} trades. Need at least 20 for pattern detection."
            }

        # Build insights
        insights = []

        # Time insights
        time_patterns = patterns.get("time_patterns", {})
        if time_patterns.get("danger_hours"):
            worst = time_patterns["danger_hours"][0]
            insights.append({
                "type": "danger_time",
                "icon": "⏰",
                "title": "Your Danger Hour",
                "value": f"{worst['hour']}:00",
                "detail": f"{worst['win_rate']}% win rate",
                "recommendation": f"Avoid trading at {worst['hour']}:00"
            })

        if time_patterns.get("best_hours"):
            best = time_patterns["best_hours"][0]
            insights.append({
                "type": "best_time",
                "icon": "✨",
                "title": "Your Best Hour",
                "value": f"{best['hour']}:00",
                "detail": f"{best['win_rate']}% win rate",
                "recommendation": f"Focus your trading around {best['hour']}:00"
            })

        # Symbol insights
        symbol_patterns = patterns.get("symbol_patterns", {})
        if symbol_patterns.get("problem_symbols"):
            worst = symbol_patterns["problem_symbols"][0]
            insights.append({
                "type": "problem_symbol",
                "icon": "🚫",
                "title": "Avoid This",
                "value": worst["symbol"],
                "detail": f"{worst['win_rate']}% win rate",
                "recommendation": f"Consider removing {worst['symbol']} from your watchlist"
            })

        if symbol_patterns.get("strong_symbols"):
            best = symbol_patterns["strong_symbols"][0]
            insights.append({
                "type": "strong_symbol",
                "icon": "💪",
                "title": "Your Edge",
                "value": best["symbol"],
                "detail": f"{best['win_rate']}% win rate",
                "recommendation": f"Focus more on {best['symbol']}"
            })

        # Intervention timing
        intervention = patterns.get("intervention_timing", {})
        if intervention.get("personal_revenge_window_minutes"):
            insights.append({
                "type": "revenge_window",
                "icon": "⏱️",
                "title": "Your Revenge Window",
                "value": f"{intervention['personal_revenge_window_minutes']} min",
                "detail": "Time you typically wait before revenge trading",
                "recommendation": f"Set cooldown to at least {int(intervention['personal_revenge_window_minutes'] * 1.5)} minutes"
            })

        return {
            "has_data": True,
            "last_updated": patterns.get("last_updated"),
            "trades_analyzed": patterns.get("trades_analyzed", 0),
            "insights": insights,
            "predictive_alerts": patterns.get("predictive_windows", {}).get("alerts", [])
        }


# Singleton instance
ai_personalization_service = AIPersonalizationService()
