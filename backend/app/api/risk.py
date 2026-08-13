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
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# A user may silence real-time delivery of at most this many patterns at once.
# Capped so they can't mute everything — that would defeat the app's purpose.
MAX_ACTIVE_MUTES = 3
# What a trader can say about an alert. `planned` (migration 079) is the one
# that separates "your detection is wrong" from "I meant to do that" — the same
# tap, a completely different statement, and the difference between a detector
# with a precision problem and one that is simply not telling this trader
# anything new.
#
# Requires migration 079: 069 added a CHECK constraint listing the first three,
# so an INSERT of 'planned' fails at the database until it is applied.
VALID_OUTCOMES = {"stopped", "took_anyway", "not_useful", "planned"}

@router.get("/patterns")
async def get_pattern_catalogue():
    """
    Every behaviour pattern this system can raise, with what it observes and why.

    One catalogue, served from the detector registry, so the copy cannot drift
    from the pattern name again — which is exactly what happened when it lived
    in three frontend `Record` maps keyed on names engine v2 had renamed.

    Unauthenticated and cacheable: it is the same for every user, it is the
    glossary, and it is the honest answer to "why did I get this alert".
    """
    from app.core.severity import SEVERITY_ORDER
    from app.services.detector_registry import (
        ALIASES, BY_NAME, all_pattern_types, pattern_copy,
    )

    patterns = []
    for name in all_pattern_types():
        copy = pattern_copy(name)
        spec = BY_NAME.get(name)
        patterns.append({
            "pattern_type": name,
            "label": copy.label,
            "observes": copy.observes,
            "explanation": copy.explanation,
            "nature": spec.nature if spec else None,
            "disposition": spec.disposition if spec else "alerting",
            "trigger": spec.trigger if spec else "position",
            "guardian_eligible": spec.guardian_eligible if spec else False,
            "version": spec.version if spec else ALIASES.get(name),
        })
    patterns.sort(key=lambda p: p["label"])
    return {"patterns": patterns, "count": len(patterns),
            "severity_order": list(SEVERITY_ORDER)}


