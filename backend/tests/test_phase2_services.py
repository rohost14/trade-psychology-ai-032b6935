"""
Phase 2 Service Tests

Tests for TradingSessionService and PositionLedgerService.
Both services are tested in isolation — no pipeline wiring yet.

Structure:
  TestComputeFillEffect   — pure function, no DB (fast, exhaustive edge cases)
  TestPositionLedgerDB    — DB-backed: apply_fill, idempotency, get_position
  TestTradingSessionDB    — DB-backed: get_or_create, risk score, state transitions
"""

import pytest
from decimal import Decimal
from datetime import datetime, timezone, date, timedelta
from uuid import uuid4

from app.services.position_ledger_service import (
    _compute_fill_effect,
    FillData,
    PositionLedgerService,
)
from app.services.trading_session_service import TradingSessionService, _state_for_score
from app.models.position_ledger import PositionLedger
from app.models.trading_session import TradingSession
from tests.helpers import now_utc


# =============================================================================
# _compute_fill_effect — pure function tests (no DB, fast)
# =============================================================================

class TestComputeFillEffect:
    """
    All edge cases for the core fill computation.
    These run in milliseconds — no DB access.
    """

    # ── OPEN ──────────────────────────────────────────────────────────

    def test_open_long(self):
        entry_type, new_qty, new_avg, pnl = _compute_fill_effect(
            current_qty=0, current_avg_price=None,
            fill_qty=50, fill_price=Decimal("100")
        )
        assert entry_type == "OPEN"
        assert new_qty == 50
        assert new_avg == Decimal("100")
        assert pnl == Decimal("0")

    def test_open_short(self):
        entry_type, new_qty, new_avg, pnl = _compute_fill_effect(
            current_qty=0, current_avg_price=None,
            fill_qty=-50, fill_price=Decimal("100")
        )
        assert entry_type == "OPEN"
        assert new_qty == -50
        assert new_avg == Decimal("100")
        assert pnl == Decimal("0")

    # ── INCREASE ──────────────────────────────────────────────────────

    def test_increase_long(self):
        """BUY 50 @ 100, then BUY 50 @ 110 → avg = 105"""
        entry_type, new_qty, new_avg, pnl = _compute_fill_effect(
            current_qty=50, current_avg_price=Decimal("100"),
            fill_qty=50, fill_price=Decimal("110")
        )
        assert entry_type == "INCREASE"
        assert new_qty == 100
        assert new_avg == Decimal("105.0000")
        assert pnl == Decimal("0")

    def test_increase_short(self):
        """SELL 50 @ 100, then SELL 50 @ 90 → avg short price = 95"""
        entry_type, new_qty, new_avg, pnl = _compute_fill_effect(
            current_qty=-50, current_avg_price=Decimal("100"),
            fill_qty=-50, fill_price=Decimal("90")
        )
        assert entry_type == "INCREASE"
        assert new_qty == -100
        assert new_avg == Decimal("95.0000")
        assert pnl == Decimal("0")

    def test_averaging_down(self):
        """BUY 50 @ 200, then BUY 50 @ 180 → avg = 190"""
        entry_type, new_qty, new_avg, pnl = _compute_fill_effect(
            current_qty=50, current_avg_price=Decimal("200"),
            fill_qty=50, fill_price=Decimal("180")
        )
        assert entry_type == "INCREASE"
        assert new_qty == 100
        assert new_avg == Decimal("190.0000")
        assert pnl == Decimal("0")

    # ── DECREASE ──────────────────────────────────────────────────────

    def test_decrease_long_profit(self):
        """BUY 100 @ 100, SELL 50 @ 120 → pnl = (120-100)*50 = 1000"""
        entry_type, new_qty, new_avg, pnl = _compute_fill_effect(
            current_qty=100, current_avg_price=Decimal("100"),
            fill_qty=-50, fill_price=Decimal("120")
        )
        assert entry_type == "DECREASE"
        assert new_qty == 50
        assert new_avg == Decimal("100")  # unchanged on partial close
        assert pnl == Decimal("1000.0000")

    def test_decrease_long_loss(self):
        """BUY 100 @ 100, SELL 50 @ 80 → pnl = (80-100)*50 = -1000"""
        entry_type, new_qty, new_avg, pnl = _compute_fill_effect(
            current_qty=100, current_avg_price=Decimal("100"),
            fill_qty=-50, fill_price=Decimal("80")
        )
        assert entry_type == "DECREASE"
        assert new_qty == 50
        assert pnl == Decimal("-1000.0000")

    def test_decrease_short_profit(self):
        """SELL 100 @ 100, BUY 50 @ 80 → pnl = (100-80)*50 = 1000"""
        entry_type, new_qty, new_avg, pnl = _compute_fill_effect(
            current_qty=-100, current_avg_price=Decimal("100"),
            fill_qty=50, fill_price=Decimal("80")
        )
        assert entry_type == "DECREASE"
        assert new_qty == -50
        assert pnl == Decimal("1000.0000")

    # ── CLOSE ─────────────────────────────────────────────────────────

    def test_close_long_exact(self):
        """BUY 50 @ 100, SELL 50 @ 130 → CLOSE, pnl = 1500"""
        entry_type, new_qty, new_avg, pnl = _compute_fill_effect(
            current_qty=50, current_avg_price=Decimal("100"),
            fill_qty=-50, fill_price=Decimal("130")
        )
        assert entry_type == "CLOSE"
        assert new_qty == 0
        assert new_avg is None
        assert pnl == Decimal("1500.0000")

    def test_close_short_exact(self):
        """SELL 50 @ 200, BUY 50 @ 150 → CLOSE, pnl = 2500"""
        entry_type, new_qty, new_avg, pnl = _compute_fill_effect(
            current_qty=-50, current_avg_price=Decimal("200"),
            fill_qty=50, fill_price=Decimal("150")
        )
        assert entry_type == "CLOSE"
        assert new_qty == 0
        assert new_avg is None
        assert pnl == Decimal("2500.0000")

    def test_close_breakeven(self):
        """Buy and sell at same price → pnl = 0"""
        entry_type, new_qty, new_avg, pnl = _compute_fill_effect(
            current_qty=100, current_avg_price=Decimal("150"),
            fill_qty=-100, fill_price=Decimal("150")
        )
        assert entry_type == "CLOSE"
        assert pnl == Decimal("0.0000")

    # ── FLIP ──────────────────────────────────────────────────────────

    def test_flip_long_to_short(self):
        """
        Long 50 @ 100. SELL 100 → closes 50 long, opens 50 short.
        pnl = (exit_price - avg_entry) * closed_qty = (120-100)*50 = 1000
        new position: -50 @ 120
        """
        entry_type, new_qty, new_avg, pnl = _compute_fill_effect(
            current_qty=50, current_avg_price=Decimal("100"),
            fill_qty=-100, fill_price=Decimal("120")
        )
        assert entry_type == "FLIP"
        assert new_qty == -50
        assert new_avg == Decimal("120")   # new short starts at fill price
        assert pnl == Decimal("1000.0000")

    def test_flip_short_to_long(self):
        """
        Short 50 @ 200. BUY 100 → closes 50 short, opens 50 long.
        pnl = (avg_entry - exit_price) * closed_qty = (200-180)*50 = 1000
        new position: +50 @ 180
        """
        entry_type, new_qty, new_avg, pnl = _compute_fill_effect(
            current_qty=-50, current_avg_price=Decimal("200"),
            fill_qty=100, fill_price=Decimal("180")
        )
        assert entry_type == "FLIP"
        assert new_qty == 50
        assert new_avg == Decimal("180")   # new long starts at fill price
        assert pnl == Decimal("1000.0000")

    def test_flip_with_loss(self):
        """Long 50 @ 100, SELL 100 @ 80 → loss on close"""
        entry_type, new_qty, new_avg, pnl = _compute_fill_effect(
            current_qty=50, current_avg_price=Decimal("100"),
            fill_qty=-100, fill_price=Decimal("80")
        )
        assert entry_type == "FLIP"
        assert new_qty == -50
        assert pnl == Decimal("-1000.0000")  # (80-100)*50

    # ── Edge cases ────────────────────────────────────────────────────

    def test_pnl_only_on_closing_fills(self):
        """Opening and increasing fills must have zero pnl."""
        for entry_type in ["OPEN", "INCREASE"]:
            _, _, _, pnl = _compute_fill_effect(
                current_qty=0 if entry_type == "OPEN" else 50,
                current_avg_price=None if entry_type == "OPEN" else Decimal("100"),
                fill_qty=50,
                fill_price=Decimal("110"),
            )
            assert pnl == Decimal("0"), f"{entry_type} should have zero pnl"

    def test_weighted_average_unequal_sizes(self):
        """BUY 30 @ 100, BUY 70 @ 200 → avg = (3000 + 14000) / 100 = 170"""
        entry_type, new_qty, new_avg, pnl = _compute_fill_effect(
            current_qty=30, current_avg_price=Decimal("100"),
            fill_qty=70, fill_price=Decimal("200")
        )
        assert new_avg == Decimal("170.0000")


