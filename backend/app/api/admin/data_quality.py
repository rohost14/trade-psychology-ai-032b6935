"""
Admin data-quality view — stored reconciliation divergences (migration 070).

Surfaces data_quality_events so FIFO-vs-broker P&L divergences (usually a
missing multiplier in mcx_contract_specs.py) are visible without grepping
pod logs. Read-only.
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin.deps import get_current_admin
from app.core.database import get_db
from app.models.data_quality_event import DataQualityEvent

router = APIRouter()


@router.get("/data-quality")
async def list_data_quality_events(
    days: int = Query(default=30, ge=1, le=180),
    kind: str | None = Query(default=None, max_length=50),
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    """Recent data-quality events + per-kind and per-symbol summaries."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    filters = [DataQualityEvent.detected_at >= cutoff]
    if kind:
        filters.append(DataQualityEvent.kind == kind)

    rows_result = await db.execute(
        select(DataQualityEvent)
        .where(and_(*filters))
        .order_by(desc(DataQualityEvent.detected_at))
        .limit(limit)
    )
    events = [e.to_dict() for e in rows_result.scalars().all()]

    kind_result = await db.execute(
        select(
            DataQualityEvent.kind,
            func.count(DataQualityEvent.id).label("count"),
            func.count(func.distinct(DataQualityEvent.broker_account_id)).label("accounts"),
            func.max(DataQualityEvent.detected_at).label("last_detected"),
        )
        .where(DataQualityEvent.detected_at >= cutoff)
        .group_by(DataQualityEvent.kind)
        .order_by(func.count(DataQualityEvent.id).desc())
    )
    by_kind = [
        {
            "kind": r.kind,
            "count": r.count,
            "accounts": r.accounts,
            "last_detected": r.last_detected.isoformat() if r.last_detected else None,
        }
        for r in kind_result.all()
    ]

    # Per-symbol rollup — for fifo_broker_divergence this is the actionable
    # list: each symbol here likely needs an mcx_contract_specs.py entry.
    symbol_result = await db.execute(
        select(
            DataQualityEvent.tradingsymbol,
            DataQualityEvent.exchange,
            func.count(DataQualityEvent.id).label("days_seen"),
            func.max(DataQualityEvent.detected_at).label("last_detected"),
        )
        .where(and_(*filters, DataQualityEvent.tradingsymbol.isnot(None)))
        .group_by(DataQualityEvent.tradingsymbol, DataQualityEvent.exchange)
        .order_by(func.count(DataQualityEvent.id).desc())
        .limit(50)
    )
    by_symbol = [
        {
            "tradingsymbol": r.tradingsymbol,
            "exchange": r.exchange,
            "days_seen": r.days_seen,
            "last_detected": r.last_detected.isoformat() if r.last_detected else None,
        }
        for r in symbol_result.all()
    ]

    return {
        "window_days": days,
        "total_events": len(events),
        "events": events,
        "by_kind": by_kind,
        "by_symbol": by_symbol,
    }
