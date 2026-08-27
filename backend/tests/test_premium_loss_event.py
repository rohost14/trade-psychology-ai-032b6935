"""
`premium_loss_event` — how much of a long option's premium is gone.

Pattern #8 review, 2026-08-27. **Verdict was KEEP AS-IS**, so these tests pin
the behaviour that was NOT changed as firmly as the three cleanup items that
were. The bands, the expiry shift, the repeat rule, the severity mapping and the
trigger timing are all untouched, and a test here fails if any of them moves.

Why it survived where Patterns 5, 6 and 7 did not: its 48 flagged trades carry
-Rs 238,623 against a book whose gross loss is -Rs 690,545 — 35% of every rupee
lost, from 5% of positions — and its severity ladder tracks magnitude, with the
critical band's median loss 1.9x the caution band's. It is the only reviewed
detector whose flagged set is the expensive one.

The three cleanup items:
  1. the stale MANDATORY_REVIEW flag on premium_loss_caution_pct is cleared,
     because measurement refuted it: only 6% of long options lose 40%+.
  2. the two unsourced constants are recorded as unsourced.
  3. the exit-time message no longer reads as though the loss were still
     happening to a position that is already closed.
"""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.models.completed_trade import CompletedTrade
from app.services.behavior_engine import BehaviorEngine, EngineContext

engine = BehaviorEngine()


def _opt(loss_pct, symbol="NIFTY25AUG25000CE", direction="LONG",
         instrument_type="CE", hold=120, qty=75, entry=100.0):
    """A closed long option that lost `loss_pct` percent of its premium."""
    ct = MagicMock(spec=CompletedTrade)
    ct.id = uuid4()
    ct.broker_account_id = uuid4()
    ct.tradingsymbol = symbol
    ct.exchange = "NFO"
    ct.direction = direction
    ct.instrument_type = instrument_type
    ct.avg_entry_price = Decimal(str(entry))
    ct.avg_exit_price = Decimal(str(round(entry * (1 - loss_pct / 100), 4)))
    ct.pnl_pct = Decimal(str(-loss_pct))
    ct.realized_pnl = Decimal(str(round(-entry * loss_pct / 100 * qty, 2)))
    ct.total_quantity = qty
    ct.duration_minutes = hold
    ct.entry_time = None
    ct.exit_time = None
    return ct


def _run(ct, prior=(), thresholds=None):
    ctx = EngineContext(
        broker_account_id=ct.broker_account_id,
        session=SimpleNamespace(session_pnl=Decimal("0"),
                                session_date=None, market_open=None),
        completed_trade=ct, session_trades=list(prior),
        active_cooldowns=[], thresholds=thresholds or {},
    )
    return engine._detect_premium_loss_event(ctx)


# ── the bands are unchanged ────────────────────────────────────────────────

@pytest.mark.parametrize("loss,expected", [
    (39.9, None),
    (40.0, "caution"),
    (55.0, "caution"),
    (59.9, "caution"),
    (60.0, "danger"),
    (75.0, "danger"),
    (79.9, "danger"),
    (80.0, "critical"),
    (100.0, "critical"),
])
def test_the_bands_are_40_60_80(loss, expected):
    ev = _run(_opt(loss))
    assert (ev.severity if ev else None) == expected, f"{loss}% -> {expected}"


def test_the_band_constants_did_not_move():
    from app.core.trading_defaults import COLD_START_DEFAULTS as D

    assert D["premium_loss_caution_pct"] == 40
    assert D["premium_loss_danger_pct"] == 60
    assert D["premium_loss_critical_pct"] == 80
    assert D["premium_loss_expiry_shift_pct"] == 15
    assert D["premium_loss_fast_hold_min"] == 30


def test_it_stays_universal_safety():
    """A trader's habits must not raise the bar on how much premium is gone."""
    from app.core.threshold_registry import THRESHOLD_SPECS
    from app.core.threshold_resolution import Kind

    for key in ("premium_loss_caution_pct", "premium_loss_danger_pct",
                "premium_loss_critical_pct"):
        assert THRESHOLD_SPECS[key].kind is Kind.UNIVERSAL_SAFETY


# ── the population guard is unchanged ──────────────────────────────────────

def test_short_options_are_never_considered():
    """Premium is received, not destroyed; a percentage of it is meaningless."""
    assert _run(_opt(90.0, direction="SHORT")) is None


@pytest.mark.parametrize("kind", ["FUT", "EQ"])
def test_only_options_are_considered(kind):
    assert _run(_opt(90.0, instrument_type=kind)) is None


def test_a_profitable_option_says_nothing():
    ct = _opt(0)
    ct.pnl_pct = Decimal("25")
    assert _run(ct) is None


# ── the repeat rule is unchanged ───────────────────────────────────────────

def test_a_second_option_past_danger_promotes_danger_to_critical():
    """
    Unsourced and load-bearing: it produced 2 of the 10 criticals on the
    reference book. Left alone by the review; pinned here so a change is
    deliberate.
    """
    prior = [_opt(70.0, symbol="BANKNIFTY25AUG55000CE")]
    # 65% is in the danger band on its own...
    assert _run(_opt(65.0), prior=[]).severity == "danger"
    # ...and a second long option already past danger today makes it critical.
    assert _run(_opt(65.0), prior=prior).severity == "critical"


