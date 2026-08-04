"""
S1: the batch matcher and the live ledger must split a partial exit identically.

`pnl_calculator` used to realize P&L against the oldest open lot (strict FIFO)
while `PositionLedger` charged it against the running weighted average. Over a
complete flat-to-flat round both produce the same total, so nothing on screen
disagreed — but per-fill `Trade.pnl`, and any window that cut a round in half,
did. The canonical case:

    BUY  3 @  9      weighted average 9.5
    BUY  3 @ 10
    SELL 3 @ 11      weighted average: (11 - 9.5) * 3 = 4.5   FIFO: (11 - 9) * 3 = 6
    SELL 3 @ 12      weighted average: (12 - 9.5) * 3 = 7.5   FIFO: (12 - 10) * 3 = 6
                                             total 12                      total 12

Weighted average is now the single convention, because Kite's positions payload
carries only aggregates and no fill sequence — the `realised` shown there cannot
be FIFO. These tests pin the split, the preserved round total, and the equality
of the two engines.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select

from app.models.completed_trade import CompletedTrade
from app.models.trade import Trade
from app.services.pnl_calculator import pnl_calculator
from app.services.position_ledger_service import (
    FillData,
    PositionLedgerService,
    _compute_fill_effect,
)

BASE = datetime(2026, 8, 4, 9, 15, tzinfo=timezone.utc)

# (side, qty, price) — the canonical partial-exit sequence from the docstring.
SEQUENCE = [
    ("BUY", 3, "9.00"),
    ("BUY", 3, "10.00"),
    ("SELL", 3, "11.00"),
    ("SELL", 3, "12.00"),
]


# =============================================================================
# Pure: the convention itself
# =============================================================================

class TestWeightedAverageConvention:

    def test_partial_exit_charges_the_average_not_the_oldest_lot(self):
        qty, avg = 0, None
        realized = []
        for side, q, price in SEQUENCE:
            signed = q if side == "BUY" else -q
            _, qty, avg, pnl = _compute_fill_effect(qty, avg, signed, Decimal(price))
            realized.append(pnl)

        assert realized[0] == Decimal("0")
        assert realized[1] == Decimal("0")
        assert realized[2] == Decimal("4.5000"), "FIFO would say 6 — the oldest lot at 9"
        assert realized[3] == Decimal("7.5000"), "FIFO would say 6 — the second lot at 10"
        assert sum(realized) == Decimal("12.0000"), "round total is identical either way"

    def test_partial_exit_leaves_the_remaining_cost_basis_alone(self):
        """The property FIFO does not have: selling half must not re-price the rest."""
        qty, avg = 0, None
        _, qty, avg, _ = _compute_fill_effect(qty, avg, 3, Decimal("9.00"))
        _, qty, avg, _ = _compute_fill_effect(qty, avg, 3, Decimal("10.00"))
        assert avg == Decimal("9.5000")

        etype, qty, avg, _ = _compute_fill_effect(qty, avg, -3, Decimal("11.00"))
        assert etype == "DECREASE"
        assert qty == 3
        assert avg == Decimal("9.5000"), "FIFO would leave the remaining lot priced at 10"


# =============================================================================
# The batch matcher, against the database
# =============================================================================

class TestBatchMatcherUsesWeightedAverage:

    async def _seed(self, db, broker, symbol):
        trades = []
        for i, (side, qty, price) in enumerate(SEQUENCE):
            t = Trade(
                broker_account_id=broker.id,
                order_id=f"ORD_{uuid4().hex[:10]}",
                tradingsymbol=symbol,
                exchange="NFO",
                transaction_type=side,
                order_type="MARKET",
                product="MIS",
                quantity=qty,
                filled_quantity=qty,
                average_price=Decimal(price),
                price=Decimal(price),
                status="COMPLETE",
                asset_class="DERIVATIVE",
                instrument_type="CE",
                product_type="MIS",
                order_timestamp=BASE + timedelta(minutes=i * 5),
            )
            db.add(t)
            trades.append(t)
        await db.flush()
        return trades

    async def test_per_fill_pnl_matches_the_average_not_fifo(self, db, broker):
        symbol = f"CONV_{uuid4().hex[:6]}"
        trades = await self._seed(db, broker, symbol)

        await pnl_calculator._process_symbol_trades(trades, db, broker.id)
        await db.flush()

        pnls = {}
        for t in trades:
            row = (await db.execute(
                select(Trade.transaction_type, Trade.pnl, Trade.average_price)
                .where(Trade.id == t.id)
            )).one()
            pnls[float(row.average_price)] = row.pnl

        assert pnls[9.00] is None, "an opening fill realizes nothing"
        assert pnls[10.00] is None
        assert float(pnls[11.00]) == 4.5, "FIFO would have written 6"
        assert float(pnls[12.00]) == 7.5, "FIFO would have written 6"

    async def test_round_total_is_unchanged_by_the_convention(self, db, broker):
        symbol = f"CONV_{uuid4().hex[:6]}"
        trades = await self._seed(db, broker, symbol)

        await pnl_calculator._process_symbol_trades(trades, db, broker.id)
        await db.flush()

        ct = (await db.execute(
            select(CompletedTrade).where(
                CompletedTrade.broker_account_id == broker.id,
                CompletedTrade.tradingsymbol == symbol,
            )
        )).scalar_one()

        assert float(ct.realized_pnl) == 12.0
        assert ct.direction == "LONG"
        assert ct.total_quantity == 6
        assert float(ct.avg_entry_price) == 9.5
        assert float(ct.avg_exit_price) == 11.5

    async def test_flip_still_closes_the_round(self, db, broker):
        """Round structure is still FIFO-driven; the cost change must not break it."""
        symbol = f"FLIPC_{uuid4().hex[:6]}"
        seq = [("BUY", 5, "100.00"), ("SELL", 8, "110.00")]
        trades = []
        for i, (side, qty, price) in enumerate(seq):
            t = Trade(
                broker_account_id=broker.id,
                order_id=f"ORD_{uuid4().hex[:10]}",
                tradingsymbol=symbol, exchange="NFO",
                transaction_type=side, order_type="MARKET", product="MIS",
                quantity=qty, filled_quantity=qty,
                average_price=Decimal(price), price=Decimal(price),
                status="COMPLETE", asset_class="DERIVATIVE",
                instrument_type="CE", product_type="MIS",
                order_timestamp=BASE + timedelta(minutes=i * 5),
            )
            db.add(t)
            trades.append(t)
        await db.flush()

        await pnl_calculator._process_symbol_trades(trades, db, broker.id)
        await db.flush()

        ct = (await db.execute(
            select(CompletedTrade).where(
                CompletedTrade.broker_account_id == broker.id,
                CompletedTrade.tradingsymbol == symbol,
            )
        )).scalar_one()
        assert ct.closed_by_flip is True
        assert float(ct.realized_pnl) == 50.0     # (110 - 100) * 5


# =============================================================================
# The point of S1: both engines, same fills, same answer
# =============================================================================

class TestBothEnginesAgree:

    async def test_ledger_and_batch_split_a_partial_exit_identically(self, db, broker):
        symbol = f"AGREE_{uuid4().hex[:6]}"

        # Live path: the same fills through the ledger.
        ledger_realized = []
        for i, (side, qty, price) in enumerate(SEQUENCE):
            signed = qty if side == "BUY" else -qty
            entry, _ = await PositionLedgerService.apply_fill(
                FillData(
                    broker_account_id=broker.id,
                    tradingsymbol=symbol, exchange="NFO",
                    fill_order_id=f"L_{uuid4().hex[:8]}",
                    fill_qty=signed, fill_price=Decimal(price),
                    occurred_at=BASE + timedelta(minutes=i * 5),
                    idempotency_key=f"{uuid4().hex}:ledger",
                    product="MIS",
                ),
                db,
            )
            ledger_realized.append(Decimal(str(entry.realized_pnl or 0)))
        await db.flush()

        # Batch path: same fills, a different symbol so the two do not interfere.
        batch_symbol = f"{symbol}B"
        trades = []
        for i, (side, qty, price) in enumerate(SEQUENCE):
            t = Trade(
                broker_account_id=broker.id,
                order_id=f"ORD_{uuid4().hex[:10]}",
                tradingsymbol=batch_symbol, exchange="NFO",
                transaction_type=side, order_type="MARKET", product="MIS",
                quantity=qty, filled_quantity=qty,
                average_price=Decimal(price), price=Decimal(price),
                status="COMPLETE", asset_class="DERIVATIVE",
                instrument_type="CE", product_type="MIS",
                order_timestamp=BASE + timedelta(minutes=i * 5),
            )
            db.add(t)
            trades.append(t)
        await db.flush()

        await pnl_calculator._process_symbol_trades(trades, db, broker.id)
        await db.flush()

        batch_realized = []
        for t in trades:
            pnl = (await db.execute(select(Trade.pnl).where(Trade.id == t.id))).scalar_one()
            batch_realized.append(Decimal(str(pnl or 0)))

        assert batch_realized == ledger_realized, (
            "the batch matcher and the live ledger must charge a partial exit "
            f"the same way — batch={batch_realized} ledger={ledger_realized}"
        )
