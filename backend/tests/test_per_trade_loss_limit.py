"""
`per_trade_loss_limit` — the third money rule.

The most the trader is willing to lose on ONE position, in rupees. Opt-in, no
suggested value, enforced by `constitution_violation` at exit. Added 1 Sep 2026
(Pattern 24).

SEMANTICS, all settled before the code was written
(docs/patterns/24-constitution_violation/per_trade_loss_limit_semantics.md):

  realised, at exit    `constitution_violation` is trigger="exit", so the only
                       loss that exists when it runs is realised. It cannot
                       warn mid-trade; the live path is separate work.
  losses only          a winning trade is not a small breach, it is not a breach
  POSITION level       a CompletedTrade is written only when quantity returns to
                       zero, so realized_pnl already sums every exit tranche.
                       Splitting an exit cannot evade the limit — 8 of 740
                       rounds on the reference book closed in more than one
                       tranche, all as single rows.
  no instrument branch rupees are rupees; futures and options are identical
  RAW P&L              no brokerage, no STT, no tax, per the standing charter
  ladder unchanged     0.80 caution / 1.00 danger / 1.20 critical

MULTI-LEG IS A DOCUMENTED LIMITATION, NOT A DESIGN. Netting a structure's legs
was approved in principle and then measured as unusable: `strategy_detector`
groups on "same underlying, entered within 15 minutes", which cannot separate a
vertical spread from two independent bets (29 of 48 candidate pairs are the same
option type), and 45% of grouped rounds have no closed sibling at their own exit
— so the same structure would be judged leg-level at one exit and net-level at
the next. `session_meltdown` reads `strategy_group` to SUPPRESS, which fails
safe; using it to MEASURE would make a false statement in either direction.

So this rule measures EACH LEG SEPARATELY and does not read `strategy_group`.
§7 pins that, including that it behaves identically whether a group is present
or not.
"""
import inspect
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.trading_defaults import COLD_START_DEFAULTS, get_thresholds
from app.services.behavior_engine import BehaviorEngine, EngineContext
from app.services.constitution_service import (
    RULE_FIELDS, classify_change, constitution_service,
)

engine = BehaviorEngine()
NOW = datetime(2026, 4, 15, 11, 0, tzinfo=timezone.utc)
ACCT = uuid4()

LIMIT = 4000.0


def trade(pnl, *, symbol="NIFTY25APR24000CE", itype="CE", qty=75,
          num_exits=1, entry=None, exit_=None):
    entry = entry or NOW - timedelta(minutes=30)
    exit_ = exit_ or NOW
    return SimpleNamespace(
        id=uuid4(), broker_account_id=ACCT, tradingsymbol=symbol,
        exchange="NFO", product="MIS", instrument_type=itype, direction="LONG",
        total_quantity=qty, avg_entry_price=Decimal("100"),
        avg_exit_price=Decimal("90"), realized_pnl=Decimal(str(pnl)), pnl_pct=None,
        duration_minutes=30, entry_time=entry, exit_time=exit_,
        num_entries=1, num_exits=num_exits, status="closed", quality_score=None)


def ctx(ct, priors=(), *, strategy_group=None, **rules):
    th = dict(COLD_START_DEFAULTS)
    th["per_trade_loss_limit"] = LIMIT
    th.update(rules)
    return EngineContext(
        broker_account_id=ACCT,
        session=SimpleNamespace(
            session_pnl=Decimal(str(sum(float(t.realized_pnl) for t in priors) + float(ct.realized_pnl))),
            session_date=NOW.date(), market_open=None),
        completed_trade=ct, session_trades=list(priors), thresholds=th,
        strategy_group=strategy_group)


def fired(evs, rule="per_trade_loss"):
    return [e for e in (evs or []) if e.context["rule"] == rule]


def sev(ct, priors=(), **rules):
    evs = fired(engine._detect_constitution_violation(ctx(ct, priors, **rules)))
    return evs[0].severity if evs else None


# ── 1. the ladder, at and around the limit ─────────────────────────────────

def test_loss_below_the_limit_is_silent():
    assert sev(trade(-2000)) is None          # 0.50


def test_loss_just_below_the_warning_rung_is_silent():
    assert sev(trade(-3199)) is None          # 0.7998


