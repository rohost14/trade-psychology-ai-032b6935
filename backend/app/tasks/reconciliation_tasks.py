"""
Reconciliation Tasks (Celery Beat)

Runs once daily at 4:00 AM IST (off-peak). Two jobs:

  1. Missing-trade reconciliation:
     kite_complete_orders (yesterday) - our_stored_order_ids = missing trades
     → re-queue missing trades via process_webhook_trade

  2. Expired-position cleanup:
     F&O contracts that expire worthless generate no close order — the
     position stays open in our DB indefinitely. This job parses each
     open position's tradingsymbol to extract the expiry_date and zeros
     out any that have passed.

     Monthly contracts (expiry_date.day == 1 proxy): zeroed after the
     full expiry month has passed (conservative — avoids false positives).
     Weekly contracts (exact expiry_date): zeroed the next morning.

Staggered to respect Kite rate limits:
  Process 10 accounts per second → 1000 users = ~100 seconds total.
  All done at 4 AM, no user impact.
"""

import calendar
import logging
from datetime import date, datetime, timezone, timedelta
from uuid import UUID
from typing import List, Dict, Any
from zoneinfo import ZoneInfo

import pytz

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.core.market_hours import is_market_open, MarketSegment
from app.models.broker_account import BrokerAccount
from app.services.zerodha_service import zerodha_client, KiteTokenExpiredError, KiteAPIError
from app.services.instrument_parser import parse_symbol
from sqlalchemy import select, and_

logger = logging.getLogger(__name__)

IST = pytz.timezone("Asia/Kolkata")
_IST_TZ = ZoneInfo("Asia/Kolkata")

# NSE/BSE F&O market closes at 15:30 IST — use as canonical expiry time
_FNO_CLOSE_HOUR = 15
_FNO_CLOSE_MINUTE = 30

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
    return asyncio.run(_reconcile_all_accounts())


async def _reconcile_all_accounts():
    """Inner async function — reconciles all connected broker accounts."""
    today_ist = datetime.now(_IST_TZ).date()

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
        total_expired = 0
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
            try:
                expired = await _expire_stale_positions(account.id, today_ist)
                total_expired += expired
            except Exception as e:
                logger.error(
                    f"[reconcile] Expiry cleanup failed for account {account.id}: {e}",
                    exc_info=True
                )
            # Pause 1 second after every batch of 10
            if (i + 1) % BATCH_SIZE == 0:
                await asyncio.sleep(1)

    logger.info(
        f"[reconcile] Done. {len(accounts)} accounts checked, "
        f"{total_missing} missing trades re-queued, "
        f"{total_expired} expired positions zeroed."
    )
    return {
        "accounts_checked": len(accounts),
        "missing_requeued": total_missing,
        "expired_positions": total_expired,
    }


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


def _is_contract_expired(expiry_date: date, today: date) -> bool:
    """
    Return True if an F&O contract is definitively past its expiry.

    Monthly contracts (expiry_date.day == 1 proxy from instrument_parser):
      The parser uses day=1 because it doesn't resolve the exact last-Thursday.
      We only mark expired after the full expiry month has passed — conservative,
      avoids false positives mid-month.

    Weekly contracts (exact date from instrument_parser):
      Expired when expiry_date < today.
    """
    if expiry_date.day == 1:
        # Monthly proxy: safe only once the entire expiry month has passed
        last_day = calendar.monthrange(expiry_date.year, expiry_date.month)[1]
        return today > date(expiry_date.year, expiry_date.month, last_day)
    else:
        # Weekly (exact date): expired the next calendar day
        return expiry_date < today


async def _expire_stale_positions(account_id: UUID, today_ist: date) -> int:
    """
    Zero out open positions for F&O contracts past their expiry date.

    Called per-account from _reconcile_all_accounts. Opens its own session
    so writes are isolated from the read-only reconciliation session.

    Returns count of positions expired.
    """
    from app.models.position import Position

    async with SessionLocal() as db:
        result = await db.execute(
            select(Position).where(
                and_(
                    Position.broker_account_id == account_id,
                    Position.total_quantity != 0,
                )
            )
        )
        open_positions = result.scalars().all()

        # Max-age cutoff: F&O position not updated in 60 days is almost certainly
        # from an expired contract whose symbol format parse_symbol() couldn't parse.
        # Flag as stale rather than silently leaving indefinitely.
        _max_age_cutoff = datetime.now(timezone.utc) - timedelta(days=60)

        expired_count = 0
        for pos in open_positions:
            parsed = parse_symbol(pos.tradingsymbol)

            # Only CE/PE/FUT have expiry dates; EQ returns expiry_date=None
            if parsed.instrument_type not in ("CE", "PE", "FUT"):
                continue

            if not parsed.expiry_date:
                # Couldn't parse expiry (e.g. non-NSE symbol format or MCX contract).
                # Fallback: if position hasn't been updated in 60 days, mark as stale.
                last_update = pos.updated_at or pos.created_at
                if last_update and last_update < _max_age_cutoff:
                    logger.warning(
                        f"[reconcile] Unparseable expiry, position stale 60+ days: "
                        f"{pos.tradingsymbol} (account={str(account_id)[:8]}, "
                        f"qty={pos.total_quantity}, last_updated={last_update.date()}). "
                        f"Marking stale — manual review may be needed."
                    )
                    pos.status = "stale"
                    expired_count += 1
                continue

            if not _is_contract_expired(parsed.expiry_date, today_ist):
                continue

            # Expiry has passed — zero out the position
            old_qty = pos.total_quantity
            pos.total_quantity = 0
            pos.status = "expired"
            # Use 15:30 IST on the expiry date as canonical exit time
            pos.last_exit_time = datetime(
                parsed.expiry_date.year,
                parsed.expiry_date.month,
                parsed.expiry_date.day,
                _FNO_CLOSE_HOUR,
                _FNO_CLOSE_MINUTE,
                0,
                tzinfo=_IST_TZ,
            )
            expired_count += 1
            logger.warning(
                f"[reconcile] Expired position zeroed: {pos.tradingsymbol} "
                f"(account={str(account_id)[:8]}, qty={old_qty}, "
                f"expiry={parsed.expiry_date})"
            )

        if expired_count:
            await db.commit()

        return expired_count


def _today_ist_start_utc() -> datetime:
    """
    Return yesterday's market day start (00:00 IST) as UTC datetime.
    At 4 AM IST, 'yesterday' is the trading day we want to reconcile.
    """
    yesterday_ist = (
        datetime.now(IST) - timedelta(days=1)
    ).replace(hour=0, minute=0, second=0, microsecond=0)
    return yesterday_ist.astimezone(timezone.utc)
