"""
ConstitutionService — Engine v2 Phase 2 (master §1C).

The constitution is the trader's own rulebook, stored on UserProfile
(single source of truth). This service owns all rule changes:

  * tighten  -> instant, any time, no friction (§1C.3)
  * loosen   -> requires override_confirmed; during market hours the change
                takes effect NEXT session (kills mid-tilt rule edits);
                logged to constitution_history and emitted as a
                constitution_override BehaviorEvent (the override itself is
                a behavioral signal)
  * every change -> constitution_history row (Q18)

Rule fields and their tighten direction:
  daily_loss_limit        lower  = tighter   (₹/day)
  daily_trade_limit       lower  = tighter   (count/day)
  max_position_size       lower  = tighter   (% capital per trade)
  cooldown_after_loss     higher = tighter   (minutes)
  max_consecutive_losses  lower  = tighter   (count)
  restricted_windows      superset = tighter (adding windows restricts more)
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_profile import UserProfile
from app.models.constitution_history import ConstitutionHistory
from app.core.trading_defaults import COLD_START_DEFAULTS

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")

RULE_FIELDS = (
    "daily_loss_limit",
    "daily_trade_limit",
    "max_position_size",
    "cooldown_after_loss",
    "max_consecutive_losses",
    "restricted_windows",
)

# direction: +1 means numerically higher = tighter, -1 means lower = tighter
_TIGHTEN_DIRECTION = {
    "daily_loss_limit": -1,
    "daily_trade_limit": -1,
    "max_position_size": -1,
    "cooldown_after_loss": +1,
    "max_consecutive_losses": -1,
}

LOCK_DAYS = 30


class LoosenRequiresOverride(Exception):
    """Raised when a loosening change is attempted without override confirmation."""
    def __init__(self, fields: List[str]):
        self.fields = fields
        super().__init__(f"Loosening {fields} requires override confirmation")


def _is_market_hours(now_utc: datetime) -> bool:
    ist = now_utc.astimezone(IST)
    if ist.weekday() >= 5:  # Sat/Sun
        return False
    minutes = ist.hour * 60 + ist.minute
    return (9 * 60 + 15) <= minutes <= (15 * 60 + 30)


def _next_session_start(now_utc: datetime) -> datetime:
    """Loosening during market hours becomes effective after today's close."""
    ist = now_utc.astimezone(IST)
    close = ist.replace(hour=15, minute=35, second=0, microsecond=0)
    return close.astimezone(timezone.utc)


def classify_change(field: str, old: Any, new: Any) -> Optional[str]:
    """Return 'tighten' | 'loosen' | None (no change)."""
    if field == "restricted_windows":
        old_set, new_set = set(old or []), set(new or [])
        if old_set == new_set:
            return None
        if new_set >= old_set:
            return "tighten"      # only additions
        return "loosen"           # any removal counts as loosening
    if old == new:
        return None
    direction = _TIGHTEN_DIRECTION[field]
    # Removing a rule entirely (value -> None) is always loosening;
    # adding a rule (None -> value) is always tightening.
    if new is None:
        return "loosen"
    if old is None:
        return "tighten"
    return "tighten" if (new - old) * direction > 0 else "loosen"


