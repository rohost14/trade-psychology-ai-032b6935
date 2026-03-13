import asyncio
import uuid
import logging
from sqlalchemy import select
from app.core.database import SessionLocal
from app.models.broker_account import BrokerAccount
from app.models.trade import Trade
from app.models.position import Position
from app.api.deps import get_settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def reproduce_issue():
    async with SessionLocal() as db:
        # 1. Get a test account
        result = await db.execute(select(BrokerAccount))
        account = result.scalars().first()
        
        if not account:
            logger.error("No broker account found. Please connect an account first.")
            return

        logger.info(f"Using account: {account.id} ({account.broker_user_id})")

        # 2. Simulate a Webhook Payload for a new trade
        # Unique Order ID to avoid conflicts
        order_id = f"TEST_ORDER_{uuid.uuid4().hex[:8]}"
        symbol = "SBIN"
        qty = 100
        
        webhook_payload = {
            "order_id": order_id,
            "exchange_order_id": f"EX_{order_id}",
            "status": "COMPLETE",
            "tradingsymbol": symbol,
            "exchange": "NSE",
            "transaction_type": "BUY",
            "order_type": "MARKET",
            "product": "MIS",
            "quantity": qty,
            "filled_quantity": qty,
            "price": 500.0,
            "average_price": 500.0,
            "order_timestamp": "2024-01-01 10:00:00",
            "exchange_timestamp": "2024-01-01 10:00:01",
            "tag": f"user_{account.id}",  # Important for mapping
            "checksum": "dummy" # checksum validation is skipped if we call the task directly
        }

        # 3. Check baseline state
        logger.info(f"--- Baseline ---")
        trade_q = await db.execute(select(Trade).where(Trade.order_id == order_id))
        logger.info(f"Trade exists? {trade_q.scalar_one_or_none() is not None}")
        
        # 4. Call process_webhook_trade DIRECTLY (bypassing API/Celery for sync test)
        # We simulate what the Celery task does
        logger.info(f"--- Simulating Webhook Processing ---")
        from app.tasks.trade_tasks import process_webhook_trade
        
        # process_webhook_trade is a Celery task, so we call the underlying async function logic
        # But wait, the task itself defines specific logic.
        # Let's import the task and run its logic. 
        # Since it's decorated, we might need to look at how to invoke it synchronously.
        # Or simpler: Call the service logic that the task calls.
        
        # Actually, let's call the API endpoint handler logic to be more realistic, 
        # OR just call `process_webhook_trade.apply(args=[webhook_payload, str(account.id)])` if we want to run it eager.
        # But we don't have celery eager configured.
        # Let's manually run the logic inside `process_webhook_trade`.
        
        from app.services.trade_sync_service import TradeSyncService
        from app.utils.trade_classifier import classify_trade
        
        # LOGIC FROM TASK copied here for reproduction
        classification = classify_trade(webhook_payload)
        normalized = TradeSyncService.transform_zerodha_order(webhook_payload)
        normalized["asset_class"] = classification["asset_class"]
        normalized["instrument_type"] = classification["instrument_type"]
        normalized["product_type"] = classification["product_type"]
        
        trade, is_new = await TradeSyncService.upsert_trade(db, normalized, account.id)
        await db.commit()
        logger.info(f"Trade upserted: {is_new}")

        # 5. Verify Trade Table
        logger.info(f"--- Verification ---")
        trade_q = await db.execute(select(Trade).where(Trade.order_id == order_id))
        saved_trade = trade_q.scalar_one_or_none()
        logger.info(f"Trade Table Updated: {'YES' if saved_trade else 'NO'}")

        # 6. Verify Position Table
        # We expect a position for SBIN MIS
        pos_q = await db.execute(
            select(Position).where(
                Position.broker_account_id == account.id,
                Position.tradingsymbol == symbol,
                Position.product == "MIS"
            )
        )
        position = pos_q.scalar_one_or_none()
        
        logger.info(f"Position Table Updated: {'YES' if position else 'NO'}")
        
        if position:
            logger.info(f"Position Qty: {position.total_quantity}")
            if position.total_quantity != qty:
                 logger.info("Position exists but quantity mismatch (stale?)")
        else:
            logger.info("Position does NOT exist (Confirmed Gap)")

        # Cleanup
        if saved_trade:
            await db.delete(saved_trade)
            await db.commit()
            logger.info("Cleanup: Deleted test trade")

if __name__ == "__main__":
    asyncio.run(reproduce_issue())
