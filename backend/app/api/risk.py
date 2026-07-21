from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from uuid import UUID
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel

from app.core.database import get_db
from app.api.deps import get_verified_broker_account_id
from app.models.risk_alert import RiskAlert
from app.models.alert_mute import AlertMute
from app.schemas.risk_alert import RiskAlertListResponse, RiskStateResponse

router = APIRouter()

# A user may silence real-time delivery of at most this many patterns at once.
# Capped so they can't mute everything — that would defeat the app's purpose.
MAX_ACTIVE_MUTES = 3
VALID_OUTCOMES = {"stopped", "took_anyway", "not_useful"}

@router.get("/state", response_model=RiskStateResponse)
async def get_risk_state(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
):
    """Get current risk state — derived from BehaviorEngine RiskAlerts (last 4h)."""
    # MED-3: replaced deprecated RiskDetector.calculate_risk_state() with a direct
    # query. RiskDetector is still in the codebase (see docs/DEAD_CODE.md) but is
    # no longer called. /risk/state now uses the same RiskAlert table that
    # BehaviorEngine writes to, and uses its severity vocabulary (danger/caution).
    cutoff = datetime.now(timezone.utc) - timedelta(hours=4)
    result = await db.execute(
        select(RiskAlert)
        .where(
            and_(
                RiskAlert.broker_account_id == broker_account_id,
                RiskAlert.detected_at >= cutoff,
                RiskAlert.acknowledged_at.is_(None),
            )
        )
        .order_by(desc(RiskAlert.detected_at))
        .limit(5)
    )
    recent_alerts = result.scalars().all()

    if not recent_alerts:
        risk_state = "safe"
        active_patterns = []
    elif any(a.severity == "danger" for a in recent_alerts):
        risk_state = "danger"
        active_patterns = list({a.pattern_type for a in recent_alerts if a.severity == "danger"})
    else:
        risk_state = "caution"
        active_patterns = list({a.pattern_type for a in recent_alerts})

    return RiskStateResponse(
        risk_state=risk_state,
        active_patterns=active_patterns,
        recent_alerts=recent_alerts,
        recommendations=[],
    )

@router.get("/alerts", response_model=RiskAlertListResponse)
async def get_risk_alerts(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    # Clamped: largest legit window is the 90-day calendar (2160h) + slack.
    hours: int = Query(default=24, ge=1, le=2200),
    db: AsyncSession = Depends(get_db)
):
    """Get risk alerts for account"""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    result = await db.execute(
        select(RiskAlert)
        .where(
            and_(
                RiskAlert.broker_account_id == broker_account_id,
                RiskAlert.detected_at >= cutoff
            )
        )
        .order_by(desc(RiskAlert.detected_at))
    )
    alerts = result.scalars().all()

    unacknowledged = [a for a in alerts if a.acknowledged_at is None]

    return RiskAlertListResponse(
        alerts=alerts,
        total_count=len(alerts),
        unacknowledged_count=len(unacknowledged)
    )

