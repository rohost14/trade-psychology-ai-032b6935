"""
Every user rule must be settable, clearable, and reported — 2026-09-02.

Two gaps closed here, both of the same shape: a field was a RULE_FIELD, was
stored, was classified by the change gate and was READ BY THE ENGINE, but some
surface in the middle did not carry it, so the trader could never actually
govern it.

  `sl_percent_options`  ConstitutionUpdate had no field for it, so PUT
                        /api/constitution/ dropped the key silently; and
                        /effective never listed it, so no page reported it.
  `restricted_windows`  had no editor at all. Zero profiles ever held one, zero
                        alerts ever fired, zero history rows — not because the
                        rule was unwanted but because nothing could write it.

The structural test at the top is the one that matters: it fails for the NEXT
field anyone adds to RULE_FIELDS without a way to set it.
"""
import inspect
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.api.constitution import ConstitutionUpdate, _RULE_TO_THRESHOLD
from app.core.trading_defaults import get_thresholds
from app.services.constitution_service import (
    RULE_FIELDS, ConstitutionService, classify_change,
)

SRC = Path(__file__).resolve().parents[2] / "src"


class Prof:
    trading_capital = 100_000.0
    detected_patterns = None

    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)

    def __getattr__(self, _n):
        return None


# ══ THE CONTRACT ═══════════════════════════════════════════════════════════

@pytest.mark.parametrize("field", RULE_FIELDS)
def test_every_rule_field_can_be_set_through_the_change_gate(field):
    """
    THE TEST THAT WOULD HAVE CAUGHT BOTH GAPS.

    PUT /api/constitution/ is the only endpoint that routes through
    tighten/loosen, override and the audit log. A rule the engine enforces but
    this schema cannot carry is a rule the trader cannot govern.
    """
    assert field in ConstitutionUpdate.model_fields, (
        f"{field} is enforced but ConstitutionUpdate has no field for it - "
        f"pydantic drops the key and the change is silently ignored"
    )


@pytest.mark.parametrize("field", RULE_FIELDS)
def test_every_rule_field_is_reported_somewhere_read_only(field):
    """Set a rule and have no page confirm it, and the trader cannot trust any
    of them. Lists are reported by /status, scalars by /effective."""
    from app.api.constitution import constitution_status

    if field == "restricted_windows":
        assert '"rule": "restricted_windows"' in inspect.getsource(constitution_status)
    else:
        assert field in _RULE_TO_THRESHOLD


# ══ sl_percent_options ═════════════════════════════════════════════════════

def test_the_put_schema_carries_it():
    u = ConstitutionUpdate(sl_percent_options=30)
    assert u.sl_percent_options == 30.0
    assert "sl_percent_options" in u.model_fields_set


def test_it_can_be_explicitly_cleared_and_omission_is_different():
    cleared = ConstitutionUpdate(sl_percent_options=None)
    omitted = ConstitutionUpdate(daily_trade_limit=5)
    assert "sl_percent_options" in cleared.model_fields_set
    assert cleared.sl_percent_options is None
    assert "sl_percent_options" not in omitted.model_fields_set


@pytest.mark.parametrize("bad", [0, -1, 101])
def test_its_range_matches_the_profile_endpoint_that_used_to_own_it(bad):
    """0.1-100, copied from `validate_percent`. No new range was invented."""
    with pytest.raises(ValidationError):
        ConstitutionUpdate(sl_percent_options=bad)


def test_exiting_sooner_is_tightening():
    assert classify_change("sl_percent_options", 50.0, 30.0) == "tighten"
    assert classify_change("sl_percent_options", 30.0, 50.0) == "loosen"
    assert classify_change("sl_percent_options", None, 30.0) == "tighten"
    assert classify_change("sl_percent_options", 30.0, None) == "loosen"


def test_effective_reports_unset_as_unset_not_as_a_default():
    declared = ConstitutionService.snapshot(Prof())
    effective = get_thresholds(Prof())
    assert declared["sl_percent_options"] is None
    assert effective.get("sl_percent_options") is None      # -> source "unset"


def test_no_default_was_invented_for_it():
    d = ConstitutionService.generate_defaults(
        experience_level="beginner", trading_capital=100_000.0)
    assert "sl_percent_options" not in d


# ══ restricted_windows ═════════════════════════════════════════════════════

def test_a_window_is_normalised_and_deduplicated():
    u = ConstitutionUpdate(restricted_windows=["9:15-9:30", "09:15-09:30"])
    assert u.restricted_windows == ["09:15-09:30"]


