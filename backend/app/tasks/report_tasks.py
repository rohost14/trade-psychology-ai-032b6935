"""
Report Tasks (Celery)

Scheduled tasks for:
- End of Day reports (3:30 PM for equity, 11:45 PM for commodity)
- Morning prep messages (8:30 AM)
- Weekly summaries
"""

import asyncio
import logging
from uuid import UUID
from datetime import datetime, timezone

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.services.retention_service import RetentionService
from app.models.user import User
from app.models.broker_account import BrokerAccount
from app.models.goal import Goal
from sqlalchemy import select

logger = logging.getLogger(__name__)

BATCH_SIZE = 20  # accounts processed concurrently per batch


# ---------------------------------------------------------------------------
# Per-account helpers — each opens its own session (safe for asyncio.gather)
# ---------------------------------------------------------------------------

async def _get_delivery_channels(account_id: UUID, db) -> tuple:
    """Return (phone,) for report delivery via WhatsApp."""
    account = await db.get(BrokerAccount, account_id)
    user = await db.get(User, account.user_id) if account and account.user_id else None
    phone = user.guardian_phone if user else None
    return phone, None  # email delivery removed


async def _send_eod_for_account(account_id: UUID, retention_service: RetentionService) -> bool:
    """Send equity EOD report for one account via WhatsApp and/or email."""
    async with SessionLocal() as db:
        try:
            goal_result = await db.execute(
                select(Goal).where(Goal.broker_account_id == account_id)
            )
            goal = goal_result.scalar_one_or_none()
            if goal and goal.primary_segment == "COMMODITY":
                return False

            phone, email = await _get_delivery_channels(account_id, db)
            if not phone and not email:
                logger.info(f"No delivery channel for account {account_id}, skipping EOD")
                return False

            await retention_service.send_eod_report(
                broker_account_id=account_id,
                phone_number=phone,
                db=db,
            )
            return True
        except Exception as e:
            logger.error(f"EOD report failed for {account_id}: {e}")
            return False


async def _send_commodity_eod_for_account(account_id: UUID, retention_service: RetentionService) -> bool:
    """Send commodity EOD report for one account."""
    async with SessionLocal() as db:
        try:
            phone, email = await _get_delivery_channels(account_id, db)
            if not phone and not email:
                logger.info(f"No delivery channel for account {account_id}, skipping commodity EOD")
                return False

            await retention_service.send_eod_report(
                broker_account_id=account_id,
                phone_number=phone,
                db=db,
            )
            return True
        except Exception as e:
            logger.error(f"Commodity EOD failed for {account_id}: {e}")
            return False


async def _send_morning_brief_for_account(account_id: UUID, retention_service: RetentionService) -> bool:
    """Send morning brief for one account via WhatsApp and/or email."""
    async with SessionLocal() as db:
        try:
            phone, email = await _get_delivery_channels(account_id, db)
            if not phone and not email:
                logger.info(f"No delivery channel for account {account_id}, skipping morning brief")
                return False

            await retention_service.send_morning_brief(
                broker_account_id=account_id,
                phone_number=phone,
                db=db,
            )
            return True
        except Exception as e:
            logger.error(f"Morning brief failed for {account_id}: {e}")
            return False


# ---------------------------------------------------------------------------
# Celery tasks
# ---------------------------------------------------------------------------

@celery_app.task
def generate_eod_reports():
    """
    Generate and send EOD reports for all equity users.
    Runs at 4:00 PM IST (after equity market close).
    Accounts processed in parallel batches of 20.
    """
    async def _generate():
        async with SessionLocal() as db:
            result = await db.execute(
                select(BrokerAccount.id).where(BrokerAccount.status == "connected")
            )
            account_ids = result.scalars().all()

        if not account_ids:
            return {"sent": 0, "errors": 0}

        retention_service = RetentionService()
        all_results = []
        for i in range(0, len(account_ids), BATCH_SIZE):
            batch = account_ids[i:i + BATCH_SIZE]
            batch_results = await asyncio.gather(
                *[_send_eod_for_account(aid, retention_service) for aid in batch],
                return_exceptions=True,
            )
            all_results.extend(batch_results)

        sent = sum(1 for r in all_results if r is True)
        errors = sum(1 for r in all_results if isinstance(r, Exception) or r is False)
        logger.info(f"EOD reports: {sent} sent, {errors} skipped/failed of {len(account_ids)}")
        return {"sent": sent, "errors": errors}

    return asyncio.run(_generate())


