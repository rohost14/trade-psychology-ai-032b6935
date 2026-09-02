"""
`cooldown_violation` is retired. These tests hold the retirement in place AND
prove the shared cooldown infrastructure it sat on top of still works.

WHY IT WAS RETIRED (2026-08-29, Pattern 15)

Its precondition never occurred on the live path. `Cooldown` rows are written in
exactly one place - `danger_zone_service.trigger_intervention` - reachable only
from `POST /danger-zone/trigger-intervention` and `POST /sync/all`. No Celery
task calls it, so the postback pipeline that ran this detector never created a
cooldown. It fired 0 times on the 175-session book.

The behaviour it named is fully covered. `constitution_violation`'s `cooldown`
rule reads the trader's OWN declared `cooldown_after_loss`, measures the gap
from the last losing exit, and fires at DANGER. Measured at a 15-minute declared
value it raised 181 events on the same book, against this detector's 0.

Its registry copy - "the cooldown you set" - described that other detector's
mechanism. This one read a SYSTEM-imposed row and never touched the declared
value.

WHAT MUST STILL WORK, and is asserted below: `cooldown_service`, the `Cooldown`
model and table, the `/cooldown` API, the danger zone's use of them, and the
trader's `cooldown_after_loss` rule feeding `constitution_violation`,
`revenge_trade` and `user_cooldown_min`.

Evidence: docs/patterns/15-cooldown_violation/.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

APP = Path(__file__).resolve().parents[1] / "app"

RETIRED = "cooldown_violation"


# ── 1. it cannot generate new events ───────────────────────────────────────

def test_the_detector_method_is_gone():
    from app.services.behavior_engine import BehaviorEngine

    assert not hasattr(BehaviorEngine(), "_detect_cooldown_violation")


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
        assert spec.method != "_detect_cooldown_violation"
        assert hasattr(engine, spec.method), f"{spec.name} points at a missing method"


def test_the_engine_counts_are_what_the_retirement_left():
    from app.services.detector_registry import ALIASES, REGISTRY, all_pattern_types

    assert len(REGISTRY) == 15
    # 2026-09-02: 5 -> 4 aliases and 20 -> 19 pattern types. `death_spiral`
    # was retired - a summary of alerts already delivered, not a state.
    assert len(ALIASES) == 4
    assert len(all_pattern_types()) == 19


def test_it_is_recorded_as_retired():
    from tests.test_pattern_contract import RETIRED_PATTERN_NAMES

    assert RETIRED in RETIRED_PATTERN_NAMES


# ── 2. the plumbing that existed only for it is gone ───────────────────────

def test_the_context_no_longer_carries_active_cooldowns():
    """
    `ctx.active_cooldowns` had exactly one reader. With the detector gone the
    field and the per-trade query that filled it are dead weight.
    """
    import dataclasses

    from app.services.behavior_engine import EngineContext

    fields = {f.name for f in dataclasses.fields(EngineContext)}
    assert "active_cooldowns" not in fields


def test_the_per_trade_cooldown_query_is_gone():
    """One fewer database round-trip on every completed trade."""
    src = (APP / "services" / "behavior_engine.py").read_text(encoding="utf-8")
    code = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
    assert "select(Cooldown)" not in code
    assert "from app.models.cooldown import Cooldown" not in code


# ── 3. SHARED COOLDOWN INFRASTRUCTURE STILL WORKS ──────────────────────────
#
# This is the half of the retirement that matters most: the detector went, the
# feature did not.

def test_the_cooldown_model_and_factory_survive():
    from app.models.cooldown import Cooldown, create_cooldown

    c = create_cooldown(uuid4(), "loss_limit", duration_minutes=15)
    assert isinstance(c, Cooldown)
    assert c.reason == "loss_limit"
    assert c.duration_minutes == 15
    assert c.expires_at > datetime.now(timezone.utc)


def test_the_cooldown_service_and_api_survive():
    import app.api.cooldown                       # noqa: F401
    from app.services.cooldown_service import cooldown_service

    for method in ("check_cooldown", "start_cooldown", "end_cooldown",
                   "get_cooldown_history"):
        assert hasattr(cooldown_service, method), method


def test_the_danger_zone_still_starts_cooldowns():
    """
    The one production writer. Retiring a READER must not disturb the WRITER.
    """
    import inspect

    from app.services.danger_zone_service import DangerZoneService

    src = inspect.getsource(DangerZoneService.trigger_intervention)
    assert "cooldown_service.start_cooldown" in src


# ── THE RETIREMENT'S ORIGINAL JUSTIFICATION NO LONGER HOLDS. 2026-09-02. ──
#
# `cooldown_violation` was retired on 2026-08-29 BECAUSE `constitution_violation`
# carried the same behaviour: the trader's declared cooldown was enforced there
# at DANGER, with their own number in the message, 181 firings against this
# detector's 0.
#
# On 2026-09-02 `cooldown_after_loss` stopped being a user-configurable rule by
# product decision, and that constitution rule went with it. So the behaviour
# this retirement pointed at as its replacement IS ALSO GONE.
#
# TWO TESTS WERE DELETED HERE, NOT WEAKENED - their subject no longer exists:
#   test_the_traders_declared_cooldown_rule_still_resolves
#   test_constitution_violation_still_owns_the_behaviour
#
# THIS DOES NOT REOPEN THE RETIREMENT. `cooldown_violation`'s own finding stands
# on its own evidence and is untouched: its precondition never occurred on the
# live path, because `Cooldown` rows are written only by
# `danger_zone_service.trigger_intervention`, which no Celery task calls. It
# fired 0 times in 175 sessions and would still fire 0 times today.
#
# WHAT REMAINS OF POST-LOSS PROTECTION, and it is not a rule:
#   `revenge_trade` and `rapid_reentry` judge re-entry after a loss against
#   `revenge_window_min` / `revenge_window_caution_min`, which carry their own
#   resolved values (10 and 20). They were only ever OVERRIDDEN by the declared
#   cooldown, never sourced from it, so they are unaffected.
#
# Pinned by test_rule_clearing_and_removals::
#   test_THE_PROTECTION_SURVIVES_at_its_own_value


def test_the_declared_cooldown_rule_is_gone_and_the_window_remains():
    """The replacement behaviour is gone; the engine's own window is not."""
    from app.core.trading_defaults import COLD_START_DEFAULTS, get_thresholds

    class _Profile:
        cooldown_after_loss = 15          # even if the legacy column holds one

        def __getattr__(self, _):
            return None

    th = get_thresholds(_Profile())
    assert "user_cooldown_min" not in th, "the declared cooldown is still resolved"
    assert th["revenge_window_min"] == COLD_START_DEFAULTS["revenge_window_min"]
    assert th["revenge_window_caution_min"] ==         COLD_START_DEFAULTS["revenge_window_caution_min"]


def test_the_frontend_can_still_name_a_stored_row():
    ctx = Path(__file__).resolve().parents[2] / "src" / "contexts" / "AlertContext.tsx"
    if not ctx.exists():
        return
    text = ctx.read_text(encoding="utf-8")

    routing = text[text.index("const BACKEND_TO_FRONTEND_TYPE"):]
    routing = routing[:routing.index("\n};")]
    assert "'cooldown_violation':" not in routing

    assert "'cooldown_violation': 'Cooldown ignored'" in text, (
        "stored rows must still render a human name")
