import logging
import uuid
from datetime import datetime, date, time, timedelta, timezone
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
from app.models.completed_trade import CompletedTrade
from app.utils.trade_classifier import classify_trade
from app.services.zerodha_service import zerodha_client
from app.services.pnl_calculator import pnl_calculator
from app.services.instrument_service import instrument_service
from app.services.mcx_contract_specs import get_lot_multiplier
from app.core.market_hours import market_minutes
from app.models.instrument import Instrument
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import func as sa_func

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

        # Terminal statuses — a trade in these states must NEVER be overwritten by a
        # later postback. Zerodha sometimes delivers webhooks out of order (COMPLETE
        # can arrive before OPEN, or a duplicate OPEN can arrive after COMPLETE).
        _TERMINAL = {"COMPLETE", "REJECTED", "CANCELLED"}

        if existing_trade:
            # Reject status downgrades: COMPLETE/REJECTED/CANCELLED → anything else.
            # This prevents out-of-order postbacks from corrupting finalized trades.
            new_status = (trade_data.get("status") or "").upper()
            old_status = (existing_trade.status or "").upper()
            if old_status in _TERMINAL and new_status and new_status != old_status:
                logger.warning(
                    f"Rejected status downgrade for order {trade_data.get('order_id')}: "
                    f"{old_status} → {new_status} (out-of-order webhook, ignoring)"
                )
                return existing_trade, False

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
            overnight_closed_positions: List[Dict[str, Any]] = []
            try:
                pos_stats = await cls.sync_positions(broker_account_id, db, access_token)
                stats["positions_synced"] = pos_stats.get("synced", 0)
                overnight_closed_positions = pos_stats.get("overnight_closed", [])
                if pos_stats.get("errors"):
                    stats["errors"].extend(pos_stats["errors"])
            except Exception as e:
                logger.error(f"Error fetching positions: {e}")
                stats["errors"].append(f"Positions Fetch: {str(e)}")



            # 3. Orders sync removed — orders go to orders table via sync_orders_to_db()
            # Pushing /orders into trades table caused duplicates (every COMPLETE order
            # appeared twice: once from /trades with trade_id, once from /orders with order_id)

            # 4. Idempotent replay of any fills not yet in PositionLedger.
            #
            # Architecture: PositionLedger is the single writer for CompletedTrades.
            #   - Real-time: webhook → apply_fill() → build_completed_trade_on_close()
            #   - Sync path: catches any fills PositionLedger missed (webhook failures)
            #     by replaying them through apply_fill() in timestamp order.
            #     apply_fill() is idempotent (same idempotency_key = no-op), so fills
            #     that already arrived via webhook are safely skipped.
            #
            # Why not pnl_calculator here: pnl_calculator deletes then recreates
            # CompletedTrades, destroying real-time records built by PositionLedger.
            # pnl_calculator is kept as a historical-backfill-only tool (admin endpoint).
            try:
                replayed = await cls.replay_missed_fills_into_ledger(
                    broker_account_id, db, days_back=30
                )
                stats["fills_replayed"] = replayed
                if replayed:
                    logger.info(f"[ledger replay] {replayed} fill(s) processed from missed webhooks")
            except Exception as e:
                logger.error(f"Ledger replay failed: {e}", exc_info=True)
                stats["errors"].append(f"Ledger Replay: {str(e)}")

            # 4b. Backfill CompletedTrades for cross-day positions PositionLedger missed.
            # Overnight holds have entry fills from yesterday — those entries are in the
            # ledger already; only the exit fills from today may be missing.
            # replay_missed_fills_into_ledger covers this, but _backfill_overnight_completed_trades
            # handles the case where YESTERDAY's entry fills were never recorded in the ledger.
            if overnight_closed_positions:
                try:
                    backfilled = await cls._backfill_overnight_completed_trades(
                        broker_account_id, overnight_closed_positions, db
                    )
                    stats["overnight_trades_backfilled"] = backfilled
                    if backfilled:
                        logger.info(f"Backfilled {backfilled} cross-day CompletedTrade(s)")
                except Exception as e:
                    logger.error(f"Overnight CompletedTrade backfill failed (non-fatal): {e}")
                    stats["errors"].append(f"Overnight Backfill: {str(e)}")

            # 4c. Reconciliation (log-only — no overwrites).
            # PositionLedger P&L is authoritative for NSE/NFO/BSE/BFO and MCX.
            # This block only logs WARNING when FIFO vs Zerodha aggregate diverges >10%
            # (which indicates a missing MCX multiplier entry that needs to be added).
            try:
                await db.flush()
                reconciled = await cls._reconcile_pnl_with_zerodha(
                    broker_account_id, db
                )
                if reconciled:
                    stats["pnl_reconciled"] = reconciled
                    logger.info(f"P&L reconciliation check: {reconciled} record(s) verified")
            except Exception as e:
                logger.error(f"P&L reconciliation failed (non-fatal): {e}")
                stats["errors"].append(f"P&L Reconciliation: {str(e)}")

            # 5. Risk detection decoupled from sync pipeline
            # Moved to post-sync step in zerodha.py sync_all_data().
            # FIFO/sync must remain deterministic and replayable.
            # Behavioral detection runs AFTER data pipeline completes.

            # Stamp last_sync_at only after data pipeline fully completes.
            account.last_sync_at = datetime.now(timezone.utc)

            await db.commit()
            
            return {"success": True, **stats}
            
        except Exception as e:
            logger.error(f"Sync error for account {broker_account_id}: {e}")
            return {"success": False, "error": str(e)}

    @classmethod
    async def replay_missed_fills_into_ledger(
        cls,
        broker_account_id: uuid.UUID,
        db: AsyncSession,
        days_back: int = 30,
    ) -> int:
        """
        Replay any COMPLETE Trade fills not yet recorded in PositionLedger.

        This is the EOD catch-up path: webhooks fire for each fill in real-time,
        but if a webhook was missed (network blip, Celery restart, etc.) the fill
        never reached apply_fill().  This method finds those gaps and replays them.

        Design:
        - apply_fill() is idempotent (same idempotency_key → return existing, is_new=False).
          Fills that already arrived via webhook are safely skipped — no double-counting.
        - Processes fills in ascending timestamp order so position state accumulates
          correctly (same invariant as the webhook path).
        - On CLOSE/FLIP: calls build_completed_trade_on_close() to create the
          CompletedTrade.  Existing CompletedTrades (from successful webhooks) are
          never deleted or overwritten.

        Returns: number of fills that were newly processed (missed_webhook count).
        """
        from decimal import Decimal as _Decimal
        from app.services.position_ledger_service import PositionLedgerService, FillData
        from app.models.position_ledger import PositionLedger

        cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)

        # All COMPLETE fills in window, ordered by timestamp
        result = await db.execute(
            select(Trade).where(
                Trade.broker_account_id == broker_account_id,
                Trade.status == "COMPLETE",
                Trade.order_timestamp >= cutoff,
            ).order_by(Trade.order_timestamp.asc())
        )
        all_trades = list(result.scalars().all())

        if not all_trades:
            return 0

        # Fetch all existing ledger idempotency keys for this account — O(1) lookup
        key_result = await db.execute(
            select(PositionLedger.idempotency_key).where(
                PositionLedger.broker_account_id == broker_account_id
            )
        )
        seen_keys = {row[0] for row in key_result}

        missed = 0
        for trade in all_trades:
            idem_key = f"{trade.order_id}:ledger"
            if idem_key in seen_keys:
                continue  # Already in ledger — skip (idempotent)

            qty = trade.filled_quantity or trade.quantity or 0
            signed_qty = qty if trade.transaction_type == "BUY" else -qty
            if signed_qty == 0:
                continue

            fill = FillData(
                broker_account_id=broker_account_id,
                tradingsymbol=trade.tradingsymbol or "",
                exchange=trade.exchange or "",
                fill_order_id=trade.order_id or str(trade.id),
                fill_qty=signed_qty,
                fill_price=_Decimal(str(trade.average_price or trade.price or 0)),
                occurred_at=trade.order_timestamp or datetime.now(timezone.utc),
                idempotency_key=idem_key,
            )

            try:
                ledger_entry, is_new = await PositionLedgerService.apply_fill(fill, db)
                if not is_new:
                    seen_keys.add(idem_key)
                    continue  # Race: another worker got there first

                seen_keys.add(idem_key)
                missed += 1

                # If position closed: create CompletedTrade (if one doesn't exist)
                if ledger_entry.entry_type in ("CLOSE", "FLIP"):
                    ct = await PositionLedgerService.build_completed_trade_on_close(
                        ledger_entry, db
                    )
                    if ct:
                        db.add(ct)
                        await db.flush()
                        logger.info(
                            f"[ledger replay] CompletedTrade: {ct.tradingsymbol} "
                            f"{ct.direction} pnl={ct.realized_pnl:.2f}"
                        )

            except Exception as e:
                logger.error(
                    f"[ledger replay] apply_fill failed for {trade.tradingsymbol} "
                    f"order={trade.order_id}: {e}",
                    exc_info=True,
                )
                # Non-fatal: continue with remaining fills

        return missed

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

        stats: Dict[str, Any] = {"synced": 0, "errors": [], "overnight_closed": []}

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

            # Build entry-time lookups from today's completed BUY trades in DB.
            # first_entry: earliest BUY today → when user first entered the position
            # last_entry:  latest BUY today  → when user most recently added to it
            # Both are stored on the Position row so position_monitor can calculate
            # hold duration without re-querying trades each time.
            today_start = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            trade_ts_result = await db.execute(
                select(Trade).where(
                    Trade.broker_account_id == broker_account_id,
                    Trade.transaction_type == "BUY",
                    Trade.order_timestamp >= today_start,
                    Trade.filled_quantity > 0,
                ).order_by(Trade.order_timestamp.asc())
            )
            _first_entry_map: dict[tuple, datetime] = {}
            _last_entry_map: dict[tuple, datetime] = {}
            for _t in trade_ts_result.scalars().all():
                _k = (_t.tradingsymbol, _t.product)
                if _t.order_timestamp:
                    if _k not in _first_entry_map:
                        _first_entry_map[_k] = _t.order_timestamp
                    _last_entry_map[_k] = _t.order_timestamp  # always overwrite → keeps latest
            # Keep backward-compat alias used below
            _entry_time_map = _first_entry_map

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
                        # Use our authoritative multiplier table for MCX/CDS — Zerodha's
                        # instruments CSV sets lot_size=1 for all MCX instruments, so
                        # pos.get("multiplier") is unreliable (returns 1 for CRUDEOIL etc.).
                        # get_lot_multiplier returns 1 for NSE/BSE/NFO/BFO (no change there).
                        "multiplier": float(get_lot_multiplier(
                            pos.get("exchange", ""), pos.get("tradingsymbol", "")
                        )),
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

                    _pkey = (pos.get("tradingsymbol"), pos.get("product"))
                    _first_ts = _first_entry_map.get(_pkey)
                    _last_ts = _last_entry_map.get(_pkey)

                    async with db.begin_nested():
                        if existing:
                            # Update existing — preserve first_entry_time if already set;
                            # backfill from trade timestamp if still NULL.
                            # Always update last_entry_time to today's latest BUY.
                            for field, value in update_fields.items():
                                setattr(existing, field, value)
                            if existing.first_entry_time is None and _first_ts:
                                existing.first_entry_time = _first_ts
                            if _last_ts:
                                existing.last_entry_time = _last_ts
                            elif existing.last_entry_time is None and existing.first_entry_time:
                                existing.last_entry_time = existing.first_entry_time
                            existing.updated_at = datetime.now(timezone.utc)
                        else:
                            # Insert new position with full entry time data
                            position = Position(
                                broker_account_id=broker_account_id,
                                tradingsymbol=pos.get("tradingsymbol"),
                                exchange=pos.get("exchange"),
                                product=pos.get("product"),
                                first_entry_time=_first_ts,
                                last_entry_time=_last_ts or _first_ts,
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

            # Identify cross-day closes: qty=0 today but was held overnight.
            # These need a CompletedTrade that FIFO can't create (missing entry leg).
            # Returned so the caller can backfill AFTER pnl_calculator runs.
            for pos in net_positions:
                if pos.get("product") not in TRACKED_PRODUCTS:
                    continue
                qty = int(pos.get("quantity", 0))
                overnight_qty = int(pos.get("overnight_quantity", 0))
                realised = float(pos.get("realised", 0.0))
                if qty == 0 and overnight_qty != 0 and abs(realised) > 0.01:
                    # M1 guard: only backfill if we have at least one BUY trade in DB for
                    # this symbol today. Prevents phantom CompletedTrade records for
                    # positions opened on another platform or before our tracking started.
                    _symbol = pos.get("tradingsymbol")
                    _today_ist = datetime.now(IST).date()
                    _today_start_utc = datetime.combine(
                        _today_ist, time(0, 0), tzinfo=IST
                    ).astimezone(timezone.utc)
                    try:
                        _entry_count = await db.scalar(
                            select(sa_func.count()).select_from(Trade).where(
                                Trade.broker_account_id == broker_account_id,
                                Trade.tradingsymbol == _symbol,
                                Trade.transaction_type == "BUY",
                                Trade.order_timestamp >= _today_start_utc,
                            )
                        )
                        if not _entry_count:
                            logger.info(
                                f"[overnight] {_symbol}: no BUY entry in DB today — "
                                f"skipping backfill (untracked position)"
                            )
                            continue
                    except Exception as _m1e:
                        logger.warning(f"[overnight] M1 guard query failed for {_symbol}: {_m1e}")
                    stats["overnight_closed"].append(pos)

        except Exception as e:
            logger.error(f"Error fetching positions: {e}")
            stats["errors"].append(f"Positions Fetch: {str(e)}")

        return stats

    @classmethod
    async def _backfill_overnight_completed_trades(
        cls,
        broker_account_id: uuid.UUID,
        overnight_positions: List[Dict[str, Any]],
        db: AsyncSession,
    ) -> int:
        """
        Create CompletedTrade records for cross-day positions that FIFO couldn't match.

        Called AFTER pnl_calculator.calculate_and_update_pnl so we only act on
        positions that FIFO missed (missing yesterday's entry leg in DB).

        Data accuracy:
          - avg_entry_price: Zerodha's carry-forward average_price (100% accurate)
          - avg_exit_price:  day_sell_price (LONG) / day_buy_price (SHORT) — weighted
                             average of today's exit fills (100% accurate)
          - realized_pnl:    Zerodha's own FIFO realised field (100% accurate)
          - exit_time:       latest exchange_timestamp of today's matching exit trade in DB
          - entry_time:      previous trading day 15:30 IST (approximation — exact entry
                             timestamp not available without historical trade data)
          - duration_minutes: derived from entry_time → exit_time (approximate)

        No polling — runs once as part of the sync pipeline.
        """
        today_ist = datetime.now(IST).date()
        today_start_utc = datetime.combine(today_ist, time(0, 0), tzinfo=IST).astimezone(timezone.utc)

        def prev_trading_day_close(today: date) -> datetime:
            """Return 15:30 IST on the most recent trading day before today."""
            d = today - timedelta(days=1)
            # Skip weekends
            while d.weekday() >= 5:
                d -= timedelta(days=1)
            return datetime.combine(d, time(15, 30), tzinfo=IST).astimezone(timezone.utc)

        created = 0
        for pos in overnight_positions:
            symbol = pos.get("tradingsymbol")
            exchange = pos.get("exchange", "NSE")
            product = pos.get("product")
            overnight_qty = int(pos.get("overnight_quantity", 0))

            try:
                # Skip if a CompletedTrade for this symbol already exists today
                # (FIFO created it successfully — it had the entry leg in DB)
                existing = await db.scalar(
                    select(sa_func.count()).select_from(CompletedTrade).where(
                        CompletedTrade.broker_account_id == broker_account_id,
                        CompletedTrade.tradingsymbol == symbol,
                        CompletedTrade.exit_time >= today_start_utc,
                    )
                )
                if existing and existing > 0:
                    logger.debug(f"[overnight] CompletedTrade already exists for {symbol} today — skipping")
                    continue

                direction = "LONG" if overnight_qty > 0 else "SHORT"
                qty = abs(overnight_qty)

                avg_entry = float(pos.get("average_price") or 0)
                # Exit price: day_sell_price for LONG close, day_buy_price for SHORT cover
                if direction == "LONG":
                    avg_exit = float(pos.get("day_sell_price") or 0)
                    exit_tx = "SELL"
                else:
                    avg_exit = float(pos.get("day_buy_price") or 0)
                    exit_tx = "BUY"

                # Skip if we can't determine prices (shouldn't happen for valid closes)
                if avg_entry == 0 or avg_exit == 0:
                    logger.warning(f"[overnight] {symbol}: zero entry/exit price — skipping")
                    continue

                realized_pnl = float(pos.get("realised") or 0)

                # Get actual exit time from today's trades in DB
                exit_time_row = await db.scalar(
                    select(sa_func.max(Trade.exchange_timestamp)).where(
                        Trade.broker_account_id == broker_account_id,
                        Trade.tradingsymbol == symbol,
                        Trade.transaction_type == exit_tx,
                        Trade.exchange_timestamp >= today_start_utc,
                    )
                )
                exit_time = exit_time_row or datetime.combine(
                    today_ist,
                    time(15, 30) if exchange in ("NSE", "BSE", "NFO", "BFO") else time(17, 0),
                    tzinfo=IST,
                ).astimezone(timezone.utc)

                # Try to find the actual entry timestamp from saved Trade records.
                # The user's entry fill WAS saved when they placed the trade — we just
                # need to look across all history, not only today.
                # Fall back to prev-day-close approximation only if no record exists
                # (e.g. position was opened before the user connected the app).
                entry_buy_type = "BUY" if direction == "LONG" else "SELL"
                actual_entry_time = await db.scalar(
                    select(sa_func.min(Trade.exchange_timestamp)).where(
                        Trade.broker_account_id == broker_account_id,
                        Trade.tradingsymbol == symbol,
                        Trade.transaction_type == entry_buy_type,
                        Trade.exchange_timestamp < today_start_utc,
                    )
                )
                entry_time = actual_entry_time or prev_trading_day_close(today_ist)
                duration_minutes = market_minutes(entry_time, exit_time, exchange=exchange)

                # Derive instrument_type from symbol suffix
                sym_upper = symbol.upper()
                if sym_upper.endswith("FUT"):
                    instrument_type = "FUT"
                elif sym_upper.endswith("CE"):
                    instrument_type = "CE"
                elif sym_upper.endswith("PE"):
                    instrument_type = "PE"
                else:
                    instrument_type = "EQ"

                # Capture EOD close_price for BTST overnight-reversal detection.
                # Zerodha's /positions response includes close_price = previous EOD close.
                # For an overnight NRML hold that closes today, that IS the entry-day close.
                overnight_close = float(pos.get("close_price") or 0) or None

                ct = CompletedTrade(
                    broker_account_id=broker_account_id,
                    tradingsymbol=symbol,
                    exchange=exchange,
                    instrument_type=instrument_type,
                    product=product,
                    direction=direction,
                    total_quantity=qty,
                    num_entries=1,   # exact count unknown without historical fills
                    num_exits=1,
                    avg_entry_price=avg_entry,
                    avg_exit_price=avg_exit,
                    realized_pnl=realized_pnl,
                    entry_time=entry_time,
                    exit_time=exit_time,
                    duration_minutes=duration_minutes,
                    closed_by_flip=False,
                    entry_trade_ids=[],
                    exit_trade_ids=[],
                    status="closed",
                    overnight_close_price=overnight_close,
                )
                db.add(ct)
                await db.flush()
                created += 1
                logger.info(
                    f"[overnight] Created CompletedTrade for {symbol} "
                    f"({direction} {qty} @ entry={avg_entry} exit={avg_exit} "
                    f"pnl={realized_pnl:.2f})"
                )

            except Exception as e:
                logger.error(f"[overnight] Failed to backfill {symbol}: {e}")

        return created

    @classmethod
    async def _reconcile_pnl_with_zerodha(
        cls,
        broker_account_id: uuid.UUID,
        db: AsyncSession,
    ) -> int:
        """
        Sanity-check FIFO P&L against Zerodha's stored position data.

        Since mcx_contract_specs.py now provides correct lot multipliers for all
        known MCX/CDS contracts, FIFO P&L should be accurate everywhere.

        This function:
          - NSE/BSE/NFO/BFO: runs the repair pass (fixes old records corrupted before
            the multiplier fix was deployed).  No overwrite of current records.
          - MCX/CDS: LOG-ONLY sanity check.  If FIFO differs from Zerodha's pos.pnl
            by >10% it means a contract multiplier is missing from mcx_contract_specs.py
            — log it so we can add the entry.  Never overwrite.

        NOTE: This function queries the local `positions` table only — no Zerodha
        API calls are made here.  Position data was fetched during sync_positions().
        """
        two_days_ago = datetime.now(timezone.utc) - timedelta(hours=48)

        pos_result = await db.execute(
            select(Position).where(
                Position.broker_account_id == broker_account_id,
                Position.total_quantity == 0,
            )
        )
        closed_positions = pos_result.scalars().all()

        # All exchanges: FIFO is now correct.
        # NSE/BSE repair pass is below; MCX/CDS is log-only.
        FIFO_ACCURATE_EXCHANGES = {"NSE", "BSE", "NFO", "BFO"}

        reconciled = 0
        for pos in closed_positions:
            exch = (pos.exchange or "").upper()

            # NSE/BSE F&O: FIFO is correct (Kite sends expanded units).
            # Skip overwrite; repair pass below handles any pre-existing corruption.
            if exch in FIFO_ACCURATE_EXCHANGES:
                continue

            # MCX/CDS: FIFO now uses correct multipliers from mcx_contract_specs.py.
            # This loop is LOG-ONLY — it detects contracts missing from the spec table
            # so we can add them, but never overwrites the FIFO value.
            zerodha_pnl = float(pos.pnl or 0)
            if abs(zerodha_pnl) < 0.01:
                continue

            ct_result = await db.execute(
                select(CompletedTrade).where(
                    CompletedTrade.broker_account_id == broker_account_id,
                    CompletedTrade.tradingsymbol == pos.tradingsymbol,
                    CompletedTrade.exit_time >= two_days_ago,
                    CompletedTrade.status == "closed",
                )
            )
            cts = ct_result.scalars().all()
            if not cts:
                continue

            fifo_total = sum(float(ct.realized_pnl or 0) for ct in cts)
            if abs(zerodha_pnl) > 0.01 and abs(fifo_total) > 0.01:
                ratio = fifo_total / zerodha_pnl
                if abs(ratio - 1.0) > 0.10:
                    # >10% divergence → multiplier likely missing from mcx_contract_specs.py
                    logger.warning(
                        "[reconcile] %s (%s): FIFO_total=%.2f Zerodha=%.2f ratio=%.3f "
                        "— possible missing multiplier in mcx_contract_specs.py",
                        pos.tradingsymbol, exch, fifo_total, zerodha_pnl, ratio,
                    )

        # ── Repair pass: fix NSE/BSE CompletedTrades that were incorrectly
        # overwritten by a previous reconciliation run.
        # P&L should equal (avg_exit - avg_entry) * total_quantity for LONG,
        # (avg_entry - avg_exit) * total_quantity for SHORT.
        two_days_ago_repair = datetime.now(timezone.utc) - timedelta(hours=48)
        nse_ct_result = await db.execute(
            select(CompletedTrade).where(
                CompletedTrade.broker_account_id == broker_account_id,
                CompletedTrade.exchange.in_(list(FIFO_ACCURATE_EXCHANGES)),
                CompletedTrade.exit_time >= two_days_ago_repair,
                CompletedTrade.avg_entry_price.isnot(None),
                CompletedTrade.avg_exit_price.isnot(None),
            )
        )
        nse_cts = nse_ct_result.scalars().all()
        for ct in nse_cts:
            entry = float(ct.avg_entry_price or 0)
            exit_ = float(ct.avg_exit_price or 0)
            qty = int(ct.total_quantity or 0)
            if qty == 0:
                continue
            expected_pnl = (exit_ - entry) * qty if ct.direction == "LONG" else (entry - exit_) * qty
            actual_pnl = float(ct.realized_pnl or 0)
            if abs(expected_pnl - actual_pnl) > 0.5:
                logger.info(
                    f"[repair] {ct.tradingsymbol} {ct.direction}: "
                    f"pnl was {actual_pnl:.2f}, correcting to {expected_pnl:.2f} "
                    f"(entry={entry} exit={exit_} qty={qty})"
                )
                ct.realized_pnl = round(expected_pnl, 4)
                reconciled += 1

        return reconciled
