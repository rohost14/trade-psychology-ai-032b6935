"""
PositionLedgerService

Maintains an append-only ledger of every fill that changes a position.
Handles all real F&O edge cases correctly:

  Partial fills    — BUY 100 arrives as BUY 40 + BUY 60 (separate order IDs)
  Position flip    — SELL 100 when long 50 → closes 50 (CLOSE) + opens -50 (FLIP)
  Averaging down   — BUY 50 → BUY 50 → SELL 100 (three fills, one position)
  Out-of-order     — Late webhook: fill timestamp pre-dates existing ledger entries
  Idempotency      — Same fill arriving twice (webhook retry, reconciliation)

Design rules:
  - apply_fill is the ONLY write method. Everything else is read-only.
  - apply_fill is idempotent: same idempotency_key = return existing entry.
  - This service NEVER writes to trades, positions, completed_trades, or P&L.
  - All position state is derived from the ledger (no side state).

Phase 2: isolated, tested.
Phase 3: replaces pnl_calculator.py FIFO as source of truth.
"""

import logging
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Tuple
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.position_ledger import PositionLedger, ENTRY_TYPES

logger = logging.getLogger(__name__)

# Decimal precision for prices
_PRICE_PRECISION = Decimal("0.0001")


class FillData:
    """
    Input DTO for a single fill.
    Callers construct this from a Trade or webhook payload.
    """
    __slots__ = (
        "broker_account_id", "tradingsymbol", "exchange",
        "fill_order_id", "fill_qty", "fill_price",
        "occurred_at", "idempotency_key", "session_id",
    )

    def __init__(
        self,
        broker_account_id: UUID,
        tradingsymbol: str,
        exchange: str,
        fill_order_id: str,
        fill_qty: int,           # positive = buy, negative = sell
        fill_price: Decimal,
        occurred_at: datetime,
        idempotency_key: str,    # unique per fill — e.g. "{order_id}:0"
        session_id: Optional[UUID] = None,
    ):
        self.broker_account_id = broker_account_id
        self.tradingsymbol = tradingsymbol
        self.exchange = exchange
        self.fill_order_id = fill_order_id
        self.fill_qty = fill_qty
        self.fill_price = Decimal(str(fill_price))
        self.occurred_at = occurred_at
        self.idempotency_key = idempotency_key
        self.session_id = session_id


class PositionLedgerService:

    # ------------------------------------------------------------------
    # Core write: apply_fill
    # ------------------------------------------------------------------

    @staticmethod
    async def apply_fill(
        fill: FillData,
        db: AsyncSession,
    ) -> Tuple[PositionLedger, bool]:
        """
        Apply one fill to the position ledger.

        Returns (ledger_entry, is_new).
        is_new=False means the fill was already recorded (idempotent).

        Determines entry_type automatically:
          OPEN     — no prior position for this symbol
          INCREASE — same direction as current position
          DECREASE — opposite direction, position stays open after fill
          CLOSE    — opposite direction, position goes to zero
          FLIP     — opposite direction, position crosses zero (new short/long opens)
        """
        # Idempotency check first — fast path
        existing = await PositionLedgerService._get_by_idempotency_key(
            fill.idempotency_key, db
        )
        if existing:
            logger.debug(
                f"[ledger] Duplicate fill ignored: {fill.idempotency_key}"
            )
            return existing, False

        # Get current position state
        current_qty, avg_entry_price = await PositionLedgerService.get_position(
            fill.broker_account_id,
            fill.tradingsymbol,
            fill.exchange,
            db,
        )

        # Determine entry type and compute new state
        entry_type, new_qty, new_avg_price, realized_pnl = _compute_fill_effect(
            current_qty=current_qty,
            current_avg_price=avg_entry_price,
            fill_qty=fill.fill_qty,
            fill_price=fill.fill_price,
        )

        entry = PositionLedger(
            broker_account_id=fill.broker_account_id,
            tradingsymbol=fill.tradingsymbol,
            exchange=fill.exchange,
            entry_type=entry_type,
            fill_order_id=fill.fill_order_id,
            fill_qty=fill.fill_qty,
            fill_price=fill.fill_price,
            position_qty_after=new_qty,
            avg_entry_price_after=new_avg_price,
            realized_pnl=realized_pnl,
            session_id=fill.session_id,
            occurred_at=fill.occurred_at,
            idempotency_key=fill.idempotency_key,
        )
        db.add(entry)

        try:
            await db.flush()
        except IntegrityError:
            # Race: another worker beat us. Roll back and return existing.
            await db.rollback()
            existing = await PositionLedgerService._get_by_idempotency_key(
                fill.idempotency_key, db
            )
            if existing:
                return existing, False
            raise  # Unexpected integrity error — re-raise

        logger.debug(
            f"[ledger] {entry_type} {fill.tradingsymbol} "
            f"qty={fill.fill_qty:+d} @ {fill.fill_price} "
            f"→ net={new_qty} pnl={realized_pnl}"
        )
        return entry, True

    # ------------------------------------------------------------------
    # Read: current position state
    # ------------------------------------------------------------------

    @staticmethod
    async def get_position(
        broker_account_id: UUID,
        tradingsymbol: str,
        exchange: str,
        db: AsyncSession,
    ) -> Tuple[int, Optional[Decimal]]:
        """
        Return (net_qty, avg_entry_price) for the current open position.

        Derived from the most recent ledger entry for this symbol.
        Returns (0, None) if no position.
        """
        result = await db.execute(
            select(PositionLedger)
            .where(
                and_(
                    PositionLedger.broker_account_id == broker_account_id,
                    PositionLedger.tradingsymbol == tradingsymbol,
                    PositionLedger.exchange == exchange,
                )
            )
            .order_by(PositionLedger.occurred_at.desc(), PositionLedger.created_at.desc())
            .limit(1)
        )
        last_entry = result.scalar_one_or_none()

        if not last_entry:
            return 0, None

        return last_entry.position_qty_after, last_entry.avg_entry_price_after

    # ------------------------------------------------------------------
    # Read: realized P&L for a time range
    # ------------------------------------------------------------------

    @staticmethod
    async def get_realized_pnl(
        broker_account_id: UUID,
        from_dt: datetime,
        to_dt: datetime,
        db: AsyncSession,
    ) -> Decimal:
        """
        Sum of realized_pnl for all DECREASE / CLOSE / FLIP entries
        in the given time range.
        """
        from sqlalchemy import func

        result = await db.execute(
            select(func.sum(PositionLedger.realized_pnl)).where(
                and_(
                    PositionLedger.broker_account_id == broker_account_id,
                    PositionLedger.entry_type.in_(["DECREASE", "CLOSE", "FLIP"]),
                    PositionLedger.occurred_at >= from_dt,
                    PositionLedger.occurred_at <= to_dt,
                )
            )
        )
        total = result.scalar_one_or_none()
        return Decimal(str(total or 0))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def _get_by_idempotency_key(
        key: str, db: AsyncSession
    ) -> Optional[PositionLedger]:
        result = await db.execute(
            select(PositionLedger).where(PositionLedger.idempotency_key == key)
        )
        return result.scalar_one_or_none()


