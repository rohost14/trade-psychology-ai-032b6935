"""
Trade Processing Tasks (Celery)

Async tasks for:
- Processing webhook trade data
- Syncing trades from Zerodha
- Running risk detection
"""

import logging
from uuid import UUID
from datetime import datetime, timezone, timedelta
from typing import Dict, Any

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.core.config import settings
from app.services.trade_sync_service import TradeSyncService
from app.services.pnl_calculator import pnl_calculator
from app.models.user import User
from app.models.trade import Trade
from app.models.broker_account import BrokerAccount
from app.utils.trade_classifier import classify_trade
from sqlalchemy import select, update, and_

# RiskDetector + BehavioralEvaluator — DEPRECATED (Phase 3 cutover)
# Kept in codebase for reference, no longer called from pipeline.
# Delete after 1 week of stable BehaviorEngine operation.

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
def process_webhook_trade(self, trade_data: Dict[str, Any], broker_account_id: str, request_id: str = "-"):
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
    from app.core.request_context import request_id_var
    request_id_var.set(request_id)

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
                try:
                    from app.services.price_stream_service import price_stream
                    await price_stream.refresh_subscriptions(account_id, db)
                except Exception as e:
                    logger.error(f"Failed to refresh price subscriptions: {e}")

                # Publish position update event (durable, replayable)
                from app.core.event_bus import publish_event
                publish_event(str(account_id), "position_update", {
                    "order_id": trade_data.get("order_id"),
                    "status": trade_data.get("status"),
                })

                # Fetch fresh margin from Kite and push to frontend.
                # Replaces useMargins.ts 30s polling — margin is pushed on every
                # trade webhook so frontend always has up-to-date margin data.
                try:
                    from app.models.broker_account import BrokerAccount
                    from app.services.zerodha_service import zerodha_client, KiteTokenExpiredError
                    import json as _json

                    account_record = await db.get(BrokerAccount, account_id)
                    if account_record and account_record.access_token and not account_record.token_revoked_at:
                        access_token = account_record.decrypt_token(account_record.access_token)
                        margins = await zerodha_client.get_margins(access_token)
                        # Cache in Redis for fast reads (5 min TTL)
                        _r = _get_redis_client()
                        _r.set(f"margin:{account_id}", _json.dumps(margins), ex=300)
                        # Push to frontend via stream
                        publish_event(str(account_id), "margin_update", margins)
                except KiteTokenExpiredError:
                    pass  # Token expired — margin update skipped, not an error
                except Exception as _me:
                    logger.debug(f"Margin update skipped: {_me}")

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

                # Atomic pipeline claim: UPDATE ... WHERE processed_at IS NULL.
                # rowcount == 1 means WE set it; rowcount == 0 means another worker
                # already claimed this trade. This is the only safe race-free pattern —
                # the previous two-step read/write approach had a TOCTOU window.
                now_utc = datetime.now(timezone.utc)
                claim_result = await db.execute(
                    update(Trade)
                    .where(Trade.id == trade.id, Trade.processed_at.is_(None))
                    .values(processed_at=now_utc)
                )
                await db.commit()

                if claim_result.rowcount != 1:
                    logger.info(
                        f"Trade {trade.order_id}: lost processed_at race (rowcount=0). Skipping."
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
                    # Retry acquiring the lock up to 4 times with exponential backoff.
                    # TTL=120s: PositionLedger apply_fill + CompletedTrade build + strategy
                    # detection can collectively take ~2s; 120s gives 60× safety margin.
                    import asyncio as _asyncio
                    for attempt in range(4):
                        fifo_lock_acquired = _acquire_lock(redis_client, fifo_lock_key, ttl_seconds=120)
                        if fifo_lock_acquired:
                            break
                        backoff = 2 ** attempt  # 1s, 2s, 4s, 8s
                        await _asyncio.sleep(backoff)

                    if not fifo_lock_acquired:
                        logger.warning(
                            f"Could not acquire fifo_lock for {broker_account_id} "
                            f"after 3 attempts. Retrying task."
                        )
                        raise self.retry(countdown=min(2 ** self.request.retries * 10, 300))

                    # PositionLedger: append-only fill record.
                    # Handles partial fills, flips, out-of-order, idempotency.
                    # Replaces calculate_trade_pnl_realtime for the real-time path.
                    try:
                        from app.services.position_ledger_service import (
                            PositionLedgerService, FillData
                        )
                        from decimal import Decimal as _Decimal

                        qty = trade.filled_quantity or trade.quantity or 0
                        # +qty = BUY (adds to long / reduces short)
                        # -qty = SELL (reduces long / adds to short)
                        signed_qty = qty if trade.transaction_type == "BUY" else -qty

                        fill = FillData(
                            broker_account_id=account_id,
                            tradingsymbol=trade.tradingsymbol or "",
                            exchange=trade.exchange or "",
                            fill_order_id=trade.order_id or str(trade.id),
                            fill_qty=signed_qty,
                            fill_price=_Decimal(str(trade.average_price or trade.price or 0)),
                            occurred_at=trade.order_timestamp or datetime.now(timezone.utc),
                            idempotency_key=f"{trade.order_id}:ledger",
                        )

                        ledger_entry, is_new = await PositionLedgerService.apply_fill(fill, db)
                        await db.flush()

                        # If this fill realized P&L, write it back to Trade.pnl
                        # (backward compat for any code still reading Trade.pnl)
                        if is_new and ledger_entry.realized_pnl:
                            await db.execute(
                                update(Trade)
                                .where(Trade.id == trade.id)
                                .values(pnl=float(ledger_entry.realized_pnl))
                            )

                        # If position just closed: create CompletedTrade from ledger immediately
                        if is_new and ledger_entry.entry_type in ("CLOSE", "FLIP"):
                            ct = await PositionLedgerService.build_completed_trade_on_close(
                                ledger_entry, db
                            )
                            if ct is None:
                                logger.warning(
                                    f"[ledger] build_completed_trade_on_close returned None "
                                    f"for entry {ledger_entry.id} ({ledger_entry.tradingsymbol}). "
                                    f"No behavioral analysis will run for this trade."
                                )
                            if ct:
                                db.add(ct)
                                await db.flush()  # give ct.id before strategy detection
                                logger.info(
                                    f"[ledger] CompletedTrade: {ct.tradingsymbol} "
                                    f"{ct.direction} pnl={ct.realized_pnl}"
                                )

                                # Strategy detection — runs before BehaviorEngine so
                                # the engine can suppress false alerts on strategy legs.
                                # Detects straddle/strangle/spread/iron condor etc.
                                try:
                                    from app.services.strategy_detector import detect_and_save
                                    sg = await detect_and_save(ct, db)
                                    if sg:
                                        logger.info(
                                            f"[strategy] {sg.strategy_type} detected for "
                                            f"{ct.tradingsymbol} | net_pnl={float(sg.net_pnl or 0):+,.0f}"
                                        )
                                except Exception as _sd_e:
                                    # Log as ERROR: if strategy detection fails, the behavior
                                    # engine won't suppress false alerts on losing hedge legs.
                                    logger.error(
                                        f"Strategy detection failed for {ct.tradingsymbol} "
                                        f"(behavior engine will not suppress hedge alerts): {_sd_e}",
                                        exc_info=True,
                                    )

                            # GTT discipline tracking — detect SL honour vs override
                            try:
                                from app.services.gtt_service import (
                                    record_gtt_honored, record_gtt_overridden, has_active_gtt
                                )
                                variety = trade_data.get("variety", "regular")
                                order_id = trade_data.get("order_id", "")
                                sym = trade.tradingsymbol or ""
                                if variety == "gtt":
                                    await record_gtt_honored(account_id, sym, order_id, db)
                                elif variety == "regular":
                                    if await has_active_gtt(account_id, sym, db):
                                        await record_gtt_overridden(account_id, sym, order_id, db)
                            except Exception as _gtt_e:
                                logger.debug(f"GTT tracking skipped: {_gtt_e}")

                        await db.commit()
                        logger.info(
                            f"[ledger] {ledger_entry.entry_type} {trade.tradingsymbol} "
                            f"qty={signed_qty:+d} @ {trade.average_price}"
                        )

                    except Exception as e:
                        logger.error(f"PositionLedger apply_fill failed: {e}", exc_info=True)
                        # Roll back any flushed-but-uncommitted ledger data so that the
                        # behavior detection step below doesn't accidentally commit partial state.
                        await db.rollback()
                        # Non-fatal: P&L write fails gracefully, pipeline continues

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

                # ── Event-driven position checks (replaces beat tasks) ──────
                # These are fire-and-forget — failures don't retry the trade task.
                try:
                    from app.tasks.position_monitor_tasks import (
                        check_position_overexposure,
                        check_holding_loser_scheduled,
                    )
                    # Immediate overexposure check for this symbol
                    check_position_overexposure.delay(
                        broker_account_id, trade.tradingsymbol or ""
                    )
                    # For BUY fills: schedule holding-loser check 30 min out.
                    # Use SETNX chain key so multiple BUY fills don't spawn
                    # parallel chains — only one chain active per account.
                    if trade.transaction_type == "BUY":
                        chain_key = f"holding_loser_chain:{broker_account_id}"
                        if redis_client and redis_client.set(
                            chain_key, 0, ex=1900, nx=True
                        ):
                            check_holding_loser_scheduled.apply_async(
                                args=[broker_account_id, 0],
                                countdown=1800,  # 30 minutes
                            )
                except Exception as _pm_e:
                    logger.debug(f"Position monitor trigger skipped: {_pm_e}")

                # ── Portfolio concentration analysis for this account ────────
                try:
                    from app.tasks.portfolio_radar_tasks import run_portfolio_radar_for_account
                    run_portfolio_radar_for_account.delay(broker_account_id)
                except Exception as _pr_e:
                    logger.debug(f"Portfolio radar trigger skipped: {_pr_e}")

                return {"success": True, "trade_id": str(trade.id)}

            except Exception as e:
                logger.error(f"Trade processing failed: {e}", exc_info=True)
                await db.rollback()
                try:
                    raise self.retry(exc=e, countdown=min(2 ** self.request.retries * 10, 300))
                except Exception as dlq_exc:
                    from celery.exceptions import MaxRetriesExceededError
                    if isinstance(dlq_exc, MaxRetriesExceededError):
                        try:
                            import sentry_sdk
                            sentry_sdk.capture_message(
                                f"[DLQ] process_webhook_trade exhausted retries: "
                                f"order={trade_data.get('order_id')} account={broker_account_id}. Trade may be lost.",
                                level="error",
                            )
                        except Exception:
                            pass
                        logger.error(
                            f"[DLQ] process_webhook_trade: order {trade_data.get('order_id')} "
                            f"lost after {self.max_retries} retries for account {broker_account_id}"
                        )
                    raise

    # Run async function in sync context
    return asyncio.run(_process())


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
                raise self.retry(exc=e, countdown=min(2 ** self.request.retries * 10, 300))

    return asyncio.run(_sync())


@celery_app.task(bind=True, max_retries=2)
def seed_gtt_triggers_for_account(self, broker_account_id: str):
    """
    Seed GTT tracking table once on login/reconnect.

    After this initial seed, all GTT state changes arrive via webhook:
      variety='gtt'     → record_gtt_honored    (SL triggered automatically)
      variety='regular' → record_gtt_overridden  (manual exit while GTT was active)
    No recurring poll needed.
    """
    import asyncio

    async def _seed():
        async with SessionLocal() as db:
            try:
                from app.models.broker_account import BrokerAccount
                from sqlalchemy import select
                from app.services.gtt_service import sync_gtt_triggers

                result = await db.execute(
                    select(BrokerAccount).where(BrokerAccount.id == UUID(broker_account_id))
                )
                account = result.scalar_one_or_none()
                if not account or not account.access_token:
                    return

                access_token = account.decrypt_token(account.access_token)
                await sync_gtt_triggers(UUID(broker_account_id), access_token, db)
                logger.info(f"GTT seed complete for {broker_account_id[:8]}")
            except Exception as e:
                logger.error(f"GTT seed failed for {broker_account_id}: {e}", exc_info=True)
                raise self.retry(exc=e, countdown=60)

    asyncio.run(_seed())


@celery_app.task
def run_risk_detection(broker_account_id: str, trigger_trade_id: str = None):
    """
    Run risk pattern detection for an account via BehaviorEngine.
    Phase 3 cutover: delegates to run_risk_detection_async (BehaviorEngine).
    """
    import asyncio

    async def _detect():
        async with SessionLocal() as db:
            try:
                account_id = UUID(broker_account_id)
                trigger_trade = None
                if trigger_trade_id:
                    result = await db.execute(
                        select(Trade).where(Trade.id == UUID(trigger_trade_id))
                    )
                    trigger_trade = result.scalar_one_or_none()

                await run_risk_detection_async(account_id, db, trigger_trade)
                return {"success": True}

            except Exception as e:
                logger.error(f"Risk detection task failed: {e}", exc_info=True)
                return {"error": str(e)}

    return asyncio.run(_detect())


async def run_risk_detection_async(broker_account_id: UUID, db, trigger_trade: Trade = None):
    """
    Internal async helper for risk detection.

    Phase 3 cutover: uses BehaviorEngine as the single detection source.
    RiskDetector + BehavioralEvaluator are deprecated and no longer called.

    BehaviorEngine:
    - Session-scoped (today only, not 24h rolling)
    - Cumulative risk score via TradingSession
    - Returns RiskAlert objects ready for dedup + notification
    """
    try:
        from app.models.risk_alert import RiskAlert
        from app.models.completed_trade import CompletedTrade
        from app.services.behavior_engine import behavior_engine
        from sqlalchemy import desc

        # Find the most recent CompletedTrade for this account (the closed position)
        ct_result = await db.execute(
            select(CompletedTrade)
            .where(CompletedTrade.broker_account_id == broker_account_id)
            .order_by(desc(CompletedTrade.exit_time))
            .limit(1)
        )
        latest_ct = ct_result.scalar_one_or_none()

        if not latest_ct:
            # No completed trade yet — position still open, nothing to analyze
            return

        # Run BehaviorEngine — returns RiskAlert objects
        result = await behavior_engine.analyze(
            broker_account_id=broker_account_id,
            completed_trade=latest_ct,
            db=db,
        )
        alerts = result.alerts  # List[RiskAlert], ready to save

        # ── Deduplicate with pattern-specific windows ─────────────────
        # Most patterns: 24h (once per session is enough).
        # Streak/meltdown patterns: 2h so a second episode in the same day
        # still fires, and repeated consecutive_loss_streak escalates to danger.
        _DEDUP_HOURS = {
            "consecutive_loss_streak": 2,
            "session_meltdown":        2,
            "profit_giveaway":         2,
        }
        now_utc = datetime.now(timezone.utc)
        cutoff = now_utc - timedelta(hours=24)
        existing_result = await db.execute(
            select(RiskAlert).where(
                and_(
                    RiskAlert.broker_account_id == broker_account_id,
                    RiskAlert.detected_at >= cutoff
                )
            )
        )
        all_existing = existing_result.scalars().all()
        # last fired time per pattern_type
        last_fired: dict = {}
        today_patterns: set = set()
        for a in all_existing:
            today_patterns.add(a.pattern_type)
            if a.pattern_type not in last_fired or a.detected_at > last_fired[a.pattern_type]:
                last_fired[a.pattern_type] = a.detected_at

        def _is_deduped(pattern_type: str) -> bool:
            if pattern_type not in last_fired:
                return False
            hours = _DEDUP_HOURS.get(pattern_type, 24)
            return (now_utc - last_fired[pattern_type]) < timedelta(hours=hours)

        new_alerts = []
        for alert in alerts:
            if _is_deduped(alert.pattern_type):
                continue
            # consecutive_loss_streak fired again today → escalate to danger
            # so the guardian (WhatsApp/push) notification triggers.
            if alert.pattern_type == "consecutive_loss_streak" \
                    and alert.pattern_type in today_patterns:
                alert.severity = "danger"
            db.add(alert)
            new_alerts.append(alert)
            last_fired[alert.pattern_type] = now_utc
            today_patterns.add(alert.pattern_type)

        await db.commit()

        # ── Alert consolidation (5-min bucket + hard cap) ─────────────
        new_alerts = await _apply_alert_consolidation(broker_account_id, new_alerts, db)

        # ── Send notifications for danger alerts ──────────────────────
        danger_alerts = [a for a in new_alerts if a.severity == "danger"]
        for alert in danger_alerts:
            send_danger_alert.delay(str(broker_account_id), str(alert.id))

        logger.info(
            f"[BehaviorEngine] {broker_account_id}: {len(new_alerts)} new alerts "
            f"({len(danger_alerts)} danger) | "
            f"state={result.behavior_state} | "
            f"risk={float(result.risk_score_before):.0f}→{float(result.risk_score_after):.0f}"
        )

        # Notify frontend via WebSocket — new alerts available, refresh immediately.
        if new_alerts:
            from app.core.event_bus import publish_event
            publish_event(str(broker_account_id), "alert_update", {
                "count": len(new_alerts),
                "has_danger": len(danger_alerts) > 0,
                "behavior_state": result.behavior_state,
            })

        # Also notify trade update so dashboard refreshes completed trades.
        from app.core.event_bus import publish_event
        publish_event(str(broker_account_id), "trade_update", {})

    except Exception as e:
        logger.error(f"Risk detection error: {e}", exc_info=True)


async def run_behavior_engine_full_session(broker_account_id: UUID, db) -> int:
    """
    Replay the behavior engine across ALL of today's CompletedTrades in
    chronological order.

    Used by the REST sync path when trades arrive in bulk (user was not in the
    app while trading).  Running the engine only on the *most recent* trade
    misses patterns like consecutive_loss_streak and options_premium_avg_down
    that fire on the 2nd/3rd loss in a sequence — not on a later winner.

    Returns the number of new alerts saved.
    """
    from app.models.risk_alert import RiskAlert
    from app.models.completed_trade import CompletedTrade
    from app.services.behavior_engine import behavior_engine
    from datetime import date as _date
    from zoneinfo import ZoneInfo as _ZI

    today_ist = datetime.now(_ZI("Asia/Kolkata")).date()
    today_start_utc = datetime.combine(
        today_ist, datetime.min.time()
    ).replace(tzinfo=timezone.utc) - timedelta(hours=5, minutes=30)

    ct_result = await db.execute(
        select(CompletedTrade)
        .where(
            CompletedTrade.broker_account_id == broker_account_id,
            CompletedTrade.exit_time >= today_start_utc,
        )
        .order_by(CompletedTrade.exit_time.asc())
    )
    trades_today = ct_result.scalars().all()

    if not trades_today:
        return 0

    # Build dedup state once — shared across all iterations.
    # Pattern-specific windows: streak/meltdown patterns use 2h so a second
    # episode in the same day can still fire.
    _DEDUP_HOURS = {
        "consecutive_loss_streak": 2,
        "session_meltdown":        2,
        "profit_giveaway":         2,
    }
    now_utc = datetime.now(timezone.utc)
    cutoff = now_utc - timedelta(hours=24)
    existing_result = await db.execute(
        select(RiskAlert).where(
            and_(
                RiskAlert.broker_account_id == broker_account_id,
                RiskAlert.detected_at >= cutoff,
            )
        )
    )
    all_existing = existing_result.scalars().all()
    last_fired: dict = {}
    today_patterns: set = set()
    for a in all_existing:
        today_patterns.add(a.pattern_type)
        if a.pattern_type not in last_fired or a.detected_at > last_fired[a.pattern_type]:
            last_fired[a.pattern_type] = a.detected_at

    def _is_deduped_full(pattern_type: str) -> bool:
        if pattern_type not in last_fired:
            return False
        hours = _DEDUP_HOURS.get(pattern_type, 24)
        return (now_utc - last_fired[pattern_type]) < timedelta(hours=hours)

    all_new_alerts: list[RiskAlert] = []

    for ct in trades_today:
        result = await behavior_engine.analyze(
            broker_account_id=broker_account_id,
            completed_trade=ct,
            db=db,
        )
        for alert in result.alerts:
            if _is_deduped_full(alert.pattern_type):
                continue
            if alert.pattern_type == "consecutive_loss_streak" \
                    and alert.pattern_type in today_patterns:
                alert.severity = "danger"
            db.add(alert)
            all_new_alerts.append(alert)
            last_fired[alert.pattern_type] = now_utc
            today_patterns.add(alert.pattern_type)

    if all_new_alerts:
        await db.commit()
        all_new_alerts = await _apply_alert_consolidation(broker_account_id, all_new_alerts, db)

        danger_alerts = [a for a in all_new_alerts if a.severity == "danger"]
        for alert in danger_alerts:
            send_danger_alert.delay(str(broker_account_id), str(alert.id))

        if all_new_alerts:
            from app.core.event_bus import publish_event
            publish_event(str(broker_account_id), "alert_update", {
                "count": len(all_new_alerts),
                "has_danger": len(danger_alerts) > 0,
            })
            publish_event(str(broker_account_id), "trade_update", {})

        logger.info(
            f"[BehaviorEngine/FullSession] {broker_account_id}: "
            f"{len(all_new_alerts)} alerts from {len(trades_today)} trades"
        )

    return len(all_new_alerts)


async def _apply_alert_consolidation(
    broker_account_id: UUID,
    alerts: list,
    db,
) -> list:
    """
    Alert consolidation (P-02):
    1. 5-minute bucket: suppress notification if same pattern_type was already
       notified within the last 5 minutes (record the alert, just don't notify)
    2. Hard cap: if session has fired 8+ alerts today, suppress further notifications
       (user would tune out anyway — alert fatigue is worse than no alert)

    Returns the subset of alerts that should trigger notifications.
    All alerts are already saved to DB before this function runs.
    """
    from app.models.risk_alert import RiskAlert
    from app.models.trading_session import TradingSession
    from sqlalchemy import and_
    import pytz

    now_utc = datetime.now(timezone.utc)
    five_min_ago = now_utc - timedelta(minutes=5)
    today_ist = datetime.now(pytz.timezone("Asia/Kolkata")).date()

    # Check today's session alert count
    session_result = await db.execute(
        select(TradingSession).where(
            and_(
                TradingSession.broker_account_id == broker_account_id,
                TradingSession.session_date == today_ist,
            )
        )
    )
    session = session_result.scalar_one_or_none()
    session_alert_count = session.alerts_fired if session else 0

    HARD_CAP = 8
    if session_alert_count >= HARD_CAP:
        logger.info(
            f"[consolidation] {broker_account_id}: session alert cap reached "
            f"({session_alert_count}/{HARD_CAP}). Suppressing {len(alerts)} notifications."
        )
        return []  # All alerts saved to DB, none will notify

    # 5-minute bucket: check for recent same-pattern alerts
    recent_result = await db.execute(
        select(RiskAlert).where(
            and_(
                RiskAlert.broker_account_id == broker_account_id,
                RiskAlert.detected_at >= five_min_ago,
            )
        )
    )
    recent_patterns = {a.pattern_type for a in recent_result.scalars().all()}

    notifiable = []
    for alert in alerts:
        if alert.pattern_type in recent_patterns:
            logger.debug(
                f"[consolidation] {broker_account_id}: suppressing {alert.pattern_type} "
                f"— already fired in last 5 min"
            )
        else:
            notifiable.append(alert)
            recent_patterns.add(alert.pattern_type)

    # Increment session alert count for notifiable alerts
    if notifiable and session:
        from app.services.trading_session_service import TradingSessionService
        for _ in notifiable:
            await TradingSessionService.increment_alerts_fired(session.id, db)
        await db.commit()

    return notifiable



@celery_app.task(bind=True, max_retries=3)
def send_danger_alert(self, broker_account_id: str, alert_id: str):
    """Send WhatsApp and Push notifications for danger pattern."""
    import asyncio

    async def _send():
        async with SessionLocal() as db:
            from app.models.risk_alert import RiskAlert
            from app.services.alert_service import AlertService
            from app.services.push_notification_service import push_service

            result = await db.execute(
                select(RiskAlert).where(RiskAlert.id == UUID(alert_id))
            )
            alert = result.scalar_one_or_none()
            if not alert:
                return {"error": "Alert not found"}

            account_result = await db.execute(
                select(BrokerAccount).where(BrokerAccount.id == UUID(broker_account_id))
            )
            account = account_result.scalar_one_or_none()
            if not account:
                return {"error": "Account not found"}

            results = {"whatsapp": False, "push": {"sent": 0, "failed": 0}}

            # 1. Push notification — non-fatal, device delivery is best-effort
            try:
                push_result = await push_service.send_risk_alert_notification(alert, db)
                results["push"] = push_result
                logger.info(f"Push notification: {push_result}")
            except Exception as e:
                logger.error(f"Push notification failed: {e}")

            # 2. WhatsApp alert — propagates on failure so task can retry
            user = await db.get(User, account.user_id) if account.user_id else None
            phone = user.guardian_phone if user else None
            if phone:
                alert_service = AlertService()
                sent = await alert_service.send_risk_alert(alert, account, phone)
                results["whatsapp"] = sent

            return results

    try:
        return asyncio.run(_send())
    except Exception as exc:
        logger.error(f"send_danger_alert failed (attempt {self.request.retries + 1}): {exc}")
        raise self.retry(exc=exc, countdown=min(2 ** self.request.retries * 30, 300))


@celery_app.task
def eod_sync_all_accounts():
    """
    End-of-day sync for all connected broker accounts.

    Scheduled at 3:35 PM IST (Monday–Friday) — 5 minutes after NSE/NFO/BSE/BFO close.
    This is the ONLY periodic sync. No polling during the day.

    Purpose:
      - Ensure all today's fills are in DB (catches any missed webhooks)
      - Create CompletedTrades for cross-day positions (overnight holds closed today)
        using kite.positions()["net"] data, which expires at end of day
      - Feed accurate EOD state into behavioral analysis and daily reports

    Not triggered by Celery Beat alone — also called explicitly when needed
    (e.g., MCX accounts that trade past 15:30).
    """
    import asyncio

    async def _sync_all():
        async with SessionLocal() as db:
            result = await db.execute(
                select(BrokerAccount).where(
                    BrokerAccount.status == "connected",
                    BrokerAccount.access_token.isnot(None),
                )
            )
            accounts = result.scalars().all()
            logger.info(f"[EOD sync] Starting for {len(accounts)} connected account(s)")

            for account in accounts:
                try:
                    sync_trades_for_account.delay(str(account.id))
                    logger.info(f"[EOD sync] Queued sync for account {account.id}")
                except Exception as e:
                    logger.error(f"[EOD sync] Failed to queue {account.id}: {e}")

            return {"queued": len(accounts)}

    import asyncio as _asyncio
    return _asyncio.run(_sync_all())
