from typing import Any, List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from app.core.database import get_db
from app.api.deps import get_current_user
from app.services.trade_sync_service import TradeSyncService
from app.models.trade import Trade
from app.schemas.trade import TradeListResponse, TradeResponse, TradeStatsResponse

router = APIRouter()

@router.post("/sync")
async def sync_trades(
    payload: dict = Body(...), # Expect {broker_account_id: UUID}
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Sync trades from Zerodha for a given broker account."""
    broker_account_id_str = payload.get("broker_account_id")
    if not broker_account_id_str:
        raise HTTPException(status_code=400, detail="broker_account_id is required")
        
    try:
        broker_account_id = UUID(broker_account_id_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID")
        
    result = await TradeSyncService.sync_trades_for_broker_account(broker_account_id, db)
    return result

@router.get("/", response_model=TradeListResponse)
async def list_trades(
    broker_account_id: UUID,
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
    broker_account_id: UUID,
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

@router.get("/{trade_id}", response_model=TradeResponse)
async def get_trade(
    trade_id: UUID,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get single trade defail."""
    trade = await db.get(Trade, trade_id)
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    return trade
