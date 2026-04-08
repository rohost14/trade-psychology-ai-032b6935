"""
Shield Service — Factual post-alert behaviour tracking.

For each behavioural alert we answer one simple question:
  Did the trader stop, or keep going?

  • "heeded"    → no CompletedTrades for the rest of that trading session.
                  Narrative: "You stopped trading after this alert."

  • "continued" → trader kept taking positions after the alert fired.
                  Narrative: "You took 3 more trades → net P&L: −₹1,583"

No T+30 counterfactuals.  No "capital defended" performance claims.
No AlertCheckpoints.  Only facts from CompletedTrade records.

Performance:
  All public methods batch-load data upfront.
  Always ≤ 4 DB queries regardless of alert count.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.models.risk_alert import RiskAlert
from app.models.completed_trade import CompletedTrade

logger = logging.getLogger(__name__)

_IST = ZoneInfo("Asia/Kolkata")

# Market closes at 15:30 IST. Treat the session as over after this time.
_SESSION_END_HOUR = 15
_SESSION_END_MINUTE = 30


def _session_end_utc(alert_time_utc: datetime) -> datetime:
    """Return the UTC timestamp for 15:30 IST on the same calendar day as alert_time_utc."""
    ist_dt = alert_time_utc.astimezone(_IST)
    session_end_ist = ist_dt.replace(
        hour=_SESSION_END_HOUR,
        minute=_SESSION_END_MINUTE,
        second=0,
        microsecond=0,
    )
    return session_end_ist.astimezone(timezone.utc)


class ShieldService:

    # ── Public API ──────────────────────────────────────────────────────

    async def get_shield_summary(
        self,
        broker_account_id: UUID,
        db: AsyncSession,
        days: Optional[int] = None,
    ) -> Dict:
        """Hero metrics for the shield page / dashboard card."""
        try:
            alerts = await self._get_alerts(broker_account_id, db, days)
            if not alerts:
                return self._empty_summary()

            post_cts = await self._batch_load_post_alert_cts(
                broker_account_id, alerts, db
            )

            total_alerts = len(alerts)
            danger_count = sum(1 for a in alerts if a.severity in ("danger", "critical"))
            caution_count = sum(1 for a in alerts if a.severity == "caution")
            heeded_count = 0
            continued_count = 0
            post_alert_pnl_continued = 0.0   # net P&L from trades taken AFTER alerts (factual)
            current_streak = 0
            counting_streak = True

            # spiral_sessions: calendar days with ≥3 danger/critical alerts
            danger_days: Dict[str, int] = {}
            for a in alerts:
                if a.severity in ("danger", "critical") and a.detected_at:
                    day = a.detected_at.astimezone(_IST).strftime("%Y-%m-%d")
                    danger_days[day] = danger_days.get(day, 0) + 1
            spiral_sessions = sum(1 for c in danger_days.values() if c >= 3)

            # Iterate newest-first for streak calculation
            for alert in sorted(alerts, key=lambda a: a.detected_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True):
                cts_after = post_cts.get(alert.id, [])
                outcome = "heeded" if not cts_after else "continued"

                if outcome == "heeded":
                    heeded_count += 1
                    if counting_streak:
                        current_streak += 1
                else:
                    continued_count += 1
                    counting_streak = False
                    post_alert_pnl_continued += sum(
                        float(ct.realized_pnl or 0) for ct in cts_after
                    )

            return {
                "total_alerts": total_alerts,
                "danger_count": danger_count,
                "caution_count": caution_count,
                "heeded_count": heeded_count,
                "continued_count": continued_count,
                # Sum of actual P&L from trades taken AFTER alerts were ignored.
                # Negative = additional losses incurred by continuing. Positive = they worked out.
                # Named "post_alert_pnl" to be neutral — frontend decides how to present.
                "post_alert_pnl_continued": round(post_alert_pnl_continued, 2),
                "heeded_streak": current_streak,
                "spiral_sessions": spiral_sessions,
            }
        except Exception as e:
            logger.error(f"Shield summary failed: {e}", exc_info=True)
            return self._empty_summary()

    async def get_intervention_timeline(
        self,
        broker_account_id: UUID,
        db: AsyncSession,
        limit: int = 50,
    ) -> List[Dict]:
        """Per-alert detail — factual post-alert behaviour."""
        try:
            alerts = await self._get_alerts(broker_account_id, db, days=None)
            alerts = sorted(
                alerts,
                key=lambda a: a.detected_at or datetime.min.replace(tzinfo=timezone.utc),
                reverse=True,
            )[:limit]

            if not alerts:
                return []

            post_cts = await self._batch_load_post_alert_cts(
                broker_account_id, alerts, db
            )

            timeline = []
            for alert in alerts:
                cts_after = post_cts.get(alert.id, [])
                outcome = "heeded" if not cts_after else "continued"

                post_alert_pnl = sum(float(ct.realized_pnl or 0) for ct in cts_after)

                # Build per-trade summary list (newest first inside the group)
                post_trades_detail = [
                    {
                        "tradingsymbol": ct.tradingsymbol,
                        "realized_pnl": round(float(ct.realized_pnl or 0), 2),
                        "exit_time": ct.exit_time.isoformat() if ct.exit_time else None,
                    }
                    for ct in cts_after
                ]

                trigger_symbol = (alert.details or {}).get("trigger_symbol", "") if alert.details else ""

                narrative = self._build_narrative(
                    outcome=outcome,
                    post_alert_trades=cts_after,
                    post_alert_pnl=post_alert_pnl,
                )

                timeline.append({
                    "id": str(alert.id),
                    "detected_at": alert.detected_at.isoformat() if alert.detected_at else None,
                    "pattern_type": alert.pattern_type,
                    "severity": alert.severity,
                    "message": alert.message,
                    "trigger_symbol": trigger_symbol,
                    "outcome": outcome,
                    "post_alert_trade_count": len(cts_after),
                    "post_alert_pnl": round(post_alert_pnl, 2),
                    "post_alert_trades": post_trades_detail,
                    "narrative": narrative,
                    "details": alert.details,
                })

            return timeline
        except Exception as e:
            logger.error(f"Shield timeline failed: {e}", exc_info=True)
            return []

    async def get_pattern_breakdown(
        self,
        broker_account_id: UUID,
        db: AsyncSession,
    ) -> List[Dict]:
        """Per-pattern summary — heeded rate + post-alert P&L."""
        try:
            alerts = await self._get_alerts(broker_account_id, db, days=None)
            if not alerts:
                return []

            post_cts = await self._batch_load_post_alert_cts(
                broker_account_id, alerts, db
            )

            groups: Dict[str, Dict] = {}
            for alert in alerts:
                key = alert.pattern_type or "unknown"
                if key not in groups:
                    groups[key] = {
                        "alerts": 0,
                        "heeded": 0,
                        "continued": 0,
                        "post_alert_pnl": 0.0,
                    }
                g = groups[key]
                g["alerts"] += 1

                cts_after = post_cts.get(alert.id, [])
                if cts_after:
                    g["continued"] += 1
                    g["post_alert_pnl"] += sum(float(ct.realized_pnl or 0) for ct in cts_after)
                else:
                    g["heeded"] += 1

            result = []
            for pattern, stats in sorted(
                groups.items(),
                key=lambda x: x[1]["alerts"],
                reverse=True,
            ):
                n = stats["alerts"]
                heeded_pct = round(stats["heeded"] / n * 100) if n else 0
                result.append({
                    "pattern_type": pattern,
                    "display_name": pattern.replace("_", " ").title(),
                    "alerts": n,
                    "heeded": stats["heeded"],
                    "continued": stats["continued"],
                    "heeded_pct": heeded_pct,
                    "post_alert_pnl": round(stats["post_alert_pnl"], 2),
                })

            return result
        except Exception as e:
            logger.error(f"Shield pattern breakdown failed: {e}", exc_info=True)
            return []

    # ── Batch loaders ────────────────────────────────────────────────────

    async def _get_alerts(
        self,
        broker_account_id: UUID,
        db: AsyncSession,
        days: Optional[int],
    ) -> List[RiskAlert]:
        query = select(RiskAlert).where(
            RiskAlert.broker_account_id == broker_account_id
        )
        if days is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            query = query.where(RiskAlert.detected_at >= cutoff)
        query = query.order_by(RiskAlert.detected_at.desc())
        result = await db.execute(query)
        return list(result.scalars().all())

    async def _batch_load_post_alert_cts(
        self,
        broker_account_id: UUID,
        alerts: List[RiskAlert],
        db: AsyncSession,
    ) -> Dict:
        """
        For each alert, load CompletedTrades that exited AFTER the alert fired
        and before the end of that trading session (15:30 IST same day).

        Returns {alert_id: [CompletedTrade, ...]} ordered by exit_time asc.

        Uses a single DB query: fetch all CTs from earliest_alert to latest_session_end,
        then partition in Python.
        """
        if not alerts:
            return {}

        alert_times = [a.detected_at for a in alerts if a.detected_at]
        if not alert_times:
            return {a.id: [] for a in alerts}

        range_start = min(alert_times)
        # Ceiling: latest session end (could span multiple days if days=30)
        range_end = max(_session_end_utc(t) for t in alert_times)

        try:
            result = await db.execute(
                select(CompletedTrade).where(
                    and_(
                        CompletedTrade.broker_account_id == broker_account_id,
                        CompletedTrade.exit_time > range_start,
                        CompletedTrade.exit_time <= range_end,
                    )
                ).order_by(CompletedTrade.exit_time.asc())
            )
            all_cts = list(result.scalars().all())
        except Exception as e:
            logger.error(f"Batch post-alert CTs load failed: {e}")
            return {a.id: [] for a in alerts}

        cts_by_alert: Dict = {}
        for alert in alerts:
            if not alert.detected_at:
                cts_by_alert[alert.id] = []
                continue
            session_end = _session_end_utc(alert.detected_at)
            cts_by_alert[alert.id] = [
                ct for ct in all_cts
                if ct.exit_time
                and ct.exit_time > alert.detected_at
                and ct.exit_time <= session_end
            ]

        return cts_by_alert

    # ── Narrative builder ────────────────────────────────────────────────

    def _build_narrative(
        self,
        outcome: str,
        post_alert_trades: List[CompletedTrade],
        post_alert_pnl: float,
    ) -> str:
        if outcome == "heeded":
            return "You stopped trading after this alert."

        n = len(post_alert_trades)
        trade_word = "trade" if n == 1 else "trades"
        sign = "+" if post_alert_pnl >= 0 else ""
        pnl_str = f"{sign}₹{abs(post_alert_pnl):,.0f}"
        direction = "" if post_alert_pnl >= 0 else "additional loss "
        if post_alert_pnl >= 0:
            return f"You took {n} more {trade_word} after this alert → net P&L: {sign}₹{post_alert_pnl:,.0f}"
        else:
            return (
                f"You took {n} more {trade_word} after this alert "
                f"→ additional loss ₹{abs(post_alert_pnl):,.0f}"
            )

    def _empty_summary(self) -> Dict:
        return {
            "total_alerts": 0,
            "danger_count": 0,
            "caution_count": 0,
            "heeded_count": 0,
            "continued_count": 0,
            "post_alert_pnl_continued": 0.0,
            "heeded_streak": 0,
            "spiral_sessions": 0,
        }


shield_service = ShieldService()