def test_blank_rows_are_not_windows():
    assert ConstitutionUpdate(restricted_windows=["", "   "]).restricted_windows == []


@pytest.mark.parametrize("bad", [
    ["1pm-2pm"],            # not HH:MM
    ["13:00"],              # no range
    ["25:00-26:00"],        # not a time of day
    ["13:70-14:00"],        # not a minute
    ["14:00-13:00"],        # ends before it starts
])
def test_an_unenforceable_window_is_rejected_at_the_boundary(bad):
    """
    WHY THIS IS STRICT. Both enforcement sites parse inside a try and
    `continue` past anything that raises, so a malformed window would be
    stored, listed back as one of the trader's rules, and silently never fire.
    The API is the only place the trader can be told.
    """
    with pytest.raises(ValidationError):
        ConstitutionUpdate(restricted_windows=bad)


def test_both_enforcement_sites_still_parse_the_format_we_validate():
    """The validator is only correct while it matches the parsers."""
    from app.services.behavior_engine import BehaviorEngine
    import app.tasks.position_monitor_tasks as pm

    engine_src = inspect.getsource(BehaviorEngine._detect_constitution_violation)
    tasks_src = Path(pm.__file__).read_text(encoding="utf-8")
    for src in (engine_src, tasks_src):
        assert 'w.split("-")' in src


def test_adding_a_window_tightens_and_removing_one_loosens():
    assert classify_change("restricted_windows", [], ["13:00-14:00"]) == "tighten"
    assert classify_change("restricted_windows",
                           ["13:00-14:00"], ["13:00-14:00", "09:15-09:30"]) == "tighten"
    assert classify_change("restricted_windows", ["13:00-14:00"], []) == "loosen"
    assert classify_change("restricted_windows",
                           ["13:00-14:00"], ["13:00-14:00"]) is None


def test_no_windows_are_invented_by_default():
    d = ConstitutionService.generate_defaults(
        experience_level="beginner", trading_capital=100_000.0)
    assert d.get("restricted_windows") == []


# ══ the dead entry-time cooldown twin ══════════════════════════════════════

def test_the_entry_time_cooldown_check_is_gone_too():
    """
    The 2026-09-02 removal took the engine's exit-time copy and missed this
    one. It read a threshold key no resolver publishes, so it was unreachable
    rather than merely unused.
    """
    import app.tasks.position_monitor_tasks as pm

    body = "\n".join(
        line for line in Path(pm.__file__).read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("#"))
    assert "user_cooldown_min" not in body


# ══ the surfaces ═══════════════════════════════════════════════════════════

def test_my_rules_offers_both_rules():
    p = SRC / "pages" / "MyRules.tsx"
    if not p.exists():
        return
    t = p.read_text(encoding="utf-8")
    assert "['sl_percent_options'," in t
    assert "restricted_windows: [...(d.restricted_windows ?? []), '']" in t


def test_no_surface_dresses_an_unset_rule_as_a_chosen_one():
    """
    The fabrication class. `?? 50` highlighted a preset the trader never picked
    and `?? 10` showed a limit they never set.
    """
    p = SRC / "components" / "settings" / "ProfileTab.tsx"
    if not p.exists():
        return
    t = p.read_text(encoding="utf-8")
    assert "sl_percent_options ?? 50" not in t
    assert "max_position_size ?? 10}%" not in t
    assert "profile.sl_percent_options == null" in t      # an explicit Not set


def test_the_rules_page_shows_a_percent_rule_as_a_percent():
    """`max_position_size` is a % of capital. It was formatted as rupees, so a
    10% cap was reported to the trader as the limit "Rs 10"."""
    p = SRC / "components" / "rules" / "EnforcedRules.tsx"
    if not p.exists():
        return
    t = p.read_text(encoding="utf-8")
    assert "const MONEY = new Set(['daily_loss_limit', 'per_trade_loss_limit'])" in t
    assert "'max_position_size', 'sl_percent_options'" in t


def test_the_guest_fixture_mirrors_the_real_rule_set():
    """Guest fixtures double as smoke fixtures."""
    p = SRC / "lib" / "demoData.ts"
    if not p.exists():
        return
    t = p.read_text(encoding="utf-8")
    assert "max_position_size: 200000" not in t          # rupees in a % field
    assert "sl_percent_options: 30," in t
    assert "per_trade_loss_limit: 6000," in t
