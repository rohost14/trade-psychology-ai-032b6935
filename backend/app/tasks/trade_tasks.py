"""
Trade Processing Tasks (Celery)

Async tasks for:
- Processing webhook trade data
- Syncing trades from Zerodha
- Running risk detection
"""

import logging
from uuid import UUID
from datetime import datetime, timezone
from typing import Dict, Any

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.core.config import settings
from app.services.trade_sync_service import TradeSyncService
from app.services.risk_detector import RiskDetector
from app.services.pnl_calculator import pnl_calculator
from app.models.user import User
from app.models.trade import Trade
from app.models.broker_account import BrokerAccount
from app.utils.trade_classifier import classify_trade
from sqlalchemy import select, update

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Redis lock helpers (SETNX pattern)
# ---------------------------------------------------------------------------

def _get_redis_client():
    """Return a synchronous redis client. Lazily imported so Celery workers
    don't need Redis at import time if REDIS_URL is unset."""
    import redis as redis_lib
    return redis_lib.from_url(settings.REDIS_URL, decode_responses=True)


def _acquire_lock(redis_client, key: str, ttl_seconds: int) -> bool:
    """
    Try to acquire a Redis SETNX lock.

    Returns True if lock acquired, False if already held by another worker.
    The lock auto-expires after ttl_seconds to prevent deadlocks.
    """
    return bool(redis_client.set(key, "1", nx=True, ex=ttl_seconds))


