"""
Portfolio Concentration Service

Detects dangerous portfolio concentration from open position metrics:
  1. Expiry concentration  — >60% of capital in same expiry week
  2. Underlying concentration — >70% of capital in same underlying
  3. Directional skew        — 100% long or 100% short (zero hedge)
  4. Margin utilization      — >80% of available margin used

All thresholds are configurable. Calculation is pure math on pre-computed
position metrics — no AI involved.

AI is used ONLY to convert a list of triggered conditions into a natural-
language WhatsApp/in-app alert message (see _generate_alert_message).
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# ─── Thresholds ──────────────────────────────────────────────────────────────
EXPIRY_CONCENTRATION_PCT = 60.0      # >60% of capital in one expiry week
UNDERLYING_CONCENTRATION_PCT = 70.0  # >70% of capital in one underlying
MARGIN_UTILIZATION_PCT = 80.0        # >80% of available margin used
ALERT_COOLDOWN_HOURS = 4             # Don't re-fire the same alert for 4 hours


def _expiry_week_key(expiry_iso: str) -> str:
    """Convert expiry date string to ISO week key like '2024-W04'."""
    try:
        d = datetime.fromisoformat(expiry_iso).date()
        return f"{d.isocalendar().year}-W{d.isocalendar().week:02d}"
    except Exception:
        return "unknown"


def _analyse_concentration(metrics: List[Dict]) -> Dict:
    """
    Given a list of position metric dicts (from PositionMetricsService),
    compute concentration metrics.

    Returns:
    {
      "total_capital_at_risk": float,
      "expiry_weeks": {"2024-W04": {"pct": 65.2, "capital": 123456}},
      "underlyings": {"NIFTY": {"pct": 72.1, "capital": 150000}},
      "long_pct": 80.0,
      "short_pct": 20.0,
      "triggered": [
        {"type": "expiry_concentration", "key": "2024-W04", "value": 65.2},
        ...
      ]
    }
    """
    if not metrics:
        return {"total_capital_at_risk": 0, "triggered": []}

    # Only include positions with known capital at risk
    priced = [m for m in metrics if m.get("capital_at_risk") is not None]
    if not priced:
        return {"total_capital_at_risk": 0, "triggered": []}

    total = sum(m["capital_at_risk"] for m in priced)
    if total == 0:
        return {"total_capital_at_risk": 0, "triggered": []}

    # Expiry grouping
    expiry_buckets: Dict[str, float] = {}
    for m in priced:
        expiry = m.get("expiry")
        if not expiry:
            continue
        week = _expiry_week_key(expiry)
        expiry_buckets[week] = expiry_buckets.get(week, 0) + m["capital_at_risk"]

    expiry_weeks = {
        wk: {"pct": round(cap / total * 100, 1), "capital": round(cap, 2)}
        for wk, cap in expiry_buckets.items()
    }

    # Underlying grouping
    underlying_buckets: Dict[str, float] = {}
    for m in priced:
        name = m.get("underlying_name") or m.get("tradingsymbol")
        underlying_buckets[name] = underlying_buckets.get(name, 0) + m["capital_at_risk"]

    underlyings = {
        sym: {"pct": round(cap / total * 100, 1), "capital": round(cap, 2)}
        for sym, cap in underlying_buckets.items()
    }

    # Directional exposure (long = positive quantity, short = negative)
    long_cap = sum(m["capital_at_risk"] for m in priced if (m.get("quantity") or 0) > 0)
    short_cap = sum(m["capital_at_risk"] for m in priced if (m.get("quantity") or 0) < 0)
    long_pct = round(long_cap / total * 100, 1)
    short_pct = round(short_cap / total * 100, 1)

    # Triggered conditions
    triggered = []

    for wk, info in expiry_weeks.items():
        if info["pct"] >= EXPIRY_CONCENTRATION_PCT:
            triggered.append({
                "type": "expiry_concentration",
                "key": wk,
                "value": info["pct"],
            })

    for sym, info in underlyings.items():
        if info["pct"] >= UNDERLYING_CONCENTRATION_PCT:
            triggered.append({
                "type": "underlying_concentration",
                "key": sym,
                "value": info["pct"],
            })

    if long_pct == 100.0 and len(priced) >= 2:
        triggered.append({"type": "directional_skew", "key": "all_long", "value": 100.0})
    elif short_pct == 100.0 and len(priced) >= 2:
        triggered.append({"type": "directional_skew", "key": "all_short", "value": 100.0})

    return {
        "total_capital_at_risk": round(total, 2),
        "expiry_weeks": expiry_weeks,
        "underlyings": underlyings,
        "long_pct": long_pct,
        "short_pct": short_pct,
        "triggered": triggered,
    }


async def check_margin_utilization(
    broker_account_id: UUID,
    db: AsyncSession,
) -> Optional[Dict]:
    """
    Check margin utilization from the latest margin snapshot.
    Returns a triggered dict if >80%, else None.
    """
    from app.models.margin_snapshot import MarginSnapshot

    result = await db.execute(
        select(MarginSnapshot)
        .where(MarginSnapshot.broker_account_id == broker_account_id)
        .order_by(MarginSnapshot.created_at.desc())
        .limit(1)
    )
    snap = result.scalar_one_or_none()
    if not snap:
        return None

    net = float(snap.equity_total or 0)
    used = float(snap.equity_used or 0)
    if net <= 0:
        return None

    utilization_pct = round(used / net * 100, 1)
    if utilization_pct >= MARGIN_UTILIZATION_PCT:
        return {
            "type": "margin_utilization",
            "key": f"{utilization_pct}pct",
            "value": utilization_pct,
        }
    return None


async def _is_in_cooldown(
    broker_account_id: UUID,
    alert_type: str,
    alert_key: str,
    db: AsyncSession,
) -> bool:
    """Return True if this alert was already sent within the cooldown window."""
    from sqlalchemy import text

    now = datetime.now(timezone.utc)
    result = await db.execute(
        text(
            "SELECT 1 FROM position_alerts_sent "
            "WHERE broker_account_id = :bid "
            "  AND alert_type = :atype "
            "  AND alert_key = :akey "
            "  AND cooldown_until > :now "
            "LIMIT 1"
        ),
        {"bid": str(broker_account_id), "atype": alert_type, "akey": alert_key, "now": now},
    )
    return result.fetchone() is not None


async def _record_alert_sent(
    broker_account_id: UUID,
    alert_type: str,
    alert_key: str,
    db: AsyncSession,
) -> None:
    """Insert a cooldown record so the same alert isn't re-fired too soon."""
    from sqlalchemy import text

    now = datetime.now(timezone.utc)
    cooldown_until = now + timedelta(hours=ALERT_COOLDOWN_HOURS)
    await db.execute(
        text(
            "INSERT INTO position_alerts_sent "
            "(broker_account_id, alert_type, alert_key, fired_at, cooldown_until) "
            "VALUES (:bid, :atype, :akey, :fired, :until)"
        ),
        {
            "bid": str(broker_account_id),
            "atype": alert_type,
            "akey": alert_key,
            "fired": now,
            "until": cooldown_until,
        },
    )


