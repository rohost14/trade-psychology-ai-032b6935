"""
`profit_giveaway` — the session built something and part of it is gone.

The detector had NO behavioural tests before its Pattern #6 review
(2026-08-27); every assertion here is new. What the review changed, and what
each group below pins:

  * **The green-to-red branch is no longer gated on `min_peak`.** That gate asks
    how HIGH the session got; the harm is how far BELOW zero it went. On the
    reference book it silenced 23 sessions that turned green into red, worth
    -Rs 66,212, against -Rs 29,751 admitted. `min_erosion` — which rises to the
    trader's own median losing trade — remains that branch's floor.

  * **One severity on the percentage branch.** The old 50/70 split ranked
    firings but did not separate behaviour (1.1 SE against a ~1.4 floor) and sat
    at no break in the distribution. `profit_giveaway_danger_pct` is deleted.

  * **`worst_giveaway` replaces `erosion_pct` as the dedup re-arm metric.**
    `erosion_pct` is unbounded once the session is red and moves both ways;
    `facts.max_drawdown` is a running maximum.

  * **Severity cannot fall within a session.** `went_red` is sticky.

  * **It reports the moment, not the outcome.** Half the alert-days on the
    reference book closed profitable.

Deliberately NOT asserted: any replacement threshold. The review proposed none.
"""

from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.models.completed_trade import CompletedTrade
from app.services.behavior_engine import BehaviorEngine, EngineContext
from app.tasks.trade_tasks import _WORSEN_METRIC, _pattern_dedup_key, _worsened
from tests.helpers import now_utc

engine = BehaviorEngine()


def _ct(pnl, offset_min):
    ct = MagicMock(spec=CompletedTrade)
    ct.id = uuid4()
    ct.broker_account_id = uuid4()
    ct.tradingsymbol = "NIFTY25AUGFUT"
    ct.exchange = "NFO"
    ct.direction = "LONG"
    ct.instrument_type = "FUT"
    ct.realized_pnl = Decimal(str(pnl))
    ct.total_quantity = 50
    ct.avg_entry_price = Decimal("22000")
    ct.avg_exit_price = Decimal("22010")
    now = now_utc()
    ct.entry_time = now + timedelta(minutes=offset_min)
    ct.exit_time = now + timedelta(minutes=offset_min + 5)
    return ct


def _facts(pnls):
    """The three SessionFacts fields this detector reads, same arithmetic."""
    running = peak = max_dd = Decimal("0")
    for p in pnls:
        running += Decimal(str(p))
        peak = max(peak, running)
        max_dd = max(max_dd, peak - running)
    return SimpleNamespace(pnl=running, peak_pnl=peak, max_drawdown=max_dd)


def _run(pnls, thresholds=None, session_date=None):
    """Run the detector on the LAST trade of a session with these P&Ls."""
    trades = [_ct(p, -60 + i * 5) for i, p in enumerate(pnls)]
    th = {"profit_giveaway_min_peak": 1500,
          "profit_giveaway_min_erosion": 500,
          "profit_giveaway_caution_pct": 0.50}
    th.update(thresholds or {})
    ctx = EngineContext(
        broker_account_id=trades[-1].broker_account_id,
        session=SimpleNamespace(session_pnl=_facts(pnls).pnl,
                                session_date=session_date, market_open=None),
        completed_trade=trades[-1],
        session_trades=trades[:-1],
        active_cooldowns=[],
        thresholds=th,
        facts=_facts(pnls),
    )
    return engine._detect_profit_giveaway(ctx)


def _sequence(pnls, thresholds=None):
    """Every firing across a session, in order — for the monotonicity checks."""
    out = []
    for i in range(2, len(pnls) + 1):
        ev = _run(pnls[:i], thresholds)
        if ev:
            out.append(ev)
    return out


# ── the gate removal ───────────────────────────────────────────────────────

def test_a_small_peak_that_turns_red_now_fires():
    """
    The regression the whole change exists for. Reference book: a day that
    touched +Rs 334 and closed at -Rs 6,548 was silent, because the PEAK was
    small. The peak is not where the harm is.
    """
    ev = _run([400, -6900])
    assert ev is not None, "a small peak turning deeply red is the case that matters"
    assert ev.severity == "danger"
    assert ev.context["sign_flip"] is True
    assert "turned from profit to loss" in ev.message