@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
):
    """Mark alert as acknowledged"""
    try:
        alert_uuid = UUID(alert_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid alert ID format")

    result = await db.execute(
        select(RiskAlert).where(
            and_(
                RiskAlert.id == alert_uuid,
                RiskAlert.broker_account_id == broker_account_id,
            )
        )
    )
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    try:
        alert.acknowledged_at = datetime.now(timezone.utc)
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to acknowledge alert")

    return {"success": True}


@router.post("/alerts/acknowledge-all")
async def acknowledge_all_alerts(
    hours: int = Query(default=168, ge=1, le=2200),
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
):
    """Acknowledge every unacknowledged alert for the account in one call
    (replaces the frontend firing N parallel POSTs)."""
    from sqlalchemy import update
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    now = datetime.now(timezone.utc)
    result = await db.execute(
        update(RiskAlert)
        .where(and_(
            RiskAlert.broker_account_id == broker_account_id,
            RiskAlert.acknowledged_at.is_(None),
            RiskAlert.detected_at >= cutoff,
        ))
        .values(acknowledged_at=now)
    )
    await db.commit()
    return {"success": True, "acknowledged": result.rowcount}


class AlertFeedbackRequest(BaseModel):
    outcome: str  # stopped | took_anyway | not_useful


@router.post("/alerts/{alert_id}/feedback")
async def submit_alert_feedback(
    alert_id: str,
    body: AlertFeedbackRequest,
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Record what the user actually did about an alert (feedback loop). Setting an
    outcome also acknowledges the alert. Enables a real behaviour-change metric.
    """
    if body.outcome not in VALID_OUTCOMES:
        raise HTTPException(status_code=422, detail=f"outcome must be one of {sorted(VALID_OUTCOMES)}")
    try:
        alert_uuid = UUID(alert_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid alert ID format")

    result = await db.execute(
        select(RiskAlert).where(and_(
            RiskAlert.id == alert_uuid,
            RiskAlert.broker_account_id == broker_account_id,
        ))
    )
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    now = datetime.now(timezone.utc)
    alert.outcome = body.outcome
    alert.outcome_at = now
    if alert.acknowledged_at is None:
        alert.acknowledged_at = now
    await db.commit()
    return {"success": True, "outcome": body.outcome}


# ── Per-pattern mutes (suppress real-time push/toast; alert still saved) ──────

@router.get("/mutes")
async def list_mutes(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
):
    """Pattern types the user has muted from real-time delivery."""
    result = await db.execute(
        select(AlertMute.pattern_type).where(AlertMute.broker_account_id == broker_account_id)
    )
    patterns = [row[0] for row in result.all()]
    return {"muted_patterns": patterns, "max": MAX_ACTIVE_MUTES}


class MuteRequest(BaseModel):
    pattern_type: str


@router.post("/mutes")
async def add_mute(
    body: MuteRequest,
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
):
    """Mute a pattern. Enforces the MAX_ACTIVE_MUTES cap."""
    pattern = (body.pattern_type or "").strip()
    if not pattern:
        raise HTTPException(status_code=422, detail="pattern_type is required")

    existing = await db.execute(
        select(AlertMute.pattern_type).where(AlertMute.broker_account_id == broker_account_id)
    )
    muted = {row[0] for row in existing.all()}
    if pattern in muted:
        return {"success": True, "muted_patterns": sorted(muted), "max": MAX_ACTIVE_MUTES}
    if len(muted) >= MAX_ACTIVE_MUTES:
        raise HTTPException(
            status_code=409,
            detail=f"Mute limit reached ({MAX_ACTIVE_MUTES}). Unmute a pattern first.",
        )

    db.add(AlertMute(broker_account_id=broker_account_id, pattern_type=pattern))
    await db.commit()
    muted.add(pattern)
    return {"success": True, "muted_patterns": sorted(muted), "max": MAX_ACTIVE_MUTES}


@router.delete("/mutes/{pattern_type}")
async def remove_mute(
    pattern_type: str,
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
):
    """Unmute a pattern."""
    from sqlalchemy import delete as _delete
    await db.execute(
        _delete(AlertMute).where(and_(
            AlertMute.broker_account_id == broker_account_id,
            AlertMute.pattern_type == pattern_type,
        ))
    )
    await db.commit()
    return {"success": True}


@router.get("/scores")
async def get_behavior_scores(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Phase 5 behavioral scores (master 1D.9): one headline (Behavior Risk),
    four drivers (tilt / risk / discipline / strategy), with per-driver
    contributors for the Analytics detail view. Dashboard shows the band only.
    """
    from app.services.behavior_scores_service import get_today_scores
    try:
        return await get_today_scores(broker_account_id, db)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"scores computation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/alert-response-stats")
async def alert_response_stats(
    days: int = 30,
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
):
    """
    User gap #8: how do YOU respond to your alerts? Ignored (never
    acknowledged) vs acted-on per pattern - the honest dismiss-rate proxy
    until a real feedback label exists. "Revenge alerts ignored: 18" is
    itself a behavioral insight.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=min(days, 180))
    result = await db.execute(
        select(RiskAlert).where(and_(
            RiskAlert.broker_account_id == broker_account_id,
            RiskAlert.detected_at >= cutoff,
        ))
    )
    alerts = list(result.scalars().all())
    by_pattern: dict = {}
    for a in alerts:
        d = by_pattern.setdefault(
            a.pattern_type,
            {"total": 0, "acknowledged": 0, "stopped": 0, "took_anyway": 0},
        )
        d["total"] += 1
        if a.acknowledged_at is not None:
            d["acknowledged"] += 1
        # Outcome breakdown (migration 069 feedback loop) — the honest signal:
        # "you took the trade anyway N times" is stronger than "ignored".
        if a.outcome == "stopped":
            d["stopped"] += 1
        elif a.outcome == "took_anyway":
            d["took_anyway"] += 1
    rows = [
        {"pattern": p, "total": d["total"], "acknowledged": d["acknowledged"],
         "ignored": d["total"] - d["acknowledged"],
         "stopped": d["stopped"], "took_anyway": d["took_anyway"],
         "ack_rate": round(d["acknowledged"] / d["total"], 2) if d["total"] else None}
        for p, d in by_pattern.items()
    ]
    # Rank by the most damning signal first: took-anyway, then ignored.
    rows.sort(key=lambda r: (-r["took_anyway"], -r["ignored"]))
    return {"window_days": days, "patterns": rows,
            "total_ignored": sum(r["ignored"] for r in rows),
            "total_took_anyway": sum(r["took_anyway"] for r in rows),
            "total_stopped": sum(r["stopped"] for r in rows)}
