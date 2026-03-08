"""
Alert Tasks (Celery)

Async tasks for sending notifications:
- WhatsApp alerts
- Push notifications (future)
- Email alerts (future)
"""

import logging
from uuid import UUID
from typing import Optional

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.services.alert_service import AlertService
from app.models.user import User
from app.models.risk_alert import RiskAlert
from app.models.broker_account import BrokerAccount
from sqlalchemy import select

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def send_whatsapp_alert(
    self,
    broker_account_id: str,
    message: str,
    phone_number: Optional[str] = None
):
    """
    Send a WhatsApp message to user.

    Args:
        broker_account_id: Account to send alert for
        message: Message content
        phone_number: Override phone (uses guardian_phone if not provided)
    """
    import asyncio

    async def _send():
        async with SessionLocal() as db:
            try:
                # Get broker account
                result = await db.execute(
                    select(BrokerAccount).where(
                        BrokerAccount.id == UUID(broker_account_id)
                    )
                )
                account = result.scalar_one_or_none()

                if not account:
                    logger.error(f"Account not found: {broker_account_id}")
                    return {"success": False, "error": "Account not found"}

                # Get phone number from user
                user = await db.get(User, account.user_id) if account.user_id else None
                phone = phone_number or (user.guardian_phone if user else None)
                if not phone:
                    logger.warning(f"No phone number for account {broker_account_id}")
                    return {"success": False, "error": "No phone number"}

                # Send via Twilio
                alert_service = AlertService()
                sent = await alert_service.send_whatsapp_message(phone, message)

                logger.info(f"WhatsApp sent to {phone[:6]}***: {sent}")
                return {"success": sent}

            except Exception as e:
                logger.error(f"WhatsApp send failed: {e}", exc_info=True)
                raise self.retry(exc=e)

    return asyncio.get_event_loop().run_until_complete(_send())


@celery_app.task
def send_risk_alert_notification(alert_id: str):
    """
    Send notification for a specific risk alert.

    Called when a new DANGER alert is created.
    """
    import asyncio

    async def _send():
        async with SessionLocal() as db:
            try:
                # Get alert with account info
                result = await db.execute(
                    select(RiskAlert).where(RiskAlert.id == UUID(alert_id))
                )
                alert = result.scalar_one_or_none()

                if not alert:
                    return {"error": "Alert not found"}

                # Get account
                account_result = await db.execute(
                    select(BrokerAccount).where(
                        BrokerAccount.id == alert.broker_account_id
                    )
                )
                account = account_result.scalar_one_or_none()

                if not account:
                    return {"error": "Account not found"}

                # Format alert message
                severity_emoji = "🔴" if alert.severity == "danger" else "🟡"
                message = f"""
{severity_emoji} *TradeMentor Alert*

Pattern: {alert.pattern_type}
Severity: {alert.severity.upper()}

{alert.message}

_Stay disciplined. Follow your rules._
"""

                # Get phone from user
                user = await db.get(User, account.user_id) if account.user_id else None
                phone = user.guardian_phone if user else None
                if not phone:
                    logger.warning(f"No guardian phone for account {account.id}, skipping alert notification")
                    return {"error": "No guardian phone configured"}

                # Send
                alert_service = AlertService()
                sent = await alert_service.send_whatsapp_message(phone, message.strip())

                return {"sent": sent}

            except Exception as e:
                logger.error(f"Risk alert notification failed: {e}", exc_info=True)
                return {"error": str(e)}

    return asyncio.get_event_loop().run_until_complete(_send())


@celery_app.task
def send_bulk_alerts(broker_account_ids: list, message: str):
    """
    Send same message to multiple users.

    Used for system-wide announcements or market alerts.
    """
    results = []
    for account_id in broker_account_ids:
        result = send_whatsapp_alert.delay(account_id, message)
        results.append({"account_id": account_id, "task_id": result.id})

    return {"queued": len(results), "tasks": results}
