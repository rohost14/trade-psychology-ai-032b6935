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
from app.core.trading_defaults import COLD_START_DEFAULTS
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
    """Return a sync Redis client from the shared pool.
    Pool is lazily initialized on first call — safe for Celery import time."""
    from app.core.redis_pool import get_sync_redis
    return get_sync_redis()


def _pattern_dedup_key(pattern_type: str, details) -> str:
    """
    Dedup key for alerts. constitution_violation covers many rules under one
    pattern_type (Q15) — a cooldown breach must not suppress a later daily-loss
    breach, so the rule joins the key.
    """
    if pattern_type == "constitution_violation":
        return f"constitution_violation:{(details or {}).get('rule', '')}"
    return pattern_type


# Dedup v2 stateful re-arm (Engine v2 1B.9): within the dedup window a
# pattern may re-fire if its driving metric got MATERIALLY worse - martingale
# fires again when size doubles again, not on a clock. Metric per pattern:
_WORSEN_METRIC = {
    "martingale_behaviour":   "max_ratio",
    "premium_loss_event":     "loss_pct",
    "same_symbol_obsession":  "total_loss",
    "constitution_violation": "ratio",
    "profit_giveaway":        "erosion_pct",  # deepening giveback re-fires
}
_WORSEN_FACTOR = 1.20  # metric must grow >=20% past the last fired value


def _worsened(pattern_type: str, old_details, new_details) -> bool:
    key = _WORSEN_METRIC.get(pattern_type)
    if not key:
        return False
    try:
        old_v = float((old_details or {}).get(key))
        new_v = float((new_details or {}).get(key))
    except (TypeError, ValueError):
        return False
    return old_v > 0 and new_v >= old_v * _WORSEN_FACTOR


async def _persist_events(db, events, surviving_by_key: dict, deduped_keys: set):
    """
    P0 fix #1: insert BehaviorEvents with ON CONFLICT DO NOTHING on the
    idempotency key - webhook retries and bulk-sync re-processing become
    insert-safe. Alert linkage / dedup markers applied before insert.
    """
    if not events:
        return
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from app.models.behavior_event import BehaviorEvent
    from uuid import uuid4 as _uuid4

    from app.services.detector_registry import BY_NAME as _SPECS_G
    from app.core.metrics import incr as _mi_gate

    rows = []
    for ev in events:
        # P2 write gating (review S7): info events from ALERTING detectors
        # with no suppression marker are confidence-demoted noise (e.g.
        # revenge at 30 confidence) - half the write volume, near-zero read
        # value. Analytics-disposition info events are the product (journal,
        # strategy driver) and suppressed evidence is sacred (1C.8) - both kept.
        if ev.severity == "info":
            spec = _SPECS_G.get(ev.detector)
            suppressed = bool((ev.evidence or {}).get("_suppressed"))
            if spec and spec.disposition == "alerting" and not suppressed:
                _mi_gate("events_info_gated")
                continue
        ek = _pattern_dedup_key(ev.detector, ev.evidence)
        risk_alert_id = surviving_by_key.get(ek)
        evidence = ev.evidence or {}
        if risk_alert_id is None and ek in deduped_keys:
            evidence = {**evidence, "_suppressed": "dedup"}
        rows.append({
            "id": _uuid4(),
            "broker_account_id": ev.broker_account_id,
            "detector": ev.detector,
            "detector_version": ev.detector_version,
            "severity": ev.severity,
            "confidence": ev.confidence,
            "data_quality": ev.data_quality,
            "message": ev.message,
            "evidence": evidence,
            "input_snapshot": ev.input_snapshot,
            "trigger_completed_trade_id": ev.trigger_completed_trade_id,
            "risk_alert_id": risk_alert_id,
            "idempotency_key": ev.idempotency_key,
            "detected_at": ev.detected_at,
        })
    stmt = pg_insert(BehaviorEvent).values(rows).on_conflict_do_nothing()
    result = await db.execute(stmt)
    from app.core.metrics import incr as _mi
    written = result.rowcount if result.rowcount is not None and result.rowcount >= 0 else len(rows)
    _mi("events_written", written)
    if written < len(rows):
        _mi("events_conflict_skipped", len(rows) - written)


