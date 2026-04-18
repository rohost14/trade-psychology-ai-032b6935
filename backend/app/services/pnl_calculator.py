"""
P&L Calculator Service

Calculates realized P&L by matching BUY and SELL trades using FIFO.
Creates CompletedTrade records for flat-to-flat position lifecycles.
Detects incomplete positions (sync gaps).
Computes ML features post-FIFO in a separate pass.

DATA PIPELINE ONLY — this service NEVER emits behavioral signals.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Dict, Tuple, Optional
from uuid import UUID
import uuid as uuid_module
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update, delete
import logging

from app.models.trade import Trade
from app.models.position import Position
from app.models.instrument import Instrument
from app.models.completed_trade import CompletedTrade
from app.models.completed_trade_feature import CompletedTradeFeature
from app.models.incomplete_position import IncompletePosition
from app.core.market_hours import market_minutes
from app.services.mcx_contract_specs import get_lot_multiplier
from app.services.position_ledger_service import _compute_pnl_pct

logger = logging.getLogger(__name__)

# Exchanges that use lot sizes for P&L calculation
F_AND_O_EXCHANGES = {"NFO", "BFO", "MCX", "CDS"}

# IST offset for feature computation (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))


class PnLCalculator:
    """
    Calculates P&L for trades by matching BUY/SELL pairs using FIFO.

    Creates CompletedTrade records using flat-to-flat semantics:
    - A round starts when the first fill opens a position
    - Partial exits accumulate in the same round
    - A round closes ONLY when the position goes to zero
    - Direction flips close the current round and start a new one

    FIFO determines structure only (rounds, direction, timing, entry/exit fills).
    P&L values are overwritten post-sync by _reconcile_pnl_with_zerodha() which
    uses Zerodha's authoritative 'realised' field — the only correct source for
    all exchanges including MCX where the instruments CSV lot_size ≠ contract multiplier.
    """

    # Cache for lot sizes (used for position sizing alerts only, NOT for P&L)
    _lot_size_cache: Dict[str, int] = {}

    async def get_lot_size(
        self,
        tradingsymbol: str,
        exchange: str,
        db: AsyncSession
    ) -> int:
        """
        Get lot size for an instrument.
        Kept for position sizing alerts — NOT used in P&L calculation.
        """
        if exchange not in F_AND_O_EXCHANGES:
            return 1

        cache_key = f"{exchange}:{tradingsymbol}"
        if cache_key in self._lot_size_cache:
            return self._lot_size_cache[cache_key]

        result = await db.execute(
            select(Instrument.lot_size).where(
                and_(
                    Instrument.tradingsymbol == tradingsymbol,
                    Instrument.exchange == exchange
                )
            )
        )
        lot_size = result.scalar_one_or_none()

        if lot_size is None:
            logger.warning(f"Lot size not found for {tradingsymbol} on {exchange}, defaulting to 1")
            lot_size = 1

        self._lot_size_cache[cache_key] = lot_size
        return lot_size

    def clear_lot_size_cache(self):
        """Clear the lot size cache. Call after refreshing instruments."""
        self._lot_size_cache.clear()

    # ------------------------------------------------------------------
    # BATCH FIFO — main entry point for sync pipeline
    # ------------------------------------------------------------------

    async def calculate_and_update_pnl(
        self,
        broker_account_id: UUID,
        db: AsyncSession,
        symbol: Optional[str] = None,
        days_back: int = 30
    ) -> Dict[str, any]:
        """
        Calculate P&L for all trades, create CompletedTrade records,
        detect incomplete positions, and compute ML features.

        Idempotent: deletes and recreates CompletedTrades within the
        recompute window (days_back). Historical data outside the window
        is NEVER touched.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)

        # --- Query trades ---
        query = select(Trade).where(
            and_(
                Trade.broker_account_id == broker_account_id,
                Trade.status == "COMPLETE",
                Trade.order_timestamp >= cutoff
            )
        )
        if symbol:
            query = query.where(Trade.tradingsymbol == symbol)
        query = query.order_by(Trade.order_timestamp.asc())

        result = await db.execute(query)
        trades = result.scalars().all()

        if not trades:
            return {"processed": 0, "updated": 0, "total_pnl": 0,
                    "completed_trades": 0, "symbols_processed": 0}

        # --- Group trades by symbol ---
        trades_by_symbol: Dict[str, List[Trade]] = {}
        for trade in trades:
            key = f"{trade.tradingsymbol}|{trade.exchange}"
            trades_by_symbol.setdefault(key, []).append(trade)

        # --- Step 3.3: Timestamp-bounded idempotent deletion ---
        # Delete CompletedTrades within recompute window only
        # Features cascade-delete via ON DELETE CASCADE
        await db.execute(
            delete(CompletedTrade).where(
                and_(
                    CompletedTrade.broker_account_id == broker_account_id,
                    CompletedTrade.exit_time >= cutoff,
                )
            )
        )

        # Clear IncompletePositions for symbols being reprocessed
        # (they'll be re-detected if still applicable)
        for symbol_key in trades_by_symbol:
            sym, exch = symbol_key.split("|", 1)
            await db.execute(
                delete(IncompletePosition).where(
                    and_(
                        IncompletePosition.broker_account_id == broker_account_id,
                        IncompletePosition.tradingsymbol == sym,
                        IncompletePosition.exchange == exch,
                    )
                )
            )

        # --- Run FIFO for each symbol ---
        total_updated = 0
        total_pnl = Decimal("0")
        total_completed = 0

        for symbol_key, symbol_trades in trades_by_symbol.items():
            updated, pnl, completed_count = await self._process_symbol_trades(
                symbol_trades, db, broker_account_id
            )
            total_updated += updated
            total_pnl += pnl
            total_completed += completed_count

        # --- Step 3.5: Feature computation (post-FIFO, separate pass) ---
        features_computed = await self._compute_features_for_new_rounds(
            broker_account_id, db, cutoff
        )

        await db.commit()

        logger.info(
            f"P&L calculation complete: {total_updated} trades updated, "
            f"{total_completed} completed rounds, {features_computed} features, "
            f"total P&L: {total_pnl}"
        )

        return {
            "processed": len(trades),
            "updated": total_updated,
            "total_pnl": float(total_pnl),
            "symbols_processed": len(trades_by_symbol),
            "completed_trades": total_completed,
            "features_computed": features_computed,
        }

    # ------------------------------------------------------------------
    # FIFO MATCHER — flat-to-flat round accumulator
    # ------------------------------------------------------------------

    async def _process_symbol_trades(
        self,
        trades: List[Trade],
        db: AsyncSession,
        broker_account_id: UUID = None
    ) -> Tuple[int, Decimal, int]:
        """
        Process trades for a single symbol using FIFO matching with
        flat-to-flat round accumulator.

        Creates CompletedTrade when opening_queue empties (position flat).
        Handles direction flips (closed_by_flip = True).
        Detects incomplete positions post-FIFO.

        Returns:
            Tuple of (trades_updated, total_pnl, completed_trades_count)
        """
        sorted_trades = sorted(
            trades, key=lambda t: t.order_timestamp or datetime.min
        )

        opening_queue: List[Dict] = []
        updated_count = 0
        total_pnl = Decimal("0")
        completed_count = 0

        # Round accumulator for flat-to-flat semantics
        round_acc = self._new_round_acc()

        # Lot multiplier: how many price-quotation units are in 1 filled lot.
        #
        # NSE/BSE/NFO/BFO: Kite already expands quantity to total units
        #   (e.g. 1 NIFTY lot → qty=50 in the fill).  Multiplier = 1.
        #
        # MCX/CDS: Kite sends quantity in LOTS (qty=1 for 1 CRUDEOIL lot = 100 bbl).
        #   Zerodha instruments CSV has lot_size=1 for ALL MCX instruments — it is
        #   the minimum order quantity, not the contract size.
        #   We use our own authoritative table in mcx_contract_specs.py.
        #   Ref: https://kite.trade/forum/discussion/14531/
        ref_exchange = (sorted_trades[0].exchange or "") if sorted_trades else ""
        ref_symbol   = (sorted_trades[0].tradingsymbol or "") if sorted_trades else ""
        lot_multiplier = Decimal(str(get_lot_multiplier(ref_exchange, ref_symbol)))

        for trade in sorted_trades:
            qty = trade.filled_quantity or trade.quantity or 0
            price = float(trade.average_price or trade.price or 0)
            side = trade.transaction_type  # "BUY" or "SELL"
            ts = trade.order_timestamp or trade.fill_timestamp

            if qty <= 0 or price <= 0:
                continue

            # --- Opening fill: same side as queue head, or queue empty ---
            if not opening_queue or side == opening_queue[0]["side"]:
                opening_queue.append({
                    "trade": trade,
                    "remaining_qty": qty,
                    "price": price,
                    "side": side,
                })
                round_acc["entry_fills"].append({
                    "trade_id": trade.id,
                    "qty": qty,
                    "price": price,
                    "timestamp": ts,
                    "product": trade.product,
                    "instrument_type": trade.instrument_type,
                })
                if round_acc["direction"] is None:
                    round_acc["direction"] = "LONG" if side == "BUY" else "SHORT"
                continue

            # --- Closing fill: opposite side to queue head ---
            trade_pnl = Decimal("0")
            remaining_close_qty = qty

            while remaining_close_qty > 0 and opening_queue:
                opening = opening_queue[0]
                match_qty = min(opening["remaining_qty"], remaining_close_qty)

                # P&L = price_diff * qty * lot_multiplier
                # For NSE/BSE F&O: lot_multiplier = 1 (Kite sends units already)
                # For MCX/CDS: lot_multiplier = lot_size (Kite sends lots, not units)
                if opening["side"] == "BUY":
                    match_pnl = Decimal(str((price - opening["price"]) * match_qty)) * lot_multiplier
                else:
                    match_pnl = Decimal(str((opening["price"] - price) * match_qty)) * lot_multiplier

                trade_pnl += match_pnl
                opening["remaining_qty"] -= match_qty
                remaining_close_qty -= match_qty

                if opening["remaining_qty"] <= 0:
                    opening_queue.pop(0)

            # Track matched portion as exit fill
            matched_qty = qty - remaining_close_qty
            if matched_qty > 0:
                round_acc["exit_fills"].append({
                    "trade_id": trade.id,
                    "qty_matched": matched_qty,
                    "price": price,
                    "timestamp": ts,
                })
                round_acc["total_pnl"] += trade_pnl

                # Backward compat: assign P&L to closing fill in trades table
                await db.execute(
                    update(Trade)
                    .where(Trade.id == trade.id)
                    .values(pnl=float(trade_pnl))
                )
                updated_count += 1
                total_pnl += trade_pnl

                logger.debug(
                    f"Trade {trade.order_id}: matched {matched_qty} qty, "
                    f"P&L: {trade_pnl}"
                )

            # --- Check if position went flat ---
            if not opening_queue:
                is_flip = remaining_close_qty > 0
                ct = self._build_completed_trade(
                    round_acc, sorted_trades[0], broker_account_id, is_flip
                )
                if ct:
                    db.add(ct)
                    completed_count += 1
                    logger.debug(
                        f"CompletedTrade: {ct.direction} {ct.tradingsymbol} "
                        f"qty={ct.total_quantity} pnl={ct.realized_pnl} "
                        f"flip={is_flip}"
                    )

                # Reset for next round
                round_acc = self._new_round_acc()

                # Direction flip: excess qty starts a new round
                if remaining_close_qty > 0:
                    opening_queue.append({
                        "trade": trade,
                        "remaining_qty": remaining_close_qty,
                        "price": price,
                        "side": side,
                    })
                    round_acc["entry_fills"].append({
                        "trade_id": trade.id,
                        "qty": remaining_close_qty,
                        "price": price,
                        "timestamp": ts,
                        "product": trade.product,
                        "instrument_type": trade.instrument_type,
                    })
                    round_acc["direction"] = "LONG" if side == "BUY" else "SHORT"

        # --- Post-FIFO: incomplete position detection ---
        if opening_queue and broker_account_id:
            await self._detect_incomplete_position(
                opening_queue, sorted_trades[0], broker_account_id, db
            )

        return updated_count, total_pnl, completed_count

    # ------------------------------------------------------------------
    # Round accumulator helpers
    # ------------------------------------------------------------------

    def _new_round_acc(self) -> Dict:
        """Create a fresh round accumulator."""
        return {
            "entry_fills": [],   # [{trade_id, qty, price, timestamp, product, instrument_type}]
            "exit_fills": [],    # [{trade_id, qty_matched, price, timestamp}]
            "direction": None,   # LONG or SHORT
            "total_pnl": Decimal("0"),
        }

    @staticmethod
    def _stable_ct_id(
        broker_account_id: UUID,
        tradingsymbol: str,
        entry_time,
        direction: str,
        exit_time,
    ) -> uuid_module.UUID:
        """
        Generate a deterministic UUID for a CompletedTrade round.

        Same round (same broker, symbol, entry time, direction, exit time) always
        produces the same UUID — so journal trade_id FK links survive re-syncs
        that delete and recreate CompletedTrade rows.
        """
        entry_str = entry_time.isoformat() if entry_time else "none"
        exit_str = exit_time.isoformat() if exit_time else "none"
        key = f"{broker_account_id}|{tradingsymbol}|{entry_str}|{direction}|{exit_str}"
        return uuid_module.uuid5(uuid_module.NAMESPACE_URL, key)

    def _build_completed_trade(
        self,
        round_acc: Dict,
        ref_trade: Trade,
        broker_account_id: UUID,
        closed_by_flip: bool
    ) -> Optional[CompletedTrade]:
        """Build a CompletedTrade record from the round accumulator."""
        entry_fills = round_acc["entry_fills"]
        exit_fills = round_acc["exit_fills"]

        if not entry_fills or not exit_fills:
            return None

        total_entry_qty = sum(f["qty"] for f in entry_fills)
        total_exit_qty = sum(f["qty_matched"] for f in exit_fills)

        if total_entry_qty == 0 or total_exit_qty == 0:
            return None

        # Weighted average prices
        avg_entry = (
            sum(f["price"] * f["qty"] for f in entry_fills) / total_entry_qty
        )
        avg_exit = (
            sum(f["price"] * f["qty_matched"] for f in exit_fills) / total_exit_qty
        )

        # Timestamps (filter out None)
        entry_times = [f["timestamp"] for f in entry_fills if f["timestamp"]]
        exit_times = [f["timestamp"] for f in exit_fills if f["timestamp"]]
        entry_time = min(entry_times) if entry_times else None
        exit_time = max(exit_times) if exit_times else None

        duration = 0
        if entry_time and exit_time:
            # Market-hours duration: strips overnight gaps, weekends, holidays
            # so a 4-day NRML hold reports actual exposure (~1,500 min), not wall-clock (~5,760 min)
            duration = market_minutes(entry_time, exit_time, exchange=ref_trade.exchange or "NFO")

        # Stable UUID: same round always gets same ID so journal FKs survive re-syncs
        ct_id = self._stable_ct_id(
            broker_account_id,
            ref_trade.tradingsymbol,
            entry_time,
            round_acc["direction"],
            exit_time,
        )

        return CompletedTrade(
            id=ct_id,
            broker_account_id=broker_account_id,
            tradingsymbol=ref_trade.tradingsymbol,
            exchange=ref_trade.exchange,
            instrument_type=entry_fills[0].get("instrument_type"),
            product=entry_fills[0].get("product"),
            direction=round_acc["direction"],
            total_quantity=total_entry_qty,
            num_entries=len(entry_fills),
            num_exits=len(exit_fills),
            avg_entry_price=round(avg_entry, 4),
            avg_exit_price=round(avg_exit, 4),
            realized_pnl=float(round_acc["total_pnl"]),
            pnl_pct=_compute_pnl_pct(round(avg_entry, 4), round(avg_exit, 4), round_acc["direction"] or "LONG"),
            entry_time=entry_time,
            exit_time=exit_time,
            duration_minutes=duration,
            closed_by_flip=closed_by_flip,
            entry_trade_ids=[str(f["trade_id"]) for f in entry_fills],
            exit_trade_ids=[str(f["trade_id"]) for f in exit_fills],
            status="closed",
        )

    # ------------------------------------------------------------------
    # Step 3.4: Incomplete position detection
    # ------------------------------------------------------------------

    async def _detect_incomplete_position(
        self,
        opening_queue: List[Dict],
        ref_trade: Trade,
        broker_account_id: UUID,
        db: AsyncSession
    ) -> None:
        """
        After FIFO, if opening_queue is non-empty but broker says position
        is flat, flag as a sync gap (IncompletePosition).
        """
        symbol = ref_trade.tradingsymbol
        exchange = ref_trade.exchange

        pos_result = await db.execute(
            select(Position).where(
                and_(
                    Position.broker_account_id == broker_account_id,
                    Position.tradingsymbol == symbol,
                    Position.exchange == exchange,
                    Position.total_quantity == 0,
                )
            )
        )
        closed_position = pos_result.scalar_one_or_none()

        if not closed_position:
            # Position is still open according to broker — no gap
            return

        # Gap: we have unmatched opening fills but broker says flat
        unmatched_qty = sum(o["remaining_qty"] for o in opening_queue)
        avg_price = (
            sum(o["price"] * o["remaining_qty"] for o in opening_queue)
            / unmatched_qty
        )
        timestamps = [
            o["trade"].order_timestamp or o["trade"].fill_timestamp
            for o in opening_queue
            if o.get("trade")
        ]
        earliest = min(t for t in timestamps if t) if timestamps else None
        direction = "LONG" if opening_queue[0]["side"] == "BUY" else "SHORT"

        incomplete = IncompletePosition(
            broker_account_id=broker_account_id,
            tradingsymbol=symbol,
            exchange=exchange,
            product=opening_queue[0]["trade"].product if opening_queue[0].get("trade") else None,
            direction=direction,
            unmatched_quantity=unmatched_qty,
            avg_entry_price=round(avg_price, 4),
            entry_time=earliest,
            reason="SYNC_GAP",
            details=(
                f"Broker shows flat but {unmatched_qty} units of "
                f"{direction} fills are unmatched"
            ),
        )
        db.add(incomplete)
        logger.warning(
            f"Incomplete position detected: {symbol} {exchange} — "
            f"{unmatched_qty} {direction} units unmatched"
        )

    # ------------------------------------------------------------------
    # Step 3.5: Feature computation (post-FIFO, separate pass)
    # ------------------------------------------------------------------

    async def _compute_features_for_new_rounds(
        self,
        broker_account_id: UUID,
        db: AsyncSession,
        cutoff: datetime
    ) -> int:
        """
        Compute ML features for completed_trades that don't yet have features.

        Runs AFTER all FIFO processing is done. Reads completed_trades,
        writes completed_trade_features. Does NOT touch trades, positions,
        or P&L. Stateless and rebuildable.
        """
        # Get completed trades without features (within recompute window)
        result = await db.execute(
            select(CompletedTrade)
            .outerjoin(
                CompletedTradeFeature,
                CompletedTradeFeature.completed_trade_id == CompletedTrade.id
            )
            .where(
                and_(
                    CompletedTrade.broker_account_id == broker_account_id,
                    CompletedTrade.exit_time >= cutoff,
                    CompletedTradeFeature.id == None,
                )
            )
            .order_by(CompletedTrade.exit_time.asc())
        )
        new_rounds = result.scalars().all()

        if not new_rounds:
            return 0

        # Load recent completed trades for context (for relative sizing,
        # consecutive losses, session P&L, gap detection)
        context_result = await db.execute(
            select(CompletedTrade)
            .where(CompletedTrade.broker_account_id == broker_account_id)
            .order_by(CompletedTrade.exit_time.desc())
            .limit(50)
        )
        all_recent = list(reversed(context_result.scalars().all()))

        for ct in new_rounds:
            # Rounds that completed BEFORE this round started
            prev_rounds = [
                r for r in all_recent
                if r.exit_time and ct.entry_time and r.exit_time < ct.entry_time
            ]

            feature = self._build_feature(ct, prev_rounds, broker_account_id)
            db.add(feature)

        logger.info(f"Computed features for {len(new_rounds)} completed trades")
        return len(new_rounds)

    def _build_feature(
        self,
        ct: CompletedTrade,
        prev_rounds: List[CompletedTrade],
        broker_account_id: UUID
    ) -> CompletedTradeFeature:
        """Build a single CompletedTradeFeature from a CompletedTrade and context."""

        # --- Timing features ---
        entry_ist = ct.entry_time.astimezone(IST) if ct.entry_time else None
        exit_ist = ct.exit_time.astimezone(IST) if ct.exit_time else None

        entry_hour = entry_ist.hour if entry_ist else None
        exit_hour = exit_ist.hour if exit_ist else None
        entry_dow = entry_ist.weekday() if entry_ist else None  # 0=Mon
        # Thursday = weekly F&O expiry day in India
        is_expiry = exit_ist.weekday() == 3 if exit_ist else False

        # --- Sizing features ---
        recent_20 = prev_rounds[-20:]
        if recent_20:
            avg_qty = sum(r.total_quantity or 0 for r in recent_20) / len(recent_20)
        else:
            avg_qty = ct.total_quantity or 1
        size_rel = (ct.total_quantity or 0) / avg_qty if avg_qty > 0 else 1.0

        # --- Context features ---
        last_round = prev_rounds[-1] if prev_rounds else None
        entry_after_loss = bool(
            last_round and float(last_round.realized_pnl or 0) < 0
        )

        consecutive_losses = 0
        for r in reversed(prev_rounds):
            if float(r.realized_pnl or 0) < 0:
                consecutive_losses += 1
            else:
                break

        # Session P&L at entry (realized P&L from same session before this round)
        session_pnl = Decimal("0")
        if entry_ist:
            try:
                from app.core.market_hours import get_session_boundaries
                sess_start, sess_end = get_session_boundaries(
                    for_date=entry_ist.date()
                )
                session_pnl = sum(
                    Decimal(str(r.realized_pnl or 0))
                    for r in prev_rounds
                    if r.exit_time and sess_start <= r.exit_time <= sess_end
                )
            except Exception:
                session_pnl = Decimal("0")

        # Gap from previous round
        minutes_since = None
        if last_round and last_round.exit_time and ct.entry_time:
            delta = ct.entry_time - last_round.exit_time
            minutes_since = max(0, int(delta.total_seconds() / 60))

        # --- Outcome features ---
        is_winner = float(ct.realized_pnl or 0) > 0
        pnl_per_unit = (
            float(ct.realized_pnl or 0) / (ct.total_quantity or 1)
        )

        return CompletedTradeFeature(
            completed_trade_id=ct.id,
            broker_account_id=broker_account_id,
            holding_duration_minutes=ct.duration_minutes,
            entry_hour_ist=entry_hour,
            exit_hour_ist=exit_hour,
            entry_day_of_week=entry_dow,
            is_expiry_day=is_expiry,
            size_relative_to_avg=round(size_rel, 4),
            is_scaled_entry=(ct.num_entries or 1) > 1,
            is_scaled_exit=(ct.num_exits or 1) > 1,
            entry_after_loss=entry_after_loss,
            consecutive_loss_count=consecutive_losses,
            session_pnl_at_entry=float(session_pnl),
            minutes_since_last_round=minutes_since,
            is_winner=is_winner,
            pnl_per_unit=round(pnl_per_unit, 4),
        )

    # ------------------------------------------------------------------
    # REALTIME P&L — for webhook single-trade calculation
    # ------------------------------------------------------------------

    async def calculate_trade_pnl_realtime(
        self,
        trade: Trade,
        db: AsyncSession
    ) -> Optional[Decimal]:
        """
        Calculate P&L for a single trade in real-time (webhook flow).
        Replays prior trades to build opening queue, then matches.

        Does NOT create CompletedTrades — that happens in batch FIFO.
        """
        trade_qty = trade.filled_quantity or trade.quantity or 0
        trade_price = float(trade.average_price or trade.price or 0)

        if trade.transaction_type == "SELL":
            opposite_side = "BUY"
        else:
            opposite_side = "SELL"

        # Find all completed trades for this symbol before this trade
        result = await db.execute(
            select(Trade).where(
                and_(
                    Trade.broker_account_id == trade.broker_account_id,
                    Trade.tradingsymbol == trade.tradingsymbol,
                    Trade.exchange == trade.exchange,
                    Trade.status == "COMPLETE",
                    Trade.order_timestamp < trade.order_timestamp
                )
            ).order_by(Trade.order_timestamp.asc())
        )
        prior_trades = result.scalars().all()

        if not prior_trades:
            return None  # First trade for this symbol, must be opening

        # Replay prior trades to find the current open position
        opening_queue: List[Dict] = []
        for pt in prior_trades:
            pt_qty = pt.filled_quantity or pt.quantity or 0
            pt_price = float(pt.average_price or pt.price or 0)
            pt_side = pt.transaction_type

            if pt_qty <= 0:
                continue

            if not opening_queue or pt_side == opening_queue[0]["side"]:
                opening_queue.append({
                    "remaining_qty": pt_qty, "price": pt_price, "side": pt_side
                })
            else:
                remaining = pt_qty
                while remaining > 0 and opening_queue:
                    match_qty = min(opening_queue[0]["remaining_qty"], remaining)
                    opening_queue[0]["remaining_qty"] -= match_qty
                    remaining -= match_qty
                    if opening_queue[0]["remaining_qty"] <= 0:
                        opening_queue.pop(0)
                if remaining > 0:
                    opening_queue.append({
                        "remaining_qty": remaining, "price": pt_price, "side": pt_side
                    })

        # Check if the current trade is closing (opposite to queue head)
        if not opening_queue or trade.transaction_type == opening_queue[0]["side"]:
            return None  # Opening trade, no P&L

        # Closing trade — match against the opening queue
        total_pnl = Decimal("0")
        remaining_close_qty = trade_qty

        while remaining_close_qty > 0 and opening_queue:
            opening = opening_queue[0]
            match_qty = min(opening["remaining_qty"], remaining_close_qty)

            if opening["side"] == "BUY":
                match_pnl = Decimal(str((trade_price - opening["price"]) * match_qty))
            else:
                match_pnl = Decimal(str((opening["price"] - trade_price) * match_qty))

            total_pnl += match_pnl
            opening["remaining_qty"] -= match_qty
            remaining_close_qty -= match_qty

            if opening["remaining_qty"] <= 0:
                opening_queue.pop(0)

        return total_pnl if (trade_qty - remaining_close_qty) > 0 else None

    # ------------------------------------------------------------------
    # UNREALIZED P&L — for open positions
    # ------------------------------------------------------------------

    async def get_unrealized_pnl(
        self,
        broker_account_id: UUID,
        db: AsyncSession
    ) -> Dict[str, Decimal]:
        """Calculate unrealized P&L for open positions."""
        result = await db.execute(
            select(Position).where(
                and_(
                    Position.broker_account_id == broker_account_id,
                    Position.total_quantity != 0
                )
            )
        )
        positions = result.scalars().all()

        unrealized = {}

        for pos in positions:
            if pos.last_price and pos.average_entry_price:
                qty = pos.total_quantity or 0
                entry = float(pos.average_entry_price)
                current = float(pos.last_price)

                # Kite qty is already in units — no multiplier needed
                if qty > 0:  # Long position
                    pnl = (current - entry) * qty
                else:  # Short position
                    pnl = (entry - current) * abs(qty)

                unrealized[pos.tradingsymbol] = Decimal(str(pnl))

        return unrealized


# Singleton instance
pnl_calculator = PnLCalculator()