def _generate_alert_message(triggered: List[Dict], concentration: Dict) -> str:
    """
    Convert structured concentration data into a concise alert message.
    No AI — pure template. Short, factual, no opinion.
    """
    lines = []
    for t in triggered:
        ttype = t["type"]
        key = t["key"]
        val = t["value"]

        if ttype == "expiry_concentration":
            lines.append(f"⚠️ {val:.0f}% of your capital expires in week {key}")
        elif ttype == "underlying_concentration":
            lines.append(f"⚠️ {val:.0f}% of capital is in {key} positions")
        elif ttype == "directional_skew":
            direction = "long" if "long" in key else "short"
            lines.append(f"⚠️ Portfolio is 100% {direction} — no hedge")
        elif ttype == "margin_utilization":
            lines.append(f"⚠️ Margin utilization at {val:.0f}% of available funds")

    if not lines:
        return ""

    total = concentration.get("total_capital_at_risk", 0)
    header = f"📊 Portfolio Concentration Alert\nCapital at risk: ₹{total:,.0f}\n\n"
    return header + "\n".join(lines)


class PortfolioConcentrationService:

    async def analyse_and_alert(
        self,
        broker_account_id: UUID,
        metrics: List[Dict],
        db: AsyncSession,
    ) -> Dict:
        """
        Analyse concentration and fire new alerts (with cooldown dedup).

        Returns:
        {
          "concentration": { ... analysis results ... },
          "new_alerts": [ { type, key, value, message } ],
          "skipped_cooldown": int,
        }
        """
        concentration = _analyse_concentration(metrics)

        # Also check margin
        margin_alert = await check_margin_utilization(broker_account_id, db)
        all_triggered = list(concentration["triggered"])
        if margin_alert:
            all_triggered.append(margin_alert)
            concentration["triggered"].append(margin_alert)

        new_alerts = []
        skipped = 0

        for t in all_triggered:
            in_cooldown = await _is_in_cooldown(
                broker_account_id, t["type"], t["key"], db
            )
            if in_cooldown:
                skipped += 1
                continue

            message = _generate_alert_message([t], concentration)
            new_alerts.append({**t, "message": message})
            await _record_alert_sent(broker_account_id, t["type"], t["key"], db)

        if new_alerts:
            await db.commit()

        return {
            "concentration": concentration,
            "new_alerts": new_alerts,
            "skipped_cooldown": skipped,
        }


portfolio_concentration_service = PortfolioConcentrationService()
