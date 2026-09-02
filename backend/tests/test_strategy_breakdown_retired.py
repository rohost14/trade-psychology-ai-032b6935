"""
`strategy_breakdown` is retired. These tests hold the retirement in place.

WHY IT WAS RETIRED (2026-09-02)

It fired only when a win-rate collapse AND a profit-factor collapse happened
together, on the reasoning that two independent degradation signals are stronger
evidence than either alone. The reasoning is sound. The second signal never
bound.

Measured on the 203-session book, with baselines supplied from the book's own
history:

    win_rate_collapse                4 firings
    strategy_breakdown               4 firings
    identical firing sets            True
    unique to strategy_breakdown     0

Profit-factor collapse is not rare on its own — 6 of the 26 sessions that reach
the 8-trade gate have one — but as the second half of an `AND` with the win-rate
condition it excluded NOTHING. That is not a coincidence of a small sample: a
session that wins 11% of its trades almost always has a wrecked profit factor,
so the two conditions are not independent in the way the design assumed.

NOT RETIRED FOR FIRING RARELY. Retired because it was a second name for one
finding, and the reviews that preceded it established that counting the same
thing twice is not corroboration.

WHAT WAS NOT DECIDED HERE

The `performance` domain still cannot reach a trader: `win_rate_collapse` is
`severity="info"`, `notification_level=0`, `disposition="analytics"`, and under
the closed INFO/EVIDENCE rule an info event never becomes a RiskAlert. That is a
PRODUCT QUESTION about what the domain is for, and it is deliberately left open
rather than answered by a retirement. Retiring the duplicate does not make the
survivor louder, and this suite asserts that it did not.

WHAT THESE TESTS COVER

  1. the detector cannot produce new events
  2. `win_rate_collapse` — which keeps the subject — is untouched
  3. the shared baselines it read are still produced, for their other readers
  4. historical rows stay readable
  5. no threshold cleanup was needed, and none happened

Full evidence in docs/patterns/25-27-performance-trio/.
"""
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "app"
SRC = Path(__file__).resolve().parents[2] / "src"

RETIRED = "strategy_breakdown"


# ── 1. it cannot generate new events ───────────────────────────────────────

def test_the_detector_method_is_gone():
    from app.services.behavior_engine import BehaviorEngine

    assert not hasattr(BehaviorEngine(), "_detect_strategy_breakdown")


def test_it_is_not_in_the_registry_or_the_vocabulary():
    from app.services.detector_registry import (
        ALIASES, BY_NAME, PATTERN_COPY, REGISTRY, all_pattern_types,
    )

    assert RETIRED not in BY_NAME
    assert RETIRED not in ALIASES
    assert RETIRED not in PATTERN_COPY
    assert RETIRED not in all_pattern_types()
    assert all(d.name != RETIRED for d in REGISTRY)
    assert all(d.method != "_detect_strategy_breakdown" for d in REGISTRY)


def test_the_engine_counts_are_what_the_retirement_left():
    """14 detectors. Pattern types and aliases moved again the same day
    with `holding_loser` and `overexposure` — 16 and 2."""
    from app.services.detector_registry import ALIASES, REGISTRY, all_pattern_types

    assert len(REGISTRY) == 14
    assert len(all_pattern_types()) == 16
    assert len(ALIASES) == 2


def test_it_is_recorded_as_retired():
    from tests.test_pattern_contract import RETIRED_PATTERN_NAMES

    assert RETIRED in RETIRED_PATTERN_NAMES


def test_every_surviving_detector_still_resolves():
    """A registry spec pointing at a deleted method fails the whole engine."""
    from app.services.behavior_engine import BehaviorEngine
    from app.services.detector_registry import REGISTRY

    engine = BehaviorEngine()
    missing = [d.name for d in REGISTRY if not hasattr(engine, d.method)]
    assert missing == [], f"registry specs with no method: {missing}"


# ── 2. the detector that keeps the subject is untouched ────────────────────

