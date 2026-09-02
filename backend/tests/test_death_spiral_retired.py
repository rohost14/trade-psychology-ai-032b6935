"""
`death_spiral` RETIRED 2026-09-02 (Review A1) — the retirement, enforced.

WHAT IT CLAIMED

A state: "several independent behavioural domains are deteriorating together
in one session", escalating warning -> danger -> critical, with the critical
tier reserved for three domains breached inside a compression window while the
trader kept going.

WHY IT WENT — measured twice against the same 203-session book

  NOT DISTINCT. Without declared rules it fired 10 times, ALL `danger`, ALL
  `emotional+risk`, and was SET-IDENTICAL to "a danger emotional alert and a
  danger risk alert happened today" - the same 10 sessions, exactly. It was
  also a strict SUBSET of the simpler rule "two danger alerts from two
  detectors" (both 10, current-only 0, simpler-only 4), and the four sessions
  the domain rule EXCLUDED included the 4th-worst day in the book (-Rs 11,015),
  rejected only because both its detectors carried nature="risk".

  With one declared rule (daily_loss_limit=5000) it fired on 79 of 203 sessions
  - 38.9%. `constitution_violation` appeared in 100% of them. In 61% BOTH
  domains were carried by `constitution_violation` and `session_meltdown`,
  which read the SAME declared daily_loss_limit: one limit, breached, reported
  twice and counted as two independent domains.

  NOT ADDITIVE. Every firing was preceded by a danger alert already delivered
  (10 of 10 without rules; 69% of danger firings with them). Both constituents
  are themselves notifiable, so the composite could not exist until the trader
  had already been told. Incremental firings: 40% without rules, 15% with.

  NOT SEQUENTIAL ENOUGH TO SAVE IT. `caution` and `danger` contain no
  timestamp at all and survived every reordering tested. `critical` does read
  time, and on the LIVE path its 180-minute window genuinely discriminated: 7
  of 79 firing sessions escalated danger -> critical. But it reached only 8.9%
  of firings, it did not make the other 91% any less redundant, and the tier it
  gated was already the rarest thing in the book.

  A WHOLE DOMAIN WAS UNREACHABLE. `performance` detectors hardcode
  severity="info" and the gate was >= danger, so it could never contribute.

  THE ABSORPTION WAS DEAD CODE. `_COMPOSITES` was matched against the events
  the ENGINE produced, and death_spiral was written afterwards by
  `trade_tasks`, never through the detector loop - so nothing was ever
  absorbed. Zero `absorbed:` markers exist in the database, and on a real
  critical session (2026-07-29) 14 RiskAlerts were written across 6 pattern
  types, none suppressed. The master document claimed the opposite for months.

WHAT REPLACED IT

Nothing. Every constituent alert still fires, unchanged. `constitution_violation`
is notification_level 4 and guardian-eligible on its own.

WHAT WAS DELIBERATELY KEPT

Historical rows. `death_spiral` RiskAlerts and BehaviorEvents are NOT deleted;
they are the trader's own history and still render by name. What must not
happen is a stored row reading as a rule that is still watching them.

Evidence: docs/patterns/A1-death_spiral/
"""
import inspect
import re
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "app"
SRC = Path(__file__).resolve().parents[2] / "src"


def _live_py():
    for p in APP.rglob("*.py"):
        if "__pycache__" in p.parts or "_archive" in p.parts:
            continue
        yield p


def _code(p):
    """Source lines with whole-line comments stripped: the removal notes name
    what they removed, so a naive scan matches its own explanation."""
    for n, line in enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
        if line.lstrip().startswith("#"):
            continue
        yield n, line


# ══ 1. IT CANNOT FIRE ══════════════════════════════════════════════════════

def test_the_evaluator_is_gone():
    import app.services.behavior_scores_service as svc

    assert not hasattr(svc, "evaluate_death_spiral")
    assert not hasattr(svc, "_ALIAS_NATURE")
    assert not hasattr(svc, "_SEV_ORDER")


def test_the_task_that_ran_it_is_gone():
    import app.tasks.trade_tasks as tt

    assert not hasattr(tt, "_run_death_spiral")


def test_no_module_can_construct_one():
    """No live code may write this pattern_type or detector name."""
    offenders = []
    for p in _live_py():
        for n, line in _code(p):
            if re.search(r'["\']death_spiral["\']', line):
                offenders.append(f"{p.relative_to(APP)}:{n}: {line.strip()}")
    assert offenders == [], offenders


