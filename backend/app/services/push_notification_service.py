"""
Push Notification Service

Sends Web Push notifications to subscribed browsers/devices.
Uses pywebpush library for VAPID authentication.
"""

import logging
from typing import Dict, Any, List, Optional
from uuid import UUID
from datetime import datetime, timezone
import json

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete

from app.core.config import settings
from app.models.push_subscription import PushSubscription
from app.models.risk_alert import RiskAlert

logger = logging.getLogger(__name__)

# Try to import pywebpush, provide fallback if not installed
try:
    from pywebpush import webpush, WebPushException
    WEBPUSH_AVAILABLE = True
except ImportError:
    WEBPUSH_AVAILABLE = False
    logger.warning("pywebpush not installed. Push notifications disabled.")


class PushNotificationService:
    """
    Manages push notification subscriptions and sends notifications.
    """

    def __init__(self):
        self.vapid_private_key = getattr(settings, 'VAPID_PRIVATE_KEY', None)
        self.vapid_public_key = getattr(settings, 'VAPID_PUBLIC_KEY', None)
        self.vapid_claims = {
            "sub": f"mailto:{getattr(settings, 'VAPID_EMAIL', 'admin@tradementor.ai')}"
        }

    def is_configured(self) -> bool:
        """Check if push notifications are properly configured."""
        return (
            WEBPUSH_AVAILABLE and
            self.vapid_private_key is not None and
            self.vapid_public_key is not None
        )

    async def subscribe(
        self,
        broker_account_id: UUID,
        endpoint: str,
        p256dh_key: str,
        auth_key: str,
        db: AsyncSession,
        user_agent: str = None,
        device_type: str = None
    ) -> PushSubscription:
        """
        Save a new push subscription or update existing one.

        Args:
            broker_account_id: Account to subscribe
            endpoint: Push service endpoint URL
            p256dh_key: Public key for encryption
            auth_key: Auth secret
            db: Database session
            user_agent: Browser user agent (optional)
            device_type: Device type (optional)

        Returns:
            Created or updated PushSubscription
        """
        # Check if subscription already exists (same endpoint)
        result = await db.execute(
            select(PushSubscription).where(PushSubscription.endpoint == endpoint)
        )
        existing = result.scalar_one_or_none()

        if existing:
            # Update existing subscription
            existing.broker_account_id = broker_account_id
            existing.p256dh_key = p256dh_key
            existing.auth_key = auth_key
            existing.user_agent = user_agent
            existing.device_type = device_type
            existing.is_active = True
            existing.failed_count = 0
            existing.updated_at = datetime.now(timezone.utc)
            subscription = existing
        else:
            # Create new subscription
            subscription = PushSubscription(
                broker_account_id=broker_account_id,
                endpoint=endpoint,
                p256dh_key=p256dh_key,
                auth_key=auth_key,
                user_agent=user_agent,
                device_type=device_type or self._detect_device_type(user_agent),
                is_active=True
            )
            db.add(subscription)

        await db.commit()
        await db.refresh(subscription)

        logger.info(f"Push subscription saved for account {broker_account_id}")
        return subscription

    async def unsubscribe(
        self,
        broker_account_id: UUID,
        endpoint: str,
        db: AsyncSession
    ) -> bool:
        """
        Remove a push subscription.

        Args:
            broker_account_id: Account to unsubscribe
            endpoint: Push service endpoint URL (optional, if None removes all)
            db: Database session

        Returns:
            True if subscription was removed
        """
        if endpoint:
            # Remove specific subscription
            result = await db.execute(
                delete(PushSubscription).where(
                    PushSubscription.broker_account_id == broker_account_id,
                    PushSubscription.endpoint == endpoint
                )
            )
        else:
            # Remove all subscriptions for account
            result = await db.execute(
                delete(PushSubscription).where(
                    PushSubscription.broker_account_id == broker_account_id
                )
            )

        await db.commit()
        deleted = result.rowcount > 0

        if deleted:
            logger.info(f"Push subscription removed for account {broker_account_id}")

        return deleted

    async def send_notification(
        self,
        broker_account_id: UUID,
        title: str,
        body: str,
        db: AsyncSession,
        data: Dict[str, Any] = None,
        severity: str = "info",
        pattern_type: str = None,
        tag: str = None
    ) -> Dict[str, Any]:
        """
        Send push notification to all subscribed devices for an account.

        Args:
            broker_account_id: Target account
            title: Notification title
            body: Notification body text
            db: Database session
            data: Additional data payload
            severity: 'danger', 'caution', or 'info'
            pattern_type: Type of pattern detected
            tag: Notification tag (for grouping/replacing)

        Returns:
            Dict with success count and failures
        """
        if not self.is_configured():
            logger.warning("Push notifications not configured, skipping")
            return {"sent": 0, "failed": 0, "error": "Not configured"}

        # Get all active subscriptions for account
        result = await db.execute(
            select(PushSubscription).where(
                PushSubscription.broker_account_id == broker_account_id,
                PushSubscription.is_active == True
            )
        )
        subscriptions = result.scalars().all()

        if not subscriptions:
            logger.info(f"No push subscriptions for account {broker_account_id}")
            return {"sent": 0, "failed": 0, "error": "No subscriptions"}

        # Build notification payload
        payload = {
            "title": title,
            "body": body,
            "icon": "/icon-192.png",
            "badge": "/badge-72.png",
            "tag": tag or f"tradementor-{pattern_type or 'alert'}",
            "severity": severity,
            "pattern_type": pattern_type,
            "data": data or {},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        sent_count = 0
        failed_count = 0
        failed_endpoints = []

        for subscription in subscriptions:
            try:
                success = await self._send_to_subscription(subscription, payload)
                if success:
                    sent_count += 1
                    # Update last used
                    subscription.last_used_at = datetime.now(timezone.utc)
                else:
                    failed_count += 1
                    failed_endpoints.append(subscription.endpoint)
                    # Track failure — deactivate after 3 failures
                    await self._handle_failed_delivery(subscription, db)
            except Exception as e:
                logger.error(f"Push send error: {e}")
                failed_count += 1
                failed_endpoints.append(subscription.endpoint)
                await self._handle_failed_delivery(subscription, db)

        await db.commit()

        logger.info(f"Push notifications: {sent_count} sent, {failed_count} failed")
        return {
            "sent": sent_count,
            "failed": failed_count,
            "failed_endpoints": failed_endpoints if failed_count > 0 else None
        }

    async def send_risk_alert_notification(
        self,
        alert: RiskAlert,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Send push notification for a risk alert.

        Args:
            alert: The RiskAlert to notify about
            db: Database session

        Returns:
            Send result
        """
        # Build title and body based on severity
        if alert.severity == "danger":
            title = "🚨 DANGER: Trading Alert"
        else:
            title = "⚠️ Caution: Trading Pattern Detected"

        # Map pattern types to readable names
        pattern_names = {
            "consecutive_loss": "Consecutive Losses",
            "revenge_sizing": "Revenge Trading",
            "overtrading": "Overtrading",
            "martingale": "Martingale Sizing",
            "tilt_loss_spiral": "Loss Spiral",
            "fomo": "FOMO Entry"
        }

        pattern_name = pattern_names.get(alert.pattern_type, alert.pattern_type.replace("_", " ").title())
        body = alert.message or f"{pattern_name} pattern detected. Take a moment to review."

        return await self.send_notification(
            broker_account_id=alert.broker_account_id,
            title=title,
            body=body,
            db=db,
            data={
                "alert_id": str(alert.id),
                "pattern_type": alert.pattern_type,
                "url": "/dashboard"
            },
            severity=alert.severity,
            pattern_type=alert.pattern_type,
            tag=f"risk-{alert.pattern_type}"
        )

    async def _send_to_subscription(
        self,
        subscription: PushSubscription,
        payload: Dict[str, Any]
    ) -> bool:
        """
        Send notification to a single subscription.

        Args:
            subscription: Target subscription
            payload: Notification payload

        Returns:
            True if sent successfully
        """
        if not WEBPUSH_AVAILABLE:
            return False

        try:
            webpush(
                subscription_info=subscription.to_dict(),
                data=json.dumps(payload),
                vapid_private_key=self.vapid_private_key,
                vapid_claims=self.vapid_claims
            )
            return True
        except WebPushException as e:
            logger.error(f"WebPush error for {subscription.endpoint[:50]}...: {e}")
            # Check if subscription is expired/invalid
            if e.response and e.response.status_code in [404, 410]:
                logger.info(f"Subscription expired: {subscription.endpoint[:50]}...")
            return False
        except Exception as e:
            logger.error(f"Unexpected push error: {e}")
            return False

    async def _handle_failed_delivery(
        self,
        subscription: PushSubscription,
        db: AsyncSession
    ):
        """
        Handle failed delivery - increment counter, deactivate if too many failures.
        """
        try:
            current_count = int(subscription.failed_count or 0) + 1

            if current_count >= 3:
                # Deactivate after 3 failures
                subscription.is_active = False
                logger.info(f"Deactivated subscription after {current_count} failures")
            else:
                subscription.failed_count = current_count
        except (ValueError, TypeError):
            subscription.failed_count = 1

    def _detect_device_type(self, user_agent: str) -> str:
        """Detect device type from user agent."""
        if not user_agent:
            return "unknown"

        ua_lower = user_agent.lower()
        if "mobile" in ua_lower or "android" in ua_lower or "iphone" in ua_lower:
            return "mobile"
        elif "tablet" in ua_lower or "ipad" in ua_lower:
            return "tablet"
        else:
            return "desktop"


# Singleton instance
push_service = PushNotificationService()
# Alias for backwards compatibility
push_notification_service = push_service
