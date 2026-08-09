"""
Rule suggestion service (G3).

The builders are pure functions over completed trades, so they are tested
directly with lightweight stand-ins — no DB, no fixtures. What matters here is
the refusal behaviour as much as the detection: a suggestion that fires on thin
data, or that proposes loosening a rule, is a worse defect than one that never
fires at all.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from app.services.rule_suggestion_service import (
    MIN_SESSIONS,
    _group_by_session,
    suggest_cooldown_after_loss,
    suggest_daily_loss_limit,
    suggest_daily_trade_limit,
    suggest_max_consecutive_losses,
    uses_multi_leg,
)

IST = ZoneInfo("Asia/Kolkata")
BASE = datetime(2026, 5, 4, 10, 0, tzinfo=IST)


def trade(day: int, minute: int = 0, pnl: float = 100.0, symbol: str = "NIFTY25AUG24500CE",
          duration: int = 5):
    """One completed trade on `day` (offset from BASE), entered at `minute`."""
    entry = BASE + timedelta(days=day, minutes=minute)
    return SimpleNamespace(
        tradingsymbol=symbol,
        entry_time=entry,
        exit_time=entry + timedelta(minutes=duration),
        realized_pnl=pnl,
    )


def sessions_from(trades):
    return _group_by_session(trades)


# ── daily_trade_limit ────────────────────────────────────────────────────────

def _paced_ledger():
    """Six calm green sessions (3 trades), six busy red ones (9 trades)."""
    trades = []
    for d in range(6):
        for i in range(3):
            trades.append(trade(d, minute=i * 30, pnl=400))
    for d in range(6, 12):
        for i in range(9):
            trades.append(trade(d, minute=i * 10, pnl=-200))
    return trades


def test_trade_limit_found_where_outcomes_split():
    s = sessions_from(_paced_ledger())
    out = suggest_daily_trade_limit(s, current=None)
    assert out is not None
    assert out.field == "daily_trade_limit"
    assert 3 <= out.suggested_value < 9
    assert len(out.evidence) == 2


def test_trade_limit_not_suggested_when_rule_already_tighter():
    s = sessions_from(_paced_ledger())
    assert suggest_daily_trade_limit(s, current=2) is None


def test_trade_limit_needs_minimum_sessions():
    trades = [trade(d, pnl=400) for d in range(MIN_SESSIONS - 1)]
    assert suggest_daily_trade_limit(sessions_from(trades), current=None) is None


def test_trade_limit_silent_when_pace_does_not_separate():
    """Busy days and calm days both finish green — pace is not their problem."""
    trades = []
    for d in range(12):
        for i in range(3 if d % 2 else 9):
            trades.append(trade(d, minute=i * 10, pnl=300))
    assert suggest_daily_trade_limit(sessions_from(trades), current=None) is None


# ── daily_loss_limit ─────────────────────────────────────────────────────────

def test_loss_limit_sits_inside_the_red_distribution():
    trades = []
    for d in range(6):
        trades.append(trade(d, pnl=1500))
    for d, loss in enumerate([-2000, -2500, -3000, -3500, -9000, -12000], start=6):
        trades.append(trade(d, pnl=loss))
    out = suggest_daily_loss_limit(sessions_from(trades), current=None)
    assert out is not None
    assert 2000 <= out.suggested_value <= 9000
    assert out.field == "daily_loss_limit"


def test_loss_limit_never_loosens_an_existing_rule():
    trades = [trade(d, pnl=1500) for d in range(6)]
    trades += [trade(d, pnl=-3000) for d in range(6, 12)]
    out = suggest_daily_loss_limit(sessions_from(trades), current=1000)
    assert out is None


# ── max_consecutive_losses ───────────────────────────────────────────────────

def test_consecutive_losses_detects_the_collapse_point():
    """Baseline wins; the trade after two straight losses never does."""
    trades = []
    for d in range(12):
        trades.append(trade(d, minute=0, pnl=500))
        trades.append(trade(d, minute=20, pnl=-300))
        trades.append(trade(d, minute=40, pnl=-300))
        trades.append(trade(d, minute=60, pnl=-800))   # the follow-up trade
        trades.append(trade(d, minute=80, pnl=600))
    out = suggest_max_consecutive_losses(sessions_from(trades), current=None)
    assert out is not None
    assert out.suggested_value == 2
    assert "won 0 of" in out.evidence[0]["value"]


def test_consecutive_losses_respects_a_tighter_existing_rule():
    trades = []
    for d in range(12):
        trades.append(trade(d, minute=0, pnl=500))
        trades.append(trade(d, minute=20, pnl=-300))
        trades.append(trade(d, minute=40, pnl=-300))
        trades.append(trade(d, minute=60, pnl=-800))
        trades.append(trade(d, minute=80, pnl=600))
    assert suggest_max_consecutive_losses(sessions_from(trades), current=2) is None


# ── cooldown_after_loss ──────────────────────────────────────────────────────

def test_cooldown_detects_impaired_reentry_window():
    """Re-entries inside 5 minutes lose; patient ones win."""
    trades = []
    for d in range(12):
        trades.append(trade(d, minute=0, pnl=-500, duration=1))
        trades.append(trade(d, minute=3, pnl=-400, duration=1))    # 2 min gap
        trades.append(trade(d, minute=10, pnl=-500, duration=1))
        trades.append(trade(d, minute=60, pnl=700, duration=1))    # 49 min gap
    out = suggest_cooldown_after_loss(sessions_from(trades), current=None)
    assert out is not None
    assert out.suggested_value in (5, 10, 15, 20, 30)
    assert out.field == "cooldown_after_loss"


def test_cooldown_not_suggested_below_existing_rule():
    trades = []
    for d in range(12):
        trades.append(trade(d, minute=0, pnl=-500, duration=1))
        trades.append(trade(d, minute=3, pnl=-400, duration=1))
        trades.append(trade(d, minute=10, pnl=-500, duration=1))
        trades.append(trade(d, minute=60, pnl=700, duration=1))
    assert suggest_cooldown_after_loss(sessions_from(trades), current=60) is None


# ── multi-leg guard ──────────────────────────────────────────────────────────

def test_multi_leg_detected_for_simultaneous_same_underlying_entries():
    legs = [
        trade(0, minute=0, symbol="NIFTY25AUG24500CE"),
        trade(0, minute=0, symbol="NIFTY25AUG24700CE"),
    ]
    assert uses_multi_leg(legs) is True


def test_single_leg_trading_is_not_flagged():
    spaced = [
        trade(0, minute=0, symbol="NIFTY25AUG24500CE"),
        trade(0, minute=30, symbol="NIFTY25AUG24700CE"),
    ]
    assert uses_multi_leg(spaced) is False


def test_different_underlyings_at_the_same_moment_are_not_a_spread():
    pair = [
        trade(0, minute=0, symbol="NIFTY25AUG24500CE"),
        trade(0, minute=0, symbol="BANKNIFTY25AUG52000CE"),
    ]
    assert uses_multi_leg(pair) is False