def test_loss_at_the_warning_rung_is_caution():
    assert sev(trade(-3200)) == "caution"     # 0.80 exactly


def test_loss_exactly_at_the_limit_is_danger():
    """1.00 is the breach, not the approach."""
    assert sev(trade(-4000)) == "danger"


def test_loss_above_the_limit_is_danger_until_the_severe_rung():
    assert sev(trade(-4500)) == "danger"      # 1.125


def test_loss_at_the_severe_rung_is_critical():
    assert sev(trade(-4800)) == "critical"    # 1.20 exactly


def test_a_much_larger_loss_is_still_critical():
    assert sev(trade(-40000)) == "critical"


# ── 2. only losses ─────────────────────────────────────────────────────────

def test_a_winning_trade_never_breaches_a_loss_limit():
    assert sev(trade(+40000)) is None


def test_a_scratch_trade_is_not_a_breach():
    assert sev(trade(0)) is None


# ── 3. no rule configured -> abstain ───────────────────────────────────────

def test_no_rule_configured_abstains():
    ct = trade(-40000)
    evs = engine._detect_constitution_violation(ctx(ct, per_trade_loss_limit=None))
    assert fired(evs) == []


def test_a_zero_limit_is_treated_as_unset():
    """Falsy: a limit of zero is not a rule, it is the absence of one."""
    ct = trade(-40000)
    evs = engine._detect_constitution_violation(ctx(ct, per_trade_loss_limit=0))
    assert fired(evs) == []


# ── 4. partial exits cannot evade it ───────────────────────────────────────

def test_a_position_closed_in_tranches_is_measured_once_on_the_total():
    """
    THE EVASION TEST. Three exits of Rs 1,600 against a Rs 4,000 limit is a
    Rs 4,800 loss on that position, not three sub-limit losses.

    This holds because a CompletedTrade is written only when quantity returns to
    zero — `realized_pnl` is already the sum. The rule does not have to
    aggregate; it must simply not look at fills, and it does not.
    """
    ct = trade(-4800, num_exits=3)

    assert sev(ct) == "critical"
    ev = fired(engine._detect_constitution_violation(ctx(ct)))[0]
    assert ev.context["current"] == 4800.0, "the summed loss, not a tranche"


def test_the_rule_never_reads_fill_level_data():
    src = inspect.getsource(BehaviorEngine._detect_constitution_violation)
    body = src[src.index("per_trade_limit = th.get"):]
    body = body[:body.index("# ── Rule: max trades per day")]
    assert "position_fills" not in body
    assert "num_exits" not in body


# ── 5. instruments — no branch ─────────────────────────────────────────────

@pytest.mark.parametrize("symbol,itype", [
    ("NIFTY25APR24000CE", "CE"),
    ("NIFTY25APR24000PE", "PE"),
    ("NIFTY25APRFUT", "FUT"),
    ("RELIANCE25APRFUT", "FUT"),
])
def test_every_instrument_is_measured_identically(symbol, itype):
    """Rupees are rupees. Unlike max_position_size this never abstains."""
    assert sev(trade(-4500, symbol=symbol, itype=itype)) == "danger"


def test_it_does_not_abstain_where_the_capital_rules_do():
    """
    MCX: the risk layer must abstain on that exchange, so `max_trade_risk` goes
    quiet. A rupee loss limit needs no risk layer and must still report.
    """
    ct = trade(-4500, symbol="GOLDM25APRFUT", itype="FUT")
    ct.exchange = "MCX"

    evs = engine._detect_constitution_violation(
        ctx(ct, max_position_size=2.0, trading_capital=500_000))

    assert [e.severity for e in fired(evs)] == ["danger"]
    assert fired(evs, "max_trade_risk") == [], "the capital rule abstains on MCX"


# ── 6. several rules on one trade ──────────────────────────────────────────

def test_two_money_rules_breached_by_one_trade_produce_two_events():
    """
    The brief's worked example. Per-rule dedup keeps them separate; no grouping
    architecture is involved.
    """
    ct = trade(-4500)
    evs = engine._detect_constitution_violation(
        ctx(ct, daily_loss_limit=4000))     # session_pnl is this trade alone

    rules = sorted(e.context["rule"] for e in (evs or []))
    assert "per_trade_loss" in rules
    assert "daily_loss" in rules


