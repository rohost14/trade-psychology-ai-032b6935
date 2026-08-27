"""
`expiry_day_overtrading` is retired. These tests hold the retirement in place.

WHY IT WAS RETIRED (2026-08-27)

It never withheld. Of the 55 positions it was allowed to judge across the
189-session book - expiry day, CE/PE/FUT, entry at or after the 13:00 IST gate -
it fired on 55 and stayed silent on 0. A detector that never says no is not
measuring anything.

The cause was a units bug. `today_lots` summed `total_quantity`, which is
CONTRACTS (completed_trade.py: "in units, lot_size already factored"), against a
threshold of 10. A NIFTY lot is 75 contracts and the smallest position in the
book was 20, so the `today_lots >= 10` clause was not a threshold - it was True.
71% of firings came from that clause alone with a trade count under five, and
the count was 1 on eight of them: a detector named *overtrading* firing on the
trader's first expiry trade of the day. The same number was displayed beside the
word "lots", inflated by the lot size ("1 NIFTY trades / 750 lots").

Both trader-facing sentences were unsourced and both measured false:

  claimed  ">85% structural loss rate in the last 2 hours of expiry day"
  measured  53.8% at 14:00+, 61.8% at 13:00+, against a book-wide ~60%

  claimed  "each additional trade after 13:00 reduces your edge"  (asserts r < 0)
  measured  r = +0.260, p = 0.056, n = 55                          (opposite sign)

The reversal repeats at day level (expiry-trade-count vs session P&L r = +0.107,
p = 0.485, n = 45), and this trader's expiry-active sessions are their BETTER
sessions (51.1% green against 38.9%). Post-13:00 expiry trading against all
non-expiry trading is Rs 58/trade at p = 0.863.

The only source for the 85% figure anywhere in the repository was
docs/archive/PATTERN_REFERENCE.md, which asserts "NSE market data shows" and
cites nothing. It is now annotated as retracted.

Fixing the units would have moved the pass rate from 100% to 58% - restoring
discrimination without creating a finding, because there is no outcome
difference to discriminate on. So the units were not fixed and no replacement
threshold or detector was introduced.

WHAT THESE TESTS COVER

  1. the detector cannot produce new events
  2. the invented statistics cannot come back
  3. historical rows stay readable
  4. expiry-day-ness survives where it legitimately works
  5. no other detector's wiring moved

Full evidence in docs/patterns/09-expiry_day_overtrading/.
"""

import io
import re
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src"
APP = Path(__file__).resolve().parents[1] / "app"

RETIRED = "expiry_day_overtrading"


# ── 1. it cannot generate new events ───────────────────────────────────────

def test_the_detector_method_is_gone():
    from app.services.behavior_engine import BehaviorEngine

    assert not hasattr(BehaviorEngine(), "_detect_expiry_day_overtrading")


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
        assert spec.method != "_detect_expiry_day_overtrading"
        assert hasattr(engine, spec.method), f"{spec.name} points at a missing method"


def test_the_engine_counts_are_what_the_retirement_left():
    """
    24 detectors, 30 pattern types. Patterns 4, 6, 9 and 10 each took one of
    each (33 -> 32 -> 31 -> 30); the six aliases are untouched throughout.
    """
    from app.services.detector_registry import ALIASES, REGISTRY, all_pattern_types

    # 24 / 30 since `size_escalation` was retired 2026-08-27 (Pattern 10).
    assert len(REGISTRY) == 24
    assert len(ALIASES) == 6
    assert len(all_pattern_types()) == 30


def test_it_is_recorded_as_retired():
    from tests.test_pattern_contract import RETIRED_PATTERN_NAMES

    assert RETIRED in RETIRED_PATTERN_NAMES


def test_the_three_thresholds_are_gone():
    """
    All three were Kind.PERSONAL_BASELINE against Source.HISTORY metrics that no
    code produced, so the ladder always fell through to the literals anyway.
    """
    from app.core.threshold_registry import THRESHOLD_SPECS
    from app.core.trading_defaults import COLD_START_DEFAULTS

    for key in ("expiry_overtrading_caution_count",
                "expiry_overtrading_danger_count",
                "expiry_overtrading_caution_lots"):
        assert key not in COLD_START_DEFAULTS
        assert key not in THRESHOLD_SPECS


def test_the_phantom_metrics_are_not_referenced_anywhere():
    """
    expiry_day_trades_p75 / _p90 and expiry_day_lots_p75 were produced by no
    code. With the specs gone they must not appear at all - a live reference
    would mean a spec came back.
    """
    offenders = {}
    for path in APP.rglob("*.py"):
        if "__pycache__" in path.parts or "_archive" in path.parts:
            continue
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.lstrip().startswith("#"):
                continue      # the retirement note names them to explain the deletion
            for metric in ("expiry_day_trades_p75", "expiry_day_trades_p90",
                           "expiry_day_lots_p75"):
                if metric in line:
                    offenders.setdefault(str(path.relative_to(APP)), []).append(metric)
    assert offenders == {}, f"phantom baseline metrics referenced: {offenders}"


# ── 2. the invented statistics cannot come back ────────────────────────────

def _live_python_sources():
    for path in APP.rglob("*.py"):
        if "__pycache__" in path.parts or "_archive" in path.parts:
            continue
        yield path