def test_it_is_not_in_the_live_vocabulary():
    from app.services.detector_registry import (
        ALIASES, BY_NAME, PATTERN_COPY, all_pattern_types)

    assert "death_spiral" not in all_pattern_types()
    assert "death_spiral" not in ALIASES
    assert "death_spiral" not in BY_NAME
    assert "death_spiral" not in PATTERN_COPY


def test_the_counts_are_what_the_retirement_left():
    from app.services.detector_registry import ALIASES, REGISTRY, all_pattern_types

    assert len(REGISTRY) == 14          # unchanged: it was never a detector
    assert len(ALIASES) == 2            # was 5
    assert len(all_pattern_types()) == 16   # was 20


# ══ 2. NO EXECUTION PATH REMAINS ═══════════════════════════════════════════

def test_no_call_site_survives_in_the_pipeline():
    import app.tasks.trade_tasks as tt

    body = "\n".join(l for l in Path(tt.__file__).read_text(encoding="utf-8").splitlines()
                     if not l.lstrip().startswith("#"))
    assert "_run_death_spiral" not in body
    assert "spiral_alert" not in body
    assert "death_spiral_ms" not in body


def test_the_timing_metric_is_gone():
    from app.core.metrics import COUNTERS, TIMINGS

    assert "death_spiral_ms" not in TIMINGS
    assert "death_spiral_ms" not in COUNTERS
    assert [t for t in TIMINGS if "spiral" in t] == []


def test_its_four_thresholds_are_gone_and_nothing_replaced_them():
    from app.core.trading_defaults import COLD_START_DEFAULTS

    for key in ("spiral_domain_min_severity", "spiral_warning_domains",
                "spiral_critical_domains", "spiral_window_min"):
        assert key not in COLD_START_DEFAULTS
    assert [k for k in COLD_START_DEFAULTS if "spiral" in k] == []


def test_the_guardian_channel_has_no_spec_less_exception():
    """
    death_spiral had no DetectorSpec, so it reached the guardian - the loudest
    channel there is - through a hardcoded name check rather than through
    `guardian_eligible`. With it retired, an unknown pattern must resolve to
    False, so a stored historical row can never be re-delivered to a guardian.
    """
    import app.tasks.trade_tasks as tt

    body = "\n".join(l for l in Path(tt.__file__).read_text(encoding="utf-8").splitlines()
                     if not l.lstrip().startswith("#"))
    assert "bool(spec and spec.guardian_eligible)" in body
    assert 'else alert.pattern_type ==' not in body


# ══ 3. THE ABSORPTION MUST NOT COME BACK ═══════════════════════════════════

def test_the_composite_mechanism_is_gone():
    from app.services.behavior_engine import BehaviorEngine

    assert not hasattr(BehaviorEngine, "_COMPOSITES")


def test_nothing_absorbs_another_detectors_alert():
    """
    THE ONE MOST WORTH KEEPING. The branch was dead for its whole life and the
    documentation asserted the opposite. If a composite is ever reintroduced it
    must be produced BY the engine, or it will be dead in exactly this way
    again - and this test will fail first.
    """
    from app.services.behavior_engine import BehaviorEngine

    src = inspect.getsource(BehaviorEngine._consolidate)
    code = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
    assert "absorbed:" not in code
    assert "_COMPOSITES" not in code


def test_the_surviving_consolidation_rules_are_untouched():
    """Families and the rule-breach merge are NOT part of this retirement."""
    from app.services.behavior_engine import BehaviorEngine

    src = inspect.getsource(BehaviorEngine._consolidate)
    assert "same_story:" in src
    assert "merged_into_rule_breach" in src
    fam = dict(BehaviorEngine._FAMILIES)
    assert fam["sizing after losses"] == ("martingale_behaviour", "post_loss_recovery_bet")


# ══ 4. HISTORY SURVIVES, AND READS AS HISTORY ══════════════════════════════

def test_stored_rows_still_render_by_name():
    """
    Deleting a trader's history to tidy a vocabulary would be worse than
    keeping a name. A missing key renders as a title-cased raw string.
    """
    p = SRC / "contexts" / "AlertContext.tsx"
    if not p.exists():
        pytest.skip("frontend not present")
    t = p.read_text(encoding="utf-8")
    assert "'death_spiral': 'Multi-domain breakdown'" in t