def test_min_peak_still_gates_the_percentage_branch():
    """
    Removing the gate was scoped to green-to-red. Giving back half of a peak
    that never amounted to anything is still not worth a sentence.
    """
    # peak 900 (< min_peak 1500), gives back 600 (>= min_erosion), never red
    assert _run([900, -600]) is None


def test_min_erosion_still_gates_the_green_to_red_branch():
    """The only floor that branch has left. A trivial dip is still trivial."""
    assert _run([200, -350]) is None       # peak 200, now -150 -> erosion 350
    assert _run([100, -150]) is None       # peak 100, now  -50 -> erosion 150


def test_the_self_relative_floor_still_applies():
    """
    `min_erosion` rises to the trader's own median losing trade once three
    losses are on record. Rs 500 is a bad hour for one trader and a rounding
    error for another.
    """
    # three prior losses of 3000 -> median loss 3000, so a 1200 giveback is
    # below this trader's own idea of a loss worth naming.
    ev = _run([-3000, -3000, -3000, 12000, -1200])
    assert ev is None


def test_peak_of_zero_says_nothing():
    """Nothing was built, so nothing was given back."""
    assert _run([-1000, -2000]) is None


# ── one severity on the percentage branch ──────────────────────────────────

@pytest.mark.parametrize("giveback", [0.50, 0.60, 0.70, 0.85, 0.99])
def test_the_percentage_branch_has_exactly_one_severity(giveback):
    """
    The 70% danger tier is gone. Giving back 99% of a peak is exactly as loud as
    giving back 50% — the split ranked firings but did not separate behaviour.
    """
    peak = 10_000
    ev = _run([peak, -peak * giveback])
    assert ev is not None
    assert ev.severity == "caution", f"{giveback:.0%} should not escalate on its own"
    assert ev.context["sign_flip"] is False


def test_the_deleted_danger_tier_is_not_resolvable():
    """It had exactly one reader — this detector — and now has none."""
    from app.core.trading_defaults import COLD_START_DEFAULTS

    assert "profit_giveaway_danger_pct" not in COLD_START_DEFAULTS
    assert "profit_giveaway_caution_pct" in COLD_START_DEFAULTS


# ── the re-arm metric ──────────────────────────────────────────────────────

def test_worst_giveaway_is_reported_and_is_the_rearm_metric():
    from app.tasks.trade_tasks import _WORSEN_METRIC

    assert _WORSEN_METRIC["profit_giveaway"] == "worst_giveaway"
    ev = _run([5000, -4000])
    assert "worst_giveaway" in ev.context


def test_the_rearm_metric_never_decreases_across_a_session():
    """
    The property `erosion_pct` did not have. A session that sinks, recovers and
    sinks again must never hand dedup a smaller number than last time.
    """
    pnls = [6000, -3000, -2000, 4000, -5000, 2000, -3000]
    seq = _sequence(pnls)
    assert len(seq) >= 3
    values = [e.context["worst_giveaway"] for e in seq]
    assert values == sorted(values), f"re-arm metric moved backwards: {values}"


def test_erosion_pct_no_longer_decides_severity():
    """
    Reported for context, but it is unbounded once the session is red — observed
    to 4.87 on the reference book — and nothing keys off it any more.
    """
    ev = _run([2000, -8000])
    assert ev.context["erosion_pct"] > 1.0
    assert ev.severity == "danger"          # from the sign flip, not the ratio
    assert ev.context["sign_flip"] is True


# ── severity cannot fall ───────────────────────────────────────────────────

def test_severity_does_not_fall_when_the_session_recovers():
    """
    The oscillation the review found on 2 of 20 alert-days: the same peak
    produced danger, then caution, then danger again as the session bounced.
    """
    # peak 6000, crashes to -1000 (danger), recovers to +2000 — still danger.
    ev = _run([6000, -7000, 3000])
    assert ev is not None
    assert ev.severity == "danger", "severity fell after the session recovered"
    assert ev.context["current_pnl"] > 0, "the session is green again"


