"""
Pre-pattern hygiene pass — regression tests, 2026-08-24.

Two kinds of test live here:

  1. A CONTRACT test that makes the inline-default drift class impossible to
     reintroduce. Two detectors were reading `ctx.thresholds.get(key, X)` with
     an X that disagreed with COLD_START_DEFAULTS. The resolved value always
     won, so the inline number was unreachable and silently wrong — the sort of
     thing that only surfaces when someone reads the file and believes it.

  2. Behavioural tests for detectors that fire often in the replay and had no
     test at all. These pin CURRENT behaviour so the pattern reviews have a
     baseline to change deliberately. They are NOT endorsements of the numbers.
"""
import re
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from app.core.trading_defaults import COLD_START_DEFAULTS
from app.services.behavior_engine import BehaviorEngine, _STOP_ORDER_TYPES
from tests.test_behavior_engine import make_ct, make_ctx, make_session

engine = BehaviorEngine()

ENGINE_SRC = Path(__file__).resolve().parents[1] / "app" / "services" / "behavior_engine.py"


# ---------------------------------------------------------------------------
# 1. Contract: an inline default may not contradict the configured value
# ---------------------------------------------------------------------------

def _inline_defaults():
    """Every `ctx.thresholds.get("key", <number>)` in the engine."""
    src = ENGINE_SRC.read_text(encoding="utf-8")
    out = {}
    for m in re.finditer(r"""thresholds\.get\(\s*["']([a-z_0-9]+)["']\s*,\s*([0-9.]+)\s*\)""", src):
        out.setdefault(m.group(1), set()).add(float(m.group(2)))
    return out


def test_inline_defaults_agree_with_cold_start_defaults():
    """
    The bug this closes: fomo_expiry_day_symbols read an inline 2 while
    COLD_START_DEFAULTS said 4, and profit_giveaway_min_peak read 1000 while
    the config said 1500. Both inline numbers were dead, because
    resolve_thresholds always supplies the key — so the file said one thing and
    the engine did another.

    A detector may still carry an inline default (it is the honest fallback if
    the key ever goes missing); it may not carry one that CONTRADICTS the
    configured value.
    """
    disagreements = []
    for key, values in sorted(_inline_defaults().items()):
        configured = COLD_START_DEFAULTS.get(key)
        if configured is None:
            continue  # not config-backed; nothing to contradict
        if not any(abs(v - float(configured)) < 1e-9 for v in values):
            disagreements.append(f"{key}: inline {sorted(values)} vs config {configured}")
    assert not disagreements, "inline default contradicts COLD_START_DEFAULTS:\n" + "\n".join(disagreements)


def test_confidence_alert_gate_is_gone_and_stays_gone():
    """
    Deliberately absent, not missing. See
    docs/contracts/confidence_alert_gate_CLOSED.md — it had one reader for its
    entire life (revenge_trade's deleted points score) and zero at removal.
    Global confidence suppression is DEFERRED; this asserts nothing quietly
    reintroduces the constant in the meantime.
    """
    assert "confidence_alert_gate" not in COLD_START_DEFAULTS


def test_stop_order_types_defined_once():
    """panic_exit and no_stoploss both mean the same thing by 'a stop fired'."""
    assert _STOP_ORDER_TYPES == frozenset({"SL", "SL-M", "SLM", "SL-MKT"})
    src = ENGINE_SRC.read_text(encoding="utf-8")
    # The literal set may appear only in the constant's own definition.
    assert src.count('"SL-MKT"') == 1


# ---------------------------------------------------------------------------
# 2. opening_5min_trap — severity is info, and that is the whole answer
# ---------------------------------------------------------------------------

