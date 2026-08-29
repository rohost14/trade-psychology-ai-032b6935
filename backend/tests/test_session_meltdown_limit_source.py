"""
Pattern 17 — the limit `session_meltdown` judges against must be the trader's.

CHANGED 2026-08-30: the `trading_capital * 0.05` fallback is gone from BOTH the
detector and `api/risk.py`. With no declared `daily_loss_limit` the detector
abstains.

WHY, in one paragraph. The 5% had no documented provenance - it predates the
visible history and no commit justifies it - and it contradicted the product's
own answer twice over: `constitution_service`'s experience matrix suggests
2% / 2% / 2.5% / 3%, and the onboarding wizard computes 2%. It also contradicted
a decided policy: `constitution_service` owns `daily_loss_limit` as a RULE_FIELD
and deliberately returns None for it, because F&O lot sizes make a
percent-of-capital money rule unusable - a real replay produced 212 rule
violations across 61 sessions, 54% of all alerts, none describing behaviour.
Money rules are suggested, never applied.

NO REPLACEMENT PERCENTAGE WAS SUBSTITUTED, and these tests forbid one.

The 40% / 75% ladder is untouched and is pinned below, because it was NOT part
of this change and a future edit should have to be deliberate about it.
"""
import inspect
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.trading_defaults import COLD_START_DEFAULTS
from app.services.behavior_engine import BehaviorEngine, EngineContext

engine = BehaviorEngine()
APP = Path(__file__).resolve().parents[1] / "app"
NOW = datetime(2026, 4, 15, 11, 0, tzinfo=timezone.utc)


def _ct(pnl=-1000.0):
    return SimpleNamespace(
        id=uuid4(), broker_account_id=uuid4(), tradingsymbol="NIFTY25APR24000CE",
        exchange="NFO", product="MIS", instrument_type="CE", direction="LONG",
        total_quantity=75, avg_entry_price=Decimal("100"),
        avg_exit_price=Decimal("90"), realized_pnl=Decimal(str(pnl)),
        duration_minutes=30, entry_time=NOW - timedelta(minutes=30),
        exit_time=NOW, num_entries=1, num_exits=1, status="closed")


def _ctx(session_pnl, *, limit=None, capital=None):
    ct = _ct()
    th = dict(COLD_START_DEFAULTS)
    th["daily_loss_limit"] = limit
    th["trading_capital"] = capital
    return EngineContext(
        broker_account_id=ct.broker_account_id,
        session=SimpleNamespace(session_pnl=Decimal(str(session_pnl)),
                                session_date=NOW.date(), market_open=None),
        completed_trade=ct, session_trades=[ct], thresholds=th)


# ── 1. declared limit — unchanged behaviour ────────────────────────────────

def test_a_declared_limit_still_fires_caution_at_40_percent():
    ev = engine._detect_session_meltdown(_ctx(-2100, limit=5000))
    assert ev is not None
    assert ev.severity == "caution"
    assert ev.context["daily_loss_limit"] == 5000
    assert ev.context["limit_source"] == "declared"
    assert "your ₹5,000 daily limit" in ev.message


def test_a_declared_limit_still_fires_danger_at_75_percent():
    ev = engine._detect_session_meltdown(_ctx(-3800, limit=5000))
    assert ev is not None
    assert ev.severity == "danger"


def test_a_declared_limit_below_the_caution_ladder_stays_silent():
    assert engine._detect_session_meltdown(_ctx(-1900, limit=5000)) is None


def test_a_profitable_session_never_fires():
    assert engine._detect_session_meltdown(_ctx(4000, limit=5000)) is None


# ── 2. no declared limit — must abstain ────────────────────────────────────

def test_no_limit_and_no_capital_abstains():
    assert engine._detect_session_meltdown(_ctx(-9999, limit=None, capital=None)) is None


@pytest.mark.parametrize("capital", [50_000, 100_000, 500_000, 5_000_000])
def test_capital_present_but_no_declared_limit_ABSTAINS(capital):
    """
    The case this change is about. Previously `capital * 0.05` invented a limit
    and the detector fired; a Rs 50,000 account was judged against Rs 2,500 and
    alerted on 52% of all sessions in the reference book.

    A loss large enough to breach any plausible derived limit must now produce
    nothing at all.
    """
    assert engine._detect_session_meltdown(
        _ctx(-500_000, limit=None, capital=capital)) is None


@pytest.mark.parametrize("limit", [0, 0.0, -1, None])
def test_a_zero_or_negative_limit_is_treated_as_undeclared(limit):
    assert engine._detect_session_meltdown(
        _ctx(-50_000, limit=limit, capital=1_000_000)) is None


# ── 3. no replacement percentage may creep back ────────────────────────────

def test_the_detector_derives_no_limit_from_capital():
    """
    Guards against substituting 2%, 2.5%, 3% or anything else. Suggested limits
    stay suggestions - `constitution_service` returns None for this rule on
    purpose, and enforcing its suggestion here would re-make the mistake its own
    comment documents.
    """
    src = inspect.getsource(BehaviorEngine._detect_session_meltdown)
    code = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
    assert "trading_capital" not in code, (
        "the detector must not read capital at all - the limit is the trader's "
        "or there is no judgement")
    for frac in ("0.05", "0.02", "0.025", "0.03"):
        assert frac not in code, f"a capital fraction ({frac}) is back"


def test_the_api_derives_no_limit_from_capital():
    """
    The paired site. `api/risk.py` mirrored the fallback so the dashboard hero
    and the alert copy would agree on ONE limit; removing it from the detector
    alone would have re-broken that agreement.
    """
    src = (APP / "api" / "risk.py").read_text(encoding="utf-8")
    body = src[src.index("daily_loss_limit = None"):]
    body = body[:body.index("daily_trade_limit = int(tl)")]
    code = "\n".join(l for l in body.splitlines() if not l.lstrip().startswith("#"))
    assert "0.05" not in code
    assert 'th.get("trading_capital")' not in code, (
        "the hero must report no limit rather than invent one")


def test_the_two_sites_agree_that_an_undeclared_limit_is_None():
    """
    The invariant the paired change exists to hold: neither surface may produce
    a number the other does not have.
    """
    detector_src = inspect.getsource(BehaviorEngine._detect_session_meltdown)
    api_src = (APP / "api" / "risk.py").read_text(encoding="utf-8")

    assert "if not daily_loss_limit or daily_loss_limit <= 0:\n            return None" \
        in detector_src
    assert "float(loss_limit) if loss_limit and loss_limit > 0 else None" in api_src


# ── 4. the ladder was NOT part of this change ──────────────────────────────

def test_the_forty_seventyfive_ladder_is_untouched():
    assert COLD_START_DEFAULTS["meltdown_caution_pct"] == 0.40
    assert COLD_START_DEFAULTS["meltdown_danger_pct"] == 0.75


def test_the_ladder_is_still_read_from_thresholds_not_hardcoded():
    src = inspect.getsource(BehaviorEngine._detect_session_meltdown)
    assert 'ctx.thresholds.get("meltdown_caution_pct"' in src
    assert 'ctx.thresholds.get("meltdown_danger_pct"' in src


def test_the_strategy_leg_guard_survives():
    """A losing leg inside a net-profitable structure is still not a meltdown."""
    ctx = _ctx(-4000, limit=5000)
    ctx.strategy_group = SimpleNamespace(net_pnl=Decimal("1200"))
    assert engine._detect_session_meltdown(ctx) is None
