"""
Reconciliation Tasks (Celery Beat)

Polls Kite API every 3 minutes during market hours to catch any trades
that were missed by webhooks (network blip, Celery downtime, retry exhaustion).

Logic:
  kite_complete_orders - our_stored_order_ids = missing trades
  → re-queue each missing trade as a process_webhook_trade task

This is the safety net for C-03/C-04. It does NOT replace webhooks —
webhooks remain the primary path. This poller catches the gaps.
"""

import logging
from datetime import datetime, date, timezone, timedelta
from uuid import UUID
from typing import List, Dict, Any

import pytz

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.core.market_hours import is_market_open, MarketSegment
from app.models.broker_account import BrokerAccount
from app.services.zerodha_service import zerodha_client, KiteTokenExpiredError, KiteAPIError
from sqlalchemy import select, and_

logger = logging.getLogger(__name__)

IST = pytz.timezone("Asia/Kolkata")

# Only reconcile COMPLETE orders — open/pending orders have no P&L to protect
RECONCILE_STATUS = "COMPLETE"

# Only these products are tracked (no CNC/delivery)
TRACKED_PRODUCTS = {"MIS", "NRML", "MTF"}


@celery_app.task(name="app.tasks.reconciliation_tasks.reconcile_trades")
def reconcile_trades():
    """
    Celery Beat task — runs every 3 minutes.

    Skips immediately if market is closed (weekends, holidays, off-hours).
    For each connected account, finds COMPLETE orders that exist in Kite
    but not in our DB, and re-queues them for processing.
    """
    import asyncio
    return asyncio.get_event_loop().run_until_complete(_reconcile_all_accounts())


async def _reconcile_all_accounts():
    """Inner async function — reconciles all connected broker accounts."""

    # Skip outside equity/F&O market hours (09:15 - 15:31 IST, weekdays only)
    # We use a 1-minute buffer past 15:30 to catch last-minute fills
    now_ist = datetime.now(IST)
    if not _is_reconcile_window(now_ist):
        logger.debug(f"[reconcile] Outside market window ({now_ist.strftime('%H:%M IST')}), skipping.")
        return {"skipped": True, "reason": "outside_market_hours"}

    async with SessionLocal() as db:
        # Get all connected accounts with a valid (non-revoked) token
        result = await db.execute(
            select(BrokerAccount).where(
                and_(
                    BrokerAccount.status == "connected",
                    BrokerAccount.access_token != None,       # noqa: E711
                    BrokerAccount.token_revoked_at == None,   # noqa: E711
                )
            )
        )
        accounts = result.scalars().all()

        if not accounts:
            logger.debug("[reconcile] No connected accounts to reconcile.")
            return {"accounts_checked": 0}

        total_missing = 0
        for account in accounts:
            try:
                missing = await _reconcile_account(account, db)
                total_missing += missing
            except Exception as e:
                logger.error(
                    f"[reconcile] Failed for account {account.id}: {e}",
                    exc_info=True
                )

    logger.info(
        f"[reconcile] Done. {len(accounts)} accounts checked, "
        f"{total_missing} missing trades re-queued."
    )
    return {"accounts_checked": len(accounts), "missing_requeued": total_missing}


async def _reconcile_account(account: BrokerAccount, db) -> int:
    """
    Reconcile one account. Returns count of missing trades re-queued.
    """
    from app.tasks.trade_tasks import process_webhook_trade

    account_id = str(account.id)

    # Decrypt token
    try:
        access_token = account.decrypt_token(account.access_token)
    except ValueError as e:
        logger.warning(f"[reconcile] {account_id}: token decrypt failed — {e}")
        return 0

    # Fetch today's orders from Kite
    try:
        kite_orders = await zerodha_client.get_orders(access_token)
    except KiteTokenExpiredError:
        logger.warning(f"[reconcile] {account_id}: token expired, skipping.")
        return 0
    except KiteAPIError as e:
        logger.warning(f"[reconcile] {account_id}: Kite API error — {e}")
        return 0

    # Filter to COMPLETE orders in tracked products only
    kite_complete = [
        o for o in kite_orders
        if o.get("status") == RECONCILE_STATUS
        and o.get("product") in TRACKED_PRODUCTS
    ]

    if not kite_complete:
        return 0

    # Build set of kite order_ids we need to have
    kite_order_ids = {str(o["order_id"]) for o in kite_complete}

    # Get today's order_ids we already have in DB for this account
    today_start = _today_ist_start_utc()
    from app.models.trade import Trade
    existing_result = await db.execute(
        select(Trade.order_id).where(
            and_(
                Trade.broker_account_id == account.id,
                Trade.status == RECONCILE_STATUS,
                Trade.order_timestamp >= today_start,
            )
        )
    )
    existing_ids = {str(row[0]) for row in existing_result.fetchall()}

    # Missing = in Kite but not in our DB
    missing_ids = kite_order_ids - existing_ids
    if not missing_ids:
        return 0

    logger.warning(
        f"[reconcile] {account_id}: {len(missing_ids)} missing trade(s) detected, re-queuing."
    )

    # Build a lookup from order_id → full order dict
    kite_by_id = {str(o["order_id"]): o for o in kite_complete}

    # Re-queue each missing trade exactly as if it came from a webhook
    queued = 0
    for order_id in missing_ids:
        order_data = kite_by_id.get(order_id)
        if not order_data:
            continue
        try:
            process_webhook_trade.delay(order_data, account_id)
            queued += 1
            logger.info(
                f"[reconcile] Re-queued order {order_id} for account {account_id}"
            )
        except Exception as e:
            logger.error(f"[reconcile] Failed to re-queue {order_id}: {e}")

    return queued


def _is_reconcile_window(now_ist: datetime) -> bool:
    """
    Returns True if we should run reconciliation right now.

    Window: 09:14 – 15:31 IST, weekdays only.
    (1 min before open to catch pre-open fills, 1 min after close for stragglers)
    """
    from datetime import time as dtime

    if now_ist.weekday() >= 5:  # Saturday=5, Sunday=6
        return False

    current = now_ist.time()
    return dtime(9, 14) <= current <= dtime(15, 31)


def _today_ist_start_utc() -> datetime:
    """Return today's market day start (00:00 IST) as UTC datetime."""
    today_ist = datetime.now(IST).replace(hour=0, minute=0, second=0, microsecond=0)
    return today_ist.astimezone(timezone.utc)
