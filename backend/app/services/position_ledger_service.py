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
from typing import Optional, Tuple, List, Dict, TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select, and_, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.position_ledger import PositionLedger, ENTRY_TYPES
from app.services.mcx_contract_specs import get_lot_multiplier_or_none

if TYPE_CHECKING:
    # Runtime import is local (inside build_completed_trade_on_close); this block
    # only resolves the quoted "CompletedTrade" return annotation for mypy/pyflakes.
    from app.models.completed_trade import CompletedTrade

logger = logging.getLogger(__name__)

# Decimal precision for prices
_PRICE_PRECISION = Decimal("0.0001")


class FillData:
    """
    Input DTO for a single fill.
    Callers construct this from a Trade or webhook payload.
    """
    __slots__ = (
        "broker_account_id", "tradingsymbol", "exchange", "product",
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
        product: Optional[str] = None,   # MIS/NRML/MTF — part of the position key (M1)
    ):
        self.broker_account_id = broker_account_id
        self.tradingsymbol = tradingsymbol
        self.exchange = exchange
        self.product = product
        self.fill_order_id = fill_order_id
        self.fill_qty = fill_qty
        self.fill_price = Decimal(str(fill_price))
        self.occurred_at = occurred_at
        self.idempotency_key = idempotency_key
        self.session_id = session_id


