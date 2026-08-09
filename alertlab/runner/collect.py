"""
Reading back what a scenario produced — including what it deliberately did NOT.

The alert feed is the obvious output. The **suppression trace** is the one no
existing tool provides, and the one that matters most: twelve of the fifteen
defects found reviewing this week's work were something firing wrongly or
vanishing silently. A run that only lists alerts shows you half the behaviour.
"""
from __future__ import annotations

from typing import Any, Dict, List

from .harness import IST, LAB_ACCOUNT_ID


def _iso(value):
    return value.isoformat() if value is not None else None


async def collect_alerts(db) -> List[Dict[str, Any]]:
    """Every alert the run raised, oldest first, with its evidence."""
    from sqlalchemy import select

    from app.models.risk_alert import RiskAlert
    from app.services.detector_registry import BY_NAME, pattern_copy

    rows = (await db.execute(
        select(RiskAlert)
        .where(RiskAlert.broker_account_id == LAB_ACCOUNT_ID)
        .order_by(RiskAlert.detected_at, RiskAlert.created_at)
    )).scalars().all()

    out = []
    for a in rows:
        copy = pattern_copy(a.pattern_type)
        spec = BY_NAME.get(a.pattern_type)
        latency = None
        if a.detected_at and a.created_at:
            delta = (a.created_at - a.detected_at).total_seconds()
            latency = round(delta, 3) if delta >= 0 else None
        out.append({
            "id": str(a.id),
            "pattern_type": a.pattern_type,
            "label": copy.label if copy else a.pattern_type,
            "severity": a.severity,
            "message": a.message,
            "details": a.details or {},
            "confidence": float(a.confidence) if a.confidence is not None else None,
            "lifecycle": getattr(a, "lifecycle", "post"),
            "detected_at": _iso(a.detected_at),
            "detected_at_ist": a.detected_at.astimezone(IST).strftime("%H:%M:%S")
                               if a.detected_at else None,
            "latency_seconds": latency,
            "trigger_completed_trade_id": str(a.trigger_completed_trade_id)
                                          if a.trigger_completed_trade_id else None,
            # The guardian panel's input. Delivery is parked; the ROUTING
            # decision is testable now, and a `caution` appearing here would be
            # a visible bug rather than a silent one.
            "guardian_eligible": bool(spec.guardian_eligible) if spec else False,
            "would_route_to_guardian": bool(
                spec and spec.guardian_eligible and a.severity in ("danger", "critical")
            ),
        })
    return out


async def collect_suppressed(db) -> List[Dict[str, Any]]:
    """
    Detections that never became an alert, and which layer stopped each.

    BehaviorEvents are written for EVERY detection (§1C.8 — evidence is never
    suppressed), so an event with no `risk_alert_id` is a detection the pipeline
    chose not to surface. That choice is the thing worth seeing.
    """
    from sqlalchemy import select

    from app.models.behavior_event import BehaviorEvent

    rows = (await db.execute(
        select(BehaviorEvent)
        .where(BehaviorEvent.broker_account_id == LAB_ACCOUNT_ID)
        .order_by(BehaviorEvent.detected_at)
    )).scalars().all()

    out = []
    for ev in rows:
        if ev.risk_alert_id is not None:
            continue        # it became an alert; not suppressed
        evidence = ev.evidence or {}
        marker = evidence.get("_suppressed")
        if ev.shadow:
            reason = "shadow mode — recorded for the promote decision, never alerts"
        elif marker == "dedup":
            reason = "deduplicated — same pattern already fired inside its window"
        elif marker == "constitution_breach":
            # Deliberate: a rule the trader wrote is louder and more specific
            # than the behaviour behind it, so the constitution alert wins and
            # the ordinary pattern stays quiet.
            reason = "constitution breach took precedence — the rule alert is the louder one"
        elif marker and str(marker).startswith("strategy_group"):
            reason = f"part of a recognised structure — {marker}"
        elif marker:
            reason = f"suppressed — {marker}"
        elif ev.severity == "info":
            reason = "info severity — analytics evidence, never an alert"
        else:
            reason = "recorded as evidence, not surfaced"
        out.append({
            "detector": ev.detector,
            "severity": ev.severity,
            "message": ev.message,
            "confidence": float(ev.confidence) if ev.confidence is not None else None,
            "shadow": bool(ev.shadow),
            "reason": reason,
            "detected_at_ist": ev.detected_at.astimezone(IST).strftime("%H:%M:%S")
                               if ev.detected_at else None,
        })
    return out


