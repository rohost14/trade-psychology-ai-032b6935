from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from uuid import UUID

from app.models.trade import Trade
from app.models.risk_alert import RiskAlert
from app.models.position import Position
from app.models.broker_account import BrokerAccount
from app.services.alert_service import AlertService
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
        self.alert_service = AlertService()
    
    async def send_eod_report(
        self,
        broker_account_id: UUID,
        phone_number: str,
        db: AsyncSession
    ) -> bool:
        """
        Generate and send End-of-Day report via WhatsApp.
        
        Called by cron at 3:30 PM IST daily.
        """
        try:
            # Get today's data
            today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            today_end = datetime.now(timezone.utc)
            
            # Get today's trades
            trades_result = await db.execute(
                select(Trade).where(
                    Trade.broker_account_id == broker_account_id,
                    Trade.order_timestamp >= today_start,
                    Trade.order_timestamp <= today_end,
                    Trade.status == "COMPLETE"
                )
            )
            today_trades = trades_result.scalars().all()
            
            # Get today's alerts
            alerts_result = await db.execute(
                select(RiskAlert).where(
                    RiskAlert.broker_account_id == broker_account_id,
                    RiskAlert.detected_at >= today_start,
                    RiskAlert.detected_at <= today_end
                )
            )
            today_alerts = alerts_result.scalars().all()
            
            # Get current positions for P&L
            positions_result = await db.execute(
                select(Position).where(
                    Position.broker_account_id == broker_account_id
                )
            )
            positions = positions_result.scalars().all()
            total_pnl = sum(p.pnl or 0 for p in positions)
            
            # Generate report message
            message = self._format_eod_report(
                trades=today_trades,
                alerts=today_alerts,
                total_pnl=total_pnl
            )
            
            # Send via WhatsApp
            twilio_message = self.alert_service.client.messages.create(
                body=message,
                from_=self.alert_service.from_number,
                to=f"whatsapp:{phone_number}"
            )
            
            logger.info(f"EOD report sent: {twilio_message.sid}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send EOD report: {e}", exc_info=True)
            return False
    
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
            f"Time: {datetime.now().strftime('%I:%M %p')}\n"
            f"TradeMentor AI"
        )
        
        return header + pnl_section + risk_section + analysis + footer
    
    async def send_morning_brief(
        self,
        broker_account_id: UUID,
        phone_number: str,
        db: AsyncSession
    ) -> bool:
        """
        Generate and send Morning Brief via WhatsApp.
        
        Called by cron at 8:30 AM IST daily.
        """
        try:
            # Get yesterday's summary
            yesterday = datetime.now(timezone.utc) - timedelta(days=1)
            yesterday_start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
            yesterday_end = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
            
            # Yesterday's alerts
            alerts_result = await db.execute(
                select(RiskAlert).where(
                    RiskAlert.broker_account_id == broker_account_id,
                    RiskAlert.detected_at >= yesterday_start,
                    RiskAlert.detected_at <= yesterday_end
                )
            )
            yesterday_alerts = alerts_result.scalars().all()
            
            # Get current risk state (from last 4 hours of alerts)
            recent_cutoff = datetime.now(timezone.utc) - timedelta(hours=4)
            recent_alerts_result = await db.execute(
                select(RiskAlert).where(
                    RiskAlert.broker_account_id == broker_account_id,
                    RiskAlert.detected_at >= recent_cutoff,
                    RiskAlert.acknowledged_at.is_(None)
                )
            )
            recent_alerts = recent_alerts_result.scalars().all()
            
            # Determine risk state
            risk_state = "safe"
            if any(a.severity == "danger" for a in recent_alerts):
                risk_state = "danger"
            elif any(a.severity == "caution" for a in recent_alerts):
                risk_state = "caution"
            
            # Generate message
            message = self._format_morning_brief(
                yesterday_alerts=yesterday_alerts,
                current_risk_state=risk_state
            )
            
            # Send via WhatsApp
            twilio_message = self.alert_service.client.messages.create(
                body=message,
                from_=self.alert_service.from_number,
                to=f"whatsapp:{phone_number}"
            )
            
            logger.info(f"Morning brief sent: {twilio_message.sid}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send morning brief: {e}", exc_info=True)
            return False
    
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
