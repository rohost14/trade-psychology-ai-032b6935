from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import hashlib
import logging
from datetime import datetime
from uuid import UUID

from app.core.database import get_db
from app.models.broker_account import BrokerAccount
from app.models.trade import Trade
from app.services.trade_sync_service import TradeSyncService
from app.utils.trade_classifier import classify_trade
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/zerodha/postback")
async def zerodha_postback(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Receive real-time order updates from Zerodha.
    
    Zerodha sends webhooks when:
    - Order placed
    - Order executed (filled)
    - Order modified
    - Order cancelled
    - Order rejected
    
    We process COMPLETE orders immediately for risk detection.
    """
    try:
        # 1. Get raw payload
        body = await request.body()
        form_data = await request.form()
        
        logger.info(f"Received postback from Zerodha")
        logger.debug(f"Postback data: {dict(form_data)}")
        
        # 2. Verify checksum (CRITICAL for security)
        checksum = form_data.get("checksum")
        api_secret = settings.ZERODHA_API_SECRET
        
        # Zerodha sends checksum as SHA256(api_secret + postback_data)
        # We need to verify this to ensure request is from Zerodha
        
        # Build string to hash (exclude checksum itself)
        data_to_hash = "&".join([
            f"{k}={v}" for k, v in sorted(form_data.items())
            if k != "checksum"
        ])
        
        expected_checksum = hashlib.sha256(
            f"{api_secret}{data_to_hash}".encode()
        ).hexdigest()
        
        if checksum != expected_checksum:
            logger.warning(f"Invalid checksum in postback. Possible attack.")
            raise HTTPException(403, "Invalid checksum")
        
        # 3. Extract order data
        order_data = {
            "order_id": form_data.get("order_id"),
            "exchange_order_id": form_data.get("exchange_order_id"),
            "status": form_data.get("status"),
            "tradingsymbol": form_data.get("tradingsymbol"),
            "exchange": form_data.get("exchange"),
            "transaction_type": form_data.get("transaction_type"),
            "order_type": form_data.get("order_type"),
            "product": form_data.get("product"),
            "quantity": int(form_data.get("quantity", 0)),
            "filled_quantity": int(form_data.get("filled_quantity", 0)),
            "pending_quantity": int(form_data.get("pending_quantity", 0)),
            "cancelled_quantity": int(form_data.get("cancelled_quantity", 0)),
            "price": float(form_data.get("price", 0)),
            "average_price": float(form_data.get("average_price", 0)),
            "status_message": form_data.get("status_message"),
            "order_timestamp": form_data.get("order_timestamp"),
            "exchange_timestamp": form_data.get("exchange_timestamp"),
        }
        
        # 4. Extract user identification from tag
        # Zerodha allows setting "tag" field when placing orders
        # We'll use format: "user_{broker_account_id}"
        tag = form_data.get("tag", "")
        
        if not tag or not tag.startswith("user_"):
            logger.warning(f"Postback received without valid tag: {tag}")
            # We can't identify the user, but acknowledge receipt
            return {"status": "ok", "message": "No user tag found"}
        
        # Extract broker_account_id from tag
        broker_account_id_str = tag.replace("user_", "")
        
        try:
            broker_account_id = UUID(broker_account_id_str)
        except:
            logger.error(f"Invalid broker_account_id in tag: {broker_account_id_str}")
            return {"status": "ok", "message": "Invalid user tag"}
        
        # 5. Get broker account
        result = await db.execute(
            select(BrokerAccount).where(BrokerAccount.id == broker_account_id)
        )
        broker_account = result.scalar_one_or_none()
        
        if not broker_account:
            logger.error(f"Broker account not found: {broker_account_id}")
            return {"status": "ok", "message": "Account not found"}
        
        # 6. Classify trade
        classification = classify_trade(order_data)
        
        # 7. Prepare trade data
        trade_data = {
            "user_id": broker_account.user_id,
            "broker_account_id": broker_account_id,
            "order_id": order_data["order_id"],
            "tradingsymbol": order_data["tradingsymbol"],
            "exchange": order_data["exchange"],
            "transaction_type": order_data["transaction_type"],
            "order_type": order_data["order_type"],
            "product": order_data["product"],
            "quantity": order_data["quantity"],
            "filled_quantity": order_data["filled_quantity"],
            "pending_quantity": order_data["pending_quantity"],
            "cancelled_quantity": order_data["cancelled_quantity"],
            "price": order_data["price"],
            "average_price": order_data["average_price"],
            "status": order_data["status"],
            "status_message": order_data.get("status_message"),
            "asset_class": classification["asset_class"],
            "instrument_type": classification["instrument_type"],
            "product_type": classification["product_type"],
            "order_timestamp": datetime.fromisoformat(order_data["order_timestamp"]),
            "exchange_timestamp": datetime.fromisoformat(order_data["exchange_timestamp"]) if order_data.get("exchange_timestamp") else None,
            "raw_payload": dict(form_data)
        }
        
        # 8. Upsert trade to database
        sync_service = TradeSyncService()
        await sync_service.upsert_trade(db, trade_data, broker_account_id)
        await db.commit()
        
        logger.info(f"Postback processed: {order_data['order_id']} - Status: {order_data['status']}")
        
        # 9. If trade is COMPLETE, trigger risk detection
        if order_data["status"] == "COMPLETE":
            logger.info(f"Trade completed: {order_data['tradingsymbol']} - Running risk detection")
            
            # Trigger risk detection
            from app.services.risk_detector import RiskDetector
            risk_detector = RiskDetector()
            
            # Get the just-saved trade to ensure we have latest DB state
            result = await db.execute(
                select(Trade).where(Trade.order_id == order_data["order_id"])
            )
            saved_trade = result.scalar_one_or_none()
            
            alerts = await risk_detector.detect_patterns(
                broker_account_id,
                db,
                trigger_trade=saved_trade
            )
            
            # Save alerts
            for alert in alerts:
                db.add(alert)
            
            await db.commit()
            
            if alerts:
                logger.warning(f"⚠️ RISK ALERT: {len(alerts)} pattern(s) detected")
                
                danger_alerts = [a for a in alerts if a.severity == "danger"]
                
                if danger_alerts:
                    # Send WhatsApp alerts for DANGER patterns
                    from app.services.alert_service import AlertService
                    alert_service = AlertService()
                    
                    # Get broker account for phone number
                    # For Phase 1: Use hardcoded test number
                    # Phase 2: Get from broker_account.user.phone
                    
                    # TODO: Replace with actual user phone from database
                    test_phone = "+919011230038"  # User's WhatsApp number
                    
                    for danger_alert in danger_alerts:
                        try:
                            sent = await alert_service.send_risk_alert(
                                danger_alert,
                                broker_account,
                                test_phone
                            )
                            if sent:
                                logger.info(f"📱 WhatsApp alert sent for {danger_alert.pattern_type}")
                        except Exception as e:
                            logger.error(f"Alert send failed: {e}")
                
                for alert in alerts:
                    logger.warning(f"  {alert.severity.upper()}: {alert.message}")
        
        # 10. Always return 200 OK quickly
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Postback processing error: {e}", exc_info=True)
        # Still return 200 to Zerodha (they don't retry on 500)
        return {"status": "error", "message": str(e)}
