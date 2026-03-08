"""
Notification Rate Limiter

Controls the frequency of notifications to prevent alert fatigue.
Implements tiered rate limiting based on notification severity.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass, field
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class NotificationTier(Enum):
    """Notification priority tiers with different rate limits."""
    CRITICAL = "critical"      # No rate limit - always send
    WARNING = "warning"        # Max 3/hour, 10/day
    INFORMATIONAL = "info"     # Max 1/4hours, 5/day
    DIGEST = "digest"          # Max 1/day (bundled notifications)


class NotificationType(Enum):
    """Types of notifications with their assigned tiers."""
    # Critical - Always sent immediately
    LOSS_LIMIT_BREACHED = ("loss_limit_breached", NotificationTier.CRITICAL)
    MAX_POSITION_EXCEEDED = ("max_position_exceeded", NotificationTier.CRITICAL)
    TOKEN_EXPIRED = ("token_expired", NotificationTier.CRITICAL)
    ACCOUNT_LOCKED = ("account_locked", NotificationTier.CRITICAL)

    # Warning - Rate limited
    APPROACHING_LOSS_LIMIT = ("approaching_loss_limit", NotificationTier.WARNING)
    REVENGE_TRADING_DETECTED = ("revenge_trading", NotificationTier.WARNING)
    OVERTRADING_DETECTED = ("overtrading", NotificationTier.WARNING)
    TILT_DETECTED = ("tilt_detected", NotificationTier.WARNING)
    FOMO_DETECTED = ("fomo_detected", NotificationTier.WARNING)
    LOSS_CHASING_DETECTED = ("loss_chasing", NotificationTier.WARNING)
    COOLDOWN_STARTED = ("cooldown_started", NotificationTier.WARNING)

    # Informational - Heavily rate limited
    WIN_STREAK = ("win_streak", NotificationTier.INFORMATIONAL)
    JOURNAL_REMINDER = ("journal_reminder", NotificationTier.INFORMATIONAL)
    PATTERN_INSIGHT = ("pattern_insight", NotificationTier.INFORMATIONAL)
    GOAL_PROGRESS = ("goal_progress", NotificationTier.INFORMATIONAL)

    # Digest - Once per day
    DAILY_SUMMARY = ("daily_summary", NotificationTier.DIGEST)
    WEEKLY_SUMMARY = ("weekly_summary", NotificationTier.DIGEST)

    def __init__(self, type_name: str, tier: NotificationTier):
        self.type_name = type_name
        self.tier = tier


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting a notification tier."""
    max_per_hour: int
    max_per_day: int
    min_interval_seconds: int  # Minimum time between same notification type


@dataclass
class NotificationRecord:
    """Record of a sent notification."""
    notification_type: str
    sent_at: datetime
    tier: NotificationTier
    account_id: str