def test_win_rate_collapse_survives():
    from app.services.behavior_engine import BehaviorEngine
    from app.services.detector_registry import BY_NAME

    assert "win_rate_collapse" in BY_NAME
    assert hasattr(BehaviorEngine(), "_detect_win_rate_collapse")


def test_win_rate_collapse_was_not_made_louder_by_the_retirement():
    """
    THE POINT OF THIS TEST. Removing a duplicate must not be used as cover for
    promoting the survivor. Whether the `performance` domain should reach a
    trader at all is an open product question; it is not answered here.
    """
    from app.services.detector_registry import BY_NAME

    spec = BY_NAME["win_rate_collapse"]
    assert spec.disposition == "analytics"
    assert spec.notification_level == 0
    assert spec.nature == "performance"


def test_the_shared_baselines_are_still_produced():
    """
    `strategy_breakdown` read `baseline_win_rate` and `baseline_profit_factor`.
    Neither may go with it: the first is `win_rate_collapse`'s only input, and
    the second has other readers.
    """
    import inspect

    from app.services import baseline_service

    src = inspect.getsource(baseline_service)
    assert '"win_rate"' in src
    assert '"profit_factor"' in src


# ── 3. historical rows stay readable ───────────────────────────────────────

def test_the_frontend_still_renders_a_stored_row():
    """
    Stored `RiskAlert` rows are kept. A missing key renders as a title-cased
    raw key, which is how a retirement leaks into the UI.
    """
    text = (SRC / "contexts" / "AlertContext.tsx").read_text(encoding="utf-8")
    assert f"'{RETIRED}': 'Strategy underperforming'" in text


def test_it_is_not_in_the_frontend_routing_map():
    """It was never there — analytics disposition, info only. Pinned so."""
    text = (SRC / "contexts" / "AlertContext.tsx").read_text(encoding="utf-8")
    routing = text.split("const BACKEND_TO_FRONTEND_TYPE")[1].split("};")[0]
    assert f"'{RETIRED}':" not in routing


def test_it_is_not_a_pattern_type_in_the_guest_fixtures():
    """Guest fixtures double as smoke fixtures; a retired name there is a bug."""
    demo = (SRC / "lib" / "demoData.ts").read_text(encoding="utf-8")
    assert f"pattern_type: '{RETIRED}'" not in demo
    assert f'pattern_type: "{RETIRED}"' not in demo


# ── 4. no live module reads it ─────────────────────────────────────────────

def test_no_live_module_compares_against_the_retired_name():
    offenders = []
    for path in APP.rglob("*.py"):
        if "__pycache__" in path.parts or "_archive" in path.parts:
            continue
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1
        ):
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            if f'"{RETIRED}"' in line or f"'{RETIRED}'" in line:
                offenders.append(f"{path.relative_to(APP)}:{lineno}")
    assert offenders == [], f"retired name still live: {offenders}"


# ── 5. it owned no thresholds, so none were removed ────────────────────────

def test_it_had_no_thresholds_of_its_own():
    """
    Its 0.40 and 0.50 were inline literals, not registry keys — so unlike most
    retirements there was nothing to clean up, and nothing was cleaned up by
    accident. `win_rate_collapse`'s own inline 0.4 is untouched.
    """
    from app.core.threshold_registry import THRESHOLD_SPECS
    from app.core.trading_defaults import COLD_START_DEFAULTS

    for pool in (COLD_START_DEFAULTS, THRESHOLD_SPECS):
        assert not any(RETIRED in k for k in pool)


@pytest.mark.parametrize("key", ["baseline_win_rate", "baseline_profit_factor"])
def test_the_baseline_keys_it_read_are_not_removed(key):
    """Shared inputs. Removing them with the detector would break the survivor."""
    import inspect

    from app.services.behavior_engine import BehaviorEngine

    src = inspect.getsource(BehaviorEngine._detect_win_rate_collapse)
    if key == "baseline_win_rate":
        assert key in src
    else:
        from app.services import baseline_service
        assert '"profit_factor"' in inspect.getsource(baseline_service)
