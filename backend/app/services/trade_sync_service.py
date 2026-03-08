import logging
import uuid
from datetime import datetime, date, timedelta, timezone
from typing import Dict, Any, List, Optional
from zoneinfo import ZoneInfo
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from dateutil import parser
from fastapi import HTTPException

from app.models.trade import Trade
from app.models.position import Position
from app.models.broker_account import BrokerAccount
from app.models.order import Order
from app.models.holding import Holding
from app.utils.trade_classifier import classify_trade
from app.services.zerodha_service import zerodha_client
from app.services.pnl_calculator import pnl_calculator
from app.services.instrument_service import instrument_service
from app.models.instrument import Instrument
from sqlalchemy.dialects.postgresql import insert

logger = logging.getLogger(__name__)

# Zerodha sends all timestamps in IST without timezone info
IST = ZoneInfo("Asia/Kolkata")

# Only sync these product types (user trades MIS/NRML/MTF, not CNC/delivery)
TRACKED_PRODUCTS = {"MIS", "NRML", "MTF"}

class TradeSyncService:
    @staticmethod
    async def fetch_orders_from_zerodha(access_token: str) -> List[Dict[str, Any]]:
        return await zerodha_client.get_orders(access_token)
    
    @staticmethod
    def _parse_timestamp(ts_value) -> Optional[datetime]:
        """Parse timestamp from various formats.

        Zerodha sends all timestamps in IST without timezone info.
        We tag naive datetimes as IST so PostgreSQL stores them correctly as UTC.
        """
        if not ts_value:
            return None
        try:
            if isinstance(ts_value, (datetime, date)):
                dt = ts_value if isinstance(ts_value, datetime) else datetime.combine(ts_value, datetime.min.time())
            else:
                dt = parser.parse(str(ts_value))

            # Zerodha timestamps are IST but arrive without tz info.
            # Tag as IST so TIMESTAMP WITH TIME ZONE stores the correct UTC value.
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=IST)

            return dt
        except Exception:
            return None

    @staticmethod
    def transform_zerodha_order(raw_order: Dict[str, Any]) -> Dict[str, Any]:
        """Transform Zerodha order/trade to internal Trade schema."""
        classification = classify_trade(raw_order)

        # Parse timestamps
        order_ts = TradeSyncService._parse_timestamp(raw_order.get("order_timestamp"))
        exchange_ts = TradeSyncService._parse_timestamp(raw_order.get("exchange_timestamp"))
        fill_ts = TradeSyncService._parse_timestamp(raw_order.get("fill_timestamp"))

        # Helper to get float safely
        def safe_float(val):
            try:
                return float(val) if val is not None else 0.0
            except (ValueError, TypeError):
                return 0.0

        def safe_int(val, default=0):
            try:
                return int(val) if val is not None else default
            except (ValueError, TypeError):
                return default

        return {
            # Core identifiers
            "order_id": str(raw_order.get("trade_id") or raw_order.get("order_id", "")),
            "kite_order_id": str(raw_order.get("order_id", "")) if raw_order.get("order_id") else None,
            "exchange_order_id": raw_order.get("exchange_order_id"),

            # Symbol info
            "tradingsymbol": raw_order.get("tradingsymbol"),
            "exchange": raw_order.get("exchange"),
            "instrument_token": safe_int(raw_order.get("instrument_token")) or None,

            # Order details
            "transaction_type": raw_order.get("transaction_type"),
            "order_type": raw_order.get("order_type"),
            "product": raw_order.get("product"),
            "validity": raw_order.get("validity", "DAY"),
            "variety": raw_order.get("variety", "regular"),

            # Quantities
            "quantity": safe_int(raw_order.get("quantity")),
            "filled_quantity": safe_int(raw_order.get("filled_quantity")),
            "pending_quantity": safe_int(raw_order.get("pending_quantity")),
            "cancelled_quantity": safe_int(raw_order.get("cancelled_quantity")),
            "disclosed_quantity": safe_int(raw_order.get("disclosed_quantity")),

            # Prices
            "price": safe_float(raw_order.get("price")),
            "average_price": safe_float(raw_order.get("average_price")),
            "trigger_price": safe_float(raw_order.get("trigger_price")),

            # Status
            "status": raw_order.get("status"),
            "status_message": raw_order.get("status_message"),

            # Timestamps
            "order_timestamp": order_ts,
            "exchange_timestamp": exchange_ts,
            "fill_timestamp": fill_ts,

            # Metadata
            "tag": raw_order.get("tag"),
            "guid": raw_order.get("guid"),
            "parent_order_id": raw_order.get("parent_order_id"),

            # Classification
            "asset_class": classification["asset_class"],
            "instrument_type": classification["instrument_type"],
            "product_type": classification["product_type"],

            # Raw data
            "raw_payload": raw_order,
            "pnl": 0.0
        }

    @classmethod
    async def upsert_trade(cls, db: AsyncSession, trade_data: Dict[str, Any], broker_account_id: uuid.UUID) -> tuple:
        """
        Upsert a trade. Returns (trade_obj, is_new) tuple.
        is_new=True means this was a fresh insert, False means update.
        """
        # Check if trade exists
        stmt = select(Trade).where(
            Trade.order_id == trade_data["order_id"],
            Trade.broker_account_id == broker_account_id
        )
        result = await db.execute(stmt)
        existing_trade = result.scalars().first()

        if existing_trade:
            # Update - but preserve previously calculated P&L
            existing_pnl = existing_trade.pnl
            for key, value in trade_data.items():
                if key not in ["id", "created_at", "broker_account_id"]:
                    # Don't overwrite non-zero calculated P&L with zero from re-sync
                    if key == "pnl" and existing_pnl is not None and float(existing_pnl) != 0.0:
                        if value is None or float(value) == 0.0:
                            continue
                    setattr(existing_trade, key, value)
            existing_trade.updated_at = datetime.now(timezone.utc)
            return existing_trade, False
        else:
            # Create
            create_data = trade_data.copy()
            create_data["broker_account_id"] = broker_account_id
            trade = Trade(**create_data)
            db.add(trade)
            return trade, True

    @classmethod
    async def sync_trades_for_broker_account(cls, broker_account_id: uuid.UUID, db: AsyncSession) -> Dict[str, Any]:
        """Syncs trades, positions, and orders for a specific broker account."""
        account = await db.get(BrokerAccount, broker_account_id)
        if not account:
            return {"success": False, "error": "Broker account not found"}
            
        if not account.access_token:
             return {"success": False, "error": "Broker not connected (no token)"}
             
        try:
            # Decrypt token
            access_token = account.decrypt_token(account.access_token)
            
            # Validate token before making API calls
            if not access_token or len(access_token) < 20:
                logger.error("Access token appears invalid or too short")
                return {
                    "success": False,
                    "error": "Invalid access token - please reconnect Zerodha"
                }

            stats = {
                "trades_synced": 0,
                "positions_synced": 0,
                "orders_synced": 0,
                "errors": [],
                "new_trade_ids": [],  # IDs of newly inserted trades (for behavioral evaluator)
            }

            # 0. Refresh instruments if stale (once per day)
            # Instruments are needed for lot sizes (F&O P&L calculation)
            try:
                stale_cutoff = datetime.now(timezone.utc) - timedelta(hours=23)
                latest_instrument = await db.execute(
                    select(Instrument.updated_at)
                    .order_by(Instrument.updated_at.desc())
                    .limit(1)
                )
                last_updated = latest_instrument.scalar_one_or_none()

                if last_updated is None or last_updated < stale_cutoff:
                    logger.info("Instruments stale or missing — refreshing from Kite")
                    result = await instrument_service.refresh_instruments(db)
                    stats["instruments_refreshed"] = result.get("total", 0)
                    pnl_calculator.clear_lot_size_cache()
                    logger.info(f"Instruments refreshed: {result.get('total', 0)} total")
                else:
                    logger.info("Instruments up to date, skipping refresh")
            except Exception as e:
                logger.error(f"Instrument refresh failed (non-fatal): {e}")
                stats["errors"].append(f"Instrument Refresh: {str(e)}")

            # 1. Sync Trades (Direct execution history)
            try:
                trades_data = await zerodha_client.get_trades(access_token)
                logger.info(f"Fetched {len(trades_data)} trades from Zerodha")
            except Exception as e:
                logger.error(f"Error fetching trades: {e}")
                trades_data = []
                stats["errors"].append(f"Trades Fetch: {str(e)}")

            for trade_data in trades_data:
                try:
                     # Skip CNC/delivery trades
                     if trade_data.get("product") not in TRACKED_PRODUCTS:
                         continue

                     trade_data["status"] = "COMPLETE"
                     trade_data["filled_quantity"] = trade_data.get("quantity", 0)
                     
                     normalized_data = cls.transform_zerodha_order(trade_data)
                     async with db.begin_nested():
                        trade_obj, is_new = await cls.upsert_trade(db, normalized_data, broker_account_id)
                     stats["trades_synced"] += 1
                     # Only track truly new fills for behavioral evaluator (not re-synced updates)
                     if is_new and trade_obj and trade_obj.id:
                         stats["new_trade_ids"].append(trade_obj.id)
                except Exception as e:
                    logger.error(f"Error syncing individual trade: {e}")
                    stats["errors"].append(f"Trade Sync ID {trade_data.get('trade_id')}: {str(e)}")

            # 2. Sync Positions (Snapshot) — upsert to preserve historical data
            try:
                pos_stats = await cls.sync_positions(broker_account_id, db, access_token)
                stats["positions_synced"] = pos_stats.get("synced", 0)
                if pos_stats.get("errors"):
                    stats["errors"].extend(pos_stats["errors"])
            except Exception as e:
                logger.error(f"Error fetching positions: {e}")
                stats["errors"].append(f"Positions Fetch: {str(e)}")



            # 3. Orders sync removed — orders go to orders table via sync_orders_to_db()
            # Pushing /orders into trades table caused duplicates (every COMPLETE order
            # appeared twice: once from /trades with trade_id, once from /orders with order_id)

            account.last_sync_at = datetime.now(timezone.utc)

            # 4. Calculate P&L for trades (FIFO matching)
            try:
                pnl_result = await pnl_calculator.calculate_and_update_pnl(
                    broker_account_id, db, days_back=30
                )
                stats["pnl_trades_updated"] = pnl_result.get("updated", 0)
                stats["total_pnl_calculated"] = pnl_result.get("total_pnl", 0)
                logger.info(f"P&L calculation: {pnl_result['updated']} trades updated, total: {pnl_result['total_pnl']}")
            except Exception as e:
                logger.error(f"P&L calculation failed: {e}")
                stats["errors"].append(f"P&L Calculation: {str(e)}")

            # 5. Risk detection decoupled from sync pipeline
            # Moved to post-sync step in zerodha.py sync_all_data().
            # FIFO/sync must remain deterministic and replayable.
            # Behavioral detection runs AFTER data pipeline completes.

            await db.commit()
            
            return {"success": True, **stats}
            
        except Exception as e:
            logger.error(f"Sync error for account {broker_account_id}: {e}")
            return {"success": False, "error": str(e)}

    @classmethod
    async def sync_orders_to_db(
        cls,
        broker_account_id: uuid.UUID,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Sync all orders (including cancelled/rejected) to orders table.

        This provides complete order flow data for behavioral analysis:
        - Cancellation rate
        - Rejection reasons
        - Order modification patterns
        """
        account = await db.get(BrokerAccount, broker_account_id)
        if not account or not account.access_token:
            return {"success": False, "error": "Broker not connected"}

        try:
            access_token = account.decrypt_token(account.access_token)
            orders_data = await zerodha_client.get_orders(access_token)

            synced = 0
            errors = []

            for order_data in orders_data:
                try:
                    async with db.begin_nested():
                        order_dict = cls._map_order_to_model(order_data, broker_account_id)

                        # Upsert order
                        stmt = insert(Order).values(**order_dict)
                        stmt = stmt.on_conflict_do_update(
                            index_elements=['broker_account_id', 'kite_order_id'],
                            set_={
                                "status": order_dict["status"],
                                "status_message": order_dict["status_message"],
                                "filled_quantity": order_dict["filled_quantity"],
                                "pending_quantity": order_dict["pending_quantity"],
                                "cancelled_quantity": order_dict["cancelled_quantity"],
                                "average_price": order_dict["average_price"],
                                "exchange_timestamp": order_dict["exchange_timestamp"],
                                "updated_at": datetime.now(timezone.utc)
                            }
                        )
                        await db.execute(stmt)
                    synced += 1

                except Exception as e:
                    logger.error(f"Error syncing order {order_data.get('order_id')}: {e}")
                    errors.append(str(e))

            await db.commit()

            return {
                "success": True,
                "orders_synced": synced,
                "errors": errors
            }

        except Exception as e:
            logger.error(f"Orders sync error: {e}")
            return {"success": False, "error": str(e)}

    @classmethod
    def _map_order_to_model(cls, order_data: Dict[str, Any], broker_account_id: uuid.UUID) -> Dict[str, Any]:
        """Map Kite order response to Order model."""

        def safe_int(val, default=0):
            try:
                return int(val) if val is not None else default
            except (ValueError, TypeError):
                return default

        def safe_float(val):
            try:
                return float(val) if val is not None else None
            except (ValueError, TypeError):
                return None

        return {
            "broker_account_id": broker_account_id,
            "kite_order_id": str(order_data.get("order_id", "")),
            "exchange_order_id": order_data.get("exchange_order_id"),
            "status": order_data.get("status", ""),
            "status_message": order_data.get("status_message"),
            "status_message_raw": order_data.get("status_message_raw"),
            "tradingsymbol": order_data.get("tradingsymbol", ""),
            "exchange": order_data.get("exchange", ""),
            "transaction_type": order_data.get("transaction_type", ""),
            "order_type": order_data.get("order_type", ""),
            "product": order_data.get("product", ""),
            "variety": order_data.get("variety", "regular"),
            "validity": order_data.get("validity", "DAY"),
            "quantity": safe_int(order_data.get("quantity")),
            "disclosed_quantity": safe_int(order_data.get("disclosed_quantity")),
            "pending_quantity": safe_int(order_data.get("pending_quantity")),
            "cancelled_quantity": safe_int(order_data.get("cancelled_quantity")),
            "filled_quantity": safe_int(order_data.get("filled_quantity")),
            "price": safe_float(order_data.get("price")),
            "trigger_price": safe_float(order_data.get("trigger_price")),
            "average_price": safe_float(order_data.get("average_price")),
            "order_timestamp": cls._parse_timestamp(order_data.get("order_timestamp")),
            "exchange_timestamp": cls._parse_timestamp(order_data.get("exchange_timestamp")),
            "exchange_update_timestamp": cls._parse_timestamp(order_data.get("exchange_update_timestamp")),
            "tag": order_data.get("tag"),
            "guid": order_data.get("guid"),
            "parent_order_id": order_data.get("parent_order_id"),
        }

    @classmethod
    async def sync_holdings(
        cls,
        broker_account_id: uuid.UUID,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Sync CNC/delivery holdings to holdings table.

        Holdings are long-term positions separate from intraday positions.
        """
        account = await db.get(BrokerAccount, broker_account_id)
        if not account or not account.access_token:
            return {"success": False, "error": "Broker not connected"}

        try:
            access_token = account.decrypt_token(account.access_token)
            holdings_data = await zerodha_client.get_holdings(access_token)

            synced = 0
            errors = []

            # Clear existing holdings for this account (full refresh)
            await db.execute(
                delete(Holding).where(Holding.broker_account_id == broker_account_id)
            )

            for holding_data in holdings_data:
                try:
                    async with db.begin_nested():
                        holding = cls._map_holding_to_model(holding_data, broker_account_id)
                        db.add(Holding(**holding))
                    synced += 1

                except Exception as e:
                    logger.error(f"Error syncing holding {holding_data.get('tradingsymbol')}: {e}")
                    errors.append(str(e))

            await db.commit()

            return {
                "success": True,
                "holdings_synced": synced,
                "errors": errors
            }

        except Exception as e:
            logger.error(f"Holdings sync error: {e}")
            return {"success": False, "error": str(e)}

    @classmethod
    def _map_holding_to_model(cls, holding_data: Dict[str, Any], broker_account_id: uuid.UUID) -> Dict[str, Any]:
        """Map Kite holding response to Holding model."""

        def safe_int(val, default=0):
            try:
                return int(val) if val is not None else default
            except (ValueError, TypeError):
                return default

        def safe_float(val):
            try:
                return float(val) if val is not None else None
            except (ValueError, TypeError):
                return None

        return {
            "broker_account_id": broker_account_id,
            "tradingsymbol": holding_data.get("tradingsymbol", ""),
            "exchange": holding_data.get("exchange", ""),
            "isin": holding_data.get("isin"),
            "quantity": safe_int(holding_data.get("quantity")),
            "authorised_quantity": safe_int(holding_data.get("authorised_quantity")),
            "t1_quantity": safe_int(holding_data.get("t1_quantity")),
            "collateral_quantity": safe_int(holding_data.get("collateral_quantity")),
            "collateral_type": holding_data.get("collateral_type"),
            "average_price": safe_float(holding_data.get("average_price")),
            "last_price": safe_float(holding_data.get("last_price")),
            "close_price": safe_float(holding_data.get("close_price")),
            "pnl": safe_float(holding_data.get("pnl")),
            "day_change": safe_float(holding_data.get("day_change")),
            "day_change_percentage": safe_float(holding_data.get("day_change_percentage")),
            "instrument_token": safe_int(holding_data.get("instrument_token")) or None,
            "product": "CNC",
        }


    @classmethod
    async def sync_positions(
        cls, 
        broker_account_id: uuid.UUID, 
        db: AsyncSession,
        access_token: str = None
    ) -> Dict[str, Any]:
        """
        Sync open positions from broker.
        Can be called independently (e.g., after webhook trade).
        """
        if not access_token:
            account = await db.get(BrokerAccount, broker_account_id)
            if not account or not account.access_token:
                 return {"synced": 0, "errors": ["Broker not connected"]}
            access_token = account.decrypt_token(account.access_token)

        stats = {"synced": 0, "errors": []}
        
        try:
            positions_resp = await zerodha_client.get_positions(access_token)
            net_positions = positions_resp.get("net", [])
            logger.info(f"Fetched {len(net_positions)} positions from Zerodha")

            # Helper for safe conversions
            def safe_float(val, default=0.0):
                try:
                    return float(val) if val is not None else default
                except (ValueError, TypeError):
                    return default

            def safe_int(val, default=0):
                try:
                    return int(val) if val is not None else default
                except (ValueError, TypeError):
                    return default

            # Load existing positions into a lookup dict
            existing_result = await db.execute(
                select(Position).where(Position.broker_account_id == broker_account_id)
            )
            existing_positions = {
                (p.tradingsymbol, p.exchange, p.product): p
                for p in existing_result.scalars().all()
            }

            seen_keys = set()

            for pos in net_positions:
                # Skip CNC/delivery positions
                if pos.get("product") not in TRACKED_PRODUCTS:
                    continue

                qty = pos.get("quantity", 0)
                key = (pos.get("tradingsymbol"), pos.get("exchange"), pos.get("product"))
                seen_keys.add(key)

                try:
                    classification = classify_trade(pos)
                    existing = existing_positions.get(key)

                    # Fields to update from Zerodha snapshot
                    update_fields = {
                        "instrument_type": classification["instrument_type"],
                        "total_quantity": qty,
                        "average_entry_price": safe_float(pos.get("average_price")),
                        "instrument_token": safe_int(pos.get("instrument_token")) or None,
                        "overnight_quantity": safe_int(pos.get("overnight_quantity")),
                        "multiplier": safe_float(pos.get("multiplier"), 1.0),
                        "pnl": safe_float(pos.get("pnl")),
                        "unrealized_pnl": safe_float(pos.get("unrealised")),
                        "realized_pnl": safe_float(pos.get("realised")),
                        "day_pnl": safe_float(pos.get("m2m")),
                        "m2m": safe_float(pos.get("m2m")),
                        "last_price": safe_float(pos.get("last_price")),
                        "close_price": safe_float(pos.get("close_price")),
                        "value": safe_float(pos.get("value")),
                        "buy_value": safe_float(pos.get("buy_value")),
                        "sell_value": safe_float(pos.get("sell_value")),
                        "day_buy_quantity": safe_int(pos.get("day_buy_quantity")),
                        "day_sell_quantity": safe_int(pos.get("day_sell_quantity")),
                        "day_buy_price": safe_float(pos.get("day_buy_price")),
                        "day_sell_price": safe_float(pos.get("day_sell_price")),
                        "day_buy_value": safe_float(pos.get("day_buy_value")),
                        "day_sell_value": safe_float(pos.get("day_sell_value")),
                        "status": "open" if qty != 0 else "closed",
                        "synced_at": datetime.now(timezone.utc),
                    }

                    async with db.begin_nested():
                        if existing:
                            # Update existing — preserves first_entry_time, created_at, order_ids
                            for field, value in update_fields.items():
                                setattr(existing, field, value)
                            existing.updated_at = datetime.now(timezone.utc)
                        else:
                            # Insert new position
                            position = Position(
                                broker_account_id=broker_account_id,
                                tradingsymbol=pos.get("tradingsymbol"),
                                exchange=pos.get("exchange"),
                                product=pos.get("product"),
                                **update_fields,
                            )
                            db.add(position)
                        stats["synced"] += 1
                except Exception as e:
                    logger.error(f"Error syncing position {pos.get('tradingsymbol')}: {e}")
                    stats["errors"].append(f"Position Sync: {str(e)}")

            # Mark positions not in Zerodha response as closed (don't delete)
            for key, existing_pos in existing_positions.items():
                if key not in seen_keys and existing_pos.status != "closed":
                    existing_pos.total_quantity = 0
                    existing_pos.status = "closed"
                    existing_pos.synced_at = datetime.now(timezone.utc)

        except Exception as e:
            logger.error(f"Error fetching positions: {e}")
            stats["errors"].append(f"Positions Fetch: {str(e)}")
            
        return stats
