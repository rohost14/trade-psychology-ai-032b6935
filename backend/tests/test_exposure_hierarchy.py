"""
The exposure hierarchy, pinned. Implemented 2026-09-01.

THREE CONCEPTS THAT MUST NEVER MERGE:

  1. TOTAL PORTFOLIO UTILISATION - capital deployed against trading capital.
     INFORMATION ONLY. Never a RiskAlert, never a ladder, never a push.
     80% utilised is not a finding; it is a number on a screen.

  2. SINGLE-POSITION EXPOSURE - one position's capital requirement against
     trading capital. A breach of the limit THE TRADER DECLARED, and nothing
     else. NO DECLARED RULE, NO ALERT. There is no universal exposure
     threshold and none replaced the retired 5/10/15/30/50.

  3. SEVERE POSITION LOSS - percent of premium destroyed. UNIVERSAL SAFETY,
     40/60/80, unchanged. Independent of any exposure rule, and it fires
     whether or not the trader declared anything.

WHY THE UNIVERSAL EXPOSURE LINE WENT. Measured against live resolution: a
trader who DECLARED a 40% limit was told DANGER at 35% - inside their own rule -
because `safety_bounds` clamps a declared value so it may only tighten, and the
alert could not distinguish 35% from 45%. The outcome evidence never supported
it either: per round, 0-5% of capital won 40.2%, 5-10% 37.4%, 10-15% 43.1%,
15-25% 43.9% - no trend - and only 25%+ separated, at n=10 with 81% of that
bucket's loss from one position.

WHY THE SEVERE-LOSS LINE STAYED. A large loss is objective danger. How much of
their own capital a trader commits is a decision.
"""
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.risk_quantities import quantities_for_trade
from app.core.threshold_resolution import resolve_thresholds
from app.core.trading_defaults import COLD_START_DEFAULTS, get_thresholds
from app.services.live_risk_state import DECLARED, UNIVERSAL, build_watches

CAP = 100_000.0


def _consts(fn):
    """Every string constant in a function, including nested tuples."""
    out = set()

    def walk(code):
        for c in code.co_consts:
            if isinstance(c, str):
                out.add(c)
            elif isinstance(c, tuple):
                out.update(x for x in c if isinstance(x, str))
            elif hasattr(c, "co_consts"):
                walk(c)

    walk(fn.__code__)
    return out


def _names(fn):
    out = set(fn.__code__.co_names)
    for c in fn.__code__.co_consts:
        if hasattr(c, "co_names"):
            out.update(c.co_names)
    return out

#: Everything the old universal exposure ladder was made of.
RETIRED_EXPOSURE_KEYS = ("max_position_pct_caution", "max_position_pct_danger")


class Prof:
    """A profile with nothing declared unless the test declares it."""

    trading_capital = CAP
    detected_patterns = None

    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)

    def __getattr__(self, _n):
        return None


def a_position(symbol="NIFTY26FEB24000CE", qty=400, entry=75.0,
               itype="CE", direction="LONG"):
    return SimpleNamespace(
        id=uuid4(), tradingsymbol=symbol, exchange="NFO", product="MIS",
        instrument_type=itype, direction=direction, total_quantity=abs(qty),
        avg_entry_price=Decimal(str(entry)), avg_exit_price=None,
        realized_pnl=None, pnl_pct=None,
    )


# ══ 1. NO UNIVERSAL EXPOSURE THRESHOLD EXISTS ANY MORE ═════════════════════

@pytest.mark.parametrize("key", RETIRED_EXPOSURE_KEYS)
def test_the_universal_exposure_thresholds_are_gone(key):
    from app.core.threshold_registry import THRESHOLD_SPECS

    assert key not in COLD_START_DEFAULTS, key
    assert key not in THRESHOLD_SPECS, key