class LedgerPositionState:
    """
    Snapshot of one position key as the ledger currently sees it.

    Returned by get_position_states_bulk. `avg_entry_price` is the cost of the
    CURRENT open round only — unlike the broker's day-cumulative average, which
    still carries fills from rounds that have already closed.
    """
    __slots__ = (
        "tradingsymbol", "exchange", "product",
        "qty", "avg_entry_price", "round_started_at", "last_entry_type",
    )

    def __init__(
        self,
        tradingsymbol: str,
        exchange: Optional[str],
        product: Optional[str],
        qty: int,
        avg_entry_price: Optional[Decimal],
        round_started_at: Optional[datetime],
        last_entry_type: Optional[str],
    ):
        self.tradingsymbol = tradingsymbol
        self.exchange = exchange
        self.product = product
        self.qty = qty
        self.avg_entry_price = avg_entry_price
        self.round_started_at = round_started_at
        self.last_entry_type = last_entry_type


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
            fill.broker_account_id, fill.tradingsymbol, fill.exchange, db,
            product=fill.product,
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
            fill.broker_account_id, fill.tradingsymbol, fill.exchange, db,
            product=fill.product,
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
        _lot_mult = await PositionLedgerService._resolve_lot_mult(
            fill.broker_account_id, fill.exchange, fill.tradingsymbol, db
        )
        if _lot_mult != 1 and realized_pnl:
            realized_pnl = realized_pnl * _lot_mult

        entry = PositionLedger(
            broker_account_id=fill.broker_account_id,
            tradingsymbol=fill.tradingsymbol,
            exchange=fill.exchange,
            product=fill.product,
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
                    PositionLedger.product == fill.product,   # M1: replay one product only
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
            product=fill.product,
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
        _replay_lot_mult = await PositionLedgerService._resolve_lot_mult(
            fill.broker_account_id, fill.exchange, fill.tradingsymbol, db
        )

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

        # Rebuild the CompletedTrades derived from the rounds this late fill changed.
        # A late fill can alter qty/price/P&L of an already-closed round, or change an
        # entry's type (e.g. CLOSE→DECREASE so a round no longer closes there). The
        # derived CompletedTrades built from the OLD values are now stale, so we delete
        # and recreate the ledger-derived CompletedTrades for every round closing at or
        # after this fill's timestamp. The new_entry's OWN round is excluded here — the
        # caller (webhook / replay path) builds that one, so it can run strategy
        # detection on the fresh CompletedTrade.
        await PositionLedgerService._rebuild_completed_trades_after_replay(
            fill.broker_account_id,
            fill.tradingsymbol,
            fill.exchange,
            fill.occurred_at,
            exclude_entry_id=new_entry.id,
            db=db,
            product=fill.product,
        )

        logger.info(
            f"[ledger] Replay complete for {fill.tradingsymbol}: "
            f"{len(existing_entries)} existing entries recomputed, "
            f"new fill inserted at position {new_idx}/{len(all_entries)}"
        )
        return new_entry, True

    @staticmethod
    async def _rebuild_completed_trades_after_replay(
        broker_account_id: UUID,
        tradingsymbol: str,
        exchange: str,
        from_dt: datetime,
        exclude_entry_id,
        db: AsyncSession,
        product: Optional[str] = None,
    ) -> None:
        """
        Delete and recreate ledger-derived CompletedTrades for a symbol's rounds that
        close at or after `from_dt`, using the (already-recomputed) ledger as truth.
        Scoped to one product (M1) so a MIS replay never rebuilds NRML rounds.

        Called only from _apply_fill_with_replay after an out-of-order fill mutates the
        ledger. Overnight-backfill CompletedTrades (no exit_trade_ids — their entry leg
        predates the ledger) are left untouched. The round terminated by the new fill
        (exclude_entry_id) is skipped so the caller can build it and run strategy
        detection on the result.
        """
        from app.models.completed_trade import CompletedTrade as CTModel

        # 1. Delete stale ledger-derived CompletedTrades closing at/after from_dt.
        stale_result = await db.execute(
            select(CTModel).where(
                and_(
                    CTModel.broker_account_id == broker_account_id,
                    CTModel.tradingsymbol == tradingsymbol,
                    CTModel.exchange == exchange,
                    CTModel.product == product,
                    CTModel.exit_time >= from_dt,
                )
            )
        )
        for ct in stale_result.scalars().all():
            # exit_trade_ids populated ⇒ ledger-derived (safe to rebuild).
            # Empty ⇒ overnight backfill (ledger lacks its entry leg) — leave intact.
            if ct.exit_trade_ids:
                await db.delete(ct)
        await db.flush()

        # 2. Rebuild each CLOSE/FLIP round closing at/after from_dt from the ledger,
        #    excluding the new fill's own round (the caller builds that one).
        entries_result = await db.execute(
            select(PositionLedger)
            .where(
                and_(
                    PositionLedger.broker_account_id == broker_account_id,
                    PositionLedger.tradingsymbol == tradingsymbol,
                    PositionLedger.exchange == exchange,
                    PositionLedger.product == product,
                )
            )
            .order_by(PositionLedger.occurred_at.asc(), PositionLedger.created_at.asc())
        )
        for entry in entries_result.scalars().all():
            if entry.id == exclude_entry_id:
                continue
            if entry.entry_type in ("CLOSE", "FLIP") and entry.occurred_at >= from_dt:
                ct = await PositionLedgerService.build_completed_trade_on_close(entry, db)
                if ct:
                    db.add(ct)
        await db.flush()

    # ------------------------------------------------------------------
    # Read: current position state
    # ------------------------------------------------------------------

    @staticmethod
    async def get_position(
        broker_account_id: UUID,
        tradingsymbol: str,
        exchange: str,
        db: AsyncSession,
        product: Optional[str] = None,
    ) -> Tuple[int, Optional[Decimal]]:
        """
        Return (net_qty, avg_entry_price) for the current open position.

        Derived from the most recent ledger entry for this symbol + product (M1):
        the same symbol in MIS vs NRML is two independent positions.
        Returns (0, None) if no position.
        """
        result = await db.execute(
            select(PositionLedger)
            .where(
                and_(
                    PositionLedger.broker_account_id == broker_account_id,
                    PositionLedger.tradingsymbol == tradingsymbol,
                    PositionLedger.exchange == exchange,
                    PositionLedger.product == product,
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

    @staticmethod
    async def get_position_states_bulk(
        broker_account_id: UUID,
        db: AsyncSession,
    ) -> Dict[Tuple[str, Optional[str], Optional[str]], "LedgerPositionState"]:
        """
        Return the current ledger state for EVERY position key of one account,
        in a single query, keyed by (tradingsymbol, exchange, product).

        Why this exists: `positions.average_entry_price` is a mirror of Kite's
        `average_price`, which is the day-CUMULATIVE buy average — it still includes
        fills belonging to rounds that already closed. Buy 1 @9.00, sell 1 @8.85,
        buy 3 @9.41 leaves Kite reporting 9.3075 for a position whose real cost is
        9.41. The ledger already models this correctly (a CLOSE resets the average),
        so trade_sync_service overwrites the broker figure from here.

        Per key this returns the latest entry's net qty and average, plus the start
        time of the CURRENT round — the round boundary is what makes the number
        different from the broker's, and it also fixes hold duration on a position
        that closed and reopened in the same session.

        Raw SQL because it needs a window function: `round_idx` counts the CLOSE/FLIP
        entries strictly BEFORE each row, which numbers the flat-to-flat rounds. A
        CLOSE therefore belongs to the round it terminates and the next fill starts a
        new one — the same segmentation `_build_round_ct_fields` applies.
        """
        sql = text("""
            WITH marked AS (
                SELECT
                    tradingsymbol, exchange, product, entry_type,
                    position_qty_after, avg_entry_price_after, occurred_at, created_at,
                    COALESCE(SUM(CASE WHEN entry_type IN ('CLOSE','FLIP') THEN 1 ELSE 0 END) OVER (
                        PARTITION BY tradingsymbol, exchange, product
                        ORDER BY occurred_at, created_at
                        ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                    ), 0) AS round_idx
                FROM position_ledger
                WHERE broker_account_id = :account_id
            ),
            latest AS (
                SELECT DISTINCT ON (tradingsymbol, exchange, product)
                    tradingsymbol, exchange, product, entry_type,
                    position_qty_after, avg_entry_price_after, occurred_at, round_idx
                FROM marked
                ORDER BY tradingsymbol, exchange, product, occurred_at DESC, created_at DESC
            ),
            round_start AS (
                SELECT tradingsymbol, exchange, product, round_idx,
                       MIN(occurred_at) AS started_at
                FROM marked
                GROUP BY tradingsymbol, exchange, product, round_idx
            )
            SELECT l.tradingsymbol, l.exchange, l.product, l.entry_type,
                   l.position_qty_after, l.avg_entry_price_after,
                   l.occurred_at AS last_occurred_at,
                   rs.started_at  AS round_started_at
            FROM latest l
            JOIN round_start rs
              ON  rs.tradingsymbol = l.tradingsymbol
              AND rs.exchange IS NOT DISTINCT FROM l.exchange
              AND rs.product  IS NOT DISTINCT FROM l.product
              AND rs.round_idx = l.round_idx
        """)

        result = await db.execute(sql, {"account_id": str(broker_account_id)})

        states: Dict[Tuple[str, Optional[str], Optional[str]], LedgerPositionState] = {}
        for row in result.mappings():
            round_started_at = row["round_started_at"]
            # A FLIP closes the previous round AND opens the current one, so it is
            # grouped with the round it terminated. When the newest entry IS the flip,
            # the current round began at the flip itself, not at the older round's open.
            if row["entry_type"] == "FLIP":
                round_started_at = row["last_occurred_at"]

            avg = row["avg_entry_price_after"]
            states[(row["tradingsymbol"], row["exchange"], row["product"])] = LedgerPositionState(
                tradingsymbol=row["tradingsymbol"],
                exchange=row["exchange"],
                product=row["product"],
                qty=int(row["position_qty_after"] or 0),
                avg_entry_price=Decimal(str(avg)) if avg is not None else None,
                round_started_at=round_started_at,
                last_entry_type=row["entry_type"],
            )
        return states

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
                    PositionLedger.product == close_entry.product,   # M1: this round's product only
                )
            )
            .order_by(PositionLedger.occurred_at.asc(), PositionLedger.created_at.asc())
        )
        all_entries: List[PositionLedger] = list(result.scalars().all())

        # Find this round: entries from just after the most recent previous
        # CLOSE/FLIP up to (and including) the close entry. Bounding the slice at
        # close_idx (not to the end) keeps it correct when later entries already
        # exist (the replay-rebuild path), not just in the live call.
        close_idx = next((i for i, e in enumerate(all_entries) if e.id == close_entry.id), None)
        if close_idx is None:
            return None
        round_start_idx = 0
        for i in range(close_idx):
            if all_entries[i].entry_type in ("CLOSE", "FLIP"):
                round_start_idx = i + 1
        round_entries = all_entries[round_start_idx: close_idx + 1]

        # A FLIP immediately before this round closed the prior round AND opened
        # this one — pass it so its opened quantity counts as this round's entry
        # (M2: flip-opened rounds were previously dropped for lacking OPEN fills).
        preceding = all_entries[round_start_idx - 1] if round_start_idx > 0 else None
        preceding_flip = preceding if (preceding is not None and preceding.entry_type == "FLIP") else None

        fields = _build_round_ct_fields(round_entries, preceding_flip)
        if fields is None:
            return None

        duration = max(0, int((fields["exit_time"] - fields["entry_time"]).total_seconds() / 60))

        return CTModel(
            # Deterministic id shared with the batch FIFO builder so a later
            # recompute reuses this id instead of churning it (M6/E2).
            id=stable_completed_trade_id(
                close_entry.broker_account_id,
                close_entry.tradingsymbol,
                fields["entry_time"],
                fields["direction"],
                fields["exit_time"],
            ),
            broker_account_id=close_entry.broker_account_id,
            tradingsymbol=close_entry.tradingsymbol,
            exchange=close_entry.exchange,
            product=close_entry.product,
            direction=fields["direction"],
            total_quantity=fields["total_quantity"],
            num_entries=fields["num_entries"],
            num_exits=fields["num_exits"],
            avg_entry_price=float(fields["avg_entry"]),
            avg_exit_price=float(fields["avg_exit"]),
            realized_pnl=float(fields["total_pnl"]),
            pnl_pct=_compute_pnl_pct(float(fields["avg_entry"]), float(fields["avg_exit"]), fields["direction"]),
            entry_time=fields["entry_time"],
            exit_time=fields["exit_time"],
            duration_minutes=duration,
            closed_by_flip=(close_entry.entry_type == "FLIP"),
            entry_trade_ids=fields["entry_trade_ids"],
            exit_trade_ids=fields["exit_trade_ids"],
            status="closed",
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def _resolve_lot_mult(
        broker_account_id: UUID,
        exchange: str,
        tradingsymbol: str,
        db: AsyncSession,
    ) -> Decimal:
        """
        Resolve the contract multiplier used to scale realized P&L.

        Fast path (NSE/BSE/NFO/BFO and known MCX/CDS contracts): returned from the
        hardcoded table with no DB access. Only an MCX contract missing from the table
        falls through to a single query for Zerodha's own multiplier, which sync_positions
        stored on the Position row. Defaults to 1 if still unresolved.
        """
        mult = get_lot_multiplier_or_none(exchange, tradingsymbol)
        if mult is not None:
            return Decimal(str(mult))

        from app.models.position import Position
        result = await db.execute(
            select(Position.multiplier)
            .where(
                and_(
                    Position.broker_account_id == broker_account_id,
                    Position.tradingsymbol == tradingsymbol,
                    Position.exchange == exchange,
                )
            )
            .order_by(Position.synced_at.desc())
            .limit(1)
        )
        val = result.scalar_one_or_none()
        try:
            resolved = Decimal(str(val)) if val else Decimal("1")
        except Exception:
            resolved = Decimal("1")
        return resolved if resolved > 0 else Decimal("1")

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
        product: Optional[str] = None,
    ) -> Optional[PositionLedger]:
        """Return the most recent ledger entry for a symbol + product (by occurred_at DESC)."""
        result = await db.execute(
            select(PositionLedger)
            .where(
                and_(
                    PositionLedger.broker_account_id == broker_account_id,
                    PositionLedger.tradingsymbol == tradingsymbol,
                    PositionLedger.exchange == exchange,
                    PositionLedger.product == product,
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


def _build_round_ct_fields(round_entries, preceding_flip=None):
    """
    Pure: aggregate one flat-to-flat round's ledger entries into CompletedTrade
    field values (no DB). `round_entries` = this round's rows ending at its closing
    entry. `preceding_flip` = the FLIP that OPENED this round (its close of the prior
    round doubles as this round's opening) or None for a normally-opened round.

    Fixes M2: a flip-opened round had no OPEN/INCREASE fills, so it returned None and
    never became a CompletedTrade. The flip's opened quantity is now counted as the
    round's entry, at the flip fill price. Returns a field dict, or None if insufficient.
    """
    entry_items = []  # (qty>0, price:Decimal, occurred_at, order_id)
    direction = None

    if preceding_flip is not None:
        opened = abs(preceding_flip.position_qty_after or 0)
        if opened > 0:
            price = preceding_flip.avg_entry_price_after
            if price is None:
                price = preceding_flip.fill_price
            entry_items.append(
                (opened, Decimal(str(price)), preceding_flip.occurred_at, preceding_flip.fill_order_id)
            )
            direction = "LONG" if preceding_flip.position_qty_after > 0 else "SHORT"

    for e in round_entries:
        if e.entry_type in ("OPEN", "INCREASE"):
            entry_items.append((abs(e.fill_qty), Decimal(str(e.fill_price)), e.occurred_at, e.fill_order_id))
            if direction is None:
                direction = "LONG" if e.fill_qty > 0 else "SHORT"

    exit_fills = [e for e in round_entries if e.entry_type in ("DECREASE", "CLOSE", "FLIP")]
    if not entry_items or not exit_fills:
        return None

    total_entry_qty = sum(q for q, _, _, _ in entry_items)
    total_exit_qty = sum(abs(e.fill_qty) for e in exit_fills)
    if total_entry_qty == 0 or total_exit_qty == 0:
        return None

    avg_entry = (
        sum(p * q for q, p, _, _ in entry_items) / total_entry_qty
    ).quantize(_PRICE_PRECISION, rounding=ROUND_HALF_UP)
    avg_exit = (
        sum(Decimal(str(e.fill_price)) * abs(e.fill_qty) for e in exit_fills) / total_exit_qty
    ).quantize(_PRICE_PRECISION, rounding=ROUND_HALF_UP)

    return {
        "direction": direction or "LONG",
        "total_quantity": total_entry_qty,
        "num_entries": len(entry_items),
        "num_exits": len(exit_fills),
        "avg_entry": avg_entry,
        "avg_exit": avg_exit,
        "total_pnl": sum(e.realized_pnl for e in exit_fills),
        "entry_time": min(t for _, _, t, _ in entry_items),
        "exit_time": max(e.occurred_at for e in exit_fills),
        "entry_trade_ids": [oid for _, _, _, oid in entry_items],
        "exit_trade_ids": [e.fill_order_id for e in exit_fills],
    }


def stable_completed_trade_id(
    broker_account_id,
    tradingsymbol,
    entry_time,
    direction: str,
    exit_time,
):
    """
    Deterministic CompletedTrade id for a flat-to-flat round.

    The SAME logic must be used by both the live ledger builder
    (build_completed_trade_on_close) and the batch FIFO builder
    (PnLCalculator._stable_ct_id), so that a batch recompute deletes and recreates
    a round with the *same* id. Otherwise the live round's random id churns at the
    first recompute — nulling alert/event `trigger_completed_trade_id`
    (ON DELETE SET NULL) and under-counting `behaviour-cost`. See deep-review M6/E2.
    """
    import uuid as _uuid
    entry_str = entry_time.isoformat() if entry_time else "none"
    exit_str = exit_time.isoformat() if exit_time else "none"
    key = f"{broker_account_id}|{tradingsymbol}|{entry_str}|{direction}|{exit_str}"
    return _uuid.uuid5(_uuid.NAMESPACE_URL, key)


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
