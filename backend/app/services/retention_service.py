from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from uuid import UUID

from app.models.trade import Trade
from app.models.risk_alert import RiskAlert
from app.models.position import Position
from app.models.broker_account import BrokerAccount
from app.models.push_subscription import PushSubscription
from app.services.daily_reports_service import daily_reports_service
from app.services.whatsapp_service import whatsapp_service
from app.services.push_notification_service import push_notification_service
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class RetentionService:
    """
    Generate and send daily WhatsApp messages for user retention.
    - EOD Report: After market close (3:30 PM)
    - Morning Brief: Before market open (8:30 AM)
    """
    
    def __init__(self):
        pass
    
    async def _save_report(
        self,
        broker_account_id: UUID,
        report_type: str,
        report_date,
        report_data: dict,
        db: AsyncSession,
        sent_via: str = "whatsapp",
    ) -> None:
        """Save a generated report to the DB for the Reports Hub."""
        from app.models.generated_report import GeneratedReport
        from datetime import date as date_type
        rpt = GeneratedReport(
            broker_account_id=broker_account_id,
            report_type=report_type,
            report_date=report_date if isinstance(report_date, date_type) else date_type.fromisoformat(report_date),
            report_data=report_data,
            sent_via=sent_via,
        )
        db.add(rpt)
        await db.commit()

    async def send_eod_report(
        self,
        broker_account_id: UUID,
        phone_number: Optional[str],
        db: AsyncSession,
    ) -> bool:
        """
        Generate and send End-of-Day report via WhatsApp + Email + Push Notification.

        Called by cron at 4:00 PM IST daily.
        Uses the comprehensive daily_reports_service for rich insights.
        """
        try:
            # Generate comprehensive post-market report
            report = await daily_reports_service.generate_post_market_report(
                broker_account_id=broker_account_id,
                db=db
            )

            if not report.get("has_trades"):
                logger.info(f"No trades today for {broker_account_id}, skipping EOD report")
                return True

            # Save to Reports Hub
            try:
                from datetime import date
                await self._save_report(
                    broker_account_id=broker_account_id,
                    report_type="post_market",
                    report_date=date.fromisoformat(report["report_date"]),
                    report_data=report,
                    db=db,
                )
            except Exception as e:
                logger.error(f"Failed to save EOD report: {e}")

            # Send via WhatsApp
            if phone_number:
                try:
                    message = self._format_eod_report_v2(report)
                    await whatsapp_service.send_message(phone_number, message)
                    logger.info(f"EOD WhatsApp report sent for {broker_account_id}")
                except Exception as e:
                    logger.error(f"WhatsApp EOD failed: {e}")

            # Also send push notification
            try:
                summary = report["summary"]
                pnl = summary["total_pnl"]
                pnl_emoji = "📈" if pnl >= 0 else "📉"

                await push_notification_service.send_notification(
                    broker_account_id=broker_account_id,
                    db=db,
                    title="📊 Your Post-Market Report",
                    body=f"{pnl_emoji} P&L: ₹{pnl:,.0f} | {summary['total_trades']} trades | {summary['win_rate']}% win rate",
                    data={"type": "post_market_report", "url": "/reports"}
                )
                logger.info(f"EOD push notification sent for {broker_account_id}")
            except Exception as e:
                logger.error(f"Push notification failed: {e}")

            return True

        except Exception as e:
            logger.error(f"Failed to send EOD report: {e}", exc_info=True)
            return False

    def _format_eod_report_v2(self, report: dict) -> str:
        """Format comprehensive EOD report for WhatsApp."""
        summary = report["summary"]
        patterns = report.get("patterns_detected", [])
        lessons = report.get("key_lessons", [])
        tomorrow = report.get("tomorrow_focus", {})
        journey = report.get("emotional_journey", {})

        # Header
        pnl = summary["total_pnl"]
        pnl_emoji = "📈" if pnl >= 0 else "📉"

        msg = f"📊 *POST-MARKET REPORT*\n\n"

        # Summary
        msg += f"{pnl_emoji} *P&L:* ₹{pnl:,.2f}\n"
        msg += f"📝 *Trades:* {summary['total_trades']} ({summary['win_rate']}% win rate)\n"
        msg += f"💰 *Best:* ₹{summary['largest_win']:,.0f} | *Worst:* ₹{summary['largest_loss']:,.0f}\n\n"

        # Emotional Journey (simplified)
        if journey.get("timeline"):
            msg += "*Emotional Journey:*\n"
            emojis = [t["emoji"] for t in journey["timeline"][:6]]
            msg += " → ".join(emojis) + "\n\n"

        # Patterns
        if patterns:
            danger_patterns = [p for p in patterns if p["severity"] == "danger"]
            if danger_patterns:
                msg += "*⚠️ Patterns Detected:*\n"
                for p in danger_patterns[:3]:
                    msg += f"• {p['pattern'].replace('_', ' ').title()} at {p['time']}\n"
                msg += "\n"
        else:
            msg += "✅ *No danger patterns today*\n\n"

        # Key Lesson
        if lessons:
            lesson = lessons[0]
            msg += f"*💡 Key Lesson:*\n{lesson['lesson']}\n\n"

        # Tomorrow Focus
        if tomorrow:
            msg += f"*🎯 Tomorrow's Focus:*\n{tomorrow.get('primary', 'Stay disciplined')}\n"
            msg += f"Rule: {tomorrow.get('rule', 'Follow your plan')}\n"

        msg += f"\n_TradeMentor AI_"

        return msg
    
    def _format_eod_report(
        self,
        trades: list,
        alerts: list,
        total_pnl: float
    ) -> str:
        """Format EOD report message."""
        
        header = "📊 *END-OF-DAY REPORT*\n\n"
        
        # P&L Summary
        pnl_emoji = "📈" if total_pnl >= 0 else "📉"
        pnl_section = (
            f"{pnl_emoji} *Today's P&L:* ₹{total_pnl:,.2f}\n"
            f"📝 *Trades Executed:* {len(trades)}\n\n"
        )
        
        # Risk Analysis
        danger_alerts = [a for a in alerts if a.severity == "danger"]
        caution_alerts = [a for a in alerts if a.severity == "caution"]
        
        if alerts:
            risk_section = "*⚠️ Risk Violations:*\n"
            if danger_alerts:
                risk_section += f"🔴 DANGER alerts: {len(danger_alerts)}\n"
                for alert in danger_alerts[:2]:  # Show first 2
                    pattern = alert.pattern_type.replace('_', ' ').title()
                    risk_section += f"  • {pattern}\n"
            if caution_alerts:
                risk_section += f"🟡 CAUTION alerts: {len(caution_alerts)}\n"
            risk_section += "\n"
        else:
            risk_section = "✅ *No risk violations today*\n\n"
        
        # What went wrong / right
        if danger_alerts:
            analysis = (
                "*What went wrong:*\n"
                "You violated risk rules today. Review your trades and identify triggers.\n\n"
                "*Tomorrow's focus:*\n"
                "Follow your plan. No revenge trading. Respect stop losses.\n"
            )
        elif total_pnl < 0:
            analysis = (
                "*What happened:*\n"
                "Negative day, but you stayed disciplined (no major alerts).\n\n"
                "*Tomorrow's focus:*\n"
                "Don't chase losses. Quality over quantity.\n"
            )
        else:
            analysis = (
                "*What went right:*\n"
                "Good discipline today. You traded within your rules.\n\n"
                "*Tomorrow's focus:*\n"
                "Keep the same approach. Consistency is key.\n"
            )
        
        footer = (
            f"\n"
            f"Time: {datetime.now(timezone.utc).strftime('%I:%M %p')} UTC\n"
            f"TradeMentor AI"
        )
        
        return header + pnl_section + risk_section + analysis + footer
    
    async def send_morning_brief(
        self,
        broker_account_id: UUID,
        phone_number: Optional[str],
        db: AsyncSession,
    ) -> bool:
        """
        Generate and send Morning Brief via WhatsApp + Email + Push Notification.

        Called by cron at 8:30 AM IST daily.
        Uses the comprehensive daily_reports_service for rich insights.
        """
        try:
            # Generate comprehensive morning briefing
            briefing = await daily_reports_service.generate_morning_briefing(
                broker_account_id=broker_account_id,
                db=db
            )

            # Save to Reports Hub
            try:
                from datetime import date
                await self._save_report(
                    broker_account_id=broker_account_id,
                    report_type="morning_briefing",
                    report_date=date.fromisoformat(briefing["report_date"]),
                    report_data=briefing,
                    db=db,
                )
            except Exception as e:
                logger.error(f"Failed to save morning brief: {e}")

            # Send via WhatsApp
            if phone_number:
                try:
                    message = self._format_morning_brief_v2(briefing)
                    await whatsapp_service.send_message(phone_number, message)
                    logger.info(f"Morning brief WhatsApp sent for {broker_account_id}")
                except Exception as e:
                    logger.error(f"WhatsApp morning brief failed: {e}")

            # Also send push notification
            try:
                readiness = briefing.get("readiness_score", {})
                score = readiness.get("score", 100)
                status = readiness.get("status", "ready")

                if status == "warning":
                    title = "⚠️ Morning Alert: High Risk Day"
                elif status == "caution":
                    title = "🟡 Morning Brief: Trade Carefully"
                else:
                    title = "🌅 Morning Brief: Ready to Trade"

                # Build body with watch-outs
                watch_outs = briefing.get("watch_outs", [])
                if watch_outs:
                    body = watch_outs[0].get("message", "Review your morning briefing")
                else:
                    body = f"Readiness: {score}/100. {readiness.get('message', 'Stay disciplined!')}"

                await push_notification_service.send_notification(
                    broker_account_id=broker_account_id,
                    db=db,
                    title=title,
                    body=body,
                    data={"type": "morning_briefing", "url": "/reports"}
                )
                logger.info(f"Morning push notification sent for {broker_account_id}")
            except Exception as e:
                logger.error(f"Push notification failed: {e}")

            return True

        except Exception as e:
            logger.error(f"Failed to send morning brief: {e}", exc_info=True)
            return False

    def _format_morning_brief_v2(self, briefing: dict) -> str:
        """Format comprehensive morning briefing for WhatsApp."""
        readiness = briefing.get("readiness_score", {})
        day_warning = briefing.get("day_warning")
        recent = briefing.get("recent_summary", {})
        watch_outs = briefing.get("watch_outs", [])
        checklist = briefing.get("checklist", [])

        msg = f"🌅 *MORNING READINESS BRIEF*\n"
        msg += f"_{briefing.get('day_name', 'Today')}_\n\n"

        # Readiness Score
        score = readiness.get("score", 100)
        status = readiness.get("status", "ready")
        if status == "warning":
            score_emoji = "🔴"
        elif status == "caution":
            score_emoji = "🟡"
        else:
            score_emoji = "✅"

        msg += f"{score_emoji} *Readiness:* {score}/100\n"
        msg += f"{readiness.get('message', '')}\n\n"

        # Day Warning
        if day_warning and day_warning.get("is_danger_day"):
            msg += f"⚠️ *WARNING:* {day_warning['message']}\n\n"

        # Recent Summary
        if recent.get("has_recent_trades"):
            msg += f"*Recent:* {recent.get('message', '')}\n\n"

        # Watch-Outs (top 3)
        if watch_outs:
            msg += "*Today's Watch-Outs:*\n"
            for wo in watch_outs[:3]:
                msg += f"{wo['icon']} {wo['message']}\n"
            msg += "\n"

        # Quick Checklist
        msg += "*Mental Checklist:*\n"
        for item in checklist[:3]:
            msg += f"☐ {item['item']}\n"

        msg += f"\n*What's your ONE rule for today?*\n"
        msg += f"\n_Markets open at 9:15 AM_\n_TradeMentor AI_"

        return msg
    
    def _format_morning_brief(
        self,
        yesterday_alerts: list,
        current_risk_state: str
    ) -> str:
        """Format morning brief message."""
        
        header = "🌅 *GOOD MORNING*\n\n"
        
        # Risk State
        risk_emoji = {
            "safe": "✅",
            "caution": "🟡",
            "danger": "🔴"
        }
        
        risk_section = (
            f"{risk_emoji[current_risk_state]} *Current Risk State:* "
            f"{current_risk_state.upper()}\n\n"
        )
        
        # Yesterday recap
        if yesterday_alerts:
            danger_count = sum(1 for a in yesterday_alerts if a.severity == "danger")
            recap = (
                f"*Yesterday:*\n"
                f"You had {len(yesterday_alerts)} risk alert(s)"
            )
            if danger_count:
                recap += f", including {danger_count} DANGER violations"
            recap += ".\n\n"
        else:
            recap = "*Yesterday:* Clean trading, no violations. ✅\n\n"
        
        # Today's focus
        if current_risk_state == "danger":
            focus = (
                "*🚨 TODAY'S FOCUS:*\n"
                "You are in DANGER state. Take a break.\n"
                "Do NOT trade until you've reviewed yesterday.\n"
            )
        elif current_risk_state == "caution":
            focus = (
                "*⚠️ TODAY'S FOCUS:*\n"
                "Trade cautiously. Reduce position sizes.\n"
                "One mistake away from DANGER.\n"
            )
        else:
            focus = (
                "*📝 TODAY'S FOCUS:*\n"
                "Trade with discipline.\n"
                "Wait for your setups. Don't force trades.\n"
            )
        
        footer = (
            f"\n\n"
            f"Markets open in 45 minutes.\n"
            f"TradeMentor AI"
        )
        
        return header + risk_section + recap + focus + footer
