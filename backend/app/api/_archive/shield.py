"""
Shield API — Data-driven blowup protection metrics.

GET /api/shield/summary?days=30   → hero metrics
GET /api/shield/timeline?limit=50 → per-alert detail with real trades
GET /api/shield/patterns          → pattern breakdown
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional
import logging

from app.core.database import get_db
from app.api.deps import get_verified_broker_account_id
from app.services.shield_service import shield_service

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/summary")
async def get_shield_summary(
    days: Optional[int] = Query(None, ge=1, le=365),
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
):
    """Get shield summary with data-driven capital defended metrics."""
    return await shield_service.get_shield_summary(broker_account_id, db, days)


@router.get("/timeline")
async def get_shield_timeline(
    limit: int = Query(50, ge=1, le=200),
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
):
    """Get per-alert intervention timeline with real trade data."""
    timeline = await shield_service.get_intervention_timeline(
        broker_account_id, db, limit
    )
    return {"timeline": timeline, "total": len(timeline)}


@router.get("/patterns")
async def get_shield_patterns(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
):
    """Get per-pattern breakdown of shield effectiveness."""
    patterns = await shield_service.get_pattern_breakdown(broker_account_id, db)
    return {"patterns": patterns}
