"""
Push Notification API Endpoints

Handles subscription management and notification sending.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from uuid import UUID
from typing import Optional
import logging

from app.core.database import get_db
from app.api.deps import get_verified_broker_account_id
from app.services.push_notification_service import push_service

router = APIRouter()
logger = logging.getLogger(__name__)


class SubscriptionKeys(BaseModel):
    p256dh: str
    auth: str


class SubscriptionData(BaseModel):
    endpoint: str
    keys: SubscriptionKeys


class SubscribeRequest(BaseModel):
    subscription: SubscriptionData


class UnsubscribeRequest(BaseModel):
    endpoint: Optional[str] = None  # If None, removes all subscriptions


class TestNotificationRequest(BaseModel):
    title: Optional[str] = "Test Notification"
    body: Optional[str] = "This is a test push notification from TradeMentor AI"


@router.post("/subscribe")
async def subscribe_to_push(
    request: SubscribeRequest,
    req: Request,
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Subscribe to push notifications.

    Saves the browser's push subscription to the database.
    """
    try:
        user_agent = req.headers.get("user-agent")

        subscription = await push_service.subscribe(
            broker_account_id=broker_account_id,
            endpoint=request.subscription.endpoint,
            p256dh_key=request.subscription.keys.p256dh,
            auth_key=request.subscription.keys.auth,
            db=db,
            user_agent=user_agent
        )

        logger.info(f"Push subscription created for account {broker_account_id}")

        return {
            "success": True,
            "subscription_id": str(subscription.id),
            "device_type": subscription.device_type
        }

    except Exception as e:
        logger.error(f"Failed to subscribe: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/unsubscribe")
async def unsubscribe_from_push(
    request: UnsubscribeRequest,
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Unsubscribe from push notifications.

    If endpoint is provided, removes that specific subscription.
    If endpoint is None, removes all subscriptions for the account.
    """
    try:
        removed = await push_service.unsubscribe(
            broker_account_id=broker_account_id,
            endpoint=request.endpoint,
            db=db
        )

        return {
            "success": True,
            "removed": removed
        }

    except Exception as e:
        logger.error(f"Failed to unsubscribe: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/test")
async def send_test_notification(
    request: TestNotificationRequest,
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Send a test push notification.

    Useful for verifying push is working correctly.
    """
    try:
        result = await push_service.send_notification(
            broker_account_id=broker_account_id,
            title=request.title,
            body=request.body,
            db=db,
            severity="info",
            tag="test-notification"
        )

        if result.get("sent", 0) > 0:
            return {
                "success": True,
                "message": f"Test notification sent to {result['sent']} device(s)"
            }
        else:
            return {
                "success": False,
                "message": "No active subscriptions found",
                "error": result.get("error")
            }

    except Exception as e:
        logger.error(f"Failed to send test notification: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/status")
async def get_notification_status(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Get push notification status for an account.

    Returns whether push is configured and subscription count.
    """
    from sqlalchemy import select, func
    from app.models.push_subscription import PushSubscription

    try:
        # Count active subscriptions
        result = await db.execute(
            select(func.count(PushSubscription.id)).where(
                PushSubscription.broker_account_id == broker_account_id,
                PushSubscription.is_active == True
            )
        )
        subscription_count = result.scalar() or 0

        return {
            "configured": push_service.is_configured(),
            "subscriptions": subscription_count,
            "push_enabled": subscription_count > 0
        }

    except Exception as e:
        logger.error(f"Failed to get notification status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
