"""
Portfolio Radar Tasks — Celery Beat

Runs every 5 minutes during market hours (09:15–15:30 IST).
For each connected account:
  1. Compute position metrics (breakeven, decay, DTE, capital_at_risk)
  2. Analyse portfolio concentration
  3. Sync GTT triggers from Kite
  4. Fire new in-app + WhatsApp alerts for triggered conditions

Zero REST API calls for metrics — uses Redis LTP cache from KiteTicker.
GTT sync does make one Kite API call per account (lightweight GET /gtt/triggers).
"""

import asyncio
import logging
from datetime import datetime, time as dtime
from typing import Dict
from uuid import UUID
from zoneinfo import ZoneInfo

from app.core.celery_app import celery_app
from app.core.database import SessionLocal

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")

_MARKET_START = dtime(9, 15)
_MARKET_END = dtime(15, 30)


def _is_market_hours() -> bool:
    now = datetime.now(IST)
    if now.weekday() >= 5:
        return False
    return _MARKET_START <= now.time() <= _MARKET_END


@celery_app.task(name="app.tasks.portfolio_radar_tasks.run_portfolio_radar")
def run_portfolio_radar():
    """Celery Beat entry point — every 5 minutes."""
    return asyncio.run(_run_all_accounts())


async def _run_all_accounts() -> Dict:
    if not _is_market_hours():
        return {"skipped": "outside_market_hours"}

    from app.models.broker_account import BrokerAccount
    from sqlalchemy import select, and_

    async with SessionLocal() as db:
        result = await db.execute(
            select(BrokerAccount).where(
                and_(
                    BrokerAccount.status == "connected",
                    BrokerAccount.token_revoked_at == None,  # noqa: E711
                )
            )
        )
        accounts = result.scalars().all()

    async def _run_safe(account):
        async with SessionLocal() as db:
            await _run_account(account, db)

    processed = 0
    errors = 0
    batch_size = 20
    for i in range(0, len(accounts), batch_size):
        batch = accounts[i:i + batch_size]
        results = await asyncio.gather(*[_run_safe(a) for a in batch], return_exceptions=True)
        for r in results:
            if isinstance(r, Exception):
                errors += 1
                logger.error(f"[portfolio_radar] Batch account failed: {r}")
            else:
                processed += 1

    return {"processed": processed, "errors": errors}


async def _run_account(account, db) -> None:
    from app.services.position_metrics_service import position_metrics_service
    from app.services.portfolio_concentration_service import portfolio_concentration_service
    from app.services.alert_service import alert_service
    from app.core.event_bus import publish_event

    broker_account_id = account.id

    # 1. Compute position metrics from Redis LTP cache (no API calls)
    metrics = await position_metrics_service.compute_all(broker_account_id, db)
    if not metrics:
        return  # No open F&O positions — nothing to do

    # 2. Analyse concentration and generate alerts
    result = await portfolio_concentration_service.analyse_and_alert(
        broker_account_id, metrics, db
    )

    # 3. Fire alerts for new concentration conditions
    # NOTE: GTT sync is NOT done here — it's seeded once on login (seed_gtt_triggers_for_account)
    # and updated via webhooks (variety='gtt' → honored, variety='regular' → overridden).
    # Polling Zerodha every 5 min for GTTs is unnecessary and burns API quota.
    new_alerts = result.get("new_alerts", [])
    for alert_data in new_alerts:
        message = alert_data.get("message", "")
        if not message:
            continue

        # In-app alert via RiskAlert
        try:
            await alert_service.create_risk_alert(
                db=db,
                broker_account_id=broker_account_id,
                alert_type=alert_data["type"],
                severity="caution",
                message=message,
                details={"key": alert_data["key"], "value": alert_data["value"]},
            )
        except Exception as e:
            logger.warning(f"[portfolio_radar] Failed to create alert: {e}")

        # Publish WebSocket event so frontend updates in real-time
        try:
            publish_event(str(broker_account_id), "alert_update", {
                "type": alert_data["type"],
                "message": message,
            })
        except Exception:
            pass

        # WhatsApp notification
        try:
            from app.services.whatsapp_service import whatsapp_service
            from app.models.user_profile import UserProfile
            from sqlalchemy import select

            profile_result = await db.execute(
                select(UserProfile).where(
                    UserProfile.broker_account_id == broker_account_id
                )
            )
            profile = profile_result.scalar_one_or_none()
            if profile and getattr(profile, "whatsapp_enabled", False) and profile.phone_number:
                await whatsapp_service.send_message(profile.phone_number, message)
        except Exception as e:
            logger.warning(f"[portfolio_radar] WhatsApp failed for {broker_account_id}: {e}")

    if new_alerts:
        logger.info(
            f"[portfolio_radar] {broker_account_id}: "
            f"{len(new_alerts)} new alerts, "
            f"{result.get('skipped_cooldown', 0)} skipped (cooldown)"
        )


# ---------------------------------------------------------------------------
# Event-driven single-account task (triggered by trade fills)
# ---------------------------------------------------------------------------

@celery_app.task(name="app.tasks.portfolio_radar_tasks.run_portfolio_radar_for_account")
def run_portfolio_radar_for_account(broker_account_id: str):
    """
    Run portfolio concentration analysis for a single account.
    Triggered after each COMPLETE trade fill in trade_tasks.py pipeline.
    Replaces the 5-min beat for this account.
    """
    return asyncio.run(
        _run_for_single_account(broker_account_id)
    )


async def _run_for_single_account(broker_account_id: str) -> dict:
    if not _is_market_hours():
        return {"skipped": "outside_market_hours"}

    # Debounce: skip if radar ran for this account in the last 60 seconds.
    # Prevents N tasks queuing up when a trader does a flurry of fills.
    from app.core.config import settings
    import redis as redis_lib
    _r = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)
    debounce_key = f"radar_debounce:{broker_account_id}"
    if _r.set(debounce_key, 1, ex=60, nx=True) is None:
        return {"skipped": "debounced"}
    _r.close()

    from app.models.broker_account import BrokerAccount
    from sqlalchemy import select

    async with SessionLocal() as db:
        result = await db.execute(
            select(BrokerAccount).where(BrokerAccount.id == UUID(broker_account_id))
        )
        account = result.scalar_one_or_none()
        if not account or account.status != "connected" or account.token_revoked_at is not None:
            return {"skipped": "account_not_connected"}

        await _run_account(account, db)

    return {"processed": broker_account_id}