async def _already_analyzed(broker_account_id: UUID, completed_trade_id, db) -> bool:
    """
    P0 fix #5: idempotency pre-check. If evidence already exists for this
    trigger trade, a previous attempt completed its commit - re-running
    analyze() would double-increment the session risk score and re-notify.
    """
    from app.models.behavior_event import BehaviorEvent
    result = await db.execute(
        select(BehaviorEvent.id).where(and_(
            BehaviorEvent.broker_account_id == broker_account_id,
            BehaviorEvent.trigger_completed_trade_id == completed_trade_id,
        )).limit(1)
    )
    return result.scalar_one_or_none() is not None


def _incr_metric(name: str, n: int = 1):
    """P1: delegate to the metrics module (daily buckets, TTL)."""
    from app.core.metrics import incr
    incr(name, n)


async def _run_death_spiral(broker_account_id: UUID, db, latest_trade_time=None):
    """
    Phase 5 meta-detector (L2): evaluates today's BehaviorEvents for the
    death-spiral state and persists alert + evidence when it fires.
    Dedup: severity-escalation-only within the day (warning->danger->critical
    each fire once). Returns the new RiskAlert or None.
    """
    from zoneinfo import ZoneInfo as _ZI
    from app.models.behavior_event import BehaviorEvent
    from app.models.risk_alert import RiskAlert
    from app.services.behavior_scores_service import evaluate_death_spiral
    from app.services.behavior_engine import ENGINE_VERSION
    from uuid import uuid4 as _uuid4

    now_utc = datetime.now(timezone.utc)
    ist_now = now_utc.astimezone(_ZI("Asia/Kolkata"))
    day_start = ist_now.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)

    ev_result = await db.execute(
        select(BehaviorEvent).where(and_(
            BehaviorEvent.broker_account_id == broker_account_id,
            BehaviorEvent.detected_at >= day_start,
            # Shadow detector events never contribute to the death-spiral verdict.
            BehaviorEvent.shadow.is_(False),
        ))
    )
    events = list(ev_result.scalars().all())
    verdict = evaluate_death_spiral(events, now_utc)
    if not verdict:
        return None

    _RANK = {"info": 0, "caution": 1, "danger": 2, "critical": 3}
    prior_result = await db.execute(
        select(RiskAlert).where(and_(
            RiskAlert.broker_account_id == broker_account_id,
            RiskAlert.pattern_type == "death_spiral",
            RiskAlert.detected_at >= day_start,
        ))
    )
    prior = list(prior_result.scalars().all())
    max_prior = max((_RANK.get(a.severity, 0) for a in prior), default=-1)
    if _RANK.get(verdict["severity"], 0) <= max_prior:
        return None  # already fired at this level or higher today

    detected_at = latest_trade_time or now_utc
    alert = RiskAlert(
        id=_uuid4(),
        broker_account_id=broker_account_id,
        pattern_type="death_spiral",
        severity=verdict["severity"],
        message=verdict["message"],
        details=verdict["context"],
        trigger_completed_trade_id=None,
        detector_version="1.0.0",
        confidence=90.0,  # multi-domain agreement IS the confidence
        detected_at=detected_at,
    )
    db.add(alert)
    await db.flush()
    db.add(BehaviorEvent(
        broker_account_id=broker_account_id,
        detector="death_spiral",
        detector_version="1.0.0",
        severity=verdict["severity"],
        confidence=90.0,
        data_quality="GOOD",
        message=verdict["message"],
        evidence=verdict["context"],
        input_snapshot={"source": "meta", "events_considered": len(events)},
        risk_alert_id=alert.id,
        detected_at=detected_at,
    ))
    await db.commit()
    logger.warning(
        f"[death_spiral] {broker_account_id}: {verdict['severity'].upper()} - "
        f"domains={verdict['context'].get('domains')}"
    )
    return alert


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


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60, time_limit=120, soft_time_limit=110)
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

                # BUG-3 fix: filter CNC/delivery trades before any processing
                product = trade_data.get("product", "")
                if product and product not in {"MIS", "NRML", "MTF"}:
                    logger.debug(f"Webhook: skipping product={product} trade {trade_data.get('order_id')}")
                    return {"success": True, "skipped": f"product={product}"}

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

                # Refresh KiteTicker subscriptions — a new position may have opened.
                # The shared ticker lives in the FastAPI process, NOT in this Celery
                # worker, so calling price_stream.refresh_subscriptions() here would only
                # touch a dead process-local singleton (and could spawn a rogue second
                # KiteTicker). Instead we publish an internal event; the FastAPI event
                # subscriber (which owns the live ticker) performs the refresh locally.
                from app.core.event_bus import publish_event
                publish_event(str(account_id), "subscription_refresh", {}, replay=False)

                # Publish position update event (durable, replayable)
                publish_event(str(account_id), "position_update", {
                    "order_id": trade_data.get("order_id"),
                    "status": trade_data.get("status"),
                })

                # Push margin data to frontend.
                # Cache TTL = 60s — serves all fills within same trading minute
                # from cache, avoiding a REST call per fill during active sessions.
                try:
                    # BrokerAccount already imported at module scope (line 23).
                    # Do NOT re-import here: a local import would make the name
                    # function-local and break the earlier use at the top of _process.
                    from app.services.zerodha_service import zerodha_client, KiteTokenExpiredError
                    import json as _json

                    _r = _get_redis_client()
                    _margin_key = f"margin:{account_id}"
                    _cached = _r.get(_margin_key)
                    if _cached:
                        # Serve from cache — no REST call
                        publish_event(str(account_id), "margin_update", _json.loads(_cached))
                    else:
                        account_record = await db.get(BrokerAccount, account_id)
                        if account_record and account_record.access_token and not account_record.token_revoked_at:
                            access_token = account_record.decrypt_token(account_record.access_token)
                            margins = await zerodha_client.get_margins(access_token)
                            _r.set(_margin_key, _json.dumps(margins), ex=60)
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
                _closed_ct_id: UUID = None  # set when a CompletedTrade is created this pipeline run

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
                            occurred_at=(
                                trade.fill_timestamp
                                or trade.exchange_timestamp
                                or trade.order_timestamp
                                or datetime.now(timezone.utc)
                            ),
                            idempotency_key=f"{trade.order_id}:ledger",
                            product=trade.product or trade.product_type,   # M1: position key
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
                                _closed_ct_id = ct.id  # pass to run_risk_detection_async below
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
                        behavior_lock_acquired = _acquire_lock(redis_client, behavior_lock_key, ttl_seconds=60)
                        if behavior_lock_acquired:
                            break
                        await _asyncio.sleep(2)

                    if not behavior_lock_acquired:
                        # P0 fix #2: skipping detection silently loses exactly
                        # the burst-moment analysis that matters most. Requeue
                        # the detection via the idempotent bulk path (pre-check
                        # + unique index make re-processing safe) and COUNT it.
                        _incr_metric("behavior_lock_exhausted")
                        _incr_metric("behavior_requeued")
                        logger.error(
                            f"behavior_lock exhausted for {broker_account_id} - "
                            f"requeuing detection for trade {trade.id}"
                        )
                        run_behavior_detection_retry.apply_async(
                            args=[str(broker_account_id)], countdown=10,
                        )
                        return {"success": True, "trade_id": str(trade.id),
                                "behavior_requeued": True}

                    await run_risk_detection_async(account_id, db, trade, completed_trade_id=_closed_ct_id)

                finally:
                    if redis_client and behavior_lock_acquired:
                        _release_lock(redis_client, behavior_lock_key)

                # ── Event-driven position checks (replaces beat tasks) ──────
                # These are fire-and-forget — failures don't retry the trade task.
                try:
                    from app.tasks.position_monitor_tasks import (
                        check_holding_loser_scheduled,
                        _overexposure_task,
                        _concentration_task,
                        _entry_rules_task,
                    )
                    # P2 coalescing (review S6.2): position checks run INLINE
                    # in this worker instead of 3 spawned Celery tasks - kills
                    # the task fan-out and its per-task connection churn.
                    # Each is individually non-fatal.
                    try:
                        await _overexposure_task(broker_account_id, trade.tradingsymbol or "")
                    except Exception as _oe:
                        logger.warning(f"overexposure inline check failed: {_oe}")
                    try:
                        await _concentration_task(broker_account_id)
                    except Exception as _ce:
                        logger.warning(f"concentration inline check failed: {_ce}")
                    if trade.transaction_type == "BUY":
                        try:
                            await _entry_rules_task(broker_account_id, trade.tradingsymbol or "")
                        except Exception as _ee:
                            logger.warning(f"entry rules inline check failed: {_ee}")
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

                # Portfolio-radar trigger removed 2026-07-26 — the task was archived
                # (broken AlertService integration; routers already archived 2026-07-25).

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


