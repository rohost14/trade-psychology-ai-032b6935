"""
E2 — counting structures instead of legs, and classifying open positions.

A CompletedTrade is per tradingsymbol, so one four-leg iron condor is four rows.
Every detector that counted trades was counting legs: two condors read as eight
trades against a burst threshold of five, and a spread trader collected a
danger-severity overtrading alert for holding two positions.

The safety property these tests exist to protect: **the count can only fall.**
A cluster collapses to one only when it classifies as a recognised strategy, so
a trader who never trades multi-leg sees exactly the numbers they saw before.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.models.strategy_group import StrategyType
from app.services.strategy_detector import (
    LegView, classify_legs, classify_open_positions, cluster_legs, count_structures,
)

BASE = datetime(2026, 8, 6, 10, 0, tzinfo=timezone.utc)

# One weekly NIFTY expiry, four strikes.
CE_LO, CE_HI = "NIFTY25AUG24500CE", "NIFTY25AUG24700CE"
PE_HI, PE_LO = "NIFTY25AUG24300PE", "NIFTY25AUG24100PE"


def trade(symbol: str, direction: str = "LONG", seconds: int = 0, qty: int = 50):
    return SimpleNamespace(
        tradingsymbol=symbol,
        direction=direction,
        entry_time=BASE + timedelta(seconds=seconds),
        total_quantity=qty,
        realized_pnl=0,
    )


def condor(offset_seconds: int = 0):
    """Four legs, entered within two seconds of each other."""
    return [
        trade(CE_HI, "SHORT", offset_seconds + 0),
        trade(CE_LO, "LONG", offset_seconds + 1),
        trade(PE_HI, "SHORT", offset_seconds + 1),
        trade(PE_LO, "LONG", offset_seconds + 2),
    ]


# ── The regression ───────────────────────────────────────────────────────────

def test_one_condor_counts_as_one_decision():
    assert count_structures(condor()) == 1


def test_two_condors_count_as_two_not_eight():
    """
    The exact case that fired danger-severity overtrading for two positions:
    eight legs against a burst danger threshold of eight.
    """
    trades = condor(0) + condor(600)
    assert len(trades) == 8
    assert count_structures(trades) == 2


def test_a_straddle_counts_as_one():
    legs = [trade(CE_LO, "LONG", 0), trade("NIFTY25AUG24500PE", "LONG", 1)]
    assert count_structures(legs) == 2 - 1


def test_a_vertical_spread_counts_as_one():
    legs = [trade(CE_LO, "LONG", 0), trade(CE_HI, "SHORT", 1)]
    assert count_structures(legs) == 1


# ── The safety property: the count can only fall ─────────────────────────────

def test_single_leg_trading_is_completely_unchanged():
    """A directional trader must see exactly the old numbers."""
    trades = [trade(CE_LO, "LONG", i * 300) for i in range(7)]
    assert count_structures(trades) == 7


def test_repeat_entries_on_one_symbol_are_separate_decisions():
    """
    A scalper taking the same strike three times in a minute is overtrading, not
    a three-leg structure. Without the distinct-symbol rule their behaviour
    would vanish from the count entirely.
    """
    trades = [trade(CE_LO, "LONG", 0), trade(CE_LO, "LONG", 20), trade(CE_LO, "LONG", 40)]
    assert count_structures(trades) == 3


def test_two_directional_trades_close_together_are_not_a_structure():
    """
    Same underlying, same expiry, different strikes, both long — this is not a
    recognised strategy, so it must stay two decisions rather than becoming a
    mystery spread.
    """
    trades = [trade(CE_LO, "LONG", 0), trade(CE_HI, "LONG", 30)]
    assert classify_legs([LegView(CE_LO, "LONG"), LegView(CE_HI, "LONG")]) == \
        StrategyType.MULTI_LEG_UNKNOWN
    assert count_structures(trades) == 2


def test_structures_far_apart_in_time_do_not_merge():
    """A spread at 10:00 and another at 10:30 are two decisions."""
    trades = [trade(CE_LO, "LONG", 0), trade(CE_HI, "SHORT", 1),
              trade(CE_LO, "LONG", 1800), trade(CE_HI, "SHORT", 1801)]
    assert count_structures(trades) == 2


def test_different_underlyings_never_merge():
    trades = [trade(CE_LO, "LONG", 0), trade("BANKNIFTY25AUG52000CE", "SHORT", 1)]
    assert count_structures(trades) == 2


def test_the_count_never_exceeds_the_leg_count():
    """The property that makes this change safe to ship without shadow mode."""
    for trades in (condor(), condor(0) + condor(600),
                   [trade(CE_LO, "LONG", i * 10) for i in range(5)],
                   []):
        assert count_structures(trades) <= len(trades)


# ── Degenerate input ─────────────────────────────────────────────────────────

def test_empty_list_counts_zero():
    assert count_structures([]) == 0


def test_trades_without_entry_time_are_counted_individually():
    """Never guess. An unparseable trade is its own decision."""
    orphan = SimpleNamespace(tradingsymbol=CE_LO, direction="LONG",
                             entry_time=None, total_quantity=50)
    assert count_structures([orphan, orphan]) == 2


def test_equity_symbols_are_counted_individually():
    """No expiry, so no structure — RELIANCE is not a leg of anything."""
    eq = [trade("RELIANCE", "LONG", 0), trade("RELIANCE", "LONG", 10)]
    assert count_structures(eq) == 2


# ── Clustering ───────────────────────────────────────────────────────────────

def test_cluster_keeps_the_legs_of_one_structure_together():
    clusters = cluster_legs(condor())
    assert len(clusters) == 1
    assert len(clusters[0]) == 4


def test_cluster_splits_on_a_repeated_symbol():
    trades = [trade(CE_LO, "LONG", 0), trade(CE_HI, "SHORT", 1), trade(CE_LO, "LONG", 2)]
    assert len(cluster_legs(trades)) == 2


# ── Entry-time classification from open positions ────────────────────────────

def position(symbol: str, qty: int):
    return SimpleNamespace(tradingsymbol=symbol, total_quantity=qty)


def test_open_positions_classify_as_an_iron_condor():
    """
    What the exit-time detector cannot do: recognise the structure while every
    leg is still open.
    """
    positions = [position(CE_HI, -50), position(CE_LO, 50),
                 position(PE_HI, -50), position(PE_LO, 50)]
    structures = classify_open_positions(positions)
    assert len(structures) == 1
    assert structures[0]["strategy_type"] == StrategyType.IRON_CONDOR
    assert structures[0]["leg_count"] == 4
    assert structures[0]["underlying"] == "NIFTY"


def test_direction_comes_from_the_sign_of_the_quantity():
    """A negative quantity is a short leg — that is all the classifier needs."""
    positions = [position(CE_LO, 50), position(CE_HI, -50)]
    structures = classify_open_positions(positions)
    assert len(structures) == 1
    assert structures[0]["strategy_type"] == StrategyType.BULL_CALL_SPREAD


def test_a_single_open_position_is_not_a_structure():
    assert classify_open_positions([position(CE_LO, 50)]) == []


def test_closed_positions_are_ignored():
    positions = [position(CE_LO, 0), position(CE_HI, 0)]
    assert classify_open_positions(positions) == []


def test_unrecognised_combinations_are_omitted():
    """A maybe is not useful for suppressing a false positive."""
    positions = [position(CE_LO, 50), position(CE_HI, 50)]
    assert classify_open_positions(positions) == []


def test_positions_in_different_underlyings_do_not_form_a_structure():
    positions = [position(CE_LO, 50), position("BANKNIFTY25AUG52000CE", -50)]
    assert classify_open_positions(positions) == []


# ── The detector actually uses it ────────────────────────────────────────────
# The unit tests above prove count_structures is right. These prove the burst
# detector reaches it — the counting fix is worthless if the detector still
# calls len().

def _engine_ct(symbol, direction, minutes_ago, pnl=-500.0):
    """A CompletedTrade shaped the way the engine's own tests shape one."""
    from decimal import Decimal
    from unittest.mock import MagicMock
    from uuid import uuid4

    from app.models.completed_trade import CompletedTrade

    now = datetime.now(timezone.utc)
    ct = MagicMock(spec=CompletedTrade)
    ct.id = uuid4()
    ct.tradingsymbol = symbol
    ct.exchange = "NFO"
    ct.direction = direction
    ct.instrument_type = symbol[-2:]
    ct.realized_pnl = Decimal(str(pnl))
    ct.total_quantity = 50
    ct.entry_time = now - timedelta(minutes=minutes_ago)
    ct.exit_time = now - timedelta(minutes=max(minutes_ago - 1, 0))
    return ct


