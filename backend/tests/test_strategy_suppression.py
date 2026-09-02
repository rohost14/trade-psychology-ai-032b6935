"""
F6 and F20 — what a multi-leg structure earns, and what it must not reach.

Two defects were closed together on 2026-09-02 because they were the same
mistake made twice: a detector's output was consumed by something that had no
business reading it.

F6. Suppression tested `ctx.strategy_group is not None` — PRESENCE, never the
    classification. So `MULTI_LEG_UNKNOWN` earned exactly what a recognised
    straddle earned, and on the reference book 71% of groups and 77% of
    suppressed legs were UNKNOWN. Worse, 70% of those UNKNOWN groups were the
    same option type, all bought, at adjacent strikes — a trader buying more of
    one directional view, which is the shape the suppressed detectors exist to
    see.

F20. `overexposure` read `BehaviorEvent` rows for `revenge_trade`,
     `martingale_behaviour` and `post_loss_recovery_bet` and escalated its own
     severity danger -> critical. The query never excluded SUPPRESSED events —
     and suppression is notification-only, so the rows exist. A suppressed
     revenge event sent the trader no alert and silently made a DIFFERENT alert
     critical.

The rule these tests protect:

    Suppression is a claim that the detector's SUBJECT DOES NOT EXIST inside
    this structure. It is not a volume control, and it is not a reward for
    being grouped.

So it is granted per detector, and only inside a structure we could actually
name. Everything else alerts as it always did.
"""
from types import SimpleNamespace

import pytest

from app.models.strategy_group import StrategyType
from app.services.behavior_engine import BehaviorEngine
from app.services.strategy_detector import (
    LegView, STRUCTURE_GAP_SECONDS, classify_legs,
)

engine = BehaviorEngine()

SUPPRESSED_IN_A_RECOGNISED_STRUCTURE = {
    "rapid_reentry",
    "post_loss_recovery_bet",
}
NEVER_SUPPRESSED_BY_STRUCTURE = {
    "revenge_trade",
    "no_stoploss",
    # `martingale_behaviour` left the set on 2026-09-02 (Q1). Not because
    # suppression was wrong for it, but because its SUBJECT CHANGED: inside a
    # recognised structure it now compares the structure's deployment against
    # the last comparable structure, and that claim is not defeated by the
    # legs being one construction. Suppressing it would have made the
    # structure-level branch unreachable — dead on arrival.
    "martingale_behaviour",
}


def group(strategy_type):
    """The only two fields the suppression path reads."""
    return SimpleNamespace(strategy_type=strategy_type, net_pnl=None)


def legs(*pairs):
    return [LegView(symbol, direction) for symbol, direction in pairs]


# ── A recognised structure suppresses three detectors, and only three ────────

@pytest.mark.parametrize("strategy_type", [
    StrategyType.STRADDLE_BUY,
    StrategyType.STRANGLE_BUY,
    StrategyType.BULL_CALL_SPREAD,
    StrategyType.IRON_CONDOR,
    StrategyType.IRON_BUTTERFLY,
    StrategyType.FUTURES_HEDGE_BULLISH,
])
@pytest.mark.parametrize("detector", sorted(SUPPRESSED_IN_A_RECOGNISED_STRUCTURE))
def test_a_recognised_structure_suppresses_the_construction_detectors(
    strategy_type, detector
):
    """
    These three read a SEQUENCE — a re-entry, an escalation, a sized-up bet
    after losses. Inside a named structure the legs are not a sequence, they
    are one construction, so the subject genuinely does not exist.
    """
    assert engine._structure_suppresses(group(strategy_type), detector) is True


@pytest.mark.parametrize("strategy_type", [
    StrategyType.STRADDLE_BUY,
    StrategyType.IRON_CONDOR,
    StrategyType.FUTURES_HEDGE_BULLISH,
])
@pytest.mark.parametrize("detector", sorted(NEVER_SUPPRESSED_BY_STRUCTURE))
def test_revenge_and_no_stoploss_survive_a_recognised_structure(
    strategy_type, detector
):
    """
    `revenge_trade`: its 20-minute window is WIDER than the 15-minute sibling
    window that groups the legs, so grouping systematically ate its subject —
    a loss at 10:05 and a different strike at 10:08 grouped, and the revenge
    finding vanished into the group that contained it.

    `no_stoploss`: being a leg of a structure says nothing about whether a stop
    existed. Suppressing it asserted that the structure IS the risk management,
    which is a claim nobody made and the data cannot support.
    """
    assert engine._structure_suppresses(group(strategy_type), detector) is False


