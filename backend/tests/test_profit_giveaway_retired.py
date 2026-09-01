"""
`profit_giveaway` is retired. These tests hold the retirement in place.

WHY IT WAS RETIRED (2026-08-27)

A drawdown from the session high-water mark is arithmetic, not behaviour. The
peak is by definition the maximum of the running curve, so 181 of 189 sessions
contain a giveback. Shuffling each session's trade order - same trades, same
day, different sequence - produced MORE firings than the real order (49 observed
against 56.3 expected, ratio 0.87) and an identical amount of money given back
(Rs 624,839 against Rs 616,891, ratio 1.01). The trader's ordering contributed
nothing.

Every mechanism it was premised on failed as well. House money predicts risk
RISING after a peak; this trader's risk fell in 54% of sessions (median
Rs 7,315 -> Rs 6,737). The break-even effect predicts that crossing zero changes
behaviour; measured against a size-matched loss that did not cross, it was
0.6 SE against a ~1.4 floor. The median giveback puts 77% of its loss in a
single trade, which is what a losing trade is.

WHAT THESE TESTS COVER

  1. the detector cannot produce new events
  2. historical rows stay readable
  3. no other detector's wiring moved

The measurement itself is kept and tested separately in
test_daily_report_giveback.py. Full evidence in
docs/patterns/06-profit_giveaway/.
"""

import io
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src"


# ── 1. it cannot generate new events ───────────────────────────────────────

def test_the_detector_method_is_gone():
    from app.services.behavior_engine import BehaviorEngine

    assert not hasattr(BehaviorEngine(), "_detect_profit_giveaway")


def test_it_is_not_in_the_registry_or_the_vocabulary():
    from app.services.detector_registry import (
        ALIASES, BY_NAME, all_pattern_types, pattern_copy,
    )

    assert "profit_giveaway" not in BY_NAME
    assert "profit_giveaway" not in ALIASES
    assert "profit_giveaway" not in all_pattern_types()
    assert pattern_copy("profit_giveaway") is None


def test_no_registry_spec_points_at_the_deleted_method():
    """A spec naming a missing method would log an error on every trade."""
    from app.services.behavior_engine import BehaviorEngine
    from app.services.detector_registry import REGISTRY

    engine = BehaviorEngine()
    missing = [s.name for s in REGISTRY if not hasattr(engine, s.method)]
    assert missing == []


def test_the_engine_counts_are_what_the_retirement_left():
    from app.services.detector_registry import REGISTRY, all_pattern_types

    # 20 / 26 since `early_exit` was retired 2026-08-30 (Pattern 18).
    assert len(REGISTRY) == 16
    assert len(all_pattern_types()) == 22


def test_it_is_recorded_as_retired():
    from tests.test_pattern_contract import RETIRED_PATTERN_NAMES

    assert "profit_giveaway" in RETIRED_PATTERN_NAMES


# ── 2. historical rows stay readable ───────────────────────────────────────
#
# Stored RiskAlert rows still carry pattern_type='profit_giveaway'. Every
# surface that renders one has to keep its entry, or a real trader's history
# renders as a title-cased raw key.

def test_the_weekly_report_can_still_label_a_stored_row():
    import inspect

    from app.tasks import report_tasks

    assert '"profit_giveaway": "Profit Giveaway"' in inspect.getsource(report_tasks)


@pytest.mark.parametrize("relpath,needle", [
    ("contexts/AlertContext.tsx", "'profit_giveaway':               'Profit Giveaway'"),
    ("types/patterns.ts", "'profit_giveaway'"),
    ("components/alerts/AlertDetailSheet.tsx", "case 'profit_giveaway':"),
    ("components/patterns/BehaviourCostCard.tsx", "profit_giveaway:"),
    ("components/analytics/BehaviourLead.tsx", "profit_giveaway:"),
])
def test_the_frontend_can_still_render_a_stored_row(relpath, needle):
    path = SRC / relpath
    if not path.exists():
        pytest.skip(f"{path} not present")
    assert needle in io.open(path, encoding="utf-8").read(), (
        f"{relpath} lost its profit_giveaway entry; historical alerts would "
        f"render as a title-cased raw key"
    )


def test_the_frontend_no_longer_claims_the_engine_emits_it():
    """
    The other direction: BACKEND_TO_FRONTEND_TYPE maps live pattern types, and
    a dead entry there reads as though the engine still produces them.
    """
    path = SRC / "contexts" / "AlertContext.tsx"
    if not path.exists():
        pytest.skip("AlertContext.tsx not present")
    text = io.open(path, encoding="utf-8").read()
    start = text.index("const BACKEND_TO_FRONTEND_TYPE")
    body = text[start:text.index("\n};", start)]
    assert "profit_giveaway" not in body


# ── 3. no other detector moved ─────────────────────────────────────────────

def test_no_other_detector_lost_its_worsen_metric():
    from app.tasks.trade_tasks import _WORSEN_METRIC

    assert set(_WORSEN_METRIC) == {
        "martingale_behaviour", "premium_loss_event", "constitution_violation",
    }


def test_the_two_surviving_per_episode_dedup_keys_are_intact():
    from app.tasks.trade_tasks import _pattern_dedup_key

    assert (_pattern_dedup_key("constitution_violation", {"rule": "daily_loss"})
            == "constitution_violation:daily_loss")
    assert (_pattern_dedup_key("same_symbol_obsession", {"underlying": "NIFTY"})
            == "same_symbol_obsession:NIFTY")


