"""
Money rules are SUGGESTED, never applied — enforced end to end.

THE DEFECT (Pattern 24, fixed 1 Sep 2026)

`constitution_service.generate_defaults` returns `daily_loss_limit: None` and
`max_position_size: None` on purpose, offering `suggested_*` beside them. Its
comment gives the reason: F&O lot sizes are fixed, so on Rs 50,000 a 2%
per-trade rule allows Rs 1,000 while one option lot costs Rs 5,000-15,000 — an
auto-applied limit breaches on contact.

`OnboardingWizard.tsx` defeated that. It carried its own form defaults —
`daily_loss_limit: 5000` and `max_position_size: 50000` — which survived the
merge because the server's `null` lost to `??`. Every onboarded trader was
given:

  * a daily loss limit they never chose, at 2% of capital, from a second copy
    of the matrix that lived in the frontend, and
  * a per-trade risk rule in the WRONG UNIT — 50000 is rupees, and the backend,
    MyRules and the detector all read that field as a PERCENTAGE of capital, so
    the rule silently never fired.

MEASURED ON THE REFERENCE BOOK (175 sessions, intermediate profile):

    before, wizard defaults      Rs 50k   442 raw / 272 alerts, loss 175, risk 0
    after, not opted in          Rs 50k   267 raw / 184 alerts, loss   0, risk 0
    after, not opted in          Rs  1M   267 raw / 184 alerts  (capital-invariant)
    after, trader enables both   Rs 50k  1153 raw / 447 alerts, loss 175, risk 711
    after, trader enables both   Rs  1M   319 raw / 224 alerts, loss   0, risk  52

The default path produces NO money-rule alerts; an explicitly enabled rule is
enforced. Suggestion -> trader decides -> Rule becomes active.

Evidence: docs/patterns/24-constitution_violation/.
"""
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.trading_defaults import COLD_START_DEFAULTS
from app.services.behavior_engine import BehaviorEngine, EngineContext
from app.services.constitution_service import (
    RULE_FIELDS, ConstitutionService, classify_change, constitution_service,
)

engine = BehaviorEngine()
NOW = datetime(2026, 4, 15, 11, 0, tzinfo=timezone.utc)


# ── 1. the service still refuses to set money rules ────────────────────────

@pytest.mark.parametrize("level", ["beginner", "intermediate", "experienced", "professional"])
def test_generate_defaults_never_sets_a_money_rule(level):
    d = constitution_service.generate_defaults(level, 500_000)

    assert d["daily_loss_limit"] is None
    assert d["max_position_size"] is None


@pytest.mark.parametrize("level", ["beginner", "intermediate", "experienced", "professional"])
def test_it_does_suggest_them(level):
    """Suggested, so the trader has something to accept or reject."""
    d = constitution_service.generate_defaults(level, 500_000)

    assert d["suggested_daily_loss_limit"] is not None
    assert d["suggested_max_position_size"] is not None


def test_the_suggested_risk_is_a_PERCENTAGE_not_rupees():
    """
    The whole units defect. 1.0-3.0 is a share of capital; the wizard used to
    submit 50000, a rupee figure, into the same field.
    """
    for level in ("beginner", "intermediate", "experienced", "professional"):
        pct = constitution_service.generate_defaults(level, 500_000)["suggested_max_position_size"]
        assert 0 < pct <= 10, f"{level}: {pct} is not a percentage of capital"


def test_the_suggested_loss_limit_needs_capital_and_says_so():
    """It is derived from capital, so with none there is nothing to suggest."""
    assert constitution_service.generate_defaults("intermediate", None)[
        "suggested_daily_loss_limit"] is None
    assert constitution_service.generate_defaults("intermediate", 0)[
        "suggested_daily_loss_limit"] is None


def test_the_count_and_time_rules_ARE_set():
    """
    They are not shares of capital — "more than 10 trades today" means the same
    at any account size — so they ship enforced.
    """
    d = constitution_service.generate_defaults("intermediate", None)

    assert d["daily_trade_limit"] == 10
    assert d["cooldown_after_loss"] == 10
    assert d["max_consecutive_losses"] == 4


# ── 2. the endpoint can suggest for capital that is not yet saved ──────────

