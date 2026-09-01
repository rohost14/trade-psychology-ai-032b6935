"""
Pattern 24 — the three consistency fixes to `constitution_violation`.

All three are "no behavioural change intended", and the review measured that
each holds. Verified after the change at the same configuration the review
used (declared: loss limit 2% of Rs 50k, trades 10, cooldown 15, consec 3):

    raw events              606   unchanged
    max_consecutive_losses  194   unchanged
    cooldown                181   unchanged   <- the relation change
    daily_loss              175   unchanged
    daily_trades             56   unchanged
    max_trade_risk            0   unchanged   <- the abstain change

WHAT CHANGED AND WHY

1. The cooldown rule read `t.exit_time <= ct.entry_time` inline while
   `EngineContext.concluded_before_entry` - the shared CONCLUDED relation
   introduced at the temporal-contract work - uses `<`. The two disagreed only
   at identical timestamps, which the review measured at 0 of 740 trades. It is
   now the shared relation, so there is ONE definition of "the trader could see
   this loss when they entered".

2. `max_trade_risk` abstained with `return events or None`, which was correct
   only because it is the LAST rule. A rule added below it would have been
   silently skipped whenever capital was not determinable - 2% of trades today,
   and 100% for an exchange the risk layer must abstain on. Abstaining from one
   rule must not abstain from the others.

3. `constitution_approaching_pct` (0.80) and `constitution_severe_pct` (1.20)
   had no THRESHOLD_SPECS record. They are now classified PRODUCT_POLICY with
   their values UNCHANGED. They are the only two numbers this detector chooses.

Evidence: docs/patterns/24-constitution_violation/.
"""
import inspect
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from app.core.trading_defaults import COLD_START_DEFAULTS
from app.services.behavior_engine import BehaviorEngine, EngineContext

engine = BehaviorEngine()
DAY = datetime(2026, 4, 15, tzinfo=timezone.utc)
ACCT = uuid4()


# Two cooldown tests were DELETED 2026-09-02 WITH THEIR SUBJECT. `cooldown_after_loss` stopped being a user-configurable rule on
# 2026-09-02, so there is no declared cooldown to measure against. The
# engine keeps its own revenge window (`revenge_window_min`, fallback 10),
# pinned by test_rule_clearing_and_removals::
# test_THE_PROTECTION_SURVIVES_at_its_own_value.


def at(h, m):
    return DAY.replace(hour=h, minute=m)


