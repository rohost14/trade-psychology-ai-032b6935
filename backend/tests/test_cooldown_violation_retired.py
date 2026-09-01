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
    assert len(ALIASES) == 5
    assert len(all_pattern_types()) == 20


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


def test_the_traders_declared_cooldown_rule_still_resolves():
    from app.core.trading_defaults import get_thresholds

    class _Profile:
        cooldown_after_loss = 15

        def __getattr__(self, _):
            return None

    th = get_thresholds(_Profile())
    assert th["user_cooldown_min"] == 15
    assert th["revenge_window_min"] == 15, (
        "the declared cooldown also drives revenge_trade's window")


def test_constitution_violation_still_owns_the_behaviour():
    """
    The reason this retirement is safe. The trader's declared cooldown is
    enforced here, at DANGER, with their own number in the message.
    """
    from app.core.trading_defaults import COLD_START_DEFAULTS
    from app.services.behavior_engine import BehaviorEngine, EngineContext

    engine = BehaviorEngine()
    now = datetime(2026, 4, 15, 10, 0, tzinfo=timezone.utc)

    def _ct(entry, exit_, pnl):
        return SimpleNamespace(
            id=uuid4(), broker_account_id=uuid4(), tradingsymbol="NIFTY25APR24000CE",
            exchange="NFO", product="MIS", instrument_type="CE", direction="LONG",
            total_quantity=75, avg_entry_price=Decimal("100"),
            avg_exit_price=Decimal("90"), realized_pnl=Decimal(str(pnl)),
            duration_minutes=10, entry_time=entry, exit_time=exit_,
            num_entries=1, num_exits=1, status="closed")

    loss = _ct(now - timedelta(minutes=20), now - timedelta(minutes=10), -2400)
    reentry = _ct(now - timedelta(minutes=7), now, -500)   # 3 min after the loss

    th = dict(COLD_START_DEFAULTS)
    th["user_cooldown_min"] = 15
    ctx = EngineContext(
        broker_account_id=reentry.broker_account_id,
        session=SimpleNamespace(session_pnl=Decimal("-2900"),
                                session_date=now.date(), market_open=None),
        completed_trade=reentry, session_trades=[loss, reentry],
        thresholds=th)

    events = engine._detect_constitution_violation(ctx) or []
    cooldown_events = [e for e in events if "cooldown" in (e.message or "").lower()]
    assert cooldown_events, "the declared cooldown rule must still fire"
    assert cooldown_events[0].severity == "danger"
    assert "15-minute cooldown rule violated" in cooldown_events[0].message


# ── 4. historical rows stay readable ───────────────────────────────────────

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