def test_the_generate_endpoint_accepts_a_capital_override():
    """
    The wizard collects capital on the same screen that shows the suggestion,
    and does not persist it until that step is submitted. Without this the
    server could only answer "no suggestion" and the opt-in checkbox could
    never be ticked during onboarding.
    """
    import inspect

    import app.api.constitution as mod

    src = inspect.getsource(mod)
    assert "class GenerateRequest" in src
    assert "trading_capital: Optional[float] = None" in src

    sig = inspect.signature(mod.generate_recommended)
    assert "body" in sig.parameters
    assert sig.parameters["body"].default is None, (
        "POST {} must keep working — the override is optional")


def test_the_override_does_not_change_what_is_suggested():
    """It passes an argument generate_defaults already takes. Nothing more."""
    direct = constitution_service.generate_defaults("intermediate", 250_000)

    assert direct["suggested_daily_loss_limit"] == round(250_000 * 0.02)
    assert direct["daily_loss_limit"] is None, (
        "supplying capital must still not ENFORCE a money rule")


# ── 3. enabling a rule is a TIGHTEN, so it applies without friction ────────

def test_turning_a_money_rule_on_is_a_tighten():
    """None -> value. The trader gains a constraint, so there is nothing to protect."""
    assert classify_change("daily_loss_limit", None, 5000) == "tighten"
    assert classify_change("max_position_size", None, 2.0) == "tighten"


def test_leaving_it_off_is_not_a_change_at_all():
    assert classify_change("daily_loss_limit", None, None) is None
    assert classify_change("max_position_size", None, None) is None


def test_both_money_rules_are_real_rule_fields():
    assert "daily_loss_limit" in RULE_FIELDS
    assert "max_position_size" in RULE_FIELDS


def test_the_onboarding_handler_drops_nulls():
    """
    The backend half of the opt-in: a rule the trader did not enable arrives as
    null and is never written, so the profile keeps None.
    """
    import inspect

    import app.api.profile as mod

    src = inspect.getsource(mod)
    assert "{k: v for k, v in rules.items() if v is not None}" in src


# ── 4. the detector abstains on an un-opted rule, enforces an opted one ────

def _ct(qty=750, pnl=-5000):
    return SimpleNamespace(
        id=uuid4(), broker_account_id=uuid4(), tradingsymbol="NIFTY25APR24000CE",
        exchange="NFO", product="MIS", instrument_type="CE", direction="LONG",
        total_quantity=qty, avg_entry_price=Decimal("100"),
        avg_exit_price=Decimal("90"), realized_pnl=Decimal(str(pnl)), pnl_pct=None,
        duration_minutes=30, entry_time=NOW, exit_time=NOW,
        num_entries=1, num_exits=1, status="closed", quality_score=None)


def _ctx(ct, **rules):
    th = dict(COLD_START_DEFAULTS)
    th.update(rules)
    return EngineContext(
        broker_account_id=ct.broker_account_id,
        session=SimpleNamespace(session_pnl=Decimal("-20000"),
                                session_date=NOW.date(), market_open=None),
        completed_trade=ct, session_trades=[ct], thresholds=th)


def _rules(evs):
    return sorted(e.context["rule"] for e in (evs or []))


def test_the_detector_is_silent_on_money_rules_that_were_not_enabled():
    """
    The default path. A heavily losing, heavily sized trade raises NO money-rule
    alert, because the trader never declared either limit.
    """
    evs = engine._detect_constitution_violation(
        _ctx(_ct(), daily_loss_limit=None, max_position_size=None,
             trading_capital=50_000))

    fired = _rules(evs)
    assert "daily_loss" not in fired
    assert "max_trade_risk" not in fired


def test_an_ENABLED_loss_limit_is_enforced():
    evs = engine._detect_constitution_violation(
        _ctx(_ct(), daily_loss_limit=5000, max_position_size=None,
             trading_capital=50_000))

    assert "daily_loss" in _rules(evs)


def test_an_ENABLED_risk_rule_is_enforced_AS_A_PERCENTAGE():
    """
    2.0 means 2% of capital. If this field were ever fed a rupee figure again
    the ratio would collapse to ~0 and the rule would go quiet — which is
    exactly how it was broken.
    """
    enabled = engine._detect_constitution_violation(
        _ctx(_ct(), max_position_size=2.0, trading_capital=50_000))
    assert "max_trade_risk" in _rules(enabled)

    as_rupees = engine._detect_constitution_violation(
        _ctx(_ct(), max_position_size=50000, trading_capital=50_000))
    assert "max_trade_risk" not in _rules(as_rupees), (
        "a rupee figure in a percentage field silently disables the rule — the "
        "defect this fix removed at its source")
