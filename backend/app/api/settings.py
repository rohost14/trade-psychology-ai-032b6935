from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from pydantic import BaseModel
from uuid import UUID
import logging

from app.core.database import get_db
from app.models.broker_account import BrokerAccount

router = APIRouter()
logger = logging.getLogger(__name__)

class GuardianSettingsRequest(BaseModel):
    broker_account_id: UUID
    guardian_name: str | None = None
    guardian_phone: str | None = None

@router.post("/guardian")
async def update_guardian_settings(
    request: GuardianSettingsRequest,
    db: AsyncSession = Depends(get_db)
):
    """Update Risk Guardian settings for a broker account."""
    
    try:
        # Update broker account
        stmt = (
            update(BrokerAccount)
            .where(BrokerAccount.id == request.broker_account_id)
            .values(
                guardian_name=request.guardian_name,
                guardian_phone=request.guardian_phone
            )
        )
        
        result = await db.execute(stmt)
        await db.commit()
        
        if result.rowcount == 0:
            raise HTTPException(404, "Broker account not found")
        
        logger.info(f"Guardian settings updated for account {request.broker_account_id}")
        
        return {
            "success": True,
            "message": "Guardian settings updated"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to update guardian settings: {e}")
        raise HTTPException(500, f"Failed to update settings: {str(e)}")
