from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import List, Optional, Dict, Any
import logging
from uuid import UUID

from app.models.trade import Trade
from app.models.completed_trade import CompletedTrade
from app.models.risk_alert import RiskAlert
from app.models.broker_account import BrokerAccount
from app.core.trading_defaults import get_thresholds

logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")


class RiskDetector:
    """
    Detects dangerous trading patterns:
    1. Consecutive Loss Spiral
    2. Revenge Sizing
    3. Overtrading Burst
    4. FOMO Entry (rapid entry after price move)
    5. Tilt/Loss Spiral (escalating losses)

    All thresholds are profile-driven via get_thresholds() — no hardcoded magic numbers.
    """

    async def detect_patterns(
        self,
        broker_account_id: UUID,
        db: AsyncSession,
        trigger_trade: Optional[Trade] = None,
        profile=None,
    ) -> List[RiskAlert]:
        """
        Run all pattern detections and return any alerts.

        Args:
            broker_account_id: Account to check
            db: Database session
            trigger_trade: The trade that triggered detection (optional)
            profile: UserProfile model instance for threshold calibration

        Returns:
            List of RiskAlert objects (not yet saved to DB)
        """
        alerts = []

        # Build thresholds from profile (3-tier system)
        thresholds = get_thresholds(profile)

        # Get recent trades (last 24 hours)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

        result = await db.execute(
            select(Trade)
            .where(
                and_(
                    Trade.broker_account_id == broker_account_id,
                    Trade.order_timestamp >= cutoff,
                    Trade.status == "COMPLETE"
                )
            )
            .order_by(desc(Trade.order_timestamp))
        )
        recent_trades = result.scalars().all()

        if not recent_trades:
            return alerts

        logger.info(f"Analyzing {len(recent_trades)} recent trades for patterns")

        # Get recent CompletedTrades (24h window) — these have real P&L
        ct_result = await db.execute(
            select(CompletedTrade)
            .where(
                and_(
                    CompletedTrade.broker_account_id == broker_account_id,
                    CompletedTrade.exit_time >= cutoff
                )
            )
            .order_by(desc(CompletedTrade.exit_time))
        )
        recent_completed = ct_result.scalars().all()

        # Pattern 1: Consecutive Loss Spiral (uses CompletedTrade for real P&L)
        loss_alert = await self._detect_consecutive_losses(recent_completed, trigger_trade, thresholds)
        if loss_alert:
            alerts.append(loss_alert)

        # Pattern 2: Revenge Sizing (uses CompletedTrade for loss detection + Trade for sizing)
        revenge_alert = await self._detect_revenge_sizing(recent_trades, recent_completed, trigger_trade, thresholds)
        if revenge_alert:
            alerts.append(revenge_alert)

        # Pattern 3: Overtrading Burst (count-based, no P&L needed)
        overtrading_alert = await self._detect_overtrading(recent_trades, trigger_trade, thresholds)
        if overtrading_alert:
            alerts.append(overtrading_alert)

        # Pattern 4: FOMO Entry (count/time-based, no P&L needed)
        fomo_alert = await self._detect_fomo_entry(recent_trades, trigger_trade, thresholds)
        if fomo_alert:
            alerts.append(fomo_alert)

        # Pattern 5: Tilt/Loss Spiral (uses CompletedTrade for P&L + Trade for sizing)
        tilt_alert = await self._detect_tilt_spiral(recent_trades, recent_completed, trigger_trade, thresholds)
        if tilt_alert:
            alerts.append(tilt_alert)

        # If danger alert, trigger cooldown
        danger_alerts = [a for a in alerts if a.severity == "danger"]
        if danger_alerts:
            await self._trigger_cooldown(broker_account_id, danger_alerts[0], db)

        return alerts

    async def _detect_consecutive_losses(
        self,
        completed_trades: List[CompletedTrade],
        trigger_trade: Optional[Trade],
        thresholds: dict,
    ) -> Optional[RiskAlert]:
        """
        Detect: N+ losing completed trades in a row.
        Uses CompletedTrade.realized_pnl (real P&L, not Trade.pnl which is always 0).
        Caution: consecutive_loss_caution threshold
        Danger: consecutive_loss_danger threshold
        """
        if not completed_trades:
            return None

        caution_threshold = thresholds.get('consecutive_loss_caution', 3)
        danger_threshold = thresholds.get('consecutive_loss_danger', 5)

        # Sort by exit_time (newest first)
        sorted_ct = sorted(completed_trades, key=lambda ct: ct.exit_time, reverse=True)

        # Count consecutive losses from most recent
        consecutive_losses = 0
        total_loss = 0.0
        losing_ids = []

        for ct in sorted_ct:
            pnl = float(ct.realized_pnl or 0)
            if pnl < 0:
                consecutive_losses += 1
                total_loss += abs(pnl)
                losing_ids.append(str(ct.id))
            else:
                break

        if consecutive_losses >= danger_threshold:
            return RiskAlert(
                broker_account_id=sorted_ct[0].broker_account_id,
                pattern_type="consecutive_loss",
                severity="danger",
                message=f"DANGER: {consecutive_losses} consecutive losing trades, total loss ₹{total_loss:,.0f}",
                details={
                    "consecutive_losses": consecutive_losses,
                    "total_loss": float(total_loss),
                    "loss_streak_started": sorted_ct[consecutive_losses - 1].exit_time.isoformat(),
                    "danger_threshold": danger_threshold,
                },
                trigger_trade_id=trigger_trade.id if trigger_trade else None,
                related_trade_ids=losing_ids
            )
        elif consecutive_losses >= caution_threshold:
            return RiskAlert(
                broker_account_id=sorted_ct[0].broker_account_id,
                pattern_type="consecutive_loss",
                severity="caution",
                message=f"CAUTION: {consecutive_losses} consecutive losing trades, total loss ₹{total_loss:,.0f}",
                details={
                    "consecutive_count": consecutive_losses,
                    "total_loss": float(total_loss),
                    "recommendation": "Review your strategy. Take a break if needed.",
                    "caution_threshold": caution_threshold,
                },
                trigger_trade_id=trigger_trade.id if trigger_trade else None,
                related_trade_ids=losing_ids[:caution_threshold]
            )

        return None

    async def _detect_revenge_sizing(
        self,
        trades: List[Trade],
        completed_trades: List[CompletedTrade],
        trigger_trade: Optional[Trade],
        thresholds: dict,
    ) -> Optional[RiskAlert]:
        """
        Detect: Position size >1.5x after a losing CompletedTrade within revenge_window_min.
        Uses CompletedTrade.realized_pnl for loss detection (real P&L).
        The 1.5x size ratio is a behavioral constant (not user-adjustable).
        """
        if not trigger_trade or len(trades) < 2:
            return None

        revenge_window = thresholds.get('revenge_window_min', 10)

        # Find the most recent completed loss
        sorted_ct = sorted(completed_trades, key=lambda ct: ct.exit_time, reverse=True)
        recent_loss = None
        for ct in sorted_ct:
            if float(ct.realized_pnl or 0) < 0:
                recent_loss = ct
                break

        if not recent_loss:
            return None

        # Check if trigger trade came within revenge_window_min of the loss exit
        time_gap = (trigger_trade.order_timestamp - recent_loss.exit_time).total_seconds() / 60
        if time_gap < 0 or time_gap > revenge_window:
            return None

        # Check size increase: trigger trade qty vs the losing trade's qty
        loss_qty = recent_loss.total_quantity or 0
        curr_qty = trigger_trade.filled_quantity or trigger_trade.quantity or 0

        if loss_qty > 0 and curr_qty > loss_qty * 1.5:
            size_increase_pct = ((curr_qty - loss_qty) / loss_qty) * 100
            loss_amount = abs(float(recent_loss.realized_pnl or 0))

            return RiskAlert(
                broker_account_id=trigger_trade.broker_account_id,
                pattern_type="revenge_sizing",
                severity="danger",
                message=f"DANGER: Position size increased {size_increase_pct:.0f}% within {time_gap:.1f} minutes after ₹{loss_amount:,.0f} loss",
                details={
                    "previous_quantity": loss_qty,
                    "current_quantity": curr_qty,
                    "size_increase_pct": size_increase_pct,
                    "time_gap_minutes": time_gap,
                    "loss_amount": loss_amount,
                    "revenge_window_min": revenge_window,
                    "recommendation": "STOP TRADING. This is classic revenge trading behavior."
                },
                trigger_trade_id=trigger_trade.id,
                related_trade_ids=[str(recent_loss.id)]
            )

        return None

    async def _detect_overtrading(
        self,
        trades: List[Trade],
        trigger_trade: Optional[Trade],
        thresholds: dict,
    ) -> Optional[RiskAlert]:
        """
        Detect: burst_trades_per_15min+ trades in 15-min window.
        Caution: at burst_threshold
        Danger: at 1.4x burst_threshold
        """
        burst_threshold = thresholds.get('burst_trades_per_15min', 7)
        danger_threshold = int(burst_threshold * 1.4)

        if len(trades) < burst_threshold:
            return None

        sorted_trades = sorted(trades, key=lambda t: t.order_timestamp, reverse=True)

        # Check 15-minute rolling window from the NEWEST trade
        newest_ts = sorted_trades[0].order_timestamp
        window_start = newest_ts - timedelta(minutes=15)

        trades_in_window = [
            t for t in sorted_trades
            if t.order_timestamp >= window_start
        ]

        trade_count = len(trades_in_window)

        if trade_count >= danger_threshold:
            return RiskAlert(
                broker_account_id=sorted_trades[0].broker_account_id,
                pattern_type="overtrading",
                severity="danger",
                message=f"DANGER: {trade_count} trades in 15 minutes - Overtrading detected",
                details={
                    "trade_count": trade_count,
                    "window_minutes": 15,
                    "burst_threshold": burst_threshold,
                    "trades_per_minute": trade_count / 15,
                    "recommendation": "STOP. Take a mandatory 30-minute break."
                },
                trigger_trade_id=trigger_trade.id if trigger_trade else None,
                related_trade_ids=[t.id for t in trades_in_window]
            )
        elif trade_count >= burst_threshold:
            return RiskAlert(
                broker_account_id=sorted_trades[0].broker_account_id,
                pattern_type="overtrading",
                severity="caution",
                message=f"CAUTION: {trade_count} trades in 15 minutes - Slow down",
                details={
                    "trade_count": trade_count,
                    "window_minutes": 15,
                    "burst_threshold": burst_threshold,
                    "recommendation": "You're trading frequently. Review your plan."
                },
                trigger_trade_id=trigger_trade.id if trigger_trade else None,
                related_trade_ids=[t.id for t in trades_in_window[:burst_threshold]]
            )

        return None

    async def calculate_risk_state(
        self,
        broker_account_id: UUID,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Calculate overall risk state based on recent alerts.
        """
        # Get unacknowledged alerts from last 4 hours
        cutoff = datetime.now(timezone.utc) - timedelta(hours=4)

        result = await db.execute(
            select(RiskAlert)
            .where(
                and_(
                    RiskAlert.broker_account_id == broker_account_id,
                    RiskAlert.detected_at >= cutoff,
                    RiskAlert.acknowledged_at.is_(None)
                )
            )
            .order_by(desc(RiskAlert.detected_at))
        )
        active_alerts = result.scalars().all()

        if not active_alerts:
            return {
                "risk_state": "safe",
                "active_patterns": [],
                "recommendations": ["All clear. Trade with discipline."]
            }

        # Check for any DANGER alerts
        danger_alerts = [a for a in active_alerts if a.severity == "danger"]

        if danger_alerts:
            patterns = list(set([a.pattern_type for a in danger_alerts]))
            recommendations = [
                "STOP TRADING IMMEDIATELY",
                "Review what went wrong",
                "Take a mandatory break"
            ]

            return {
                "risk_state": "danger",
                "active_patterns": patterns,
                "recommendations": recommendations
            }

        # Only CAUTION alerts
        patterns = list(set([a.pattern_type for a in active_alerts]))
        recommendations = [
            "Slow down and review your strategy",
            "Stick to your trading plan",
            "Consider reducing position sizes"
        ]

        return {
            "risk_state": "caution",
            "active_patterns": patterns,
            "recommendations": recommendations
        }

    async def _detect_fomo_entry(
        self,
        trades: List[Trade],
        trigger_trade: Optional[Trade],
        thresholds: dict,
    ) -> Optional[RiskAlert]:
        """
        Detect FOMO entries:
        - Multiple rapid entries in same direction
        - Trading immediately at market open (9:15-9:20 IST)

        Uses IST timezone explicitly to avoid UTC-based false positives.
        """
        if not trigger_trade or len(trades) < 2:
            return None

        # Check if trading in first 5 minutes of market open — use IST
        trade_time_ist = trigger_trade.order_timestamp.astimezone(IST)
        if trade_time_ist.hour == 9 and trade_time_ist.minute < 20:
            # Count trades in opening minutes (IST-aware)
            opening_trades = [
                t for t in trades
                if t.order_timestamp.astimezone(IST).hour == 9
                and t.order_timestamp.astimezone(IST).minute < 20
                and t.order_timestamp.astimezone(IST).date() == trade_time_ist.date()
            ]

            if len(opening_trades) >= 3:
                return RiskAlert(
                    broker_account_id=trigger_trade.broker_account_id,
                    pattern_type="fomo",
                    severity="caution",
                    message=f"CAUTION: {len(opening_trades)} trades in first 5 minutes - Possible FOMO",
                    details={
                        "opening_trade_count": len(opening_trades),
                        "recommendation": "Market opening is volatile. Wait for clarity."
                    },
                    trigger_trade_id=trigger_trade.id,
                    related_trade_ids=[t.id for t in opening_trades]
                )

        # Check for chasing behavior - multiple same-direction trades in 5 mins
        recent_window = trigger_trade.order_timestamp - timedelta(minutes=5)
        same_direction_trades = [
            t for t in trades
            if t.order_timestamp >= recent_window
            and t.transaction_type == trigger_trade.transaction_type
            and t.tradingsymbol == trigger_trade.tradingsymbol
        ]

        if len(same_direction_trades) >= 3:
            return RiskAlert(
                broker_account_id=trigger_trade.broker_account_id,
                pattern_type="fomo",
                severity="caution",
                message=f"CAUTION: {len(same_direction_trades)} rapid {trigger_trade.transaction_type}s on {trigger_trade.tradingsymbol} - Chasing detected",
                details={
                    "rapid_trades": len(same_direction_trades),
                    "direction": trigger_trade.transaction_type,
                    "symbol": trigger_trade.tradingsymbol,
                    "recommendation": "Stop chasing. Set a limit order and wait."
                },
                trigger_trade_id=trigger_trade.id,
                related_trade_ids=[t.id for t in same_direction_trades]
            )

        return None

    async def _detect_tilt_spiral(
        self,
        trades: List[Trade],
        completed_trades: List[CompletedTrade],
        trigger_trade: Optional[Trade],
        thresholds: dict,
    ) -> Optional[RiskAlert]:
        """
        Detect tilt/loss spiral:
        - Increasing position sizes while losing (uses CompletedTrade for P&L)
        - Total losses exceeding a threshold in short time
        """
        caution_threshold = thresholds.get('consecutive_loss_caution', 3)

        if len(completed_trades) < caution_threshold:
            return None

        # Sort by exit_time (oldest first)
        sorted_ct = sorted(completed_trades, key=lambda ct: ct.exit_time)
        recent_ct = sorted_ct[-10:]  # Last 10 completed trades

        total_pnl = 0.0
        sizes = []
        losses_in_row = 0

        for ct in recent_ct:
            pnl = float(ct.realized_pnl or 0)
            total_pnl += pnl
            qty = ct.total_quantity or 0
            price = float(ct.avg_entry_price or 0)
            sizes.append(qty * price)

            if pnl < 0:
                losses_in_row += 1

        # Check for escalating sizes while losing
        if len(sizes) >= 4 and losses_in_row >= caution_threshold:
            recent_sizes = sizes[-4:]
            is_escalating = all(
                recent_sizes[i] < recent_sizes[i + 1]
                for i in range(len(recent_sizes) - 1)
            )

            if is_escalating and total_pnl < 0:
                return RiskAlert(
                    broker_account_id=recent_ct[0].broker_account_id,
                    pattern_type="tilt_loss_spiral",
                    severity="danger",
                    message=f"DANGER: Loss spiral detected - Increasing size while losing ₹{abs(total_pnl):,.0f}",
                    details={
                        "total_loss": float(total_pnl),
                        "consecutive_losses": losses_in_row,
                        "size_trend": "escalating",
                        "recommendation": "STOP IMMEDIATELY. You are tilting."
                    },
                    trigger_trade_id=trigger_trade.id if trigger_trade else None,
                    related_trade_ids=[str(ct.id) for ct in recent_ct[-4:]]
                )

        return None

    async def _trigger_cooldown(
        self,
        broker_account_id: UUID,
        alert: RiskAlert,
        db: AsyncSession
    ):
        """
        Automatically trigger a cooldown when danger pattern detected.
        """
        from app.models.cooldown import create_cooldown
        from app.models.user_profile import UserProfile

        try:
            # Check user preferences for cooldown duration
            profile_result = await db.execute(
                select(UserProfile).where(UserProfile.broker_account_id == broker_account_id)
            )
            profile = profile_result.scalar_one_or_none()

            duration = 15  # Default
            if profile and profile.cooldown_after_loss:
                duration = profile.cooldown_after_loss

            # Create cooldown
            cooldown = create_cooldown(
                broker_account_id=broker_account_id,
                reason=alert.pattern_type,
                duration_minutes=duration,
                can_skip=True,
                trigger_alert_id=alert.id
            )

            db.add(cooldown)
            await db.commit()
            logger.info(f"Cooldown triggered for {broker_account_id}: {alert.pattern_type} ({duration}min)")

        except Exception as e:
            logger.error(f"Failed to trigger cooldown: {e}")
