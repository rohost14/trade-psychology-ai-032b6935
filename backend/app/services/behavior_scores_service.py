"""
Behavior Scores + Death Spiral — Engine v2 Phase 5.

Layering (A.10): this module sits ABOVE detectors. It consumes BehaviorEvents
only — never detector internals, never EngineContext. Detectors must never
consume these scores (derived-state ban).

Driver scores (master §1D.1, user V3/V4 final):
    contribution = pattern_weight × severity_mult × (confidence/100)
    score        = Σ contributions × exp-decay(event age) → clamp 0-100
  * one aging mechanism only: decay on the running sum, no recency factor
  * no positive-behavior credits in v1 — absence of new events + decay IS
    the recovery
  * suppressed events STILL contribute (§1C.8 — suppression is notification-
    layer only; hiding evidence would corrupt the state)

Drivers map from the registry nature axis:
    emotional → tilt · risk → risk · discipline → discipline · performance → strategy
  All four are higher-is-worse (discipline here measures rule-breaking, not
  adherence — the inversion the master doc requires happens by construction).

Headline (V4): Behavior Risk = max(drivers) + w × mean(other drivers), so
"Tilt 95, rest quiet" reads ~95, never a mushy average.

Death Spiral (master §1D.2 FINAL — state-based, never raw counts):
    warning  → in-app        (behavior deteriorating)
    danger   → push          (+ capital at meaningful risk)
    critical → push+guardian (3+ independent domains + continued escalation
                              inside the compression window)
Guardian budget: hard cap per month (§1B.8) enforced at dispatch.
"""
import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.trading_defaults import COLD_START_DEFAULTS
from app.services.detector_registry import BY_NAME

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")

# Pattern weight = risk delta (already per-pattern calibrated). Imported lazily
# to avoid a circular import with behavior_engine.
_NATURE_TO_DRIVER = {
    "emotional": "tilt",
    "risk": "risk",
    "discipline": "discipline",
    "performance": "strategy",
}

# Emitted names that carry another spec's nature
_ALIAS_NATURE = {
    "daily_overtrading": "emotional",
    "death_spiral": "emotional",
    # Position-monitor patterns (Phase 6, entry-time)
    "overexposure": "risk",
    "portfolio_concentration": "risk",
    "holding_loser": "risk",
}


def _driver_for(detector: str) -> Optional[str]:
    spec = BY_NAME.get(detector)
    nature = spec.nature if spec else _ALIAS_NATURE.get(detector)
    return _NATURE_TO_DRIVER.get(nature) if nature else None


def compute_scores(events: List, now: Optional[datetime] = None) -> Dict:
    """
    Pure function: today's BehaviorEvents → driver scores + headline.
    Accepts anything with .detector, .severity, .confidence, .detected_at,
    .evidence (BehaviorEvent rows or compatible objects).
    """
    from app.services.behavior_engine import RISK_DELTAS

    now = now or datetime.now(timezone.utc)
    half_life = float(COLD_START_DEFAULTS.get("score_halflife_min", 90))
    sev_mult = {
        "info":     float(COLD_START_DEFAULTS.get("score_sev_mult_info", 0.5)),
        "caution":  float(COLD_START_DEFAULTS.get("score_sev_mult_caution", 1.0)),
        "danger":   float(COLD_START_DEFAULTS.get("score_sev_mult_danger", 1.5)),
        "critical": float(COLD_START_DEFAULTS.get("score_sev_mult_critical", 2.0)),
    }

    drivers = {"tilt": 0.0, "risk": 0.0, "discipline": 0.0, "strategy": 0.0}
    contributors: Dict[str, List] = {k: [] for k in drivers}

    for ev in events:
        driver = _driver_for(ev.detector)
        if not driver:
            continue
        weight = float(RISK_DELTAS.get(ev.detector, 10))
        mult = sev_mult.get(ev.severity, 1.0)
        conf = float(ev.confidence or 75) / 100.0
        age_min = max(0.0, (now - ev.detected_at).total_seconds() / 60) if ev.detected_at else 0.0
        decay = math.pow(0.5, age_min / half_life)
        contribution = weight * mult * conf * decay
        if contribution < 0.5:
            continue  # fully decayed — noise
        drivers[driver] += contribution
        contributors[driver].append({
            "detector": ev.detector,
            "severity": ev.severity,
            "contribution": round(contribution, 1),
            "age_min": round(age_min),
        })

    for k in drivers:
        drivers[k] = min(100.0, round(drivers[k], 1))
        contributors[k].sort(key=lambda c: -c["contribution"])

    # Headline: dominant-driver weighted (V4) — never a mean
    values = list(drivers.values())
    dominant = max(values)
    others = [v for v in values if v != dominant] or [0.0]
    w = float(COLD_START_DEFAULTS.get("headline_other_weight", 0.15))
    behavior_risk = min(100.0, round(dominant + w * (sum(others) / len(others)), 1))

    b_elev = COLD_START_DEFAULTS.get("score_band_elevated", 30)
    b_high = COLD_START_DEFAULTS.get("score_band_high", 60)
    b_crit = COLD_START_DEFAULTS.get("score_band_critical", 80)
    band = ("critical" if behavior_risk >= b_crit
            else "high" if behavior_risk >= b_high
            else "elevated" if behavior_risk >= b_elev
            else "normal")

    return {
        "behavior_risk": behavior_risk,
        "band": band,
        "drivers": drivers,
        "contributors": contributors,
        "computed_at": now.isoformat(),
    }


