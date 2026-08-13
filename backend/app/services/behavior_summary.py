"""
Behavior summary from the REAL engine — replaces the retired dual engine.

The legacy `behavioral_analysis_service` recomputed behavioural patterns from raw
Trades with its own logic/thresholds, contradicting the live BehaviorEngine (which
writes RiskAlert / BehaviorEvent). Deep-review E1 (P2) flagged this as a dual
engine. This module builds the same summary shape the frontend reads, but sourced
from the single source of truth — stored `RiskAlert`s + the session risk score.

`summarize_behavior` is pure (unit-tested); `get_behavior_summary` does the queries.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.severity import rank as _sev_rank


def summarize_behavior(alerts, flagged_pnl=0.0) -> dict:
    """
    Pure: build the behavioural summary the FE reads from the real engine's alerts.

    alerts: objects with .pattern_type, .severity, .message.
    Returns patterns_detected (distinct pattern, worst severity, representative
    message) and emotional_tax (realized P&L of flagged trades — factual,
    negative = drag).

    `behavior_score` was dropped 2026-08-13 with the rest of the session risk
    score (docs/GLOBALS_DERIVATION.md). No caller read it.
    """
    by_pattern: dict = {}
    for a in alerts:
        pt = a.pattern_type
        if pt is None:
            continue
        sev = a.severity or "medium"
        cur = by_pattern.get(pt)
        if cur is None or _sev_rank(sev) > _sev_rank(cur["severity"]):
            by_pattern[pt] = {
                "pattern_type": pt,
                "name": pt,
                "severity": sev,
                "description": a.message or "",
                "is_positive": False,
            }
    patterns = sorted(by_pattern.values(), key=lambda p: -_sev_rank(p["severity"]))
    return {
        "patterns_detected": patterns,
        "emotional_tax": round(float(flagged_pnl or 0), 2),
        "top_strength": None,
        "focus_area": patterns[0]["pattern_type"] if patterns else None,
    }


async def get_behavior_summary(broker_account_id, db: AsyncSession, days: int = 30) -> dict:
    """Query the real engine's stored data for the window and summarise it."""
    from app.models.risk_alert import RiskAlert
    from app.models.completed_trade import CompletedTrade

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    alerts = (await db.execute(
        select(RiskAlert).where(
            and_(RiskAlert.broker_account_id == broker_account_id, RiskAlert.detected_at >= cutoff)
        )
    )).scalars().all()

    # emotional_tax = realized P&L of the DISTINCT trades an alert fired on (factual;
    # mirrors /behaviour-cost). Uses the trigger link the engine already stores.
    flagged_pnl = (await db.execute(
        select(func.coalesce(func.sum(CompletedTrade.realized_pnl), 0)).select_from(CompletedTrade).where(
            CompletedTrade.id.in_(
                select(RiskAlert.trigger_completed_trade_id).where(
                    and_(
                        RiskAlert.broker_account_id == broker_account_id,
                        RiskAlert.detected_at >= cutoff,
                        RiskAlert.trigger_completed_trade_id.isnot(None),
                    )
                )
            )
        )
    )).scalar() or 0

    return summarize_behavior(alerts, flagged_pnl=float(flagged_pnl))
