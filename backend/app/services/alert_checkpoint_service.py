"""
AlertCheckpoint Service

CRUD operations for alert checkpoints + user actual P&L queries.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from uuid import UUID
import logging

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert_checkpoint import AlertCheckpoint
from app.models.completed_trade import CompletedTrade

logger = logging.getLogger(__name__)


class AlertCheckpointService:

    async def create_checkpoint(
        self,
        alert_id: UUID,
        broker_account_id: UUID,
        positions: List[Dict],
        db: AsyncSession,
    ) -> AlertCheckpoint:
        """
        Create a new AlertCheckpoint at alert time.

        positions: list of dicts with keys:
          tradingsymbol, exchange, quantity, avg_entry_price, ltp_at_alert, unrealised_pnl
        """
        total_unrealized = sum(float(p.get("unrealised_pnl", 0)) for p in positions)

        checkpoint = AlertCheckpoint(
            alert_id=alert_id,
            broker_account_id=broker_account_id,
            positions_snapshot=positions,
            total_unrealized_pnl=total_unrealized,
            calculation_status="pending",
        )
        db.add(checkpoint)
        await db.commit()
        await db.refresh(checkpoint)
        logger.info(
            f"AlertCheckpoint created: {checkpoint.id} for alert {alert_id}, "
            f"{len(positions)} positions tracked"
        )
        return checkpoint

    async def get_by_alert_id(
        self, alert_id: UUID, db: AsyncSession
    ) -> Optional[AlertCheckpoint]:
        result = await db.execute(
            select(AlertCheckpoint).where(AlertCheckpoint.alert_id == alert_id)
        )
        return result.scalar_one_or_none()

    async def update_t5(
        self,
        checkpoint_id: UUID,
        prices: Dict[str, float],
        pnl: float,
        db: AsyncSession,
    ) -> None:
        result = await db.execute(
            select(AlertCheckpoint).where(AlertCheckpoint.id == checkpoint_id)
        )
        cp = result.scalar_one_or_none()
        if not cp:
            logger.warning(f"Checkpoint {checkpoint_id} not found for T+5 update")
            return
        cp.prices_at_t5 = prices
        cp.pnl_at_t5 = pnl
        cp.checked_at_t5 = datetime.now(timezone.utc)
        cp.calculation_status = "calculating"
        await db.commit()

    async def update_t30(
        self,
        checkpoint_id: UUID,
        prices: Dict[str, float],
        pnl: float,
        user_actual_pnl: float,
        money_saved: float,
        db: AsyncSession,
    ) -> None:
        result = await db.execute(
            select(AlertCheckpoint).where(AlertCheckpoint.id == checkpoint_id)
        )
        cp = result.scalar_one_or_none()
        if not cp:
            logger.warning(f"Checkpoint {checkpoint_id} not found for T+30 update")
            return
        cp.prices_at_t30 = prices
        cp.pnl_at_t30 = pnl
        cp.checked_at_t30 = datetime.now(timezone.utc)
        cp.user_actual_pnl = user_actual_pnl
        cp.money_saved = money_saved
        cp.calculation_status = "complete"
        await db.commit()

    async def update_t60(
        self,
        checkpoint_id: UUID,
        prices: Dict[str, float],
        pnl: float,
        user_actual_pnl: float,
        money_saved: float,
        db: AsyncSession,
    ) -> None:
        result = await db.execute(
            select(AlertCheckpoint).where(AlertCheckpoint.id == checkpoint_id)
        )
        cp = result.scalar_one_or_none()
        if not cp:
            logger.warning(f"Checkpoint {checkpoint_id} not found for T+60 update")
            return
        cp.prices_at_t60 = prices
        cp.pnl_at_t60 = pnl
        cp.checked_at_t60 = datetime.now(timezone.utc)
        cp.user_actual_pnl = user_actual_pnl
        cp.money_saved = money_saved
        # status stays 'complete'
        await db.commit()

    async def mark_error(
        self, checkpoint_id: UUID, db: AsyncSession
    ) -> None:
        result = await db.execute(
            select(AlertCheckpoint).where(AlertCheckpoint.id == checkpoint_id)
        )
        cp = result.scalar_one_or_none()
        if cp:
            cp.calculation_status = "error"
            await db.commit()

    async def mark_token_expiring(
        self, checkpoint_id: UUID, db: AsyncSession
    ) -> None:
        """
        Mark checkpoint as stopped due to token expiry.
        Unlike 'error', this is expected at end-of-day and the chain should NOT continue.
        Zerodha tokens expire at ~6:30 AM IST — alerts near market open risk hitting this.
        """
        result = await db.execute(
            select(AlertCheckpoint).where(AlertCheckpoint.id == checkpoint_id)
        )
        cp = result.scalar_one_or_none()
        if cp:
            cp.calculation_status = "token_expiring"
            await db.commit()

    async def mark_no_positions(
        self, alert_id: UUID, broker_account_id: UUID, db: AsyncSession
    ) -> AlertCheckpoint:
        """Create a checkpoint that immediately marks status='no_positions'."""
        checkpoint = AlertCheckpoint(
            alert_id=alert_id,
            broker_account_id=broker_account_id,
            positions_snapshot=[],
            total_unrealized_pnl=0,
            calculation_status="no_positions",
        )
        db.add(checkpoint)
        await db.commit()
        await db.refresh(checkpoint)
        return checkpoint

    async def get_user_actual_pnl(
        self,
        broker_account_id: UUID,
        trigger_symbol: str,
        alert_time: datetime,
        window_minutes: int,
        db: AsyncSession,
    ) -> float:
        """
        Sum realized_pnl from CompletedTrades for the trigger symbol
        whose exit_time falls within alert_time + window_minutes.
        """
        window_end = alert_time + timedelta(minutes=window_minutes)
        result = await db.execute(
            select(CompletedTrade).where(
                and_(
                    CompletedTrade.broker_account_id == broker_account_id,
                    CompletedTrade.tradingsymbol == trigger_symbol,
                    CompletedTrade.exit_time >= alert_time,
                    CompletedTrade.exit_time <= window_end,
                )
            )
        )
        trades = result.scalars().all()
        return sum(float(t.realized_pnl or 0) for t in trades)


alert_checkpoint_service = AlertCheckpointService()
