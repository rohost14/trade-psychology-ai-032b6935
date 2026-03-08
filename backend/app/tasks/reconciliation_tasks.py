"""
Reconciliation Tasks (Celery Beat)

Runs once daily at 4:00 AM IST (off-peak) to catch any trades missed
by webhooks during the previous trading day.

This is NOT a polling loop. Webhooks + KiteTicker on_order_update handle
real-time order updates. This is the safety net only.

Logic:
  kite_complete_orders (yesterday) - our_stored_order_ids = missing trades
  → re-queue missing trades via process_webhook_trade

Staggered to respect Kite rate limits:
  Process 10 accounts per second → 1000 users = ~100 seconds total.
  All done at 4 AM, no user impact.
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
    Celery Beat task — runs once daily at 4:00 AM IST.

    Finds COMPLETE orders from the previous trading day that exist in Kite
    but not in our DB. Re-queues them for processing.
    Staggered: 10 accounts per second to respect Kite rate limits.
    """
    import asyncio
    return asyncio.get_event_loop().run_until_complete(_reconcile_all_accounts())


async def _reconcile_all_accounts():
    """Inner async function — reconciles all connected broker accounts."""
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
        # Stagger: process 10 accounts per second to respect Kite rate limits.
        # 1000 users → ~100 seconds at 4 AM. No user impact.
        BATCH_SIZE = 10
        for i, account in enumerate(accounts):
            try:
                missing = await _reconcile_account(account, db)
                total_missing += missing
            except Exception as e:
                logger.error(
                    f"[reconcile] Failed for account {account.id}: {e}",
                    exc_info=True
                )
            # Pause 1 second after every batch of 10
            if (i + 1) % BATCH_SIZE == 0:
                await asyncio.sleep(1)

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


def _today_ist_start_utc() -> datetime:
    """
    Return yesterday's market day start (00:00 IST) as UTC datetime.
    At 4 AM IST, 'yesterday' is the trading day we want to reconcile.
    """
    yesterday_ist = (
        datetime.now(IST) - timedelta(days=1)
    ).replace(hour=0, minute=0, second=0, microsecond=0)
    return yesterday_ist.astimezone(timezone.utc)
