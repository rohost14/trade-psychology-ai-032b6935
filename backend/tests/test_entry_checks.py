"""
E3 — the rules that are decidable the moment a position opens.

Trade limit, loss limit and the MIS square-off run-up are arithmetic against a
number the trader wrote down, or a clock reading. Waiting for the position to
close makes the answer later, never better — and for the square-off case it
destroys the answer entirely, since "you have 20 minutes before this is closed
for you" is not useful afterwards.

The severity ladder is shared with the exit-time detector rather than restated.
Two copies of "80% is caution, 100% is danger, 120% is critical" is the drift
that produced the pattern-name and severity bugs elsewhere in this codebase, and
120% is the severity that reaches an accountability partner.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from app.services.entry_checks import (
    constitution_ladder, count_entries_today, evaluate_loss_limit,
    evaluate_mis_panic, evaluate_trade_limit, squareoff_window,
)

IST = ZoneInfo("Asia/Kolkata")


# ── The shared ladder ────────────────────────────────────────────────────────

def test_ladder_matches_the_exit_time_thresholds():
    assert constitution_ladder(0.79) is None
    assert constitution_ladder(0.80) == "caution"
    assert constitution_ladder(0.99) == "caution"
    assert constitution_ladder(1.00) == "danger"
    assert constitution_ladder(1.19) == "danger"
    assert constitution_ladder(1.20) == "critical"


def test_ladder_respects_custom_thresholds():
    assert constitution_ladder(0.60, approaching=0.50, severe=2.0) == "caution"
    assert constitution_ladder(2.5, approaching=0.50, severe=2.0) == "critical"


# ── Trade limit ──────────────────────────────────────────────────────────────

def test_trade_limit_silent_below_the_approach_band():
    assert evaluate_trade_limit(3, 10) is None


def test_trade_limit_cautions_on_approach():
    hit = evaluate_trade_limit(8, 10)
    assert hit["severity"] == "caution"
    assert "approaching" in hit["message"]


def test_trade_limit_breach_is_danger():
    hit = evaluate_trade_limit(10, 10)
    assert hit["severity"] == "danger"
    assert "breached" in hit["message"]


def test_trade_limit_far_past_is_critical():
    """120% of your own limit is the tier that reaches a guardian."""
    assert evaluate_trade_limit(12, 10)["severity"] == "critical"


def test_trade_limit_says_the_position_is_open():
    """The copy has to earn its earliness — it is about a live position."""
    assert "OPEN" in evaluate_trade_limit(10, 10)["message"]


def test_no_trade_limit_set_means_no_alert():
    assert evaluate_trade_limit(50, None) is None
    assert evaluate_trade_limit(50, 0) is None


# ── Loss limit ───────────────────────────────────────────────────────────────

def test_loss_limit_ignores_a_green_session():
    assert evaluate_loss_limit(5000, 10000) is None


def test_loss_limit_cautions_on_approach():
    hit = evaluate_loss_limit(-8000, 10000)
    assert hit["severity"] == "caution"


def test_loss_limit_breach_is_danger():
    hit = evaluate_loss_limit(-10000, 10000)
    assert hit["severity"] == "danger"
    assert hit["ratio"] == 1.0


def test_loss_limit_far_past_is_critical():
    assert evaluate_loss_limit(-12500, 10000)["severity"] == "critical"


def test_loss_limit_names_the_new_position():
    """The point is not the loss — they know. It is opening another one."""
    assert "another position" in evaluate_loss_limit(-10000, 10000)["message"]


def test_no_loss_limit_set_means_no_alert():
    assert evaluate_loss_limit(-50000, None) is None


# ── MIS square-off run-up ────────────────────────────────────────────────────

def at(hour, minute, day=6):
    return datetime(2026, 8, day, hour, minute, tzinfo=IST)


def test_nfo_squareoff_window():
    panic_start, squareoff = squareoff_window("NFO", at(15, 10))
    assert panic_start.hour == 15 and panic_start.minute == 0
    assert squareoff == "15:25"


def test_equity_squareoff_is_earlier_than_fno():
    _, nse = squareoff_window("NSE", at(15, 10))
    _, nfo = squareoff_window("NFO", at(15, 10))
    assert nse == "15:15"
    assert nfo == "15:25"


def test_commodity_squareoff_is_not_three_in_the_afternoon():
    """
    A flat 15:00 cutoff once meant every evening MIS entry on MCX — which
    trades to 23:30 — was scored as end-of-session panic. Hours of false
    alerts a day, not a missed signal.
    """
    panic_start, squareoff = squareoff_window("MCX", at(20, 0))
    assert panic_start.hour >= 22
    assert squareoff > "20:00"


def test_mis_panic_needs_the_late_window():
    assert evaluate_mis_panic(at(14, 30), "NFO", "MIS", 5) is None


def test_mis_panic_needs_enough_late_entries():
    assert evaluate_mis_panic(at(15, 5), "NFO", "MIS", 1) is None


def test_mis_panic_cautions_at_two_late_entries():
    hit = evaluate_mis_panic(at(15, 5), "NFO", "MIS", 2)
    assert hit["severity"] == "caution"


def test_mis_panic_is_danger_at_three():
    hit = evaluate_mis_panic(at(15, 5), "NFO", "MIS", 3)
    assert hit["severity"] == "danger"


def test_mis_panic_counts_down_to_squareoff():
    """The content of this alert is the time remaining — that is why it is early."""
    hit = evaluate_mis_panic(at(15, 5), "NFO", "MIS", 3)
    assert hit["minutes_to_squareoff"] == 20
    # Wording, not behaviour: "from now" read as the wall clock when the alert
    # was reviewed later, though it was always measured from the entry. The
    # number is the assertion that matters and it is unchanged.
    assert "20 minutes after this entry" in hit["message"]


def test_mis_panic_ignores_delivery_products():
    assert evaluate_mis_panic(at(15, 5), "NFO", "NRML", 5) is None
    assert evaluate_mis_panic(at(15, 5), "NFO", "CNC", 5) is None
    assert evaluate_mis_panic(at(15, 5), "NFO", None, 5) is None


def test_mis_panic_does_not_go_negative_after_squareoff():
    hit = evaluate_mis_panic(at(15, 30), "NFO", "MIS", 3)
    assert hit["minutes_to_squareoff"] == 0


# ── Counting today's entries ─────────────────────────────────────────────────

def ledger(symbol, entry_type="OPEN", minutes=0, qty=50):
    return SimpleNamespace(
        tradingsymbol=symbol,
        entry_type=entry_type,
        occurred_at=datetime(2026, 8, 6, 10, 0, tzinfo=timezone.utc) + timedelta(minutes=minutes),
        fill_qty=qty,
    )


def test_only_opening_fills_count_as_entries():
    """Closing a position is not taking a trade."""
    rows = [
        ledger("NIFTY25AUG24500CE", "OPEN", 0),
        ledger("NIFTY25AUG24500CE", "CLOSE", 5),
        ledger("NIFTY25AUG24700CE", "DECREASE", 10),
    ]
    assert count_entries_today(rows) == 1


def test_entries_are_counted_as_structures_not_legs():
    """
    A four-leg condor is one decision against the trade limit. Counting legs
    would put a spread trader over their own limit after two positions.
    """
    rows = [
        ledger("NIFTY25AUG24700CE", "OPEN", 0, qty=-50),
        ledger("NIFTY25AUG24500CE", "OPEN", 0, qty=50),
        ledger("NIFTY25AUG24300PE", "OPEN", 0, qty=-50),
        ledger("NIFTY25AUG24100PE", "OPEN", 0, qty=50),
    ]
    assert count_entries_today(rows) == 1


def test_single_leg_entries_count_individually():
    rows = [ledger(f"NIFTY25AUG2{4000 + i * 100}CE", "OPEN", i * 10) for i in range(5)]
    assert count_entries_today(rows) == 5


def test_no_entries_today_counts_zero():
    assert count_entries_today([]) == 0
