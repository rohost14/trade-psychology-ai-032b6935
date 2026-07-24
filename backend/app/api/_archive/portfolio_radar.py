"""
Portfolio Radar API

Exposes position metrics, concentration analysis, and GTT discipline summary
for the Portfolio Radar frontend component.

All data is pre-calculated by the Celery radar task every 5 minutes.
This endpoint just reads the latest cached results and returns them.
For on-demand refresh it also triggers a synchronous compute.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, List
from uuid import UUID

from app.core.database import get_db
from app.api.deps import get_verified_broker_account_id
from app.core.rate_limit import rate_limit

router = APIRouter(prefix="/api/portfolio-radar", tags=["portfolio_radar"])


@router.get("/metrics")
async def get_position_metrics(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
) -> Dict:
    """
    Return position metrics for all open F&O positions.
    Includes breakeven, premium decay, DTE, capital at risk.
    Uses Redis LTP cache — instant, no Kite API call.
    """
    from app.services.position_metrics_service import position_metrics_service

    metrics = await position_metrics_service.compute_all(broker_account_id, db)
    return {"metrics": metrics, "count": len(metrics)}


@router.get("/concentration")
async def get_concentration(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
) -> Dict:
    """
    Return portfolio concentration analysis:
    - Expiry week distribution
    - Underlying concentration
    - Directional skew (long/short split)
    - Margin utilization
    Does NOT fire alerts (read-only view).
    """
    from app.services.position_metrics_service import position_metrics_service
    from app.services.portfolio_concentration_service import _analyse_concentration, check_margin_utilization

    bid = broker_account_id
    metrics = await position_metrics_service.compute_all(bid, db)
    concentration = _analyse_concentration(metrics)

    margin_alert = await check_margin_utilization(bid, db)
    if margin_alert:
        concentration["margin_utilization"] = margin_alert["value"]
    else:
        concentration["margin_utilization"] = None

    return concentration


@router.get("/gtt-discipline")
async def get_gtt_discipline(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
) -> Dict:
    """
    Return GTT discipline summary: active GTTs, honored vs overridden counts.
    NOTE: discipline_rate is omitted from response (internal metric only).
    """
    from app.services.gtt_service import get_discipline_summary

    summary = await get_discipline_summary(broker_account_id, db)
    # Strip the internal score — not for frontend display
    summary.pop("discipline_rate", None)
    return summary


@router.post("/sync-gtts")
async def sync_gtts(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(rate_limit(max_calls=5, window_seconds=60)),
) -> Dict:
    """
    Manually trigger GTT sync for this account.
    Called when user opens Portfolio Radar page to get fresh data.
    """
    from app.services.gtt_service import sync_gtt_triggers
    from app.models.broker_account import BrokerAccount
    from sqlalchemy import select

    bid = broker_account_id

    result = await db.execute(
        select(BrokerAccount).where(BrokerAccount.id == bid)
    )
    account = result.scalar_one_or_none()
    if not account or not account.access_token:
        return {"error": "account_not_found"}

    try:
        access_token = account.decrypt_token(account.access_token)
    except ValueError:
        return {"error": "token_decrypt_failed"}

    return await sync_gtt_triggers(bid, access_token, db)