@pytest.mark.parametrize("claim", [
    "structural loss rate",
    "last 2 hours of expiry",
    "reduces your edge",
])
def test_no_shipping_module_asserts_the_retracted_expiry_claim(claim):
    """
    The exact defect: two sentences with no source outside our own archived
    prose were shipped to traders as measurement, and rendered in the alert
    list, the detail sheet, the history sheet, the merged push body AND the AI
    coach prompt (AlertDetailSheet.tsx pastes alert.message into it).

    Retirement notes may DISCUSS the claim; they may not ASSERT it. An assertion
    is the sentence in a string literal, which is what reaches a trader.
    """
    offenders = []
    for path in _live_python_sources():
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1
        ):
            if claim not in line:
                continue
            if line.lstrip().startswith("#"):
                continue          # a comment explaining the retirement
            offenders.append(f"{path.relative_to(APP)}:{lineno}")
    assert offenders == [], (
        f"the retracted expiry claim {claim!r} is in live code, not a comment: "
        f"{offenders}"
    )


def test_the_frontend_does_not_carry_the_retracted_claim():
    if not SRC.exists():
        pytest.skip("src/ not present")
    offenders = []
    for path in SRC.rglob("*.ts*"):
        if "_archive" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for claim in ("structural loss rate", "reduces your edge"):
            if claim in text:
                offenders.append(f"{path.relative_to(SRC)}: {claim}")
    assert offenders == [], f"retracted expiry claim on the frontend: {offenders}"


def test_the_archived_origin_is_marked_retracted():
    """
    docs/archive/PATTERN_REFERENCE.md is the ONLY origin of the 85% figure in
    the repository. Leaving it unannotated is how it gets re-adopted.
    """
    doc = Path(__file__).resolve().parents[2] / "docs" / "archive" / "PATTERN_REFERENCE.md"
    if not doc.exists():
        pytest.skip("archived reference not present")
    text = io.open(doc, encoding="utf-8").read()
    head = text.index("### 20. Expiry Day Overtrading")
    section = text[head:head + 1600]
    assert "RETRACTED" in section, (
        "the archived origin of the 85% claim is not marked retracted"
    )


# ── 3. historical rows stay readable ───────────────────────────────────────
#
# Stored alerts still carry this pattern_type. Every surface that renders one
# keeps its entry, or a real trader's history renders as a title-cased raw key.

def test_the_weekly_report_can_still_label_a_stored_row():
    import inspect

    from app.tasks import report_tasks

    assert '"expiry_day_overtrading": "Expiry Day Overtrading"' in inspect.getsource(report_tasks)


@pytest.mark.parametrize("relpath,needle", [
    ("contexts/AlertContext.tsx", "'expiry_day_overtrading': 'Expiry-day activity'"),
    ("components/patterns/BehaviourCostCard.tsx", "expiry_day_overtrading:"),
    ("components/analytics/BehaviourLead.tsx", "expiry_day_overtrading:"),
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
    """
    The other direction: BACKEND_TO_FRONTEND_TYPE maps live pattern types, and a
    dead entry there reads as though the engine still produces them.
    """
    path = SRC / "contexts" / "AlertContext.tsx"
    if not path.exists():
        pytest.skip("AlertContext.tsx not present")
    text = io.open(path, encoding="utf-8").read()
    start = text.index("const BACKEND_TO_FRONTEND_TYPE")
    body = text[start:text.index("\n};", start)]
    assert RETIRED not in body


# ── 4. expiry-day-ness survives where it legitimately works ────────────────

def test_the_expiry_modifiers_in_other_detectors_are_intact():
    """
    Retiring the standalone alert must not touch the places expiry genuinely
    changes another detector's arithmetic.
    """
    from app.core.trading_defaults import COLD_START_DEFAULTS

    assert COLD_START_DEFAULTS["premium_loss_expiry_shift_pct"] == 15
    assert "no_stoploss_expiry_loss_pct" in COLD_START_DEFAULTS
    assert "no_stoploss_expiry_hold_min" in COLD_START_DEFAULTS


def test_is_expiry_day_and_count_structures_still_exist():
    """Both had other readers; neither was the detector's private helper."""
    from app.services.instrument_parser import is_expiry_day
    from app.services.strategy_detector import count_structures

    assert callable(is_expiry_day)
    assert callable(count_structures)


def test_is_expiry_day_still_has_live_readers():
    readers = [
        p.relative_to(APP)
        for p in _live_python_sources()
        if "is_expiry_day" in p.read_text(encoding="utf-8", errors="ignore")
    ]
    assert readers, "is_expiry_day lost every reader — it should not have"


# ── 5. no other detector moved ─────────────────────────────────────────────

def test_no_other_detector_lost_its_worsen_metric():
    from app.tasks.trade_tasks import _WORSEN_METRIC

    assert _WORSEN_METRIC["martingale_behaviour"] == "max_ratio"
    assert _WORSEN_METRIC["premium_loss_event"] == "loss_pct"
    assert RETIRED not in _WORSEN_METRIC


def test_the_per_episode_dedup_keys_are_intact():
    from app.tasks.trade_tasks import _pattern_dedup_key

    assert _pattern_dedup_key("constitution_violation", {"rule": "daily_loss"}) == \
        "constitution_violation:daily_loss"
    assert _pattern_dedup_key("same_symbol_obsession", {"underlying": "NIFTY"}) == \
        "same_symbol_obsession:NIFTY"


def test_death_spiral_keeps_every_domain_it_had():
    """
    Pattern 8 already showed death_spiral falls when a danger-domain contributor
    stops emitting. That is arithmetic. What must NOT change is the set of
    domains it counts over.
    """
    from app.services.detector_registry import REGISTRY

    domains = {d.nature for d in REGISTRY}
    for expected in ("emotional", "risk", "discipline"):
        assert expected in domains


def test_every_surviving_detector_still_resolves():
    from app.services.behavior_engine import BehaviorEngine
    from app.services.detector_registry import REGISTRY

    engine = BehaviorEngine()
    missing = [d.name for d in REGISTRY if not hasattr(engine, d.method)]
    assert missing == [], f"registry specs with no method: {missing}"
