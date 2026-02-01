from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.services.retention_service import RetentionService
from app.models.broker_account import BrokerAccount
from sqlalchemy import select
import logging

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

async def send_all_eod_reports():
    """Send EOD reports to all active users at 3:30 PM IST."""
    logger.info("Starting EOD report batch...")
    
    async for db in get_db():
        try:
            # Get all active broker accounts
            result = await db.execute(
                select(BrokerAccount).where(
                    BrokerAccount.access_token.isnot(None)
                )
            )
            accounts = result.scalars().all()
            
            retention_service = RetentionService()
            
            for account in accounts:
                # TODO: Get actual user phone from user table
                # For now, use hardcoded
                user_phone = "+919011230038"  # REPLACE with actual user.phone
                
                try:
                    await retention_service.send_eod_report(
                        broker_account_id=account.id,
                        phone_number=user_phone,
                        db=db
                    )
                except Exception as e:
                    logger.error(f"EOD report failed for {account.id}: {e}")
            
            logger.info(f"EOD reports sent to {len(accounts)} users")
            
        except Exception as e:
            logger.error(f"EOD batch failed: {e}", exc_info=True)

async def send_all_morning_briefs():
    """Send morning briefs to all active users at 8:30 AM IST."""
    logger.info("Starting morning brief batch...")
    
    async for db in get_db():
        try:
            result = await db.execute(
                select(BrokerAccount).where(
                    BrokerAccount.access_token.isnot(None)
                )
            )
            accounts = result.scalars().all()
            
            retention_service = RetentionService()
            
            for account in accounts:
                user_phone = "+919011230038"  # REPLACE with actual user.phone
                
                try:
                    await retention_service.send_morning_brief(
                        broker_account_id=account.id,
                        phone_number=user_phone,
                        db=db
                    )
                except Exception as e:
                    logger.error(f"Morning brief failed for {account.id}: {e}")
            
            logger.info(f"Morning briefs sent to {len(accounts)} users")
            
        except Exception as e:
            logger.error(f"Morning brief batch failed: {e}", exc_info=True)

def start_scheduler():
    """Start scheduled tasks."""
    
    # EOD Report - 3:30 PM IST daily
    scheduler.add_job(
        send_all_eod_reports,
        CronTrigger(hour=15, minute=30, timezone="Asia/Kolkata"),
        id="eod_reports",
        replace_existing=True
    )
    
    # Morning Brief - 8:30 AM IST daily
    scheduler.add_job(
        send_all_morning_briefs,
        CronTrigger(hour=8, minute=30, timezone="Asia/Kolkata"),
        id="morning_briefs",
        replace_existing=True
    )
    
    scheduler.start()
    logger.info("Retention scheduler started")