def test_the_daily_rule_is_untouched_by_this_addition():
    """A day of small losses breaches the daily rule and NOT the per-trade one."""
    priors = [trade(-1500) for _ in range(6)]
    ct = trade(-1000)
    evs = engine._detect_constitution_violation(
        ctx(ct, priors, daily_loss_limit=10000))

    assert fired(evs) == [], "no single trade came near Rs 4,000"
    assert fired(evs, "daily_loss"), "the daily rule still fires on the total"


# ── 7. multi-leg — measured per leg, group deliberately ignored ────────────

def test_the_rule_does_not_read_strategy_group():
    """
    Grouping was measured unreliable, so it is not consulted. Pinned because a
    later reader might "fix" this by wiring the group in, reintroducing a
    judgement that depends on which leg happened to close first.
    """
    src = inspect.getsource(BehaviorEngine._detect_constitution_violation)
    body = src[src.index("per_trade_limit = th.get"):]
    body = body[:body.index("# ── Rule: max trades per day")]
    code = "\n".join(l for l in body.splitlines() if not l.lstrip().startswith("#"))
    assert "strategy_group" not in code


def test_a_leg_breaches_even_inside_a_net_profitable_structure():
    """
    The documented limitation, asserted so it is visible rather than surprising.
    A hedge whose short leg loses Rs 6,000 reports a breach even though the
    structure made money.
    """
    short_leg = trade(-6000, symbol="NIFTY25APR24000CE")
    group = SimpleNamespace(net_pnl=Decimal("500"), strategy_type="iron_condor")

    assert sev(short_leg) == "critical"
    evs = engine._detect_constitution_violation(ctx(short_leg, strategy_group=group))
    assert [e.severity for e in fired(evs)] == ["critical"], (
        "behaviour must be identical with a group present — it is not read")


def test_behaviour_is_identical_with_and_without_a_group():
    ct = trade(-4500)
    without = engine._detect_constitution_violation(ctx(ct))
    with_g = engine._detect_constitution_violation(
        ctx(ct, strategy_group=SimpleNamespace(net_pnl=Decimal("-100"),
                                               strategy_type="straddle_buy")))

    assert [e.severity for e in fired(without)] == [e.severity for e in fired(with_g)]


# ── 8. it is a real rule, opt-in, never suggested ──────────────────────────

def test_it_is_a_rule_field_and_tightening_lowers_it():
    assert "per_trade_loss_limit" in RULE_FIELDS
    assert classify_change("per_trade_loss_limit", None, 4000) == "tighten"
    assert classify_change("per_trade_loss_limit", 4000, 2000) == "tighten"
    assert classify_change("per_trade_loss_limit", 4000, 8000) == "loosen"
    assert classify_change("per_trade_loss_limit", None, None) is None


@pytest.mark.parametrize("level", ["beginner", "intermediate", "experienced", "professional"])
def test_it_is_never_set_and_never_suggested(level):
    d = constitution_service.generate_defaults(level, 500_000)

    assert d["per_trade_loss_limit"] is None
    assert "suggested_per_trade_loss_limit" not in d, (
        "there is no evidence for a recommended per-trade loss figure for F&O")


def test_it_resolves_from_the_profile_and_survives_an_unapplied_migration():
    """
    Migration 082 may not be applied. An absent column must read as "rule not
    set", not raise.
    """
    class WithColumn:
        per_trade_loss_limit = 4000
        def __getattr__(self, _): return None

    class WithoutColumn:
        def __getattr__(self, _): return None

    assert get_thresholds(WithColumn())["per_trade_loss_limit"] == 4000
    assert get_thresholds(WithoutColumn())["per_trade_loss_limit"] is None
    assert get_thresholds(None)["per_trade_loss_limit"] is None


# ── 9. the ladder itself is untouched ──────────────────────────────────────

def test_the_ladder_values_are_unchanged():
    assert COLD_START_DEFAULTS["constitution_approaching_pct"] == 0.80
    assert COLD_START_DEFAULTS["constitution_severe_pct"] == 1.20