@router.get("/patterns/{pattern_type}/my-record")
async def get_pattern_my_record(
    pattern_type: str,
    days: int = Query(180, ge=7, le=1825),
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
):
    """
    The trader's OWN history with one pattern: when it fired, what it cost.

    This replaces what used to sit in the alert panel — a paragraph of precise,
    unsourced population statistics ("win rate on the 4th trade after 3 losses
    is typically below 30%") written to sound like measurement. Nobody measured
    it. The trader's own record is both true and more persuasive, and it is the
    thing no competitor can show them.

    Same discipline as /api/my-record:
      * Facts only. Realised P&L of the trades this pattern actually flagged,
        joined through trigger_completed_trade_id. Never a counterfactual —
        we do not claim what would have happened had they not traded.
      * P&L stays RAW, per the standing project rule.
      * Sample-gated and honest about it. A two-trade history is reported as
        insufficient rather than dressed up as a finding.
    """
    from app.api.my_record import MIN_SAMPLE, _stats
    from app.models.completed_trade import CompletedTrade

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    alerts = (await db.execute(
        select(RiskAlert).where(and_(
            RiskAlert.broker_account_id == broker_account_id,
            RiskAlert.pattern_type == pattern_type,
            RiskAlert.detected_at >= cutoff,
        )).order_by(desc(RiskAlert.detected_at))
    )).scalars().all()

    trade_ids = [a.trigger_completed_trade_id for a in alerts
                 if a.trigger_completed_trade_id is not None]

    trades = []
    if trade_ids:
        trades = list((await db.execute(
            select(CompletedTrade).where(and_(
                CompletedTrade.id.in_(trade_ids),
                CompletedTrade.realized_pnl.isnot(None),
            ))
        )).scalars().all())

    stats = _stats(trades)
    last_seen = alerts[0].detected_at if alerts else None

    return {
        "pattern_type": pattern_type,
        "window_days": days,
        "times_fired": len(alerts),
        "last_seen": last_seen.isoformat() if last_seen else None,
        # Alerts raised while a position was still open have no completed trade
        # until it closes, so the flagged-trade count trails times_fired. Stated
        # rather than hidden — a silent gap between the two numbers reads as a bug.
        "trades_measured": stats["trades"],
        **{k: v for k, v in stats.items() if k != "trades"},
        "min_sample": MIN_SAMPLE,
    }


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

    # Severity has four values. This read `any(severity == "danger")` and fell
    # to "caution" otherwise — so a session whose only unacknowledged alert was
    # CRITICAL reported as caution, the mildest state above safe, on the
    # endpoint that drives the dashboard. `worst` asks the shared vocabulary
    # instead of comparing to a literal.
    from app.core.severity import worst as _worst_severity

    if not recent_alerts:
        risk_state = "safe"
        active_patterns = []
    else:
        top = _worst_severity(a.severity for a in recent_alerts)
        if top in ("critical", "danger"):
            risk_state = top
            active_patterns = list({a.pattern_type for a in recent_alerts if a.severity == top})
        else:
            risk_state = "caution"
            active_patterns = list({a.pattern_type for a in recent_alerts})

    # Resolve the user's EFFECTIVE daily limits from the same source the engine's
    # constitution / session-meltdown detectors use, so the dashboard hero and the
    # alert copy agree on ONE limit (was: hero fell back to a hardcoded 25,000 while
    # the constitution alert used the real profile limit).
    daily_loss_limit = None
    daily_trade_limit = None
    try:
        from app.models.user_profile import UserProfile
        from app.core.trading_defaults import get_thresholds
        prof_result = await db.execute(
            select(UserProfile).where(UserProfile.broker_account_id == broker_account_id)
        )
        profile = prof_result.scalar_one_or_none()
        th = get_thresholds(profile)
        loss_limit = th.get("daily_loss_limit")
        if not loss_limit or loss_limit <= 0:
            cap = th.get("trading_capital")
            loss_limit = float(cap) * 0.05 if cap and float(cap) > 0 else None
        daily_loss_limit = float(loss_limit) if loss_limit else None
        tl = th.get("daily_trade_limit")
        daily_trade_limit = int(tl) if tl else None
    except Exception as _lim_err:  # never let limit resolution break the risk state
        logger.warning(f"[risk/state] limit resolution failed: {_lim_err}")

    return RiskStateResponse(
        risk_state=risk_state,
        active_patterns=active_patterns,
        recent_alerts=recent_alerts,
        recommendations=[],
        daily_loss_limit=daily_loss_limit,
        daily_trade_limit=daily_trade_limit,
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


# GET /scores (Behavior Risk headline + four driver scores) was removed
# 2026-08-13 — docs/GLOBALS_DERIVATION.md. Its only two callers were an
# unmounted badge and an archived card, and the year of replayed trades did not
# support the weights, the severity multiplier or the decay constant behind it.


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
            {"total": 0, "acknowledged": 0, "stopped": 0, "took_anyway": 0,
             "not_useful": 0, "planned": 0},
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
        elif a.outcome == "planned":
            # Detection correct, concern misplaced. Deliberately NOT folded into
            # not_useful: one says we were wrong, the other says we were right
            # and this trader already knew.
            d["planned"] += 1
        elif a.outcome == "not_useful":
            # The only signal we have that the ENGINE was wrong rather than the
            # trader. It was accepted, stored, and read by nothing — so every
            # other number here measured the user's compliance and none
            # measured our accuracy.
            d["not_useful"] += 1
    rows = [
        {"pattern": p, "total": d["total"], "acknowledged": d["acknowledged"],
         "ignored": d["total"] - d["acknowledged"],
         "stopped": d["stopped"], "took_anyway": d["took_anyway"],
         "not_useful": d["not_useful"], "planned": d["planned"],
         # Share of alerts the trader marked as not useful. This is the closest
         # thing to a false-positive rate the product has.
         "not_useful_rate": round(d["not_useful"] / d["total"], 2) if d["total"] else None,
         "ack_rate": round(d["acknowledged"] / d["total"], 2) if d["total"] else None}
        for p, d in by_pattern.items()
    ]
    # Rank by the most damning signal first: took-anyway, then ignored.
    rows.sort(key=lambda r: (-r["took_anyway"], -r["ignored"]))
    return {"window_days": days, "patterns": rows,
            "total_ignored": sum(r["ignored"] for r in rows),
            "total_took_anyway": sum(r["took_anyway"] for r in rows),
            "total_stopped": sum(r["stopped"] for r in rows),
            "total_not_useful": sum(r["not_useful"] for r in rows),
            "total_planned": sum(r["planned"] for r in rows)}