# ── MULTI_LEG_UNKNOWN earns nothing ──────────────────────────────────────────

@pytest.mark.parametrize("detector", sorted(
    SUPPRESSED_IN_A_RECOGNISED_STRUCTURE | NEVER_SUPPRESSED_BY_STRUCTURE
))
def test_multi_leg_unknown_suppresses_nothing_at_all(detector):
    """
    The core of F6. UNKNOWN means "these legs are one decision and we cannot
    name the strategy" — an honest uncertainty state, and NOT grounds to claim
    a detector's subject does not exist. We do not know that. We do not know
    anything, which is what UNKNOWN says.
    """
    assert engine._structure_suppresses(
        group(StrategyType.MULTI_LEG_UNKNOWN), detector) is False


def test_ce_plus_ce_is_unknown_and_therefore_suppresses_nothing():
    """
    The measured majority case: 14 of the book's 27 UNKNOWN groups are two
    same-type long options at adjacent strikes. Two calls is not a straddle
    and never was — it is a second helping of one directional view.
    """
    shape = classify_legs(legs(("NIFTY25MAR24600CE", "LONG"),
                               ("NIFTY25MAR24700CE", "LONG")))
    assert shape == StrategyType.MULTI_LEG_UNKNOWN
    for detector in SUPPRESSED_IN_A_RECOGNISED_STRUCTURE | NEVER_SUPPRESSED_BY_STRUCTURE:
        assert engine._structure_suppresses(group(shape), detector) is False


def test_pe_plus_pe_is_unknown_too():
    shape = classify_legs(legs(("NIFTY25MAR25100PE", "LONG"),
                               ("NIFTY25MAR25150PE", "LONG")))
    assert shape == StrategyType.MULTI_LEG_UNKNOWN
    assert engine._structure_suppresses(group(shape), "martingale_behaviour") is False


def test_a_real_straddle_is_still_recognised_and_still_suppresses():
    """The other side: the case suppression was written for must keep working."""
    shape = classify_legs(legs(("NIFTY25MAR25000CE", "LONG"),
                               ("NIFTY25MAR25000PE", "LONG")))
    assert shape == StrategyType.STRADDLE_BUY
    assert engine._structure_suppresses(group(shape), "rapid_reentry") is True
    assert engine._structure_suppresses(group(shape), "revenge_trade") is False


# ── No group at all ──────────────────────────────────────────────────────────

def test_no_group_suppresses_nothing():
    for detector in SUPPRESSED_IN_A_RECOGNISED_STRUCTURE | NEVER_SUPPRESSED_BY_STRUCTURE:
        assert engine._structure_suppresses(None, detector) is False


def test_the_first_leg_to_close_is_deterministic_and_unsuppressed():
    """
    A `StrategyGroup` is written when the SECOND leg closes, so the first leg
    was analysed with `strategy_group=None`. That asymmetry is a property of
    the pipeline, not a rule, and it is pinned here so it is a known fact
    rather than a surprise: on the reference book it exempts 38 of 96
    structure legs by timing alone.
    """
    first_leg_ctx_group = None
    second_leg_ctx_group = group(StrategyType.STRADDLE_BUY)
    assert engine._structure_suppresses(first_leg_ctx_group, "rapid_reentry") is False
    assert engine._structure_suppresses(second_leg_ctx_group, "rapid_reentry") is True


def test_an_unset_or_malformed_strategy_type_is_treated_as_unknown():
    """Fail closed: if we cannot read the type, we have not recognised it."""
    for bad in (None, "", "something_we_never_defined"):
        assert engine._structure_suppresses(
            SimpleNamespace(strategy_type=bad, net_pnl=None), "rapid_reentry") is False
    assert engine._structure_suppresses(
        SimpleNamespace(net_pnl=None), "rapid_reentry") is False


# ── The suppression set itself ───────────────────────────────────────────────

def test_the_suppressed_set_is_exactly_its_two_members():
    """
    Pinned so a detector cannot be added to the set without someone stating
    why its subject cannot exist inside a structure — and so martingale cannot
    be added back without someone noticing it would kill the structure-level
    branch.
    """
    assert engine._STRATEGY_SUPPRESSED == SUPPRESSED_IN_A_RECOGNISED_STRUCTURE
    assert "martingale_behaviour" not in engine._STRATEGY_SUPPRESSED


def test_revenge_and_no_stoploss_are_not_in_the_set():
    for detector in NEVER_SUPPRESSED_BY_STRUCTURE:
        assert detector not in engine._STRATEGY_SUPPRESSED


# ── Grouping stays time-bound at 30 seconds ──────────────────────────────────

