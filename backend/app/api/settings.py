from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from uuid import UUID
import logging

from app.core.database import get_db
from app.api.deps import get_verified_broker_account_id, get_current_user_id
from app.models.user import User
from app.models.broker_account import BrokerAccount

router = APIRouter()
logger = logging.getLogger(__name__)

class GuardianSettingsRequest(BaseModel):
    guardian_name: str | None = None
    guardian_phone: str | None = None

@router.post("/guardian")
async def update_guardian_settings(
    request: GuardianSettingsRequest,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """Update Risk Guardian settings. Stored on the user, not the broker account."""

    try:
        user = await db.get(User, user_id)
        if not user:
            raise HTTPException(404, "User not found")

        if request.guardian_name is not None:
            user.guardian_name = request.guardian_name
        if request.guardian_phone is not None:
            user.guardian_phone = request.guardian_phone

        await db.commit()

        logger.info(f"Guardian settings updated for user {user_id}")

        return {
            "success": True,
            "message": "Guardian settings updated"
        }

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to update guardian settings: {e}")
        raise HTTPException(500, "Failed to update guardian settings")
