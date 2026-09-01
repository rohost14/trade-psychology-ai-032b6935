"""
`opening_5min_trap` is retired. These tests hold the retirement in place.

WHY IT WAS RETIRED (2026-08-30, Pattern 21)

THE OPENING WINDOW WAS NOT A WORSE PLACE TO TRADE.

It fired on an entry within 10 minutes of 09:15 that LOST and either exited
within 15 minutes or lost >= 30% of premium. Its premise was that price
discovery makes the opening hazardous. Measured on 175 sessions / 740 rounds:

    inside 09:15-09:25   n=33   win 39.4%   mean +Rs 99   median -Rs 112
    rest of day          n=707  win 39.5%   mean -Rs 59   median -Rs 180

Win rates 0.1 percentage points apart, and on money the window was BETTER -
permutation p = 0.274, so not a real edge in either direction. Indistinguishable
from the rest of the day.

It reached its finding only by discarding 14 of 33 window entries (42%) for
having made money, before any behaviour was examined. SELECTION ON OUTCOME - the
shape that retired `panic_exit` - and the code's own comment conceded it: "a
profitable opening trade could be a deliberate strategy". If the behaviour is
innocent and only the result distinguishes a firing, the result is what is being
flagged.

Its message explained the loss with a mechanism it never measured: "the widest
bid-ask spreads of the day". That is market microstructure rather than a
fabricated statistic, and broadly true - but we store no spread data, and the
outcome it DID measure was not worse in that window.

Three windows disagreed: the NAME said 5 minutes, the threshold said 10, the copy
said 09:15-09:25. Market open was hardcoded 09:15 while `end_of_session_mis_panic`
- reviewed alongside it - derives the equivalent boundary from
`exchange_constants`, having fixed exactly that defect for MCX.

DISTINGUISHED FROM `rapid_reentry`, kept at Pattern 13 while also being
info-with-no-reader: that detector's window WAS genuinely selective and only its
consumer was missing. This one's was not selective on anything measurable.

NOT RETIRED PERMANENTLY. Opening spreads are real. Testing that needs per-fill
spread and premium-stability data, which we do not store.

Evidence: docs/patterns/21-session_windows/.
"""
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"

RETIRED = "opening_5min_trap"


# ── 1. it cannot generate new events ───────────────────────────────────────

def test_the_detector_method_is_gone():
    from app.services.behavior_engine import BehaviorEngine

    assert not hasattr(BehaviorEngine(), "_detect_opening_5min_trap")


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
        assert spec.method != "_detect_opening_5min_trap"
        assert hasattr(engine, spec.method), f"{spec.name} points at a missing method"


def test_the_engine_counts_are_what_the_retirement_left():
    from app.services.detector_registry import ALIASES, REGISTRY, all_pattern_types

    assert len(REGISTRY) == 16
    assert len(ALIASES) == 6
    assert len(all_pattern_types()) == 22


def test_it_is_recorded_as_retired():
    from tests.test_pattern_contract import RETIRED_PATTERN_NAMES

    assert RETIRED in RETIRED_PATTERN_NAMES


# ── 2. its three thresholds went with it, unreplaced ───────────────────────

def test_the_thresholds_are_gone():
    from app.core.threshold_registry import THRESHOLD_SPECS
    from app.core.trading_defaults import COLD_START_DEFAULTS

    for key in ("opening_trap_window_end_min", "opening_trap_quick_exit_min",
                "opening_trap_large_loss_pct"):
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
            if "opening_trap_" in line:
                offenders.append(f"{path.relative_to(APP)}:{lineno}")
    assert offenders == [], f"deleted thresholds still read: {offenders}"


def test_no_window_was_substituted():
    """
    The window was not mis-sized - it was not a worse place to trade at any
    width. 5, 10 and 15 minutes all sit on the same undifferentiated
    distribution, so a replacement would have been inventing a number.
    """
    from app.core.trading_defaults import COLD_START_DEFAULTS

    assert not any(k.startswith("opening_trap") for k in COLD_START_DEFAULTS)


