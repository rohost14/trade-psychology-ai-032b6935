"""
`direction_instability` is retired. These tests hold the retirement in place.

WHY IT WAS RETIRED (2026-08-28)

It could not separate an emotional reversal from a change of view, and what it
selected looked like the change of view.

Every CE<->PE transition on one underlying across the 189-session book:

    simultaneous (legs overlap - hedge/structure)   10   correctly excluded
    rapid        (sequential, gap < 10 min)         16   FLAGGED
    slow         (sequential, gap >= 10 min)        48   not flagged

So the only thing separating a flagged flip from an unflagged one was the clock -
and the clock sorted them backwards:

    flagged flip trade        n=16  win 56.2%   mean +Rs 276
    not flagged (gap >=10m)   n=48  win 41.7%   mean -Rs  73
    the position exited OUT of flagged -Rs 284 / 31% win  vs  +Rs 35 / 54% win

The trader reversed FAST when a position had gone badly and slowly when it had
not: cutting a loser. Sessions containing a flip ended +Rs 1,305 against -Rs 860
for no-flip sessions in the same trade-count band (p = 0.129), and rest-of-session
AFTER the first flip was +Rs 953 against -Rs 112 matched (p = 0.095) - the premise
predicts deterioration and the measurement showed improvement. Flagged flips were
flat-sized (median ratio 1.03), so there was no escalation story either.
`revenge_trade` already fired on 10 of the 18 firings.

Nothing reached p < 0.05 at n=16, but five independent measures pointed the same
way. An alert that fires on good decisions is worse than one that fires on noise.

THE CONCEPT IS NOT RETIRED PERMANENTLY

Level 1 - a same-symbol LONG<->SHORT reversal - was never testable on this book:
911 LONG against 1 SHORT, and zero same-symbol opposite-direction pairs at any
gap. It would be the live branch for a futures trader or an option seller.
Revisit with a book that contains shorts. No replacement detector and no
replacement threshold were introduced.

WHAT THESE TESTS COVER

  1. the detector cannot produce new events
  2. the adjacent detectors that own the real story are untouched
  3. historical rows stay readable
  4. no other detector's wiring moved

Full evidence in docs/patterns/11-direction_instability/.
"""

import io
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src"
APP = Path(__file__).resolve().parents[1] / "app"

RETIRED = "direction_instability"


# ── 1. it cannot generate new events ───────────────────────────────────────

def test_the_detector_method_is_gone():
    from app.services.behavior_engine import BehaviorEngine

    assert not hasattr(BehaviorEngine(), "_detect_direction_instability")


def test_it_is_not_in_the_registry_or_the_vocabulary():
    from app.services.detector_registry import (
        ALIASES,
        BY_NAME,
        REGISTRY,
        all_pattern_types,
    )

    assert RETIRED not in BY_NAME
    assert RETIRED not in ALIASES
    assert RETIRED not in all_pattern_types()
    assert all(d.name != RETIRED for d in REGISTRY)


def test_no_registry_spec_points_at_the_deleted_method():
    from app.services.behavior_engine import BehaviorEngine
    from app.services.detector_registry import REGISTRY

    engine = BehaviorEngine()
    for spec in REGISTRY:
        assert spec.method != "_detect_direction_instability"
        assert hasattr(engine, spec.method), f"{spec.name} points at a missing method"


def test_the_engine_counts_are_what_the_retirement_left():
    """
    20 detectors, 26 pattern types. Patterns 4, 6, 9, 10, 11, 14, 15 and 18 each took one of
    each (33 -> 26); the six aliases are untouched throughout.
    """
    from app.services.detector_registry import ALIASES, REGISTRY, all_pattern_types

    assert len(REGISTRY) == 20
    assert len(ALIASES) == 6
    assert len(all_pattern_types()) == 26


def test_it_is_recorded_as_retired():
    from tests.test_pattern_contract import RETIRED_PATTERN_NAMES

    assert RETIRED in RETIRED_PATTERN_NAMES


def test_both_thresholds_are_gone():
    """
    `rapid_flip_min` (registry + defaults + universal floor) and
    `direction_confusion_window_min` (defaults only, never registered).
    """
    from app.core.threshold_registry import THRESHOLD_SPECS
    from app.core.trading_defaults import COLD_START_DEFAULTS, UNIVERSAL_FLOORS

    for key in ("rapid_flip_min", "direction_confusion_window_min"):
        assert key not in COLD_START_DEFAULTS
        assert key not in THRESHOLD_SPECS
        assert key not in UNIVERSAL_FLOORS


def test_no_live_module_reads_either_threshold():
    offenders = []
    for path in APP.rglob("*.py"):
        if "__pycache__" in path.parts or "_archive" in path.parts:
            continue
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1
        ):
            if line.lstrip().startswith("#"):
                continue
            for key in ("rapid_flip_min", "direction_confusion_window_min"):
                if key in line:
                    offenders.append(f"{path.relative_to(APP)}:{lineno} {key}")
    assert offenders == [], f"deleted thresholds still read: {offenders}"


