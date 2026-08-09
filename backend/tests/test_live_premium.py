"""
E4 — telling an option buyer their premium is going, while it is still going.

The exit-time detector reports the same fact after the position closed and the
loss was taken. Every input is available live. The tests that matter here are
the refusals: a missing price must produce silence, never a fabricated loss
percentage on a real position.
"""
import pytest

from app.services.live_checks import (
    evaluate_live_premium_loss, live_premium_message, premium_loss_pct,
)

THRESHOLDS = {
    "premium_loss_caution_pct": 40,
    "premium_loss_danger_pct": 60,
    "premium_loss_critical_pct": 80,
    "premium_loss_expiry_shift_pct": 15,
}


def check(entry, ltp, qty=50, expiry=False, thresholds=None):
    return evaluate_live_premium_loss(entry, ltp, qty, thresholds or THRESHOLDS, expiry)


# ── A missing price is silence, not zero ─────────────────────────────────────

def test_no_price_says_nothing():
    """
    get_cached_ltp returns None for anything older than two seconds. Treating
    that as a price would invent a loss on a real position.
    """
    assert check(100.0, None) is None


def test_no_entry_price_says_nothing():
    assert check(None, 20.0) is None
    assert check(0, 20.0) is None


def test_unparseable_prices_say_nothing():
    assert check("n/a", 20.0) is None
    assert check(100.0, "n/a") is None


def test_a_position_in_profit_says_nothing():
    assert check(100.0, 130.0) is None


def test_a_flat_position_says_nothing():
    assert check(100.0, 100.0) is None


# ── The bands, matching the exit-time detector ───────────────────────────────

def test_below_the_caution_band_says_nothing():
    assert check(100.0, 65.0) is None      # 35% gone


def test_caution_band():
    assert check(100.0, 55.0)["severity"] == "caution"      # 45% gone


def test_danger_band():
    assert check(100.0, 35.0)["severity"] == "danger"       # 65% gone


def test_critical_band_is_the_guardian_tier():
    """80% of premium gone is the severity that reaches an accountability partner."""
    assert check(100.0, 15.0)["severity"] == "critical"     # 85% gone


def test_exact_band_edges_round_up_not_down():
    assert check(100.0, 60.0)["severity"] == "caution"      # exactly 40%
    assert check(100.0, 40.0)["severity"] == "danger"       # exactly 60%
    assert check(100.0, 20.0)["severity"] == "critical"     # exactly 80%


# ── Expiry day ───────────────────────────────────────────────────────────────

def test_expiry_day_raises_the_bar():
    """
    Options decay hard on expiry day, so the same percentage means less. A 45%
    loss is caution on a normal day and nothing at all on expiry.
    """
    assert check(100.0, 55.0)["severity"] == "caution"
    assert check(100.0, 55.0, expiry=True) is None


def test_expiry_day_still_fires_when_it_is_genuinely_bad():
    result = check(100.0, 5.0, expiry=True)     # 95% gone
    assert result["severity"] == "critical"
    assert result["expiry_day"] is True


# ── Direction ────────────────────────────────────────────────────────────────

def test_short_options_are_not_premium_destruction():
    """
    Premium destruction is a buyer's problem — the exit-time detector is LONG
    options only and this mirrors it. A short option that moves against you is
    a different pattern.
    """
    assert check(100.0, 20.0, qty=-50) is None


def test_a_closed_position_is_not_evaluated():
    assert check(100.0, 20.0, qty=0) is None


# ── The numbers reported ─────────────────────────────────────────────────────

def test_loss_percentage_is_of_premium_paid():
    assert premium_loss_pct(100.0, 25.0) == 75.0


def test_unrealised_loss_uses_the_position_size():
    result = check(100.0, 25.0, qty=50)
    assert result["loss_pct"] == 75.0
    assert result["unrealised_loss"] == 3750      # (100 - 25) * 50


def test_levels_are_reported_so_the_evidence_can_show_them():
    result = check(100.0, 25.0)
    assert result["levels"] == {"caution": 40.0, "danger": 60.0, "critical": 80.0}


# ── Copy ─────────────────────────────────────────────────────────────────────

def test_message_is_an_observation_not_advice():
    """
    It describes arithmetic already true about a position the trader holds. It
    would become advice the moment it suggested an action, so it does not.
    """
    text = live_premium_message("NIFTY25AUG24500CE", check(100.0, 25.0))
    assert "75%" in text
    assert "OPEN" in text
    for instruction in ("exit", "close", "should", "consider", "cut", "stop"):
        assert instruction not in text.lower()


def test_message_flags_the_expiry_day_adjustment():
    text = live_premium_message("NIFTY25AUG24500CE", check(100.0, 2.0, expiry=True))
    assert "expiry day" in text
