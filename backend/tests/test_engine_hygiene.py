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
from datetime import date, datetime, timedelta, timezone
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
# 2. opening_5min_trap — RETIRED 2026-08-30 (Pattern 21)
#
# `TestOpeningTrapSeverity` (3 tests) is deleted with it. They pinned that the
# detector returns a hardcoded `info` on both trigger branches and stays silent
# on a profitable opening trade — and that last one turned out to be the reason
# it was retired: the outcome gate discarded 42% of window entries for having
# made money, while the window measured 39.4% win against 39.5% for the rest of
# the day. See tests/test_opening_5min_trap_retired.py.

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

def _loss_run(n, *, symbol="NIFTY25AUGFUT", qtys=None, start=-240, pnl=-500.0,
              anchor=None):
    out = []
    for i in range(n):
        t = make_ct(symbol=symbol, pnl=pnl, entry_offset_min=start + i * 20,
                    duration_min=10, anchor=anchor)
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

    #: A fixed instant inside one IST trading day: 14:30 on Thursday 15 Jan
    #: 2026, expressed in UTC.
    #:
    #: These tests count "positions opened today", which is decided by
    #: comparing each trade's IST date against the session's. Measuring the
    #: offsets from `now` made that a property of the wall clock: `_loss_run`
    #: places its earliest prior four hours back, so between 00:00 and 04:00
    #: IST those trades belonged to YESTERDAY, the detector correctly excluded
    #: them, and the assertions failed for four hours a night.
    #:
    #: The anchor is chosen so every synthetic trade lands inside one session
    #: and inside market hours: the earliest prior is 10:30 IST and the trade
    #: under test is 14:25, well within 09:15-15:30. Nothing here reads the
    #: real clock or real market activity.
    ANCHOR = datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc)      # 14:30 IST
    SESSION_DATE = date(2026, 1, 15)

    def _run(self, n_prior, declared=7, thresholds=None):
        priors = _loss_run(n_prior, anchor=self.ANCHOR)
        ct = make_ct(pnl=-100.0, entry_offset_min=-5, anchor=self.ANCHOR)
        th = {"user_daily_trade_limit": declared,
              "burst_trades_per_30min_caution": 5, "burst_trades_per_30min_danger": 8}
        th.update(thresholds or {})
        return engine._detect_overtrading_burst(
            make_ctx(completed_trade=ct, session_trades=priors, thresholds=th,
                     session=make_session(session_date=self.SESSION_DATE)))

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


# `TestWinningStreakOverconfidence` (4 tests) deleted 2026-08-30 with the
# detector they exercised. They asserted the caution/danger ladder and the
# five-wins-small-size fall-through; all three behaviours no longer exist.
# The retirement itself is pinned by tests/test_winning_streak_retired.py.


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
    `win_rate_collapse` has never fired in 203 sessions. These pin the GUARDS —
    why it stays silent — rather than the tiers, so the pattern review can tell
    "correctly silent" from "unreachable". The review reached its answer: the
    guards are sound and the silence is an artefact of a CSV book carrying no
    profile.

    `strategy_breakdown` was covered here too until it was retired 2026-09-02.
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

    # Two `strategy_breakdown` guard tests were DELETED 2026-09-02 with their
    # subject: `_detect_strategy_breakdown` no longer exists. They asserted it
    # needed both baselines and took the weaker confidence — both true of the
    # detector while it lived, and neither meaningful now. The retirement and
    # its reasoning are pinned by `test_strategy_breakdown_retired.py`.


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
