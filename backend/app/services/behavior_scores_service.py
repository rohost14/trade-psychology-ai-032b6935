"""
Guardian budget — Engine v2 Phase 5.

All that remains of this module. Two things it used to own have gone, in this
order:

  * the four driver scores and the Behavior Risk headline, removed 2026-08-13
    (docs/GLOBALS_DERIVATION.md): the weights did not rank with measured cost,
    the severity multiplier had the wrong sign, and nothing rendered the result;
  * `evaluate_death_spiral`, removed 2026-09-02 - see the note below it.

`check_guardian_budget` is unrelated to both and is unchanged: a hard cap on
guardian messages per calendar month (§1B.8 - a guardian pinged weekly stops
reading), enforced at dispatch for every guardian-eligible alert.
"""
import logging
from datetime import datetime, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.trading_defaults import COLD_START_DEFAULTS

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")

# ─────────────────────────────────────────────────────────────────────────────
# `evaluate_death_spiral` and `_ALIAS_NATURE` were REMOVED 2026-09-02.
#
# WHY
#
# The meta-detector claimed a state: "several independent behavioural domains
# are deteriorating together in one session". Measured against 203 real
# sessions, twice, it was a summary of alerts the trader had already been sent.
#
#   NOT DISTINCT. At `danger` - 100% of firings without declared rules - it was
#   set-identical to "a danger emotional alert and a danger risk alert happened
#   today". With one declared rule (daily_loss_limit), `constitution_violation`
#   appeared in 100% of 79 firings, and in 61% of them BOTH domains were
#   carried by `constitution_violation` and `session_meltdown`, which read the
#   SAME declared daily_loss_limit. "Two independent domains" was one limit,
#   breached, reported twice.
#
#   NOT ADDITIVE. 69% of danger firings came after a danger alert already
#   delivered; only 15% were incremental (fired alone with trades still to
#   come). At `caution`, 0% were.
#
#   NOT A SPIRAL. 38.9% of sessions with one declared rule - 79 of 203.
#
#   NOT SEQUENTIAL ENOUGH TO SAVE IT. The `danger` and `caution` tiers contain
#   no timestamp at all and were order-independent under thousands of
#   reorderings - together they are 91% of firings. `critical` does read time,
#   and its 180-minute window did discriminate on the live path: 7 of 79 firing
#   sessions escalated danger -> critical. That tier was real and rare, and it
#   did not make the other 91% any less redundant.
#
# One domain (`performance`) could never contribute at all: both its detectors
# hardcode `severity="info"` and the gate is >= danger.
#
# NOTHING REPLACED IT. Every constituent alert still fires, unchanged, and each
# was already notifiable on its own. `constitution_violation` in particular is
# notification_level 4 and guardian-eligible without this.
#
# Historical rows are KEPT. `death_spiral` RiskAlerts and BehaviorEvents remain
# in the database and still render, via `formatPatternName` in
# `src/contexts/AlertContext.tsx`. They are history, not a live rule.
#
# Evidence: docs/patterns/A1-death_spiral/
# Enforced by: backend/tests/test_death_spiral_retired.py
# ─────────────────────────────────────────────────────────────────────────────


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