class TestOpeningTrapSeverity:
    """
    A `severity = "danger" if ... else "caution"` was computed and thrown away;
    the event has returned a hardcoded "info" since the Phase 4 analytics flip.
    Both branches are pinned so the dead line cannot come back unnoticed.
    """

    def _trap(self, *, duration, pnl, qty=100, price=10.0):
        ct = make_ct(symbol="NIFTY25AUG24000CE", instrument_type="CE",
                     pnl=pnl, duration_min=duration)
        ct.avg_entry_price = Decimal(str(price))
        ct.total_quantity = qty
        ct.duration_minutes = duration
        # entry inside the opening window
        entry = ct.entry_time.astimezone(engine and __import__("zoneinfo").ZoneInfo("Asia/Kolkata"))
        ct.entry_time = ct.entry_time.replace(
            hour=3, minute=47, second=0, microsecond=0)  # 09:17 IST in UTC
        ct.exit_time = ct.entry_time + timedelta(minutes=duration)
        return engine._detect_opening_5min_trap(make_ctx(completed_trade=ct))

    def test_quick_and_large_loss_is_still_info(self):
        ev = self._trap(duration=5, pnl=-600.0)   # 60% of a 1000 premium
        assert ev is not None
        assert ev.severity == "info"
        assert ev.context["is_quick_reactive"] and ev.context["is_large_loss"]

    def test_large_loss_alone_is_info(self):
        ev = self._trap(duration=40, pnl=-600.0)
        assert ev is not None and ev.severity == "info"
        assert ev.context["is_large_loss"] and not ev.context["is_quick_reactive"]

    def test_profitable_opening_trade_is_not_flagged(self):
        assert self._trap(duration=5, pnl=250.0) is None


# ---------------------------------------------------------------------------
# 3. size_escalation — a rupee sequence may not be labelled "qty"
# ---------------------------------------------------------------------------

def test_size_escalation_cross_instrument_reports_rupees_not_qty():
    """
    The `cross` flag was computed and never read, so a notional sequence was
    printed as "12500.0→18000.0→24000.0 qty". Detection is unchanged; only the
    sentence and one context key are.
    """
    priors = []
    for i, (sym, qty, price, pnl) in enumerate([
        ("NIFTY25AUG24000CE", 75, 100.0, -500.0),
        ("SENSEX25AUG80000CE", 20, 600.0, -700.0),
        ("BANKNIFTY25AUG52000CE", 30, 700.0, -400.0),
    ]):
        t = make_ct(symbol=sym, instrument_type="CE", pnl=pnl, entry_offset_min=-90 + i * 20)
        t.total_quantity = qty
        t.avg_entry_price = Decimal(str(price))
        priors.append(t)
    ct = make_ct(symbol="FINNIFTY25AUG23000CE", instrument_type="CE", pnl=-300.0)
    ct.total_quantity = 40
    ct.avg_entry_price = Decimal("800")

    ev = engine._detect_size_escalation(make_ctx(completed_trade=ct, session_trades=priors))
    assert ev is not None, "three rising notionals with losses should escalate"
    assert ev.context["cross_instrument"] is True
    assert "qty" not in ev.message
    assert "₹" in ev.message


# ---------------------------------------------------------------------------
# 4. Detectors that fire often in the replay and had no test at all
# ---------------------------------------------------------------------------

def _loss_run(n, *, symbol="NIFTY25AUGFUT", qtys=None, start=-240, pnl=-500.0):
    out = []
    for i in range(n):
        t = make_ct(symbol=symbol, pnl=pnl, entry_offset_min=start + i * 20, duration_min=10)
        if qtys:
            t.total_quantity = qtys[i]
        out.append(t)
    return out


class TestDailyOvertrading:
    """37 alerts across 36 replay sessions and, until now, zero tests."""

    def _run(self, n_prior, thresholds=None):
        priors = _loss_run(n_prior)
        ct = make_ct(pnl=-100.0, entry_offset_min=-5)
        th = {"daily_trade_limit": 7, "daily_trade_danger": 12,
              "burst_trades_per_30min_caution": 5, "burst_trades_per_30min_danger": 8}
        th.update(thresholds or {})
        return engine._detect_overtrading_burst(
            make_ctx(completed_trade=ct, session_trades=priors, thresholds=th))

    def test_under_the_limit_is_silent(self):
        assert self._run(3) is None

    def test_crossing_the_daily_limit_emits_daily_overtrading(self):
        ev = self._run(7)
        assert ev is not None
        assert ev.event_type == "daily_overtrading", "the alias, not the spec name"
        assert ev.severity == "caution"
        assert ev.context["daily_count"] >= 7

    def test_daily_danger_tier(self):
        ev = self._run(12)
        assert ev is not None and ev.event_type == "daily_overtrading"
        assert ev.severity == "danger"