def test_severity_is_monotonic_across_a_whole_session():
    order = {"info": 0, "caution": 1, "danger": 2, "critical": 3}
    pnls = [8000, -5000, 1000, -6000, 3000, -2000]
    seq = _sequence(pnls)
    ranks = [order[e.severity] for e in seq]
    assert ranks == sorted(ranks), f"severity moved backwards: {[e.severity for e in seq]}"


# ── it reports the moment, not the outcome ─────────────────────────────────

def test_a_recovered_session_is_described_as_it_stands_now():
    """
    Severity is sticky; the sentence is not. Telling a trader who is back in
    profit that their session "turned to loss" would be false at the moment it
    is read.
    """
    ev = _run([6000, -7000, 3000])
    assert "turned from profit to loss" not in ev.message
    assert "below break-even" in ev.message
    assert ev.context["currently_negative"] is False
    assert ev.context["trough_pnl"] is not None and ev.context["trough_pnl"] < 0


def test_a_currently_red_session_says_so_plainly():
    ev = _run([6000, -7000])
    assert "turned from profit to loss" in ev.message
    assert ev.context["currently_negative"] is True


def test_the_percentage_message_says_so_far():
    """No claim about how the day ends — it often ends green."""
    ev = _run([10_000, -6000])
    assert "so far" in ev.message


# ── the spec ───────────────────────────────────────────────────────────────

def test_the_spec_declares_the_facts_it_consumes():
    """Both primary inputs come from `facts`, which the spec used to omit."""
    from app.services.detector_registry import BY_NAME

    assert "facts" in BY_NAME["profit_giveaway"].consumes


def test_the_detector_is_pure():
    """No DB. Every test in this file runs it with no session and no await."""
    import inspect

    src = inspect.getsource(engine._detect_profit_giveaway)
    for forbidden in ("await ", "db.", "select("):
        assert forbidden not in src, f"detector reaches for {forbidden!r}"


# ── episode dedup: one episode is one fall from one high-water mark ────────
#
# Added 2026-08-27. `worst_giveaway` is facts.max_drawdown, which is SESSION-wide
# and does not reset when the session makes a new high. Under the old
# pattern_type key a second, shallower giveback could therefore be swallowed: a
# session peaking at 5,000 that falls to 1,000 alerts, recovers to 8,000 and
# falls to 5,000 has given back 3,000 from a new high while max_drawdown still
# reads 4,000 - no escalation, no +20% re-arm, inside the window, silence.
#
# On the reference book this changes nothing: 100 alerts before and after, the
# identical set, because 47 of the 48 affected sessions hold exactly one
# episode. It is a correctness fix, not a volume one. Full analysis in
# docs/patterns/06-profit_giveaway/episode_dedup_analysis.md.


