"""
The pattern vocabulary must mean the same thing everywhere.

`detector_registry.py` is the single source of truth for which pattern types
exist. Four other places carry a copy of that vocabulary, and every one of them
has drifted from it at least once:

  * `AlertContext.tsx` — 14 real pattern types had no mapping and 16 no display
    name, while 10 mapped keys named patterns engine v2 stopped emitting. A
    trader saw a title-cased raw key instead of the curated copy.
  * `src/types/patterns.ts` — `PatternSeverity` gained `critical`, and
    `AlertContext` kept folding it into `danger` on the live path only.
  * `demoData.ts` — guest fixtures emit `severity: 'high'`, retired since v2.

Project memory names this exact thing — "pattern-vocabulary drift across 4
copies" — as a root cause. Nothing was asserting it, so every fix was manual and
every drift was found by a human reading files.

This test asserts the contract instead. It reads the TypeScript as text rather
than importing it, because that is the only way to see both vocabularies at
once, and a slightly awkward test that catches a real bug class beats an elegant
one that catches nothing.

Deliberately NOT asserted: that `BACKEND_TO_FRONTEND_TYPE` maps every type. That
map collapses several patterns on purpose (`martingale_behaviour` and
`size_escalation` both become `position_sizing`) and its correct end state is
deletion in favour of GET /api/risk/patterns. Asserting completeness would
freeze a design we intend to remove.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.core.severity import SEVERITY_ORDER
from app.services.detector_registry import (
    ALIASES,
    BY_NAME,
    all_pattern_types,
    pattern_copy,
)

SRC = Path(__file__).resolve().parents[2] / "src"
ALERT_CONTEXT = SRC / "contexts" / "AlertContext.tsx"
PATTERNS_TS = SRC / "types" / "patterns.ts"
DEMO_DATA = SRC / "lib" / "demoData.ts"

#: Severities the engine can put on an alert. `info` is analytics-only.
LIVE_SEVERITIES = set(SEVERITY_ORDER)

#: Retired severity words. Any of these in live frontend code or fixtures means
#: something is speaking a vocabulary the API stopped using at engine v2.
RETIRED_SEVERITIES = {"high", "medium", "low"}


def _object_keys(text: str, marker: str, end: str) -> set[str]:
    """Quoted keys of the object literal that starts at `marker`."""
    start = text.index(marker)
    body = text[start : text.index(end, start)]
    return set(re.findall(r"'([a-z_0-9]+)'\s*:", body))


@pytest.fixture(scope="module")
def alert_context() -> str:
    if not ALERT_CONTEXT.exists():
        pytest.skip(f"{ALERT_CONTEXT} not present")
    return ALERT_CONTEXT.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# The registry is internally consistent
# ---------------------------------------------------------------------------

def test_every_pattern_type_has_copy():
    """
    A pattern with no copy renders as a title-cased key. That is the failure the
    catalogue endpoint exists to prevent, so the copy has to be complete.
    """
    # pattern_copy() is the accessor, not PATTERN_COPY: detector copy lives in
    # PATTERN_COPY (27) and alias copy in ALIAS_COPY (6). Reading the dict
    # directly reports the six aliases as uncovered when they are not.
    missing = sorted(p for p in all_pattern_types() if pattern_copy(p) is None)
    assert not missing, f"pattern types with no copy: {missing}"


def test_pattern_types_are_registry_plus_aliases_and_nothing_else():
    assert set(all_pattern_types()) == set(BY_NAME) | set(ALIASES)


# ---------------------------------------------------------------------------
# The frontend speaks the same vocabulary
# ---------------------------------------------------------------------------

def test_frontend_has_a_display_name_for_every_pattern_type(alert_context):
    """
    Caught 22 Aug: 16 of 33 types fell through to the title-case fallback, so an
    alert read "Same Symbol Obsession" instead of "Repeated same instrument".
    """
    named = _object_keys(alert_context, "const names: Record<string, string> = {", "\n  };")
    missing = sorted(p for p in all_pattern_types() if p not in named)
    assert not missing, (
        f"{len(missing)} pattern types have no frontend display name and will "
        f"render as a title-cased raw key: {missing}"
    )


def test_frontend_map_names_no_pattern_the_engine_cannot_emit(alert_context):
    """
    Caught 22 Aug: 10 keys named v1 patterns (fomo, overtrading, iv_crush_behavior
    ...). Dead entries are not harmless - they read as though the engine still
    emits those names.
    """
    mapped = _object_keys(alert_context, "const BACKEND_TO_FRONTEND_TYPE", "\n};")
    phantom = sorted(k for k in mapped if k not in set(all_pattern_types()))
    assert not phantom, f"map keys the engine cannot emit: {phantom}"


def test_frontend_severity_union_matches_the_engine():
    """
    `critical` was missing from PatternSeverity once already, and the live alert
    path folded it into `danger` while history did not - the same alert rendered
    two ways on one screen.
    """
    if not PATTERNS_TS.exists():
        pytest.skip("patterns.ts not present")
    text = PATTERNS_TS.read_text(encoding="utf-8")
    m = re.search(r"export type PatternSeverity\s*=\s*([^;]+);", text)
    assert m, "PatternSeverity union not found"
    declared = set(re.findall(r"'([a-z]+)'", m.group(1)))

    # 'positive' is a frontend-only affordance; 'info' is analytics-only and
    # never reaches an alert row.
    engine_facing = LIVE_SEVERITIES - {"info"}
    missing = sorted(engine_facing - declared)
    assert not missing, f"severities the engine emits but the UI cannot express: {missing}"

    retired = sorted(declared & RETIRED_SEVERITIES)
    assert not retired, f"PatternSeverity still declares retired severities: {retired}"


# ---------------------------------------------------------------------------
# Fixtures must mirror the real API
# ---------------------------------------------------------------------------

def test_demo_fixtures_use_only_live_severities():
    """
    Guest-mode fixtures double as smoke fixtures, so a fixture speaking a dead
    vocabulary hides real bugs - which is how DEMO_HABITS' `pnl` vs `net_pnl`
    and the missing session-log stub both survived.

    Scoped to objects carrying a `pattern_type`, i.e. alert/pattern shapes.
    `high`/`medium` are NOT universally wrong in this file: daily_reports_service
    genuinely emits "severity": "high"/"medium" for its danger-zone rows, and
    `importance: high` is the signal-stacking evidence field, a third vocabulary
    again. An earlier version of this test asserted across the whole file and
    would have forced correct fixtures to be broken to satisfy it.
    """
    if not DEMO_DATA.exists():
        pytest.skip("demoData.ts not present")
    text = DEMO_DATA.read_text(encoding="utf-8")
    pattern_lines = [ln for ln in text.splitlines() if "pattern_type:" in ln]
    bad = sorted({
        m for ln in pattern_lines
        for m in re.findall(r"severity:\s*'(high|medium|low)'", ln)
    })
    assert not bad, (
        f"demoData.ts gives a pattern a retired severity {bad}; alerts have used "
        f"info/caution/danger/critical since engine v2"
    )


def test_demo_fixtures_use_only_real_pattern_types():
    if not DEMO_DATA.exists():
        pytest.skip("demoData.ts not present")
    text = DEMO_DATA.read_text(encoding="utf-8")
    used = set(re.findall(r"pattern_type:\s*'([a-z_0-9]+)'", text))
    unknown = sorted(used - set(all_pattern_types()))
    assert not unknown, (
        f"demoData.ts uses pattern types the engine cannot emit: {unknown}"
    )
