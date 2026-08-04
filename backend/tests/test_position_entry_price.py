"""
Open-position entry price must be the cost of the CURRENT round, not Kite's
day-cumulative average.

Kite's `average_price` on the net-positions payload is buy_value / buy_quantity
over the whole day. After a round-trip and a re-entry in the same contract it
still blends the lots that were already closed:

    BUY  1 lot @ 9.00
    SELL 1 lot @ 8.85     <- flat
    BUY  3 lots @ 9.41    <- new round

Kite reports (9.00*1 + 9.41*3) / 4 = 9.3075 for a position that actually cost
9.41. Every unrealized-P&L consumer multiplies that gap by the open quantity.

PositionLedger already resets its running average on CLOSE, so the correct number
exists; these tests pin the ledger's behaviour and the rules that decide when to
trust it over the broker.

The first two classes are pure (no DB). TestApplyLedgerEntryPrices needs Postgres,
like the other DB-backed suites in this directory.
"""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select

from app.models.position import Position
from app.services.position_ledger_service import (
    LedgerPositionState,
    PositionLedgerService,
    _compute_fill_effect,
)
from app.services.trade_sync_service import TradeSyncService, resolve_entry_price


def _state(qty, avg, round_started_at=None, last_entry_type="OPEN"):
    return LedgerPositionState(
        tradingsymbol="MAXHEALTH26AUG1200CE",
        exchange="NFO",
        product="MIS",
        qty=qty,
        avg_entry_price=(Decimal(str(avg)) if avg is not None else None),
        round_started_at=round_started_at,
        last_entry_type=last_entry_type,
    )


# =============================================================================
# The ledger's own arithmetic — the reported scenario, end to end
# =============================================================================

class TestLedgerResetsAverageOnClose:

    def test_reopen_after_round_trip_uses_new_price_not_blend(self):
        """buy 1 @9.00, sell 1 @8.85, buy 3 @9.41  ->  open average 9.41."""
        qty, avg = 0, None

        etype, qty, avg, pnl = _compute_fill_effect(qty, avg, 1, Decimal("9.00"))
        assert etype == "OPEN" and avg == Decimal("9.00")

        etype, qty, avg, pnl = _compute_fill_effect(qty, avg, -1, Decimal("8.85"))
        assert etype == "CLOSE"
        assert qty == 0
        assert avg is None, "a closed round must not leave its cost behind"
        assert pnl == Decimal("-0.1500")

        etype, qty, avg, pnl = _compute_fill_effect(qty, avg, 3, Decimal("9.41"))
        assert etype == "OPEN"
        assert qty == 3
        assert avg == Decimal("9.41"), "must be the new leg, not Kite's 9.3075 blend"

        # What Kite would report for the same day, for contrast.
        kite_blend = (Decimal("9.00") * 1 + Decimal("9.41") * 3) / 4
        assert kite_blend == Decimal("9.3075")

    def test_short_side_mirrors(self):
        """sell 1 @9.00, buy 1 @9.15, sell 3 @8.60  ->  open average 8.60."""
        qty, avg = 0, None
        _, qty, avg, _ = _compute_fill_effect(qty, avg, -1, Decimal("9.00"))
        etype, qty, avg, _ = _compute_fill_effect(qty, avg, 1, Decimal("9.15"))
        assert etype == "CLOSE" and avg is None
        etype, qty, avg, _ = _compute_fill_effect(qty, avg, -3, Decimal("8.60"))
        assert etype == "OPEN" and qty == -3 and avg == Decimal("8.60")

    def test_plain_average_up_is_unchanged(self):
        """No prior round: ledger and broker agree. Guards against a regression."""
        qty, avg = 0, None
        _, qty, avg, _ = _compute_fill_effect(qty, avg, 1, Decimal("9.00"))
        etype, qty, avg, _ = _compute_fill_effect(qty, avg, 3, Decimal("9.41"))
        assert etype == "INCREASE"
        assert avg == Decimal("9.3075")  # same figure Kite reports


# =============================================================================
# When to trust the ledger over the broker (pure)
# =============================================================================

