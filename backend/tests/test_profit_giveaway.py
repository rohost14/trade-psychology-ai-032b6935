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


def _run(pnls, thresholds=None):
    """Run the detector on the LAST trade of a session with these P&Ls."""
    trades = [_ct(p, -60 + i * 5) for i, p in enumerate(pnls)]
    th = {"profit_giveaway_min_peak": 1500,
          "profit_giveaway_min_erosion": 500,
          "profit_giveaway_caution_pct": 0.50}
    th.update(thresholds or {})
    ctx = EngineContext(
        broker_account_id=trades[-1].broker_account_id,
        session=SimpleNamespace(session_pnl=_facts(pnls).pnl,
                                session_date=None, market_open=None),
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