class ConstitutionService:

    # ── Read ───────────────────────────────────────────────────────────────

    @staticmethod
    async def apply_pending_if_due(profile: UserProfile, db: AsyncSession) -> bool:
        """
        Lazily apply loosening changes whose next-session effective time has
        passed. Called on every profile load path (API + engine). Returns True
        if something was applied.
        """
        pending = profile.constitution_pending
        if not pending:
            return False
        effective_at = pending.get("_effective_at")
        if not effective_at:
            profile.constitution_pending = None
            return False
        if datetime.fromisoformat(effective_at) > datetime.now(timezone.utc):
            return False

        changes = {}
        for field, new_value in pending.items():
            if field.startswith("_"):
                continue
            old_value = getattr(profile, field, None)
            setattr(profile, field, new_value)
            changes[field] = {"old": old_value, "new": new_value}

        profile.constitution_pending = None
        db.add(ConstitutionHistory(
            broker_account_id=profile.broker_account_id,
            change_type="pending_applied",
            changes=changes,
            effective_at=datetime.now(timezone.utc),
            during_market_hours=False,
            override_flag=True,
        ))
        await db.commit()
        logger.info(f"[constitution] pending changes applied for {profile.broker_account_id}: {list(changes)}")
        return True

    @staticmethod
    def snapshot(profile: UserProfile) -> Dict[str, Any]:
        return {f: getattr(profile, f, None) for f in RULE_FIELDS}

    # ── Change ─────────────────────────────────────────────────────────────

    @staticmethod
    async def apply_changes(
        profile: UserProfile,
        db: AsyncSession,
        new_values: Dict[str, Any],
        override_confirmed: bool = False,
        change_type_override: Optional[str] = None,  # "initial" | "accept" for onboarding
    ) -> Dict[str, Any]:
        """
        Validate + apply rule changes with lock semantics.

        Returns {"applied": {...}, "pending": {...}, "change_type": str}.
        Raises LoosenRequiresOverride when loosening without confirmation.
        """
        now_utc = datetime.now(timezone.utc)
        market_hours = _is_market_hours(now_utc)

        tightens: Dict[str, Any] = {}
        loosens: Dict[str, Any] = {}
        for field, new_value in new_values.items():
            if field not in RULE_FIELDS:
                continue
            kind = classify_change(field, getattr(profile, field, None), new_value)
            if kind == "tighten":
                tightens[field] = new_value
            elif kind == "loosen":
                loosens[field] = new_value

        if not tightens and not loosens:
            return {"applied": {}, "pending": {}, "change_type": "none"}

        # Onboarding flows bypass friction entirely (nothing to protect yet)
        if change_type_override in ("initial", "accept"):
            changes = {}
            for field, v in {**tightens, **loosens}.items():
                changes[field] = {"old": getattr(profile, field, None), "new": v}
                setattr(profile, field, v)
            profile.constitution_accepted_at = now_utc
            profile.constitution_locked_until = now_utc + timedelta(days=LOCK_DAYS)
            db.add(ConstitutionHistory(
                broker_account_id=profile.broker_account_id,
                change_type=change_type_override,
                changes=changes,
                effective_at=now_utc,
                during_market_hours=market_hours,
            ))
            await db.commit()
            return {"applied": {**tightens, **loosens}, "pending": {}, "change_type": change_type_override}

        if loosens and not override_confirmed:
            raise LoosenRequiresOverride(sorted(loosens))

        applied: Dict[str, Any] = {}
        pending: Dict[str, Any] = {}

        # Tightening: instant, always (§1C.3)
        if tightens:
            changes = {}
            for field, v in tightens.items():
                changes[field] = {"old": getattr(profile, field, None), "new": v}
                setattr(profile, field, v)
                applied[field] = v
            db.add(ConstitutionHistory(
                broker_account_id=profile.broker_account_id,
                change_type="tighten",
                changes=changes,
                effective_at=now_utc,
                during_market_hours=market_hours,
            ))

        # Loosening: confirmed via friction flow. During market hours the
        # change is queued for next session; otherwise immediate.
        if loosens:
            changes = {f: {"old": getattr(profile, f, None), "new": v} for f, v in loosens.items()}
            if market_hours:
                effective = _next_session_start(now_utc)
                merged = dict(profile.constitution_pending or {})
                merged.update(loosens)
                merged["_effective_at"] = effective.isoformat()
                profile.constitution_pending = merged
                pending = loosens
                db.add(ConstitutionHistory(
                    broker_account_id=profile.broker_account_id,
                    change_type="loosen",
                    changes=changes,
                    effective_at=effective,
                    during_market_hours=True,
                    override_flag=True,
                ))
            else:
                for field, v in loosens.items():
                    setattr(profile, field, v)
                    applied[field] = v
                db.add(ConstitutionHistory(
                    broker_account_id=profile.broker_account_id,
                    change_type="loosen",
                    changes=changes,
                    effective_at=now_utc,
                    during_market_hours=False,
                    override_flag=True,
                ))

        # Any modification refreshes the 30-day soft-lock horizon
        profile.constitution_locked_until = now_utc + timedelta(days=LOCK_DAYS)
        await db.commit()

        if loosens:
            logger.info(
                f"[constitution] OVERRIDE by {profile.broker_account_id}: loosened {sorted(loosens)} "
                f"(market_hours={market_hours}, pending={bool(pending)})"
            )

        return {
            "applied": applied,
            "pending": pending,
            "change_type": "loosen" if loosens else "tighten",
        }

    # ── Onboarding defaults (§1C.5 — experience drives behavior, capital drives ₹) ──

    @staticmethod
    def generate_defaults(experience_level: str, trading_capital: Optional[float]) -> Dict[str, Any]:
        matrix = {
            "beginner":     {"loss_pct": 0.02, "max_trades": 5,  "cooldown": 15, "consec": 3, "risk_pct": 1.0},
            "intermediate": {"loss_pct": 0.02, "max_trades": 10, "cooldown": 10, "consec": 4, "risk_pct": 2.0},
            "experienced":  {"loss_pct": 0.025, "max_trades": 15, "cooldown": 5, "consec": 5, "risk_pct": 2.5},
            "professional": {"loss_pct": 0.03, "max_trades": 20, "cooldown": 5, "consec": 5, "risk_pct": 3.0},
        }
        m = matrix.get(experience_level or "beginner", matrix["beginner"])
        capital = float(trading_capital or 0)
        return {
            "daily_loss_limit": round(capital * m["loss_pct"]) if capital else None,
            "daily_trade_limit": m["max_trades"],
            "cooldown_after_loss": m["cooldown"],
            "max_consecutive_losses": m["consec"],
            "max_position_size": m["risk_pct"],
            "restricted_windows": [],
        }


constitution_service = ConstitutionService()
