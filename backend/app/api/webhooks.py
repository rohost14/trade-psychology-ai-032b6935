from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import hashlib
import logging
from datetime import datetime
from uuid import UUID
from typing import Optional

from app.core.database import get_db
from app.models.broker_account import BrokerAccount
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

# Flag to check if Celery is available
CELERY_ENABLED = True
try:
    from app.tasks.trade_tasks import process_webhook_trade
except ImportError:
    CELERY_ENABLED = False
    logger.warning("Celery tasks not available, falling back to sync processing")


def verify_zerodha_checksum(form_data: dict, api_secret: str) -> bool:
    """
    Verify Zerodha postback checksum for security.

    Kite sends: SHA-256(order_id + order_timestamp + api_secret)
    """
    checksum = form_data.get("checksum")
    if not checksum:
        logger.warning("Postback rejected: no checksum in form data or header")
        return False

    order_id = form_data.get("order_id", "")
    order_timestamp = form_data.get("order_timestamp", "")

    # Kite's checksum format
    expected_checksum = hashlib.sha256(
        f"{order_id}{order_timestamp}{api_secret}".encode()
    ).hexdigest()

    return checksum == expected_checksum


def verify_zerodha_checksum_header(order_id: str, timestamp: str, checksum: str, api_secret: str) -> bool:
    """
    Alternative verification using X-Kite-Checksum header.

    Some integrations send checksum in header instead of body.
    """
    expected = hashlib.sha256(
        f"{order_id}{timestamp}{api_secret}".encode()
    ).hexdigest()

    return expected == checksum


def extract_broker_account_id(tag: str) -> Optional[UUID]:
    """Extract broker_account_id from order tag."""
    if not tag or not tag.startswith("user_"):
        return None

    try:
        return UUID(tag.replace("user_", ""))
    except (ValueError, AttributeError):
        return None


