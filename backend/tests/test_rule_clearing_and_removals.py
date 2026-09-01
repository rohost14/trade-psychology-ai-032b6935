"""
Three product decisions of 2026-09-02, pinned.

  1. `sl_percent_futures` is not a user input. It was collected, validated,
     stored and displayed with the claim "Used to detect no-stop-loss behavior
     on futures trades" - and read by NOTHING.
  2. `cooldown_after_loss` is not a user-configurable rule. The PROTECTION
     stays: `revenge_window_min` / `revenge_window_caution_min` carry their own
     resolved values and were only ever OVERRIDDEN by the declared cooldown.
  3. An optional rule can be cleared back to NULL. The service layer was always
     ready - `classify_change` returns "loosen" for value -> None - the
     blockage was two API filters that dropped an explicit null.

Evidence: docs/DEEP_REVIEW/RULE_CLEARING_INVESTIGATION.md
"""
from pathlib import Path

import pytest

from app.core.threshold_resolution import Source, resolve_thresholds
from app.core.trading_defaults import COLD_START_DEFAULTS, get_thresholds
from app.services.constitution_service import (
    RULE_FIELDS, _TIGHTEN_DIRECTION, ConstitutionService, classify_change,
)

APP = Path(__file__).resolve().parents[1] / "app"
SRC = Path(__file__).resolve().parents[2] / "src"

#: Optional rules that must support the NULL lifecycle.
CLEARABLE = ("daily_loss_limit", "per_trade_loss_limit",
             "max_position_size", "sl_percent_options")


class Prof:
    trading_capital = 100_000.0
    detected_patterns = None

    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)

    def __getattr__(self, _n):
        return None


def _live_py():
    for path in APP.rglob("*.py"):
        if "__pycache__" in path.parts or "_archive" in path.parts:
            continue
        yield path


