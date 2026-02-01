from twilio.rest import Client
from typing import Optional
import logging
from uuid import UUID

from app.core.config import settings
from app.models.risk_alert import RiskAlert
from app.models.broker_account import BrokerAccount

logger = logging.getLogger(__name__)

class AlertService:
    """
    Send WhatsApp alerts for critical risk patterns.
    Currently uses Twilio WhatsApp API.
    """
    
    def __init__(self):
        self.client = Client(
            settings.TWILIO_ACCOUNT_SID,
            settings.TWILIO_AUTH_TOKEN
        )
        self.from_number = settings.TWILIO_WHATSAPP_FROM
    
    async def send_risk_alert(
        self,
        risk_alert: RiskAlert,
        broker_account: BrokerAccount,
        phone_number: str
    ) -> bool:
        """
        Send WhatsApp alert for risk pattern.
        
        Args:
            risk_alert: The RiskAlert object
            broker_account: User's broker account
            phone_number: WhatsApp number (format: +919876543210)
        
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            # Only send for DANGER alerts (not CAUTION)
            if risk_alert.severity != "danger":
                logger.info(f"Skipping alert (severity={risk_alert.severity})")
                return False
            
            # Format message based on pattern type
            message = self._format_alert_message(risk_alert, broker_account)
            
            # Send via Twilio
            twilio_message = self.client.messages.create(
                body=message,
                from_=self.from_number,
                to=f"whatsapp:{phone_number}"
            )
            
            logger.info(f"WhatsApp alert sent: {twilio_message.sid}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send WhatsApp alert: {e}", exc_info=True)
            return False
    
    def _format_alert_message(
        self,
        alert: RiskAlert,
        broker_account: BrokerAccount
    ) -> str:
        """
        Format alert message based on pattern type.
        Keep it SHORT, URGENT, ACTIONABLE.
        """
        header = "🚨 *TRADEMENTOR RISK ALERT* 🚨\n\n"
        
        if alert.pattern_type == "overtrading":
            details = alert.details or {}
            trade_count = details.get("trade_count", "multiple")
            
            message = (
                f"{header}"
                f"⚠️ *OVERTRADING DETECTED*\n\n"
                f"You've taken *{trade_count} trades in 15 minutes*.\n\n"
                f"🛑 *STOP TRADING NOW*\n"
                f"Take a mandatory 30-minute break.\n\n"
                f"This pattern historically leads to major losses."
            )
        
        elif alert.pattern_type == "revenge_sizing":
            details = alert.details or {}
            size_increase = details.get("size_increase_pct", 0)
            
            message = (
                f"{header}"
                f"⚠️ *REVENGE TRADING DETECTED*\n\n"
                f"Position size increased *{size_increase:.0f}%* after recent trade.\n\n"
                f"🛑 *STOP IMMEDIATELY*\n"
                f"You are in tilt mode.\n\n"
                f"Close this position and step away."
            )
        
        elif alert.pattern_type == "consecutive_loss":
            details = alert.details or {}
            loss_count = details.get("consecutive_losses", details.get("consecutive_count", 3))
            
            message = (
                f"{header}"
                f"⚠️ *LOSS SPIRAL DETECTED*\n\n"
                f"*{loss_count} consecutive trades* without clear wins.\n\n"
                f"🛑 *STOP TRADING*\n"
                f"Your strategy isn't working today.\n\n"
                f"Review and come back tomorrow."
            )
        
        else:
            message = (
                f"{header}"
                f"⚠️ *RISK PATTERN DETECTED*\n\n"
                f"{alert.message}\n\n"
                f"🛑 Stop trading and review your approach."
            )
        
        # Add footer
        footer = (
            f"\n\n"
            f"Account: {broker_account.broker_user_id}\n"
            f"Time: {alert.detected_at.strftime('%I:%M %p')}"
        )
        
        return message + footer
    
    async def send_test_alert(self, phone_number: str) -> bool:
        """
        Send test alert to verify WhatsApp setup.
        """
        try:
            message = (
                "✅ *TradeMentor Test Alert*\n\n"
                "Your WhatsApp alerts are configured correctly!\n\n"
                "You'll receive urgent notifications here when dangerous trading patterns are detected."
            )
            
            twilio_message = self.client.messages.create(
                body=message,
                from_=self.from_number,
                to=f"whatsapp:{phone_number}"
            )
            
            logger.info(f"Test alert sent: {twilio_message.sid}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send test alert: {e}", exc_info=True)
            return False
    
    async def send_risk_alert_with_guardian(
        self,
        risk_alert: RiskAlert,
        broker_account: BrokerAccount,
        user_phone: str
    ) -> bool:
        """
        Send alert to user AND their risk guardian (if configured).
        """
        try:
            # Send to user
            user_sent = await self.send_risk_alert(
                risk_alert,
                broker_account,
                user_phone
            )
            
            # Send to guardian if configured
            guardian_sent = False
            if broker_account.guardian_phone:
                guardian_message = self._format_guardian_alert(
                    risk_alert,
                    broker_account
                )
                
                twilio_message = self.client.messages.create(
                    body=guardian_message,
                    from_=self.from_number,
                    to=f"whatsapp:{broker_account.guardian_phone}"
                )
                
                logger.info(f"Guardian alert sent: {twilio_message.sid}")
                guardian_sent = True
            
            return user_sent
            
        except Exception as e:
            logger.error(f"Failed to send guardian alert: {e}", exc_info=True)
            return False

    def _format_guardian_alert(
        self,
        alert: RiskAlert,
        broker_account: BrokerAccount
    ) -> str:
        """Format alert for risk guardian."""
        
        guardian_name = broker_account.guardian_name or "Guardian"
        user_name = broker_account.broker_user_id  # Use Zerodha ID for now
        
        header = f"⚠️ *RISK GUARDIAN ALERT*\n\n"
        
        if alert.pattern_type == "overtrading":
            details = alert.details or {}
            trade_count = details.get("trade_count", "multiple")
            
            message = (
                f"{header}"
                f"*{user_name}* is showing high-risk behavior.\n\n"
                f"🔴 *Pattern:* Overtrading\n"
                f"📊 *Details:* {trade_count} trades in 15 minutes\n\n"
                f"This pattern historically leads to major losses.\n\n"
                f"*You may want to check in with them.*"
            )
        
        elif alert.pattern_type == "revenge_sizing":
            details = alert.details or {}
            size_increase = details.get("size_increase_pct", 0)
            
            message = (
                f"{header}"
                f"*{user_name}* is showing high-risk behavior.\n\n"
                f"🔴 *Pattern:* Revenge Trading\n"
                f"📊 *Details:* Position size increased {size_increase:.0f}% after loss\n\n"
                f"They may be in tilt mode.\n\n"
                f"*You may want to check in with them.*"
            )
        
        elif alert.pattern_type == "consecutive_loss":
            details = alert.details or {}
            loss_count = details.get("consecutive_losses", 3)
            
            message = (
                f"{header}"
                f"*{user_name}* is showing high-risk behavior.\n\n"
                f"🔴 *Pattern:* Loss Spiral\n"
                f"📊 *Details:* {loss_count} consecutive trades without wins\n\n"
                f"They may need to step away.\n\n"
                f"*You may want to check in with them.*"
            )
        
        else:
            message = (
                f"{header}"
                f"*{user_name}* triggered a risk alert.\n\n"
                f"{alert.message}\n\n"
                f"*You may want to check in with them.*"
            )
        
        footer = (
            f"\n\n"
            f"Time: {alert.detected_at.strftime('%I:%M %p')}\n"
            f"TradeMentor AI - Risk Guardian"
        )
        
        return message + footer