# ── 3. the last analytics detector, and the rule that governs it ───────────

def test_rapid_reentry_is_now_the_only_analytics_detector():
    """
    It was one of two. `rapid_reentry` was reviewed at Pattern 13 and KEPT -
    its window IS selective and only its consumer is missing, which is exactly
    the distinction this retirement turned on.
    """
    from app.services.behavior_engine import BehaviorEngine
    from app.services.detector_registry import BY_NAME, REGISTRY

    analytics = [d.name for d in REGISTRY if d.disposition == "analytics"]
    assert RETIRED not in analytics
    assert "rapid_reentry" in analytics

    engine = BehaviorEngine()
    assert hasattr(engine, BY_NAME["rapid_reentry"].method)


def test_the_info_visibility_rule_still_has_a_subject():
    """
    The closed INFO/evidence rule governs analytics detectors. Retiring one of
    the two must not leave the rule with nothing to govern - if it ever does,
    that is a signal the disposition itself needs a decision, not a silent
    empty set.
    """
    from app.services.detector_registry import REGISTRY

    analytics = [d.name for d in REGISTRY if d.disposition == "analytics"]
    assert analytics, "the analytics disposition has no members left"
    for name in analytics:
        spec = next(d for d in REGISTRY if d.name == name)
        assert spec.notification_level == 0


# ── 4. its sibling in the same review is UNTOUCHED ─────────────────────────

def test_end_of_session_mis_panic_was_not_modified():
    """
    Reviewed alongside it and DEFERRED, not retired: its subject is
    mechanically checkable, its exchange-aware square-off is correct work, and
    its effect points the right way - it is blocked on the tradebook having no
    `product` column, not on judgement.
    """
    from app.services.behavior_engine import BehaviorEngine
    from app.core.trading_defaults import COLD_START_DEFAULTS
    from app.services.detector_registry import BY_NAME, PATTERN_COPY

    assert "end_of_session_mis_panic" in BY_NAME
    assert "end_of_session_mis_panic" in PATTERN_COPY
    assert hasattr(BehaviorEngine(), "_detect_end_of_session_mis_panic")

    assert COLD_START_DEFAULTS["end_session_mis_caution_count"] == 2
    assert COLD_START_DEFAULTS["end_session_mis_danger_count"] == 3

    spec = BY_NAME["end_of_session_mis_panic"]
    assert spec.disposition == "alerting"
    assert spec.notification_level == 1


def test_the_exchange_aware_squareoff_survives():
    """
    The best work in either detector, and the direct contrast with the
    hardcoded 09:15 that went. A flat 15:00 boundary flagged every evening MCX
    entry as panic, because MCX trades to 23:30.
    """
    import inspect

    from app.services.behavior_engine import BehaviorEngine

    src = inspect.getsource(BehaviorEngine._detect_end_of_session_mis_panic)
    assert "get_close_time" in src
    assert 'exchange in ("MCX", "CDS", "BCD")' in src


# ── 5. historical rows stay readable ───────────────────────────────────────

def test_the_report_label_survives_for_stored_rows():
    src = (APP / "tasks" / "report_tasks.py").read_text(encoding="utf-8")
    assert '"opening_5min_trap": "Opening 5-Min Trap"' in src


def test_the_frontend_can_still_name_a_stored_row():
    ctx = Path(__file__).resolve().parents[2] / "src" / "contexts" / "AlertContext.tsx"
    if not ctx.exists():
        return
    text = ctx.read_text(encoding="utf-8")

    routing = text[text.index("const BACKEND_TO_FRONTEND_TYPE"):]
    routing = routing[:routing.index("\n};")]
    assert "'opening_5min_trap':" not in routing, (
        "the engine cannot emit it, so the routing map must not name it")

    assert "'opening_5min_trap':             'Opening 5-Min Trap'" in text, (
        "stored rows must still render a human name")