@router.post("/zerodha/postback")
async def zerodha_postback(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Receive real-time order updates from Zerodha.

    Return codes:
    - 200: Validation failed (bad checksum, unknown account) — Zerodha must NOT retry.
    - 200: Successfully queued/processed.
    - 500: Infrastructure failure (Celery/Redis/DB down) — Zerodha WILL retry.
    """
    # 1. Parse payload
    form_data = await request.form()
    form_dict = dict(form_data)

    logger.info(f"Postback received: {form_dict.get('order_id')} - {form_dict.get('status')}")

    # 2. Extract broker account ID from tag early — needed to resolve per-user API secret
    tag = form_dict.get("tag", "")
    broker_account_id = extract_broker_account_id(tag)

    if not broker_account_id:
        logger.warning(f"No valid user tag in postback: {tag}")
        return {"status": "ok", "message": "No user tag"}

    # 3. Verify account exists and is active — return 200 for all non-active states
    #    so Zerodha does NOT retry (these are permanent states, retrying won't help).
    result = await db.execute(
        select(BrokerAccount).where(BrokerAccount.id == broker_account_id)
    )
    account = result.scalar_one_or_none()
    if not account:
        logger.warning(f"Postback for unknown account {broker_account_id} — discarding")
        return {"status": "ok", "message": "Account not found"}
    acct_status = account.status

    # 4. Verify checksum using per-user API secret (fallback to global if not stored)
    #    Must happen AFTER account lookup so we can use the right secret.
    api_secret = account.decrypt_api_secret() or settings.ZERODHA_API_SECRET or ""
    header_checksum = request.headers.get("X-Kite-Checksum")
    if header_checksum:
        is_valid = verify_zerodha_checksum_header(
            form_dict.get("order_id", ""),
            form_dict.get("order_timestamp", ""),
            header_checksum,
            api_secret,
        )
    else:
        is_valid = verify_zerodha_checksum(form_dict, api_secret)

    if not is_valid:
        logger.warning(f"Invalid checksum in postback for account {broker_account_id}")
        return {"status": "ok", "message": "Invalid checksum"}
    if acct_status == "deleted":
        logger.info(
            f"Postback for deleted account {broker_account_id} "
            f"(order {form_dict.get('order_id')}) — discarding (DPDP erasure)"
        )
        return {"status": "ok", "message": "Account deleted"}
    if acct_status == "suspended":
        logger.warning(
            f"Postback for suspended account {broker_account_id} "
            f"(order {form_dict.get('order_id')}) — discarding"
        )
        return {"status": "ok", "message": "Account suspended"}
    if acct_status != "connected":
        logger.warning(
            f"Postback for account {broker_account_id} with status={acct_status!r} "
            f"(order {form_dict.get('order_id')}) — discarding"
        )
        return {"status": "ok", "message": f"Account status: {acct_status}"}

    # 5. Build trade data for processing
    # H3: Early reject when all timestamps are NULL — impossible to do behavioral analysis
    _ts_fields = (
        form_dict.get("order_timestamp"),
        form_dict.get("exchange_timestamp"),
        form_dict.get("fill_timestamp"),
    )
    if not any(_ts_fields):
        logger.error(
            f"Postback rejected — order {form_dict.get('order_id')} "
            f"(status={form_dict.get('status')}): all timestamps are NULL. "
            f"Cannot determine entry/hold time for behavioral analysis."
        )
        return {"status": "ok", "message": "No timestamps"}

    def _si(key, default=0):
        """Safe int conversion — handles None, empty string, 'None' strings."""
        v = form_dict.get(key)
        try:
            return int(v) if v not in (None, "", "None") else default
        except (ValueError, TypeError):
            return default

    def _sf(key, default=0.0):
        """Safe float conversion — handles None, empty string, 'None' strings."""
        v = form_dict.get(key)
        try:
            return float(v) if v not in (None, "", "None") else default
        except (ValueError, TypeError):
            return default

    trade_data = {
        "order_id": form_dict.get("order_id"),
        "exchange_order_id": form_dict.get("exchange_order_id"),
        "status": form_dict.get("status"),
        "tradingsymbol": form_dict.get("tradingsymbol"),
        "exchange": form_dict.get("exchange"),
        "transaction_type": form_dict.get("transaction_type"),
        "order_type": form_dict.get("order_type"),
        "product": form_dict.get("product"),
        "quantity": _si("quantity"),
        "filled_quantity": _si("filled_quantity"),
        "pending_quantity": _si("pending_quantity"),
        "cancelled_quantity": _si("cancelled_quantity"),
        "price": _sf("price"),
        "average_price": _sf("average_price"),
        "trigger_price": _sf("trigger_price"),
        "status_message": form_dict.get("status_message"),
        "order_timestamp": form_dict.get("order_timestamp"),
        "exchange_timestamp": form_dict.get("exchange_timestamp"),
        "validity": form_dict.get("validity", "DAY"),
        "variety": form_dict.get("variety", "regular"),
        "disclosed_quantity": _si("disclosed_quantity"),
        "parent_order_id": form_dict.get("parent_order_id"),
        "tag": form_dict.get("tag"),
        "guid": form_dict.get("guid"),
        "instrument_token": _si("instrument_token") if form_dict.get("instrument_token") else None,
        "raw_payload": form_dict,
    }

    # 6. Dispatch to processing — infrastructure failures return 500 so Zerodha retries
    try:
        if CELERY_ENABLED:
            request_id = getattr(request.state, "request_id", "-")
            task = process_webhook_trade.delay(trade_data, str(broker_account_id), request_id)
            logger.info(f"Trade queued for processing: {task.id}")
            return {"status": "queued", "task_id": task.id}
        else:
            await process_trade_sync(trade_data, broker_account_id, db)
            return {"status": "ok", "processed": "sync"}
    except Exception as e:
        logger.error(f"Postback processing failed, Zerodha will retry: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Processing error")


async def process_trade_sync(trade_data: dict, broker_account_id: UUID, db: AsyncSession):
    """
    Fallback sync processing when Celery is not available.
    Used in development mode.
    """
    from app.services.trade_sync_service import TradeSyncService
    from app.utils.trade_classifier import classify_trade
    from app.services.risk_detector import RiskDetector
    from app.models.trade import Trade

    # Classify and transform
    classification = classify_trade(trade_data)
    normalized = TradeSyncService.transform_zerodha_order(trade_data)
    normalized["asset_class"] = classification["asset_class"]
    normalized["instrument_type"] = classification["instrument_type"]
    normalized["product_type"] = classification["product_type"]

    # Save trade
    _trade, _is_new = await TradeSyncService.upsert_trade(db, normalized, broker_account_id)
    await db.commit()

    # Trigger Immediate Position Sync
    try:
        await TradeSyncService.sync_positions(broker_account_id, db)
    except Exception as e:
        logger.error(f"Failed to sync positions in webhook fallback: {e}")

    # Risk detection for COMPLETE trades

    if trade_data.get("status") == "COMPLETE":
        result = await db.execute(
            select(Trade).where(Trade.order_id == trade_data["order_id"])
        )
        saved_trade = result.scalar_one_or_none()

        risk_detector = RiskDetector()
        alerts = await risk_detector.detect_patterns(
            broker_account_id, db, trigger_trade=saved_trade
        )

        for alert in alerts:
            db.add(alert)
        await db.commit()

        if alerts:
            logger.warning(f"Risk alerts created: {len(alerts)}")
