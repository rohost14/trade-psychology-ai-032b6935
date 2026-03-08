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

    # 2. Verify checksum — forged/tampered = 200 (no retry, nothing to recover)
    header_checksum = request.headers.get("X-Kite-Checksum")
    if header_checksum:
        is_valid = verify_zerodha_checksum_header(
            form_dict.get("order_id", ""),
            form_dict.get("order_timestamp", ""),
            header_checksum,
            settings.ZERODHA_API_SECRET
        )
    else:
        is_valid = verify_zerodha_checksum(form_dict, settings.ZERODHA_API_SECRET)

    if not is_valid:
        logger.warning("Invalid checksum in postback")
        return {"status": "ok", "message": "Invalid checksum"}

    # 3. Extract broker account ID from tag — untagged order = 200 (not our user)
    tag = form_dict.get("tag", "")
    broker_account_id = extract_broker_account_id(tag)

    if not broker_account_id:
        logger.warning(f"No valid user tag in postback: {tag}")
        return {"status": "ok", "message": "No user tag"}

    # 4. Verify account exists — deleted account = 200 (nothing to recover)
    result = await db.execute(
        select(BrokerAccount.id).where(BrokerAccount.id == broker_account_id)
    )
    if not result.scalar_one_or_none():
        logger.error(f"Broker account not found: {broker_account_id}")
        return {"status": "ok", "message": "Account not found"}

    # 5. Build trade data for processing
    trade_data = {
        "order_id": form_dict.get("order_id"),
        "exchange_order_id": form_dict.get("exchange_order_id"),
        "status": form_dict.get("status"),
        "tradingsymbol": form_dict.get("tradingsymbol"),
        "exchange": form_dict.get("exchange"),
        "transaction_type": form_dict.get("transaction_type"),
        "order_type": form_dict.get("order_type"),
        "product": form_dict.get("product"),
        "quantity": int(form_dict.get("quantity", 0)),
        "filled_quantity": int(form_dict.get("filled_quantity", 0)),
        "pending_quantity": int(form_dict.get("pending_quantity", 0)),
        "cancelled_quantity": int(form_dict.get("cancelled_quantity", 0)),
        "price": float(form_dict.get("price", 0)),
        "average_price": float(form_dict.get("average_price", 0)),
        "trigger_price": float(form_dict.get("trigger_price", 0)),
        "status_message": form_dict.get("status_message"),
        "order_timestamp": form_dict.get("order_timestamp"),
        "exchange_timestamp": form_dict.get("exchange_timestamp"),
        "validity": form_dict.get("validity", "DAY"),
        "variety": form_dict.get("variety", "regular"),
        "disclosed_quantity": int(form_dict.get("disclosed_quantity", 0)),
        "parent_order_id": form_dict.get("parent_order_id"),
        "tag": form_dict.get("tag"),
        "guid": form_dict.get("guid"),
        "instrument_token": int(form_dict.get("instrument_token", 0)) if form_dict.get("instrument_token") else None,
        "raw_payload": form_dict,
    }

    # 6. Dispatch to processing — infrastructure failures return 500 so Zerodha retries
    try:
        if CELERY_ENABLED:
            task = process_webhook_trade.delay(trade_data, str(broker_account_id))
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