def _code_lines(path):
    """Source lines with whole-line comments stripped - the removal notes name
    what they removed, so a naive scan matches its own explanation."""
    for n, line in enumerate(
            path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
        if line.lstrip().startswith("#"):
            continue
        yield n, line


# ══ 1. sl_percent_futures has no runtime consumer ══════════════════════════

def test_sl_percent_futures_is_gone_from_every_runtime_path():
    offenders = []
    for path in _live_py():
        for n, line in _code_lines(path):
            if "sl_percent_futures" in line:
                offenders.append(f"{path.relative_to(APP)}:{n}")
    assert offenders == [], offenders


def test_neither_resolver_produces_it():
    for prof in (Prof(), Prof(sl_percent_futures=2.0), None):
        ts = resolve_thresholds(prof)
        assert "sl_percent_futures" not in ts.values
        assert ts.explain("sl_percent_futures") is None
        assert "sl_percent_futures" not in get_thresholds(prof)


def test_no_stoploss_never_read_it_and_still_does_not():
    """The UI claimed this field drove no-stop-loss detection. It never did."""
    import inspect

    from app.services.behavior_engine import BehaviorEngine

    src = inspect.getsource(BehaviorEngine._detect_no_stoploss)
    assert "sl_percent" not in src
    assert "no_stoploss_loss_pct_danger" in src


def test_the_frontend_no_longer_collects_it():
    for rel in ("components/settings/ProfileTab.tsx", "pages/Settings.tsx",
                "lib/settingsConstants.ts", "contexts/AlertContext.tsx"):
        p = SRC / rel
        if p.exists():
            assert "sl_percent_futures" not in p.read_text(encoding="utf-8"), rel


# ══ 2. cooldown_after_loss: input gone, protection intact ══════════════════

def test_it_is_no_longer_a_user_rule():
    assert "cooldown_after_loss" not in RULE_FIELDS
    assert "cooldown_after_loss" not in _TIGHTEN_DIRECTION


def test_generate_defaults_no_longer_suggests_one():
    d = ConstitutionService.generate_defaults(
        experience_level="beginner", trading_capital=100_000.0)
    assert "cooldown_after_loss" not in d


def test_no_resolver_publishes_the_user_cooldown_key():
    for prof in (Prof(), Prof(cooldown_after_loss=30), None):
        ts = resolve_thresholds(prof)
        assert "user_cooldown_min" not in ts.values
        assert "user_cooldown_min" not in get_thresholds(prof)


@pytest.mark.parametrize("declared", [None, 0, 15, 45])
def test_THE_PROTECTION_SURVIVES_at_its_own_value(declared):
    """
    THE POINT OF THIS DECISION. The revenge window is an ENGINE safeguard, not
    a user rule. A declared cooldown used to override it; now nothing does, and
    it resolves to its own value whatever the profile says.
    """
    ts = resolve_thresholds(Prof(cooldown_after_loss=declared))
    assert ts["revenge_window_min"] == COLD_START_DEFAULTS["revenge_window_min"]
    assert ts["revenge_window_caution_min"] == \
        COLD_START_DEFAULTS["revenge_window_caution_min"]
    assert ts.explain("revenge_window_min").source is not Source.DECLARED


def test_the_constitution_cooldown_rule_is_gone():
    import inspect

    from app.services.behavior_engine import BehaviorEngine

    body = "\n".join(
        l for l in inspect.getsource(
            BehaviorEngine._detect_constitution_violation).splitlines()
        if not l.lstrip().startswith("#"))
    assert "user_cooldown_min" not in body
    assert '"cooldown"' not in body


def test_revenge_trade_keeps_its_own_window_and_matrix():
    """
    revenge_trade is FROZEN. The only change was the declared-cooldown severity
    bump, which had no input left to read once the user rule went.
    """
    import inspect

    from app.services.behavior_engine import BehaviorEngine

    src = inspect.getsource(BehaviorEngine._detect_revenge_trade)
    body = "\n".join(l for l in src.splitlines()
                     if not l.lstrip().startswith("#"))
    assert "user_cooldown_min" not in body
    assert "declared_breach" not in body
    assert "revenge_window_caution_min" in body      # its own window, untouched
    assert "_RT_MATRIX" in body


def test_no_replacement_user_threshold_was_invented():
    for pool in (COLD_START_DEFAULTS,):
        for k in pool:
            assert "cooldown" not in k, k


def test_the_frontend_no_longer_collects_it():
    for rel in ("components/settings/ProfileTab.tsx",
                "components/onboarding/OnboardingWizard.tsx",
                "lib/settingsConstants.ts"):
        p = SRC / rel
        if p.exists():
            assert "cooldown_after_loss" not in p.read_text(encoding="utf-8"), rel


def test_my_rules_no_longer_offers_it_as_an_editable_field():
    p = SRC / "pages" / "MyRules.tsx"
    if not p.exists():
        return
    text = p.read_text(encoding="utf-8")
    assert "['cooldown_after_loss'," not in text
    # the LABEL stays, so stored history rows still render a human name
    assert "cooldown_after_loss: 'Cooldown after a loss'" in text


# ══ 3. clearing an optional rule ═══════════════════════════════════════════

@pytest.mark.parametrize("field", CLEARABLE)
def test_every_clearable_rule_is_still_a_rule_field(field):
    assert field in RULE_FIELDS
    assert field in _TIGHTEN_DIRECTION


@pytest.mark.parametrize("field", CLEARABLE)
def test_removal_classifies_as_loosen_and_addition_as_tighten(field):
    """Already true before this change - it is what made the fix small."""
    assert classify_change(field, 25.0, None) == "loosen"
    assert classify_change(field, None, 25.0) == "tighten"
    assert classify_change(field, 25.0, 25.0) is None


def test_the_api_distinguishes_omitted_from_explicitly_null():
    """
    THE WHOLE FIX. A key the client SENT is in `model_fields_set`; an omitted
    one is not. Sending null clears; saying nothing leaves the rule alone.
    """
    from app.api.constitution import ConstitutionUpdate

    sent_null = ConstitutionUpdate(max_position_size=None)
    omitted = ConstitutionUpdate()

    assert "max_position_size" in sent_null.model_fields_set
    assert "max_position_size" not in omitted.model_fields_set
    assert sent_null.max_position_size is None


def test_the_constitution_endpoint_builds_new_values_from_sent_keys():
    import inspect

    from app.api import constitution

    body = "\n".join(
        l for l in inspect.getsource(constitution.update_constitution).splitlines()
        if not l.lstrip().startswith("#"))
    assert "model_fields_set" in body
    assert "if f in sent" in body
    # the old filter must be gone, or a null is dropped again
    assert "is not None" not in body


def test_the_profile_endpoint_no_longer_filters_rule_nulls():
    import inspect

    from app.api import profile

    body = "\n".join(
        l for l in inspect.getsource(profile.update_profile).splitlines()
        if not l.lstrip().startswith("#"))
    assert "if f in RULE_FIELDS}" in body
    # non-rule fields KEEP their guard - a null there would blank a display field
    assert "if hasattr(profile, field) and value is not None:" in body


@pytest.mark.parametrize("field", CLEARABLE)
def test_a_cleared_rule_is_not_evaluated_by_the_engine(field):
    """NULL must continue to mean "no declared rule", per Pattern 28."""
    ts = resolve_thresholds(Prof(**{field: None}))
    assert ts.get(field) is None


def test_a_cleared_exposure_rule_produces_no_exposure_alert():
    import app.tasks.position_monitor_tasks as pm

    consts = set()

    def walk(code):
        for c in code.co_consts:
            if isinstance(c, str):
                consts.add(c)
            elif hasattr(c, "co_consts"):
                walk(c)

    walk(pm._overexposure_task.__code__)
    assert "no_declared_exposure_rule" in consts


def test_a_cleared_options_stop_leaves_only_the_universal_ladder():
    from decimal import Decimal
    from types import SimpleNamespace

    from app.services.live_risk_state import DECLARED, UNIVERSAL, build_watches

    ts = resolve_thresholds(Prof(sl_percent_options=None))
    assert ts.get("sl_percent_options") is None

    (w,) = build_watches(
        positions=[SimpleNamespace(
            tradingsymbol="NIFTY26FEB24000CE", total_quantity=400,
            average_entry_price=Decimal("75"), instrument_token=1,
            exchange="NFO")],
        thresholds=ts, broker_account_id="a")
    kinds = {c.kind for c in w.evaluate(75.0 * 0.30)}     # 70% of premium gone
    assert UNIVERSAL in kinds
    assert DECLARED not in kinds


def test_the_universal_severe_loss_ladder_is_untouched():
    assert COLD_START_DEFAULTS["premium_loss_caution_pct"] == 40
    assert COLD_START_DEFAULTS["premium_loss_danger_pct"] == 60
    assert COLD_START_DEFAULTS["premium_loss_critical_pct"] == 80


def test_my_rules_says_something_when_nothing_changed():
    """No silent success - the symptom that hid the clearing bug."""
    p = SRC / "pages" / "MyRules.tsx"
    if not p.exists():
        return
    assert "No changes to save." in p.read_text(encoding="utf-8")
