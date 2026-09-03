"""
Checkpoint Tasks (Celery)

Self-chaining tasks that track counterfactual P&L for danger/critical alerts.

Flow:
  create_alert_checkpoint (immediate, ~10s delay)
    → check_alert_t30 (T+30 min)

money_saved = user_actual_pnl - counterfactual_pnl_at_t30
  positive = alert helped user avoid a worse outcome
  negative = market recovered / user exited at worse time
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict
from uuid import UUID

from app.core.celery_app import celery_app
from app.core.database import SessionLocal

logger = logging.getLogger(__name__)


def _compute_counterfactual_pnl(positions_snapshot: list, prices: Dict[str, float]) -> float:
    """
    Compute what the open position P&L would be at the given prices.

    positions_snapshot entries:
      tradingsymbol, exchange, quantity (net, signed), avg_entry_price, ltp_at_alert, unrealised_pnl

    quantity > 0 = LONG, quantity < 0 = SHORT
    counterfactual_pnl = abs(qty) * (new_price - avg_entry_price) * direction
    """
    total = 0.0
    for pos in positions_snapshot:
        qty = float(pos.get("quantity", 0))
        if qty == 0:
            continue
        avg_entry = float(pos.get("avg_entry_price", 0))
        exchange = pos.get("exchange", "NSE")
        symbol = pos.get("tradingsymbol", "")
        key = f"{exchange}:{symbol}"
        new_price = prices.get(key) or prices.get(symbol)
        if new_price is None:
            continue
        direction = 1 if qty > 0 else -1
        total += abs(qty) * (float(new_price) - avg_entry) * direction
    return total


@celery_app.task(
    bind=True,
    max_retries=2,
    name="app.tasks.checkpoint_tasks.create_alert_checkpoint",
)
def create_alert_checkpoint(self, alert_id: str, broker_account_id: str):
    """
    Immediate snapshot: find trigger trade's open position + LTP at alert time.
    Chains to check_alert_t30 at T+30 min on success.
    """
    async def _run():
        async with SessionLocal() as db:
            try:
                from sqlalchemy import select
                from app.models.risk_alert import RiskAlert
                from app.models.trade import Trade
                from app.models.broker_account import BrokerAccount
                from app.services.alert_checkpoint_service import alert_checkpoint_service
                from app.services.zerodha_service import zerodha_client, KiteTokenExpiredError, KiteAPIError
                from app.core.config import settings
                from cryptography.fernet import Fernet

                aid = UUID(alert_id)
                baid = UUID(broker_account_id)

                # 1. Load alert
                alert_res = await db.execute(
                    select(RiskAlert).where(RiskAlert.id == aid)
                )
                alert = alert_res.scalar_one_or_none()
                if not alert:
                    logger.warning(f"[checkpoint] Alert {alert_id} not found, skipping")
                    return

                # 2. Require trigger_trade_id
                if not alert.trigger_trade_id:
                    logger.info(f"[checkpoint] Alert {alert_id} has no trigger_trade_id, marking no_positions")
                    await alert_checkpoint_service.mark_no_positions(aid, baid, db)
                    return

                # 3. Load trigger trade → get tradingsymbol + exchange
                trade_res = await db.execute(
                    select(Trade).where(Trade.id == alert.trigger_trade_id)
                )
                trigger_trade = trade_res.scalar_one_or_none()
                if not trigger_trade:
                    logger.warning(f"[checkpoint] Trigger trade {alert.trigger_trade_id} not found")
                    await alert_checkpoint_service.mark_no_positions(aid, baid, db)
                    return

                tradingsymbol = trigger_trade.tradingsymbol
                exchange = trigger_trade.exchange or "NSE"

                # 4. Load broker account + decrypt token
                acct_res = await db.execute(
                    select(BrokerAccount).where(BrokerAccount.id == baid)
                )
                account = acct_res.scalar_one_or_none()
                if not account or not account.access_token:
                    logger.warning(f"[checkpoint] No broker account or token for {broker_account_id}")
                    await alert_checkpoint_service.mark_no_positions(aid, baid, db)
                    return

                fernet = Fernet(settings.ENCRYPTION_KEY.encode())
                access_token = fernet.decrypt(account.access_token.encode()).decode()

                # 5. Fetch positions from Kite
                try:
                    positions_data = await zerodha_client.get_positions(access_token)
                except (KiteTokenExpiredError, KiteAPIError) as e:
                    logger.warning(f"[checkpoint] Kite positions fetch failed: {e}")
                    await alert_checkpoint_service.mark_no_positions(aid, baid, db)
                    return

                net_positions = positions_data.get("net", [])

                # 6. Find open position for trigger symbol
                open_pos = None
                for pos in net_positions:
                    if pos.get("tradingsymbol") == tradingsymbol and int(pos.get("quantity", 0)) != 0:
                        open_pos = pos
                        break

                if not open_pos:
                    logger.info(
                        f"[checkpoint] No open position for {tradingsymbol} in account {broker_account_id}"
                    )
                    await alert_checkpoint_service.mark_no_positions(aid, baid, db)
                    return

                # 7. Fetch LTP for the symbol
                instrument_key = f"{exchange}:{tradingsymbol}"
                try:
                    ltps = await zerodha_client.get_ltp(access_token, [instrument_key])
                except (KiteTokenExpiredError, KiteAPIError) as e:
                    logger.warning(f"[checkpoint] LTP fetch failed for {instrument_key}: {e}")
                    await alert_checkpoint_service.mark_no_positions(aid, baid, db)
                    return

                ltp = ltps.get(instrument_key, 0.0)
                qty = int(open_pos.get("quantity", 0))
                avg_entry = float(open_pos.get("average_price", 0))
                unrealised = float(open_pos.get("unrealised", 0))

                positions_snapshot = [{
                    "tradingsymbol": tradingsymbol,
                    "exchange": exchange,
                    "quantity": qty,
                    "avg_entry_price": avg_entry,
                    "ltp_at_alert": ltp,
                    "unrealised_pnl": unrealised,
                }]

                # 8. Create checkpoint
                checkpoint = await alert_checkpoint_service.create_checkpoint(
                    alert_id=aid,
                    broker_account_id=baid,
                    positions=positions_snapshot,
                    db=db,
                )

                logger.info(
                    f"[checkpoint] Created for alert {alert_id}: "
                    f"{tradingsymbol} qty={qty} ltp={ltp} entry={avg_entry}"
                )

                # 9. Chain to T+30 (1800s)
                check_alert_t30.apply_async(
                    args=[alert_id, broker_account_id],
                    countdown=1800,
                )

            except Exception as e:
                logger.error(f"[checkpoint] create_alert_checkpoint failed: {e}", exc_info=True)
                raise self.retry(exc=e)

    asyncio.run(_run())


@celery_app.task(
    bind=True,
    max_retries=2,
    name="app.tasks.checkpoint_tasks.check_alert_t30",
)
def check_alert_t30(self, alert_id: str, broker_account_id: str):
    """T+30 min: primary counterfactual + compute money_saved."""
    async def _run():
        async with SessionLocal() as db:
            try:
                from sqlalchemy import select
                from app.models.broker_account import BrokerAccount
                from app.models.risk_alert import RiskAlert
                from app.services.alert_checkpoint_service import alert_checkpoint_service
                from app.services.zerodha_service import zerodha_client, KiteTokenExpiredError, KiteAPIError
                from app.core.config import settings
                from cryptography.fernet import Fernet

                aid = UUID(alert_id)
                baid = UUID(broker_account_id)

                checkpoint = await alert_checkpoint_service.get_by_alert_id(aid, db)
                if not checkpoint or not checkpoint.positions_snapshot:
                    logger.info(f"[checkpoint T+30] No checkpoint/positions for alert {alert_id}")
                    return

                # Load alert for alert_time
                alert_res = await db.execute(
                    select(RiskAlert).where(RiskAlert.id == aid)
                )
                alert = alert_res.scalar_one_or_none()
                alert_time = alert.detected_at if alert else checkpoint.created_at

                # Decrypt token
                acct_res = await db.execute(
                    select(BrokerAccount).where(BrokerAccount.id == baid)
                )
                account = acct_res.scalar_one_or_none()
                if not account or not account.access_token:
                    await alert_checkpoint_service.mark_error(checkpoint.id, db)
                    return

                fernet = Fernet(settings.ENCRYPTION_KEY.encode())
                try:
                    access_token = fernet.decrypt(account.access_token.encode()).decode()
                except Exception:
                    await alert_checkpoint_service.mark_error(checkpoint.id, db)
                    return

                # Fetch current prices
                instruments = [
                    f"{p['exchange']}:{p['tradingsymbol']}"
                    for p in checkpoint.positions_snapshot
                ]
                try:
                    prices = await zerodha_client.get_ltp(access_token, instruments)
                except KiteTokenExpiredError as e:
                    logger.warning(f"[checkpoint T+30] Token expired for {broker_account_id}: {e}")
                    await alert_checkpoint_service.mark_token_expiring(checkpoint.id, db)
                    return  # Do NOT chain — token won't refresh in 30 minutes
                except KiteAPIError as e:
                    logger.warning(f"[checkpoint T+30] LTP fetch failed (API error): {e}. Marking error.")
                    await alert_checkpoint_service.mark_error(checkpoint.id, db)
                    return

                # Compute counterfactual P&L at T+30
                pnl_t30 = _compute_counterfactual_pnl(checkpoint.positions_snapshot, prices)

                # Compute user's actual P&L for the trigger symbol in the 30-min window
                trigger_symbol = checkpoint.positions_snapshot[0]["tradingsymbol"] if checkpoint.positions_snapshot else None
                user_actual_pnl = 0.0
                if trigger_symbol and alert_time:
                    user_actual_pnl = await alert_checkpoint_service.get_user_actual_pnl(
                        broker_account_id=baid,
                        trigger_symbol=trigger_symbol,
                        alert_time=alert_time,
                        window_minutes=30,
                        db=db,
                    )

                # money_saved = what user actually got - what they would have if they held
                money_saved = user_actual_pnl - pnl_t30

                await alert_checkpoint_service.update_t30(
                    checkpoint_id=checkpoint.id,
                    prices=prices,
                    pnl=pnl_t30,
                    user_actual_pnl=user_actual_pnl,
                    money_saved=money_saved,
                    db=db,
                )

                logger.info(
                    f"[checkpoint T+30] alert={alert_id} pnl_t30={pnl_t30:.2f} "
                    f"user_actual={user_actual_pnl:.2f} money_saved={money_saved:.2f}"
                )

            except Exception as e:
                logger.error(f"[checkpoint T+30] failed: {e}", exc_info=True)
                raise self.retry(exc=e)

    asyncio.run(_run())


