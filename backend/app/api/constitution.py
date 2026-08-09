"""
Constitution API — Engine v2 Phase 2 (master §1C).

The trader's rulebook. Change control lives in ConstitutionService:
tighten = instant · loosen = override confirmation (+ next-session effect
during market hours) · every change audited in constitution_history.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_verified_broker_account_id
from app.core.database import get_db
from app.models.user_profile import UserProfile
from app.models.constitution_history import ConstitutionHistory
from app.models.risk_alert import RiskAlert
from app.models.completed_trade import CompletedTrade
from app.services.constitution_service import (
    ConstitutionService, LoosenRequiresOverride, RULE_FIELDS,
)
from app.services.rule_suggestion_service import build_suggestions

router = APIRouter()
logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")


class ConstitutionUpdate(BaseModel):
    daily_loss_limit: Optional[float] = Field(None, ge=0)
    daily_trade_limit: Optional[int] = Field(None, ge=1, le=200)
    max_position_size: Optional[float] = Field(None, ge=0.1, le=100)
    cooldown_after_loss: Optional[int] = Field(None, ge=0, le=240)
    max_consecutive_losses: Optional[int] = Field(None, ge=1, le=20)
    restricted_windows: Optional[List[str]] = None
    override_confirmed: bool = False
    # onboarding flows: "initial" (auto-generated) or "accept" (review screen)
    change_type: Optional[str] = None


async def _get_profile(broker_account_id: UUID, db: AsyncSession) -> UserProfile:
    result = await db.execute(
        select(UserProfile).where(UserProfile.broker_account_id == broker_account_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found — complete onboarding first")
    await ConstitutionService.apply_pending_if_due(profile, db)
    return profile


@router.get("/")
async def get_constitution(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
):
    """Current rules + lock state + pending changes."""
    profile = await _get_profile(broker_account_id, db)
    return {
        "rules": ConstitutionService.snapshot(profile),
        "accepted_at": profile.constitution_accepted_at.isoformat() if profile.constitution_accepted_at else None,
        "locked_until": profile.constitution_locked_until.isoformat() if profile.constitution_locked_until else None,
        "pending": profile.constitution_pending,
    }


@router.put("/")
async def update_constitution(
    payload: ConstitutionUpdate,
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Apply rule changes. Tightening applies instantly. Loosening without
    override_confirmed returns 409 with the fields that need confirmation;
    with confirmation, it applies (or queues for next session during market
    hours).
    """
    profile = await _get_profile(broker_account_id, db)
    new_values = {
        f: getattr(payload, f)
        for f in RULE_FIELDS
        if getattr(payload, f, None) is not None or f == "restricted_windows" and payload.restricted_windows is not None
    }
    # Explicit None handling: pydantic None means "not provided" here — rule
    # REMOVAL goes through restricted PUT with explicit override in a later
    # iteration; out of scope for Phase 2 backend.
    try:
        outcome = await ConstitutionService.apply_changes(
            profile, db, new_values,
            override_confirmed=payload.override_confirmed,
            change_type_override=payload.change_type,
        )
    except LoosenRequiresOverride as e:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "override_required",
                "loosening_fields": e.fields,
                "message": (
                    "These changes relax your own rules. Confirm the override to proceed. "
                    "Changes made during market hours take effect next session."
                ),
            },
        )
    return {"success": True, **outcome, "rules": ConstitutionService.snapshot(profile)}