def test_the_repeat_rule_does_not_promote_caution():
    """It escalates danger, and only danger."""
    prior = [_opt(70.0, symbol="BANKNIFTY25AUG55000CE")]
    assert _run(_opt(45.0), prior=prior).severity == "caution"


def test_the_repeat_rule_needs_a_prior_past_danger():
    prior = [_opt(45.0, symbol="BANKNIFTY25AUG55000CE")]   # caution only
    assert _run(_opt(65.0), prior=prior).severity == "danger"


def test_the_repeat_count_is_reported():
    prior = [_opt(70.0, symbol="BANKNIFTY25AUG55000CE")]
    assert _run(_opt(65.0), prior=prior).context["repeat_count_today"] == 1


# ── the impossible-loss cap is unchanged ───────────────────────────────────

def test_a_loss_past_100_percent_is_capped_not_printed():
    """
    A long option cannot lose more than the premium. Past 100% the stored
    pnl_pct is wrong, and "180% of premium lost" reaching a trader would cost
    the credibility of every other number on the screen.
    """
    ct = _opt(50.0)
    ct.pnl_pct = Decimal("-180")
    ev = _run(ct)
    assert ev.context["loss_pct"] == 100.0
    assert "180" not in ev.message


# ── cleanup 1: the stale flag is cleared ───────────────────────────────────

def test_the_stale_mandatory_review_flag_is_cleared():
    """
    It was flagged as "firing routinely without behavioural failure". Measured
    across 888 long options, only 6% lose 40%+ of premium, so the flag was
    refuted rather than confirmed and an open-concern marker on it would be
    false.
    """
    from app.core.threshold_registry import MANDATORY_REVIEW

    assert "premium_loss_caution_pct" not in MANDATORY_REVIEW


def test_the_constants_that_were_deleted_keep_their_entries():
    """
    Clearing a vindicated flag must not clear the retired ones. Those three
    constants no longer exist, so the set is the only place their reason lives.
    """
    from app.core.threshold_registry import MANDATORY_REVIEW

    for key in ("burst_trades_per_15min", "revenge_window_danger_min",
                "fomo_symbols_at_open"):
        assert key in MANDATORY_REVIEW


# ── cleanup 2: the unsourced constants are recorded as such ────────────────

@pytest.mark.parametrize("key", ["premium_loss_expiry_shift_pct",
                                 "premium_loss_fast_hold_min"])
def test_the_unsourced_constants_say_so(key):
    """
    Neither has a derivation. The file's own convention is that an unmarked
    number is a judgement someone made once; these are now marked.
    """
    import inspect

    from app.core import trading_defaults

    src = inspect.getsource(trading_defaults)
    line = next(l for l in src.splitlines() if f"'{key}'" in l)
    assert "UNSOURCED" in line, f"{key} is unsourced but does not say so"


def test_the_repeat_rules_inline_literal_is_recorded_as_unsourced():
    import inspect

    src = inspect.getsource(engine._detect_premium_loss_event)
    assert "INLINE LITERAL WITH NO KEY AND NO SOURCE" in src


# ── cleanup 3: the message describes a closed position ─────────────────────

def test_the_message_says_the_position_is_closed():
    ev = _run(_opt(85.0))
    assert ev.message.startswith("Closed "), ev.message
    assert "lost 85% of the premium paid" in ev.message


def test_the_message_no_longer_speculates_about_why():
    """
    It used to say "likely bought into peak IV". The hold time is observed; the
    reason for it is not, and this detector cannot see implied volatility at
    entry.
    """
    ev = _run(_opt(85.0, hold=10))
    assert ev.context["fast_collapse"] is True
    low = ev.message.lower()
    for claim in ("likely", "peak iv", "iv crush", "bought into", "panic",
                  "chasing"):
        assert claim not in low, f"message speculates: {claim!r}"
    assert "held 10 min" in ev.message, "the observed fact should survive"


def test_the_fast_collapse_flag_still_never_touches_severity():
    slow = _run(_opt(65.0, hold=600))
    fast = _run(_opt(65.0, hold=5))
    assert slow.severity == fast.severity == "danger"
    assert fast.context["fast_collapse"] is True
    assert slow.context["fast_collapse"] is False


# ── unchanged plumbing ─────────────────────────────────────────────────────

def test_the_evidence_still_carries_what_a_trader_would_need():
    ev = _run(_opt(85.0))
    for key in ("tradingsymbol", "loss_pct", "entry_premium", "exit_premium",
                "realized_pnl", "hold_minutes", "fast_collapse",
                "repeat_count_today", "levels"):
        assert key in ev.context, key
    assert ev.context["levels"] == {"caution": 40.0, "danger": 60.0,
                                    "critical": 80.0}


def test_the_spec_and_worsen_metric_did_not_move():
    from app.services.detector_registry import BY_NAME
    from app.tasks.trade_tasks import _WORSEN_METRIC

    spec = BY_NAME["premium_loss_event"]
    assert spec.nature == "risk"
    assert spec.disposition == "alerting"
    assert spec.notification_level == 3
    assert spec.guardian_eligible is False
    assert _WORSEN_METRIC["premium_loss_event"] == "loss_pct"


def test_the_detector_is_pure():
    import inspect

    src = inspect.getsource(engine._detect_premium_loss_event)
    for forbidden in ("await ", "db.", "select("):
        assert forbidden not in src
