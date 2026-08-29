"""
Broker margin capture — the nine scenarios.

In process. No database, no Redis, no network. The Kite client and the
persistence layer are replaced by fakes so the LOGIC is what gets tested:
what we ask the broker, what we store, what reaches the risk layer, and what
happens when any of it is missing.

The point is not that COMPUTED equals the broker figure — it does not, and a
known residual is documented. The point is:

    BROKER value captured -> persisted -> resolved -> consumed.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.risk_quantities import (
    Capital, MarginSource, quantities_for_trade,
)
from app.services import broker_margin_service as BMS

ACCOUNT = uuid4()
NOW = datetime(2026, 8, 28, 10, 30, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _reset_table_probe():
    """
    `_TABLE_AVAILABLE` is memoised per process so a missing table is reported
    once and never re-queried. That is right in production and would make these
    tests order-dependent, so it is reset around each one.
    """
    BMS._TABLE_AVAILABLE = None
    yield
    BMS._TABLE_AVAILABLE = None


def _pos(symbol, qty, exchange="NFO", product="NRML"):
    return SimpleNamespace(tradingsymbol=symbol, total_quantity=qty,
                           exchange=exchange, product=product)


def _trade(symbol, direction, qty, price, exchange="NFO", product="NRML"):
    return SimpleNamespace(
        tradingsymbol=symbol, exchange=exchange, direction=direction,
        total_quantity=qty, avg_entry_price=price, product=product,
        broker_account_id=ACCOUNT, entry_time=NOW,
        exit_time=NOW + timedelta(hours=2), instrument_type=None)


# ---------------------------------------------------------------------------
# Lifecycle policy
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("entry_type,product,expected", [
    ("OPEN", "NRML", True),
    ("INCREASE", "MIS", True),
    ("FLIP", "NRML", True),
    ("DECREASE", "NRML", False),     # shrinking needs no fresh observation
    ("CLOSE", "NRML", False),        # nothing left to collateralise
    ("OPEN", "CNC", False),          # delivery is paid in full
    (None, "NRML", False),
])
def test_capture_lifecycle_is_narrow(entry_type, product, expected):
    """
    No polling and no per-tick calls. One call per position-opening fill, which
    is the only moment the figure can be obtained at all.
    """
    assert BMS.should_capture(entry_type, product) is expected


def test_the_request_describes_the_whole_structure():
    """
    Margin is a property of the structure. Measured on a real account, a NIFTY
    call spread cost 64,174 against 175,747 for its short leg alone, so asking
    per leg would overstate committed capital threefold.
    """
    legs = [BMS._leg_payload(_pos("NIFTY26SEP24200CE", -65)),
            BMS._leg_payload(_pos("NIFTY26SEP24300CE", 65))]
    assert legs[0]["transaction_type"] == "SELL"
    assert legs[1]["transaction_type"] == "BUY"
    assert all(leg["quantity"] == 65 for leg in legs), "quantity is absolute"
    assert all(leg["product"] == "NRML" for leg in legs)


# ---------------------------------------------------------------------------
# Reading Kite's answer
# ---------------------------------------------------------------------------

def test_basket_response_keeps_final_not_initial():
    """
    `final` has spread benefit applied and is what the account actually has
    blocked. `initial` charges legs independently.
    """
    payload = [{"tradingsymbol": "NIFTY26SEP24200CE"},
               {"tradingsymbol": "NIFTY26SEP24300CE"}]
    resp = {
        "initial": {"total": 175747.0, "span": 144550.0, "exposure": 31196.0},
        "final": {"total": 64174.0, "span": 32977.0, "exposure": 31196.0,
                  "option_premium": 0, "additional": 0},
        "orders": [{"tradingsymbol": "NIFTY26SEP24200CE", "total": 60000.0},
                   {"tradingsymbol": "NIFTY26SEP24300CE", "total": 4174.0}],
    }
    got = BMS._read_basket_response(resp, payload)
    assert got["total"] == 64174.0, "must be the spread-benefited figure"
    assert got["per_leg"]["NIFTY26SEP24200CE"] == 60000.0


def test_an_unusable_response_is_none_not_zero():
    payload = [{"tradingsymbol": "X"}]
    assert BMS._read_basket_response({}, payload) is None
    assert BMS._read_basket_response(None, payload) is None


# ---------------------------------------------------------------------------
# The nine scenarios: capture -> resolve -> consume
# ---------------------------------------------------------------------------

class _Savepoint:
    """
    Mirrors `AsyncSession.begin_nested()`. The real code reads inside a
    savepoint so that a failure - most importantly a missing table when
    migration 081 is unapplied - rolls back only that read and leaves the
    caller's transaction usable. A fake without this would let a bug through.
    """

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _FakeDB:
    """Stands in for the observation table. Append-only, like the real one."""

    def __init__(self, rows=None, raises=False):
        self.rows = list(rows or [])
        self.raises = raises

    def begin_nested(self):
        return _Savepoint()

    async def execute(self, *_a, **_k):
        if self.raises:
            raise RuntimeError(
                'relation "position_margin_observations" does not exist')
        rows = self.rows
        return SimpleNamespace(scalars=lambda: SimpleNamespace(
            first=lambda: rows[0] if rows else None))


def _obs(symbol, total, leg_count=1, per_leg=None, captured=NOW):
    return SimpleNamespace(
        broker_account_id=ACCOUNT, underlying="NIFTY", captured_at=captured,
        total=total, leg_count=leg_count, per_leg=per_leg or {},
        span=None, exposure=None, margin_source="broker")


async def _capital(trade, db):
    return await BMS.resolve_for_trade(trade, db)


@pytest.mark.asyncio
async def test_1_nifty_future_broker_value_reaches_the_risk_layer():
    trade = _trade("NIFTY26SEPFUT", "LONG", 65, 24349.0)
    cap = await _capital(trade, _FakeDB([_obs("NIFTY26SEPFUT", 178663.0)]))
    assert cap.source is MarginSource.BROKER
    assert cap.amount == pytest.approx(178663.0)

    rq = quantities_for_trade(trade, margin=cap)
    assert rq.usable_for_capital_rules
    assert rq.capital_requirement.amount == pytest.approx(178663.0)
    assert rq.capital_requirement.source is MarginSource.BROKER


@pytest.mark.asyncio
async def test_2_short_nifty_option_becomes_usable_only_with_broker_margin():
    trade = _trade("NIFTY26SEP24200CE", "SHORT", 65, 97.2)

    without = quantities_for_trade(trade, margin=None)
    assert not without.usable_for_capital_rules, "no margin -> abstain"

    cap = await _capital(trade, _FakeDB([_obs("NIFTY26SEP24200CE", 175747.0)]))
    with_broker = quantities_for_trade(trade, margin=cap)
    assert with_broker.usable_for_capital_rules
    assert with_broker.capital_requirement.amount == pytest.approx(175747.0)


def test_3_long_nifty_option_never_needed_broker_margin():
    """Definitional: the premium was paid in full. Works with no observation."""
    trade = _trade("NIFTY26SEP24200CE", "LONG", 65, 97.2)
    rq = quantities_for_trade(trade, margin=None)
    assert rq.usable_for_capital_rules
    assert rq.capital_requirement.amount == pytest.approx(97.2 * 65)
    assert rq.capital_requirement.source is MarginSource.COMPUTED


@pytest.mark.asyncio
async def test_4_defined_risk_spread_is_attributed_as_a_structure():
    """
    A structure's margin is not one leg's margin. The leg figure comes back,
    and the scope says 'structure' so a consumer cannot mistake one for the
    other.
    """
    trade = _trade("NIFTY26SEP24200CE", "SHORT", 65, 97.2)
    obs = _obs("NIFTY26SEP24200CE", 64174.0, leg_count=2,
               per_leg={"NIFTY26SEP24200CE": 60000.0,
                        "NIFTY26SEP24300CE": 4174.0})
    cap = await _capital(trade, _FakeDB([obs]))
    assert cap.source is MarginSource.BROKER
    assert cap.scope == "structure"
    assert cap.amount == pytest.approx(60000.0)
    assert "2-leg structure" in cap.note


@pytest.mark.asyncio
async def test_5_ratio_net_short_structure_resolves():
    trade = _trade("NIFTY26SEP24200CE", "SHORT", 130, 97.2)
    obs = _obs("NIFTY26SEP24200CE", 196757.0, leg_count=2,
               per_leg={"NIFTY26SEP24200CE": 190000.0,
                        "NIFTY26SEP24300CE": 6757.0})
    cap = await _capital(trade, _FakeDB([obs]))
    assert cap.amount == pytest.approx(190000.0)
    assert quantities_for_trade(trade, margin=cap).usable_for_capital_rules


@pytest.mark.asyncio
async def test_6_unsupported_multi_expiry_still_abstains_without_broker_data():
    """
    Broker capture must not quietly remove an existing safety guard. With no
    observation, a multi-expiry short is still unjudgeable.
    """
    trade = _trade("NIFTY26OCT24200CE", "SHORT", 65, 351.9)
    assert await _capital(trade, _FakeDB([])) is None
    assert not quantities_for_trade(trade, margin=None).usable_for_capital_rules

    from app.core.margin_model import Leg, Segment, compute_margin
    m = compute_margin(
        [Leg("OPT", -65, 351.9, 32, "CE", 24200.0, 65),
         Leg("OPT", 65, 470.0, 60, "CE", 24200.0, 65)],
        underlying=24341.9, annualised_vol=0.162, segment=Segment.INDEX)
    assert not m.reliable, "the COMPUTED guard stays regardless of broker capture"


@pytest.mark.asyncio
async def test_7_mcx_position_uses_the_broker_multiplier_and_broker_margin():
    trade = _trade("GOLDM26SEPFUT", "LONG", 1, 155999.0, exchange="MCX")

    # Entry value carries the multiplier: one lot of 100g quoted per 10g.
    assert quantities_for_trade(trade).entry_value.amount == pytest.approx(1_559_990.0)
    # And MCX capital, unavailable on its own, becomes available with a broker
    # figure - without ever applying NSE's scan ranges to bullion.
    obs = SimpleNamespace(broker_account_id=ACCOUNT, underlying="GOLDM",
                          captured_at=NOW, total=146073.0, leg_count=1,
                          per_leg={}, margin_source="broker")
    cap = await _capital(trade, _FakeDB([obs]))
    rq = quantities_for_trade(trade, margin=cap)
    assert rq.usable_for_capital_rules
    assert rq.capital_requirement.source is MarginSource.BROKER


@pytest.mark.asyncio
async def test_8_missing_broker_margin_abstains_and_never_substitutes():
    trade = _trade("NIFTY26SEPFUT", "LONG", 65, 24349.0)
    assert await _capital(trade, _FakeDB([])) is None
    rq = quantities_for_trade(trade, margin=None)
    assert not rq.usable_for_capital_rules
    assert rq.capital_requirement.amount is None
    # Never premium, never notional, never a percentage.
    assert rq.entry_value.amount == pytest.approx(24349.0 * 65)


@pytest.mark.asyncio
async def test_9_missing_table_or_query_failure_is_not_an_error():
    """
    Migration 081 may be unapplied. That must degrade to 'no observation', not
    break the engine: the risk layer then abstains, exactly where it is today.
    """
    trade = _trade("NIFTY26SEPFUT", "LONG", 65, 24349.0)
    assert await _capital(trade, _FakeDB(raises=True)) is None
    assert not quantities_for_trade(trade, margin=None).usable_for_capital_rules


@pytest.mark.asyncio
async def test_a_later_observation_never_applies_to_an_earlier_trade():
    """
    Observations are facts at a moment. A capture made after this trade closed
    belongs to a position it is no longer part of, so the cutoff is enforced in
    the query rather than left to the caller.
    """
    import inspect
    src = inspect.getsource(BMS.resolve_for_trade)
    assert "captured_at <= cutoff" in src.replace("PositionMarginObservation.", "")


def test_computed_never_overwrites_broker():
    """
    Provenance ordering, asserted directly: a supplied BROKER figure is what
    the risk layer reports, and nothing downgrades it.
    """
    trade = _trade("NIFTY26SEPFUT", "LONG", 65, 24349.0)
    broker = Capital(amount=178663.0, source=MarginSource.BROKER, scope="position")
    rq = quantities_for_trade(trade, margin=broker)
    assert rq.capital_requirement.source is MarginSource.BROKER
    assert rq.capital_requirement.amount == pytest.approx(178663.0)