@pytest.mark.parametrize("pattern", [
    "martingale_behaviour", "revenge_trade", "adding_to_adverse_position",
    "post_loss_recovery_bet", "daily_overtrading", "overtrading_burst",
    "session_meltdown", "fomo_entry",
])
def test_every_other_pattern_still_keys_on_its_type_alone(pattern):
    from app.tasks.trade_tasks import _pattern_dedup_key

    assert _pattern_dedup_key(pattern, {"peak_pnl": 5000}) == pattern


def test_the_consolidation_families_are_untouched():
    from app.services.behavior_engine import BehaviorEngine

    names = {n for _, members in BehaviorEngine._FAMILIES for n in members}
    assert "profit_giveaway" not in names
    assert "martingale_behaviour" in names and "same_symbol_obsession" in names


def test_death_spiral_still_has_its_emotional_domain():
    """
    death_spiral counts nature-domains off the registry. Removing an `emotional`
    detector must not leave that domain unable to contribute.

    REWRITTEN 2026-08-27 (Pattern #10). The assertion was `len(emotional) >= 12`
    — a raw NAME count, which is the wrong measure and goes stale on every
    justified retirement. death_spiral only counts events at **danger or above**
    (`spiral_domain_min_severity = "danger"`), so a `caution`-only or `info`-only
    detector is invisible to it however many of them exist. Six of the eleven
    emotional detectors can never contribute at all.

    What actually has to hold is that the domain retains detectors that CAN
    reach danger+. `size_escalation`, retired that day, emitted exactly one
    severity — `caution` — so it was never among them and its removal changed
    this number by zero. Same for `profit_giveaway` before it.
    """
    import inspect
    import re

    from app.services.behavior_engine import BehaviorEngine
    from app.services.detector_registry import BY_NAME

    engine = BehaviorEngine()
    danger_capable = []
    for name, spec in BY_NAME.items():
        if spec.nature != "emotional":
            continue
        method = getattr(engine, spec.method, None)
        if method is None:
            continue
        src = inspect.getsource(method)
        sev = set(re.findall(r"""severity\s*=\s*["'](\w+)["']""", src))
        sev |= set(re.findall(r"""["'](caution|danger|critical|info)["']\s*if""", src))
        if sev & {"danger", "critical"}:
            danger_capable.append(name)

    # The SET, not a count. A bare number goes stale on every justified
    # retirement — that is how `>= 12` and then `>= 5` both broke — and it
    # cannot catch a substitution. Changing this set means changing what
    # death_spiral can see, so it must be deliberate.
    #
    # 2026-08-28: was five. `direction_instability` (Pattern #11) emitted
    # `danger` at 3+ session flips and so could contribute; it produced exactly
    # ONE danger event across the 189-session book, so at most one session could
    # lose its emotional domain to this retirement. `size_escalation` before it
    # was caution-only and contributed nothing.
    # 2026-08-30: was four. `winning_streak_overconfidence` (Pattern #19) had a
    # `danger` branch in code and so counted as capable, but it produced
    # **ZERO** danger events across the book - only 1 trade of 740 ever had the
    # required 5-win run behind it, and that one missed the 2.0x size gate. So
    # no session can lose its emotional domain to this retirement, and the
    # death_spiral change is nil rather than merely small.
    # 2026-08-30: was three. `opening_5min_trap` was retired (Pattern 21), and
    # its removal exposes an error in this set rather than merely shrinking it.
    # That detector returned a HARDCODED `info` on every branch and could never
    # reach death_spiral at all. It appeared here because the scan above regexes
    # the method source for `severity = "..."`, and its body carried a COMMENT
    # recording a dead computation — `severity = "danger" if ... else "caution"`
    # — removed in the 24 Aug hygiene pass. The scan matched the comment.
    # Practical impact of the correction: nil, because it never contributed.
    EXPECTED_DANGER_CAPABLE = {
        "overtrading_burst",
        "same_symbol_obsession",
    }

    assert set(danger_capable) == EXPECTED_DANGER_CAPABLE, (
        f"the set of emotional detectors that can reach death_spiral changed: "
        f"{sorted(set(danger_capable) ^ EXPECTED_DANGER_CAPABLE)}"
    )


def test_the_capital_ratio_rung_survived_the_deletion():
    """
    The two retained thresholds have no detector reader and are kept anyway:
    they are the only entries in _CAPITAL_RATIOS, so deleting them would empty
    rung 4 of the ladder and remove its only test vehicle.
    """
    from app.core.threshold_resolution import _CAPITAL_RATIOS

    assert set(_CAPITAL_RATIOS) == {
        "profit_giveaway_min_peak", "profit_giveaway_min_erosion",
    }


def test_the_severity_tier_that_was_purely_the_detectors_is_gone():
    from app.core.trading_defaults import COLD_START_DEFAULTS

    assert "profit_giveaway_caution_pct" not in COLD_START_DEFAULTS
    assert "profit_giveaway_danger_pct" not in COLD_START_DEFAULTS
    # ...but the capital-relative floors stay.
    assert "profit_giveaway_min_peak" in COLD_START_DEFAULTS
    assert "profit_giveaway_min_erosion" in COLD_START_DEFAULTS


def test_session_facts_still_carries_the_measurements():
    from app.core.session_facts import SessionFacts

    fields = SessionFacts.__dataclass_fields__
    for name in ("peak_pnl", "drawdown_from_peak", "max_drawdown"):
        assert name in fields