class TestResolveEntryPrice:

    def test_ledger_wins_when_quantities_agree(self):
        avg, source, first_entry, mismatch = resolve_entry_price(
            broker_avg=9.3075, broker_qty=3,
            ledger_state=_state(3, "9.41"), stored_first_entry_time=None,
        )
        assert avg == 9.41
        assert source == "ledger"
        assert mismatch is False

    def test_no_ledger_history_falls_back_without_flagging(self):
        """Overnight carry from before the ledger existed. Expected, not a defect."""
        avg, source, _, mismatch = resolve_entry_price(
            broker_avg=9.3075, broker_qty=3,
            ledger_state=None, stored_first_entry_time=None,
        )
        assert avg == 9.3075
        assert source == "broker"
        assert mismatch is False

    def test_quantity_disagreement_falls_back_and_flags(self):
        """A missing fill makes the ledger's price confidently wrong — don't use it."""
        avg, source, _, mismatch = resolve_entry_price(
            broker_avg=9.3075, broker_qty=3,
            ledger_state=_state(-1, "8.60"), stored_first_entry_time=None,
        )
        assert avg == 9.3075
        assert source == "broker"
        assert mismatch is True

    def test_null_ledger_average_falls_back(self):
        avg, source, _, mismatch = resolve_entry_price(
            broker_avg=9.3075, broker_qty=3,
            ledger_state=_state(3, None), stored_first_entry_time=None,
        )
        assert source == "broker"
        assert mismatch is False

    def test_first_entry_time_moves_forward_to_current_round(self):
        opened_at = datetime(2026, 8, 4, 9, 41, tzinfo=timezone.utc)
        stale = datetime(2026, 8, 4, 9, 15, tzinfo=timezone.utc)
        _, _, first_entry, _ = resolve_entry_price(
            broker_avg=9.3075, broker_qty=3,
            ledger_state=_state(3, "9.41", round_started_at=opened_at),
            stored_first_entry_time=stale,
        )
        assert first_entry == opened_at, "hold duration must not count the closed leg"

    def test_first_entry_time_never_moves_backward(self):
        opened_at = datetime(2026, 8, 4, 9, 41, tzinfo=timezone.utc)
        _, _, first_entry, _ = resolve_entry_price(
            broker_avg=9.41, broker_qty=3,
            ledger_state=_state(3, "9.41", round_started_at=opened_at),
            stored_first_entry_time=opened_at,
        )
        assert first_entry is None

    def test_naive_stored_timestamp_is_read_as_ist(self):
        """Zerodha sends IST without a tzinfo; a naive compare would be 5h30m out."""
        opened_at = datetime(2026, 8, 4, 4, 11, tzinfo=timezone.utc)   # 09:41 IST
        stored_naive = datetime(2026, 8, 4, 9, 15)                     # 09:15 IST, naive
        _, _, first_entry, _ = resolve_entry_price(
            broker_avg=9.3075, broker_qty=3,
            ledger_state=_state(3, "9.41", round_started_at=opened_at),
            stored_first_entry_time=stored_naive,
        )
        assert first_entry == opened_at


# =============================================================================
# End to end against the database
# =============================================================================