class TestEpisodeDedup:

    def test_a_new_high_water_mark_is_a_new_episode(self):
        """`peak_pnl` identifies the episode, so a new peak is a new key."""
        first = _pattern_dedup_key(
            "profit_giveaway", {"session_date": "2026-02-06", "peak_pnl": 1667.0})
        second = _pattern_dedup_key(
            "profit_giveaway", {"session_date": "2026-02-06", "peak_pnl": 3615.0})
        assert first != second, (
            "a giveback from a higher high would be suppressed by the earlier one"
        )

    def test_the_same_peak_shares_one_key(self):
        a = _pattern_dedup_key(
            "profit_giveaway", {"session_date": "2026-02-06", "peak_pnl": 1667.0})
        b = _pattern_dedup_key(
            "profit_giveaway", {"session_date": "2026-02-06", "peak_pnl": 1667.0})
        assert a == b, "one episode must not alert twice for the same reason"

    def test_the_same_peak_on_a_different_day_is_a_different_episode(self):
        """
        peak_pnl resets at the market open, so two sessions can coincidentally
        reach the same figure. The session date is in the key for that reason.
        """
        a = _pattern_dedup_key(
            "profit_giveaway", {"session_date": "2026-02-06", "peak_pnl": 2000.0})
        b = _pattern_dedup_key(
            "profit_giveaway", {"session_date": "2026-02-09", "peak_pnl": 2000.0})
        assert a != b

    def test_the_detector_supplies_both_halves_of_the_key(self):
        """
        `last_fired` is rebuilt by re-keying stored RiskAlert rows, so both key
        components have to survive into the alert's details - not just be
        available in the engine.
        """
        ev = _run([6000, -4000], session_date="2026-02-06")
        assert ev.context["peak_pnl"] == 6000
        assert ev.context["session_date"] == "2026-02-06"
        key = _pattern_dedup_key("profit_giveaway", ev.context)
        assert key == "profit_giveaway:2026-02-06:6000.0"

    def test_an_earlier_episode_does_not_suppress_a_later_one(self):
        """
        The end-to-end case, run through the real dedup predicate rather than
        asserted about the key. Episode 1 gives back from a peak of 6,000 and
        alerts. The session then makes a new high of 12,000 and gives back from
        THAT - shallower in absolute terms, so max_drawdown has not moved and
        the severity has not escalated. It must still be heard.
        """
        first = _run([6000, -4000], session_date="2026-02-06")
        # Recover past the old peak, then give back half of the NEW one. The
        # second giveback (4,500) is deeper than the first (4,000) but not by
        # the 20% the re-arm needs, so nothing except the episode key can let
        # it through.
        second = _run([6000, -4000, 7000, -4500], session_date="2026-02-06")
        assert first is not None and second is not None
        assert second.context["peak_pnl"] > first.context["peak_pnl"]

        k1 = _pattern_dedup_key("profit_giveaway", first.context)
        k2 = _pattern_dedup_key("profit_giveaway", second.context)
        assert k1 != k2, "the second episode shares the first's dedup stream"

        # Same severity, and max_drawdown has NOT grown by 20% - so neither the
        # escalation rule nor the re-arm would have let it through.
        assert second.severity == first.severity
        assert not _worsened("profit_giveaway", first.context, second.context), (
            "this test is only meaningful if the re-arm would NOT have fired"
        )

    def test_the_rearm_still_works_inside_one_episode(self):
        """
        The episode key must not disable the deepening re-arm. Same peak, same
        key, but the giveback grew well past 20% - `_worsened` still says yes.
        """
        shallow = _run([8000, -4000], session_date="2026-02-06")
        deep = _run([8000, -4000, -3000], session_date="2026-02-06")
        assert shallow.context["peak_pnl"] == deep.context["peak_pnl"]
        assert (_pattern_dedup_key("profit_giveaway", shallow.context)
                == _pattern_dedup_key("profit_giveaway", deep.context))
        assert _worsened("profit_giveaway", shallow.context, deep.context), (
            "a deepening giveback inside one episode must still re-fire"
        )

    def test_a_shallower_moment_in_the_same_episode_does_not_refire(self):
        """The re-arm rule is unchanged: it takes +20%, not any change."""
        deep = _run([8000, -6000], session_date="2026-02-06")
        recovered = _run([8000, -6000, 2000], session_date="2026-02-06")
        assert not _worsened("profit_giveaway", deep.context, recovered.context)


class TestOtherDetectorsUntouched:

    @pytest.mark.parametrize("pattern", [
        "martingale_behaviour", "revenge_trade", "adding_to_adverse_position",
        "size_escalation", "daily_overtrading", "overtrading_burst",
    ])
    def test_every_other_pattern_still_keys_on_its_type_alone(self, pattern):
        assert _pattern_dedup_key(
            pattern, {"peak_pnl": 5000, "session_date": "2026-02-06"}) == pattern

    def test_the_two_pre_existing_per_episode_keys_are_unchanged(self):
        assert (_pattern_dedup_key("constitution_violation", {"rule": "daily_loss"})
                == "constitution_violation:daily_loss")
        assert (_pattern_dedup_key("same_symbol_obsession", {"underlying": "NIFTY"})
                == "same_symbol_obsession:NIFTY")

    def test_other_worsen_metrics_are_intact(self):
        for pattern in ("martingale_behaviour", "premium_loss_event",
                        "constitution_violation"):
            assert pattern in _WORSEN_METRIC

    def test_the_dedup_window_is_still_two_hours(self):
        """
        The window was NOT part of this change. `_DEDUP_HOURS` is a local inside
        both task functions rather than a module attribute, so this reads the
        source - an awkward test that pins a real decision beats no test.
        """
        import inspect

        from app.tasks import trade_tasks

        src = inspect.getsource(trade_tasks)
        assert src.count('"profit_giveaway":         2,') == 2, (
            "the 2-hour dedup window changed, or moved"
        )
