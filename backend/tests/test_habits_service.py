"""Unit tests for the Habits service — zero-input behavioural insights.

Pure function over completed-trade-like objects (no DB), so these run anywhere. Guards the
logic behind the Analytics → Habits tab and the post-import recap: min-sample gating, IST
hour/day bucketing, instrument grouping, after-loss size drift, and best/worst summary.
"""
from datetime import datetime, timezone
from types import SimpleNamespace

from app.services.habits_service import build_habits, _underlying, _hour_label, MIN_SAMPLE


def _ct(pnl, *, symbol="NIFTY24JAN18000CE", qty=50, entry_price=100.0, hour_utc=8, minute=30, day=1):
    """A minimal CompletedTrade stand-in. UTC 08:30 == 14:00 IST (hour 14)."""
    dt = datetime(2026, 1, day, hour_utc, minute, tzinfo=timezone.utc)
    return SimpleNamespace(
        realized_pnl=pnl,
        entry_time=dt,
        exit_time=dt,
        tradingsymbol=symbol,
        total_quantity=qty,
        avg_entry_price=entry_price,
    )


# ── helpers ──────────────────────────────────────────────────────────────────
def test_underlying_extraction():
    assert _underlying("NIFTY24JAN18000CE") == "NIFTY"
    assert _underlying("BANKNIFTY24JANFUT") == "BANKNIFTY"
    assert _underlying("RELIANCE") == "RELIANCE"
    assert _underlying("M&M24JAN") == "M&M"
    assert _underlying("") == "?"


def test_hour_label():
    assert _hour_label(0) == "12am"
    assert _hour_label(9) == "9am"
    assert _hour_label(12) == "12pm"
    assert _hour_label(14) == "2pm"


# ── min-sample gating ─────────────────────────────────────────────────────────
def test_below_min_sample_returns_no_data():
    trades = [_ct(100) for _ in range(MIN_SAMPLE - 1)]
    out = build_habits(trades, days=365)
    assert out["has_data"] is False
    assert out["sample"] == MIN_SAMPLE - 1


# ── aggregation ────────────────────────────────────────────────────────────────
def test_ist_hour_bucketing():
    # UTC 08:30 -> IST 14:00 -> hour 14 ("2pm")
    trades = [_ct(10, hour_utc=8, minute=30) for _ in range(5)]
    out = build_habits(trades, days=365)
    assert out["has_data"] is True
    hours = {r["key"]: r for r in out["by_hour"]}
    assert 14 in hours
    assert hours[14]["trades"] == 5
    assert hours[14]["label"] == "2pm"


def test_win_rate_and_net_pnl_by_instrument():
    trades = [
        _ct(100, symbol="NIFTY24JAN18000CE"),
        _ct(-40, symbol="NIFTY24JAN18000CE"),
        _ct(100, symbol="BANKNIFTY24JANFUT"),
        _ct(100, symbol="BANKNIFTY24JANFUT"),
        _ct(-200, symbol="BANKNIFTY24JANFUT"),
    ]
    out = build_habits(trades, days=365)
    inst = {r["label"]: r for r in out["by_instrument"]}
    assert inst["NIFTY"]["net_pnl"] == 60.0
    assert inst["NIFTY"]["win_rate"] == 50.0
    assert inst["BANKNIFTY"]["trades"] == 3
    assert inst["BANKNIFTY"]["net_pnl"] == 0.0            # 100+100-200
    assert round(inst["BANKNIFTY"]["win_rate"], 1) == 66.7


# ── after-loss size drift ──────────────────────────────────────────────────────
def test_after_loss_size_drift_ratio():
    # sequence by exit_time: loss, (after-loss)big, win, loss, (after-loss)big
    trades = [
        _ct(-100, qty=10, entry_price=100.0, day=1),   # notional 1000, loss
        _ct(50,   qty=30, entry_price=100.0, day=2),   # notional 3000, AFTER loss
        _ct(50,   qty=10, entry_price=100.0, day=3),   # notional 1000, after a win
        _ct(-100, qty=10, entry_price=100.0, day=4),   # notional 1000, loss
        _ct(50,   qty=30, entry_price=100.0, day=5),   # notional 3000, AFTER loss
    ]
    out = build_habits(trades, days=365)
    als = out["after_loss_size"]
    assert als["after_loss_count"] == 2
    # overall avg notional = (1000+3000+1000+1000+3000)/5 = 1800; after-loss avg = 3000
    assert round(als["ratio"], 2) == round(3000 / 1800, 2)   # ~1.67


def test_after_loss_ratio_none_when_no_after_loss_trades():
    # all wins → no trade is preceded by a loss
    trades = [_ct(10, day=i + 1) for i in range(5)]
    out = build_habits(trades, days=365)
    assert out["after_loss_size"]["ratio"] is None
    assert out["after_loss_size"]["after_loss_count"] == 0


# ── summary ────────────────────────────────────────────────────────────────────
def test_summary_gross_and_extremes():
    trades = [
        _ct(500, symbol="NIFTY24JAN18000CE"),
        _ct(500, symbol="NIFTY24JAN18000CE"),
        _ct(500, symbol="NIFTY24JAN18000CE"),
        _ct(-300, symbol="BANKNIFTY24JANFUT"),
        _ct(-300, symbol="BANKNIFTY24JANFUT"),
        _ct(-300, symbol="BANKNIFTY24JANFUT"),
    ]
    out = build_habits(trades, days=365)
    s = out["summary"]
    assert s["total_trades"] == 6
    assert s["gross_pnl"] == 600.0                       # 1500 - 900
    assert s["best_instrument"] == "NIFTY"               # +1500, needs >= MIN_BUCKET(3)
    assert s["worst_instrument"] == "BANKNIFTY"          # -900