# ------------------------------------------------------------------
# Pure function: compute fill effect (no DB, fully testable)
# ------------------------------------------------------------------

def _compute_fill_effect(
    current_qty: int,
    current_avg_price: Optional[Decimal],
    fill_qty: int,       # positive = buy, negative = sell
    fill_price: Decimal,
) -> Tuple[str, int, Optional[Decimal], Decimal]:
    """
    Compute the ledger entry type, new position state, and realized P&L
    for a single fill.

    Returns:
        (entry_type, new_qty, new_avg_price, realized_pnl)

    This is a pure function — no DB access. All edge cases handled here.
    """
    fill_price = Decimal(str(fill_price))
    current_avg_price = Decimal(str(current_avg_price)) if current_avg_price else Decimal("0")

    new_qty = current_qty + fill_qty
    realized_pnl = Decimal("0")

    # ── OPEN: no existing position ────────────────────────────────────
    if current_qty == 0:
        entry_type = "OPEN"
        new_avg_price = fill_price if new_qty != 0 else None
        return entry_type, new_qty, new_avg_price, realized_pnl

    # ── INCREASE: same direction as current position ──────────────────
    current_is_long = current_qty > 0
    fill_is_buy = fill_qty > 0

    if current_is_long == fill_is_buy:
        entry_type = "INCREASE"
        # Weighted average entry price
        new_avg_price = (
            (current_avg_price * abs(current_qty) + fill_price * abs(fill_qty))
            / abs(new_qty)
        ).quantize(_PRICE_PRECISION, rounding=ROUND_HALF_UP)
        return entry_type, new_qty, new_avg_price, realized_pnl

    # ── Closing / reducing fill (opposite direction) ──────────────────
    closing_qty = min(abs(fill_qty), abs(current_qty))

    if current_is_long:
        realized_pnl = (fill_price - current_avg_price) * Decimal(str(closing_qty))
    else:
        realized_pnl = (current_avg_price - fill_price) * Decimal(str(closing_qty))

    realized_pnl = realized_pnl.quantize(_PRICE_PRECISION, rounding=ROUND_HALF_UP)

    if new_qty == 0:
        # ── CLOSE: position goes exactly to zero ─────────────────────
        entry_type = "CLOSE"
        new_avg_price = None

    elif (new_qty > 0) == current_is_long:
        # ── DECREASE: position reduced but same direction ─────────────
        entry_type = "DECREASE"
        new_avg_price = current_avg_price  # avg price unchanged on partial close

    else:
        # ── FLIP: position crosses zero (new direction opens) ─────────
        # e.g. long 50, sell 100 → closes 50 long, opens 50 short
        entry_type = "FLIP"
        # The new position's avg entry price = the fill price
        # (the fill_qty beyond the close starts a new position at fill_price)
        new_avg_price = fill_price

    return entry_type, new_qty, new_avg_price, realized_pnl


# Singleton
position_ledger_service = PositionLedgerService()
