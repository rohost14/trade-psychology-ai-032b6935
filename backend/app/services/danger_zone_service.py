"""
Danger Zone Service

Monitors trading activity and triggers interventions when dangerous
patterns are detected. Integrates with:
- Cooldown service (graduated cooldowns)
- Notification rate limiter (WhatsApp/push notifications)
- AI personalization (learned patterns)

Danger Zone Triggers:
1. Loss Limit Breach (CRITICAL) - Immediate hard cooldown + WhatsApp
2. Approaching Loss Limit (WARNING) - Soft warning + optional notification
3. Pattern Detection (WARNING) - Contextual intervention based on pattern
4. Consecutive Losses (GRADUATED) - Escalating cooldowns
5. Overtrading (SOFT) - Warning + suggestion
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from uuid import UUID
from dataclasses import dataclass
from enum import Enum
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

from app.models.user import User
from app.models.trade import Trade
from app.models.completed_trade import CompletedTrade
from app.models.risk_alert import RiskAlert
from app.models.user_profile import UserProfile
from app.models.broker_account import BrokerAccount
from app.services.cooldown_service import cooldown_service, CooldownResult
from app.services.notification_rate_limiter import (
    notification_rate_limiter,
    NotificationType,
    NotificationTier
)
from app.services.whatsapp_service import whatsapp_service
from app.core.trading_defaults import get_thresholds as get_trader_thresholds

logger = logging.getLogger(__name__)


class DangerLevel(Enum):
    """Danger level assessment."""
    SAFE = "safe"
    CAUTION = "caution"
    WARNING = "warning"
    DANGER = "danger"
    CRITICAL = "critical"


# Numeric severity order — string .value comparison is alphabetical and WRONG
# ('danger' < 'warning' alphabetically, but danger is MORE severe)
_LEVEL_ORDER: Dict[str, int] = {
    'safe': 0, 'caution': 1, 'warning': 2, 'danger': 3, 'critical': 4
}


def _upgrade_level(current: DangerLevel, candidate: DangerLevel) -> DangerLevel:
    """Return higher-severity level — never downgrade."""
    return candidate if _LEVEL_ORDER[candidate.value] > _LEVEL_ORDER[current.value] else current


class InterventionType(Enum):
    """Types of interventions."""
    NONE = "none"
    SOFT_WARNING = "soft_warning"           # In-app warning only
    NOTIFICATION = "notification"            # Push/WhatsApp notification
    SOFT_COOLDOWN = "soft_cooldown"          # Skippable cooldown
    HARD_COOLDOWN = "hard_cooldown"          # Cannot skip
    TRADING_BLOCK = "trading_block"          # Full block for rest of day


@dataclass
class DangerZoneStatus:
    """Current danger zone status for an account."""
    level: DangerLevel
    intervention: InterventionType
    triggers: List[str]
    message: str
    cooldown_active: bool
    cooldown_remaining_minutes: int
    daily_loss_used_percent: float
    trade_count_today: int
    consecutive_losses: int
    patterns_active: List[str]
    recommendations: List[str]
    whatsapp_sent: bool = False


@dataclass
class TriggerThresholds:
    """Configurable thresholds for danger zone triggers."""
    # Loss limits (as percentage of daily limit)
    loss_limit_warning_percent: float = 70.0
    loss_limit_danger_percent: float = 85.0
    loss_limit_critical_percent: float = 100.0

    # Trading frequency
    trades_per_15min_warning: int = 5
    trades_per_15min_danger: int = 8
    trades_per_hour_warning: int = 15
    trades_per_hour_danger: int = 25

    # Consecutive losses
    consecutive_loss_warning: int = 2
    consecutive_loss_danger: int = 3
    consecutive_loss_critical: int = 5

    # Time-based (avoid trading during bad times for user)
    # These would be personalized per user
    avoid_first_minutes: int = 0   # Skip first N minutes of market
    avoid_last_minutes: int = 15    # Skip last N minutes


class DangerZoneService:
    """
    Monitors and manages danger zone states.

    Responsibilities:
    1. Assess current danger level
    2. Trigger appropriate interventions
    3. Send notifications (respecting rate limits)
    4. Record alerts and cooldowns
    5. Track patterns for personalization
    """

    def __init__(self, thresholds: Optional[TriggerThresholds] = None):
        self.thresholds = thresholds or TriggerThresholds()

    async def assess_danger_level(
        self,
        db: AsyncSession,
        broker_account_id: UUID
    ) -> DangerZoneStatus:
        """
        Assess the current danger level for an account.

        This is the main entry point - call this periodically or after each trade.
        """
        user_id = str(broker_account_id)
        now = datetime.now(timezone.utc)
        triggers = []
        patterns_active = []
        recommendations = []

        # 1. Check current cooldown status
        cooldown_result = await cooldown_service.check_cooldown(db, broker_account_id)

        # 2. Get user profile for limits and profile-derived thresholds
        profile = await self._get_user_profile(db, broker_account_id)
        daily_loss_limit = profile.daily_loss_limit if profile else None
        trader_thresholds = get_trader_thresholds(profile)

        # 3. Calculate today's P&L
        today_pnl = await self._get_today_pnl(db, broker_account_id)
        daily_loss_used_percent = 0.0

        if daily_loss_limit and daily_loss_limit > 0:
            # Loss is negative, so we negate it
            if today_pnl < 0:
                daily_loss_used_percent = (abs(today_pnl) / daily_loss_limit) * 100

        # 4. Get recent trades
        trades_15min = await self._get_trade_count(db, broker_account_id, minutes=15)
        trades_1hr = await self._get_trade_count(db, broker_account_id, minutes=60)
        trades_today = await self._get_trade_count(db, broker_account_id, minutes=None)  # All today

        # 5. Count consecutive losses
        consecutive_losses = await self._count_consecutive_losses(db, broker_account_id)

        # 6. Check recent patterns/alerts
        recent_alerts = await self._get_recent_alerts(db, broker_account_id, minutes=30)
        patterns_active = [a.pattern_type for a in recent_alerts]

        # =======================================================================
        # DANGER LEVEL ASSESSMENT
        # =======================================================================

        level = DangerLevel.SAFE
        intervention = InterventionType.NONE

        # Check loss limit
        if daily_loss_used_percent >= 100:
            level = DangerLevel.CRITICAL
            intervention = InterventionType.HARD_COOLDOWN
            triggers.append("loss_limit_breach")
            recommendations.append("Stop trading for today. You've hit your daily loss limit.")

        elif daily_loss_used_percent >= self.thresholds.loss_limit_danger_percent:
            level = DangerLevel.DANGER
            intervention = InterventionType.NOTIFICATION
            triggers.append("approaching_loss_limit")
            recommendations.append(f"You've used {daily_loss_used_percent:.0f}% of your daily loss limit.")

        elif daily_loss_used_percent >= self.thresholds.loss_limit_warning_percent:
            level = _upgrade_level(level, DangerLevel.WARNING)
            triggers.append("loss_limit_warning")
            recommendations.append("Consider reducing position sizes.")

        # Profile-derived consecutive loss thresholds (3-tier system)
        consec_caution = trader_thresholds['consecutive_loss_caution']   # e.g. 3
        consec_danger  = trader_thresholds['consecutive_loss_danger']    # e.g. 5
        consec_critical = consec_danger + 2                              # e.g. 7

        # Check consecutive losses
        if consecutive_losses >= consec_critical:
            level = DangerLevel.CRITICAL
            intervention = InterventionType.HARD_COOLDOWN
            triggers.append("consecutive_loss_critical")
            recommendations.append(f"{consecutive_losses} consecutive losses. Take a break.")

        elif consecutive_losses >= consec_danger:
            level = _upgrade_level(level, DangerLevel.DANGER)
            if level == DangerLevel.DANGER and intervention == InterventionType.NONE:
                intervention = InterventionType.SOFT_COOLDOWN
            triggers.append("consecutive_loss_danger")
            recommendations.append("Consider pausing to reset mentally.")

        elif consecutive_losses >= consec_caution:
            level = _upgrade_level(level, DangerLevel.WARNING)
            triggers.append("consecutive_loss_warning")

        # Profile-derived overtrading thresholds
        burst_warn   = trader_thresholds['burst_trades_per_15min']       # e.g. 7
        burst_danger = int(burst_warn * 1.6)                             # e.g. 11

        # Check overtrading
        if trades_15min >= burst_danger:
            level = _upgrade_level(level, DangerLevel.DANGER)
            if level == DangerLevel.DANGER and intervention == InterventionType.NONE:
                intervention = InterventionType.SOFT_COOLDOWN
            triggers.append("overtrading_danger")
            recommendations.append("Too many trades. Slow down.")

        elif trades_15min >= burst_warn:
            level = _upgrade_level(level, DangerLevel.WARNING)
            triggers.append("overtrading_warning")

        # Check pattern-based triggers
        danger_patterns = {"revenge_trading", "tilt", "fomo", "loss_chasing"}
        if any(p in danger_patterns for p in patterns_active):
            level = _upgrade_level(level, DangerLevel.DANGER)
            if level == DangerLevel.DANGER and intervention == InterventionType.NONE:
                intervention = InterventionType.NOTIFICATION
            for pattern in patterns_active:
                if pattern in danger_patterns:
                    triggers.append(f"pattern_{pattern}")

        caution_patterns = {"overconfidence", "anchoring", "round_number_bias"}
        if any(p in caution_patterns for p in patterns_active):
            level = _upgrade_level(level, DangerLevel.CAUTION)
            for pattern in patterns_active:
                if pattern in caution_patterns:
                    triggers.append(f"pattern_{pattern}")

        # Build message
        message = self._build_message(level, triggers, daily_loss_used_percent)

        return DangerZoneStatus(
            level=level,
            intervention=intervention,
            triggers=triggers,
            message=message,
            cooldown_active=cooldown_result.is_active,
            cooldown_remaining_minutes=cooldown_result.current_duration_minutes if cooldown_result.is_active else 0,
            daily_loss_used_percent=daily_loss_used_percent,
            trade_count_today=trades_today,
            consecutive_losses=consecutive_losses,
            patterns_active=patterns_active,
            recommendations=recommendations
        )

    async def trigger_intervention(
        self,
        db: AsyncSession,
        broker_account_id: UUID,
        status: DangerZoneStatus
    ) -> Dict:
        """
        Trigger the appropriate intervention based on danger status.

        Returns dict with actions taken.
        """
        actions = {
            "cooldown_started": False,
            "notification_sent": False,
            "whatsapp_sent": False,
            "alert_created": False
        }

        # Skip if no intervention needed
        if status.intervention == InterventionType.NONE:
            return actions

        primary_trigger = status.triggers[0] if status.triggers else "manual"

        user_id = str(broker_account_id)

        # Handle cooldowns
        if status.intervention in [InterventionType.HARD_COOLDOWN, InterventionType.SOFT_COOLDOWN]:
            force_hard = status.intervention == InterventionType.HARD_COOLDOWN

            cooldown_result = await cooldown_service.start_cooldown(
                db=db,
                broker_account_id=broker_account_id,
                trigger_reason=primary_trigger,
                force_hard=force_hard,
                custom_message=status.message
            )
            actions["cooldown_started"] = cooldown_result.is_active

        # Handle notifications
        if status.intervention in [InterventionType.NOTIFICATION, InterventionType.HARD_COOLDOWN]:
            # Determine notification type based on trigger
            notification_type = self._get_notification_type(primary_trigger)

            can_send, reason = notification_rate_limiter.can_send(
                user_id, notification_type
            )

            if can_send:
                notification_rate_limiter.record_sent(user_id, notification_type)
                actions["notification_sent"] = True

                # For critical triggers, also send WhatsApp
                if status.level == DangerLevel.CRITICAL:
                    whatsapp_sent = await self._send_whatsapp_notification(
                        user_id, broker_account_id, status, db
                    )
                    actions["whatsapp_sent"] = whatsapp_sent
            else:
                logger.debug(f"Notification rate limited: {reason}")

        return actions

    def _get_notification_type(self, trigger: str) -> NotificationType:
        """Map trigger to notification type."""
        mapping = {
            "loss_limit_breach": NotificationType.LOSS_LIMIT_BREACHED,
            "approaching_loss_limit": NotificationType.APPROACHING_LOSS_LIMIT,
            "consecutive_loss_critical": NotificationType.LOSS_LIMIT_BREACHED,
            "consecutive_loss_danger": NotificationType.TILT_DETECTED,
            "overtrading_danger": NotificationType.OVERTRADING_DETECTED,
            "pattern_revenge_trading": NotificationType.REVENGE_TRADING_DETECTED,
            "pattern_tilt": NotificationType.TILT_DETECTED,
            "pattern_fomo": NotificationType.FOMO_DETECTED,
            "pattern_loss_chasing": NotificationType.LOSS_CHASING_DETECTED,
        }
        return mapping.get(trigger, NotificationType.PATTERN_INSIGHT)

    async def _send_whatsapp_notification(
        self,
        user_id: str,
        broker_account_id: UUID,
        status: DangerZoneStatus,
        db: Optional[AsyncSession] = None
    ) -> bool:
        """
        Send WhatsApp notification for critical alerts via Twilio.
        """
        # Check guardian_enabled before sending
        try:
            profile = await self._get_user_profile(db, broker_account_id) if db else None
            if profile and not profile.guardian_enabled:
                logger.debug(f"Guardian not enabled for account {broker_account_id}, skipping WhatsApp")
                return False
        except Exception:
            pass

        # Check if we can send (critical tier has no rate limit, but we still track)
        can_send, _ = notification_rate_limiter.can_send(
            user_id,
            NotificationType.LOSS_LIMIT_BREACHED  # Critical tier
        )

        if not can_send:
            return False

        try:
            # Get broker account to get phone numbers
            if db:
                result = await db.execute(
                    select(BrokerAccount).where(BrokerAccount.id == broker_account_id)
                )
                broker_account = result.scalar_one_or_none()

                # Load user for guardian contact
                user = await db.get(User, broker_account.user_id) if broker_account and broker_account.user_id else None
                guardian_phone = user.guardian_phone if user else None

                if broker_account and guardian_phone:
                    # Format message based on danger status
                    message = self._format_whatsapp_message(status, broker_account)

                    try:
                        success = await whatsapp_service.send_message(
                            to_number=guardian_phone,
                            content=message
                        )

                        if success:
                            notification_rate_limiter.record_sent(
                                user_id,
                                NotificationType.LOSS_LIMIT_BREACHED
                            )
                        return success

                    except Exception as e:
                        logger.error(f"Failed to send WhatsApp: {e}")
                        return False
                else:
                    logger.warning(f"No guardian phone configured for account {broker_account_id}")
                    return False
            else:
                logger.warning("No database session provided for WhatsApp notification")
                return False

        except Exception as e:
            logger.error(f"Error in WhatsApp notification: {e}")
            return False

    def _format_whatsapp_message(
        self,
        status: DangerZoneStatus,
        broker_account: BrokerAccount
    ) -> str:
        """Format WhatsApp message for danger zone alert."""
        header = "🚨 *TRADEMENTOR DANGER ZONE ALERT* 🚨\n\n"

        level_emoji = {
            DangerLevel.CRITICAL: "🔴",
            DangerLevel.DANGER: "🟠",
            DangerLevel.WARNING: "🟡",
        }

        emoji = level_emoji.get(status.level, "⚠️")

        message = f"{header}"
        message += f"{emoji} *Status: {status.level.value.upper()}*\n\n"

        # Add triggers
        if status.triggers:
            message += "*Triggers:*\n"
            for trigger in status.triggers[:3]:  # Limit to 3
                message += f"• {trigger.replace('_', ' ').title()}\n"
            message += "\n"

        # Add key metrics
        message += f"📊 *Metrics:*\n"
        message += f"• Daily Loss: {status.daily_loss_used_percent:.0f}% used\n"
        message += f"• Trades Today: {status.trade_count_today}\n"
        message += f"• Consecutive Losses: {status.consecutive_losses}\n\n"

        # Add recommendation
        if status.recommendations:
            message += f"💡 *Action:* {status.recommendations[0]}\n\n"

        # Add cooldown info
        if status.cooldown_active:
            message += f"⏱️ *Cooldown Active:* {status.cooldown_remaining_minutes} minutes remaining\n\n"

        # Footer
        user_id = broker_account.broker_user_id or "Unknown"
        message += f"Account: {user_id}\n"
        message += f"Time: {datetime.now(timezone.utc).strftime('%I:%M %p')} UTC"

        return message

    def _build_message(
        self,
        level: DangerLevel,
        triggers: List[str],
        loss_percent: float
    ) -> str:
        """Build human-readable message for the danger level."""
        if level == DangerLevel.CRITICAL:
            return f"🚨 STOP! You've exceeded your limits. Take a mandatory break."
        elif level == DangerLevel.DANGER:
            return f"⚠️ Warning: {loss_percent:.0f}% of daily loss limit used. Consider stopping."
        elif level == DangerLevel.WARNING:
            return f"⚡ Caution: Risky trading patterns detected. Trade carefully."
        elif level == DangerLevel.CAUTION:
            return f"💡 Note: Be mindful of your trading decisions."
        else:
            return "✅ Trading within normal parameters."

    async def _get_user_profile(
        self,
        db: AsyncSession,
        broker_account_id: UUID
    ) -> Optional[UserProfile]:
        """Get user profile with trading limits."""
        result = await db.execute(
            select(UserProfile).where(UserProfile.broker_account_id == broker_account_id)
        )
        return result.scalar_one_or_none()

    async def _get_today_pnl(
        self,
        db: AsyncSession,
        broker_account_id: UUID
    ) -> float:
        """Get total P&L for today using CompletedTrade.realized_pnl (real P&L)."""
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        result = await db.execute(
            select(func.sum(CompletedTrade.realized_pnl)).where(
                and_(
                    CompletedTrade.broker_account_id == broker_account_id,
                    CompletedTrade.exit_time >= today_start
                )
            )
        )
        total = result.scalar()
        return float(total) if total else 0.0

    async def _get_trade_count(
        self,
        db: AsyncSession,
        broker_account_id: UUID,
        minutes: Optional[int] = None
    ) -> int:
        """Get trade count in time window."""
        now = datetime.now(timezone.utc)
        if minutes:
            cutoff = now - timedelta(minutes=minutes)
        else:
            cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # Ensure cutoff is timezone-aware if Trade.order_timestamp is aware
        # In this project, all timestamps should be UTC aware.

        result = await db.execute(
            select(func.count(Trade.id)).where(
                and_(
                    Trade.broker_account_id == broker_account_id,
                    Trade.status == "COMPLETE",
                    Trade.order_timestamp >= cutoff
                )
            )
        )
        return result.scalar() or 0

    async def _count_consecutive_losses(
        self,
        db: AsyncSession,
        broker_account_id: UUID
    ) -> int:
        """Count consecutive losing completed trades from most recent (uses real P&L)."""
        result = await db.execute(
            select(CompletedTrade).where(
                and_(
                    CompletedTrade.broker_account_id == broker_account_id,
                    CompletedTrade.realized_pnl.isnot(None)
                )
            ).order_by(CompletedTrade.exit_time.desc()).limit(10)
        )
        completed_trades = result.scalars().all()

        consecutive = 0
        for ct in completed_trades:
            if float(ct.realized_pnl) < 0:
                consecutive += 1
            else:
                break

        return consecutive

    async def _get_recent_alerts(
        self,
        db: AsyncSession,
        broker_account_id: UUID,
        minutes: int = 30
    ) -> List[RiskAlert]:
        """Get recent risk alerts."""
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)

        result = await db.execute(
            select(RiskAlert).where(
                and_(
                    RiskAlert.broker_account_id == broker_account_id,
                    RiskAlert.detected_at >= cutoff
                )
            )
        )
        return result.scalars().all()


# Global service instance
danger_zone_service = DangerZoneService()