def _burst(trades):
    """Run the burst detector over `trades`, newest last, and return the event."""
    from tests.test_behavior_engine import engine, make_ctx, make_session

    ctx = make_ctx(
        completed_trade=trades[-1],
        session_trades=trades[:-1],
        session=make_session(session_pnl=-5000.0),
        thresholds={"burst_trades_per_30min_caution": 5,
                    "burst_trades_per_30min_danger": 8,
                    "daily_trade_limit": 99, "daily_trade_danger": 99},
    )
    return engine._detect_overtrading_burst(ctx)


def test_burst_detector_counts_two_condors_as_two_not_eight():
    """
    Eight legs, danger threshold eight. Before E2 this fired danger; a trader
    holding two positions was told they had opened eight.
    """
    trades = []
    for base in (10, 5):
        for sym, side in ((CE_HI, "SHORT"), (CE_LO, "LONG"), (PE_HI, "SHORT"), (PE_LO, "LONG")):
            trades.append(_engine_ct(sym, side, base))
    assert len(trades) == 8
    assert _burst(trades) is None


def test_burst_detector_still_fires_on_real_single_leg_overtrading():
    """The other half: eight genuinely separate trades must still be caught."""
    trades = [
        _engine_ct(f"NIFTY25AUG2{4000 + i * 100}CE", "LONG", 20 - i * 2)
        for i in range(8)
    ]
    event = _burst(trades)
    assert event is not None
    assert event.event_type == "overtrading_burst"
    assert event.severity == "danger"


