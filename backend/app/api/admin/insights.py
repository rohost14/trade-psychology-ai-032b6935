"""Admin behavioral insights — aggregate pattern data across all users."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from datetime import datetime, timezone, timedelta

from app.core.database import get_db
from app.api.admin.deps import get_current_admin
from app.models.risk_alert import RiskAlert

router = APIRouter()


@router.get("/insights")
async def get_behavioral_insights(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    since = datetime.now(timezone.utc) - timedelta(days=days)

    # Pattern frequency
    pattern_counts = (await db.execute(
        select(RiskAlert.pattern_type, func.count().label("count"))
        .where(RiskAlert.created_at >= since)
        .group_by(RiskAlert.pattern_type)
        .order_by(desc("count"))
    )).all()

    # Severity breakdown
    severity_counts = (await db.execute(
        select(RiskAlert.severity, func.count().label("count"))
        .where(RiskAlert.created_at >= since)
        .group_by(RiskAlert.severity)
    )).all()

    # Alerts per day (last 14 days for chart)
    chart_since = datetime.now(timezone.utc) - timedelta(days=14)
    daily_counts = (await db.execute(
        select(
            func.date_trunc("day", RiskAlert.created_at).label("day"),
            func.count().label("count"),
        )
        .where(RiskAlert.created_at >= chart_since)
        .group_by("day")
        .order_by("day")
    )).all()

    return {
        "period_days": days,
        "patterns": [{"pattern": r.pattern_type, "count": r.count} for r in pattern_counts],
        "severity": [{"severity": r.severity, "count": r.count} for r in severity_counts],
        "daily": [
            {"date": r.day.strftime("%Y-%m-%d"), "count": r.count}
            for r in daily_counts
        ],
    }