async def run_risk_detection_async(
    broker_account_id: UUID,
    db,
    trigger_trade: Trade = None,
    completed_trade_id: UUID = None,
):
    """
    Internal async helper for risk detection.

    Phase 3 cutover: uses BehaviorEngine as the single detection source.
    RiskDetector + BehavioralEvaluator are deprecated and no longer called.

    BehaviorEngine:
    - Session-scoped (today only, not 24h rolling)
    - Cumulative risk score via TradingSession
    - Returns RiskAlert objects ready for dedup + notification

    completed_trade_id: when provided, analyze that specific CompletedTrade rather
    than falling back to LIMIT 1 latest. Avoids race conditions when two trades
    close in rapid succession.
    """
    try:
        from app.models.risk_alert import RiskAlert
        from app.models.completed_trade import CompletedTrade
        from app.services.behavior_engine import behavior_engine
        from sqlalchemy import desc

        if completed_trade_id is not None:
            # P0 fix #5: skip if a prior (retried) attempt already committed
            # evidence for this trade - prevents risk-score double-increment
            # and duplicate notifications on Celery retries.
            if await _already_analyzed(broker_account_id, completed_trade_id, db):
                logger.info(
                    f"[BehaviorEngine] {broker_account_id}: trade "
                    f"{completed_trade_id} already analyzed - skipping (idempotent)"
                )
                _incr_metric("trades_skipped_idempotent")
                return
            latest_ct = await db.get(CompletedTrade, completed_trade_id)
        else:
            # Fallback: most recent CompletedTrade (used from eod_sync and legacy callers)
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

        # Run BehaviorEngine — returns RiskAlert objects + BehaviorEvent evidence
        from app.core.metrics import timer as _mtimer, observe_ms as _mobserve, incr as _mincr
        with _mtimer("analyze_ms"):
            result = await behavior_engine.analyze(
                broker_account_id=broker_account_id,
                completed_trade=latest_ct,
                db=db,
                source="webhook" if completed_trade_id is not None else "unknown",
            )
        _mincr("trades_analyzed")
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
        # HIGH-3 fix: track both timestamp and severity of last fire so that
        # severity escalation (caution → danger) is allowed through within the
        # dedup window. Previously the escalation code was unreachable — the
        # dedup `continue` ran before it.
        _SEV_RANK = {"info": 0, "caution": 1, "danger": 2, "critical": 3}
        last_fired: dict = {}      # dedup key -> datetime
        last_fired_sev: dict = {}  # dedup key -> severity string
        last_fired_details: dict = {}  # dedup key -> details (worsening re-arm)
        today_patterns: set = set()
        for a in all_existing:
            k = _pattern_dedup_key(a.pattern_type, a.details)
            today_patterns.add(a.pattern_type)
            if k not in last_fired or a.detected_at > last_fired[k]:
                last_fired[k] = a.detected_at
                last_fired_sev[k] = a.severity
                last_fired_details[k] = a.details

        def _is_deduped(key: str, pattern_type: str, new_severity: str, new_details=None) -> bool:
            if key not in last_fired:
                return False
            hours = _DEDUP_HOURS.get(pattern_type, 24)
            if (now_utc - last_fired[key]) >= timedelta(hours=hours):
                return False  # Window elapsed — allow
            # Within window: allow severity escalation through (caution → danger)
            prev_rank = _SEV_RANK.get(last_fired_sev.get(key, ""), 0)
            new_rank = _SEV_RANK.get(new_severity, 0)
            if new_rank > prev_rank:
                return False  # escalation always passes
            # Stateful re-arm (1B.9): same severity but the driving metric
            # materially worsened - fire again.
            if _worsened(pattern_type, last_fired_details.get(key), new_details):
                return False
            return True

        new_alerts = []
        deduped_keys = set()
        for alert in alerts:
            k = _pattern_dedup_key(alert.pattern_type, alert.details)
            if _is_deduped(k, alert.pattern_type, alert.severity, alert.details):
                deduped_keys.add(k)
                _mincr("alerts_deduped")
                continue
            db.add(alert)
            new_alerts.append(alert)
            last_fired[k] = latest_ct.exit_time or now_utc
            last_fired_sev[k] = alert.severity
            last_fired_details[k] = alert.details
            today_patterns.add(alert.pattern_type)

        # Persist BehaviorEvents for EVERY detection (§1C.8 — evidence is never
        # suppressed). Link each event to its surviving alert; deduped ones get
        # a marker instead of a link.
        # Flush alerts BEFORE adding events: the UOW does not order these
        # inserts by the risk_alert_id FK, and an event row referencing an
        # unflushed alert violates the FK (caught in Phase 1 validation).
        with _mtimer("persist_ms"):
            if new_alerts:
                await db.flush()
            surviving_by_key = {
                _pattern_dedup_key(a.pattern_type, a.details): a.id for a in new_alerts
            }
            await _persist_events(db, result.events, surviving_by_key, deduped_keys)
            await db.commit()
        _mincr("alerts_created", len(new_alerts))

        # THE SLO metric: trade completion -> detection persisted
        if latest_ct.exit_time:
            _mobserve("alert_e2e_lag_ms",
                      (now_utc - latest_ct.exit_time).total_seconds() * 1000)

        # ── Death spiral meta-check (Phase 5) — after evidence persisted ──
        try:
            with _mtimer("death_spiral_ms"):
                spiral_alert = await _run_death_spiral(
                    broker_account_id, db, latest_ct.exit_time or now_utc
                )
            if spiral_alert:
                new_alerts.append(spiral_alert)
        except Exception as _ds_err:
            logger.warning(f"[death_spiral] evaluation failed (non-fatal): {_ds_err}")

        # ── Alert consolidation (5-min bucket + hard cap) ─────────────
        new_alerts = await _apply_alert_consolidation(broker_account_id, new_alerts, db)

        # ── Send notifications for danger alerts ──────────────────────
        # Staleness gate (master Q12): push only when the triggering trade is
        # recent. detected_at = trade time, so bulk-synced old trades are
        # naturally suppressed here while still saved + visible in-app.
        danger_alerts = [a for a in new_alerts if a.severity in ("danger", "critical")]
        stale_cutoff = now_utc - timedelta(
            minutes=COLD_START_DEFAULTS.get("alert_stale_push_min", 30)
        )
        pushable = [a for a in danger_alerts if (a.detected_at or now_utc) >= stale_cutoff]
        suppressed = len(danger_alerts) - len(pushable)
        if suppressed:
            _mincr("notifications_stale_suppressed", suppressed)
            logger.info(
                f"[staleness] {broker_account_id}: {suppressed} danger alert(s) "
                f"older than push window — saved, not pushed"
            )
        # Per-pattern mute (migration 069): a muted pattern still saved its RiskAlert
        # above (visible in History) — only its real-time push is suppressed here.
        try:
            from app.models.alert_mute import AlertMute
            _mrows = await db.execute(
                select(AlertMute.pattern_type).where(
                    AlertMute.broker_account_id == broker_account_id
                )
            )
            _muted = {r[0] for r in _mrows.all()}
            if _muted:
                _before = len(pushable)
                pushable = [a for a in pushable if a.pattern_type not in _muted]
                _muted_n = _before - len(pushable)
                if _muted_n:
                    _mincr("notifications_muted_suppressed", _muted_n)
                    logger.info(
                        f"[mute] {broker_account_id}: {_muted_n} alert(s) not pushed "
                        f"(pattern muted) — still saved to history"
                    )
        except Exception as _mute_err:
            logger.debug(f"mute filter skipped: {_mute_err}")
        _mincr("notifications_dispatched", len(pushable))
        from app.services.detector_registry import BY_NAME as _SPECS_N
        guardian_alerts = [a for a in pushable
                           if (_SPECS_N.get(a.pattern_type)
                               and _SPECS_N[a.pattern_type].guardian_eligible)
                           or a.pattern_type == "death_spiral"]
        other_alerts = [a for a in pushable if a not in guardian_alerts]
        for alert in guardian_alerts:
            send_danger_alert.delay(str(broker_account_id), str(alert.id))
        if len(other_alerts) > 1:
            # One merged push instead of N (user gap #4: alert fatigue)
            try:
                from app.services.push_notification_service import push_service
                titles = [a.pattern_type.replace("_", " ") for a in other_alerts]
                await push_service.send_notification(
                    broker_account_id=broker_account_id,
                    title=f"{len(other_alerts)} risk patterns on your last trade",
                    body=" · ".join(a.message[:70] for a in other_alerts[:3]),
                    db=db,
                    data={"type": "merged_alerts",
                          "alert_ids": [str(a.id) for a in other_alerts]},
                    severity="danger",
                    tag="merged-risk",
                )
                _mincr("notifications_merged")
            except Exception as _mp_err:
                logger.warning(f"merged push failed, falling back: {_mp_err}")
                for alert in other_alerts:
                    send_danger_alert.delay(str(broker_account_id), str(alert.id))
        elif other_alerts:
            send_danger_alert.delay(str(broker_account_id), str(other_alerts[0].id))

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

        # Early warnings (soft nudges before danger threshold)
        try:
            from app.services.early_warning_service import check_early_warnings
            from app.services.push_notification_service import push_service
            ew_redis = _get_redis_client()
            ew_warnings = await check_early_warnings(broker_account_id, db, ew_redis)
            for w in ew_warnings:
                await push_service.send_notification(
                    broker_account_id=broker_account_id,
                    title=w["title"],
                    body=w["body"],
                    db=db,
                    data=w["data"],
                    severity=w.get("severity", "info"),
                    tag=w.get("tag", "early-warning"),
                )
        except Exception as ew_e:
            logger.warning(f"[EarlyWarning] non-critical failure: {ew_e}")

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

    # P0 fix #4: bulk sync must not race the webhook path on the same
    # account - same lock, abort with metric if unavailable (sync can rerun).
    _redis = None
    _lock_key = f"behavior_lock:{broker_account_id}"
    _lock_acquired = False
    try:
        _redis = _get_redis_client()
        for _ in range(5):
            _lock_acquired = _acquire_lock(_redis, _lock_key, ttl_seconds=300)
            if _lock_acquired:
                break
            import asyncio as _a
            await _a.sleep(2)
    except Exception as _lk_err:
        logger.warning(f"[FullSession] lock infra unavailable: {_lk_err}")
    if _redis is not None and not _lock_acquired:
        _incr_metric("behavior_bulk_lock_abort")
        logger.warning(
            f"[FullSession] {broker_account_id}: behavior_lock busy - aborting "
            f"bulk detection (webhook path active); rerun sync to retry"
        )
        return 0

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
    # HIGH-3 fix: track severity of last fire to allow caution → danger escalation.
    _SEV_RANK = {"info": 0, "caution": 1, "danger": 2, "critical": 3}
    last_fired: dict = {}
    last_fired_sev: dict = {}
    last_fired_details: dict = {}
    today_patterns: set = set()
    for a in all_existing:
        k = _pattern_dedup_key(a.pattern_type, a.details)
        today_patterns.add(a.pattern_type)
        if k not in last_fired or a.detected_at > last_fired[k]:
            last_fired[k] = a.detected_at
            last_fired_sev[k] = a.severity
            last_fired_details[k] = a.details

    def _is_deduped_full(key: str, pattern_type: str, trade_time: datetime, new_severity: str, new_details=None) -> bool:
        if key not in last_fired:
            return False
        hours = _DEDUP_HOURS.get(pattern_type, 24)
        # Use trade's own exit_time as reference (not now_utc) so bulk historical
        # replay doesn't incorrectly suppress same-session patterns.
        if (trade_time - last_fired[key]) >= timedelta(hours=hours):
            return False  # Window elapsed — allow
        # Within window: allow severity escalation (caution → danger)
        prev_rank = _SEV_RANK.get(last_fired_sev.get(key, ""), 0)
        new_rank = _SEV_RANK.get(new_severity, 0)
        if new_rank > prev_rank:
            return False
        if _worsened(pattern_type, last_fired_details.get(key), new_details):
            return False
        return True

    all_new_alerts: list[RiskAlert] = []

    for ct in trades_today:
        # P0 fix #1/#5: webhook path (or an earlier sync) already analyzed
        # this trade - skip. The unique index is the backstop; this is the
        # fast path that also avoids re-running detectors.
        if await _already_analyzed(broker_account_id, ct.id, db):
            continue
        trade_time = ct.exit_time or now_utc
        result = await behavior_engine.analyze(
            broker_account_id=broker_account_id,
            completed_trade=ct,
            db=db,
            source="bulk_sync",
        )
        surviving_by_key: dict = {}
        deduped_keys: set = set()
        for alert in result.alerts:
            k = _pattern_dedup_key(alert.pattern_type, alert.details)
            if _is_deduped_full(k, alert.pattern_type, trade_time, alert.severity, alert.details):
                deduped_keys.add(k)
                continue
            db.add(alert)
            all_new_alerts.append(alert)
            surviving_by_key[k] = alert.id
            last_fired[k] = ct.exit_time or now_utc
            last_fired_sev[k] = alert.severity
            last_fired_details[k] = alert.details
            today_patterns.add(alert.pattern_type)

        # Evidence records for every detection (§1C.8), linked where an alert survived.
        # Flush alerts first — FK ordering (see webhook path note).
        if surviving_by_key:
            await db.flush()
        await _persist_events(db, result.events, surviving_by_key, deduped_keys)

    # Commit regardless of alert survival — BehaviorEvents (evidence) must
    # persist even when every notification was deduped.
    await db.commit()

    # Death spiral meta-check (Phase 5). Staleness gate below keeps historical
    # replays from pushing; the alert row itself is still valuable evidence.
    try:
        last_time = trades_today[-1].exit_time if trades_today else now_utc
        spiral_alert = await _run_death_spiral(broker_account_id, db, last_time)
        if spiral_alert:
            all_new_alerts.append(spiral_alert)
    except Exception as _ds_err:
        logger.warning(f"[death_spiral] evaluation failed (non-fatal): {_ds_err}")

    if all_new_alerts:
        all_new_alerts = await _apply_alert_consolidation(broker_account_id, all_new_alerts, db)

        # Staleness gate (master Q12): bulk sync processes hours of history —
        # only trades closed within the push window may notify. Everything else
        # is saved for analytics/in-app only.
        danger_alerts = [a for a in all_new_alerts if a.severity in ("danger", "critical")]
        stale_cutoff = now_utc - timedelta(
            minutes=COLD_START_DEFAULTS.get("alert_stale_push_min", 30)
        )
        pushable = [a for a in danger_alerts if (a.detected_at or now_utc) >= stale_cutoff]
        suppressed = len(danger_alerts) - len(pushable)
        if suppressed:
            logger.info(
                f"[staleness/FullSession] {broker_account_id}: {suppressed} danger "
                f"alert(s) older than push window — saved, not pushed"
            )
        for alert in pushable:
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

    if _redis is not None and _lock_acquired:
        _release_lock(_redis, _lock_key)

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
    five_min_ago = now_utc - timedelta(
        minutes=COLD_START_DEFAULTS.get("alert_bucket_minutes", 5)
    )
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

    HARD_CAP = COLD_START_DEFAULTS.get("alert_session_hard_cap", 8)
    if session_alert_count >= HARD_CAP:
        # LOW-3: warn (not info) — danger alerts silently suppressed after cap is worth seeing in ops logs
        suppressed_summary = [f"{a.pattern_type}({a.severity})" for a in alerts]
        logger.warning(
            f"[consolidation] {broker_account_id}: session alert cap reached "
            f"({session_alert_count}/{HARD_CAP}). Suppressing: {suppressed_summary}"
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

    # LOW-1: batch counter increment — single DB write instead of N serial writes
    if notifiable and session:
        from app.services.trading_session_service import TradingSessionService
        await TradingSessionService.increment_alerts_fired(session.id, db, count=len(notifiable))
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

            # 2. WhatsApp (guardian) alert — propagates on failure so task can retry.
            # Phase 5 gates (§1B.8): guardian is emergency accountability, not
            # daily coaching. Only guardian-eligible patterns reach it, and a
            # hard monthly budget applies — a guardian pinged weekly stops reading.
            user = await db.get(User, account.user_id) if account.user_id else None
            phone = user.guardian_phone if user else None
            if phone:
                from app.services.detector_registry import BY_NAME as _SPECS
                spec = _SPECS.get(alert.pattern_type)
                guardian_ok = (
                    (spec.guardian_eligible if spec else alert.pattern_type == "death_spiral")
                    and alert.severity in ("danger", "critical")
                )
                if guardian_ok:
                    from app.services.behavior_scores_service import check_guardian_budget
                    guardian_ok = await check_guardian_budget(UUID(broker_account_id), db)
                if guardian_ok:
                    alert_service = AlertService()
                    sent = await alert_service.send_risk_alert(alert, account, phone)
                    results["whatsapp"] = sent
                else:
                    results["whatsapp"] = "skipped"

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


@celery_app.task(name="app.tasks.trade_tasks.run_behavior_detection_retry",
                 bind=True, max_retries=2, default_retry_delay=15)
def run_behavior_detection_retry(self, broker_account_id: str):
    """
    P0 fix #2: deferred detection after behavior_lock exhaustion. The full-
    session path is idempotent (per-trade pre-check + unique event index),
    so it safely analyzes exactly the trades the skipped webhook missed.
    """
    import asyncio

    async def _run():
        async with SessionLocal() as db:
            return await run_behavior_engine_full_session(UUID(broker_account_id), db)

    try:
        analyzed = asyncio.run(_run())
        return {"requeued_analysis_alerts": analyzed}
    except Exception as exc:
        # Bounded retry (max_retries=2). On exhaustion, surface it — a poison
        # account must not fail silently. Mirror process_webhook_trade's DLQ path.
        try:
            raise self.retry(exc=exc)
        except Exception as dlq_exc:
            from celery.exceptions import MaxRetriesExceededError
            if isinstance(dlq_exc, MaxRetriesExceededError):
                _incr_metric("behavior_detection_retry_dlq")
                try:
                    import sentry_sdk
                    sentry_sdk.capture_message(
                        f"[DLQ] run_behavior_detection_retry exhausted retries for "
                        f"account {broker_account_id}. Deferred detection lost.",
                        level="error",
                    )
                except Exception:
                    pass
                logger.error(
                    f"[DLQ] run_behavior_detection_retry: account {broker_account_id} "
                    f"lost after {self.max_retries} retries"
                )
            raise
