"""Admin behavioral insights — alert engagement, top impacted users, pattern re-occurrence."""
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin.deps import get_current_admin
from app.core.database import get_db
from app.models.broker_account import BrokerAccount
from app.models.risk_alert import RiskAlert

router = APIRouter()

_HIGH_SEV = ('critical', 'high')


@router.get("/insights")
async def get_behavioral_insights(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    chart_since = datetime.now(timezone.utc) - timedelta(days=14)

    # ── Pattern frequency ─────────────────────────────────────────────────────
    pattern_rows = (await db.execute(
        select(RiskAlert.pattern_type, func.count().label("count"))
        .where(RiskAlert.created_at >= since)
        .group_by(RiskAlert.pattern_type)
        .order_by(desc("count"))
    )).all()

    # ── Severity breakdown ────────────────────────────────────────────────────
    severity_rows = (await db.execute(
        select(RiskAlert.severity, func.count().label("count"))
        .where(RiskAlert.created_at >= since)
        .group_by(RiskAlert.severity)
    )).all()

    # ── Daily volume chart (last 14 days) ─────────────────────────────────────
    daily_rows = (await db.execute(
        select(
            func.date_trunc("day", RiskAlert.created_at).label("day"),
            func.count().label("count"),
        )
        .where(RiskAlert.created_at >= chart_since)
        .group_by("day")
        .order_by("day")
    )).all()

    # ── Engagement rate per pattern ───────────────────────────────────────────
    # AVG(EXTRACT(EPOCH FROM (acknowledged_at - created_at))) = avg seconds to ack
    eng_rows = (await db.execute(
        select(
            RiskAlert.pattern_type,
            func.count().label("total"),
            func.count(RiskAlert.acknowledged_at).label("acknowledged"),
            func.avg(
                func.extract(
                    "epoch",
                    RiskAlert.acknowledged_at - RiskAlert.created_at,
                )
            ).label("avg_ack_seconds"),
        )
        .where(RiskAlert.created_at >= since)
        .group_by(RiskAlert.pattern_type)
        .order_by(desc("total"))
    )).all()

    engagement = []
    for r in eng_rows:
        total = r.total or 0
        acked = r.acknowledged or 0
        engagement.append({
            "pattern":          r.pattern_type,
            "total":            total,
            "acknowledged":     acked,
            "rate":             round(acked / total, 3) if total > 0 else 0.0,
            "avg_ack_minutes":  round(r.avg_ack_seconds / 60, 1) if r.avg_ack_seconds else None,
        })

    # ── Top impacted users ────────────────────────────────────────────────────
    top_rows = (await db.execute(
        select(
            RiskAlert.broker_account_id,
            func.count().label("alert_count"),
            func.sum(
                case((RiskAlert.severity.in_(_HIGH_SEV), 1), else_=0)
            ).label("high_severity"),
            func.max(RiskAlert.created_at).label("last_alert_at"),
        )
        .where(RiskAlert.created_at >= since)
        .group_by(RiskAlert.broker_account_id)
        .order_by(desc("alert_count"))
        .limit(10)
    )).all()

    top_account_ids = [r.broker_account_id for r in top_rows]
    acc_map: dict[str, dict] = {}
    if top_account_ids:
        acc_rows = (await db.execute(
            select(BrokerAccount.id, BrokerAccount.broker_user_id, BrokerAccount.broker_email)
            .where(BrokerAccount.id.in_(top_account_ids))
        )).all()
        acc_map = {str(a.id): {"broker_user_id": a.broker_user_id, "broker_email": a.broker_email}
                   for a in acc_rows}

    top_users = []
    for r in top_rows:
        acc = acc_map.get(str(r.broker_account_id), {})
        top_users.append({
            "account_id":    str(r.broker_account_id),
            "broker_user_id": acc.get("broker_user_id") or "—",
            "email":         acc.get("broker_email") or "—",
            "alert_count":   r.alert_count or 0,
            "high_severity": int(r.high_severity or 0),
            "last_alert_at": r.last_alert_at.isoformat() if r.last_alert_at else None,
        })

    # ── Pattern re-occurrence analysis ────────────────────────────────────────
    # Fetch all alerts in period with minimal columns; compute re-occurrence in Python.
    # For each (account, pattern): if any alert was acknowledged AND a later alert
    # for same pattern exists → that user "re-occurred".
    # This avoids an expensive self-join on potentially large tables.
    alert_rows = (await db.execute(
        select(
            RiskAlert.broker_account_id,
            RiskAlert.pattern_type,
            RiskAlert.created_at,
            RiskAlert.acknowledged_at,
        )
        .where(RiskAlert.created_at >= since)
        .order_by(RiskAlert.broker_account_id, RiskAlert.pattern_type, RiskAlert.created_at)
    )).all()

    # Group by (account_id, pattern_type)
    groups: dict[tuple, list] = defaultdict(list)
    for row in alert_rows:
        groups[(str(row.broker_account_id), row.pattern_type)].append(row)

    # For each group: find the earliest acknowledged_at, then check for later alerts
    recur_users: dict[str, set[str]] = defaultdict(set)   # pattern → set of account_ids
    base_acked:  dict[str, set[str]] = defaultdict(set)    # pattern → accounts that acked

    for (acc_id, pattern), alerts in groups.items():
        # alerts already sorted by created_at (ORDER BY above)
        first_ack_at: datetime | None = None
        for a in alerts:
            if a.acknowledged_at and first_ack_at is None:
                first_ack_at = a.acknowledged_at
                base_acked[pattern].add(acc_id)
            elif first_ack_at and a.created_at > first_ack_at:
                # Same pattern fired again after user acknowledged it
                recur_users[pattern].add(acc_id)
                break  # one re-occurrence per (account, pattern) is enough

    all_patterns = {r.pattern_type for r in alert_rows}
    recurrence = []
    for pattern in sorted(all_patterns):
        base = len(base_acked.get(pattern, set()))
        reoccurred = len(recur_users.get(pattern, set()))
        if base == 0:
            continue
        recurrence.append({
            "pattern":          pattern,
            "base_acked":       base,
            "recurrence_count": reoccurred,
            "rate":             round(reoccurred / base, 3),
        })
    recurrence.sort(key=lambda x: x["recurrence_count"], reverse=True)

    return {
        "period_days": days,
        "patterns":   [{"pattern": r.pattern_type, "count": r.count} for r in pattern_rows],
        "severity":   [{"severity": r.severity, "count": r.count} for r in severity_rows],
        "daily":      [{"date": r.day.strftime("%Y-%m-%d"), "count": r.count} for r in daily_rows],
        "engagement": engagement,
        "top_users":  top_users,
        "recurrence": recurrence,
    }
