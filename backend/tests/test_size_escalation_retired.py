"""
`size_escalation` is retired. These tests hold the retirement in place.

WHY IT WAS RETIRED (2026-08-27)

Its entire claim was that the ORDER of position sizes carries information: three
consecutive trades each larger than the last, while losing. Tested with the
detector's own code against 200 permutations of each session's trade order -
same trades, same sizes, same P&L, only the sequence changed:

    observed (real order)   42
    shuffled mean           49.7      95% range [36, 65]
    ratio                   0.85
    p(shuffled >= observed) 0.880

The real order fires LESS than chance. Its defining gate selects at exactly the
rate three random numbers are increasing - 16.9% of 3-trade windows in the book
against 16.7% expected.

The rest was already broken:

  - 37 of 42 firings ran the cross-instrument branch, whose headline named
    `ct_underlying` (the CURRENT trade) while the three trades shown were the
    session's previous three: "ICICIGI: ... (TCS25APR2900PE / TCS25APR3500CE /
    HUDCO25APR230CE)".
  - `prior` excluded `ct`, so it fired on trade N and described N-3..N-1. Only
    7 of 42 alerts contained the trade that raised them.
  - "While losing" tested `pnls[:2]` for a single loss - true 83% of the time by
    base rate - and never checked the trade at the top of the escalation.
  - It predicted nothing: +Rs 69/trade, p = 0.797, sign favouring the flagged
    trade.

THE CONCEPT OF DANGEROUS SIZING IS NOT RETIRED

`martingale_behaviour` (the step the trader took, capital at risk, >=2 trailing
consecutive losses) and `post_loss_recovery_bet` (current against the mean of the
last three) both keep the current trade as the subject, and both survive
untouched. A coverage check confirmed the only shape solely this detector could
have caught - a slow ramp where every step stays under martingale's 1.5x and the
current trade under recovery's 2.0x of the recent mean - occurs **0 times in
3-trade windows** across 189 sessions (once each at 4 and 5 trades). No
replacement detector and no replacement threshold were introduced.

WHAT THESE TESTS COVER

  1. the detector cannot produce new events
  2. the surviving sizing detectors are untouched
  3. historical rows stay readable
  4. no other detector's wiring moved

Full evidence in docs/patterns/10-size_escalation/.
"""

import io
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src"
APP = Path(__file__).resolve().parents[1] / "app"

RETIRED = "size_escalation"


# ── 1. it cannot generate new events ───────────────────────────────────────

def test_the_detector_method_is_gone():
    from app.services.behavior_engine import BehaviorEngine

    assert not hasattr(BehaviorEngine(), "_detect_size_escalation")


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
        assert spec.method != "_detect_size_escalation"
        assert hasattr(engine, spec.method), f"{spec.name} points at a missing method"


def test_the_engine_counts_are_what_the_retirement_left():
    """
    22 detectors, 28 pattern types. Patterns 4, 6, 9, 10, 11 and 14 each took one
    of each (33 -> 28); the six aliases are untouched throughout.
    """
    from app.services.detector_registry import ALIASES, REGISTRY, all_pattern_types

    # 22 / 28 since `panic_exit` was retired 2026-08-29 (Pattern 14).
    assert len(REGISTRY) == 22
    assert len(ALIASES) == 6
    assert len(all_pattern_types()) == 28


def test_it_is_recorded_as_retired():
    from tests.test_pattern_contract import RETIRED_PATTERN_NAMES

    assert RETIRED in RETIRED_PATTERN_NAMES


def test_the_threshold_is_gone():
    """
    `size_escalation_pct` was never in threshold_registry, so it had no Kind and
    no provenance. It had exactly one reader, which is now deleted.
    """
    from app.core.threshold_registry import THRESHOLD_SPECS
    from app.core.trading_defaults import COLD_START_DEFAULTS

    assert "size_escalation_pct" not in COLD_START_DEFAULTS
    assert "size_escalation_pct" not in THRESHOLD_SPECS


def test_no_live_module_reads_the_deleted_threshold():
    offenders = []
    for path in APP.rglob("*.py"):
        if "__pycache__" in path.parts or "_archive" in path.parts:
            continue
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1
        ):
            if line.lstrip().startswith("#"):
                continue
            if "size_escalation_pct" in line:
                offenders.append(f"{path.relative_to(APP)}:{lineno}")
    assert offenders == [], f"deleted threshold still read: {offenders}"


def test_it_is_gone_from_the_entry_decidable_list():
    from app.services.entry_detectors import ENTRY_DECIDABLE

    assert RETIRED not in ENTRY_DECIDABLE


def test_it_is_gone_from_the_strategy_suppression_set():
    """A suppression entry for a detector that cannot fire is dead config."""
    from app.services.behavior_engine import BehaviorEngine

    assert RETIRED not in BehaviorEngine._STRATEGY_SUPPRESSED


# ── 2. the surviving sizing detectors are untouched ────────────────────────

def test_the_two_surviving_sizing_detectors_still_exist():
    from app.services.behavior_engine import BehaviorEngine
    from app.services.detector_registry import BY_NAME

    engine = BehaviorEngine()
    for name, method in (("martingale_behaviour", "_detect_martingale_behaviour"),
                         ("post_loss_recovery_bet", "_detect_post_loss_recovery_bet")):
        assert name in BY_NAME, f"{name} must survive - it owns the sizing claim"
        assert hasattr(engine, method)


def test_the_sizing_family_kept_its_two_members_in_order():
    """
    Ordering is load-bearing: the most specific claim wins inside a family.
    `size_escalation` was the third and weakest; the two above it stay, in order.
    """
    from app.services.behavior_engine import BehaviorEngine

    fam = dict(BehaviorEngine._FAMILIES)
    members = fam["sizing after losses"]
    assert members == ("martingale_behaviour", "post_loss_recovery_bet")