def _release_lock(redis_client, key: str):
    """Release a Redis lock."""
    redis_client.delete(key)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_webhook_trade(self, trade_data: Dict[str, Any], broker_account_id: str):
    """
    Process a single trade from Zerodha webhook.

    This runs async in a Celery worker, so the webhook can return immediately.

    Guards:
    - processed_at idempotency check: if the signal pipeline already ran for
      this trade (processed_at IS NOT NULL), skip immediately (item 3).
    - fifo_lock: only one FIFO P&L calculation per account at a time (item 4).
    - behavior_lock: only one behavioral detection per account at a time (item 5).
    """
    import asyncio

    async def _process():
        async with SessionLocal() as db:
            try:
                account_id = UUID(broker_account_id)

                # Get broker account
                result = await db.execute(
                    select(BrokerAccount).where(BrokerAccount.id == account_id)
                )
                account = result.scalar_one_or_none()

                if not account:
                    logger.error(f"Broker account not found: {broker_account_id}")
                    return {"success": False, "error": "Account not found"}

                # Classify trade
                classification = classify_trade(trade_data)

                # Transform and save
                normalized = TradeSyncService.transform_zerodha_order(trade_data)
                normalized["asset_class"] = classification["asset_class"]
                normalized["instrument_type"] = classification["instrument_type"]
                normalized["product_type"] = classification["product_type"]

                trade, _is_new = await TradeSyncService.upsert_trade(db, normalized, account_id)
                await db.commit()

                logger.info(f"Trade saved: {trade_data.get('order_id')} - {trade_data.get('status')}")

                # Trigger Immediate Position Sync
                # This ensures frontend "Open Positions" are updated instantly
                try:
                    await TradeSyncService.sync_positions(account_id, db)
                except Exception as e:
                    logger.error(f"Failed to sync positions in webhook: {e}")

                # Refresh KiteTicker subscriptions — new position may have opened.
                # This ensures the live price stream immediately covers any new instrument.
                try:
                    from app.services.price_stream_service import price_stream
                    await price_stream.refresh_subscriptions(account_id, db)
                except Exception as e:
                    logger.error(f"Failed to refresh price subscriptions: {e}")

                # Only run the signal pipeline for COMPLETE trades
                if trade_data.get("status") != "COMPLETE":
                    return {"success": True, "trade_id": str(trade.id)}

                # ----------------------------------------------------------------
                # ITEM 3: Idempotency guard — skip if pipeline already ran
                # ----------------------------------------------------------------
                # Re-fetch trade to get latest processed_at (another worker may
                # have set it between our upsert and now).
                fresh = await db.get(Trade, trade.id)
                if fresh and fresh.processed_at is not None:
                    logger.info(
                        f"Trade {trade.order_id} already processed at "
                        f"{fresh.processed_at}. Skipping pipeline."
                    )
                    return {"success": True, "trade_id": str(trade.id), "skipped": True}

                # Mark pipeline as started — atomic claim.
                # If two workers race here, the UNIQUE index on (account, order_id)
                # means only one upsert succeeded; the second will see processed_at set.
                now_utc = datetime.now(timezone.utc)
                await db.execute(
                    update(Trade)
                    .where(Trade.id == trade.id, Trade.processed_at == None)  # noqa: E711
                    .values(processed_at=now_utc)
                )
                await db.commit()

                # Verify we won the race (another worker may have beaten us)
                fresh = await db.get(Trade, trade.id)
                if fresh and fresh.processed_at != now_utc:
                    logger.info(
                        f"Trade {trade.order_id}: lost processed_at race. Skipping."
                    )
                    return {"success": True, "trade_id": str(trade.id), "skipped": True}

                # ----------------------------------------------------------------
                # ITEM 4: Redis SETNX lock — one FIFO P&L calculation per account
                # ----------------------------------------------------------------
                redis_client = None
                fifo_lock_key = f"fifo_lock:{broker_account_id}"
                fifo_lock_acquired = False

                try:
                    redis_client = _get_redis_client()
                    # Retry acquiring the lock up to 3 times with 2s gap
                    for attempt in range(3):
                        fifo_lock_acquired = _acquire_lock(redis_client, fifo_lock_key, ttl_seconds=30)
                        if fifo_lock_acquired:
                            break
                        import asyncio as _asyncio
                        await _asyncio.sleep(2)

                    if not fifo_lock_acquired:
                        logger.warning(
                            f"Could not acquire fifo_lock for {broker_account_id} "
                            f"after 3 attempts. Retrying task."
                        )
                        raise self.retry(countdown=5)

                    # Calculate P&L for SELL trades in real-time
                    if trade_data.get("transaction_type") == "SELL":
                        try:
                            calculated_pnl = await pnl_calculator.calculate_trade_pnl_realtime(trade, db)
                            if calculated_pnl is not None:
                                await db.execute(
                                    update(Trade)
                                    .where(Trade.id == trade.id)
                                    .values(pnl=float(calculated_pnl))
                                )
                                await db.commit()
                                logger.info(f"P&L calculated for SELL {trade.order_id}: {calculated_pnl}")
                        except Exception as e:
                            logger.error(f"Real-time P&L calculation failed: {e}")

                finally:
                    if redis_client and fifo_lock_acquired:
                        _release_lock(redis_client, fifo_lock_key)

                # ----------------------------------------------------------------
                # ITEM 5: Redis SETNX lock — one behavioral detection per account
                # ----------------------------------------------------------------
                behavior_lock_key = f"behavior_lock:{broker_account_id}"
                behavior_lock_acquired = False

                try:
                    if redis_client is None:
                        redis_client = _get_redis_client()

                    for attempt in range(3):
                        behavior_lock_acquired = _acquire_lock(redis_client, behavior_lock_key, ttl_seconds=15)
                        if behavior_lock_acquired:
                            break
                        import asyncio as _asyncio
                        await _asyncio.sleep(2)

                    if not behavior_lock_acquired:
                        logger.warning(
                            f"Could not acquire behavior_lock for {broker_account_id}. "
                            f"Behavioral detection skipped for this trade."
                        )
                        # Don't retry the whole task for behavioral detection —
                        # the P&L is already saved. Log and move on.
                        return {"success": True, "trade_id": str(trade.id), "behavior_skipped": True}

                    await run_risk_detection_async(account_id, db, trade)

                finally:
                    if redis_client and behavior_lock_acquired:
                        _release_lock(redis_client, behavior_lock_key)

                return {"success": True, "trade_id": str(trade.id)}

            except Exception as e:
                logger.error(f"Trade processing failed: {e}", exc_info=True)
                await db.rollback()
                raise self.retry(exc=e)

    # Run async function in sync context
    return asyncio.get_event_loop().run_until_complete(_process())