def trade(entry, exit_, pnl, qty=75, sym="NIFTY25APR24000CE"):
    return SimpleNamespace(
        id=uuid4(), broker_account_id=ACCT, tradingsymbol=sym,
        exchange="NFO", product="MIS", instrument_type="CE", direction="LONG",
        total_quantity=qty, avg_entry_price=Decimal("100"),
        avg_exit_price=Decimal("90"), realized_pnl=Decimal(str(pnl)), pnl_pct=None,
        duration_minutes=int((exit_ - entry).total_seconds() // 60),
        entry_time=entry, exit_time=exit_,
        num_entries=1, num_exits=1, status="closed", quality_score=None)


def ctx(current, priors, **rules):
    th = dict(COLD_START_DEFAULTS)
    th.update(rules)
    return EngineContext(
        broker_account_id=ACCT,
        session=SimpleNamespace(
            session_pnl=Decimal(str(sum(float(t.realized_pnl) for t in priors))),
            session_date=DAY.date(), market_open=None),
        completed_trade=current, session_trades=list(priors), thresholds=th)


def rules_fired(evs):
    return sorted(e.context["rule"] for e in (evs or []))


# ── 1. the cooldown rule reads the shared relation ─────────────────────────

def test_cooldown_is_silent_once_the_window_has_passed():
    loss = trade(at(10, 0), at(10, 20), -3000)
    reentry = trade(at(10, 40), at(11, 0), -500)       # 20 min after, limit 15

    evs = engine._detect_constitution_violation(
        ctx(reentry, [loss], user_cooldown_min=15))
    assert "cooldown" not in rules_fired(evs)


def test_a_loss_still_OPEN_at_this_entry_cannot_trigger_the_cooldown():
    """
    The point of CONCLUDED. A position that had not closed when this trade was
    entered was not information the trader acted on.
    """
    still_open = trade(at(10, 0), at(11, 30), -3000)   # closes AFTER the entry
    reentry = trade(at(10, 25), at(11, 0), -500)

    evs = engine._detect_constitution_violation(
        ctx(reentry, [still_open], user_cooldown_min=15))
    assert "cooldown" not in rules_fired(evs)


def test_the_boundary_is_strict_not_inclusive():
    """
    `<` not `<=`: a close in the same instant as the next entry does not count.
    This is the one case where the old inline spelling and the shared relation
    disagreed - measured at 0 of 740 real trades, pinned here so the choice is
    deliberate rather than incidental.
    """
    exact = trade(at(10, 0), at(10, 25), -3000)
    reentry = trade(at(10, 25), at(10, 40), -500)      # entry == prior exit

    evs = engine._detect_constitution_violation(
        ctx(reentry, [exact], user_cooldown_min=15))
    assert "cooldown" not in rules_fired(evs)


# ── 2. abstaining from one rule must not abstain from the others ───────────

def test_the_abstain_path_does_not_return_early():
    src = inspect.getsource(BehaviorEngine._detect_constitution_violation)
    body = src[src.index("max_trade_risk abstains"):]
    head = body[:body.index("else:")]
    assert "return" not in head, (
        "abstaining from max_trade_risk must fall through, not return - a rule "
        "added after it would be silently skipped")


def test_other_rules_still_fire_when_the_risk_rule_abstains():
    """
    An MCX trade: the risk layer must abstain on that exchange, and the rule
    beside it must still be reported.

    THE INVARIANT IS UNCHANGED - an abstention on ONE rule must never abstain
    from the others. Only the companion rule moved: this used the cooldown
    breach until `cooldown_after_loss` stopped being a user rule on 2026-09-02,
    and now uses the daily loss limit, which is a rule the trader still sets.
    """
    loss = trade(at(10, 0), at(10, 20), -3000)
    reentry = trade(at(10, 25), at(10, 40), -500)
    reentry.exchange = "MCX"
    reentry.tradingsymbol = "GOLDM25APRFUT"
    reentry.instrument_type = "FUT"

    evs = engine._detect_constitution_violation(
        ctx(reentry, [loss],
            daily_loss_limit=3000.0, max_position_size=2.0,
            trading_capital=500_000))

    fired = rules_fired(evs)
    assert "daily_loss" in fired, (
        "an abstention on the risk rule must not suppress the other rules")
    assert "max_trade_risk" not in fired, "the risk rule itself must abstain"


def test_the_risk_rule_still_fires_when_capital_IS_determinable():
    """The abstain refactor must not have disabled the rule it guards."""
    priors = [trade(at(9, 30 + i), at(9, 40 + i), -100) for i in range(3)]
    big = trade(at(11, 0), at(11, 30), -500, qty=750)

    evs = engine._detect_constitution_violation(
        ctx(big, priors, max_position_size=2.0, trading_capital=50_000))
    assert "max_trade_risk" in rules_fired(evs)


# ── 3. the ladder is classified, and its values are unchanged ──────────────

def test_the_ladder_values_are_exactly_what_shipped():
    from app.core.threshold_registry import THRESHOLD_SPECS

    assert COLD_START_DEFAULTS["constitution_approaching_pct"] == 0.80
    assert COLD_START_DEFAULTS["constitution_severe_pct"] == 1.20
    assert THRESHOLD_SPECS["constitution_approaching_pct"].fallback == 0.80
    assert THRESHOLD_SPECS["constitution_severe_pct"].fallback == 1.20


def test_the_ladder_is_product_policy_and_cannot_be_personalised():
    """
    A trader must not be able to move the point at which breaking their OWN rule
    is reported - that softens the rule without editing it, which is what
    `constitution_service`'s tighten-instant / loosen-409 gate exists to prevent.
    """
    from app.core.threshold_registry import THRESHOLD_SPECS, Kind

    for key in ("constitution_approaching_pct", "constitution_severe_pct"):
        spec = THRESHOLD_SPECS[key]
        assert spec.kind is Kind.PRODUCT_POLICY, key
        assert spec.resolution_source is None, (
            f"{key} must not resolve from a learned source")


def test_the_ladder_still_produces_all_three_rungs():
    """Classification must not have changed what the ladder does."""
    seen = set()
    for count, expect in ((8, "caution"), (10, "danger"), (13, "critical")):
        priors = [trade(at(9, 20), at(9, 30), -50) for _ in range(count - 1)]
        ct = trade(at(11, 0), at(11, 10), -50)
        evs = engine._detect_constitution_violation(
            ctx(ct, priors, user_daily_trade_limit=10))
        ev = next((e for e in (evs or []) if e.context["rule"] == "daily_trades"), None)
        assert ev is not None, f"{count} trades against a limit of 10 must fire"
        assert ev.severity == expect, f"{count} trades -> {ev.severity}, want {expect}"
        seen.add(ev.severity)
    assert seen == {"caution", "danger", "critical"}
