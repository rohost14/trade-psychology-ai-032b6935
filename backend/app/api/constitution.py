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
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_verified_broker_account_id
from app.core.database import get_db
from app.models.user_profile import UserProfile
from app.models.constitution_history import ConstitutionHistory
from app.models.risk_alert import RiskAlert
from app.core import session_facts
from app.core.risk_quantities import quantities_for_trade
from app.services.constitution_service import (
    ConstitutionService, LoosenRequiresOverride, RULE_FIELDS,
)
from app.services.rule_suggestion_service import build_suggestions

router = APIRouter()
logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")


class ConstitutionUpdate(BaseModel):
    daily_loss_limit: Optional[float] = Field(None, ge=0)
    per_trade_loss_limit: Optional[float] = Field(None, ge=0)
    daily_trade_limit: Optional[int] = Field(None, ge=1, le=200)
    max_position_size: Optional[float] = Field(None, ge=0.1, le=100)
    max_consecutive_losses: Optional[int] = Field(None, ge=1, le=20)
    # Added 2026-09-02. THIS FIELD'S ABSENCE WAS THE BUG: `sl_percent_options`
    # is a RULE_FIELD, `snapshot` returns it, `classify_change` ranks it and the
    # engine reads it - but the only endpoint that routes through the
    # tighten/loosen gate had no field for it, so pydantic dropped the key and
    # the rule could be neither set nor cleared here. Bounds copied from the
    # profile endpoint's existing `validate_percent` (0.1-100), which is where
    # the value used to be set; no new range is invented.
    sl_percent_options: Optional[float] = Field(None, ge=0.1, le=100)
    restricted_windows: Optional[List[str]] = None
    override_confirmed: bool = False

    @field_validator("restricted_windows")
    @classmethod
    def validate_windows(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """
        A window must be "HH:MM-HH:MM" IST, or it enforces NOTHING.

        Both enforcement sites - `BehaviorEngine._detect_constitution_violation`
        and `_check_entry_rules` - parse with `split("-")` / `split(":")` inside
        a try, and `continue` past anything that raises. So an unparseable
        window is stored, listed back to the trader as one of their rules, and
        silently skipped every time it should fire. That is worse than having no
        rule: the page promises a protection that does not exist. Rejecting it
        at the boundary is the only place the trader can be told.
        """
        if v is None:
            return v
        clean: List[str] = []
        for raw in v:
            w = (raw or "").strip()
            if not w:
                continue                      # a blank row is not a window
            try:
                start_s, end_s = w.split("-")
                sh, sm = map(int, start_s.strip().split(":"))
                eh, em = map(int, end_s.strip().split(":"))
            except (ValueError, AttributeError):
                raise ValueError(
                    f"'{raw}' is not a time window. Use HH:MM-HH:MM, "
                    f"for example 13:00-14:00."
                )
            if not (0 <= sh < 24 and 0 <= eh < 24 and 0 <= sm < 60 and 0 <= em < 60):
                raise ValueError(f"'{raw}' is not a real time of day.")
            if sh * 60 + sm > eh * 60 + em:
                raise ValueError(f"'{raw}' ends before it starts.")
            clean.append(f"{sh:02d}:{sm:02d}-{eh:02d}:{em:02d}")
        # Normalised and de-duplicated, order kept. Normalising matters for
        # change detection: "9:15-9:30" and "09:15-09:30" are one window, and
        # `classify_change` compares them as SETS.
        return list(dict.fromkeys(clean))
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
    # OMITTED vs EXPLICITLY NULL. 2026-09-02.
    #
    # This used to keep only `is not None` values, so an explicit
    # `{"max_position_size": null}` was indistinguishable from not sending the
    # field at all - and a rule could be set or changed but never REMOVED. The
    # note that stood here scoped removal out of Phase 2; this is that later
    # iteration.
    #
    # `model_fields_set` is the distinction pydantic already carries: a key the
    # client actually sent is in it, an omitted one is not. So a null that was
    # SENT becomes a removal, and a field that was never mentioned is left
    # alone - which is what stops an unrelated save from clearing every rule.
    #
    # Nothing else is needed. `classify_change` has always returned "loosen"
    # for value -> None, so a removal routes through the same override
    # confirmation and next-session queue as any other relaxation, and writes
    # the same ConstitutionHistory row.
    sent = payload.model_fields_set
    new_values = {
        f: getattr(payload, f)
        for f in RULE_FIELDS
        if f in sent
    }
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


class GenerateRequest(BaseModel):
    #: Capital to base the SUGGESTED money rules on, when it is not yet saved.
    #:
    #: The onboarding wizard collects capital on the same screen that shows the
    #: suggestions, and it is not persisted until that step is submitted — so
    #: without this the server could only ever answer "no suggestion", and the
    #: opt-in checkbox for the daily loss limit could never be ticked during
    #: onboarding. Defaults to the stored value, so `POST {}` is unchanged.
    #:
    #: This passes an argument `generate_defaults` already takes. It does not
    #: change what is suggested, and it still returns the money rules as null —
    #: suggestions, not rules.
    trading_capital: Optional[float] = None


@router.post("/generate")
async def generate_recommended(
    body: Optional[GenerateRequest] = None,
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
):
    """Recommended constitution from profile (onboarding step 2 — §1C.5)."""
    profile = await _get_profile(broker_account_id, db)
    capital = (body.trading_capital if body and body.trading_capital is not None
               else profile.trading_capital)
    return {
        "recommended": ConstitutionService.generate_defaults(
            profile.experience_level, capital
        ),
        "based_on": {
            "experience_level": profile.experience_level,
            "trading_capital": capital,
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
    "daily_loss_limit":       "daily_loss_limit",
    "per_trade_loss_limit":   "per_trade_loss_limit",
    "max_position_size":      "max_position_size",
    "max_consecutive_losses": "max_consecutive_losses",
    # Added 2026-09-02. `sl_percent_options` has always been a RULE_FIELD and
    # has always resolved (Source.FACT when declared, absent otherwise), but it
    # was missing here, so the one page that reports what is enforced never
    # mentioned it. Its threshold key is None when undeclared, which this
    # endpoint already renders as "unset" - no default is implied.
    "sl_percent_options":     "sl_percent_options",
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

    # My Rules shows the trader their own limits against today. The numbers come
    # from the canonical session facts so this page cannot disagree with the
    # alert that fires on the same rule - it used to run its own query from IST
    # midnight and count its own streak.
    trades = await session_facts.load_session_trades(
        db, broker_account_id, ist_now.date()
    )
    facts = session_facts.derive(trades)

    session_pnl = float(facts.pnl)
    loss = -session_pnl if session_pnl < 0 else 0.0
    streak = facts.consecutive_losses
    # A declared-cooldown countdown was reported here until 2026-09-02.
    # `cooldown_after_loss` is no longer a user rule, so there is no declared
    # limit to count down against and nothing is invented in its place.

    def usage(rule_key, current, limit):
        """A rule the session SPENDS DOWN. `current` climbs and cannot be undone."""
        return {
            "rule": rule_key, "current": current, "limit": limit,
            "kind": "cumulative",
            "ratio": round(current / limit, 2) if limit else None,
        }

    def peak(rule_key, current, limit):
        """
        A PER-TRADE rule, reported as the session's worst single instance.

        NOT A BUDGET, and the distinction is the whole reason this second
        shape exists. A daily loss limit is consumed: lose 8,455 of 25,000 and
        16,545 remain. A per-trade limit is not consumed by anything - the
        worst trade so far reaching 67% of the line leaves the NEXT trade its
        full allowance. Reporting these through `usage` would put them behind a
        progress bar that says "you have 33% left", which is false.

        `kind` is what the client reads to decide that, so the semantics travel
        with the number instead of living in a hardcoded list on the page.
        """
        return {
            "rule": rule_key, "current": current, "limit": limit,
            "kind": "peak",
            "ratio": round(current / limit, 2) if limit and current is not None else None,
        }

    # ── Largest capital at risk today ─────────────────────────────────────
    #
    # REPORTED ONLY WHEN EVERY TRADE OF THE SESSION COULD BE SIZED. The risk
    # layer is allowed to abstain - `usable_for_capital_rules` is False for,
    # among others, short equity - and on the real book it abstains on 21.3% of
    # 5,011 trades, with 46.2% OF SESSIONS containing at least one such trade.
    #
    # A maximum taken over a subset is not the maximum. On those sessions the
    # page would state "your largest position today was 7.6%" while the actual
    # largest was a trade nobody sized, which is the wrong-confident-answer
    # failure this codebase refuses. So: complete coverage or no number. The
    # rule row still renders, with its limit and no usage.
    #
    # This matches what the ALERT does - `max_trade_risk` judges only trades it
    # can size - so the two cannot disagree about the same trade.
    largest_risk_pct = None
    risk_limit = rules.get("max_position_size")
    capital = getattr(profile, "trading_capital", None)
    if risk_limit and capital:
        pcts, complete = [], True
        for t in trades:
            rq = quantities_for_trade(t, margin=None)
            if rq.usable_for_capital_rules:
                pcts.append(float(rq.capital_requirement.amount) / float(capital) * 100)
            else:
                complete = False
        if pcts and complete:
            largest_risk_pct = round(max(pcts), 2)

    worst = facts.worst_trade_pnl

    return {
        "session_date": ist_now.date().isoformat(),
        "status": [
            usage("daily_loss", round(loss, 2), rules.get("daily_loss_limit")),
            usage("daily_trades", facts.trades, rules.get("daily_trade_limit")),
            usage("max_consecutive_losses", streak, rules.get("max_consecutive_losses")),
            # Worst single trade of the session, as a positive rupee figure so
            # it reads against the limit the same way `daily_loss` does.
            peak("per_trade_loss", round(abs(float(worst)), 2) if worst else 0.0,
                 rules.get("per_trade_loss_limit")),
            peak("max_trade_risk", largest_risk_pct, risk_limit),
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
