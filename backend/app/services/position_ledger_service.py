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
  - All position state is derived from the ledger (no side state).

Real-time path (Phase 3 cutover):
  - apply_fill() called from process_webhook_trade after every COMPLETE fill
  - ledger entry's realized_pnl used to update Trade.pnl (replaces calculate_trade_pnl_realtime)
  - build_completed_trade_on_close() called on CLOSE/FLIP to create CompletedTrade immediately
  - Batch FIFO (pnl_calculator) still runs on EOD reconciliation/initial sync —
    it overwrites CompletedTrades for the recompute window (both should agree on P&L)
"""

import logging
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Tuple, List
from uuid import UUID

from sqlalchemy import select, and_, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.position_ledger import PositionLedger, ENTRY_TYPES
from app.services.mcx_contract_specs import get_lot_multiplier

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

        Handles out-of-order fills (late webhook delivery):
          If fill.occurred_at is earlier than any existing entry for the same
          symbol, a full replay is triggered — all affected entries are
          recomputed in timestamp order so position state is always correct.
        """
        # Idempotency check first — fast path
        existing = await PositionLedgerService._get_by_idempotency_key(
            fill.idempotency_key, db
        )
        if existing:
            logger.debug(f"[ledger] Duplicate fill ignored: {fill.idempotency_key}")
            return existing, False

        # Check if this is a late fill (arrived out of timestamp order)
        last_entry = await PositionLedgerService._get_last_entry(
            fill.broker_account_id, fill.tradingsymbol, fill.exchange, db
        )
        if last_entry is not None and fill.occurred_at < last_entry.occurred_at:
            logger.warning(
                f"[ledger] Late fill detected for {fill.tradingsymbol}: "
                f"fill at {fill.occurred_at} but latest entry at {last_entry.occurred_at}. "
                f"Triggering replay."
            )
            return await PositionLedgerService._apply_fill_with_replay(fill, db)

        # Normal path: sequential fill, compute against current state
        current_qty, avg_entry_price = await PositionLedgerService.get_position(
            fill.broker_account_id, fill.tradingsymbol, fill.exchange, db
        )
        entry_type, new_qty, new_avg_price, realized_pnl = _compute_fill_effect(
            current_qty=current_qty,
            current_avg_price=avg_entry_price,
            fill_qty=fill.fill_qty,
            fill_price=fill.fill_price,
        )

        # Apply lot multiplier for MCX/CDS — Kite sends fill qty in LOTS for these
        # exchanges (e.g. 1 CRUDEOIL lot = 100 barrels).  _compute_fill_effect is
        # exchange-agnostic so we apply the multiplier here.
        _lot_mult = Decimal(str(get_lot_multiplier(fill.exchange, fill.tradingsymbol)))
        if _lot_mult != 1 and realized_pnl:
            realized_pnl = realized_pnl * _lot_mult

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
            await db.rollback()
            existing = await PositionLedgerService._get_by_idempotency_key(
                fill.idempotency_key, db
            )
            if existing:
                return existing, False
            raise

        logger.debug(
            f"[ledger] {entry_type} {fill.tradingsymbol} "
            f"qty={fill.fill_qty:+d} @ {fill.fill_price} "
            f"→ net={new_qty} pnl={realized_pnl}"
        )
        return entry, True

    @staticmethod
    async def _apply_fill_with_replay(
        fill: FillData,
        db: AsyncSession,
    ) -> Tuple[PositionLedger, bool]:
        """
        Handle an out-of-order fill by replaying all entries in timestamp order.

        Strategy:
          1. Load all existing ledger entries for this symbol (ordered by occurred_at ASC)
          2. Insert the new fill at its correct chronological position
          3. Re-run _compute_fill_effect from scratch through the full sequence
          4. UPDATE all affected entries in-place (position_qty_after, avg_entry_price_after,
             realized_pnl, entry_type)
          5. Insert the new fill row

        Existing idempotency_keys are preserved — only computed fields are updated.
        The ledger remains the single source of truth.
        """
        # Load all existing entries for this symbol in time order
        result = await db.execute(
            select(PositionLedger)
            .where(
                and_(
                    PositionLedger.broker_account_id == fill.broker_account_id,
                    PositionLedger.tradingsymbol == fill.tradingsymbol,
                    PositionLedger.exchange == fill.exchange,
                )
            )
            .order_by(PositionLedger.occurred_at.asc(), PositionLedger.created_at.asc())
        )
        existing_entries: List[PositionLedger] = list(result.scalars().all())

        # Build the new entry object (not yet in DB)
        new_entry = PositionLedger(
            broker_account_id=fill.broker_account_id,
            tradingsymbol=fill.tradingsymbol,
            exchange=fill.exchange,
            entry_type="OPEN",          # placeholder — will be set during replay
            fill_order_id=fill.fill_order_id,
            fill_qty=fill.fill_qty,
            fill_price=fill.fill_price,
            position_qty_after=0,       # placeholder
            avg_entry_price_after=None, # placeholder
            realized_pnl=Decimal("0"),  # placeholder
            session_id=fill.session_id,
            occurred_at=fill.occurred_at,
            idempotency_key=fill.idempotency_key,
        )
        db.add(new_entry)
        await db.flush()  # get new_entry.id assigned

        # Insert new_entry into the sorted list at the right position
        all_entries = existing_entries + [new_entry]
        all_entries.sort(key=lambda e: (e.occurred_at, e.created_at))

        # Replay all entries from the beginning, updating computed fields
        running_qty = 0
        running_avg: Optional[Decimal] = None

        # Lot multiplier — same for all entries in this symbol (exchange is fixed)
        _replay_lot_mult = Decimal(str(get_lot_multiplier(fill.exchange, fill.tradingsymbol)))

        # Find the index where the new entry sits — only entries at or after
        # that index need updating (entries before are unchanged)
        new_idx = next(i for i, e in enumerate(all_entries) if e.id == new_entry.id)

        for i, entry in enumerate(all_entries):
            entry_type, new_qty, new_avg, pnl = _compute_fill_effect(
                current_qty=running_qty,
                current_avg_price=running_avg,
                fill_qty=entry.fill_qty,
                fill_price=entry.fill_price,
            )
            if _replay_lot_mult != 1 and pnl:
                pnl = pnl * _replay_lot_mult
            running_qty = new_qty
            running_avg = new_avg

            if i >= new_idx:
                # Update this entry's computed fields
                entry.entry_type = entry_type
                entry.position_qty_after = new_qty
                entry.avg_entry_price_after = new_avg
                entry.realized_pnl = pnl

        await db.flush()

        logger.info(
            f"[ledger] Replay complete for {fill.tradingsymbol}: "
            f"{len(existing_entries)} existing entries recomputed, "
            f"new fill inserted at position {new_idx}/{len(all_entries)}"
        )
        return new_entry, True

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

    @staticmethod
    async def get_net_qty(
        broker_account_id: UUID,
        tradingsymbol: str,
        db: AsyncSession,
    ) -> int:
        """
        Return current net position quantity for a symbol (any exchange).
        Convenience method when exchange is not known at call site.
        Returns 0 if no position exists.
        """
        result = await db.execute(
            select(PositionLedger)
            .where(
                and_(
                    PositionLedger.broker_account_id == broker_account_id,
                    PositionLedger.tradingsymbol == tradingsymbol,
                )
            )
            .order_by(PositionLedger.occurred_at.desc(), PositionLedger.created_at.desc())
            .limit(1)
        )
        last_entry = result.scalar_one_or_none()
        return last_entry.position_qty_after if last_entry else 0

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
    # CompletedTrade derivation from ledger
    # ------------------------------------------------------------------

    @staticmethod
    async def build_completed_trade_on_close(
        close_entry: "PositionLedger",
        db: AsyncSession,
    ) -> Optional["CompletedTrade"]:
        """
        Build a CompletedTrade from the ledger when a position is fully closed.

        Should be called immediately after apply_fill() returns a CLOSE or FLIP entry.
        Queries all ledger entries in the current round (from the last close/start
        to this entry) and aggregates them into a CompletedTrade.

        Returns None if the data is insufficient to build a valid trade.
        Does NOT add the CompletedTrade to the session — caller does that.
        """
        if close_entry.entry_type not in ("CLOSE", "FLIP"):
            return None

        from app.models.completed_trade import CompletedTrade as CTModel

        # Load all ledger entries for this symbol up to (and including) the close entry
        result = await db.execute(
            select(PositionLedger)
            .where(
                and_(
                    PositionLedger.broker_account_id == close_entry.broker_account_id,
                    PositionLedger.tradingsymbol == close_entry.tradingsymbol,
                    PositionLedger.exchange == close_entry.exchange,
                )
            )
            .order_by(PositionLedger.occurred_at.asc(), PositionLedger.created_at.asc())
        )
        all_entries: List[PositionLedger] = list(result.scalars().all())

        # Find the start of the current round: the entry immediately after the
        # most recent previous CLOSE or FLIP (or the very beginning if none).
        round_start_idx = 0
        for i, entry in enumerate(all_entries):
            if entry.id == close_entry.id:
                break
            if entry.entry_type in ("CLOSE", "FLIP"):
                round_start_idx = i + 1

        round_entries = all_entries[round_start_idx:]

        if not round_entries:
            return None

        # Separate entry fills (OPEN/INCREASE) from exit fills (DECREASE/CLOSE/FLIP)
        entry_fills = [e for e in round_entries if e.entry_type in ("OPEN", "INCREASE")]
        exit_fills = [e for e in round_entries if e.entry_type in ("DECREASE", "CLOSE", "FLIP")]

        if not entry_fills or not exit_fills:
            return None

        total_entry_qty = sum(abs(e.fill_qty) for e in entry_fills)
        total_exit_qty = sum(abs(e.fill_qty) for e in exit_fills)

        if total_entry_qty == 0 or total_exit_qty == 0:
            return None

        # Weighted average prices
        avg_entry = (
            sum(Decimal(str(e.fill_price)) * abs(e.fill_qty) for e in entry_fills)
            / total_entry_qty
        ).quantize(_PRICE_PRECISION, rounding=ROUND_HALF_UP)

        avg_exit = (
            sum(Decimal(str(e.fill_price)) * abs(e.fill_qty) for e in exit_fills)
            / total_exit_qty
        ).quantize(_PRICE_PRECISION, rounding=ROUND_HALF_UP)

        # Total realized P&L is the sum of all exit-side entries
        total_pnl = sum(e.realized_pnl for e in exit_fills)

        # Timing
        entry_time = min(e.occurred_at for e in entry_fills)
        exit_time = max(e.occurred_at for e in exit_fills)
        duration = max(0, int((exit_time - entry_time).total_seconds() / 60))

        # Direction from first entry fill
        direction = "LONG" if entry_fills[0].fill_qty > 0 else "SHORT"

        return CTModel(
            broker_account_id=close_entry.broker_account_id,
            tradingsymbol=close_entry.tradingsymbol,
            exchange=close_entry.exchange,
            direction=direction,
            total_quantity=total_entry_qty,
            num_entries=len(entry_fills),
            num_exits=len(exit_fills),
            avg_entry_price=float(avg_entry),
            avg_exit_price=float(avg_exit),
            realized_pnl=float(total_pnl),
            pnl_pct=_compute_pnl_pct(float(avg_entry), float(avg_exit), direction),
            entry_time=entry_time,
            exit_time=exit_time,
            duration_minutes=duration,
            closed_by_flip=(close_entry.entry_type == "FLIP"),
            entry_trade_ids=[e.fill_order_id for e in entry_fills],
            exit_trade_ids=[e.fill_order_id for e in exit_fills],
            status="closed",
        )

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

    @staticmethod
    async def _get_last_entry(
        broker_account_id: UUID,
        tradingsymbol: str,
        exchange: str,
        db: AsyncSession,
    ) -> Optional[PositionLedger]:
        """Return the most recent ledger entry for a symbol (by occurred_at DESC)."""
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
        return result.scalar_one_or_none()


# ------------------------------------------------------------------
# Pure helper: pnl_pct
# ------------------------------------------------------------------

def _compute_pnl_pct(
    avg_entry: Optional[float],
    avg_exit: Optional[float],
    direction: str,
) -> Optional[float]:
    """
    Return the percentage return relative to the entry price.

    LONG:  (exit - entry) / entry * 100
    SHORT: (entry - exit) / entry * 100

    Returns None if entry price is zero / unknown.
    """
    if not avg_entry or avg_entry == 0:
        return None
    if direction == "LONG":
        return round((avg_exit - avg_entry) / avg_entry * 100, 2)
    else:  # SHORT
        return round((avg_entry - avg_exit) / avg_entry * 100, 2)


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