# =============================================================================
# PositionLedgerService — DB tests
# =============================================================================

class TestPositionLedgerDB:

    def _make_fill(self, broker, symbol="NIFTY25JANFUT", exchange="NFO",
                   fill_qty=50, fill_price="100", order_id=None, seq=0):
        order_id = order_id or f"ORD_{uuid4().hex[:8]}"
        return FillData(
            broker_account_id=broker.id,
            tradingsymbol=symbol,
            exchange=exchange,
            fill_order_id=order_id,
            fill_qty=fill_qty,
            fill_price=Decimal(fill_price),
            occurred_at=now_utc(),
            idempotency_key=f"{order_id}:{seq}",
        )

    async def test_open_position(self, db, broker):
        fill = self._make_fill(broker, fill_qty=50, fill_price="100")
        entry, is_new = await PositionLedgerService.apply_fill(fill, db)

        assert is_new is True
        assert entry.entry_type == "OPEN"
        assert entry.position_qty_after == 50
        assert entry.realized_pnl == Decimal("0")

    async def test_get_position_after_open(self, db, broker):
        fill = self._make_fill(broker, fill_qty=50, fill_price="100")
        await PositionLedgerService.apply_fill(fill, db)

        qty, avg = await PositionLedgerService.get_position(
            broker.id, "NIFTY25JANFUT", "NFO", db
        )
        assert qty == 50
        assert avg == Decimal("100")

    async def test_no_position_returns_zero(self, db, broker):
        qty, avg = await PositionLedgerService.get_position(
            broker.id, "UNKNOWN", "NSE", db
        )
        assert qty == 0
        assert avg is None

    async def test_idempotency_same_key_returns_existing(self, db, broker):
        fill = self._make_fill(broker)
        entry1, is_new1 = await PositionLedgerService.apply_fill(fill, db)
        entry2, is_new2 = await PositionLedgerService.apply_fill(fill, db)

        assert is_new1 is True
        assert is_new2 is False
        assert entry1.id == entry2.id

    async def test_sequence_open_increase_close(self, db, broker):
        """Full round trip: OPEN → INCREASE → CLOSE"""
        order1 = f"ORD_{uuid4().hex[:8]}"
        order2 = f"ORD_{uuid4().hex[:8]}"
        order3 = f"ORD_{uuid4().hex[:8]}"

        # OPEN: BUY 50 @ 100
        f1 = FillData(broker.id, "BANKNIFTY25FUT", "NFO", order1,
                      50, Decimal("100"), now_utc(), f"{order1}:0")
        e1, _ = await PositionLedgerService.apply_fill(f1, db)
        assert e1.entry_type == "OPEN"

        # INCREASE: BUY 50 @ 120
        f2 = FillData(broker.id, "BANKNIFTY25FUT", "NFO", order2,
                      50, Decimal("120"), now_utc(), f"{order2}:0")
        e2, _ = await PositionLedgerService.apply_fill(f2, db)
        assert e2.entry_type == "INCREASE"
        assert e2.position_qty_after == 100
        assert e2.avg_entry_price_after == Decimal("110.0000")

        # CLOSE: SELL 100 @ 130 → pnl = (130-110)*100 = 2000
        f3 = FillData(broker.id, "BANKNIFTY25FUT", "NFO", order3,
                      -100, Decimal("130"), now_utc(), f"{order3}:0")
        e3, _ = await PositionLedgerService.apply_fill(f3, db)
        assert e3.entry_type == "CLOSE"
        assert e3.position_qty_after == 0
        assert e3.realized_pnl == Decimal("2000.0000")

    async def test_position_flip(self, db, broker):
        """Long 50 → SELL 100 → short 50"""
        order1 = f"ORD_{uuid4().hex[:8]}"
        order2 = f"ORD_{uuid4().hex[:8]}"

        f1 = FillData(broker.id, "NIFTY25FUT", "NFO", order1,
                      50, Decimal("22000"), now_utc(), f"{order1}:0")
        await PositionLedgerService.apply_fill(f1, db)

        f2 = FillData(broker.id, "NIFTY25FUT", "NFO", order2,
                      -100, Decimal("22500"), now_utc(), f"{order2}:0")
        e2, _ = await PositionLedgerService.apply_fill(f2, db)

        assert e2.entry_type == "FLIP"
        assert e2.position_qty_after == -50
        assert e2.avg_entry_price_after == Decimal("22500")
        # pnl = (22500 - 22000) * 50 = 25000
        assert e2.realized_pnl == Decimal("25000.0000")

    async def test_late_fill_out_of_order(self, db, broker):
        """
        Late fill arrives out of chronological order (webhook delay).

        Sequence in TIME order:
          10:00 BUY 50 @ 100   → OPEN, net=50
          10:02 BUY 25 @ 95    → INCREASE, net=75, avg=(50*100+25*95)/75 = 98.33
          10:05 SELL 75 @ 120  → CLOSE, pnl=(120-98.33)*75 = 1625

        Arrival order (webhook delay on fill at 10:02):
          10:00 BUY 50 arrives first  → processed normally
          10:05 SELL 75 arrives second → processed against LONG 50 (wrong without replay)
          10:02 BUY 25 arrives LATE   → triggers replay, corrects all entries

        After replay: SELL 75 must reflect avg_entry of 98.33, not 100.
        """
        from datetime import timezone

        base = datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        t1 = base                                           # 10:00
        t2 = base.replace(minute=2)                        # 10:02
        t3 = base.replace(minute=5)                        # 10:05

        ord1 = f"ORD_{uuid4().hex[:8]}"
        ord2 = f"ORD_{uuid4().hex[:8]}"
        ord3 = f"ORD_{uuid4().hex[:8]}"

        symbol, exchange = "NIFTY25FEB25000CE", "NFO"

        # Step 1: 10:00 BUY 50 arrives, processed normally
        f1 = FillData(broker.id, symbol, exchange, ord1, 50, Decimal("100"), t1, f"{ord1}:0")
        e1, _ = await PositionLedgerService.apply_fill(f1, db)
        assert e1.entry_type == "OPEN"
        assert e1.position_qty_after == 50

        # Step 2: 10:05 SELL 75 arrives (before 10:02 fill) — wrong state
        f3 = FillData(broker.id, symbol, exchange, ord3, -75, Decimal("120"), t3, f"{ord3}:0")
        e3, _ = await PositionLedgerService.apply_fill(f3, db)
        # At this point, state is WRONG (computed against LONG 50, not LONG 75)
        # We don't assert correctness here — it will be fixed by the late fill replay

        # Step 3: 10:02 BUY 25 arrives LATE → triggers replay
        f2 = FillData(broker.id, symbol, exchange, ord2, 25, Decimal("95"), t2, f"{ord2}:0")
        e2, is_new = await PositionLedgerService.apply_fill(f2, db)
        assert is_new is True  # new fill, not a duplicate

        # After replay: verify all 3 entries are correct in time order
        await db.refresh(e1)
        await db.refresh(e2)
        await db.refresh(e3)

        # e1: BUY 50 @ 100 — unchanged (before the late fill)
        assert e1.entry_type == "OPEN"
        assert e1.position_qty_after == 50

        # e2: BUY 25 @ 95 — INCREASE on top of 50 long, avg = (5000+2375)/75 = 98.33
        assert e2.entry_type == "INCREASE"
        assert e2.position_qty_after == 75
        expected_avg = Decimal("98.3333")
        assert abs(e2.avg_entry_price_after - expected_avg) < Decimal("0.001")

        # e3: SELL 75 @ 120 — now CLOSE, pnl = (120 - 98.3333) * 75 = 1625
        assert e3.entry_type == "CLOSE"
        assert e3.position_qty_after == 0
        expected_pnl = (Decimal("120") - e2.avg_entry_price_after) * 75
        assert abs(e3.realized_pnl - expected_pnl) < Decimal("1")  # within ₹1

    async def test_get_realized_pnl_range(self, db, broker):
        """get_realized_pnl sums CLOSE/DECREASE/FLIP entries in range."""
        now = now_utc()
        order1 = f"ORD_{uuid4().hex[:8]}"
        order2 = f"ORD_{uuid4().hex[:8]}"
        order3 = f"ORD_{uuid4().hex[:8]}"

        # Round 1: BUY 50 @ 100, SELL 50 @ 110 → pnl = 500
        f1 = FillData(broker.id, "RELIANCE", "NSE", order1,
                      50, Decimal("100"), now, f"{order1}:0")
        f2 = FillData(broker.id, "RELIANCE", "NSE", order2,
                      -50, Decimal("110"), now, f"{order2}:0")
        await PositionLedgerService.apply_fill(f1, db)
        await PositionLedgerService.apply_fill(f2, db)

        # Out-of-range fill (yesterday)
        yesterday = now - timedelta(days=1)
        f3 = FillData(broker.id, "RELIANCE", "NSE", order3,
                      -50, Decimal("90"), yesterday, f"{order3}:0")
        # Need to open first to close
        order_open = f"ORD_{uuid4().hex[:8]}"
        f_open = FillData(broker.id, "RELIANCE", "NSE", order_open,
                          50, Decimal("100"), yesterday - timedelta(hours=1),
                          f"{order_open}:0")
        await PositionLedgerService.apply_fill(f_open, db)
        await PositionLedgerService.apply_fill(f3, db)

        # Query only today's range
        pnl = await PositionLedgerService.get_realized_pnl(
            broker.id,
            from_dt=now - timedelta(minutes=1),
            to_dt=now + timedelta(minutes=1),
            db=db,
        )
        assert pnl == Decimal("500.0000")


