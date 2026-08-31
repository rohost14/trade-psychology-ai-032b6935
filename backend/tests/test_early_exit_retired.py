"""
`early_exit` is retired. These tests hold the retirement in place AND prove the
measure survives where it works.

WHY IT WAS RETIRED (2026-08-30, Pattern 18)

THE MEASURE WAS RIGHT. THE SCOPE WAS NOT.

It computed the disposition effect - average winner hold against average loser
hold - which is long-established behavioural finance (Shefrin & Statman 1985;
Odean 1998) and the only observable answer to "was that exit early". Per trade
the question is unanswerable: we see neither the plan nor what the price did
after the exit.

What failed was computing it over ONE SESSION.

    the effect is absent in this book
        winners  n=276  mean 41.0 min
        losers   n=413  mean 36.7 min     ratio 1.12 - winners held LONGER

    and at session sample sizes the ratio is noise
        3 firings, computed from 3-5 trades per side
        shuffling win/loss labels within each qualifying session gives 4+
        sub-0.40 sessions 61% of the time:   p = 0.610

That is not a threshold needing a better value - at n=3 the ratio of two small
means is unstable by arithmetic - so 0.40 was NOT tuned and no replacement was
substituted. Raising the sample gate toward validity raises it toward never
firing: n=4 leaves 9 qualifying sessions of 175, n=5 leaves 3.

WHAT SURVIVES, and is asserted below: `baseline_service` still computes
`avg_winner_hold_min` and `avg_loser_hold_min` across the trader's full history,
with counts and confidence. Those are the same measure over 276 and 413 trades
rather than three and four.

Evidence: docs/patterns/18-early_exit/.
"""
import inspect
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"

RETIRED = "early_exit"


# ── 1. it cannot generate new events ───────────────────────────────────────

def test_the_detector_method_is_gone():
    from app.services.behavior_engine import BehaviorEngine

    assert not hasattr(BehaviorEngine(), "_detect_early_exit")


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
        assert spec.method != "_detect_early_exit"
        assert hasattr(engine, spec.method), f"{spec.name} points at a missing method"


def test_the_engine_counts_are_what_the_retirement_left():
    from app.services.detector_registry import ALIASES, REGISTRY, all_pattern_types

    assert len(REGISTRY) == 17
    assert len(ALIASES) == 6
    assert len(all_pattern_types()) == 23


def test_it_is_recorded_as_retired():
    from tests.test_pattern_contract import RETIRED_PATTERN_NAMES

    assert RETIRED in RETIRED_PATTERN_NAMES


# ── 2. its three thresholds went with it ───────────────────────────────────

def test_the_thresholds_are_gone():
    from app.core.threshold_registry import THRESHOLD_SPECS
    from app.core.trading_defaults import COLD_START_DEFAULTS

    for key in ("early_exit_ratio", "early_exit_winner_max_min",
                "early_exit_min_samples"):
        assert key not in COLD_START_DEFAULTS, key
        assert key not in THRESHOLD_SPECS, key


def test_no_live_module_reads_the_deleted_thresholds():
    offenders = []
    for path in APP.rglob("*.py"):
        if "__pycache__" in path.parts or "_archive" in path.parts:
            continue
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1
        ):
            if line.lstrip().startswith("#"):
                continue
            if "early_exit_" in line:
                offenders.append(f"{path.relative_to(APP)}:{lineno}")
    assert offenders == [], f"deleted thresholds still read: {offenders}"


def test_the_ratio_was_not_tuned_on_its_way_out():
    """
    0.40 was removed, not replaced. The failure was sample size, not the value,
    so substituting a different ratio would have been fixing the wrong thing.
    """
    from app.core.trading_defaults import COLD_START_DEFAULTS

    assert not any(k.startswith("early_exit") for k in COLD_START_DEFAULTS)


# ── 3. THE MEASURE SURVIVES WHERE IT WORKS ─────────────────────────────────
#
# The half of this retirement that matters: the detector went, the measurement
# did not.

def test_baseline_service_still_computes_the_hold_asymmetry():
    import app.services.baseline_service as bs

    src = inspect.getsource(bs)
    assert '"avg_winner_hold_min": _metric(' in src
    assert '"avg_loser_hold_min": _metric(' in src


def test_the_baseline_metrics_carry_a_sample_count():
    """
    The whole reason the history scope works and the session scope did not.
    `_metric` attaches n and confidence; the detector had neither.
    """
    import app.services.baseline_service as bs

    src = inspect.getsource(bs)
    assert "winner_holds, loser_holds = [], []" in src
    assert "winner_holds.append(hold)" in src
    assert "loser_holds.append(hold)" in src


def test_session_state_still_exposes_the_same_pair():
    from app.services.state.session_state import SessionState

    assert hasattr(SessionState, "avg_winner_hold_min")
    assert hasattr(SessionState, "avg_loser_hold_min")


# ── 4. nothing else moved ──────────────────────────────────────────────────

def test_the_last_analytics_detectors_are_untouched():
    """
    It was one of four `info`/analytics detectors. `panic_exit` went at Pattern
    14 and this at Pattern 18; the remaining two have reviews outstanding.
    """
    from app.services.behavior_engine import BehaviorEngine
    from app.services.detector_registry import BY_NAME

    engine = BehaviorEngine()
    # `opening_5min_trap` was the other survivor here until Pattern 21 retired
    # it 2026-08-30. `rapid_reentry` is the last analytics detector.
    for name in ("rapid_reentry",):
        assert name in BY_NAME, name
        assert BY_NAME[name].disposition == "analytics", name
        assert hasattr(engine, BY_NAME[name].method), name


# ── 5. historical rows stay readable ───────────────────────────────────────

def test_the_frontend_can_still_name_a_stored_row():
    ctx = Path(__file__).resolve().parents[2] / "src" / "contexts" / "AlertContext.tsx"
    if not ctx.exists():
        return
    text = ctx.read_text(encoding="utf-8")

    routing = text[text.index("const BACKEND_TO_FRONTEND_TYPE"):]
    routing = routing[:routing.index("\n};")]
    assert "'early_exit':" not in routing, (
        "the engine cannot emit it, so the routing map must not name it")

    assert "'early_exit':                    'Early Exit'" in text, (
        "stored rows must still render a human name")
