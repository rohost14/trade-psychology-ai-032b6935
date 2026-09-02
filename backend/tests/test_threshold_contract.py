"""
A threshold may not claim to be personalised unless something produces it.

THE CLASS THIS CLOSES

Four separate pattern reviews each found the same defect and each recorded it as
that pattern's problem:

    Pattern 17  the 40/75 session-meltdown ladder had no THRESHOLD_SPECS record
    Pattern 18  `early_exit_winner_max_min` declared metric `winner_hold_p50`,
                which no producer emits
    Pattern 19  `winning_streak_overconfidence` declared `uses_baseline=True`
                and read no baseline at all
    Pattern 21  `end_session_mis_caution_count` / `_danger_count` declared
                metrics `late_mis_entries_p75` / `_p90`, which no producer emits

Every one sat permanently at its fallback WHILE REPORTING ITSELF PERSONALISED.
That is worse than being a fallback: a fallback is honest, and a fallback
wearing the trader's own number is not. The H1 key-name mismatch was the same
class, found and fixed once — and it recurred three more times, because nothing
checked the declaration.

So this file does not test a threshold. It tests that the REGISTRY CANNOT LIE,
which is the only fix that closes a class rather than an instance.

WHAT IT DOES NOT DO

It does not require any threshold to be personalised, does not invent
producers, and does not add fallback values. A spec is free to be
`Kind.FALLBACK` with an unsourced number — several are, deliberately, and their
provenance says so. What it may not do is declare `Source.HISTORY` against a
metric nobody emits.
"""
import ast
import inspect
from pathlib import Path

import pytest

from app.core.threshold_registry import THRESHOLD_SPECS


def _baseline_metric_keys() -> set:
    """
    Every metric key `baseline_service` actually emits.

    Read from the source by AST rather than by calling it — the producer needs
    a database and a trader's history, and neither belongs in a contract test.
    An AST walk over the dict literals is exact where a regex would guess.
    """
    from app.services import baseline_service

    tree = ast.parse(inspect.getsource(baseline_service))
    keys = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for k in node.keys:
                if isinstance(k, ast.Constant) and isinstance(k.value, str):
                    keys.add(k.value)
    return keys


def _specs_declaring_a_metric():
    out = []
    for key, spec in THRESHOLD_SPECS.items():
        metric = getattr(spec, "metric", None)
        if metric:
            out.append((key, metric))
    return sorted(out)


# ── The contract ────────────────────────────────────────────────────────────

def test_every_declared_metric_has_a_producer():
    """
    THE ONE THAT MATTERS. A spec naming a metric no producer emits resolves to
    its fallback forever while telling the trader the number is theirs.
    """
    produced = _baseline_metric_keys()
    orphans = [(k, m) for k, m in _specs_declaring_a_metric() if m not in produced]
    assert orphans == [], (
        "threshold specs declare metrics nothing produces — they will sit at "
        "their fallback while reporting themselves personalised: "
        f"{orphans}. Fix the SPEC (reclassify it, as `fomo_symbols_in_window` "
        "and the two `end_session_mis_*` keys were), or produce the metric. "
        "Do NOT add a fake producer to silence this."
    )


def test_a_history_source_always_names_a_metric():
    """
    The mirror of the above: claiming HISTORY without naming what to read is
    the same lie with a missing field instead of a wrong one.
    """
    offenders = []
    for key, spec in THRESHOLD_SPECS.items():
        source = str(getattr(spec, "resolution_source", "") or "")
        if "HISTORY" in source and not getattr(spec, "metric", None):
            offenders.append(key)
    assert offenders == [], f"Source.HISTORY with no metric named: {offenders}"


def test_a_metric_is_only_declared_with_a_history_source():
    """
    And the converse — a metric named without HISTORY resolution is a
    declaration that nothing will act on.
    """
    offenders = []
    for key, spec in THRESHOLD_SPECS.items():
        if getattr(spec, "metric", None):
            source = str(getattr(spec, "resolution_source", "") or "")
            if "HISTORY" not in source:
                offenders.append((key, source))
    assert offenders == [], f"metric declared without Source.HISTORY: {offenders}"


# ── The specific instances, pinned so they cannot come back ─────────────────

@pytest.mark.parametrize("dead_metric", [
    "late_mis_entries_p75",   # Pattern 21, reclassified 2026-09-02
    "late_mis_entries_p90",   # Pattern 21, reclassified 2026-09-02
    "winner_hold_p50",        # Pattern 18, went with `early_exit`
])
def test_the_known_orphans_are_not_declared_anywhere(dead_metric):
    declared = {m for _, m in _specs_declaring_a_metric()}
    assert dead_metric not in declared


@pytest.mark.parametrize("key", [
    "end_session_mis_caution_count",
    "end_session_mis_danger_count",
])
def test_the_end_session_specs_no_longer_claim_to_be_personalised(key):
    """
    Reclassified 2026-09-02, not deleted and not given a producer. Their
    fallbacks (2 and 3) are UNCHANGED — the correction was to the claim, not
    to the number.
    """
    spec = THRESHOLD_SPECS[key]
    assert not getattr(spec, "metric", None)
    assert "HISTORY" not in str(getattr(spec, "resolution_source", "") or "")


def test_the_end_session_fallbacks_did_not_move():
    assert THRESHOLD_SPECS["end_session_mis_caution_count"].fallback == 2
    assert THRESHOLD_SPECS["end_session_mis_danger_count"].fallback == 3


def test_the_surviving_declarations_are_the_four_that_are_real():
    """
    Pinned by name. A new entry here is a claim that a producer exists, and
    this list is where someone has to say so deliberately.
    """
    assert dict(_specs_declaring_a_metric()) == {
        "burst_trades_per_30min_caution": "burst_per_30min_p75",
        "consecutive_loss_caution": "loss_streak_p60",
        "daily_trade_limit": "daily_trades_p75",
        "revenge_window_caution_min": "reentry_after_loss_p25",
    }


# ── uses_baseline: the same class in the detector registry ─────────────────

def test_uses_baseline_is_not_declared_by_a_detector_that_reads_none():
    """
    Pattern 19's instance. `winning_streak_overconfidence` declared
    `uses_baseline=True` and its "baseline" was an inline average over today's
    session. The field has no readers, so nothing broke — which is exactly why
    it went unnoticed.

    Checked by source: a spec claiming a baseline must mention one.
    """
    from app.services.behavior_engine import BehaviorEngine
    from app.services.detector_registry import REGISTRY

    engine = BehaviorEngine()
    offenders = []
    for spec in REGISTRY:
        if not getattr(spec, "uses_baseline", False):
            continue
        method = getattr(engine, spec.method, None)
        if method is None:
            continue
        src = inspect.getsource(method)
        if "baseline" not in src and "thresholds.get" not in src:
            offenders.append(spec.name)
    assert offenders == [], (
        f"specs declare uses_baseline but read no baseline: {offenders}"
    )
