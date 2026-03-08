from twilio.rest import Client
import logging
import asyncio
from functools import partial
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

    @property
    def is_configured(self) -> bool:
        """Check if Twilio is configured and ready to send messages."""
        return self.client is not None and self.from_number is not None

    async def send_message(self, to_number: str, content: str) -> bool:
        """
        Send WhatsApp message. Returns True if successful (or mocked).
        Uses asyncio executor to avoid blocking the event loop.
        """
        if not self.client or not self.from_number:
            logger.info(
                "WhatsApp Safe Mode: Message to %s | %s",
                to_number,
                content[:120].replace("\n", " ")
            )
            return True

        try:
            # Twilio requires "whatsapp:" prefix for sender and receiver
            from_whatsapp = f"whatsapp:{self.from_number}" if not self.from_number.startswith("whatsapp:") else self.from_number
            to_whatsapp = f"whatsapp:{to_number}" if not to_number.startswith("whatsapp:") else to_number

            # Run blocking Twilio call in executor to not block event loop
            loop = asyncio.get_event_loop()
            message = await loop.run_in_executor(
                None,
                partial(
                    self.client.messages.create,
                    from_=from_whatsapp,
                    body=content,
                    to=to_whatsapp
                )
            )
            logger.info(f"WhatsApp sent: {message.sid}")
            return True

        except Exception as e:
            logger.error(f"Failed to send WhatsApp message: {e}")
            return False

# Singleton instance
whatsapp_service = WhatsAppService()
