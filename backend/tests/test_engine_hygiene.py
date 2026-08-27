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
# 3. size_escalation — RETIRED 2026-08-27 (Pattern #10)
# ---------------------------------------------------------------------------
#
# `test_size_escalation_cross_instrument_reports_rupees_not_qty` was deleted
# with its subject. It pinned a real fix - a notional sequence must not be
# labelled "qty" - but the detector it exercised no longer exists, so the test
# could only fail on an AttributeError. The retirement itself is covered by
# tests/test_size_escalation_retired.py.

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
    """
    REWRITTEN 2026-08-26 with the detector, in its Pattern #5 review.

    These tests pinned the OLD contract: a line at `daily_trade_limit` (7) with
    a danger tier at `daily_trade_danger` (12). Both are gone from the alerting
    path — the first because a p75-derived line alerts on a quarter of any
    trader's sessions by construction, the second because the file that defines
    it records "no source" while it decides a push notification.

    `test_daily_danger_tier` is deleted rather than adjusted: its subject, the
    12-tier, no longer exists. The rest move to the declared limit.

    Full evidence in docs/patterns/05-overtrading/overtrading_review.md.
    """

    def _run(self, n_prior, declared=7, thresholds=None):
        priors = _loss_run(n_prior)
        ct = make_ct(pnl=-100.0, entry_offset_min=-5)
        th = {"user_daily_trade_limit": declared,
              "burst_trades_per_30min_caution": 5, "burst_trades_per_30min_danger": 8}
        th.update(thresholds or {})
        return engine._detect_overtrading_burst(
            make_ctx(completed_trade=ct, session_trades=priors, thresholds=th))

    def test_under_the_limit_is_silent(self):
        assert self._run(3) is None

    def test_crossing_the_declared_limit_emits_daily_overtrading(self):
        ev = self._run(7)
        assert ev is not None
        assert ev.event_type == "daily_overtrading", "the alias, not the spec name"
        assert ev.severity == "caution"
        assert ev.context["daily_count"] >= 7
        assert ev.context["declared_limit"] == 7

    def test_there_is_no_second_tier_above_the_declared_limit(self):
        """
        `daily_trade_danger` = 12 was NOT reimplemented. Twelve positions
        against a declared limit of 7 is exactly as loud as seven.
        """
        ev = self._run(12)
        assert ev is not None and ev.event_type == "daily_overtrading"
        assert ev.severity == "caution"


class TestMartingaleLadder:
    """
    REWRITTEN 2026-08-24 with the detector, in its Pattern #1 review.

    These tests used to pin the OLD semantics, and one of them
    (`test_ratio_is_computed_from_priors_only`) existed specifically to record a
    defect its own docstring described as "documenting current behaviour, not
    endorsing it... Flagged for the martingale pattern review." This is that
    review, so the tests move with the contract rather than the contract being
    bent to keep them green.

    What martingale means now: a CLOSED loss, then a subsequent attempt at
    materially more CAPITAL AT RISK. The step measured is the one the trader
    took - previous closed position to this one - and the losses must be
    trailing consecutive.
    """

    def _run(self, prior_qtys, current_qty, prior_pnl=-400.0):
        priors = _loss_run(len(prior_qtys), qtys=prior_qtys, pnl=prior_pnl)
        ct = make_ct(pnl=-400.0, entry_offset_min=-5)
        ct.total_quantity = current_qty
        return engine._detect_martingale_behaviour(
            make_ctx(completed_trade=ct, session_trades=priors))

    def test_flat_sizing_after_losses_is_not_martingale(self):
        r = self._run([50, 50, 50], 50)
        assert not r.fired

    def test_a_smaller_next_attempt_is_not_martingale(self):
        """The old implementation could fire here: the current trade took no
        part in its arithmetic, so a de-escalation was scored by a step between
        two earlier trades."""
        r = self._run([50, 100, 200], 50)
        assert not r.fired

    def test_caution_at_the_caution_multiple(self):
        r = self._run([50, 50, 50], 80)          # 1.6x the previous attempt
        assert r.fired and r.severity == "caution"
        assert r.context["risk_ratio"] == pytest.approx(1.6)

    def test_danger_at_the_danger_multiple(self):
        r = self._run([50, 50, 50], 100)         # 2.0x
        assert r.fired and r.severity == "danger"

    def test_the_step_measured_is_the_one_the_trader_took(self):
        """
        The correction. Priors 50 -> 50 -> 50 contain no escalation at all; the
        escalation is the current attempt at 500. The old implementation
        returned nothing here, because it only ever compared priors.
        """
        r = self._run([50, 50, 50], 500)
        assert r.fired and r.severity == "danger"
        assert r.context["risk_ratio"] == pytest.approx(10.0)

    def test_losses_must_be_trailing_consecutive(self):
        """
        Two losses and a WIN immediately before this attempt. The message has
        always said "consecutive losses"; now the code agrees with it.
        """
        priors = _loss_run(2, qtys=[50, 50])
        winner = make_ct(pnl=900.0, entry_offset_min=-30)
        winner.total_quantity = 50
        ct = make_ct(pnl=-400.0, entry_offset_min=-5)
        ct.total_quantity = 500
        r = engine._detect_martingale_behaviour(
            make_ctx(completed_trade=ct, session_trades=priors + [winner]))
        assert not r.fired

    def test_escalating_after_WINS_is_not_martingale(self):
        r = self._run([50, 50, 50], 500, prior_pnl=400.0)
        assert not r.fired

    def test_the_ratio_is_capital_at_risk_and_says_so(self):
        """
        It used to compare lots within one underlying and rupees across them,
        against one multiplier, without recording which. Now it is one unit and
        the context names it.
        """
        r = self._run([50, 50, 50], 100)
        assert r.context["denominator_kind"]
        assert r.context["risk_before"] > 0 and r.context["risk_after"] > 0


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


