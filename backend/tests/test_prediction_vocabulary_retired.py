"""
`pattern_prediction_service` is gone, and retired names cannot re-enter
prediction output.

WHAT WAS REMOVED (2026-09-03)

The service emitted, per pattern, a `probability` percentage built by summing
hardcoded literals — base 5, +10 for one condition, +15 for another, +30 for a
third, capped at 95 — with an unsourced 2000-rupee threshold among the inputs.
It keyed that output on five names no detector has emitted for weeks:

    revenge_trading · tilt_loss_spiral · overtrading · fomo · recovery_chase

Because they were dict KEYS rather than registry entries, the pattern
vocabulary contract could not see them, and they shipped through three live
endpoints: GET /api/reports/predictions, POST /api/reports/predictions/simulate
and the `predictions` / `risk_assessment` keys of GET /api/analytics/ai-insights.

Two independent reasons to remove rather than rename. It PREDICTED, which this
product does not do — the charter is that an alert converts an automatic action
into a deliberate one, and both `time_of_day_bias` and `death_spiral` were
retired for less. And renaming the keys to live pattern types would have been
worse than leaving them: it would launder a banned prediction surface into
current vocabulary and make it read as sanctioned.

Nothing consumed it: no frontend call, and the service wrote nothing, so no
stored record depends on it. Historical alert rows are untouched — they carry
their own `pattern_type` and render through the existing label maps, which is
why those maps legitimately still contain retired names.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "app"

#: The five the archived service produced.
RETIRED_PREDICTION_KEYS = (
    "revenge_trading",
    "tilt_loss_spiral",
    "overtrading",
    "fomo",
    "recovery_chase",
)


def _live_modules():
    return [
        p
        for p in APP.rglob("*.py")
        if "_archive" not in p.parts and "__pycache__" not in p.parts
    ]


def test_the_service_is_archived_and_nothing_live_imports_it():
    assert not (APP / "services" / "pattern_prediction_service.py").exists()
    assert (APP / "services" / "_archive" / "pattern_prediction_service.py").exists()

    for path in _live_modules():
        src = path.read_text(encoding="utf-8", errors="ignore")
        for line in src.splitlines():
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("*"):
                continue  # a comment recording the removal is the point
            assert "import pattern_prediction_service" not in line, path
            assert "from app.services.pattern_prediction_service" not in line, path


def test_the_prediction_endpoints_are_gone():
    from app.main import app

    routes = {getattr(r, "path", "") for r in app.routes}
    assert "/api/reports/predictions" not in routes
    assert "/api/reports/predictions/simulate" not in routes


def test_ai_insights_no_longer_returns_prediction_keys():
    src = (APP / "api" / "analytics.py").read_text(encoding="utf-8")
    assert '"predictions": predictions,' not in src
    assert '"risk_assessment": risk_assessment,' not in src


def test_no_live_module_assigns_a_prediction_keyed_on_any_name():
    """
    The forward guard. The defect's shape was `predictions["<name>"] = {...}` —
    a dict key, invisible to a registry-based contract. Any reappearance fails
    here regardless of which name is used, so this does not go stale as the
    vocabulary changes.
    """
    pattern = re.compile(r"""predictions\[["'](\w+)["']\]\s*=""")
    offenders = []
    for path in _live_modules():
        src = path.read_text(encoding="utf-8", errors="ignore")
        for i, line in enumerate(src.splitlines(), 1):
            if line.strip().startswith("#"):
                continue
            m = pattern.search(line)
            if m:
                offenders.append(f"{path.relative_to(APP)}:{i} -> {m.group(1)}")
    assert not offenders, (
        "a prediction surface is back:\n  " + "\n  ".join(offenders)
    )


@pytest.mark.parametrize("name", RETIRED_PREDICTION_KEYS)
def test_retired_names_survive_only_where_stored_rows_need_them(name):
    """
    These names are NOT banned outright — a stored alert row carries its own
    `pattern_type` forever, and the label maps that render it must keep them.
    What must not exist is a live module PRODUCING one.

    So this asserts the narrow thing: no live module emits one as a new
    dict-literal entry under a `predictions`/`probabilities` structure. The
    broad "does this string appear anywhere" test would fail on
    `cooldown_service`, `danger_zone_service`, `daily_reports_service` and
    `notification_rate_limiter`, all of which legitimately MAP stored labels.
    """
    bad = re.compile(rf"""(predictions|probabilities)\[["']{name}["']\]""")
    for path in _live_modules():
        src = path.read_text(encoding="utf-8", errors="ignore")
        assert not bad.search(src), f"{path} produces {name}"