async def collect_positions(db) -> Dict[str, List[Dict[str, Any]]]:
    """Open positions and closed rounds, as the dashboard would show them."""
    from sqlalchemy import select

    from app.models.completed_trade import CompletedTrade
    from app.models.position import Position

    open_rows = (await db.execute(
        select(Position).where(Position.broker_account_id == LAB_ACCOUNT_ID)
    )).scalars().all()

    closed_rows = (await db.execute(
        select(CompletedTrade)
        .where(CompletedTrade.broker_account_id == LAB_ACCOUNT_ID)
        .order_by(CompletedTrade.exit_time)
    )).scalars().all()

    return {
        "open": [{
            "symbol": p.tradingsymbol,
            "qty": p.total_quantity,
            "avg_entry": float(p.average_entry_price or 0),
            "product": getattr(p, "product", None),
        } for p in open_rows if (p.total_quantity or 0) != 0],
        "closed": [{
            "symbol": c.tradingsymbol,
            "direction": c.direction,
            "qty": c.total_quantity,
            "entry": float(c.avg_entry_price or 0),
            "exit": float(c.avg_exit_price or 0),
            "pnl": float(c.realized_pnl or 0),
            "entry_ist": c.entry_time.astimezone(IST).strftime("%H:%M:%S") if c.entry_time else None,
            "exit_ist": c.exit_time.astimezone(IST).strftime("%H:%M:%S") if c.exit_time else None,
        } for c in closed_rows],
    }


async def collect_structures(db) -> List[Dict[str, Any]]:
    """Multi-leg structures recognised among the open positions."""
    from sqlalchemy import select

    from app.models.position import Position
    from app.services.strategy_detector import classify_open_positions

    rows = (await db.execute(
        select(Position).where(
            Position.broker_account_id == LAB_ACCOUNT_ID,
            Position.total_quantity != 0,
        )
    )).scalars().all()
    return classify_open_positions(list(rows))


async def collect_step(db, seen_alerts: set, seen_events: set) -> Dict[str, Any]:
    """
    State immediately after one fill, and only what is NEW since the last one.

    This is what makes a run readable. Collecting once at the end shows every
    trade and every alert arriving together, so you cannot tell which entry
    caused which alert — which is the single most important thing to see. The
    snapshot is taken per fill and diffed, so an alert appears at the step that
    actually raised it, the way it would during a live session.

    The cost is one read per fill. A scenario has a dozen or so; the clarity is
    worth several seconds.
    """
    alerts = await collect_alerts(db)
    suppressed = await collect_suppressed(db)
    positions = await collect_positions(db)

    new_alerts = [a for a in alerts if a["id"] not in seen_alerts]
    seen_alerts.update(a["id"] for a in alerts)

    def _key(s):
        return (s["detector"], s["detected_at_ist"], s["message"])

    new_suppressed = [s for s in suppressed if _key(s) not in seen_events]
    seen_events.update(_key(s) for s in suppressed)

    return {
        "new_alerts": new_alerts,
        "new_suppressed": new_suppressed,
        "open": positions["open"],
        "closed_count": len(positions["closed"]),
        "session_pnl": round(sum(c["pnl"] for c in positions["closed"]), 2),
        "last_closed": positions["closed"][-1] if positions["closed"] else None,
    }


async def collect_all(db) -> Dict[str, Any]:
    alerts = await collect_alerts(db)
    positions = await collect_positions(db)
    return {
        "alerts": alerts,
        "suppressed": await collect_suppressed(db),
        "positions": positions,
        "structures": await collect_structures(db),
        "guardian": [a for a in alerts if a["would_route_to_guardian"]],
        "session_pnl": round(sum(c["pnl"] for c in positions["closed"]), 2),
    }