@router.get("/suggestions")
async def get_rule_suggestions(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Rules derived from the user's own completed trades (G3).

    Read-only and never auto-applied: accepting a suggestion is an ordinary PUT
    to this router, so the same change control applies. Only tightening is ever
    proposed — see rule_suggestion_service for why.
    """
    profile = await _get_profile(broker_account_id, db)
    return await build_suggestions(
        broker_account_id, db, ConstitutionService.snapshot(profile)
    )


@router.post("/generate")
async def generate_recommended(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
):
    """Recommended constitution from profile (onboarding step 2 — §1C.5)."""
    profile = await _get_profile(broker_account_id, db)
    return {
        "recommended": ConstitutionService.generate_defaults(
            profile.experience_level, profile.trading_capital
        ),
        "based_on": {
            "experience_level": profile.experience_level,
            "trading_capital": profile.trading_capital,
        },
    }


# ---------------------------------------------------------------------------
# Effective thresholds
# ---------------------------------------------------------------------------

#: Declared rule -> the threshold key the engine actually enforces for it.
#: Two names for one concept exist in the codebase (daily_trade_limit on the
#: profile, daily_trades in the status payload); this map is the single place
#: that relationship is written down.
_RULE_TO_THRESHOLD = {
    "daily_trade_limit":      "daily_trade_limit",
    "cooldown_after_loss":    "revenge_window_min",
    "daily_loss_limit":       "daily_loss_limit",
    "max_position_size":      "max_position_size",
    "max_consecutive_losses": "max_consecutive_losses",
}

#: Thresholds the engine enforces that no rule can set. Surfaced so the rules
#: page can stop implying these limits do not exist.
_UNGOVERNED = (
    "burst_trades_per_30min_caution",
    "burst_trades_per_30min_danger",
    "consecutive_loss_caution",
    "consecutive_loss_danger",
    "revenge_window_caution_min",
    "daily_trade_danger",
)


@router.get("/effective")
async def get_effective_thresholds(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
):
    """
    What the engine ACTUALLY enforces, and where each number came from.

    Why this exists: a declared rule is applied only when it is more
    restrictive than the threshold already in force. Set daily_trade_limit to
    50 while your own trading averages 6 and the engine enforces 6 -- correct
    behaviour, deliberately chosen so a stale value cannot silently disable
    alerts, but until now the rules page displayed 50 and nothing said
    otherwise. The page was reporting a rule that was not the one being
    applied.

    `source` per rule:
      declared  the user's value is the one in force
      learned   their own trading produced a tighter value, which wins
      default   no rule set; a research default is in force
    """
    from app.core.trading_defaults import get_thresholds

    profile = await _get_profile(broker_account_id, db)
    declared = ConstitutionService.snapshot(profile)
    effective = get_thresholds(profile)

    has_baseline = bool((getattr(profile, "detected_patterns", None) or {}).get("baseline"))

    rules: Dict[str, Any] = {}
    for rule, key in _RULE_TO_THRESHOLD.items():
        want = declared.get(rule)
        got = effective.get(key)

        if want is None:
            source = "default" if got is not None else "unset"
        elif got is None or want == got:
            source = "declared"
        else:
            # The engine resolved to something other than what was declared,
            # which by construction means it resolved to something tighter.
            source = "learned" if has_baseline else "declared"

        rules[rule] = {
            "declared": want,
            "effective": got,
            "source": source,
            "overridden": source == "learned",
        }

    return {
        "rules": rules,
        # Enforced, and not settable by anyone. Named so the page can show them
        # as limits that exist rather than leaving them invisible.
        "ungoverned": {k: effective.get(k) for k in _UNGOVERNED if effective.get(k) is not None},
        "has_baseline": has_baseline,
    }


@router.get("/status")
async def constitution_status(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
):
    """Today's live usage vs each rule — the My Rules progress section."""
    profile = await _get_profile(broker_account_id, db)
    rules = ConstitutionService.snapshot(profile)

    ist_now = datetime.now(IST)
    day_start_utc = ist_now.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)

    result = await db.execute(
        select(CompletedTrade)
        .where(and_(
            CompletedTrade.broker_account_id == broker_account_id,
            CompletedTrade.exit_time >= day_start_utc,
        ))
        .order_by(CompletedTrade.exit_time.asc())
    )
    trades = list(result.scalars().all())

    session_pnl = sum(float(t.realized_pnl or 0) for t in trades)
    loss = -session_pnl if session_pnl < 0 else 0.0
    streak = 0
    for t in reversed(trades):
        if float(t.realized_pnl or 0) < 0:
            streak += 1
        else:
            break
    last_loss = next((t for t in reversed(trades) if float(t.realized_pnl or 0) < 0), None)
    cooldown_active = False
    cooldown_remaining_min = 0
    if last_loss and rules.get("cooldown_after_loss") and last_loss.exit_time:
        elapsed = (datetime.now(timezone.utc) - last_loss.exit_time).total_seconds() / 60
        remaining = float(rules["cooldown_after_loss"]) - elapsed
        if remaining > 0:
            cooldown_active = True
            cooldown_remaining_min = round(remaining, 1)

    def usage(rule_key, current, limit):
        return {
            "rule": rule_key, "current": current, "limit": limit,
            "ratio": round(current / limit, 2) if limit else None,
        }

    return {
        "session_date": ist_now.date().isoformat(),
        "status": [
            usage("daily_loss", round(loss, 2), rules.get("daily_loss_limit")),
            usage("daily_trades", len(trades), rules.get("daily_trade_limit")),
            usage("max_consecutive_losses", streak, rules.get("max_consecutive_losses")),
            {"rule": "cooldown", "active": cooldown_active,
             "remaining_min": cooldown_remaining_min,
             "limit_min": rules.get("cooldown_after_loss")},
            {"rule": "restricted_windows", "windows": rules.get("restricted_windows") or []},
        ],
    }


@router.get("/history")
async def constitution_history(
    limit: int = 50,
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ConstitutionHistory)
        .where(ConstitutionHistory.broker_account_id == broker_account_id)
        .order_by(desc(ConstitutionHistory.changed_at))
        .limit(min(limit, 200))
    )
    rows = result.scalars().all()
    return {"history": [
        {
            "changed_at": r.changed_at.isoformat() if r.changed_at else None,
            "change_type": r.change_type,
            "changes": r.changes,
            "effective_at": r.effective_at.isoformat() if r.effective_at else None,
            "during_market_hours": r.during_market_hours,
            "override": r.override_flag,
        } for r in rows
    ]}


@router.get("/violations")
async def constitution_violations(
    days: int = 30,
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
):
    """Constitution violations: today + rolling window count (My Rules section 3)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=min(days, 365))
    result = await db.execute(
        select(RiskAlert)
        .where(and_(
            RiskAlert.broker_account_id == broker_account_id,
            RiskAlert.pattern_type == "constitution_violation",
            RiskAlert.detected_at >= cutoff,
        ))
        .order_by(desc(RiskAlert.detected_at))
    )
    alerts = list(result.scalars().all())
    ist_today = datetime.now(IST).date()
    today = [a for a in alerts
             if a.detected_at and a.detected_at.astimezone(IST).date() == ist_today]
    return {
        "window_days": days,
        "total": len(alerts),
        "today": [
            {"rule": (a.details or {}).get("rule"), "severity": a.severity,
             "message": a.message,
             "detected_at": a.detected_at.isoformat() if a.detected_at else None}
            for a in today
        ],
        "by_rule": {
            rule: sum(1 for a in alerts if (a.details or {}).get("rule") == rule)
            for rule in {(a.details or {}).get("rule") for a in alerts if a.details}
        },
    }