def test_the_structure_gap_is_still_thirty_seconds():
    """
    F6 is fixed in the suppression rule, NOT by widening the window. Raising it
    to 60s was measured on the reference book: it captures one real FUT+PE
    hedge and also collapses two genuine directional entries 35s apart into a
    "strangle". 120s collapses three more. The window stays where it is.
    """
    assert STRUCTURE_GAP_SECONDS == 30


# ── F20: a suppressed event must not reach another detector's severity ───────

def test_overexposure_no_longer_reads_other_detectors_output():
    """
    F20, closed by removal rather than by another exception.

    The emotional multiplier queried BehaviorEvent rows for three detectors and
    escalated `constitution_violation` danger -> critical. It never excluded
    suppressed events, and suppression is notification-only, so a finding the
    trader was NEVER TOLD ABOUT made a different alert louder.

    Adding "and not suppressed" to that query would have been the third patch
    on a dependency the architecture forbids outright: the registry states
    "no detector may consume another detector's output" (A.10). So the
    dependency is gone instead.

    Asserted against the source because the point is that the READ does not
    exist — a behavioural test can only show that one input does not move the
    output, which is a weaker claim.
    """
    from pathlib import Path

    import app.tasks.position_monitor_tasks as pmt

    source = Path(pmt.__file__).read_text(encoding="utf-8")
    assert "emotional_bump" not in source, (
        "the F20 emotional multiplier is back — a detector is consuming "
        "another detector's output again"
    )
    for detector in ("post_loss_recovery_bet", "martingale_behaviour", "revenge_trade"):
        assert f'"{detector}"' not in source, (
            f"position_monitor_tasks references {detector} again; F20 was closed "
            f"by removing the cross-detector read, not by filtering it"
        )


def test_behavior_event_is_not_imported_for_severity_decisions():
    """
    The narrower pin: `overexposure`'s path must not read the events table at
    all. `BehaviorEvent` may still be WRITTEN elsewhere — this is about the
    severity decision consuming it.
    """
    from pathlib import Path

    import app.tasks.position_monitor_tasks as pmt

    source = Path(pmt.__file__).read_text(encoding="utf-8")
    assert "BehaviorEvent.detector.in_" not in source


# ── An unrecognised cluster is not persisted as a structure at all ───────────
#
# The deeper fix, 2026-09-02. F6 stopped MULTI_LEG_UNKNOWN from EARNING
# suppression; this stops it from being a group in the first place, which is
# what it always was: two calls bought a minute apart are two directional
# trades, not a mystery spread.
#
# It closes three presence-only consumers at the source rather than teaching
# each of them to re-check the classification.

def test_two_calls_are_not_a_structure_and_never_were():
    """
    The shape that made 70% of the book's UNKNOWN groups. A multi-leg structure
    is legs of different kinds placed together — a call and a put, or a buy and
    a sell of one kind. Two long calls at adjacent strikes is neither.
    """
    assert classify_legs(legs(("NIFTY25MAR24600CE", "LONG"),
                              ("NIFTY25MAR24700CE", "LONG"))) == \
        StrategyType.MULTI_LEG_UNKNOWN


def test_detect_and_save_returns_none_for_an_unrecognised_cluster():
    """
    Asserted on the source because the alternative is a full DB fixture for a
    path whose whole content is one early return. The guard must sit BEFORE the
    StrategyGroup is constructed — after it, the row exists and every
    presence-only consumer has already been misled.
    """
    import inspect

    from app.services import strategy_detector

    src = inspect.getsource(strategy_detector.detect_and_save)
    guard = src.index("MULTI_LEG_UNKNOWN")
    build = src.index("group = StrategyGroup(")
    assert guard < build, (
        "the unrecognised-cluster guard must run before the group is built"
    )
    assert "return None" in src[guard:build]


def test_the_two_grouping_paths_now_agree():
    """
    `count_structures` has always refused to collapse an unrecognised cluster;
    `detect_and_save` used to group one anyway. That was the same input read
    with opposite conservatism by two halves of one engine.
    """
    import inspect

    from app.services import strategy_detector

    for fn in (strategy_detector.detect_and_save, strategy_detector.count_structures):
        assert "MULTI_LEG_UNKNOWN" in inspect.getsource(fn)


def test_a_recognised_structure_is_still_grouped():
    """The guard must not swallow the case grouping exists for."""
    import inspect

    from app.services import strategy_detector

    src = inspect.getsource(strategy_detector.detect_and_save)
    assert "group = StrategyGroup(" in src
    assert "await db.commit()" in src
