"""
E2 — counting structures instead of legs, and classifying open positions.

A CompletedTrade is per tradingsymbol, so one four-leg iron condor is four rows.
Every detector that counted trades was counting legs: two condors read as eight
trades against a burst threshold of five, and a spread trader collected a
danger-severity overtrading alert for holding two positions.

The property these tests protect: **`count <= len(legs)`**, always. A cluster
collapses to one only when it classifies as a recognised strategy, so a trader
who never trades multi-leg sees exactly the numbers they saw before.

This file used to claim something stronger — "the count can only fall" — and
B1 (2026-09-02) disproved it. Correcting a misnamed structure to
MULTI_LEG_UNKNOWN makes the count RISE against the previous behaviour, which
is right, because the structure was two decisions all along. A classification
change is measured, never assumed conservative.
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
    """
    A real iron condor: four legs entered within two seconds of each other,
    the body SOLD and the wings BOUGHT.

        buy  24100 PE   ── wing
        sell 24300 PE   ┐
        sell 24500 CE   ┘ body
        buy  24700 CE   ── wing

    The call side was inverted here until 2026-09-02 — it read `sell CE_HI,
    buy CE_LO`, which is a bull call *debit* spread with the long inside the
    short, not a condor's short call spread. It classified as `iron_condor`
    only because the classifier tested leg count and mixed direction and
    never looked at the strikes, so the fixture and the bug agreed with each
    other. Corrected here rather than asserting less.
    """
    return [
        trade(CE_HI, "LONG", offset_seconds + 0),
        trade(CE_LO, "SHORT", offset_seconds + 1),
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


# ── The safety property: count <= leg count ───────────────────────────────

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
    """
    The one permanent invariant. NOT "the count only falls" — see the module
    docstring; B1 raises it for a structure that was never one decision.
    """
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
    positions = [position(CE_HI, 50), position(CE_LO, -50),
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
        # Same corrected shape as condor() above — body sold, wings bought.
        # This list had the call side inverted too; it is spelled out here
        # rather than reusing the helper because the engine needs a
        # CompletedTrade, not the SimpleNamespace count_structures accepts.
        for sym, side in ((CE_HI, "LONG"), (CE_LO, "SHORT"), (PE_HI, "SHORT"), (PE_LO, "LONG")):
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


# ── Classifier correctness — B1, B2, B3 (2026-09-02) ─────────────────────────
#
# Three defects, all measured before the fix and all shipping the same failure:
# the classifier named a structure without reading the property that defines it.
#
#   B1  the futures-hedge branch read the option's TYPE and never its
#       DIRECTION, so selling a put against a long future — which adds
#       downside risk — carried the label written for buying one.
#   B2  the iron-butterfly branch sat below a condor test that every real
#       butterfly also satisfies, so it was unreachable, and the only shape
#       that could reach it (four legs in one direction) is not a butterfly.
#   B3  the condor test read leg count and mixed direction only. Any four
#       mixed-direction CE/PE legs matched it, including the inverted
#       structure whose risk runs the other way.
#
# These tests pin the STRUCTURE, not the count. What a named structure then
# earns — suppression, collapsing to one decision — is a separate question
# and is deliberately not asserted here.

FUT = "RELIANCE25MARFUT"
FUT_CE = "RELIANCE25MAR2900CE"
FUT_PE = "RELIANCE25MAR2900PE"

# One expiry, four strikes for a condor and three for a butterfly.
IC_LONG_PUT, IC_SHORT_PUT = "NIFTY25MAR24600PE", "NIFTY25MAR24800PE"
IC_SHORT_CALL, IC_LONG_CALL = "NIFTY25MAR25200CE", "NIFTY25MAR25400CE"
IB_BODY_CE, IB_BODY_PE = "NIFTY25MAR25000CE", "NIFTY25MAR25000PE"
IB_WING_CE, IB_WING_PE = "NIFTY25MAR25400CE", "NIFTY25MAR24600PE"


def legs(*pairs):
    return [LegView(symbol, direction) for symbol, direction in pairs]


# ── B3: the condor must be a condor ──────────────────────────────────────────

def test_a_valid_iron_condor_is_an_iron_condor():
    """Body sold inside, wings bought outside: 24600 < 24800 < 25200 < 25400."""
    assert classify_legs(legs(
        (IC_SHORT_CALL, "SHORT"), (IC_LONG_CALL, "LONG"),
        (IC_SHORT_PUT, "SHORT"), (IC_LONG_PUT, "LONG"),
    )) == StrategyType.IRON_CONDOR


def test_an_inverted_condor_is_not_an_iron_condor():
    """
    Every leg's direction flipped: the body is BOUGHT and the wings are SOLD.
    Same four strikes, same leg count, same mixed direction — and the opposite
    risk profile. This is the case the old test could not tell from the real
    one, because it never looked at which strikes were sold.
    """
    assert classify_legs(legs(
        (IC_SHORT_CALL, "LONG"), (IC_LONG_CALL, "SHORT"),
        (IC_SHORT_PUT, "LONG"), (IC_LONG_PUT, "SHORT"),
    )) == StrategyType.MULTI_LEG_UNKNOWN


def test_four_mixed_direction_option_legs_are_not_automatically_a_condor():
    """
    Three calls and a put, mixed direction. It satisfies every condition the
    old branch tested and is not a condor by any reading.
    """
    assert classify_legs(legs(
        ("NIFTY25MAR25000CE", "LONG"), ("NIFTY25MAR25200CE", "LONG"),
        ("NIFTY25MAR25400CE", "SHORT"), (IC_LONG_PUT, "LONG"),
    )) == StrategyType.MULTI_LEG_UNKNOWN


def test_four_legs_at_one_strike_are_not_a_condor():
    """A bought and sold call and put at one strike is a box, not a condor."""
    assert classify_legs(legs(
        (IB_BODY_CE, "LONG"), (IB_BODY_CE, "SHORT"),
        (IB_BODY_PE, "LONG"), (IB_BODY_PE, "SHORT"),
    )) == StrategyType.MULTI_LEG_UNKNOWN


# ── B2: the butterfly must be reachable, and only by a butterfly ─────────────

def test_a_valid_iron_butterfly_is_an_iron_butterfly():
    """
    The body is sold at ONE strike — that single fact is what separates a
    butterfly from a condor, and it is why the two are decided together.
    Before the fix this returned `iron_condor`.
    """
    assert classify_legs(legs(
        (IB_BODY_CE, "SHORT"), (IB_BODY_PE, "SHORT"),
        (IB_WING_CE, "LONG"), (IB_WING_PE, "LONG"),
    )) == StrategyType.IRON_BUTTERFLY


def test_four_legs_in_one_direction_at_three_strikes_are_not_a_butterfly():
    """
    The only shape that could reach the old butterfly branch. An iron
    butterfly sells its body; four bought legs sell nothing.
    """
    assert classify_legs(legs(
        (IB_BODY_CE, "LONG"), (IB_BODY_PE, "LONG"),
        (IB_WING_CE, "LONG"), (IB_WING_PE, "LONG"),
    )) == StrategyType.MULTI_LEG_UNKNOWN


def test_a_butterfly_is_not_reported_as_a_condor():
    """The regression B2 names, stated directly."""
    butterfly = classify_legs(legs(
        (IB_BODY_CE, "SHORT"), (IB_BODY_PE, "SHORT"),
        (IB_WING_CE, "LONG"), (IB_WING_PE, "LONG"),
    ))
    assert butterfly != StrategyType.IRON_CONDOR


# ── B1: a hedge is an option you BOUGHT ──────────────────────────────────────

def test_long_future_with_a_bought_put_is_a_bullish_hedge():
    assert classify_legs(legs(
        (FUT, "LONG"), (FUT_PE, "LONG"),
    )) == StrategyType.FUTURES_HEDGE_BULLISH


def test_long_future_with_a_sold_put_is_not_a_hedge():
    """
    Short put under a long future: the premium is the whole cushion and the
    downside stays open. It carried `futures_hedge_bullish` — the label, and
    everything a label earns — until 2026-09-02.
    """
    assert classify_legs(legs(
        (FUT, "LONG"), (FUT_PE, "SHORT"),
    )) == StrategyType.MULTI_LEG_UNKNOWN


def test_short_future_with_a_bought_call_is_a_bearish_hedge():
    assert classify_legs(legs(
        (FUT, "SHORT"), (FUT_CE, "LONG"),
    )) == StrategyType.FUTURES_HEDGE_BEARISH


def test_short_future_with_a_sold_call_is_not_a_hedge():
    """The bearish mirror of the same defect."""
    assert classify_legs(legs(
        (FUT, "SHORT"), (FUT_CE, "SHORT"),
    )) == StrategyType.MULTI_LEG_UNKNOWN


def test_the_other_four_future_option_combinations_are_still_unknown():
    """Unchanged by this fix, pinned so the branch cannot widen by accident."""
    for fut_direction, option, option_direction in (
        ("LONG", FUT_CE, "LONG"), ("LONG", FUT_CE, "SHORT"),
        ("SHORT", FUT_PE, "LONG"), ("SHORT", FUT_PE, "SHORT"),
    ):
        assert classify_legs(legs(
            (FUT, fut_direction), (option, option_direction),
        )) == StrategyType.MULTI_LEG_UNKNOWN


def test_two_leg_structures_are_untouched_by_the_four_leg_correction():
    """The correction is scoped to FUT pairs and 4-leg CE/PE sets."""
    cases = {
        StrategyType.STRADDLE_BUY: ((IB_BODY_CE, "LONG"), (IB_BODY_PE, "LONG")),
        StrategyType.STRANGLE_SELL: ((IC_SHORT_CALL, "SHORT"), (IC_SHORT_PUT, "SHORT")),
        StrategyType.SYNTHETIC_LONG: ((IB_BODY_CE, "LONG"), (IB_BODY_PE, "SHORT")),
        StrategyType.BEAR_CALL_SPREAD: ((IC_SHORT_CALL, "SHORT"), (IC_LONG_CALL, "LONG")),
    }
    for expected, pairs in cases.items():
        assert classify_legs(legs(*pairs)) == expected


def test_a_risk_adding_future_option_pair_counts_as_two_decisions():
    """
    B1's consequence for counting, pinned deliberately rather than discovered
    later. FUT LONG + PE SHORT was named `futures_hedge_bullish` and collapsed
    to one decision. It is not a hedge, so it is MULTI_LEG_UNKNOWN, and an
    unrecognised cluster stays as its legs — two.

    This is the case that disproves "the count can only fall". The rise is
    correct: selling a put under a long future was always two decisions.
    """
    trades = [trade(FUT, "LONG", 0), trade(FUT_PE, "SHORT", 2)]
    assert classify_legs(legs((FUT, "LONG"), (FUT_PE, "SHORT"))) == \
        StrategyType.MULTI_LEG_UNKNOWN
    assert count_structures(trades) == 2


def test_a_real_futures_hedge_still_counts_as_one_decision():
    """The other side of B1: buying the put is one decision, and stays one."""
    trades = [trade(FUT, "LONG", 0), trade(FUT_PE, "LONG", 2)]
    assert count_structures(trades) == 1


def test_unknown_is_a_state_not_a_failure():
    """
    MULTI_LEG_UNKNOWN must be reachable and must behave like a real answer:
    it has a trader-facing label, and it keeps the legs visible as separate
    decisions rather than silently discarding them.
    """
    from app.services.strategy_detector import strategy_label

    assert strategy_label(StrategyType.MULTI_LEG_UNKNOWN) == "Multi-leg position"
    ratio = legs((CE_LO, "LONG"), (CE_LO, "LONG"), (CE_HI, "SHORT"))
    assert classify_legs(ratio) == StrategyType.MULTI_LEG_UNKNOWN