@celery_app.task(bind=True, max_retries=2)
def sync_trades_for_account(self, broker_account_id: str):
    """
    Full trade sync for an account.

    Called after OAuth or manual sync request.
    Rate limited to 10/minute to avoid Zerodha API limits.
    """
    import asyncio

    async def _sync():
        async with SessionLocal() as db:
            try:
                account_id = UUID(broker_account_id)
                result = await TradeSyncService.sync_trades_for_broker_account(account_id, db)

                logger.info(f"Sync complete for {broker_account_id}: {result}")
                return result

            except Exception as e:
                logger.error(f"Sync failed for {broker_account_id}: {e}", exc_info=True)
                raise self.retry(exc=e)

    return asyncio.get_event_loop().run_until_complete(_sync())


@celery_app.task
def run_risk_detection(broker_account_id: str, trigger_trade_id: str = None):
    """
    Run risk pattern detection for an account.

    Called after trade processing or on schedule.
    """
    import asyncio

    async def _detect():
        async with SessionLocal() as db:
            try:
                account_id = UUID(broker_account_id)

                # Get trigger trade if provided
                trigger_trade = None
                if trigger_trade_id:
                    result = await db.execute(
                        select(Trade).where(Trade.id == UUID(trigger_trade_id))
                    )
                    trigger_trade = result.scalar_one_or_none()

                risk_detector = RiskDetector()
                alerts = await risk_detector.detect_patterns(
                    account_id,
                    db,
                    trigger_trade=trigger_trade
                )

                # Save alerts
                for alert in alerts:
                    db.add(alert)

                await db.commit()

                logger.info(f"Risk detection complete: {len(alerts)} alerts")
                return {"alerts_created": len(alerts)}

            except Exception as e:
                logger.error(f"Risk detection failed: {e}", exc_info=True)
                return {"error": str(e)}

    return asyncio.get_event_loop().run_until_complete(_detect())


async def run_risk_detection_async(broker_account_id: UUID, db, trigger_trade: Trade = None):
    """
    Internal async helper for risk detection.
    Used when already in async context (webhook processing).
    """
    try:
        risk_detector = RiskDetector()
        alerts = await risk_detector.detect_patterns(
            broker_account_id,
            db,
            trigger_trade=trigger_trade
        )

        # Save new alerts
        from app.models.risk_alert import RiskAlert
        from sqlalchemy import and_
        from datetime import timedelta, timezone

        # Deduplicate against last 24 hours
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        existing_result = await db.execute(
            select(RiskAlert).where(
                and_(
                    RiskAlert.broker_account_id == broker_account_id,
                    RiskAlert.detected_at >= cutoff
                )
            )
        )
        existing_alerts = existing_result.scalars().all()
        existing_keys = set()
        for a in existing_alerts:
            if a.trigger_trade_id:
                existing_keys.add((str(a.trigger_trade_id), a.pattern_type))
            else:
                # Account-level alerts (no specific trigger trade) — dedup by type
                existing_keys.add(("_account_", a.pattern_type))

        new_alerts = []
        for alert in alerts:
            if alert.trigger_trade_id:
                key = (str(alert.trigger_trade_id), alert.pattern_type)
            else:
                key = ("_account_", alert.pattern_type)
            if key not in existing_keys:
                db.add(alert)
                new_alerts.append(alert)
                existing_keys.add(key)

        await db.commit()

        # Send WhatsApp for DANGER alerts
        danger_alerts = [a for a in new_alerts if a.severity == "danger"]
        if danger_alerts:
            # Queue alert sending task
            for alert in danger_alerts:
                send_danger_alert.delay(
                    str(broker_account_id),
                    str(alert.id)
                )

        # Trigger AlertCheckpoint for danger/critical alerts (real counterfactual P&L)
        checkpoint_alerts = [a for a in new_alerts if a.severity in ("danger", "critical")]
        if checkpoint_alerts:
            from app.tasks.checkpoint_tasks import create_alert_checkpoint
            for alert in checkpoint_alerts:
                create_alert_checkpoint.apply_async(
                    args=[str(alert.id), str(broker_account_id)],
                    countdown=10,
                )

        logger.info(f"Risk detection: {len(new_alerts)} new alerts, {len(danger_alerts)} danger")

        # ----------------------------------------------------------------
        # SHADOW MODE — BehaviorEngine runs AFTER production detection.
        # Production path above is completely unchanged.
        # Shadow never raises — any failure is logged and swallowed.
        # ----------------------------------------------------------------
        await _run_shadow_behavior_engine(broker_account_id, trigger_trade, db)

    except Exception as e:
        logger.error(f"Risk detection error: {e}", exc_info=True)