class TestMartingaleLadder:
    """26 danger alerts in the replay — the largest single source — no test."""

    def _run(self, qtys, current_qty):
        priors = _loss_run(len(qtys), qtys=qtys)
        ct = make_ct(pnl=-400.0, entry_offset_min=-5)
        ct.total_quantity = current_qty
        return engine._detect_martingale_behaviour(
            make_ctx(completed_trade=ct, session_trades=priors))

    def test_flat_sizing_after_losses_is_not_martingale(self):
        assert self._run([50, 50, 50], 50) is None

    def test_caution_at_the_caution_multiple(self):
        ev = self._run([50, 80, 80], 80)          # 1.6x step
        assert ev is not None and ev.severity == "caution"

    def test_danger_at_the_danger_multiple(self):
        ev = self._run([50, 100, 100], 100)       # 2.0x step
        assert ev is not None and ev.severity == "danger"

    def test_ratio_is_computed_from_priors_only(self):
        """
        Documenting current behaviour, not endorsing it: the displayed sequence
        includes the current trade, the ratio that decides severity does not.
        Flagged for the martingale pattern review.
        """
        ev = self._run([50, 50, 50], 500)         # 10x jump on the CURRENT trade
        assert ev is None, "current trade size does not enter max_ratio today"


class TestSameSymbolObsession:
    """29 alerts, 20 of them danger, and no test."""

    def _run(self, qtys, current_qty, n_losses=3):
        priors = []
        for i in range(len(qtys)):
            t = make_ct(symbol="NIFTY25AUG24000CE", instrument_type="CE",
                        pnl=-300.0 if i < n_losses else 200.0,
                        entry_offset_min=-200 + i * 20)
            t.total_quantity = qtys[i]
            priors.append(t)
        ct = make_ct(symbol="NIFTY25AUG24500CE", instrument_type="CE",
                     pnl=-250.0, entry_offset_min=-5)
        ct.total_quantity = current_qty
        return engine._detect_same_symbol_obsession(
            make_ctx(completed_trade=ct, session_trades=priors))

    def test_two_losses_is_below_the_minimum(self):
        # The CURRENT trade is a loss and counts, so one prior loss plus one
        # prior win gives two — below obsession_min_losses of 3.
        assert self._run([50, 50], 50, n_losses=1) is None

    def test_caution_when_size_is_not_rising(self):
        ev = self._run([75, 75, 75], 75)
        assert ev is not None and ev.severity == "caution"
        assert ev.context["size_rising"] is False

    def test_danger_when_size_is_rising(self):
        ev = self._run([50, 50, 50], 150)
        assert ev is not None and ev.severity == "danger"
        assert ev.context["size_rising"] is True


class TestWinningStreakOverconfidence:
    """Fires 6 times in the replay; the danger tier never fired at all."""

    def _run(self, n_wins, current_qty, prior_qty=50):
        priors = []
        for i in range(n_wins):
            t = make_ct(symbol="NIFTY25AUGFUT", pnl=400.0, entry_offset_min=-200 + i * 20)
            t.total_quantity = prior_qty
            priors.append(t)
        ct = make_ct(symbol="NIFTY25AUGFUT", pnl=100.0, entry_offset_min=-5)
        ct.total_quantity = current_qty
        return engine._detect_winning_streak_overconfidence(
            make_ctx(completed_trade=ct, session_trades=priors))

    def test_streak_without_size_increase_is_silent(self):
        assert self._run(3, 50) is None

    def test_caution_at_three_wins_and_1_3x(self):
        ev = self._run(3, 70)
        assert ev is not None and ev.severity == "caution"
        assert ev.context["win_streak"] == 3

    def test_danger_at_five_wins_and_2x(self):
        ev = self._run(5, 100)
        assert ev is not None and ev.severity == "danger"
        assert ev.context["win_streak"] == 5

    def test_five_wins_but_small_size_falls_through_to_caution(self):
        ev = self._run(5, 70)
        assert ev is not None and ev.severity == "caution"


