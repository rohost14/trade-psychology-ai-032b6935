"""
Cooldown Service

Manages trading cooldowns based on behavioral pattern detection.
Implements graduated cooldown system with multiple strategies.

Features:
- Graduated escalation (5min → 15min → 30min → 1hr → 2hr)
- Integration with notification rate limiter
- Per-trigger-type tracking
- Hard vs soft cooldowns
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from uuid import UUID
from enum import Enum
from dataclasses import dataclass
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc

from app.models.cooldown import Cooldown, create_cooldown
from app.models.risk_alert import RiskAlert
from app.models.user_profile import UserProfile
from app.services.notification_rate_limiter import (
    notification_rate_limiter,
    NotificationType
)

logger = logging.getLogger(__name__)


class CooldownStrategy(Enum):
    """Cooldown escalation strategies."""
    FIXED = "fixed"           # Same duration every time
    GRADUATED = "graduated"   # Increases with violations
    SMART = "smart"          # Based on emotional state/patterns


class CooldownType(Enum):
    """Type of cooldown (hard blocks trading, soft just warns)."""
    HARD = "hard"
    SOFT = "soft"


@dataclass
class CooldownConfig:
    """Configuration for cooldown behavior."""
    strategy: CooldownStrategy = CooldownStrategy.GRADUATED
    base_duration_minutes: int = 5
    max_duration_minutes: int = 120
    escalation_factor: float = 2.0  # Multiply duration on each violation
    reset_after_hours: int = 24     # Reset escalation after this period


@dataclass
class CooldownResult:
    """Result of a cooldown check or creation."""
    is_active: bool
    cooldown_id: Optional[str] = None
    expires_at: Optional[datetime] = None
    reason: Optional[str] = None
    violations_today: int = 0
    current_duration_minutes: int = 0
    can_skip: bool = True
    message: Optional[str] = None


class CooldownService:
    """
    Manages cooldown periods for traders.

    Features:
    - Hard cooldowns (trading blocked)
    - Soft cooldowns (warning only)
    - Graduated escalation (5min → 15min → 30min → 1hr → 2hr)
    - Per-trigger-type tracking
    - Integration with notification system
    """

    # Default escalation ladder (in minutes)
    ESCALATION_LADDER = [5, 15, 30, 60, 120]

    # Trigger types that warrant cooldowns
    COOLDOWN_TRIGGERS = {
        "loss_limit_breach": CooldownType.HARD,
        "revenge_trading": CooldownType.SOFT,
        "overtrading": CooldownType.SOFT,
        "tilt": CooldownType.SOFT,
        "fomo": CooldownType.SOFT,
        "loss_chasing": CooldownType.SOFT,
        "max_position_exceeded": CooldownType.HARD,
        "emotional_trading": CooldownType.SOFT,
    }

    def __init__(self, config: Optional[CooldownConfig] = None):
        self.config = config or CooldownConfig()
        # In-memory violation counter: (account_id, trigger) -> count
        self._violation_counts: Dict[Tuple[str, str], int] = {}
        self._last_violation: Dict[Tuple[str, str], datetime] = {}

    async def check_cooldown(
        self,
        db: AsyncSession,
        broker_account_id: UUID
    ) -> CooldownResult:
        """
        Check if a broker account is currently in cooldown.

        Returns:
            CooldownResult with current status
        """
        now = datetime.now(timezone.utc)

        # Query for active cooldowns (not skipped and not expired)
        query = select(Cooldown).where(
            and_(
                Cooldown.broker_account_id == broker_account_id,
                Cooldown.expires_at > now,
                Cooldown.skipped == False
            )
        ).order_by(Cooldown.expires_at.desc())

        result = await db.execute(query)
        active_cooldown = result.scalars().first()  # most recent active cooldown

        if active_cooldown:
            return CooldownResult(
                is_active=True,
                cooldown_id=str(active_cooldown.id),
                expires_at=active_cooldown.expires_at,
                reason=active_cooldown.reason,
                current_duration_minutes=active_cooldown.duration_minutes,
                can_skip=active_cooldown.can_skip,
                message=active_cooldown.message
            )

        return CooldownResult(is_active=False)

    async def start_cooldown(
        self,
        db: AsyncSession,
        broker_account_id: UUID,
        trigger_reason: str,
        force_hard: bool = False,
        custom_duration_minutes: Optional[int] = None,
        custom_message: Optional[str] = None,
        trigger_alert_id: Optional[UUID] = None
    ) -> CooldownResult:
        """
        Start a cooldown for a broker account with graduated escalation.

        Args:
            db: Database session
            broker_account_id: Account to cooldown
            trigger_reason: What triggered the cooldown
            force_hard: Force hard cooldown regardless of trigger type
            custom_duration_minutes: Override calculated duration
            custom_message: Custom message to show user
            trigger_alert_id: Alert that triggered this cooldown

        Returns:
            CooldownResult with new cooldown details
        """
        account_id_str = str(broker_account_id)

        # Determine cooldown type
        cooldown_type = CooldownType.HARD if force_hard else self.COOLDOWN_TRIGGERS.get(
            trigger_reason, CooldownType.SOFT
        )

        # Calculate duration based on strategy
        if custom_duration_minutes:
            duration_minutes = custom_duration_minutes
        elif self.config.strategy == CooldownStrategy.SMART:
            duration_minutes = await self._calculate_smart_duration(
                db, broker_account_id, trigger_reason
            )
        else:
            duration_minutes = self._calculate_duration(account_id_str, trigger_reason)

        # Determine if can skip (hard cooldowns can't be skipped)
        can_skip = cooldown_type != CooldownType.HARD

        # Create cooldown using existing factory function
        cooldown = create_cooldown(
            broker_account_id=broker_account_id,
            reason=trigger_reason,
            duration_minutes=duration_minutes,
            can_skip=can_skip,
            message=custom_message,
            trigger_alert_id=trigger_alert_id,
            meta_data={
                "escalation_level": self._get_escalation_level(account_id_str, trigger_reason) + 1,
                "cooldown_type": cooldown_type.value,
                "violation_count": self._get_violation_count(account_id_str, trigger_reason) + 1
            }
        )

        db.add(cooldown)
        await db.commit()
        await db.refresh(cooldown)

        # Record violation for graduated escalation
        self._record_violation(account_id_str, trigger_reason)

        # Send notification (respects rate limits)
        await self._send_cooldown_notification(
            account_id_str, trigger_reason, duration_minutes, cooldown_type
        )

        logger.info(
            f"Started {cooldown_type.value} cooldown for account {broker_account_id}: "
            f"{trigger_reason}, {duration_minutes} minutes (level {self._get_escalation_level(account_id_str, trigger_reason)})"
        )

        return CooldownResult(
            is_active=True,
            cooldown_id=str(cooldown.id),
            expires_at=cooldown.expires_at,
            reason=trigger_reason,
            current_duration_minutes=duration_minutes,
            violations_today=self._get_violation_count(account_id_str, trigger_reason),
            can_skip=can_skip,
            message=cooldown.message
        )

    async def end_cooldown(
        self,
        db: AsyncSession,
        cooldown_id: str,
        skip: bool = True
    ) -> bool:
        """
        End a cooldown early by skipping it.

        Args:
            db: Database session
            cooldown_id: ID of cooldown to end
            skip: Mark as skipped (for audit)

        Returns:
            True if ended successfully
        """
        query = select(Cooldown).where(Cooldown.id == UUID(cooldown_id))
        result = await db.execute(query)
        cooldown = result.scalar_one_or_none()

        if not cooldown:
            return False

        if not cooldown.can_skip:
            logger.warning(f"Attempted to skip non-skippable cooldown {cooldown_id}")
            return False

        cooldown.skipped = True
        cooldown.skipped_at = datetime.now(timezone.utc)

        await db.commit()
        logger.info(f"Cooldown {cooldown_id} skipped")
        return True

    async def get_cooldown_history(
        self,
        db: AsyncSession,
        broker_account_id: UUID,
        days: int = 30
    ) -> List[Dict]:
        """Get cooldown history for an account."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        query = select(Cooldown).where(
            and_(
                Cooldown.broker_account_id == broker_account_id,
                Cooldown.created_at > cutoff
            )
        ).order_by(Cooldown.created_at.desc())

        result = await db.execute(query)
        cooldowns = result.scalars().all()

        return [c.to_dict() for c in cooldowns]

    async def get_escalation_status(
        self,
        user_id: int,
        trigger_reason: str
    ) -> Dict:
        """Get current escalation status for a trigger type."""
        count = self._get_violation_count(user_id, trigger_reason)
        level = min(count, len(self.ESCALATION_LADDER) - 1)
        current_duration = self.ESCALATION_LADDER[level]
        next_duration = self.ESCALATION_LADDER[min(level + 1, len(self.ESCALATION_LADDER) - 1)]

        return {
            "trigger": trigger_reason,
            "violation_count_24h": count,
            "current_escalation_level": level + 1,
            "max_escalation_level": len(self.ESCALATION_LADDER),
            "current_duration_minutes": current_duration,
            "next_duration_minutes": next_duration,
            "at_max_escalation": level >= len(self.ESCALATION_LADDER) - 1
        }

    def _calculate_duration(self, user_id: int, trigger_reason: str) -> int:
        """Calculate cooldown duration based on strategy."""
        if self.config.strategy == CooldownStrategy.FIXED:
            return self.config.base_duration_minutes

        elif self.config.strategy == CooldownStrategy.GRADUATED:
            level = self._get_escalation_level(user_id, trigger_reason)
            if level < len(self.ESCALATION_LADDER):
                return self.ESCALATION_LADDER[level]
            return self.ESCALATION_LADDER[-1]  # Max duration

        elif self.config.strategy == CooldownStrategy.SMART:
            # Handled by _calculate_smart_duration (async) in start_cooldown.
            # This sync path is only reached if called directly outside start_cooldown.
            level = self._get_escalation_level(user_id, trigger_reason)
            if level < len(self.ESCALATION_LADDER):
                return self.ESCALATION_LADDER[level]
            return self.ESCALATION_LADDER[-1]

        return self.config.base_duration_minutes

    async def _calculate_smart_duration(
        self,
        db: AsyncSession,
        broker_account_id: UUID,
        trigger_reason: str,
    ) -> int:
        """
        SMART cooldown: adapts duration to the trader's current emotional state.

        Logic (in priority order):
        1. Session meltdown or danger-level consecutive-loss streak in last 30 min
           → 2× the graduated ladder value (maximum distress).
        2. 3 or more patterns fired in the last 30 min (tilt storm)
           → 1.5× the graduated ladder value.
        3. PersonalizationService has a learned personal_revenge_window_minutes
           → use max(graduated, revenge_window × 1.5) so the cooldown always
              outlasts the trader's own revenge window.
        4. Fall through to plain graduated (explicit, never silent).
        """
        account_id_str = str(broker_account_id)
        graduated = self._calculate_duration(account_id_str, trigger_reason)

        window_start = datetime.now(timezone.utc) - timedelta(minutes=30)

        # ── 1 & 2: Query recent alerts ─────────────────────────────────────
        try:
            result = await db.execute(
                select(RiskAlert)
                .where(
                    RiskAlert.broker_account_id == broker_account_id,
                    RiskAlert.detected_at >= window_start,
                )
                .order_by(desc(RiskAlert.detected_at))
                .limit(20)
            )
            recent_alerts = result.scalars().all()
        except Exception:
            recent_alerts = []

        HIGH_DISTRESS_TYPES = {"session_meltdown", "consecutive_loss_streak", "tilt_loss_spiral"}
        has_high_distress = any(
            a.pattern_type in HIGH_DISTRESS_TYPES and a.severity == "danger"
            for a in recent_alerts
        )

        if has_high_distress:
            return min(graduated * 2, self.ESCALATION_LADDER[-1])

        if len(recent_alerts) >= 3:
            return min(int(graduated * 1.5), self.ESCALATION_LADDER[-1])

        # ── 3: Personalized revenge window ─────────────────────────────────
        try:
            prof_result = await db.execute(
                select(UserProfile).where(UserProfile.broker_account_id == broker_account_id)
            )
            profile = prof_result.scalar_one_or_none()
            if profile and profile.detected_patterns:
                intervention = profile.detected_patterns.get("intervention_timing", {})
                revenge_window = intervention.get("personal_revenge_window_minutes")
                if revenge_window and revenge_window > 0:
                    personal_min = int(revenge_window * 1.5)
                    return max(graduated, personal_min)
        except Exception:
            pass

        # ── 4: Plain graduated ─────────────────────────────────────────────
        return graduated

    def _get_escalation_level(self, user_id: int, trigger_reason: str) -> int:
        """Get current escalation level based on recent violations."""
        count = self._get_violation_count(user_id, trigger_reason)
        return min(count, len(self.ESCALATION_LADDER) - 1)

    def _get_violation_count(self, user_id: int, trigger_reason: str) -> int:
        """Get violation count in the reset window."""
        key = (user_id, trigger_reason)

        # Check if we need to reset (violations older than reset window)
        if key in self._last_violation:
            elapsed = datetime.now(timezone.utc) - self._last_violation[key]
            if elapsed.total_seconds() > self.config.reset_after_hours * 3600:
                self._violation_counts[key] = 0

        return self._violation_counts.get(key, 0)

    def _record_violation(self, user_id: int, trigger_reason: str):
        """Record a violation for escalation tracking."""
        key = (user_id, trigger_reason)
        self._violation_counts[key] = self._violation_counts.get(key, 0) + 1
        self._last_violation[key] = datetime.now(timezone.utc)

    def reset_violations(self, user_id: int, trigger_reason: Optional[str] = None):
        """
        Reset violation counts for a user.

        Args:
            user_id: User to reset
            trigger_reason: Specific trigger to reset, or None for all
        """
        if trigger_reason:
            key = (user_id, trigger_reason)
            self._violation_counts.pop(key, None)
            self._last_violation.pop(key, None)
        else:
            # Reset all for this user
            keys_to_remove = [k for k in self._violation_counts if k[0] == user_id]
            for key in keys_to_remove:
                del self._violation_counts[key]
                self._last_violation.pop(key, None)

        logger.info(f"Reset violations for user {user_id}, trigger: {trigger_reason or 'all'}")

    async def _send_cooldown_notification(
        self,
        account_id: str,
        trigger_reason: str,
        duration_minutes: int,
        cooldown_type: CooldownType
    ):
        """Send cooldown notification (respects rate limits)."""
        can_send, block_reason = notification_rate_limiter.can_send(
            account_id,
            NotificationType.COOLDOWN_STARTED,
        )

        if can_send:
            notification_rate_limiter.record_sent(
                account_id,
                NotificationType.COOLDOWN_STARTED,
            )
            logger.info(
                f"Cooldown notification sent: {trigger_reason} ({duration_minutes}min) "
                f"for account {account_id}, type={cooldown_type.value}"
            )
        else:
            logger.debug(f"Cooldown notification rate limited: {block_reason}")


# Global cooldown service instance
cooldown_service = CooldownService()
