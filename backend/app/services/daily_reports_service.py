"""
Daily Reports Service

Generates automated reports for traders:
1. Post-Market Report (4:00 PM IST) - Day summary, patterns, lessons
2. Morning Readiness Briefing (8:30 AM IST) - Warnings, intentions, focus

Key fixes:
- Uses CLOSED POSITIONS (not individual orders) for trade count
- Converts UTC timestamps to IST before hour analysis
- Reports cover only TODAY's data (daily scope)
- Improved report quality with actionable insights
"""

from datetime import datetime, timedelta, date, timezone
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from uuid import UUID
import statistics
import logging

from app.models.position import Position
from app.models.risk_alert import RiskAlert
from app.models.user_profile import UserProfile
from app.models.cooldown import Cooldown

logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")


def _utc_to_ist(dt: Optional[datetime]) -> Optional[datetime]:
    """Convert a UTC datetime to IST. Handles naive and aware datetimes."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(IST)


def _ist_hour_label(dt: Optional[datetime]) -> Optional[str]:
    """Return HH:MM string in IST from a datetime (UTC or IST)."""
    ist_dt = _utc_to_ist(dt)
    if ist_dt is None:
        return None
    return ist_dt.strftime("%H:%M")


def _ist_hour(dt: Optional[datetime]) -> Optional[int]:
    """Return the hour (0-23) in IST from a UTC datetime."""
    ist_dt = _utc_to_ist(dt)
    return ist_dt.hour if ist_dt else None


class DailyReportsService:
    """Generates automated daily reports for traders."""

    # =========================================================================
    # POST-MARKET REPORT
    # =========================================================================

    async def generate_post_market_report(
        self,
        broker_account_id: UUID,
        db: AsyncSession,
        report_date: Optional[date] = None
    ) -> Dict:
        """
        Generate comprehensive post-market report for TODAY only.

        Uses CLOSED POSITIONS (not individual orders) so trade count
        matches what the user actually sees as completed round-trips.
        """
        # Use IST date for the report
        now_ist = datetime.now(IST)
        if report_date is None:
            report_date = now_ist.date()

        # Define IST day boundaries and convert to UTC for DB queries
        day_start_ist = datetime(report_date.year, report_date.month, report_date.day, 0, 0, 0, tzinfo=IST)
        day_end_ist = datetime(report_date.year, report_date.month, report_date.day, 23, 59, 59, tzinfo=IST)
        day_start_utc = day_start_ist.astimezone(timezone.utc)
        day_end_utc = day_end_ist.astimezone(timezone.utc)

        # Fetch TODAY's CLOSED positions (each = one completed trade round-trip)
        positions_result = await db.execute(
            select(Position).where(
                and_(
                    Position.broker_account_id == broker_account_id,
                    Position.status == "closed",
                    Position.last_exit_time >= day_start_utc,
                    Position.last_exit_time <= day_end_utc
                )
            ).order_by(Position.first_entry_time)
        )
        positions = list(positions_result.scalars().all())

        # Also fetch today's OPEN positions (for context)
        open_result = await db.execute(
            select(Position).where(
                and_(
                    Position.broker_account_id == broker_account_id,
                    Position.status == "open",
                    Position.first_entry_time >= day_start_utc,
                )
            )
        )
        open_positions = list(open_result.scalars().all())

        # Fetch today's alerts
        alerts_result = await db.execute(
            select(RiskAlert).where(
                and_(
                    RiskAlert.broker_account_id == broker_account_id,
                    RiskAlert.detected_at >= day_start_utc,
                    RiskAlert.detected_at <= day_end_utc
                )
            ).order_by(RiskAlert.detected_at)
        )
        alerts = list(alerts_result.scalars().all())

        # Fetch user profile for personalization
        profile_result = await db.execute(
            select(UserProfile).where(UserProfile.broker_account_id == broker_account_id)
        )
        profile = profile_result.scalar_one_or_none()

        # Generate report sections
        trade_summary = self._generate_trade_summary(positions, open_positions)
        patterns_detected = self._extract_patterns_from_alerts(alerts)
        emotional_journey = self._generate_emotional_journey(positions)
        key_lessons = self._generate_key_lessons(positions, alerts, profile)
        tomorrow_focus = self._generate_tomorrow_focus(positions, alerts, profile)
        time_analysis = self._generate_time_analysis(positions)

        return {
            "report_type": "post_market",
            "report_date": report_date.isoformat(),
            "generated_at": datetime.now(timezone.utc).isoformat(),

            "summary": trade_summary,
            "patterns_detected": patterns_detected,
            "emotional_journey": emotional_journey,
            "key_lessons": key_lessons,
            "tomorrow_focus": tomorrow_focus,
            "time_analysis": time_analysis,
            "open_positions": len(open_positions),

            "has_trades": len(positions) > 0,
            "trade_count": len(positions)
        }

    def _generate_trade_summary(self, positions: List[Position], open_positions: List[Position]) -> Dict:
        """Generate trade statistics from closed positions."""
        if not positions:
            return {
                "total_trades": 0,
                "open_trades": len(open_positions),
                "winners": 0,
                "losers": 0,
                "breakeven": 0,
                "win_rate": 0,
                "total_pnl": 0,
                "gross_profit": 0,
                "gross_loss": 0,
                "largest_win": 0,
                "largest_loss": 0,
                "avg_win": 0,
                "avg_loss": 0,
                "profit_factor": 0
            }

        pnls = [float(p.realized_pnl or p.pnl or 0) for p in positions]
        winners = [p for p in pnls if p > 0]
        losers = [p for p in pnls if p < 0]
        breakeven = [p for p in pnls if p == 0]

        gross_profit = sum(winners) if winners else 0
        gross_loss = abs(sum(losers)) if losers else 0
        profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else 0

        return {
            "total_trades": len(positions),
            "open_trades": len(open_positions),
            "winners": len(winners),
            "losers": len(losers),
            "breakeven": len(breakeven),
            "win_rate": round((len(winners) / len(positions)) * 100, 1) if positions else 0,
            "total_pnl": round(sum(pnls), 2),
            "gross_profit": round(gross_profit, 2),
            "gross_loss": round(-abs(sum(losers)), 2) if losers else 0,
            "largest_win": round(max(winners), 2) if winners else 0,
            "largest_loss": round(min(losers), 2) if losers else 0,
            "avg_win": round(statistics.mean(winners), 2) if winners else 0,
            "avg_loss": round(statistics.mean(losers), 2) if losers else 0,
            "profit_factor": profit_factor
        }

    def _generate_time_analysis(self, positions: List[Position]) -> Dict:
        """Analyse performance by hour in IST. Returns best/worst hours."""
        if len(positions) < 2:
            return {}

        pnl_by_hour: Dict[int, List[float]] = {}
        count_by_hour: Dict[int, int] = {}

        for pos in positions:
            hour = _ist_hour(pos.first_entry_time)
            if hour is None:
                continue
            pnl = float(pos.realized_pnl or pos.pnl or 0)
            pnl_by_hour.setdefault(hour, []).append(pnl)
            count_by_hour[hour] = count_by_hour.get(hour, 0) + 1

        if not pnl_by_hour:
            return {}

        hour_stats = {
            h: {
                "hour": h,
                "label": f"{h:02d}:00",
                "total_pnl": round(sum(pnls), 2),
                "trade_count": len(pnls),
                "win_rate": round(sum(1 for p in pnls if p > 0) / len(pnls) * 100, 0)
            }
            for h, pnls in pnl_by_hour.items()
        }

        sorted_by_pnl = sorted(hour_stats.values(), key=lambda x: x["total_pnl"])

        # Only flag worst hour if it's actually a loss
        worst = sorted_by_pnl[0] if sorted_by_pnl[0]["total_pnl"] < -100 else None
        best = sorted_by_pnl[-1] if sorted_by_pnl[-1]["total_pnl"] > 100 else None

        return {
            "hours": list(hour_stats.values()),
            "worst_hour": worst,
            "best_hour": best
        }

    def _extract_patterns_from_alerts(self, alerts: List[RiskAlert]) -> List[Dict]:
        """Extract pattern information from alerts."""
        patterns = []
        for alert in alerts:
            patterns.append({
                "pattern": alert.pattern_type,
                "severity": alert.severity,
                "time": _ist_hour_label(alert.detected_at),
                "message": alert.message,
                "acknowledged": alert.acknowledged_at is not None
            })
        return patterns

    def _generate_emotional_journey(self, positions: List[Position]) -> Dict:
        """Generate emotional journey timeline based on P&L progression (IST times)."""
        if not positions:
            return {"timeline": [], "overall_mood": "neutral"}

        timeline = []
        cumulative_pnl = 0
        prev_cumulative = 0

        for pos in positions:
            pnl = float(pos.realized_pnl or pos.pnl or 0)
            cumulative_pnl += pnl

            # Mood thresholds
            if pnl > 1000:
                mood, emoji = "euphoric", "🎉"
            elif pnl > 300:
                mood, emoji = "confident", "😊"
            elif pnl < -1000:
                mood, emoji = "stressed", "😰"
            elif pnl < -300:
                mood, emoji = "frustrated", "😤"
            elif cumulative_pnl < -2000:
                mood, emoji = "distressed", "🆘"
            else:
                mood, emoji = "neutral", "😐"

            timeline.append({
                "time": _ist_hour_label(pos.first_entry_time),
                "exit_time": _ist_hour_label(pos.last_exit_time),
                "pnl": round(pnl, 2),
                "cumulative_pnl": round(cumulative_pnl, 2),
                "mood": mood,
                "emoji": emoji,
                "symbol": pos.tradingsymbol,
                "duration_min": pos.holding_duration_minutes
            })
            prev_cumulative = cumulative_pnl

        # Overall mood
        if cumulative_pnl > 2000:
            overall = "very_positive"
        elif cumulative_pnl > 500:
            overall = "positive"
        elif cumulative_pnl < -2000:
            overall = "very_negative"
        elif cumulative_pnl < -500:
            overall = "negative"
        else:
            overall = "neutral"

        return {
            "timeline": timeline,
            "overall_mood": overall,
            "final_pnl": round(cumulative_pnl, 2),
            "peak_pnl": round(max((e["cumulative_pnl"] for e in timeline), default=0), 2),
            "trough_pnl": round(min((e["cumulative_pnl"] for e in timeline), default=0), 2)
        }

    def _generate_key_lessons(
        self,
        positions: List[Position],
        alerts: List[RiskAlert],
        profile: Optional[UserProfile]
    ) -> List[Dict]:
        """Generate data-driven lessons from today's closed positions."""
        lessons = []

        if not positions:
            return [{"lesson": "Rest day. No closed trades today. Down days force resets.", "type": "neutral"}]

        danger_alerts = [a for a in alerts if a.severity == "danger"]
        pnls = [float(p.realized_pnl or p.pnl or 0) for p in positions]
        total_pnl = sum(pnls)
        winners = [p for p in pnls if p > 0]
        losers = [p for p in pnls if p < 0]

        # --- Lesson 1: Pattern-based (personalized) ---
        if danger_alerts:
            pattern_types = list(dict.fromkeys(a.pattern_type for a in danger_alerts))  # preserve order, dedupe
            pattern_messages = {
                "revenge_trading": "Revenge trade detected. After a loss, your brain desperately wants to \"get back\" the money — but this emotional impulse almost always makes it worse. The market doesn't owe you a recovery.",
                "overtrading": "Overtrading pattern. More trades = more commissions + more emotional exposure. Ask yourself: would you have taken that last trade in paper trading?",
                "tilt_loss_spiral": "Loss spiral triggered. When losses compound, your judgment clouds. The correct response to 3 straight losses is NOT a 4th trade — it's a walk.",
                "consecutive_loss": "Consecutive losses today. This is the hardest moment to stay rational. Each loss slightly increases the impulsive urge to trade. Awareness is your only protection.",
                "fomo": "FOMO entry detected. Every missed move that you chase turns into a bad entry. The set-up you miss today will look exactly like the set-ups you'll see tomorrow.",
                "martingale": "You're doubling down after losses — martingale sizing. This works until one large loss wipes out all prior recovery gains.",
                "overconfidence": "Overconfidence bias detected. When you're up big, risk discipline tends to slip. The market doesn't care about your streak."
            }
            for pattern in pattern_types[:2]:
                msg = pattern_messages.get(pattern, f"{pattern.replace('_', ' ').title()} pattern detected. Review the trade sequence.")
                lessons.append({"lesson": msg, "type": "warning", "pattern": pattern})

        # --- Lesson 2: Best and worst trade analysis ---
        if len(positions) >= 2:
            max_win = max(pnls)
            max_loss = min(pnls)
            if max_win > 0 and abs(max_loss) > 0:
                rr = round(max_win / abs(max_loss), 2)
                if rr >= 2:
                    lessons.append({
                        "lesson": f"Your best trade was ₹{max_win:,.0f} vs your worst ₹{max_loss:,.0f}. Reward:Risk = {rr}x. This is the ratio you want to aim for consistently.",
                        "type": "positive",
                        "data": {"rr": rr}
                    })
                elif max_loss < -500 and max_win < abs(max_loss):
                    lessons.append({
                        "lesson": f"Your losses (₹{max_loss:,.0f}) outweigh your wins (₹{max_win:,.0f}). Tighter stop-losses or letting winners run longer would improve this ratio.",
                        "type": "warning"
                    })

        # --- Lesson 3: Worst IST hour (only if genuinely bad) ---
        time_data = self._generate_time_analysis(positions)
        if time_data.get("worst_hour"):
            wh = time_data["worst_hour"]
            if wh["total_pnl"] < -300:
                lessons.append({
                    "lesson": f"Your worst hour today was {wh['label']} IST (₹{wh['total_pnl']:,.0f} across {wh['trade_count']} trade(s)). This time slot may be worth avoiding or trading smaller.",
                    "type": "insight",
                    "data": wh
                })

        # --- Lesson 4: Cooldown compliance ---
        sorted_positions = sorted(positions, key=lambda p: p.first_entry_time or datetime.min)
        no_cooldown_count = 0
        for i in range(1, len(sorted_positions)):
            prev = sorted_positions[i - 1]
            curr = sorted_positions[i]
            prev_pnl = float(prev.realized_pnl or prev.pnl or 0)
            if prev_pnl < 0 and prev.last_exit_time and curr.first_entry_time:
                gap_minutes = (curr.first_entry_time - prev.last_exit_time).total_seconds() / 60
                if gap_minutes < 5:
                    no_cooldown_count += 1

        if no_cooldown_count > 0:
            potential_save = no_cooldown_count * 800
            lessons.append({
                "lesson": f"You re-entered {no_cooldown_count} time(s) within 5 minutes of a losing exit. Emotion, not analysis, drives these instant re-entries. A mandatory 15-min cooldown could save ~₹{potential_save:,} over time.",
                "type": "actionable",
                "data": {"quick_reentries": no_cooldown_count}
            })

        # --- Lesson 5: Positive reinforcement ---
        if not danger_alerts and len(positions) <= 5 and (not losers or max(winners, default=0) > abs(min(losers, default=0))):
            lessons.append({
                "lesson": f"Clean trading day. {len(winners)} winner(s), {len(losers)} loser(s), net ₹{total_pnl:+,.0f}. Discipline + process over outcome.",
                "type": "positive"
            })

        return lessons if lessons else [{"lesson": "Keep logging trades. More data → sharper insights.", "type": "neutral"}]

    def _generate_tomorrow_focus(
        self,
        positions: List[Position],
        alerts: List[RiskAlert],
        profile: Optional[UserProfile]
    ) -> Dict:
        """Generate specific, actionable focus area for tomorrow."""
        pnls = [float(p.realized_pnl or p.pnl or 0) for p in positions]

        focus = {
            "primary": "Trade your plan, not your emotions",
            "rule": "Before every trade: Am I entering for a reason, or a feeling?",
            "max_trades": profile.daily_trade_limit if profile and profile.daily_trade_limit else 5,
            "avoid_times": [],
            "avoid_symbols": [],
            "affirmation": "Consistency beats big wins."
        }

        danger_alerts = [a for a in alerts if a.severity == "danger"]
        alert_types = {a.pattern_type for a in danger_alerts}

        if "revenge_trading" in alert_types:
            focus["primary"] = "Zero revenge trades tomorrow"
            focus["rule"] = "After any loss: stand up, walk away for 15 minutes. Timer starts at exit."
            focus["affirmation"] = "The best trade after a loss is often no trade."
        elif "overtrading" in alert_types:
            focus["primary"] = "Quality > Quantity — max 4 trades"
            focus["rule"] = "Trade 4 only. Close app after 4th regardless of outcome."
            focus["max_trades"] = 4
            focus["affirmation"] = "Fewer, better trades. Not more lousy ones."
        elif "tilt_loss_spiral" in alert_types or "consecutive_loss" in alert_types:
            focus["primary"] = "Capital protection above all"
            focus["rule"] = "Two consecutive losses = stop for the day. No exceptions."
            focus["max_trades"] = 3
            focus["affirmation"] = "Surviving bad days is what separates pros from amateurs."
        elif "fomo" in alert_types:
            focus["primary"] = "Only pre-planned set-ups"
            focus["rule"] = "If it's not in your watchlist before open, you don't trade it."
            focus["affirmation"] = "Every missed opportunity is a lesson in patience."
        elif sum(pnls) > 3000:
            focus["primary"] = "Protect today's gains tomorrow"
            focus["rule"] = "Take fewer trades. Don't give back your green day."
            focus["affirmation"] = "Big win days are often followed by revenge if you try to repeat."

        # Time-based avoidance from detected patterns
        if profile and profile.detected_patterns:
            danger_hours = profile.detected_patterns.get("time_patterns", {}).get("danger_hours", [])
            focus["avoid_times"] = [f"{h['hour']:02d}:00 IST" for h in danger_hours[:2]]

            problem_symbols = profile.detected_patterns.get("symbol_patterns", {}).get("problem_symbols", [])
            focus["avoid_symbols"] = [s["symbol"] for s in problem_symbols[:2]]

        return focus

    # =========================================================================
    # MORNING READINESS BRIEFING
    # =========================================================================

    async def generate_morning_briefing(
        self,
        broker_account_id: UUID,
        db: AsyncSession
    ) -> Dict:
        """
        Generate morning readiness briefing based on YESTERDAY's data only.
        Uses actual closed positions, not raw orders.
        """
        now_ist = datetime.now(IST)
        today = now_ist.date()
        day_name = now_ist.strftime("%A")

        # Fetch user profile with learned patterns
        profile_result = await db.execute(
            select(UserProfile).where(UserProfile.broker_account_id == broker_account_id)
        )
        profile = profile_result.scalar_one_or_none()

        # Fetch YESTERDAY'S closed positions (daily scope, not 7-day)
        yesterday = today - timedelta(days=1)
        yesterday_start_ist = datetime(yesterday.year, yesterday.month, yesterday.day, 0, 0, 0, tzinfo=IST)
        yesterday_end_ist = datetime(yesterday.year, yesterday.month, yesterday.day, 23, 59, 59, tzinfo=IST)
        yesterday_start_utc = yesterday_start_ist.astimezone(timezone.utc)
        yesterday_end_utc = yesterday_end_ist.astimezone(timezone.utc)

        positions_result = await db.execute(
            select(Position).where(
                and_(
                    Position.broker_account_id == broker_account_id,
                    Position.status == "closed",
                    Position.last_exit_time >= yesterday_start_utc,
                    Position.last_exit_time <= yesterday_end_utc
                )
            ).order_by(Position.first_entry_time)
        )
        yesterday_positions = list(positions_result.scalars().all())

        # Fetch yesterday's alerts
        alerts_result = await db.execute(
            select(RiskAlert).where(
                and_(
                    RiskAlert.broker_account_id == broker_account_id,
                    RiskAlert.detected_at >= yesterday_start_utc,
                    RiskAlert.detected_at <= yesterday_end_utc
                )
            )
        )
        yesterday_alerts = list(alerts_result.scalars().all())

        # Fetch last 5 closed positions across last 3 days for streak detection
        three_days_ago_utc = (now_ist - timedelta(days=3)).astimezone(timezone.utc)
        recent_result = await db.execute(
            select(Position).where(
                and_(
                    Position.broker_account_id == broker_account_id,
                    Position.status == "closed",
                    Position.last_exit_time >= three_days_ago_utc
                )
            ).order_by(Position.last_exit_time.desc()).limit(10)
        )
        recent_positions = list(recent_result.scalars().all())

        # Generate briefing sections
        day_warning = self._generate_day_warning(day_name, profile)
        recent_summary = self._generate_recent_summary(yesterday_positions, yesterday_alerts)
        watch_outs = self._generate_watch_outs(profile, recent_positions, day_name, yesterday_alerts)
        readiness_checklist = self._generate_readiness_checklist(profile, yesterday_positions, yesterday_alerts)
        readiness_score = self._calculate_readiness_score(profile, recent_positions, day_name)

        return {
            "report_type": "morning_briefing",
            "report_date": today.isoformat(),
            "day_name": day_name,
            "generated_at": datetime.now(timezone.utc).isoformat(),

            "readiness_score": readiness_score,
            "day_warning": day_warning,
            "recent_summary": recent_summary,
            "watch_outs": watch_outs,
            "checklist": readiness_checklist,

            "commitment_prompt": "What is your ONE rule for today?",
            "suggested_commitments": self._get_suggested_commitments(watch_outs, yesterday_alerts)
        }

    def _generate_day_warning(self, day_name: str, profile: Optional[UserProfile]) -> Optional[Dict]:
        """Generate warning if today is historically a bad day."""
        if not profile or not profile.detected_patterns:
            return None

        time_patterns = profile.detected_patterns.get("time_patterns", {})

        for danger in time_patterns.get("danger_days", []):
            if danger["day"] == day_name:
                return {
                    "is_danger_day": True,
                    "day": day_name,
                    "win_rate": danger["win_rate"],
                    "message": f"{day_name} is historically your WORST trading day ({danger['win_rate']}% win rate). Consider smaller size or sitting out.",
                    "recommendation": "reduce_size"
                }

        for best in time_patterns.get("best_days", []):
            if best["day"] == day_name:
                return {
                    "is_danger_day": False,
                    "day": day_name,
                    "win_rate": best["win_rate"],
                    "message": f"{day_name} is historically your BEST day ({best['win_rate']}% win rate). Stay disciplined and don't over-trade it!",
                    "recommendation": "stay_disciplined"
                }

        return None

    def _generate_recent_summary(
        self,
        yesterday_positions: List[Position],
        yesterday_alerts: List[RiskAlert]
    ) -> Dict:
        """Summarise YESTERDAY's closed positions only."""
        if not yesterday_positions:
            return {
                "has_recent_trades": False,
                "message": "No closed trades yesterday. Fresh start!"
            }

        pnls = [float(p.realized_pnl or p.pnl or 0) for p in yesterday_positions]
        yesterday_pnl = sum(pnls)
        winners = [p for p in pnls if p > 0]
        losers = [p for p in pnls if p < 0]
        win_rate = round(len(winners) / len(pnls) * 100) if pnls else 0
        danger_count = len([a for a in yesterday_alerts if a.severity == "danger"])

        # Streak across yesterday's positions (last few trades)
        sorted_pos = sorted(yesterday_positions, key=lambda p: p.last_exit_time or datetime.min, reverse=True)
        streak_type = None
        streak_count = 0
        for pos in sorted_pos[:6]:
            pnl = float(pos.realized_pnl or pos.pnl or 0)
            if streak_type is None:
                streak_type = "win" if pnl > 0 else "loss"
                streak_count = 1
            elif (pnl > 0 and streak_type == "win") or (pnl < 0 and streak_type == "loss"):
                streak_count += 1
            else:
                break

        return {
            "has_recent_trades": True,
            "yesterday_trades": len(yesterday_positions),
            "yesterday_pnl": round(yesterday_pnl, 2),
            "yesterday_win_rate": win_rate,
            "yesterday_danger_alerts": danger_count,
            "current_streak": {"type": streak_type, "count": streak_count},
            "message": self._format_recent_message(yesterday_pnl, yesterday_positions, streak_type, streak_count, danger_count)
        }

    def _format_recent_message(
        self,
        pnl: float,
        positions: List[Position],
        streak_type: Optional[str],
        streak_count: int,
        danger_count: int
    ) -> str:
        parts = []

        trade_word = "trade" if len(positions) == 1 else "trades"
        if pnl > 500:
            parts.append(f"Yesterday: {len(positions)} {trade_word}, green (+₹{pnl:,.0f}) 🟢")
        elif pnl < -500:
            parts.append(f"Yesterday: {len(positions)} {trade_word}, red (₹{pnl:,.0f}) 🔴")
        else:
            parts.append(f"Yesterday: {len(positions)} {trade_word}, roughly flat (₹{pnl:+,.0f})")

        if streak_type == "loss" and streak_count >= 2:
            parts.append(f"⚠️ Ended on a {streak_count}-loss streak — today starts fresh, not a continuation")
        elif streak_type == "win" and streak_count >= 3:
            parts.append(f"🔥 On a {streak_count}-win streak — stay grounded, don't over-size")

        if danger_count > 0:
            parts.append(f"⚠️ {danger_count} danger alert(s) yesterday — review before trading")

        return ". ".join(parts)

    def _generate_watch_outs(
        self,
        profile: Optional[UserProfile],
        recent_positions: List[Position],
        day_name: str,
        yesterday_alerts: List[RiskAlert]
    ) -> List[Dict]:
        """Generate personalised watch-outs for today."""
        watch_outs = []

        # 1. Time-based watch-outs from detected patterns (IST hours)
        if profile and profile.detected_patterns:
            time_patterns = profile.detected_patterns.get("time_patterns", {})
            for danger in time_patterns.get("danger_hours", [])[:2]:
                h = danger["hour"]
                watch_outs.append({
                    "type": "time",
                    "icon": "⏰",
                    "message": f"Avoid {h:02d}:00–{h:02d}:59 IST — your win rate drops to {danger['win_rate']}% in this window",
                    "severity": "high" if danger["win_rate"] < 30 else "medium"
                })

            symbol_patterns = profile.detected_patterns.get("symbol_patterns", {})
            for problem in symbol_patterns.get("problem_symbols", [])[:2]:
                watch_outs.append({
                    "type": "symbol",
                    "icon": "🚫",
                    "message": f"Caution on {problem['symbol']} — {problem['win_rate']}% win rate historically for you",
                    "severity": "high" if problem["win_rate"] < 30 else "medium"
                })

        # 2. Yesterday's danger alerts → carry-over risk
        danger_alerts = [a for a in yesterday_alerts if a.severity == "danger"]
        if danger_alerts:
            pattern_names = {
                "revenge_trading": "Revenge trading",
                "overtrading": "Overtrading",
                "tilt_loss_spiral": "Tilt / loss spiral",
                "consecutive_loss": "Consecutive losses",
                "fomo": "FOMO entry",
                "martingale": "Martingale sizing"
            }
            patterns = list(dict.fromkeys(a.pattern_type for a in danger_alerts))
            names = [pattern_names.get(p, p.replace("_", " ").title()) for p in patterns[:2]]
            watch_outs.append({
                "type": "carry_over",
                "icon": "⚠️",
                "message": f"Yesterday triggered: {', '.join(names)}. These patterns tend to carry into the next session.",
                "severity": "high"
            })

        # 3. Recent losing streak
        if recent_positions:
            sorted_pos = sorted(recent_positions, key=lambda p: p.last_exit_time or datetime.min, reverse=True)
            recent_losses = sum(1 for p in sorted_pos[:5] if float(p.realized_pnl or p.pnl or 0) < 0)
            if recent_losses >= 3:
                watch_outs.append({
                    "type": "pattern",
                    "icon": "📉",
                    "message": f"{recent_losses} of your last 5 trades are losses. Revenge risk today is ELEVATED — start slow.",
                    "severity": "high"
                })

        # 4. Day-specific market watch-outs
        if day_name == "Thursday":
            watch_outs.append({
                "type": "market",
                "icon": "📅",
                "message": "Weekly F&O expiry — premium decay accelerates, implied moves can be violent. Avoid late-day hold.",
                "severity": "medium"
            })
        elif day_name == "Friday":
            watch_outs.append({
                "type": "market",
                "icon": "📅",
                "message": "End-of-week — FIIs/DIIs book profits. Don't hold overnight positions through the weekend.",
                "severity": "low"
            })
        elif day_name == "Monday":
            watch_outs.append({
                "type": "market",
                "icon": "📅",
                "message": "Monday gaps happen. Wait for the gap to fill (or confirm direction) before entering.",
                "severity": "low"
            })

        # 5. Universal opening volatility alert
        watch_outs.append({
            "type": "general",
            "icon": "🎯",
            "message": "9:15–9:30 AM IST: Highest volatility window of the day. Observe first, trade second.",
            "severity": "medium"
        })

        return watch_outs

    def _generate_readiness_checklist(
        self,
        profile: Optional[UserProfile],
        yesterday_positions: List[Position],
        yesterday_alerts: List[RiskAlert]
    ) -> List[Dict]:
        """Generate personalised morning readiness checklist."""
        checklist = [
            {"item": "I know my max loss limit for today (₹__)", "category": "risk"},
            {"item": "I am calm, rested, and not trading on emotion", "category": "mindset"},
            {"item": "My watchlist is set before 9:00 AM", "category": "preparation"},
            {"item": "I will NOT trade in the first 15 minutes (9:15–9:30)", "category": "discipline"},
            {"item": "After any loss, I wait 15 minutes before re-entering", "category": "discipline"}
        ]

        if profile and profile.known_weaknesses:
            if "revenge_trading" in profile.known_weaknesses:
                checklist.append({"item": "I commit: zero revenge trades today, regardless of P&L", "category": "personal"})
            if "overtrading" in profile.known_weaknesses:
                limit = profile.daily_trade_limit or 5
                checklist.append({"item": f"Max {limit} trades today — I close the app after #{limit}", "category": "personal"})
            if "fomo" in profile.known_weaknesses:
                checklist.append({"item": "If it wasn't on my watchlist before open, I don't trade it", "category": "personal"})

        # Extra items based on yesterday
        if yesterday_alerts and any(a.severity == "danger" for a in yesterday_alerts):
            checklist.append({"item": "I have reviewed yesterday's alerts — I know why they triggered", "category": "review"})

        return checklist

    def _calculate_readiness_score(
        self,
        profile: Optional[UserProfile],
        recent_positions: List[Position],
        day_name: str
    ) -> Dict:
        """Calculate overall readiness score (0–100). Lower = more caution needed."""
        score = 100
        factors = []

        # Factor 1: Historically bad day of week
        if profile and profile.detected_patterns:
            for danger in profile.detected_patterns.get("time_patterns", {}).get("danger_days", []):
                if danger["day"] == day_name:
                    score -= 20
                    factors.append({"factor": "danger_day", "impact": -20, "detail": f"{day_name} has low win rate historically"})

        # Factor 2: Recent PnL in last 5 trades
        if recent_positions:
            sorted_pos = sorted(recent_positions, key=lambda p: p.last_exit_time or datetime.min, reverse=True)
            recent_pnls = [float(p.realized_pnl or p.pnl or 0) for p in sorted_pos[:5]]
            recent_pnl = sum(recent_pnls)
            if recent_pnl < -3000:
                score -= 20
                factors.append({"factor": "large_recent_loss", "impact": -20, "detail": f"₹{recent_pnl:,.0f} in last 5 trades"})
            elif recent_pnl < -1500:
                score -= 10
                factors.append({"factor": "moderate_recent_loss", "impact": -10})

            # Consecutive losing trades
            streak = sum(1 for p in recent_pnls if p < 0)  # simplified
            if streak >= 4:
                score -= 15
                factors.append({"factor": "losing_streak", "impact": -15, "detail": f"{streak} recent losses"})
            elif streak >= 2:
                score -= 5
                factors.append({"factor": "losing_streak", "impact": -5})

        # Factor 3: Expiry day (volatile)
        if day_name == "Thursday":
            score -= 5
            factors.append({"factor": "expiry_day", "impact": -5, "detail": "Weekly expiry — higher volatility"})

        score = max(0, min(100, score))

        if score >= 80:
            status, message = "ready", "Good to trade. Stay disciplined and stick to your plan."
        elif score >= 60:
            status, message = "caution", "Trade carefully. Consider smaller positions than usual."
        else:
            status, message = "warning", "High-risk session. Strongly consider reduced activity or sitting out."

        return {"score": score, "status": status, "message": message, "factors": factors}

    def _get_suggested_commitments(self, watch_outs: List[Dict], yesterday_alerts: List[RiskAlert]) -> List[str]:
        """Generate suggested commitments based on watch-outs and yesterday's alerts."""
        commitments = [
            "I will wait 15 minutes after any loss before re-entering",
            "I will not trade in the first 15 minutes of open",
        ]

        alert_types = {a.pattern_type for a in yesterday_alerts if a.severity == "danger"}
        if "revenge_trading" in alert_types:
            commitments.insert(0, "Zero revenge trades today — I commit to this before clicking anything")
        if "overtrading" in alert_types:
            commitments.insert(0, "Maximum 4 trades today. Quality over quantity.")
        if "fomo" in alert_types:
            commitments.append("Only pre-planned set-ups. No chasing missed moves.")

        for wo in watch_outs:
            if wo["type"] == "time":
                commitments.append("I will skip my identified danger hour(s) today")
                break
            if wo["type"] == "symbol":
                commitments.append("I will avoid my identified problem symbol(s) today")
                break

        return list(dict.fromkeys(commitments))[:5]


# Singleton instance
daily_reports_service = DailyReportsService()
