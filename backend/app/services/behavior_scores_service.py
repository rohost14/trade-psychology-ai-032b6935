"""
Death Spiral + guardian budget — Engine v2 Phase 5.

Layering (A.10): this module sits ABOVE detectors. It consumes BehaviorEvents
only — never detector internals, never EngineContext.

Death Spiral (master §1D.2 FINAL — state-based, never raw counts):
    warning  → in-app        (behavior deteriorating)
    danger   → push          (+ capital at meaningful risk)
    critical → push+guardian (3+ independent domains + continued escalation
                              inside the compression window)
Guardian budget: hard cap per month (§1B.8) enforced at dispatch.

The driver scores and the Behavior Risk headline that this module used to own
were removed 2026-08-13 (docs/GLOBALS_DERIVATION.md). Death spiral is the part
that fires alerts, and it never depended on them.
"""
import logging
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

# Emitted names that carry another spec's nature
_ALIAS_NATURE = {
    "daily_overtrading": "emotional",
    "death_spiral": "emotional",
    # Position-monitor patterns (Phase 6, entry-time)
    "overexposure": "risk",
    "portfolio_concentration": "risk",
    "holding_loser": "risk",
}


# `compute_scores` / `get_today_scores` — the four driver scores, the
# dominant-weighted headline and the 30/60/80 band — were removed 2026-08-13.
# `docs/GLOBALS_DERIVATION.md` has the measurement: the weights did not rank
# with measured cost, the severity multiplier had the wrong sign (danger
# measured −10 lift against caution's +1), and the 90-minute half-life outlived
# the signal by roughly 3×. Nothing rendered the result.
#
# Death spiral below is UNCHANGED and still fires. It reads severity and nature
# domain off the events themselves; it never read the scores.


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
        # Named so the message can quote it. The composite absorbs the alerts it
        # summarises, so it is frequently the only thing the trader sees — it has
        # to carry the specifics rather than gesture at them.
        "event_count": sum(len(v) for v in domain_events.values()),
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
                f"Spiral forming: {' + '.join(domains)} deteriorating together, "
                f"{evidence.get('event_count', 0)} signals today, "
                f"with capital at meaningful risk."
            ),
            "context": {**evidence, "level": "danger"},
        }
    return {
        "severity": "caution",
        "message": (
            f"{' + '.join(domains)} all deteriorating — "
            f"{evidence.get('event_count', 0)} signals across "
            f"{len(domains)} areas of your trading today."
        ),
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