class TestMartingaleAcrossInstrumentClasses:
    """
    Synthetic coverage for the instruments the real book barely contains.

    The tradebook is 727 LONG positions against 15 SHORT, with 16 equity rows
    and 2 futures. Every escalation measured in it is a long option, so short
    options, futures and equity have no real case to validate against and are
    proven here instead. This is stated as a limitation in the contract, not
    papered over.

    What these pin is that risk is measured by instrument_risk rather than by
    quantity — which is the correction this detector's review made. Premium
    received is not exposure for a short; margin is.
    """

    def _run(self, itype, symbol, direction, prior_qty, current_qty, price):
        priors = []
        for i in range(2):
            t = make_ct(symbol=symbol, instrument_type=itype,
                        direction=direction, pnl=-500.0,
                        entry_offset_min=-60 + i * 20)
            t.total_quantity = prior_qty
            t.avg_entry_price = Decimal(str(price))
            priors.append(t)
        ct = make_ct(symbol=symbol, instrument_type=itype, direction=direction,
                     pnl=-400.0, entry_offset_min=-5)
        ct.total_quantity = current_qty
        ct.avg_entry_price = Decimal(str(price))
        return engine._detect_martingale_behaviour(
            make_ctx(completed_trade=ct, session_trades=priors))

    @pytest.mark.parametrize("itype,symbol,direction", [
        ("EQ", "RELIANCE", "LONG"),
        ("EQ", "RELIANCE", "SHORT"),
        ("FUT", "NIFTY25AUGFUT", "LONG"),
        ("FUT", "NIFTY25AUGFUT", "SHORT"),
        ("CE", "NIFTY25AUG24000CE", "LONG"),
        ("PE", "NIFTY25AUG24000PE", "LONG"),
        ("CE", "NIFTY25AUG24000CE", "SHORT"),
        ("PE", "NIFTY25AUG24000PE", "SHORT"),
    ])
    def test_doubling_risk_after_two_losses_fires_on_every_class(
            self, itype, symbol, direction):
        r = self._run(itype, symbol, direction, 100, 200, 50.0)
        assert r.fired, f"{direction} {itype} escalation not detected"
        assert r.severity == "danger"
        assert r.context["risk_ratio"] == pytest.approx(2.0)
        assert r.context["denominator_kind"], "the unit must be named"

    @pytest.mark.parametrize("itype,symbol,direction", [
        ("EQ", "RELIANCE", "SHORT"),
        ("FUT", "NIFTY25AUGFUT", "SHORT"),
        ("CE", "NIFTY25AUG24000CE", "SHORT"),
    ])
    def test_a_short_uses_margin_not_the_premium_received(
            self, itype, symbol, direction):
        """
        Premium received is the maximum GAIN on a short, never its exposure.
        The ratio must still be right, and the denominator must say what it is.
        """
        r = self._run(itype, symbol, direction, 100, 200, 50.0)
        assert r.fired
        assert r.context["denominator_kind"] in ("margin_posted", "notional")
        assert r.context["risk_after"] > r.context["risk_before"]

    def test_a_spread_leg_abstains_rather_than_guessing(self):
        priors = []
        for i in range(2):
            t = make_ct(symbol="NIFTY25AUG24000CE", instrument_type="CE",
                        pnl=-500.0, entry_offset_min=-60 + i * 20)
            t.total_quantity = 100
            priors.append(t)
        ct = make_ct(symbol="NIFTY25AUG24000CE", instrument_type="CE",
                     pnl=-400.0, entry_offset_min=-5)
        ct.total_quantity = 300
        ctx = make_ctx(completed_trade=ct, session_trades=priors)
        ctx.strategy_group = type("SG", (), {"strategy_type": "iron_condor",
                                             "net_pnl": None})()
        r = engine._detect_martingale_behaviour(ctx)
        assert r.abstained and not r.fired