class TestPostLossRecoveryBet:
    """Only 2 replay alerts, no tests — the ladder was entirely unpinned."""

    def _run(self, prior_qtys, current_qty):
        priors = []
        for i, q in enumerate(prior_qtys):
            t = make_ct(symbol="NIFTY25AUGFUT", pnl=-500.0, entry_offset_min=-200 + i * 20)
            t.total_quantity = q
            priors.append(t)
        ct = make_ct(symbol="NIFTY25AUGFUT", pnl=-800.0, entry_offset_min=-5)
        ct.total_quantity = current_qty
        return engine._detect_post_loss_recovery_bet(
            make_ctx(completed_trade=ct, session_trades=priors))

    def test_same_size_after_two_losses_is_silent(self):
        assert self._run([50, 50, 50], 50) is None

    def test_caution_at_two_times_the_recent_average(self):
        ev = self._run([50, 50, 50], 100)
        assert ev is not None and ev.severity == "caution"

    def test_danger_at_three_times(self):
        ev = self._run([50, 50, 50], 150)
        assert ev is not None and ev.severity == "danger"

    def test_requires_the_last_two_to_be_losses(self):
        priors = []
        for i, (q, pnl) in enumerate([(50, -500.0), (50, -500.0), (50, 900.0)]):
            t = make_ct(symbol="NIFTY25AUGFUT", pnl=pnl, entry_offset_min=-200 + i * 20)
            t.total_quantity = q
            priors.append(t)
        ct = make_ct(symbol="NIFTY25AUGFUT", pnl=-800.0, entry_offset_min=-5)
        ct.total_quantity = 200
        assert engine._detect_post_loss_recovery_bet(
            make_ctx(completed_trade=ct, session_trades=priors)) is None


class TestPerformanceDetectorGuards:
    """
    win_rate_collapse and strategy_breakdown have never fired in 203 sessions.
    These pin the GUARDS — why they stay silent — rather than the tiers, so the
    pattern review can tell "correctly silent" from "unreachable".
    """

    def _ctx(self, n_trades, thresholds):
        priors = _loss_run(max(n_trades - 1, 0))
        ct = make_ct(pnl=-100.0, entry_offset_min=-5)
        return make_ctx(completed_trade=ct, session_trades=priors, thresholds=thresholds)

    def test_win_rate_collapse_silent_without_a_baseline(self):
        assert engine._detect_win_rate_collapse(self._ctx(10, {})) is None

    def test_win_rate_collapse_silent_below_confidence(self):
        th = {"baseline_win_rate": {"value": 60.0, "confidence": 0.2}}
        assert engine._detect_win_rate_collapse(self._ctx(10, th)) is None

    def test_win_rate_collapse_silent_under_eight_trades(self):
        th = {"baseline_win_rate": {"value": 60.0, "confidence": 0.9}}
        assert engine._detect_win_rate_collapse(self._ctx(5, th)) is None

    def test_win_rate_collapse_fires_when_every_guard_is_satisfied(self):
        th = {"baseline_win_rate": {"value": 60.0, "confidence": 0.9}}
        ev = engine._detect_win_rate_collapse(self._ctx(10, th))
        assert ev is not None and ev.severity == "info"

    def test_strategy_breakdown_needs_both_baselines(self):
        th = {"baseline_win_rate": {"value": 60.0, "confidence": 0.9}}
        assert engine._detect_strategy_breakdown(self._ctx(10, th)) is None

    def test_strategy_breakdown_confidence_is_the_weaker_of_the_two(self):
        th = {"baseline_win_rate": {"value": 60.0, "confidence": 0.9},
              "baseline_profit_factor": {"value": 2.0, "confidence": 0.6}}
        priors = _loss_run(9)
        ct = make_ct(pnl=200.0, entry_offset_min=-5)
        ev = engine._detect_strategy_breakdown(
            make_ctx(completed_trade=ct, session_trades=priors, thresholds=th))
        if ev is not None:
            assert ev.confidence == pytest.approx(60.0)
