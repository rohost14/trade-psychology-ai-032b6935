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

_SEV_RANK = {"info": 0, "caution": 1, "medium": 1, "danger": 2, "high": 2, "critical": 3}


def summarize_behavior(alerts, session_risk_score=None, flagged_pnl=0.0) -> dict:
    """
    Pure: build the behavioural summary the FE reads from the real engine's alerts.

    alerts: objects with .pattern_type, .severity, .message.
    Returns patterns_detected (distinct pattern, worst severity, representative
    message), behavior_score (the session risk score, 0-100), and emotional_tax
    (realized P&L of flagged trades — factual, negative = drag).
    """
    by_pattern: dict = {}
    for a in alerts:
        pt = a.pattern_type
        if pt is None:
            continue
        sev = a.severity or "medium"
        cur = by_pattern.get(pt)
        if cur is None or _SEV_RANK.get(sev, 0) > _SEV_RANK.get(cur["severity"], 0):
            by_pattern[pt] = {
                "pattern_type": pt,
                "name": pt,
                "severity": sev,
                "description": a.message or "",
                "is_positive": False,
            }
    patterns = sorted(by_pattern.values(), key=lambda p: -_SEV_RANK.get(p["severity"], 0))
    return {
        "patterns_detected": patterns,
        "behavior_score": session_risk_score,
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

    # behavior_score = today's session risk score (0-100) from the real engine.
    session_risk = None
    try:
        from app.models.trading_session import TradingSession
        session_risk = (await db.execute(
            select(TradingSession.risk_score)
            .where(TradingSession.broker_account_id == broker_account_id)
            .order_by(TradingSession.session_date.desc())
            .limit(1)
        )).scalar()
        if session_risk is not None:
            session_risk = float(session_risk)
    except Exception:
        session_risk = None

    return summarize_behavior(alerts, session_risk_score=session_risk, flagged_pnl=float(flagged_pnl))
