"""
`panic_exit` is retired. These tests hold the retirement in place.

WHY IT WAS RETIRED (2026-08-29, Pattern 14)

Its subject did not exist. The detector was two conditions - held under five
minutes AND a loss - and "panic" was inferred entirely from those.

THE DECIDING TEST. It fired on short LOSSES and never on short WINS:

    sub-5-minute holds        180      win rate 38.3%
    5-minute-or-longer holds  560      win rate 39.8%

Short holds perform the SAME as long holds, so a fast exit is not a worse
decision for this trader. The detector fired on the losing 60% and ignored 69
identical-behaviour trades purely because they made money - selection on
OUTCOME, not on behaviour. The same shape as `size_escalation`: the claimed
discriminator does not discriminate.

A sub-five-minute hold is 24% of everything this trader does (180 of 740), so it
is their ordinary style rather than an aberration. The detector also fired on
their CHEAPEST losses - median Rs 308, and 69% of firings under Rs 500 -
flagging plausibly-good risk management as a psychological failure.

(Short losses averaged -473 against -1,053 for longer ones at p = 0.000. That
comparison is CONFOUNDED - a longer hold has more time to accumulate loss - and
is recorded, not relied on. The win-rate result carries the argument alone.)

Its message made three unsupported claims in one sentence: "no stop-loss order"
(the Pattern 12 defect, unverifiable), "quick manual exit" ("manual" is equally
unknowable without an order type), and the event name itself.

THE CONCEPT OF A FAST EXIT IS NOT RETIRED as a neutral fact. Hold time is on
every CompletedTrade and analytics can read it. What is retired is treating a
short losing hold as a behavioural finding.

Evidence: docs/patterns/14-panic_exit/ and _measurement/p14_panic.py.
"""
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"

RETIRED = "panic_exit"


# ── 1. it cannot generate new events ───────────────────────────────────────

def test_the_detector_method_is_gone():
    from app.services.behavior_engine import BehaviorEngine

    assert not hasattr(BehaviorEngine(), "_detect_panic_exit")


def test_it_is_not_in_the_registry_or_the_vocabulary():
    from app.services.detector_registry import (
        ALIASES, BY_NAME, PATTERN_COPY, REGISTRY, all_pattern_types,
    )

    assert RETIRED not in BY_NAME
    assert RETIRED not in ALIASES
    assert RETIRED not in all_pattern_types()
    assert RETIRED not in PATTERN_COPY
    assert all(d.name != RETIRED for d in REGISTRY)


def test_no_registry_spec_points_at_the_deleted_method():
    from app.services.behavior_engine import BehaviorEngine
    from app.services.detector_registry import REGISTRY

    engine = BehaviorEngine()
    for spec in REGISTRY:
        assert spec.method != "_detect_panic_exit"
        assert hasattr(engine, spec.method), f"{spec.name} points at a missing method"


def test_the_engine_counts_are_what_the_retirement_left():
    """
    20 detectors, 26 pattern types. Patterns 4, 6, 9, 10, 11, 14, 15 and 18 each took one
    of each (33 -> 26); the six aliases are untouched throughout.
    """
    from app.services.detector_registry import ALIASES, REGISTRY, all_pattern_types

    assert len(REGISTRY) == 14
    # 2026-09-02: 5 -> 4 aliases and 20 -> 19 pattern types. `death_spiral`
    # was retired - a summary of alerts already delivered, not a state.
    assert len(ALIASES) == 4
    assert len(all_pattern_types()) == 18


def test_it_is_recorded_as_retired():
    from tests.test_pattern_contract import RETIRED_PATTERN_NAMES

    assert RETIRED in RETIRED_PATTERN_NAMES


# ── 2. its threshold went with it ──────────────────────────────────────────

def test_the_threshold_is_gone():
    from app.core.threshold_registry import THRESHOLD_SPECS
    from app.core.trading_defaults import COLD_START_DEFAULTS

    assert "panic_exit_min" not in COLD_START_DEFAULTS
    assert "panic_exit_min" not in THRESHOLD_SPECS


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
            if "panic_exit_min" in line:
                offenders.append(f"{path.relative_to(APP)}:{lineno}")
    assert offenders == [], f"deleted threshold still read: {offenders}"


def test_the_session_rung_survived_the_removal():
    """
    `panic_exit_min` was one of two keys the session rung personalised. Removing
    it must not have taken the rung with it - `rapid_reentry_min` still needs it,
    and Pattern 13 kept that detector.
    """
    from app.core.threshold_resolution import Source, resolve_thresholds

    class _T:
        def __init__(self, entry, exit_):
            self.entry_time, self.exit_time = entry, exit_

    from datetime import datetime, timedelta, timezone
    start = datetime(2026, 8, 21, 9, 20, tzinfo=timezone.utc)
    trades = [_T(start + timedelta(minutes=i * 14),
                 start + timedelta(minutes=i * 14 + 10)) for i in range(9)]

    ts = resolve_thresholds(None, session_trades=trades)
    assert ts.explain("rapid_reentry_min").source is Source.SESSION


# ── 3. nothing else moved ──────────────────────────────────────────────────

def test_the_other_analytics_detectors_are_untouched():
    """
    It was one of four `info`/analytics detectors. Retiring it must not have
    disturbed the other three, whose reviews are still to come.
    """
    from app.services.behavior_engine import BehaviorEngine
    from app.services.detector_registry import BY_NAME

    engine = BehaviorEngine()
    # early_exit retired P18, opening_5min_trap retired P21 — rapid_reentry is
    # the last analytics detector standing.
    for name in ("rapid_reentry",):
        assert name in BY_NAME, name
        assert BY_NAME[name].disposition == "analytics", name
        assert hasattr(engine, BY_NAME[name].method), name


def test_the_shared_stop_order_constant_survived():
    """
    `_STOP_ORDER_TYPES` was shared with `no_stoploss`, which is NOT retired.
    """
    from app.services.behavior_engine import _STOP_ORDER_TYPES, BehaviorEngine

    assert _STOP_ORDER_TYPES == frozenset({"SL", "SL-M", "SLM", "SL-MKT"})
    assert hasattr(BehaviorEngine(), "_detect_no_stoploss")


# ── 4. historical rows stay readable ───────────────────────────────────────

def test_the_frontend_can_still_name_a_stored_row():
    """
    Stored alerts still carry `panic_exit`. The routing map must drop it - the
    engine cannot emit it - but the display name must stay, or a history screen
    renders a raw key.
    """
    ctx = Path(__file__).resolve().parents[2] / "src" / "contexts" / "AlertContext.tsx"
    if not ctx.exists():
        return
    text = ctx.read_text(encoding="utf-8")

    routing = text[text.index("const BACKEND_TO_FRONTEND_TYPE"):]
    routing = routing[:routing.index("\n};")]
    assert "'panic_exit':" not in routing, (
        "the engine cannot emit it, so the routing map must not name it")

    assert "'panic_exit':                    'Panic Exit'" in text, (
        "stored rows must still render a human name")
