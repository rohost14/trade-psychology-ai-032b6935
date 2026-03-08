from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.api.deps import get_verified_broker_account_id
from app.models.position import Position
from app.schemas.position import PositionListResponse, ExposureMetrics
from decimal import Decimal
from uuid import UUID

router = APIRouter()

@router.get("/", response_model=PositionListResponse)
async def get_positions(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Position).where(
            Position.broker_account_id == broker_account_id,
            Position.status == 'open'
        )
    )
    positions = result.scalars().all()

    # Calculate totals using Zerodha's P&L fields
    total_value = sum(float(p.value or 0) for p in positions)
    # Use unrealized_pnl for open positions, or pnl as fallback
    total_pnl = sum(float(p.unrealized_pnl or p.pnl or 0) for p in positions)

    return {
        "positions": positions,
        "total_count": len(positions),
        "total_value": Decimal(str(total_value)) if total_value else Decimal(0),
        "total_pnl": Decimal(str(total_pnl)) if total_pnl else Decimal(0)
    }

@router.get("/exposure", response_model=ExposureMetrics)
async def get_exposure_metrics(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Position).where(
            Position.broker_account_id == broker_account_id,
            Position.status == 'open'
        )
    )
    positions = result.scalars().all()

    if not positions:
        return ExposureMetrics(
            total_positions=0,
            total_value=Decimal(0),
            total_pnl=Decimal(0),
            largest_position_value=Decimal(0),
            concentration_pct=0.0
        )

    values = [abs((p.average_entry_price or 0) * (p.total_quantity or 0)) for p in positions]
    total_value = sum(values)
    largest = max(values) if values else 0

    return ExposureMetrics(
        total_positions=len(positions),
        total_value=Decimal(str(total_value)),
        total_pnl=sum(p.realized_pnl or 0 for p in positions),
        largest_position_value=Decimal(str(largest)),
        concentration_pct=float(largest / total_value * 100) if total_value > 0 else 0.0
    )