@pytest.mark.parametrize("declared", [None, 3.0, 10.0, 40.0, 80.0])
@pytest.mark.parametrize("key", RETIRED_EXPOSURE_KEYS)
def test_no_resolver_produces_them_at_any_declared_value(declared, key):
    """
    Both resolvers used to put these, and a declared `max_position_size` was
    mapped onto them. Neither does now - at any declared value, including none.
    """
    ts = resolve_thresholds(Prof(max_position_size=declared))
    assert key not in ts.values
    assert ts.explain(key) is None
    assert key not in get_thresholds(Prof(max_position_size=declared))
    assert key not in get_thresholds(None)


def test_no_replacement_exposure_threshold_was_invented():
    """
    The instruction was explicit: remove them, do not replace them. This fails
    if any new percent-of-capital exposure key appears under any name.
    """
    from app.core.threshold_registry import THRESHOLD_SPECS

    for pool in (COLD_START_DEFAULTS, THRESHOLD_SPECS):
        for k in pool:
            assert "max_position_pct" not in k, k
            assert not k.startswith("exposure_"), k


def test_no_live_module_reads_them():
    from pathlib import Path

    app = Path(__file__).resolve().parents[1] / "app"
    offenders = []
    for path in app.rglob("*.py"):
        if "__pycache__" in path.parts or "_archive" in path.parts:
            continue
        for n, line in enumerate(
                path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            if any(k in line for k in RETIRED_EXPOSURE_KEYS):
                offenders.append(f"{path.relative_to(app)}:{n}")
    assert offenders == [], offenders


# ══ 2. excess_exposure IS RETIRED ══════════════════════════════════════════

def test_excess_exposure_is_gone_from_engine_and_vocabulary():
    from app.services.behavior_engine import BehaviorEngine
    from app.services.detector_registry import (
        ALIASES, BY_NAME, PATTERN_COPY, REGISTRY, all_pattern_types,
    )

    assert not hasattr(BehaviorEngine(), "_detect_excess_exposure")
    for pool in (BY_NAME, ALIASES, PATTERN_COPY, all_pattern_types()):
        assert "excess_exposure" not in pool
    assert all(d.name != "excess_exposure" for d in REGISTRY)
    assert all(d.method != "_detect_excess_exposure" for d in REGISTRY)


def test_portfolio_concentration_is_gone_too():
    """Retired in the same review; informational composition is still allowed."""
    from app.services.detector_registry import ALIASES, PATTERN_COPY, all_pattern_types
    import app.tasks.position_monitor_tasks as pm

    for pool in (ALIASES, PATTERN_COPY, all_pattern_types()):
        assert "portfolio_concentration" not in pool
    assert not hasattr(pm, "_concentration_task")
    assert not hasattr(pm, "check_portfolio_concentration")


def test_nothing_imports_the_removed_tasks():
    """
    THE BUG THIS EXISTS TO PREVENT, and it was real: `trade_tasks` imported
    `_concentration_task` inside a broad `try/except Exception`. Deleting the
    task turned that into an ImportError which the except swallowed, silently
    skipping EVERY event-driven position check - exposure, adverse-add and the
    holding-loser schedule - with one warning line. Caught only by the
    end-to-end integration test.
    """
    from pathlib import Path

    app = Path(__file__).resolve().parents[1] / "app"
    offenders = []
    for path in app.rglob("*.py"):
        if "__pycache__" in path.parts or "_archive" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for n, line in enumerate(text.splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            if "_concentration_task" in line or "check_portfolio_concentration" in line:
                offenders.append(f"{path.relative_to(app)}:{n}")
    assert offenders == [], offenders


# ══ 3. NO DECLARED RULE -> NO EXPOSURE ALERT, AT ANY UTILISATION ═══════════

@pytest.mark.parametrize("pct_of_capital", [20, 30, 60, 80, 90, 100, 150])
async def test_no_declared_rule_means_no_exposure_alert_at_any_size(pct_of_capital):
    """
    THE HIERARCHY'S FIRST RULE. 80%, 90%, 100% of capital in one position is
    not a finding when the trader set no limit - it is their decision.
    """
    import app.tasks.position_monitor_tasks as pm

    ts = get_thresholds(Prof(max_position_size=None))
    assert not ts.get("max_position_size")

    qty = int(CAP * pct_of_capital / 100 / 75.0)
    pos = a_position(qty=qty)
    rq = quantities_for_trade(pos, margin=None)
    assert rq.usable_for_capital_rules
    # the position really is that large - the test is not vacuous
    assert abs(float(rq.capital_requirement.amount) / CAP * 100
               - pct_of_capital) < 2

    # the entry-time arm abstains for want of a rule, before any alert path
    assert "no_declared_exposure_rule" in _consts(pm._overexposure_task),         "the no-rule gate is gone"


def test_utilisation_is_never_an_alert_input():
    """
    CONCEPT 1. Total deployed capital is carried by
    `MarginSnapshot.equity_utilization_pct` and read by NO detector. If a
    detector ever starts reading it, this fails.
    """
    from pathlib import Path

    app = Path(__file__).resolve().parents[1] / "app"
    engine = (app / "services" / "behavior_engine.py").read_text(encoding="utf-8")
    body = "\n".join(l for l in engine.splitlines()
                     if not l.lstrip().startswith("#"))
    for token in ("equity_utilization_pct", "commodity_utilization_pct",
                  "max_utilization_pct", "MarginSnapshot"):
        assert token not in body, f"the engine reads {token}"


# ══ 4. A DECLARED RULE IS THE ONLY EXPOSURE ALERT, AND IT IS max_trade_risk ═

def test_the_declared_rule_is_evaluated_on_capital_requirement():
    """
    Rs 80,000 of capital requirement on Rs 1,00,000 of capital is 80%.
    NOT 575%, which is what notional produces for a future.
    """
    pos = a_position(qty=1067, entry=75.0)          # ~Rs 80,000 of premium
    rq = quantities_for_trade(pos, margin=None)
    pct = float(rq.capital_requirement.amount) / CAP * 100
    assert 79.5 <= pct <= 80.5, pct


def test_a_declared_rule_governs_and_the_old_universal_line_does_not():
    """
    The exact case that condemned the universal line: declare 80%, sit at 75%.
    Inside the rule, so nothing may fire - where `excess_exposure` used to say
    DANGER because the safety bound had clamped 80 down to 5/10.
    """
    ts = resolve_thresholds(Prof(max_position_size=80.0))
    assert ts["max_position_size"] == 80.0
    for key in RETIRED_EXPOSURE_KEYS:
        assert ts.explain(key) is None

    ratio_at_75 = 75.0 / 80.0
    ratio_at_85 = 85.0 / 80.0
    approaching = COLD_START_DEFAULTS["constitution_approaching_pct"]
    assert ratio_at_75 < 1.0
    assert ratio_at_85 >= 1.0
    # 75/80 = 0.94 is "approaching" on the trader's own ladder, never a breach
    assert approaching <= ratio_at_75 < 1.0


def test_entry_and_exit_share_one_dedup_key_so_a_breach_alerts_once():
    """
    NO DUPLICATE BETWEEN ENTRY AND EXIT. The entry-time arm emits
    `constitution_violation` with rule="max_trade_risk" - the same pattern type
    and rule the exit-time constitution check uses - so `_pattern_dedup_key`
    collapses them. Two pattern types could never be joined, which is what
    produced 820 / 453 / 215 duplicate firings at declared limits of 5/10/15%.
    """
    from app.tasks.trade_tasks import _pattern_dedup_key
    import app.tasks.position_monitor_tasks as pm

    entry = _pattern_dedup_key("constitution_violation", {"rule": "max_trade_risk"})
    exit_ = _pattern_dedup_key("constitution_violation", {"rule": "max_trade_risk"})
    assert entry == exit_ == "constitution_violation:max_trade_risk"

    # and a different rule is still its own key
    assert _pattern_dedup_key(
        "constitution_violation", {"rule": "daily_loss"}) != entry

    consts = _consts(pm._overexposure_task)
    assert "constitution_violation" in consts
    assert "max_trade_risk" in consts


def test_the_entry_arm_never_falls_back_to_notional():
    import app.tasks.position_monitor_tasks as pm

    consts = _consts(pm._overexposure_task)
    assert "capital_requirement_unavailable" in consts
    names = _names(pm._overexposure_task)
    assert "_exposure_value" not in names, "notional is back on the entry path"
    assert "quantities_for_trade" in names


def test_the_emotional_size_bump_is_gone_and_must_not_return():
    """
    Was `test_the_emotional_size_bump_survives`. It was kept through the
    2026-09-01 rework by decision and never validated; it was REMOVED on
    2026-09-02 as F20, and this test now pins the removal.

    Why it went: it read `BehaviorEvent` rows for three other detectors and
    escalated this rule danger -> critical, which is the one violation of the
    registry's own "no detector may consume another detector's output" (A.10).
    And the query never excluded SUPPRESSED events — suppression is
    notification-only, so the rows exist — meaning a finding the trader was
    never told about made a DIFFERENT alert critical.

    Filtering suppressed rows out would have been a third patch on a forbidden
    dependency, so the dependency is gone. Severity is now whatever this
    rule's own ladder computed.
    """
    import app.tasks.position_monitor_tasks as pm

    consts = _consts(pm._overexposure_task)
    for token in ("post_loss_recovery_bet", "martingale_behaviour", "revenge_trade"):
        assert token not in consts, f"the emotional bump is back via {token}"
    assert "emotional_bump" not in consts


# ══ 5. FUTURES AND NAKED SHORTS ABSTAIN ════════════════════════════════════

@pytest.mark.parametrize("pos,label", [
    (a_position("CIPLA26JANFUT", 375, 1533.2, itype="FUT"), "future"),
    (a_position(qty=-400, direction="SHORT"), "naked short option"),
])
def test_they_abstain_when_margin_is_unavailable(pos, label):
    """
    `position_margin_observations` is empty, the Kite postback carries no
    margin and /margins/orders is prospective, so the capital requirement is
    genuinely unknown. Silence beats "575.0% of capital".
    """
    rq = quantities_for_trade(pos, margin=None)
    assert not rq.usable_for_capital_rules, label
    assert rq.capital_requirement.amount is None
    assert "margin" in (rq.capital_requirement.note or "").lower()


def test_a_naked_short_is_never_described_as_loss_bounded():
    """
    Its denominator_kind says the loss is NOT bounded by what was committed, so
    no copy may present the margin as a maximum loss.
    """
    from app.core.risk_quantities import DenominatorKind

    short = quantities_for_trade(a_position(qty=-400, direction="SHORT"))
    assert short.denominator_kind is DenominatorKind.MARGIN_POSTED
    assert not short.loss_is_bounded

    long_opt = quantities_for_trade(a_position(qty=400))
    assert long_opt.denominator_kind is DenominatorKind.LOSS_CEILING
    assert long_opt.loss_is_bounded


def test_a_bought_option_is_definitional_and_needs_no_margin():
    rq = quantities_for_trade(a_position(qty=400, entry=75.0), margin=None)
    assert rq.usable_for_capital_rules
    assert float(rq.capital_requirement.amount) == pytest.approx(30_000.0)


def test_multi_leg_grouping_is_not_invented():
    """
    Both arms are POSITION level. Pattern 24 measured `strategy_group` unusable
    for netting - 45% of grouped rounds have no closed sibling at their own
    exit - so each leg is judged alone and that overstatement is a documented
    limitation, not a silent guess.
    """
    import app.tasks.position_monitor_tasks as pm

    names = _names(pm._overexposure_task)
    assert "strategy_group" not in names
    assert "StrategyGroup" not in names


# ══ 6. SEVERE LOSS IS A SEPARATE, UNCHANGED, UNIVERSAL LAYER ═══════════════

def test_the_severe_loss_ladder_is_unchanged_at_40_60_80():
    from app.core.threshold_registry import Kind, THRESHOLD_SPECS

    assert COLD_START_DEFAULTS["premium_loss_caution_pct"] == 40
    assert COLD_START_DEFAULTS["premium_loss_danger_pct"] == 60
    assert COLD_START_DEFAULTS["premium_loss_critical_pct"] == 80
    for k in ("premium_loss_caution_pct", "premium_loss_danger_pct",
              "premium_loss_critical_pct"):
        assert THRESHOLD_SPECS[k].kind is Kind.UNIVERSAL_SAFETY


def _watch(thresholds, entry=75.0, qty=400):
    return build_watches(
        positions=[SimpleNamespace(
            tradingsymbol="NIFTY26FEB24000CE", total_quantity=qty,
            average_entry_price=Decimal(str(entry)), instrument_token=1,
            exchange="NFO")],
        thresholds=thresholds, broker_account_id="acct")


def test_universal_severe_loss_fires_with_no_declared_rule_of_any_kind():
    """CONCEPT 3, standing alone. Nothing declared: no exposure rule, no SL."""
    ts = resolve_thresholds(Prof())
    assert ts.get("max_position_size") is None
    assert ts.get("sl_percent_options") is None

    (w,) = _watch(ts)
    crossings = w.evaluate(75.0 * 0.30)          # 70% of premium gone
    kinds = {c.kind for c in crossings}
    assert UNIVERSAL in kinds, "the universal ladder went silent"
    assert DECLARED not in kinds, "a rule was fabricated from nothing"


def test_an_exposure_rule_does_not_suppress_severe_loss():
    """The two concepts share no threshold, no path and no dedup scope."""
    ts = resolve_thresholds(Prof(max_position_size=80.0))
    (w,) = _watch(ts)
    crossings = w.evaluate(75.0 * 0.30)
    assert any(c.kind is UNIVERSAL or c.kind == UNIVERSAL for c in crossings)


# ══ 7. sl_percent_* : AN UNDECLARED RULE IS NOT A FACT ═════════════════════

# `sl_percent_futures` was removed as a user input 2026-09-02, so only the
# surviving optional stop rule is checked here.
@pytest.mark.parametrize("key", ["sl_percent_options"])
def test_an_undeclared_stop_rule_resolves_to_none_not_a_number(key):
    """
    It was `... or 50.0` / `or 1.0` marked Source.FACT confidence 1.0 - the
    provenance reserved for something the trader declared. A trader who set
    nothing was told "You set your options exit at 50% of premium" in a
    constitution_violation at notification_level 4.
    """
    from app.core.threshold_resolution import Source

    ts = resolve_thresholds(Prof())
    assert ts.get(key) is None
    r = ts.explain(key)
    assert r.source is Source.GLOBAL
    assert r.confidence == 0.0

    assert get_thresholds(Prof()).get(key) is None
    assert get_thresholds(None).get(key) is None


def test_a_declared_stop_rule_still_works_and_is_marked_as_declared():
    from app.core.threshold_resolution import Source

    ts = resolve_thresholds(Prof(sl_percent_options=30.0))
    assert ts["sl_percent_options"] == 30.0
    assert ts.explain("sl_percent_options").source is Source.FACT

    (w,) = _watch(ts)
    kinds = {c.kind for c in w.evaluate(75.0 * 0.60)}   # 40% of premium gone
    assert DECLARED in kinds, "a declared rule stopped working"


def test_the_fabricated_rule_can_no_longer_pre_empt_the_universal_band():
    """
    The invented 50 sat BETWEEN universal caution (40) and danger (60), and
    `_fire_position_alert` gives the declared crossing precedence - so on all 10
    reference-book rounds that reached the real 60% band, the fabricated rule
    pre-empted it and the safety finding was demoted to details["also_crossed"].
    """
    ts = resolve_thresholds(Prof())
    (w,) = _watch(ts)
    crossings = w.evaluate(75.0 * 0.45)    # 55% down: past 40, short of 60
    assert all(c.kind != DECLARED for c in crossings)


# ══ 8. NOTHING ELSE MOVED ══════════════════════════════════════════════════

def test_the_money_rules_are_untouched():
    """daily_loss_limit and per_trade_loss_limit: opt-in, None by default."""
    from app.services.constitution_service import ConstitutionService, RULE_FIELDS

    for f in ("daily_loss_limit", "per_trade_loss_limit", "max_position_size"):
        assert f in RULE_FIELDS
    d = ConstitutionService.generate_defaults(
        experience_level="intermediate", trading_capital=CAP)
    for f in ("daily_loss_limit", "per_trade_loss_limit", "max_position_size"):
        assert d.get(f) is None, f"{f} is no longer opt-in"


def test_the_constitution_ladder_is_untouched():
    assert COLD_START_DEFAULTS["constitution_approaching_pct"] == 0.80
    assert COLD_START_DEFAULTS["constitution_severe_pct"] == 1.20


def test_the_engine_counts_are_what_this_retirement_left():
    from app.services.detector_registry import ALIASES, REGISTRY, all_pattern_types

    # 2026-09-02, two retirements on one day: `death_spiral` (5 -> 4 aliases,
    # 20 -> 19 pattern types) and `strategy_breakdown` (15 -> 14 detectors,
    # 19 -> 18 pattern types). Neither is this file's subject; the counts are
    # asserted here because a wrong one means a spec went missing silently.
    assert len(REGISTRY) == 14
    assert len(ALIASES) == 2
    assert len(all_pattern_types()) == 16


def test_the_surviving_detectors_are_exactly_these():
    from app.services.detector_registry import REGISTRY

    assert {d.name for d in REGISTRY} == {
        "revenge_trade", "overtrading_burst", "rapid_reentry",
        "martingale_behaviour", "adding_to_adverse_position",
        "session_meltdown", "fomo_entry", "no_stoploss", "premium_loss_event",
        "end_of_session_mis_panic", "post_loss_recovery_bet",
        "constitution_violation", "same_symbol_obsession",
        # `strategy_breakdown` retired 2026-09-02 - it required a win-rate AND
        # a profit-factor collapse together, and the profit-factor half never
        # bound: identical firing set to `win_rate_collapse`, zero unique.
        "win_rate_collapse",
    }


# ══ 9. max_trade_risk HAS NO PRE-BREACH RUNG ═══════════════════════════════
#
# Added 2026-09-01. A trader who declared an 80% limit and took 75% did exactly
# what they said they would; reporting that as "approaching" turns compliance
# into a finding. `caution` writes a real RiskAlert (trade_tasks skips only
# `info`), so it reached the Alerts screen even though it is not notifiable.
#
# The shared ladder's NUMBERS are untouched and every other rule keeps all
# three rungs - see the daily-loss and per-trade-loss tests below.

from datetime import datetime, timezone


def _ctx(thresholds, ct, session_pnl=0.0):
    return SimpleNamespace(
        completed_trade=ct, thresholds=thresholds, broker_margin=None,
        session=SimpleNamespace(session_pnl=session_pnl, trade_count=0),
        strategy_group=None, session_trades=[], concluded_before_entry=[],
        account_risk=None,
    )


def _exposure_events(declared_limit, pct_of_capital):
    """Run the REAL detector and return only its max_trade_risk events."""
    from app.services.behavior_engine import BehaviorEngine

    # price 100 so every percentage lands on an exact integer quantity -
    # at 75.0 the rounding put "40%" at 39.975% and the boundary case passed
    # for the wrong reason.
    qty = round(CAP * pct_of_capital / 100 / 100.0)
    ct = a_position(qty=qty, entry=100.0)
    ct.realized_pnl = Decimal("0")
    ct.entry_time = datetime(2026, 2, 2, 4, 0, tzinfo=timezone.utc)
    ct.exit_time = datetime(2026, 2, 2, 5, 0, tzinfo=timezone.utc)

    th = get_thresholds(Prof(max_position_size=declared_limit))
    got = BehaviorEngine()._detect_constitution_violation(_ctx(th, ct)) or []
    return [e for e in got if (e.context or {}).get("rule") == "max_trade_risk"]


@pytest.mark.parametrize("limit,size,expect", [
    # 40% rule
    (40.0, 39.9, None),
    (40.0, 40.0, "danger"),
    (40.0, 45.0, "danger"),
    (40.0, 50.0, "critical"),        # 1.25x - the severe rung is unchanged
    # 80% rule
    (80.0, 75.0, None),              # THE CASE THIS FIX EXISTS FOR
    (80.0, 79.9, None),
    (80.0, 80.0, "danger"),
    (80.0, 85.0, "danger"),
    (80.0, 96.0, "critical"),        # 1.20x
    # a tight rule behaves the same way
    (5.0, 4.9, None),
    (5.0, 5.0, "danger"),
])
def test_the_exposure_rule_alerts_only_at_or_past_the_declared_limit(
        limit, size, expect):
    events = _exposure_events(limit, size)
    if expect is None:
        assert events == [], (
            f"{size}% against a {limit}% limit produced {[e.severity for e in events]}"
            " - the trader is inside their own rule")
    else:
        assert len(events) == 1, [e.severity for e in events]
        assert events[0].severity == expect
        assert "breached" in events[0].message
        assert "approaching" not in events[0].message


def test_no_declared_exposure_rule_produces_nothing_at_any_size():
    for size in (20, 50, 75, 90, 100, 150):
        assert _exposure_events(None, size) == [], size


def test_the_entry_arm_uses_the_same_two_rungs():
    """
    Both arms are one rule under one dedup key. A rung at entry that the exit
    rule does not have would fire once and never be reconciled.
    """
    import app.tasks.position_monitor_tasks as pm

    consts = _consts(pm._overexposure_task)
    assert "critical" in consts and "danger" in consts
    assert "caution" not in consts, "the entry arm kept a pre-breach rung"
    assert "constitution_approaching_pct" not in consts
    assert "constitution_severe_pct" in consts


# ── the other constitution rules KEEP all three rungs ──────────────────────

def test_daily_loss_keeps_its_approaching_rung():
    from app.services.behavior_engine import BehaviorEngine

    ct = a_position(qty=100)
    ct.realized_pnl = Decimal("-100")
    ct.entry_time = datetime(2026, 2, 2, 4, 0, tzinfo=timezone.utc)
    ct.exit_time = datetime(2026, 2, 2, 5, 0, tzinfo=timezone.utc)
    th = get_thresholds(Prof(daily_loss_limit=10_000.0))

    # 85% of the daily loss limit used - still climbing, still worth saying
    got = BehaviorEngine()._detect_constitution_violation(
        _ctx(th, ct, session_pnl=-8_500.0)) or []
    daily = [e for e in got if (e.context or {}).get("rule") == "daily_loss"]
    assert len(daily) == 1
    assert daily[0].severity == "caution"
    assert "approaching" in daily[0].message.lower()


def test_per_trade_loss_keeps_its_approaching_rung():
    from app.services.behavior_engine import BehaviorEngine

    ct = a_position(qty=100)
    ct.realized_pnl = Decimal("-4250")          # 85% of a Rs 5,000 limit
    ct.entry_time = datetime(2026, 2, 2, 4, 0, tzinfo=timezone.utc)
    ct.exit_time = datetime(2026, 2, 2, 5, 0, tzinfo=timezone.utc)
    th = get_thresholds(Prof(per_trade_loss_limit=5_000.0))

    got = BehaviorEngine()._detect_constitution_violation(_ctx(th, ct)) or []
    per = [e for e in got if (e.context or {}).get("rule") == "per_trade_loss"]
    assert len(per) == 1
    assert per[0].severity == "caution"
    assert "approaching" in per[0].message.lower()


def test_the_ladder_numbers_did_not_move():
    assert COLD_START_DEFAULTS["constitution_approaching_pct"] == 0.80
    assert COLD_START_DEFAULTS["constitution_severe_pct"] == 1.20
