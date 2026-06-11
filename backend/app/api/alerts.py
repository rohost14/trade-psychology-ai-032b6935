from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from uuid import UUID
import time
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import get_verified_broker_account_id, get_current_broker_account_id
from app.core.database import get_db
from app.services.alert_service import AlertService

logger = logging.getLogger(__name__)
router = APIRouter()

# 3 test alerts per hour per account — prevents using this as a spam endpoint
_TEST_ALERT_MAX = 3
_TEST_ALERT_WINDOW = 3600


class TestAlertRequest(BaseModel):
    phone_number: str  # Format: +919876543210


@router.post("/test")
async def send_test_alert(
    request: TestAlertRequest,
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Send test WhatsApp alert to verify configuration.
    Phone must match the guardian_phone on the user's account.
    Rate limited to 3 requests per hour per account.
    """
    from app.models.broker_account import BrokerAccount
    from app.models.user import User

    # ── 1. Per-account rate limit ─────────────────────────────────────────────
    try:
        import redis as redis_lib
        from app.core.config import settings
        r = redis_lib.from_url(settings.REDIS_URL, socket_connect_timeout=1)
        rl_key = f"rl:test_alert:{broker_account_id}"
        now = time.time()
        window_start = now - _TEST_ALERT_WINDOW
        pipe = r.pipeline()
        pipe.zremrangebyscore(rl_key, "-inf", window_start)
        pipe.zcard(rl_key)
        pipe.zadd(rl_key, {f"{now:.9f}": now})
        pipe.expire(rl_key, _TEST_ALERT_WINDOW + 1)
        results = pipe.execute()
        r.close()
        if results[1] >= _TEST_ALERT_MAX:
            raise HTTPException(
                status_code=429,
                detail=f"Too many test alerts. Max {_TEST_ALERT_MAX} per hour.",
                headers={"Retry-After": str(_TEST_ALERT_WINDOW)},
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Rate limit check skipped for test alert (Redis error): {e}")

    # ── 2. Validate phone matches user's guardian_phone ───────────────────────
    account_result = await db.execute(
        select(BrokerAccount).where(BrokerAccount.id == broker_account_id)
    )
    account = account_result.scalar_one_or_none()
    if not account or not account.user_id:
        raise HTTPException(status_code=404, detail="Account not found")

    user_result = await db.execute(
        select(User).where(User.id == account.user_id)
    )
    user = user_result.scalar_one_or_none()
    if not user or not user.guardian_phone:
        raise HTTPException(status_code=400, detail="No guardian phone configured on your account")

    # Normalize both sides: strip spaces, standardize +91 prefix
    def _normalize(phone: str) -> str:
        return phone.strip().replace(" ", "").replace("-", "")

    if _normalize(request.phone_number) != _normalize(user.guardian_phone):
        raise HTTPException(
            status_code=403,
            detail="Phone number does not match the guardian phone on your account",
        )

    # ── 3. Send test alert ────────────────────────────────────────────────────
    alert_service = AlertService()
    success = await alert_service.send_test_alert(request.phone_number)

    if success:
        return {"success": True, "message": f"Test alert sent to {request.phone_number}"}
    else:
        raise HTTPException(500, "Failed to send alert. Check logs.")