async def get_today_scores(broker_account_id: UUID, db: AsyncSession) -> Dict:
    """Load today's (IST) BehaviorEvents and compute scores."""
    from app.models.behavior_event import BehaviorEvent

    ist_now = datetime.now(IST)
    day_start_utc = ist_now.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
    result = await db.execute(
        select(BehaviorEvent).where(and_(
            BehaviorEvent.broker_account_id == broker_account_id,
            BehaviorEvent.detected_at >= day_start_utc,
            # Shadow (dark-launched) detector events are evidence only — excluded
            # from every user-facing score.
            BehaviorEvent.shadow.is_(False),
        ))
    )
    events = list(result.scalars().all())
    return compute_scores(events)


# ─────────────────────────────────────────────────────────────────────────────
# Death Spiral — meta-detector (L2: consumes BehaviorEvents, emits an event)
# ─────────────────────────────────────────────────────────────────────────────

_SEV_ORDER = {"info": 0, "caution": 1, "danger": 2, "critical": 3}


def evaluate_death_spiral(events: List, now: Optional[datetime] = None) -> Optional[Dict]:
    """
    Pure function over today's BehaviorEvents (suppressed included — evidence
    always counts). Returns None or:
      {"severity": "caution"|"danger"|"critical", "message", "context"}
    warning maps to caution severity for storage.
    """
    now = now or datetime.now(timezone.utc)
    min_sev = _SEV_ORDER.get(COLD_START_DEFAULTS.get("spiral_domain_min_severity", "danger"), 2)
    window_min = float(COLD_START_DEFAULTS.get("spiral_window_min", 180))
    warn_domains = int(COLD_START_DEFAULTS.get("spiral_warning_domains", 2))
    crit_domains = int(COLD_START_DEFAULTS.get("spiral_critical_domains", 3))

    # Domain trigger events: danger+ per nature-domain, spiral itself excluded
    domain_events: Dict[str, List] = {}
    for ev in events:
        if ev.detector == "death_spiral":
            continue
        if _SEV_ORDER.get(ev.severity, 0) < min_sev:
            continue
        spec = BY_NAME.get(ev.detector)
        nature = spec.nature if spec else _ALIAS_NATURE.get(ev.detector)
        if not nature:
            continue
        domain_events.setdefault(nature, []).append(ev)

    if len(domain_events) < warn_domains:
        return None

    # Time compression (master §1D.2): domains must have fired within the window
    trigger_times = [
        min(e.detected_at for e in evs if e.detected_at)
        for evs in domain_events.values()
        if any(e.detected_at for e in evs)
    ]
    latest = max((e.detected_at for evs in domain_events.values() for e in evs
                  if e.detected_at), default=None)
    compressed = (
        latest is not None and trigger_times
        and (latest - min(trigger_times)).total_seconds() / 60 <= window_min
    )

    domains = sorted(domain_events.keys())
    capital_at_risk = "risk" in domain_events
    discipline_broken = "discipline" in domain_events

    # Continued escalation (user V3: the trader who stops gets no guardian;
    # the one who overrides and keeps opening does). The breach STATE exists
    # once discipline AND risk have each fired at least once — any event after
    # that moment means the trader kept trading into a known breach.
    domain_first: Dict[str, datetime] = {
        d: min(e.detected_at for e in evs if e.detected_at)
        for d, evs in domain_events.items()
        if any(e.detected_at for e in evs)
    }
    state_established = (
        max(domain_first["discipline"], domain_first["risk"])
        if "discipline" in domain_first and "risk" in domain_first else None
    )
    continued_escalation = state_established is not None and any(
        ev.detected_at and ev.detected_at > state_established
        and ev.detector != "death_spiral"
        for ev in events
    )

    evidence = {
        "domains": domains,
        "domain_counts": {d: len(v) for d, v in domain_events.items()},
        "compressed_within_min": window_min if compressed else None,
        "continued_escalation": continued_escalation,
        "trigger_events": [
            {"detector": e.detector, "severity": e.severity,
             "at": e.detected_at.isoformat() if e.detected_at else None}
            for evs in domain_events.values() for e in evs
        ][:12],
    }

    if (len(domains) >= crit_domains and discipline_broken
            and capital_at_risk and continued_escalation and compressed):
        return {
            "severity": "critical",
            "message": (
                f"Death spiral: {len(domains)} independent systems agree — "
                f"{', '.join(domains)} all deteriorating, rules breached, and "
                f"you are still opening positions."
            ),
            "context": {**evidence, "level": "critical"},
        }
    if capital_at_risk and len(domains) >= warn_domains:
        return {
            "severity": "danger",
            "message": (
                f"Spiral forming: {' + '.join(domains)} deteriorating together "
                f"with capital at meaningful risk."
            ),
            "context": {**evidence, "level": "danger"},
        }
    return {
        "severity": "caution",
        "message": f"Behavior deteriorating across {' + '.join(domains)}.",
        "context": {**evidence, "level": "warning"},
    }


async def check_guardian_budget(broker_account_id: UUID, db: AsyncSession) -> bool:
    """
    True if a guardian message may still be sent this calendar month (§1B.8:
    a guardian pinged weekly stops reading; hard cap 1-3/month).
    """
    from app.models.risk_alert import RiskAlert

    budget = int(COLD_START_DEFAULTS.get("guardian_monthly_budget", 3))
    month_start = datetime.now(IST).replace(day=1, hour=0, minute=0, second=0,
                                            microsecond=0).astimezone(timezone.utc)
    result = await db.execute(
        select(RiskAlert).where(and_(
            RiskAlert.broker_account_id == broker_account_id,
            RiskAlert.delivered_whatsapp_at.isnot(None),
            RiskAlert.delivered_whatsapp_at >= month_start,
        ))
    )
    sent = len(result.scalars().all())
    if sent >= budget:
        logger.warning(
            f"[guardian] {broker_account_id}: monthly budget exhausted "
            f"({sent}/{budget}) — guardian send skipped"
        )
        return False
    return True
