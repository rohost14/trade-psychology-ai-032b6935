from twilio.rest import Client
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

class WhatsAppService:
    def __init__(self):
        self.account_sid = settings.TWILIO_ACCOUNT_SID
        self.auth_token = settings.TWILIO_AUTH_TOKEN
        self.from_number = settings.TWILIO_WHATSAPP_FROM
        
        self.client = None
        if self.account_sid and self.auth_token:
            try:
                self.client = Client(self.account_sid, self.auth_token)
            except Exception as e:
                logger.error(f"Failed to initialize Twilio client: {e}")
        else:
            logger.info("Twilio credentials not set. WhatsApp service in SAFE MODE (Logging only).")

    def send_message(self, to_number: str, content: str) -> bool:
        """
        Send WhatsApp message. Returns True if successful (or mocked).
        """
        if not self.client or not self.from_number:
            print("\n" + "="*50)
            print(f"📱 WHATSAPP MESSAGE (SAFE MODE) to {to_number}:")
            print("-" * 30)
            print(content)
            print("="*50 + "\n")
            logger.info(f"WhatsApp Safe Mode: Message logged for {to_number}")
            return True
            
        try:
            # Twilio requires "whatsapp:" prefix for sender and receiver
            from_whatsapp = f"whatsapp:{self.from_number}" if not self.from_number.startswith("whatsapp:") else self.from_number
            to_whatsapp = f"whatsapp:{to_number}" if not to_number.startswith("whatsapp:") else to_number
            
            message = self.client.messages.create(
                from_=from_whatsapp,
                body=content,
                to=to_whatsapp
            )
            logger.info(f"WhatsApp sent: {message.sid}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send WhatsApp message: {e}")
            return False

# Singleton instance
whatsapp_service = WhatsAppService()
