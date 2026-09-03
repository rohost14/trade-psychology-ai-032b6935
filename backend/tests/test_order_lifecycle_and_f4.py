"""
Order-lifecycle persistence, and F4's protective-stop finding.

TWO DEFECTS THIS CLOSES

1. THE STREAM THREW THE EVIDENCE AWAY. `order_stream_service._on_order_update`
   returned on anything that was not COMPLETE. Kite pushes an update for every
   order of the authenticated user wherever it was placed, carrying order_type
   and trigger_price on every state — so a resting stop-loss arrived several
   times and was discarded every time. Kite's orders() is today-only, so it
   could not be backfilled afterwards either.

2. ABSENCE WAS READ AS PROOF. `no_stoploss` could only see the exit fill's
   order type, which answers "was this exit executed by a stop" and not "did a
   stop exist". An empty answer was indistinguishable from "no stop was
   placed" — the claim the Pattern 12 review removed, and the one that must not
   come back.

THE RULE THESE ENFORCE: an order is not a fill, and silence is not evidence.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.models.completed_trade import CompletedTrade

NOW = datetime(2026, 9, 3, 6, 0, tzinfo=timezone.utc)
BROKER = uuid4()


# ── 1. lifecycle persistence ───────────────────────────────────────────────

class _Ticker:
    """The real callback, with Celery dispatch captured instead of sent."""

    def __init__(self):
        from app.services.order_stream_service import ZerodhaOrderTicker

        self.t = ZerodhaOrderTicker.__new__(ZerodhaOrderTicker)
        self.t.broker_account_id = BROKER
        self.t._dedup = _Dedup()
        self.order_events, self.fills = [], []
        self.t._enqueue_order_event = self.order_events.append
        self.t._enqueue = self.fills.append

    def send(self, **kw):
        data = {
            "order_id": "251203000000001", "status": "COMPLETE",
            "tradingsymbol": "NIFTY25SEP24000CE", "exchange": "NFO",
            "transaction_type": "SELL", "order_type": "SL", "product": "MIS",
            "quantity": 75, "filled_quantity": 0, "pending_quantity": 75,
            "cancelled_quantity": 0, "price": 0.0, "average_price": 0.0,
            "trigger_price": 90.0, "order_timestamp": NOW,
            "exchange_timestamp": NOW, "exchange_update_timestamp": NOW,
            "validity": "DAY", "variety": "regular",
        }
        data.update(kw)
        self.t._on_order_update(None, data)
        return self


class _Dedup:
    def __init__(self):
        self._seen = set()

    def add(self, key):
        if key in self._seen:
            return False
        self._seen.add(key)
        return True


@pytest.mark.parametrize("status", [
    "TRIGGER PENDING", "OPEN", "CANCELLED", "REJECTED", "UPDATE", "MODIFIED",
])
def test_every_lifecycle_state_is_persisted(status):
    """Each of these used to hit `return` and vanish."""
    t = _Ticker().send(status=status)
    assert len(t.order_events) == 1, f"{status} was not persisted"
    assert t.order_events[0]["status"] == status


def test_complete_is_still_persisted_and_still_drives_the_trade_pipeline():
    t = _Ticker().send(status="COMPLETE", filled_quantity=75, pending_quantity=0)
    assert len(t.order_events) == 1
    assert len(t.fills) == 1


@pytest.mark.parametrize("status", [
    "TRIGGER PENDING", "OPEN", "CANCELLED", "REJECTED",
])
def test_a_non_complete_order_never_becomes_a_trade(status):
    """
    The separation that matters. A TRIGGER PENDING stop has filled nothing;
    routing it into the trade pipeline would manufacture a position.
    """
    t = _Ticker().send(status=status)
    assert t.fills == [], f"{status} leaked into the trade pipeline"


def test_the_persisted_event_carries_what_F4_needs():
    t = _Ticker().send(status="TRIGGER PENDING")
    ev = t.order_events[0]
    for field in ("order_type", "trigger_price", "transaction_type",
                  "quantity", "status", "order_timestamp"):
        assert ev.get(field) is not None, f"{field} missing from the order event"
    assert ev["order_type"] == "SL"
    assert ev["trigger_price"] == 90.0


def test_a_repeated_identical_update_is_idempotent():
    t = _Ticker()
    t.send(status="TRIGGER PENDING")
    t.send(status="TRIGGER PENDING")
    assert len(t.order_events) == 1


def test_a_status_change_on_the_same_order_is_new_evidence():
    """
    Dedup must key on the STATE, not the order. A stop going
    TRIGGER PENDING -> CANCELLED is the whole story F4 needs.
    """
    t = _Ticker()
    t.send(status="TRIGGER PENDING")
    t.send(status="CANCELLED")
    assert [e["status"] for e in t.order_events] == ["TRIGGER PENDING", "CANCELLED"]


def test_untracked_products_are_still_ignored():
    t = _Ticker().send(status="TRIGGER PENDING", product="CNC")
    assert t.order_events == [] and t.fills == []


# ── 2. F4: coverage and protection ─────────────────────────────────────────

def _ct(qty=75, direction="LONG", entry_ids=("E1",), exit_ids=("X1",)):
    ct = MagicMock(spec=CompletedTrade)
    ct.id = uuid4()
    ct.broker_account_id = BROKER
    ct.tradingsymbol = "NIFTY25SEP24000CE"
    ct.exchange = "NFO"
    ct.direction = direction
    ct.total_quantity = qty
    ct.entry_time = NOW
    ct.exit_time = NOW + timedelta(minutes=40)
    ct.entry_trade_ids = list(entry_ids)
    ct.exit_trade_ids = list(exit_ids)
    return ct


def _order(qty=75, status="TRIGGER PENDING", otype="SL", side="SELL",
           placed=None, removed=None, trigger=90.0):
    return SimpleNamespace(
        kite_order_id="S1", quantity=qty, status=status, order_type=otype,
        transaction_type=side, order_timestamp=placed or (NOW + timedelta(minutes=1)),
        exchange_update_timestamp=removed, updated_at=removed,
        trigger_price=trigger,
    )


class _DB:
    """In order: protective orders, overlap count, snapshot count, GTT probe."""

    def __init__(self, orders, overlapping=0, snapshot=1, gtt=False):
        self._orders = orders
        self._scalars = [overlapping, snapshot]
        self._gtt = gtt

    async def execute(self, *_a, **_k):
        if self._orders is not None:
            payload, self._orders = self._orders, None
            return SimpleNamespace(scalars=lambda: SimpleNamespace(
                all=lambda: payload))
        if self._scalars:
            val = self._scalars.pop(0)
            return SimpleNamespace(scalar=lambda: val)
        return SimpleNamespace(fetchone=lambda: (1,) if self._gtt else None)


class _DBNoGtt(_DB):
    """A database where the GTT table cannot be read at all."""

    async def execute(self, *a, **k):
        if self._orders is None and not self._scalars:
            raise RuntimeError("relation gtt_tracking does not exist")
        return await super().execute(*a, **k)


async def _evidence(orders, ct=None, overlapping=0, snapshot=1, gtt=False,
                    db_cls=_DB):
    from app.services.behavior_engine import _load_stop_evidence
    return await _load_stop_evidence(
        ct or _ct(), db_cls(orders, overlapping, snapshot, gtt))


@pytest.mark.asyncio
async def test_an_active_gtt_withholds_the_absence_claim():
    """
    A GTT is a stop the `orders` table structurally cannot hold — it lives
    behind /gtt/triggers and produces no order until it fires. The order-book
    snapshot certifies completeness over a set that excludes it, so a trader
    holding a live GTT would otherwise be told they had no stop.
    """
    ev = await _evidence([], gtt=True)
    assert ev["gtt_active"] is True
    assert ev["snapshot_complete"] is False        # negative claim withheld


@pytest.mark.asyncio
async def test_an_unreadable_gtt_table_also_withholds_the_claim():
    """Cannot tell is not the same as no. `gtt_tracking` may not even exist."""
    ev = await _evidence([], db_cls=_DBNoGtt)
    assert ev["gtt_active"] is True
    assert ev["snapshot_complete"] is False


@pytest.mark.asyncio
async def test_a_gtt_is_never_used_to_assert_protection():
    """
    One-way only. `gtt_tracking` is seeded at connect and never reconciled, so
    its absences are untrustworthy and it must not add covered quantity.
    """
    ev = await _evidence([], gtt=True)
    assert ev["covered_qty"] == 0
    assert ev["covered_ratio"] == 0.0


@pytest.mark.asyncio
async def test_seeing_a_stop_needs_no_coverage_at_all():
    """
    The asymmetry. Observing a stop PROVES one existed whatever our ingestion
    coverage was, so a positive finding never waits on a snapshot.
    """
    ev = await _evidence([_order(qty=75)], snapshot=0)
    assert ev["covered_ratio"] == 1.0
    assert ev["snapshot_complete"] is False


@pytest.mark.asyncio
async def test_the_negative_claim_requires_a_complete_order_book():
    """
    Seeing nothing proves nothing without the whole list. `sync_orders_to_db`
    records the snapshot marker; without it this stays unlicensed.
    """
    ev = await _evidence([], snapshot=0)
    assert ev["covered_qty"] == 0
    assert ev["snapshot_complete"] is False        # detector must stay silent

    ev = await _evidence([], snapshot=1)
    assert ev["snapshot_complete"] is True         # now licensed


@pytest.mark.asyncio
async def test_an_overlapping_round_on_the_same_symbol_is_ambiguous():
    """
    "Same symbol" is not "same position". With another round overlapping, a
    stop cannot be attributed to either.
    """
    ev = await _evidence([], overlapping=1)
    assert ev["ambiguous"] is True


@pytest.mark.asyncio
async def test_a_fully_covering_stop_is_recognised():
    ev = await _evidence([_order(qty=75)])
    assert ev["covered_qty"] == 75
    assert ev["covered_ratio"] == 1.0
    assert ev["trigger_prices"] == [90.0]


@pytest.mark.asyncio
async def test_sl_m_counts_as_protection():
    ev = await _evidence([_order(otype="SL-M", trigger=88.0)])
    assert ev["covered_ratio"] == 1.0


@pytest.mark.asyncio
async def test_multiple_partial_stops_sum_rather_than_flip_a_boolean():
    ev = await _evidence([_order(qty=25), _order(qty=25)])
    assert ev["covered_qty"] == 50
    assert ev["covered_ratio"] == pytest.approx(50 / 75)


@pytest.mark.asyncio
async def test_a_stop_cancelled_before_the_exit_is_not_protection():
    ev = await _evidence([
        _order(status="CANCELLED", removed=NOW + timedelta(minutes=5)),
    ])
    assert ev["covered_qty"] == 0
    assert ev["cancelled_before_exit"] == 1


@pytest.mark.asyncio
async def test_a_stop_cancelled_after_the_exit_still_counted_as_protection():
    ev = await _evidence([
        _order(status="CANCELLED", removed=NOW + timedelta(hours=2)),
    ])
    assert ev["covered_qty"] == 75


@pytest.mark.asyncio
async def test_cancel_then_recreate_is_reported_as_replaced_not_absent():
    """A stop swapped for another is protection, not the absence of it."""
    ev = await _evidence([
        _order(status="CANCELLED", removed=NOW + timedelta(minutes=5)),
        _order(qty=50),
    ])
    assert ev["replaced"] is True
    assert ev["covered_qty"] == 50


@pytest.mark.asyncio
async def test_a_modified_trigger_is_recorded_as_a_modification():
    ev = await _evidence([
        _order(qty=75, removed=NOW + timedelta(minutes=20)),
    ])
    assert ev["modified"] == 1
    assert ev["covered_qty"] == 75


@pytest.mark.asyncio
async def test_repeated_modifications_do_not_multiply_rows():
    """
    Kite rewrites the same order row on modify, so ten trigger changes remain
    ONE order. What survives is the fact that it moved, not every price.
    """
    ev = await _evidence([_order(qty=75, removed=NOW + timedelta(minutes=30))])
    assert ev["protective_orders"] == 1
    assert ev["modified"] == 1


@pytest.mark.asyncio
async def test_a_rejected_stop_never_protected_anything():
    ev = await _evidence([_order(status="REJECTED")])
    assert ev["covered_qty"] == 0
    assert ev["rejected"] == 1


@pytest.mark.asyncio
async def test_a_stop_from_an_earlier_round_does_not_count():
    ev = await _evidence([_order(placed=NOW - timedelta(hours=2))])
    assert ev["covered_qty"] == 0


@pytest.mark.asyncio
async def test_a_limit_order_is_not_assumed_to_be_protection():
    """
    A LIMIT exit and a LIMIT entry are indistinguishable here, so LIMIT is
    never counted as a target or a stop.
    """
    import inspect
    from app.services.behavior_engine import _load_stop_evidence

    src = inspect.getsource(_load_stop_evidence)
    assert '("SL", "SL-M")' in src


@pytest.mark.asyncio
async def test_an_unknown_direction_abstains():
    assert await _evidence([_order()], ct=_ct(direction=None)) is None


# ── 3. the detector's behaviour, end to end ────────────────────────────────

def _det_ctx(stop_evidence):
    """A losing long option big enough to trip the detector, plus evidence."""
    from app.services.behavior_engine import EngineContext
    from app.core.trading_defaults import COLD_START_DEFAULTS

    ct = SimpleNamespace(
        id=uuid4(), broker_account_id=BROKER, tradingsymbol="NIFTY25APR24000CE",
        exchange="NFO", product="MIS", instrument_type="CE", direction="LONG",
        total_quantity=75, avg_entry_price=Decimal("100"),
        avg_exit_price=Decimal("60"), realized_pnl=Decimal("-3000"),
        duration_minutes=30, entry_time=NOW, exit_time=NOW + timedelta(hours=1),
        num_entries=1, num_exits=1, status="closed",
        entry_trade_ids=["E1"], exit_trade_ids=["X1"],
    )
    return EngineContext(
        broker_account_id=BROKER,
        session=SimpleNamespace(session_pnl=Decimal("0"),
                                session_date=ct.exit_time.date(), market_open=None),
        completed_trade=ct, session_trades=[ct],
        thresholds=dict(COLD_START_DEFAULTS), exit_order_types=[],
        stop_evidence=stop_evidence,
    )


def _fire(stop_evidence):
    from app.services.behavior_engine import BehaviorEngine
    return BehaviorEngine()._detect_no_stoploss(_det_ctx(stop_evidence))


def _ev(**kw):
    base = dict(snapshot_complete=True, ambiguous=False, position_qty=75,
                covered_qty=0, covered_ratio=0.0, protective_orders=0,
                cancelled_before_exit=0, rejected=0, modified=0,
                replaced=False, trigger_prices=[])
    base.update(kw)
    return base


def test_case_B_a_fully_protected_position_produces_no_finding():
    """The loss ran, but the position was covered. That is not unprotected."""
    assert _fire(_ev(covered_qty=75, covered_ratio=1.0,
                     protective_orders=1, trigger_prices=[90.0])) is None


def test_case_H_no_coverage_never_claims_a_stop_was_absent():
    """
    THE RULE. Nothing observed and no complete order book: the detector still
    reports the loss and says NOTHING about stops.
    """
    ev = _fire(_ev(snapshot_complete=False))
    assert ev is not None
    assert "stop" not in ev.message.lower()
    assert ev.context["stop_case"] == "H"


def test_case_H_ambiguous_association_also_withholds_the_negative_claim():
    """Another round overlapped on this symbol — attribution is unsafe."""
    ev = _fire(_ev(ambiguous=True))
    assert ev is not None
    assert "stop" not in ev.message.lower()
    assert ev.context["stop_case"] == "H"


def test_case_A_complete_order_book_and_nothing_placed():
    ev = _fire(_ev())
    assert ev is not None
    assert "No stop-loss order was placed on this position." in ev.message
    assert ev.context["stop_case"] == "A"


def test_case_E_partial_protection_is_reported_as_partial():
    ev = _fire(_ev(covered_qty=25, covered_ratio=25 / 75, protective_orders=1))
    assert ev is not None
    assert "33% of the position" in ev.message and "25 of 75" in ev.message
    assert ev.context["stop_case"] == "E"


def test_case_C_a_cancelled_stop_is_described_as_cancelled_not_absent():
    """
    "No stop was ever placed" and "a stop was placed then removed" are
    different behavioural facts and must not collapse.
    """
    ev = _fire(_ev(cancelled_before_exit=1))
    assert ev is not None
    assert "cancelled before the exit" in ev.message
    assert "No stop-loss order was placed" not in ev.message
    assert ev.context["stop_case"] == "C"


def test_case_D_a_rejected_stop_is_not_reported_as_absence():
    ev = _fire(_ev(rejected=1))
    assert ev is not None
    assert "rejected" in ev.message.lower()
    assert ev.context["stop_case"] == "D"


def test_case_F_a_modified_trigger_is_surfaced():
    ev = _fire(_ev(covered_qty=25, covered_ratio=25 / 75,
                   protective_orders=1, modified=1))
    assert ev is not None
    assert "modified during the position" in ev.message
    assert ev.context["stop_case"] == "F"


def test_case_G_replaced_stop_is_distinct_from_partial():
    ev = _fire(_ev(covered_qty=50, covered_ratio=50 / 75,
                   protective_orders=1, cancelled_before_exit=1, replaced=True))
    assert ev is not None
    assert ev.context["stop_case"] == "G"


def test_the_eight_cases_are_all_reachable_and_distinct():
    """No two states collapse into one generic 'no stop'."""
    seen = {
        _fire(_ev(snapshot_complete=False)).context["stop_case"],
        _fire(_ev()).context["stop_case"],
        _fire(_ev(cancelled_before_exit=1)).context["stop_case"],
        _fire(_ev(rejected=1)).context["stop_case"],
        _fire(_ev(covered_qty=25, covered_ratio=1 / 3)).context["stop_case"],
        _fire(_ev(covered_qty=25, covered_ratio=1 / 3, modified=1)).context["stop_case"],
        _fire(_ev(covered_qty=50, covered_ratio=2 / 3, replaced=True)).context["stop_case"],
    }
    assert seen == {"A", "C", "D", "E", "F", "G", "H"}
    assert _fire(_ev(covered_qty=75, covered_ratio=1.0)) is None   # case B