class TestApplyLedgerEntryPrices:

    async def _fill(self, db, broker, qty, price, minute, symbol="MAXHEALTH26AUG1200CE"):
        from app.services.position_ledger_service import FillData
        fill = FillData(
            broker_account_id=broker.id,
            tradingsymbol=symbol,
            exchange="NFO",
            fill_order_id=f"ORD_{uuid4().hex[:8]}",
            fill_qty=qty,
            fill_price=Decimal(str(price)),
            occurred_at=datetime(2026, 8, 4, 9, minute, tzinfo=timezone.utc),
            idempotency_key=f"{uuid4().hex}:ledger",
            product="MIS",
        )
        entry, _ = await PositionLedgerService.apply_fill(fill, db)
        return entry

    async def test_blended_broker_price_is_replaced_by_the_open_leg(self, db, broker):
        symbol = f"MAXH_{uuid4().hex[:6]}"
        await self._fill(db, broker, 1, "9.00", 15, symbol)
        await self._fill(db, broker, -1, "8.85", 20, symbol)
        await self._fill(db, broker, 3, "9.41", 41, symbol)

        # The broker snapshot as sync_positions would have written it.
        db.add(Position(
            broker_account_id=broker.id,
            tradingsymbol=symbol, exchange="NFO", product="MIS",
            total_quantity=3,
            average_entry_price=Decimal("9.3075"),
            first_entry_time=datetime(2026, 8, 4, 9, 15, tzinfo=timezone.utc),
            status="open",
        ))
        await db.flush()

        counts = await TradeSyncService.apply_ledger_entry_prices(broker.id, db)
        assert counts["ledger"] == 1
        assert counts["mismatch"] == 0

        pos = (await db.execute(
            select(Position).where(
                Position.broker_account_id == broker.id,
                Position.tradingsymbol == symbol,
            )
        )).scalar_one()
        assert float(pos.average_entry_price) == 9.41
        assert pos.entry_price_source == "ledger"
        assert pos.first_entry_time.hour == 9 and pos.first_entry_time.minute == 41

    async def test_quantity_mismatch_keeps_the_broker_price(self, db, broker):
        """
        A missing fill must NOT let the ledger overwrite the price.

        The mismatch also emits a data-quality event, which cannot be asserted
        here: _store_data_quality_events writes through its own session by design
        (observability must never poison the sync transaction), so it cannot see
        this test's uncommitted broker fixture and logs an FK warning instead.
        """
        symbol = f"MAXH_{uuid4().hex[:6]}"
        await self._fill(db, broker, 1, "9.00", 15, symbol)

        db.add(Position(
            broker_account_id=broker.id,
            tradingsymbol=symbol, exchange="NFO", product="MIS",
            total_quantity=3,                     # broker says 3, ledger knows 1
            average_entry_price=Decimal("9.31"),
            status="open",
        ))
        await db.flush()

        counts = await TradeSyncService.apply_ledger_entry_prices(broker.id, db)
        assert counts["mismatch"] == 1
        assert counts["ledger"] == 0

        pos = (await db.execute(
            select(Position).where(
                Position.broker_account_id == broker.id,
                Position.tradingsymbol == symbol,
            )
        )).scalar_one()
        assert float(pos.average_entry_price) == 9.31
        assert pos.entry_price_source == "broker"

    async def test_positions_price_column_only_holds_two_decimals(self, db, broker):
        """
        Schema drift, pinned deliberately: Position.average_entry_price is declared
        Numeric(15, 4) on the model but the live column is numeric(10, 2), so a
        4-decimal average is rounded on write.

        It does not change the outcome of the entry-price fix — the broker's blended
        figure would be rounded identically — but it does mean this table cannot
        represent a multi-tranche fill average exactly. The ledger and
        completed_trades, which are the P&L source of truth, are genuinely 4dp.

        If the column is ever widened to match the model, this test should fail;
        update it then rather than deleting it.
        """
        symbol = f"PREC_{uuid4().hex[:6]}"
        pos = Position(
            broker_account_id=broker.id,
            tradingsymbol=symbol, exchange="NFO", product="MIS",
            total_quantity=3, average_entry_price=Decimal("9.3075"), status="open",
        )
        db.add(pos)
        await db.flush()
        await db.refresh(pos)          # read back what Postgres actually stored

        assert float(pos.average_entry_price) == 9.31

    async def test_position_with_no_ledger_history_falls_back(self, db, broker):
        symbol = f"CARRY_{uuid4().hex[:6]}"
        db.add(Position(
            broker_account_id=broker.id,
            tradingsymbol=symbol, exchange="NFO", product="NRML",
            total_quantity=2,
            average_entry_price=Decimal("155.25"),
            status="open",
        ))
        await db.flush()

        counts = await TradeSyncService.apply_ledger_entry_prices(broker.id, db)
        assert counts["broker"] == 1
        assert counts["mismatch"] == 0

        pos = (await db.execute(
            select(Position).where(
                Position.broker_account_id == broker.id,
                Position.tradingsymbol == symbol,
            )
        )).scalar_one()
        assert float(pos.average_entry_price) == 155.25
        assert pos.entry_price_source == "broker"

    async def test_bulk_state_keeps_products_separate(self, db, broker):
        """M1: the same symbol in MIS and NRML is two positions, two averages."""
        from app.services.position_ledger_service import FillData
        symbol = f"NIFTY_{uuid4().hex[:6]}"

        for product, price in (("MIS", "100.00"), ("NRML", "200.00")):
            fill = FillData(
                broker_account_id=broker.id,
                tradingsymbol=symbol, exchange="NFO",
                fill_order_id=f"ORD_{uuid4().hex[:8]}",
                fill_qty=5, fill_price=Decimal(price),
                occurred_at=datetime(2026, 8, 4, 9, 30, tzinfo=timezone.utc),
                idempotency_key=f"{uuid4().hex}:ledger",
                product=product,
            )
            await PositionLedgerService.apply_fill(fill, db)
        await db.flush()

        states = await PositionLedgerService.get_position_states_bulk(broker.id, db)
        assert states[(symbol, "NFO", "MIS")].avg_entry_price == Decimal("100.0000")
        assert states[(symbol, "NFO", "NRML")].avg_entry_price == Decimal("200.0000")

    async def test_round_start_tracks_the_reopen(self, db, broker):
        symbol = f"ROUND_{uuid4().hex[:6]}"
        await self._fill(db, broker, 1, "9.00", 15, symbol)
        await self._fill(db, broker, -1, "8.85", 20, symbol)
        await self._fill(db, broker, 3, "9.41", 41, symbol)
        await db.flush()

        states = await PositionLedgerService.get_position_states_bulk(broker.id, db)
        state = states[(symbol, "NFO", "MIS")]
        assert state.qty == 3
        assert state.avg_entry_price == Decimal("9.4100")
        assert state.round_started_at.minute == 41

    async def test_flip_opened_round_starts_at_the_flip(self, db, broker):
        """A FLIP is grouped with the round it closed; it also opens the next one."""
        symbol = f"FLIP_{uuid4().hex[:6]}"
        await self._fill(db, broker, 5, "100.00", 15, symbol)
        await self._fill(db, broker, -8, "110.00", 30, symbol)   # closes +5, opens -3
        await db.flush()

        states = await PositionLedgerService.get_position_states_bulk(broker.id, db)
        state = states[(symbol, "NFO", "MIS")]
        assert state.qty == -3
        assert state.last_entry_type == "FLIP"
        assert state.round_started_at.minute == 30, "not the 09:15 open of the closed round"