def test_burst_evidence_keeps_the_leg_count():
    """
    A trader looking at the evidence must still be able to see their fills —
    the threshold counts decisions, the evidence shows what happened.
    """
    trades = [
        _engine_ct(f"NIFTY25AUG2{4000 + i * 100}CE", "LONG", 20 - i * 2)
        for i in range(8)
    ]
    event = _burst(trades)
    assert event.context["legs_in_window"] == 8
    assert event.context["trades_in_window"] == 8


# ── Labels for the positions table (Phase 6) ─────────────────────────────────

def test_every_strategy_type_has_a_trader_facing_label():
    """
    A label map on the frontend keyed on backend strings is the drift that
    produced the empty alert panel. These live beside the values they name.
    """
    from app.services.strategy_detector import STRATEGY_LABELS, strategy_label

    for attr in dir(StrategyType):
        if attr.startswith("_"):
            continue
        value = getattr(StrategyType, attr)
        if isinstance(value, str):
            assert value in STRATEGY_LABELS, f"{value} has no label"
            assert strategy_label(value) == STRATEGY_LABELS[value]


def test_an_unknown_strategy_type_still_reads_as_something():
    from app.services.strategy_detector import strategy_label

    assert strategy_label("some_new_structure") == "Some new structure"
    assert strategy_label("") == "Position"


def test_classified_structures_carry_their_label():
    positions = [position(CE_LO, 50), position(CE_HI, -50)]
    structure = classify_open_positions(positions)[0]
    assert structure["label"] == "Bull call spread"