async def _run_shadow_behavior_engine(
    broker_account_id: UUID,
    trigger_trade,
    db,
) -> None:
    """
    Run BehaviorEngine in shadow mode alongside the old detection pipeline.

    Writes to shadow_behavioral_events ONLY — never touches production tables.
    Any exception is caught and logged — this MUST NOT affect the caller.

    Shadow validation:
      - Run for 5 trading days
      - Compare shadow events vs production alerts
      - If match rate > 95% and no crashes → cutover in Phase 3 step 7
    """
    try:
        if trigger_trade is None:
            return  # Only run shadow when we have a specific trigger trade

        # Find the CompletedTrade that corresponds to this trigger_trade
        # (The trigger_trade is a Trade fill; CompletedTrade is the closed round)
        from app.models.completed_trade import CompletedTrade
        from sqlalchemy import desc

        ct_result = await db.execute(
            select(CompletedTrade).where(
                CompletedTrade.broker_account_id == broker_account_id
            ).order_by(desc(CompletedTrade.exit_time)).limit(1)
        )
        latest_ct = ct_result.scalar_one_or_none()

        if not latest_ct:
            return  # No completed trade yet — position still open

        # Run the BehaviorEngine
        from app.services.behavior_engine import behavior_engine
        result = await behavior_engine.analyze(
            broker_account_id=broker_account_id,
            completed_trade=latest_ct,
            db=db,
        )

        if result.events:
            logger.info(
                f"[shadow] {broker_account_id} | "
                f"{len(result.events)} shadow events | "
                f"state={result.behavior_state} | "
                f"risk={float(result.risk_score_before):.0f}→{float(result.risk_score_after):.0f} | "
                f"patterns={[e.event_type for e in result.events]}"
            )
        else:
            logger.debug(
                f"[shadow] {broker_account_id} | no events | "
                f"state={result.behavior_state}"
            )

    except Exception as e:
        # Shadow failures MUST NOT crash the production pipeline
        logger.error(f"[shadow] BehaviorEngine shadow failed (non-fatal): {e}", exc_info=True)


@celery_app.task
def send_danger_alert(broker_account_id: str, alert_id: str):
    """Send WhatsApp and Push notifications for danger pattern."""
    import asyncio

    async def _send():
        async with SessionLocal() as db:
            try:
                from app.models.risk_alert import RiskAlert
                from app.services.alert_service import AlertService
                from app.services.push_notification_service import push_service

                # Get alert
                result = await db.execute(
                    select(RiskAlert).where(RiskAlert.id == UUID(alert_id))
                )
                alert = result.scalar_one_or_none()

                if not alert:
                    return {"error": "Alert not found"}

                # Get broker account for user info
                account_result = await db.execute(
                    select(BrokerAccount).where(
                        BrokerAccount.id == UUID(broker_account_id)
                    )
                )
                account = account_result.scalar_one_or_none()

                if not account:
                    return {"error": "Account not found"}

                results = {"whatsapp": False, "push": {"sent": 0, "failed": 0}}

                # 1. Send Push Notification (to user's browser/device)
                try:
                    push_result = await push_service.send_risk_alert_notification(alert, db)
                    results["push"] = push_result
                    logger.info(f"Push notification: {push_result}")
                except Exception as e:
                    logger.error(f"Push notification failed: {e}")

                # 2. Send WhatsApp alert (to guardian if configured)
                user = await db.get(User, account.user_id) if account.user_id else None
                phone = user.guardian_phone if user else None
                if phone:
                    try:
                        alert_service = AlertService()
                        sent = await alert_service.send_risk_alert(alert, account, phone)
                        results["whatsapp"] = sent
                    except Exception as e:
                        logger.error(f"WhatsApp alert failed: {e}")

                return results

            except Exception as e:
                logger.error(f"Alert send failed: {e}", exc_info=True)
                return {"error": str(e)}

    return asyncio.get_event_loop().run_until_complete(_send())