@celery_app.task
def generate_commodity_eod():
    """
    Generate EOD reports for commodity traders.
    Runs at 11:45 PM IST (after MCX close).
    Accounts processed in parallel batches of 20.
    """
    async def _generate():
        async with SessionLocal() as db:
            result = await db.execute(
                select(BrokerAccount.id)
                .join(Goal, BrokerAccount.id == Goal.broker_account_id)
                .where(
                    BrokerAccount.status == "connected",
                    Goal.primary_segment == "COMMODITY",
                )
            )
            account_ids = result.scalars().all()

        if not account_ids:
            return {"sent": 0}

        retention_service = RetentionService()
        all_results = []
        for i in range(0, len(account_ids), BATCH_SIZE):
            batch = account_ids[i:i + BATCH_SIZE]
            batch_results = await asyncio.gather(
                *[_send_commodity_eod_for_account(aid, retention_service) for aid in batch],
                return_exceptions=True,
            )
            all_results.extend(batch_results)

        sent = sum(1 for r in all_results if r is True)
        logger.info(f"Commodity EOD reports: {sent} sent of {len(account_ids)}")
        return {"sent": sent}

    return asyncio.run(_generate())


@celery_app.task
def send_morning_prep():
    """
    Send morning preparation messages.
    Runs at 8:30 AM IST (before market open).
    Accounts processed in parallel batches of 20.
    """
    async def _send():
        async with SessionLocal() as db:
            result = await db.execute(
                select(BrokerAccount.id).where(BrokerAccount.status == "connected")
            )
            account_ids = result.scalars().all()

        if not account_ids:
            return {"sent": 0}

        retention_service = RetentionService()
        all_results = []
        for i in range(0, len(account_ids), BATCH_SIZE):
            batch = account_ids[i:i + BATCH_SIZE]
            batch_results = await asyncio.gather(
                *[_send_morning_brief_for_account(aid, retention_service) for aid in batch],
                return_exceptions=True,
            )
            all_results.extend(batch_results)

        sent = sum(1 for r in all_results if r is True)
        logger.info(f"Morning briefs: {sent} sent of {len(account_ids)}")
        return {"sent": sent}

    return asyncio.run(_send())


@celery_app.task
def send_weekly_summary(broker_account_id: str):
    """
    Send weekly performance summary to a user.
    Called on Sundays or triggered manually.
    """
    import asyncio

    async def _send():
        async with SessionLocal() as db:
            try:
                from app.services.ai_service import ai_service
                from app.services.whatsapp_service import whatsapp_service as _wa
                from app.models.completed_trade import CompletedTrade
                from sqlalchemy import and_
                from datetime import timedelta

                account_id = UUID(broker_account_id)

                week_start = datetime.now(timezone.utc) - timedelta(days=7)
                result = await db.execute(
                    select(CompletedTrade).where(
                        and_(
                            CompletedTrade.broker_account_id == account_id,
                            CompletedTrade.exit_time >= week_start,
                        )
                    )
                )
                trades = result.scalars().all()

                if not trades:
                    return {"skipped": "No trades this week"}

                total_pnl = sum(float(t.realized_pnl or 0) for t in trades)
                winners = [t for t in trades if float(t.realized_pnl or 0) > 0]
                win_rate = (len(winners) / len(trades) * 100) if trades else 0
                best = max((float(t.realized_pnl or 0) for t in trades), default=0)
                worst = min((float(t.realized_pnl or 0) for t in trades), default=0)

                report = await ai_service.generate_whatsapp_report(
                    period_days=7,
                    total_pnl=total_pnl,
                    trade_count=len(trades),
                    win_rate=win_rate,
                    best_trade=best,
                    worst_trade=worst,
                    patterns_detected=[],
                    key_strength="Consistent execution",
                    key_weakness="Position sizing"
                )

                account_result = await db.execute(
                    select(BrokerAccount).where(BrokerAccount.id == account_id)
                )
                account = account_result.scalar_one_or_none()

                if account:
                    user = await db.get(User, account.user_id) if account.user_id else None
                    phone = user.guardian_phone if user else None
                    if phone:
                        await _wa.send_message(phone, report)
                    else:
                        logger.info(f"No guardian phone for account {account_id}, skipping weekly summary")

                return {"sent": True, "pnl": total_pnl, "trades": len(trades)}

            except Exception as e:
                logger.error(f"Weekly summary failed: {e}", exc_info=True)
                return {"error": str(e)}

    return asyncio.run(_send())