class NotificationRateLimiter:
    """
    Manages rate limiting for notifications.

    Features:
    - Tiered rate limiting (Critical, Warning, Info, Digest)
    - Per-user tracking
    - Per-notification-type cooldowns
    - Configurable limits
    """

    # Default rate limit configurations by tier
    DEFAULT_CONFIGS: Dict[NotificationTier, RateLimitConfig] = {
        NotificationTier.CRITICAL: RateLimitConfig(
            max_per_hour=999,  # Unlimited
            max_per_day=999,
            min_interval_seconds=0
        ),
        NotificationTier.WARNING: RateLimitConfig(
            max_per_hour=3,
            max_per_day=10,
            min_interval_seconds=300  # 5 minutes between same type
        ),
        NotificationTier.INFORMATIONAL: RateLimitConfig(
            max_per_hour=1,
            max_per_day=5,
            min_interval_seconds=14400  # 4 hours between same type
        ),
        NotificationTier.DIGEST: RateLimitConfig(
            max_per_hour=1,
            max_per_day=1,
            min_interval_seconds=86400  # Once per day
        ),
    }

    def __init__(self):
        # In-memory storage: account_id (str) -> list of notification records
        self._records: Dict[str, List[NotificationRecord]] = defaultdict(list)
        # Custom configs per user
        self._user_configs: Dict[str, Dict[NotificationTier, RateLimitConfig]] = {}
        # Last notification time per type per user
        self._last_sent: Dict[Tuple[str, str], datetime] = {}

    def set_user_config(
        self,
        account_id: str,
        tier: NotificationTier,
        config: RateLimitConfig
    ):
        """Set custom rate limit config for a user and tier."""
        if account_id not in self._user_configs:
            self._user_configs[account_id] = {}
        self._user_configs[account_id][tier] = config
        logger.info(f"Set custom rate limit for account {account_id}, tier {tier.value}")

    def get_config(self, account_id: str, tier: NotificationTier) -> RateLimitConfig:
        """Get rate limit config for a user and tier."""
        if account_id in self._user_configs and tier in self._user_configs[account_id]:
            return self._user_configs[account_id][tier]
        return self.DEFAULT_CONFIGS[tier]

    def can_send(
        self,
        account_id: str,
        notification_type: NotificationType
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if a notification can be sent.

        Returns:
            Tuple of (can_send, reason_if_blocked)
        """
        # Ensure account_id is string
        account_id = str(account_id)
        
        tier = notification_type.tier
        config = self.get_config(account_id, tier)
        type_name = notification_type.type_name
        now = datetime.now(timezone.utc)

        # Critical notifications always allowed
        if tier == NotificationTier.CRITICAL:
            return True, None

        # Check minimum interval for same notification type
        last_key = (account_id, type_name)
        if last_key in self._last_sent:
            elapsed = (now - self._last_sent[last_key]).total_seconds()
            if elapsed < config.min_interval_seconds:
                remaining = int(config.min_interval_seconds - elapsed)
                return False, f"Same notification type sent recently. Wait {remaining}s"

        # Get recent records for this user
        user_records = self._records.get(account_id, [])

        # Filter to this tier
        tier_records = [r for r in user_records if r.tier == tier]

        # Check hourly limit
        hour_ago = now - timedelta(hours=1)
        hourly_count = len([r for r in tier_records if r.sent_at > hour_ago])
        if hourly_count >= config.max_per_hour:
            return False, f"Hourly limit reached ({config.max_per_hour}/{tier.value})"

        # Check daily limit
        day_ago = now - timedelta(days=1)
        daily_count = len([r for r in tier_records if r.sent_at > day_ago])
        if daily_count >= config.max_per_day:
            return False, f"Daily limit reached ({config.max_per_day}/{tier.value})"

        return True, None

    def record_sent(
        self,
        account_id: str,
        notification_type: NotificationType
    ):
        """Record that a notification was sent."""
        # Ensure account_id is string
        account_id = str(account_id)
        
        now = datetime.now(timezone.utc)
        type_name = notification_type.type_name

        record = NotificationRecord(
            notification_type=type_name,
            sent_at=now,
            tier=notification_type.tier,
            account_id=account_id
        )

        self._records[account_id].append(record)
        self._last_sent[(account_id, type_name)] = now

        # Cleanup old records (older than 24 hours)
        self._cleanup_old_records(account_id)

        logger.debug(f"Recorded notification: {type_name} for account {account_id}")

    def _cleanup_old_records(self, account_id: str):
        """Remove records older than 24 hours."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        if account_id in self._records:
            self._records[account_id] = [
                r for r in self._records[account_id]
                if r.sent_at > cutoff
            ]

    def get_notification_stats(self, account_id: str) -> Dict:
        """Get notification statistics for a user."""
        account_id = str(account_id)
        now = datetime.now(timezone.utc)
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)

        records = self._records.get(account_id, [])

        stats = {
            "total_24h": len([r for r in records if r.sent_at > day_ago]),
            "by_tier": {},
            "by_type": {}
        }

        for tier in NotificationTier:
            tier_records = [r for r in records if r.tier == tier]
            config = self.get_config(account_id, tier)

            hourly = len([r for r in tier_records if r.sent_at > hour_ago])
            daily = len([r for r in tier_records if r.sent_at > day_ago])

            stats["by_tier"][tier.value] = {
                "hourly": hourly,
                "hourly_limit": config.max_per_hour,
                "daily": daily,
                "daily_limit": config.max_per_day,
            }

        # Count by notification type
        for record in records:
            if record.sent_at > day_ago:
                if record.notification_type not in stats["by_type"]:
                    stats["by_type"][record.notification_type] = 0
                stats["by_type"][record.notification_type] += 1

        return stats

    def reset_user_limits(self, account_id: str):
        """Reset all records for a user."""
        account_id = str(account_id)
        self._records[account_id] = []
        keys_to_remove = [k for k in self._last_sent if k[0] == account_id]
        for key in keys_to_remove:
            del self._last_sent[key]
        logger.info(f"Reset notification limits for account {account_id}")


# Global rate limiter instance
notification_rate_limiter = NotificationRateLimiter()