def test_it_is_gone_from_the_entry_decidable_list():
    from app.services.entry_detectors import ENTRY_DECIDABLE

    assert RETIRED not in ENTRY_DECIDABLE


def test_it_is_gone_from_the_strategy_suppression_set():
    """A suppression entry for a detector that cannot fire is dead config."""
    from app.services.behavior_engine import BehaviorEngine

    assert RETIRED not in BehaviorEngine._STRATEGY_SUPPRESSED


# ── 2. the detectors that own the real story are untouched ─────────────────

def test_revenge_trade_survives_and_is_still_frozen():
    """
    It fired on 10 of the 18 firings this detector produced, so it already owns
    the "reversed after a loss" reading. It is FROZEN by decision.
    """
    from app.services.behavior_engine import BehaviorEngine
    from app.services.detector_registry import BY_NAME

    assert "revenge_trade" in BY_NAME
    assert hasattr(BehaviorEngine(), "_detect_revenge_trade")


@pytest.mark.parametrize("name,method", [
    ("same_symbol_obsession", "_detect_same_symbol_obsession"),
    ("rapid_reentry", "_detect_rapid_reentry"),
    ("options_premium_avg_down", "_detect_options_premium_avg_down"),
])
def test_the_adjacent_detectors_survive(name, method):
    from app.services.behavior_engine import BehaviorEngine
    from app.services.detector_registry import BY_NAME

    assert name in BY_NAME
    assert hasattr(BehaviorEngine(), method)


def test_the_going_back_family_is_intact():
    """`direction_instability` was never in a family; removing it changes none."""
    from app.services.behavior_engine import BehaviorEngine

    fam = dict(BehaviorEngine._FAMILIES)
    assert fam["going back to the same trade"] == (
        "same_symbol_obsession", "revenge_trade", "rapid_reentry")
    assert all(RETIRED not in members for _, members in BehaviorEngine._FAMILIES)


# ── 3. historical rows stay readable ───────────────────────────────────────

@pytest.mark.parametrize("relpath,needle", [
    ("contexts/AlertContext.tsx", "'direction_instability': 'Direction flip-flop'"),
    ("components/patterns/BehaviourCostCard.tsx", "direction_instability:"),
    ("components/analytics/BehaviourLead.tsx", "direction_instability:"),
])
def test_the_frontend_can_still_render_a_stored_row(relpath, needle):
    path = SRC / relpath
    if not path.exists():
        pytest.skip(f"{path} not present")
    assert needle in io.open(path, encoding="utf-8").read(), (
        f"{relpath} lost its {RETIRED} entry; historical alerts would render "
        f"as a title-cased raw key"
    )


def test_the_frontend_never_claimed_the_engine_emits_it():
    """
    Unlike the other retirements, this pattern had no BACKEND_TO_FRONTEND_TYPE
    entry to remove — it was already absent. Pinned so one is not added later.
    """
    path = SRC / "contexts" / "AlertContext.tsx"
    if not path.exists():
        pytest.skip("AlertContext.tsx not present")
    text = io.open(path, encoding="utf-8").read()
    start = text.index("const BACKEND_TO_FRONTEND_TYPE")
    body = text[start:text.index("\n};", start)]
    assert RETIRED not in body


# ── 4. no other detector moved ─────────────────────────────────────────────

def test_no_other_detector_lost_its_worsen_metric():
    from app.tasks.trade_tasks import _WORSEN_METRIC

    assert _WORSEN_METRIC["martingale_behaviour"] == "max_ratio"
    assert _WORSEN_METRIC["premium_loss_event"] == "loss_pct"
    assert RETIRED not in _WORSEN_METRIC


def test_the_other_consolidation_families_are_untouched():
    from app.services.behavior_engine import BehaviorEngine

    fam = dict(BehaviorEngine._FAMILIES)
    assert fam["sizing after losses"] == (
        "martingale_behaviour", "post_loss_recovery_bet")
    assert fam["the position is too big"] == (
        "excess_exposure", "overexposure", "portfolio_concentration",
        "capital_mismatch")
    assert BehaviorEngine._COMPOSITES == ("death_spiral",)


def test_the_strategy_suppression_set_kept_its_other_members():
    from app.services.behavior_engine import BehaviorEngine

    for name in ("revenge_trade", "martingale_behaviour", "rapid_reentry",
                 "no_stoploss", "post_loss_recovery_bet"):
        assert name in BehaviorEngine._STRATEGY_SUPPRESSED


def test_every_surviving_detector_still_resolves():
    from app.services.behavior_engine import BehaviorEngine
    from app.services.detector_registry import REGISTRY

    engine = BehaviorEngine()
    missing = [d.name for d in REGISTRY if not hasattr(engine, d.method)]
    assert missing == [], f"registry specs with no method: {missing}"