def test_a_stored_row_is_marked_retired_not_current():
    """
    The row stays; it must not read as a rule still watching the trader.
    """
    ctx = (SRC / "contexts" / "AlertContext.tsx")
    alerts = (SRC / "pages" / "Alerts.tsx")
    if not ctx.exists():
        pytest.skip("frontend not present")
    c = ctx.read_text(encoding="utf-8")
    assert "RETIRED_PATTERN_TYPES" in c
    assert "'death_spiral'," in c
    assert "export function isRetiredPattern" in c
    if alerts.exists():
        a = alerts.read_text(encoding="utf-8")
        assert "isRetiredPattern(alert.pattern.backend_type)" in a
        assert "Retired" in a


def test_no_migration_targets_the_historical_rows_for_deletion():
    """
    The evidence is kept. Counts are not tidied by deleting data.

    Scoped to a DELETE that NAMES this pattern - migration 066 legitimately
    deletes duplicate events and merely mentions death_spiral in a comment, so
    a whole-file scan for the word "delete" is the wrong test.
    """
    mig = Path(__file__).resolve().parents[1] / "migrations"
    if not mig.exists():
        pytest.skip("no migrations dir")
    bad = []
    for f in sorted(mig.glob("*.sql")):
        text = f.read_text(encoding="utf-8", errors="ignore").lower()
        for stmt in text.split(";"):
            if "delete" in stmt and "death_spiral" in stmt:
                bad.append(f.name)
    assert bad == [], bad


# ══ 5. UNRELATED DETECTORS ARE UNCHANGED ═══════════════════════════════════

def test_every_surviving_detector_still_resolves_to_a_method():
    from app.services.behavior_engine import BehaviorEngine
    from app.services.detector_registry import REGISTRY

    engine = BehaviorEngine()
    for spec in REGISTRY:
        assert getattr(engine, spec.method, None) is not None, spec.name


def test_the_nature_domains_all_still_have_detectors():
    from app.services.detector_registry import REGISTRY

    domains = {d.nature for d in REGISTRY}
    for expected in ("emotional", "risk", "discipline", "performance"):
        assert expected in domains


def test_the_constituents_that_carried_it_are_untouched():
    """
    Retiring a composite must not disturb what it counted. These five carried
    every firing in the reference book.
    """
    from app.services.detector_registry import BY_NAME

    for name in ("martingale_behaviour", "same_symbol_obsession",
                 "adding_to_adverse_position", "overtrading_burst",
                 "post_loss_recovery_bet", "session_meltdown",
                 "constitution_violation"):
        assert name in BY_NAME, name


def test_the_guardian_budget_is_unrelated_and_survives():
    """It shared a module with death_spiral and nothing else."""
    from app.services.behavior_scores_service import check_guardian_budget
    from app.core.trading_defaults import COLD_START_DEFAULTS

    assert callable(check_guardian_budget)
    assert COLD_START_DEFAULTS["guardian_monthly_budget"] == 3


def test_the_severity_vocabulary_is_unchanged():
    from app.core.severity import NOTIFIABLE, SEVERITY_ORDER

    assert NOTIFIABLE == frozenset({"danger", "critical"})
    assert tuple(SEVERITY_ORDER) == ("info", "caution", "danger", "critical")


# ══ 6. THE STALE ALIAS THE INVESTIGATION FOUND ═════════════════════════════

def test_portfolio_concentration_is_gone_from_the_nature_map():
    """
    Retired 2026-09-01, but still mapped in death_spiral's `_ALIAS_NATURE`
    until this retirement removed that map entirely. Inert - it could never be
    emitted - but stale, and named by the same investigation.

    SCOPED DELIBERATELY. Other `portfolio_concentration` references survive -
    `_FAMILIES`, a comment in position_monitor_tasks, and its own service
    module - and they belong to Pattern 28's retirement, not this one. They are
    recorded for that review rather than swept up here.
    """
    svc = APP / "services" / "behavior_scores_service.py"
    # Comment-stripped: the removal note NAMES what it removed, so a raw scan
    # matches its own explanation.
    code = [line for _, line in _code(svc)]
    assert not [l for l in code if "portfolio_concentration" in l]
    assert not [l for l in code if "_ALIAS_NATURE" in l]
