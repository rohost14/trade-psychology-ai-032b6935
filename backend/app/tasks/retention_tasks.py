"""
Retention Tasks Scheduler

Runs via APScheduler (AsyncIOScheduler) started in app lifespan.

Scheduling approach:
- Checks every minute for users whose custom report time matches current IST time
- Default: EOD at 16:00 IST, Morning brief at 08:30 IST
- Users can override times in their profile settings
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.services.retention_service import RetentionService
from app.models.user import User
from app.models.broker_account import BrokerAccount
from app.models.user_profile import UserProfile
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")

scheduler = AsyncIOScheduler()

# Default report times (IST) — used when user hasn't set a custom time
DEFAULT_EOD_TIME = "16:00"
DEFAULT_MORNING_TIME = "08:30"


async def _dispatch_reports(report_type: str):
    """
    Dispatch reports to all users whose configured time matches now (IST).
    Runs every minute and filters users by eod_report_time / morning_brief_time.

    report_type: 'eod' | 'morning'
    """
    now_ist = datetime.now(IST)
    current_time = now_ist.strftime("%H:%M")

    logger.info(f"[{report_type.upper()}] Tick at {current_time} IST — checking user report times")

    async for db in get_db():
        try:
            # Get all active accounts with their profiles
            result = await db.execute(
                select(BrokerAccount, UserProfile)
                .outerjoin(UserProfile, BrokerAccount.id == UserProfile.broker_account_id)
                .where(BrokerAccount.access_token.isnot(None))
            )
            rows = result.all()

            retention_service = RetentionService()
            sent_count = 0

            for account, profile in rows:
                # Determine this user's configured time (or default)
                if report_type == "eod":
                    user_time = (profile.eod_report_time if profile and profile.eod_report_time else DEFAULT_EOD_TIME)
                else:
                    user_time = (profile.morning_brief_time if profile and profile.morning_brief_time else DEFAULT_MORNING_TIME)

                # Only send if this user's time matches current minute
                if user_time != current_time:
                    continue

                user = await db.get(User, account.user_id) if account.user_id else None
                user_phone = user.guardian_phone if user else None
                if not user_phone:
                    logger.info(f"No guardian phone for account {account.id}, skipping")
                    continue

                try:
                    if report_type == "eod":
                        await retention_service.send_eod_report(
                            broker_account_id=account.id,
                            phone_number=user_phone,
                            db=db
                        )
                    else:
                        await retention_service.send_morning_brief(
                            broker_account_id=account.id,
                            phone_number=user_phone,
                            db=db
                        )
                    sent_count += 1
                except Exception as e:
                    logger.error(f"{report_type.upper()} report failed for {account.id}: {e}")

            if sent_count:
                logger.info(f"{report_type.upper()} reports sent to {sent_count} user(s) at {current_time}")

        except Exception as e:
            logger.error(f"{report_type.upper()} dispatch batch failed: {e}", exc_info=True)


async def dispatch_eod_reports():
    """Called every minute to send EOD reports to users whose time matches now."""
    await _dispatch_reports("eod")


async def dispatch_morning_briefs():
    """Called every minute to send morning briefs to users whose time matches now."""
    await _dispatch_reports("morning")


def start_scheduler():
    """Start scheduled tasks. Runs every minute to support per-user delivery times."""

    # Check every minute for EOD reports (users get report at THEIR configured time, default 16:00 IST)
    scheduler.add_job(
        dispatch_eod_reports,
        CronTrigger(minute="*", timezone="Asia/Kolkata"),
        id="eod_reports",
        replace_existing=True
    )

    # Check every minute for morning briefs (users get brief at THEIR configured time, default 08:30 IST)
    scheduler.add_job(
        dispatch_morning_briefs,
        CronTrigger(minute="*", timezone="Asia/Kolkata"),
        id="morning_briefs",
        replace_existing=True
    )

    scheduler.start()
    logger.info(f"Retention scheduler started. EOD default: {DEFAULT_EOD_TIME} IST, Morning default: {DEFAULT_MORNING_TIME} IST")