# =============================================================================
# TradingSessionService — DB tests
# =============================================================================

class TestTradingSessionDB:

    async def test_create_session(self, db, broker):
        today = date.today()
        session = await TradingSessionService.get_or_create_session(
            broker.id, today, db
        )
        assert session.broker_account_id == broker.id
        assert session.session_date == today
        assert session.session_state == "normal"
        assert session.risk_score == Decimal("0")

    async def test_get_or_create_idempotent(self, db, broker):
        """Calling twice returns the same session."""
        today = date.today()
        s1 = await TradingSessionService.get_or_create_session(broker.id, today, db)
        s2 = await TradingSessionService.get_or_create_session(broker.id, today, db)
        assert s1.id == s2.id

    async def test_state_transitions(self, db, broker):
        """Risk score thresholds drive correct state transitions."""
        assert _state_for_score(Decimal("0")) == "normal"
        assert _state_for_score(Decimal("39")) == "normal"
        assert _state_for_score(Decimal("40")) == "caution"
        assert _state_for_score(Decimal("69")) == "caution"
        assert _state_for_score(Decimal("70")) == "danger"
        assert _state_for_score(Decimal("89")) == "danger"
        assert _state_for_score(Decimal("90")) == "blowup"
        assert _state_for_score(Decimal("100")) == "blowup"

    async def test_update_risk_score_advances_state(self, db, broker):
        session = await TradingSessionService.get_or_create_session(
            broker.id, date.today(), db
        )
        assert session.session_state == "normal"

        # Push into caution
        session = await TradingSessionService.update_risk_score(
            session.id, Decimal("50"), db
        )
        assert session.risk_score == Decimal("50")
        assert session.session_state == "caution"

        # Push into danger
        session = await TradingSessionService.update_risk_score(
            session.id, Decimal("25"), db
        )
        assert session.risk_score == Decimal("75")
        assert session.session_state == "danger"

    async def test_risk_score_clamps_at_100(self, db, broker):
        session = await TradingSessionService.get_or_create_session(
            broker.id, date.today(), db
        )
        session = await TradingSessionService.update_risk_score(
            session.id, Decimal("150"), db
        )
        assert session.risk_score == Decimal("100")
        assert session.session_state == "blowup"

    async def test_risk_score_clamps_at_zero(self, db, broker):
        """Risk score cannot go below 0."""
        session = await TradingSessionService.get_or_create_session(
            broker.id, date.today(), db
        )
        session = await TradingSessionService.update_risk_score(
            session.id, Decimal("-50"), db
        )
        assert session.risk_score == Decimal("0")

    async def test_peak_risk_score_tracked(self, db, broker):
        """peak_risk_score captures the highest value seen."""
        session = await TradingSessionService.get_or_create_session(
            broker.id, date.today(), db
        )
        await TradingSessionService.update_risk_score(session.id, Decimal("70"), db)
        session = await TradingSessionService.update_risk_score(
            session.id, Decimal("-40"), db
        )
        assert session.risk_score == Decimal("30")
        assert session.peak_risk_score == Decimal("70")

    async def test_increment_trade_count(self, db, broker):
        session = await TradingSessionService.get_or_create_session(
            broker.id, date.today(), db
        )
        await TradingSessionService.increment_trade_count(session.id, db)
        await TradingSessionService.increment_trade_count(session.id, db)
        await db.refresh(session)
        assert session.trade_count == 2

    async def test_add_session_pnl(self, db, broker):
        session = await TradingSessionService.get_or_create_session(
            broker.id, date.today(), db
        )
        await TradingSessionService.add_session_pnl(session.id, Decimal("1500"), db)
        await TradingSessionService.add_session_pnl(session.id, Decimal("-500"), db)
        await db.refresh(session)
        assert session.session_pnl == Decimal("1000")

    async def test_close_session(self, db, broker):
        session = await TradingSessionService.get_or_create_session(
            broker.id, date.today(), db
        )
        await TradingSessionService.close_session(
            session.id, Decimal("500000"), db
        )
        await db.refresh(session)
        assert session.closing_equity == Decimal("500000")

    async def test_sessions_isolated_per_account(self, db, broker, user):
        """Different accounts get different sessions for same date."""
        from app.models.broker_account import BrokerAccount
        from tests.helpers import make_email

        broker2 = BrokerAccount(
            user_id=user.id, broker_name="zerodha",
            broker_email=make_email(), broker_user_id="QA5678",
            status="connected",
        )
        db.add(broker2)
        await db.flush()

        today = date.today()
        s1 = await TradingSessionService.get_or_create_session(broker.id, today, db)
        s2 = await TradingSessionService.get_or_create_session(broker2.id, today, db)

        assert s1.id != s2.id
        assert s1.broker_account_id == broker.id
        assert s2.broker_account_id == broker2.id