@celery_app.task
def send_weekly_summaries_batch():
    """
    Trigger weekly summary for all connected accounts.
    Runs every Sunday at 8:00 PM IST.
    """
    async def _batch():
        async with SessionLocal() as db:
            try:
                result = await db.execute(
                    select(BrokerAccount).where(BrokerAccount.status == "connected")
                )
                accounts = result.scalars().all()

                queued = 0
                for account in accounts:
                    user = await db.get(User, account.user_id) if account.user_id else None
                    if not (user and user.guardian_phone):
                        continue
                    send_weekly_summary.apply_async(args=[str(account.id)])
                    queued += 1

                logger.info(f"Weekly summaries queued: {queued}")
                return {"queued": queued}

            except Exception as e:
                logger.error(f"Weekly summaries batch failed: {e}", exc_info=True)
                return {"error": str(e)}

    return asyncio.run(_batch())


@celery_app.task(name="app.tasks.report_tasks.generate_coach_insight_task")
def generate_coach_insight_task(broker_account_id: str, context: dict):
    """
    Async Celery task to generate a coach insight via LLM and cache it.

    Called by GET /coach/insight when there is no valid cached insight.
    The API returns a fallback immediately; this task writes the real
    LLM response to UserProfile.ai_cache["coach_insight"] so the next
    request returns it instantly.

    context dict keys:
        risk_state, total_pnl, patterns_active, recent_trades,
        time_of_day, user_profile_context
    """
    import asyncio

    async def _generate():
        async with SessionLocal() as db:
            try:
                from app.services.ai_service import ai_service
                from app.models.user_profile import UserProfile
                from datetime import datetime, timezone
                from sqlalchemy import select

                account_id = UUID(broker_account_id)

                insight = await ai_service.generate_coach_insight(
                    risk_state=context.get("risk_state", "safe"),
                    total_pnl=context.get("total_pnl", 0.0),
                    patterns_active=context.get("patterns_active", []),
                    recent_trades=context.get("recent_trades", 0),
                    time_of_day=context.get("time_of_day", "Post-market"),
                    user_profile_context=context.get("user_profile_context", ""),
                )

                if not insight:
                    return {"error": "LLM returned empty response"}

                profile_result = await db.execute(
                    select(UserProfile).where(UserProfile.broker_account_id == account_id)
                )
                profile = profile_result.scalar_one_or_none()

                if profile:
                    current_cache = dict(profile.ai_cache or {})
                    current_cache["coach_insight"] = {
                        "insight": insight,
                        "risk_state": context.get("risk_state", "safe"),
                        "generated_at": datetime.now(timezone.utc).isoformat(),
                    }
                    profile.ai_cache = current_cache
                    await db.commit()
                    logger.info(f"Coach insight cached for account {broker_account_id}")

                return {"insight": insight}

            except Exception as e:
                logger.error(f"Coach insight generation failed: {e}", exc_info=True)
                return {"error": str(e)}

    return asyncio.run(_generate())


@celery_app.task(name="app.tasks.report_tasks.generate_analytics_narrative_task")
def generate_analytics_narrative_task(
    broker_account_id: str,
    tab: str,
    days: int,
    tab_data: dict,
    behavior_score=None,
    patterns=None,
):
    """
    Async Celery task to generate an analytics tab narrative via LLM and cache it.

    Called by GET /analytics/ai-summary on cache miss. The API returns a
    fallback immediately; this task writes the real LLM response to
    UserProfile.ai_cache["{tab}_{days}"] so the next request returns it instantly.

    tab_data: pre-gathered data dict for the tab (computed by the API handler
              before firing this task — avoids re-querying the DB here).
    behavior_score / patterns: extra context for the "behavior" tab.
    """
    import asyncio as _asyncio

    async def _generate():
        async with SessionLocal() as db:
            try:
                from app.services.ai_service import ai_service
                from app.models.user_profile import UserProfile
                from datetime import datetime, timezone
                from sqlalchemy import select

                account_id = UUID(broker_account_id)
                cache_key = f"{tab}_{days}"

                narrative_result = await ai_service.generate_analytics_narrative(
                    tab=tab,
                    data=tab_data,
                    behavior_score=behavior_score,
                    patterns=patterns,
                )

                if not narrative_result:
                    return {"error": "LLM returned empty response"}

                generated_at = datetime.now(timezone.utc).isoformat()
                cache_entry = {**narrative_result, "generated_at": generated_at}

                profile_result = await db.execute(
                    select(UserProfile).where(UserProfile.broker_account_id == account_id)
                )
                profile = profile_result.scalar_one_or_none()

                if profile:
                    current_cache = dict(profile.ai_cache or {})
                    current_cache[cache_key] = cache_entry
                    profile.ai_cache = current_cache
                    await db.commit()
                    logger.info(
                        f"Analytics narrative cached: {tab} for {broker_account_id}"
                    )

                return narrative_result

            except Exception as e:
                logger.error(f"Analytics narrative generation failed: {e}", exc_info=True)
                return {"error": str(e)}

    return _asyncio.run(_generate())
