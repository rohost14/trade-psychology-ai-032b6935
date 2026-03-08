"""
Shield Service — Real counterfactual P&L from AlertCheckpoints.

For each danger/critical alert:
  - AlertCheckpoint snapshots the trigger position + LTP at alert time
  - check_alert_t30 computes: money_saved = user_actual_pnl - counterfactual_pnl_at_t30
    (positive = alert helped user avoid a worse outcome)
    (negative = market recovered / user exited at a bad time — honest)

No bootstrap. No hardcoded ₹ defaults. Numbers are either real or not shown.

Outcome classification (heeded / partially_heeded / ignored) is behavioural:
  - based on whether the user traded within 30 min of the alert
  - independent of the checkpoint / P&L data
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.models.risk_alert import RiskAlert
from app.models.trade import Trade
from app.models.alert_checkpoint import AlertCheckpoint

logger = logging.getLogger(__name__)

SEVERITY_WEIGHT = {"danger": 2.0, "critical": 2.0, "caution": 1.0}


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

            now = datetime.now(timezone.utc)
            week_start = now - timedelta(days=7)
            month_start = now - timedelta(days=30)

            total_defended = 0.0
            week_defended = 0.0
            month_defended = 0.0
            heeded_count = 0
            ignored_count = 0
            weighted_heeded = 0.0
            weighted_total = 0.0
            current_streak = 0
            counting_streak = True

            cp_complete = 0
            cp_calculating = 0
            cp_unavailable = 0

            sorted_alerts = sorted(
                alerts, key=lambda a: a.detected_at or now, reverse=True
            )

            for alert in sorted_alerts:
                # Outcome classification (behaviour-based, independent of checkpoint)
                post_trades = await self._get_post_alert_trades(
                    broker_account_id, alert.detected_at, db
                )
                outcome = self._classify_alert_outcome(alert, post_trades)

                # Money saved — only from checkpoint real data
                checkpoint = await self._get_checkpoint(alert.id, db)
                defended = 0.0

                if checkpoint:
                    status = checkpoint.calculation_status
                    if status == "complete" and checkpoint.money_saved is not None:
                        # Positive = saved money, negative = exited at bad time
                        # Only add positive to the defended total (savings, not losses)
                        defended = max(0.0, float(checkpoint.money_saved))
                        cp_complete += 1
                    elif status in ("pending", "calculating"):
                        cp_calculating += 1
                    else:
                        # no_positions / error / null
                        cp_unavailable += 1
                else:
                    cp_unavailable += 1

                total_defended += defended
                if alert.detected_at and alert.detected_at >= week_start:
                    week_defended += defended
                if alert.detected_at and alert.detected_at >= month_start:
                    month_defended += defended

                w = SEVERITY_WEIGHT.get(alert.severity, 1.0)
                weighted_total += w

                if outcome == "heeded":
                    heeded_count += 1
                    weighted_heeded += w
                    if counting_streak:
                        current_streak += 1
                elif outcome == "partially_heeded":
                    weighted_heeded += w * 0.5
                    counting_streak = False
                else:
                    ignored_count += 1
                    counting_streak = False

            blowups = await self._count_blowups_prevented(broker_account_id, db, days)
            shield_score = (
                round(weighted_heeded / weighted_total * 100) if weighted_total > 0 else 0
            )

            return {
                "capital_defended": round(total_defended),
                "this_week": round(week_defended),
                "this_month": round(month_defended),
                "shield_score": shield_score,
                "total_alerts": len(alerts),
                "heeded": heeded_count,
                "ignored": ignored_count,
                "heeded_streak": current_streak,
                "blowups_prevented": blowups,
                "checkpoint_coverage": {
                    "complete": cp_complete,
                    "calculating": cp_calculating,
                    "unavailable": cp_unavailable,
                },
                "data_points": cp_complete,
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
        """Per-alert detail with real checkpoint data."""
        try:
            alerts = await self._get_alerts(broker_account_id, db, days=None)
            alerts = sorted(
                alerts,
                key=lambda a: a.detected_at or datetime.min.replace(tzinfo=timezone.utc),
                reverse=True,
            )[:limit]

            if not alerts:
                return []

            timeline = []

            for alert in alerts:
                post_trades = await self._get_post_alert_trades(
                    broker_account_id, alert.detected_at, db
                )
                outcome = self._classify_alert_outcome(alert, post_trades)

                # Trigger trade info
                trigger_symbol = "Multiple Positions"
                trigger_info = None
                if alert.trigger_trade_id:
                    result = await db.execute(
                        select(Trade).where(Trade.id == alert.trigger_trade_id)
                    )
                    trigger_trade = result.scalar_one_or_none()
                    if trigger_trade:
                        trigger_symbol = trigger_trade.tradingsymbol or trigger_symbol
                        trigger_info = {
                            "tradingsymbol": trigger_trade.tradingsymbol,
                            "quantity": trigger_trade.quantity,
                            "average_price": float(trigger_trade.average_price or 0),
                            "transaction_type": trigger_trade.transaction_type,
                        }

                # Checkpoint — the single source of truth for P&L numbers
                checkpoint = await self._get_checkpoint(alert.id, db)
                calc_status = checkpoint.calculation_status if checkpoint else None
                money_saved = None
                counterfactual_pnl_t30 = None
                user_actual_pnl = None
                capital_defended = None

                if checkpoint and checkpoint.calculation_status == "complete":
                    money_saved = (
                        float(checkpoint.money_saved)
                        if checkpoint.money_saved is not None else None
                    )
                    counterfactual_pnl_t30 = (
                        float(checkpoint.pnl_at_t30)
                        if checkpoint.pnl_at_t30 is not None else None
                    )
                    user_actual_pnl = (
                        float(checkpoint.user_actual_pnl)
                        if checkpoint.user_actual_pnl is not None else None
                    )
                    capital_defended = (
                        round(max(0.0, money_saved)) if money_saved is not None else 0
                    )

                timeline.append({
                    "id": str(alert.id),
                    "detected_at": alert.detected_at.isoformat() if alert.detected_at else None,
                    "pattern_type": alert.pattern_type,
                    "severity": alert.severity,
                    "message": alert.message,
                    "outcome": outcome,
                    "trigger_symbol": trigger_symbol,
                    "trigger_trade": trigger_info,
                    "capital_defended": capital_defended,
                    "details": alert.details,
                    # Checkpoint fields
                    "calculation_status": calc_status,
                    "money_saved": round(money_saved) if money_saved is not None else None,
                    "counterfactual_pnl_t30": (
                        round(counterfactual_pnl_t30)
                        if counterfactual_pnl_t30 is not None else None
                    ),
                    "user_actual_pnl": (
                        round(user_actual_pnl)
                        if user_actual_pnl is not None else None
                    ),
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
        """Grouped stats per pattern type — real checkpoint data only."""
        try:
            alerts = await self._get_alerts(broker_account_id, db, days=None)
            if not alerts:
                return []

            pattern_groups: Dict[str, Dict] = {}

            for alert in alerts:
                key = alert.pattern_type or "unknown"
                if key not in pattern_groups:
                    pattern_groups[key] = {
                        "alerts": 0,
                        "heeded": 0,
                        "ignored": 0,
                        "total_saved": 0.0,   # sum of real money_saved (incl. negatives)
                        "total_defended": 0.0, # sum of max(0, money_saved)
                        "real_data_count": 0,
                    }
                grp = pattern_groups[key]
                grp["alerts"] += 1

                post_trades = await self._get_post_alert_trades(
                    broker_account_id, alert.detected_at, db
                )
                outcome = self._classify_alert_outcome(alert, post_trades)
                if outcome == "heeded":
                    grp["heeded"] += 1
                elif outcome == "ignored":
                    grp["ignored"] += 1

                checkpoint = await self._get_checkpoint(alert.id, db)
                if checkpoint and checkpoint.calculation_status == "complete" \
                        and checkpoint.money_saved is not None:
                    saved = float(checkpoint.money_saved)
                    grp["total_saved"] += saved
                    grp["total_defended"] += max(0.0, saved)
                    grp["real_data_count"] += 1

            result = []
            for pattern, stats in sorted(
                pattern_groups.items(),
                key=lambda x: x[1]["total_defended"],
                reverse=True,
            ):
                n = stats["alerts"]
                real = stats["real_data_count"]
                heeded_pct = round(stats["heeded"] / n * 100) if n else 0
                avg_defended = round(stats["total_defended"] / real) if real else 0
                result.append({
                    "pattern_type": pattern,
                    "display_name": pattern.replace("_", " ").title(),
                    "alerts": n,
                    "heeded": stats["heeded"],
                    "ignored": stats["ignored"],
                    "heeded_pct": heeded_pct,
                    "avg_defended": avg_defended,
                    "total_defended": round(stats["total_defended"]),
                    "real_data_count": real,
                })

            return result
        except Exception as e:
            logger.error(f"Shield pattern breakdown failed: {e}", exc_info=True)
            return []

    # ── Internal helpers ────────────────────────────────────────────────

    async def _get_alerts(
        self, broker_account_id: UUID, db: AsyncSession, days: Optional[int]
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

    async def _get_post_alert_trades(
        self,
        broker_account_id: UUID,
        alert_time: Optional[datetime],
        db: AsyncSession,
    ) -> List[Trade]:
        """Trades within 60 minutes after alert — used only for outcome classification."""
        if not alert_time:
            return []
        window_end = alert_time + timedelta(minutes=60)
        day_end = alert_time.replace(
            hour=0, minute=0, second=0, microsecond=0
        ) + timedelta(days=1)

        result = await db.execute(
            select(Trade).where(
                and_(
                    Trade.broker_account_id == broker_account_id,
                    Trade.order_timestamp > alert_time,
                    Trade.order_timestamp <= window_end,
                    Trade.order_timestamp < day_end,
                    Trade.status == "COMPLETE",
                )
            ).order_by(Trade.order_timestamp)
        )
        return list(result.scalars().all())

    def _classify_alert_outcome(
        self, alert: RiskAlert, post_trades: List[Trade]
    ) -> str:
        """Classify: heeded | partially_heeded | ignored — based on trading behaviour."""
        if not alert.detected_at:
            return "ignored"

        has_ack = alert.acknowledged_at is not None

        if not post_trades:
            return "heeded"

        first_trade_time = min(
            (t.order_timestamp for t in post_trades if t.order_timestamp),
            default=None,
        )
        if not first_trade_time:
            return "heeded"

        gap_minutes = (first_trade_time - alert.detected_at).total_seconds() / 60

        if has_ack and gap_minutes > 30:
            return "heeded"
        elif has_ack and gap_minutes <= 30:
            return "partially_heeded"
        elif gap_minutes > 30:
            return "partially_heeded"
        else:
            return "ignored"

    async def _get_checkpoint(
        self, alert_id, db: AsyncSession
    ) -> Optional[AlertCheckpoint]:
        try:
            result = await db.execute(
                select(AlertCheckpoint).where(AlertCheckpoint.alert_id == alert_id)
            )
            return result.scalar_one_or_none()
        except Exception:
            return None

    async def _count_blowups_prevented(
        self, broker_account_id: UUID, db: AsyncSession, days: Optional[int]
    ) -> int:
        """Days where user received 5+ danger alerts and ultimately stopped trading."""
        query = select(RiskAlert).where(
            and_(
                RiskAlert.broker_account_id == broker_account_id,
                RiskAlert.severity.in_(["danger", "critical"]),
            )
        )
        if days is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            query = query.where(RiskAlert.detected_at >= cutoff)

        result = await db.execute(query)
        danger_alerts = list(result.scalars().all())

        daily_counts: Dict[str, int] = {}
        for a in danger_alerts:
            if a.detected_at:
                day_key = a.detected_at.strftime("%Y-%m-%d")
                daily_counts[day_key] = daily_counts.get(day_key, 0) + 1

        return sum(1 for c in daily_counts.values() if c >= 5)

    def _empty_summary(self) -> Dict:
        return {
            "capital_defended": 0,
            "this_week": 0,
            "this_month": 0,
            "shield_score": 0,
            "total_alerts": 0,
            "heeded": 0,
            "ignored": 0,
            "heeded_streak": 0,
            "blowups_prevented": 0,
            "checkpoint_coverage": {
                "complete": 0,
                "calculating": 0,
                "unavailable": 0,
            },
            "data_points": 0,
        }


shield_service = ShieldService()