def test_notional_survives_because_other_detectors_read_it():
    from app.services.behavior_engine import BehaviorEngine

    assert hasattr(BehaviorEngine, "_notional")
    src = (APP / "services" / "behavior_engine.py").read_text(encoding="utf-8")
    # Was >= 3 when post_loss_recovery_bet also called it. F22 (2026-08-29)
    # deleted that detector's cross-underlying branch, which was UNREACHABLE -
    # its `prior` list is filtered to a single underlying, so the set it tested
    # could never hold more than one element. The two calls it made went with
    # it. `_notional` still has a live consumer in
    # winning_streak_overconfidence, which is what this test exists to prove:
    # the helper was not orphaned when size_escalation was retired.
    assert src.count("self._notional(") >= 2


def test_the_surviving_sizing_thresholds_are_intact():
    from app.core.trading_defaults import COLD_START_DEFAULTS

    assert COLD_START_DEFAULTS["recovery_bet_caution_mul"] == 2.0
    assert COLD_START_DEFAULTS["recovery_bet_danger_mul"] == 3.0
    assert "martingale_min_losses" in COLD_START_DEFAULTS


# ── 3. historical rows stay readable ───────────────────────────────────────

def test_the_weekly_report_can_still_label_a_stored_row():
    import inspect

    from app.tasks import report_tasks

    assert '"size_escalation": "Size Escalation"' in inspect.getsource(report_tasks)


def test_the_weekly_report_no_longer_lists_it_as_a_live_pattern():
    import inspect

    from app.tasks import report_tasks

    src = inspect.getsource(report_tasks)
    start = src.index("_COMMON_PATTERNS")
    body = src[start:src.index("]", start)]
    assert RETIRED not in body


def test_analytics_can_still_tag_a_stored_sizing_day():
    """
    `SIZING` reads stored BehaviorEvents to tag historical days. Dropping the
    name would silently re-tag a real trader's past sessions.
    """
    import inspect

    from app.api import analytics

    assert '"size_escalation"' in inspect.getsource(analytics)


@pytest.mark.parametrize("relpath,needle", [
    ("contexts/AlertContext.tsx", "'size_escalation':               'Size Escalation'"),
    ("components/patterns/BehaviourCostCard.tsx", "size_escalation:"),
    ("components/analytics/BehaviourLead.tsx", "size_escalation:"),
    ("components/alerts/AlertDetailSheet.tsx", "case 'size_escalation':"),
])
def test_the_frontend_can_still_render_a_stored_row(relpath, needle):
    path = SRC / relpath
    if not path.exists():
        pytest.skip(f"{path} not present")
    assert needle in io.open(path, encoding="utf-8").read(), (
        f"{relpath} lost its {RETIRED} entry; historical alerts would render "
        f"as a title-cased raw key"
    )


def test_the_frontend_no_longer_claims_the_engine_emits_it():
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
    assert fam["going back to the same trade"] == (
        "same_symbol_obsession", "revenge_trade", "rapid_reentry")
    assert fam["the position is too big"] == (
        "excess_exposure", "overexposure", "portfolio_concentration",
        "capital_mismatch")
    assert BehaviorEngine._COMPOSITES == ("death_spiral",)


def test_removing_it_could_not_have_changed_death_spiral():
    """
    The replay expectation, proven rather than assumed.

    `death_spiral` counts nature-domains with an event at **danger or above**
    (`spiral_domain_min_severity = "danger"`). The retired detector emitted
    exactly ONE severity - `caution` - hardcoded, never escalating; all 42 of its
    firings across the 189-session book were `caution`.

    A caution event is invisible to death_spiral. So removing `size_escalation`
    cannot cost any day a domain, and the confirmation replay must show
    death_spiral **UNCHANGED**. An earlier note predicting "a death_spiral fall
    as arithmetic" was wrong, and this test exists so it cannot be repeated.
    """
    import inspect
    import re

    from app.core.trading_defaults import COLD_START_DEFAULTS
    from app.services.behavior_engine import BehaviorEngine
    from app.services.detector_registry import BY_NAME

    assert COLD_START_DEFAULTS["spiral_domain_min_severity"] == "danger"

    engine = BehaviorEngine()
    capable = []
    for name, spec in BY_NAME.items():
        if spec.nature != "emotional":
            continue
        m = getattr(engine, spec.method, None)
        if m is None:
            continue
        body = inspect.getsource(m)
        sev = set(re.findall(r"severity\s*=\s*[\"']([a-z]+)[\"']", body))
        sev |= set(re.findall(r"[\"'](caution|danger|critical|info)[\"']\s*if", body))
        if sev & {"danger", "critical"}:
            capable.append(name)
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
    EXPECTED_DANGER_CAPABLE = {
        "overtrading_burst",
        "winning_streak_overconfidence",
        "opening_5min_trap",
        "same_symbol_obsession",
    }

    assert set(capable) == EXPECTED_DANGER_CAPABLE, (
        f"the set of emotional detectors that can reach death_spiral changed: "
        f"{sorted(set(capable) ^ EXPECTED_DANGER_CAPABLE)}"
    )


def test_every_surviving_detector_still_resolves():
    from app.services.behavior_engine import BehaviorEngine
    from app.services.detector_registry import REGISTRY

    engine = BehaviorEngine()
    missing = [d.name for d in REGISTRY if not hasattr(engine, d.method)]
    assert missing == [], f"registry specs with no method: {missing}"
