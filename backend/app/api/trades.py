from typing import Any, List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_

from app.core.database import get_db
from app.api.deps import get_verified_broker_account_id
from app.services.trade_sync_service import TradeSyncService
from app.models.trade import Trade
from app.models.completed_trade import CompletedTrade
from app.models.incomplete_position import IncompletePosition
from app.schemas.trade import (
    TradeListResponse, TradeResponse, TradeStatsResponse,
    CompletedTradeListResponse, CompletedTradeResponse,
    IncompletePositionListResponse, IncompletePositionResponse,
)

router = APIRouter()

@router.post("/sync")
async def sync_trades(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Sync trades from Zerodha for a given broker account."""
    result = await TradeSyncService.sync_trades_for_broker_account(broker_account_id, db)
    return result

@router.get("/", response_model=TradeListResponse)
async def list_trades(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    limit: int = 50,
    offset: int = 0,
    status: Optional[str] = None,
    asset_class: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """List trades with filtering."""
    query = select(Trade).where(Trade.broker_account_id == broker_account_id)

    if status:
        query = query.where(Trade.status == status)
    if asset_class:
        query = query.where(Trade.asset_class == asset_class)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query)

    # Pagination & Sort
    query = query.order_by(desc(Trade.order_timestamp)).offset(offset).limit(limit)
    result = await db.execute(query)
    trades = result.scalars().all()

    return {
        "trades": trades,
        "total": total or 0,
        "page": (offset // limit) + 1,
        "limit": limit
    }

@router.get("/stats", response_model=TradeStatsResponse)
async def get_trade_stats(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get trade statistics."""
    query = select(Trade).where(Trade.broker_account_id == broker_account_id)
    result = await db.execute(query)
    trades = result.scalars().all()

    total_trades = len(trades)
    winning = [t for t in trades if (t.pnl or 0) > 0]
    losing = [t for t in trades if (t.pnl or 0) < 0]
    total_pnl = sum([float(t.pnl or 0) for t in trades])
    avg_pnl = total_pnl / total_trades if total_trades > 0 else 0

    return {
        "total_trades": total_trades,
        "winning_trades": len(winning),
        "losing_trades": len(losing),
        "total_pnl": total_pnl,
        "avg_pnl": avg_pnl
    }

# ------------------------------------------------------------------
# CompletedTrade endpoints (flat-to-flat rounds)
# MUST be registered BEFORE /{trade_id} to avoid UUID matching
# ------------------------------------------------------------------

@router.get("/completed", response_model=CompletedTradeListResponse)
async def list_completed_trades(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    List completed trade rounds (flat-to-flat position lifecycles).
    Ordered by exit_time descending (most recent first).
    """
    base_query = select(CompletedTrade).where(
        CompletedTrade.broker_account_id == broker_account_id
    )

    count_query = select(func.count()).select_from(base_query.subquery())
    total = await db.scalar(count_query)

    query = (
        base_query
        .order_by(desc(CompletedTrade.exit_time))
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(query)
    trades = result.scalars().all()

    return {"trades": trades, "total": total or 0}


@router.get("/incomplete", response_model=IncompletePositionListResponse)
async def list_incomplete_positions(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    status: Optional[str] = Query(None, description="Filter by resolution_status: PENDING, RESOLVED, IGNORED"),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    List incomplete positions (sync gaps where FIFO has unmatched fills
    but broker says position is flat).
    """
    base_query = select(IncompletePosition).where(
        IncompletePosition.broker_account_id == broker_account_id
    )
    if status:
        base_query = base_query.where(
            IncompletePosition.resolution_status == status
        )

    count_query = select(func.count()).select_from(base_query.subquery())
    total = await db.scalar(count_query)

    query = base_query.order_by(desc(IncompletePosition.detected_at))
    result = await db.execute(query)
    positions = result.scalars().all()

    return {"positions": positions, "total": total or 0}


# ------------------------------------------------------------------
# Single trade by ID (must be AFTER /completed and /incomplete)
# ------------------------------------------------------------------

@router.get("/{trade_id}", response_model=TradeResponse)
async def get_trade(
    trade_id: UUID,
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get single trade detail."""
    trade = await db.get(Trade, trade_id)
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    if trade.broker_account_id != broker_account_id:
        raise HTTPException(status_code=404, detail="Trade not found")
    return trade
