"""
Pattern #3 — same_symbol_obsession.

The behaviour is the session's relationship with ONE UNDERLYING: coming back to
it, losing on it, and coming back again. On 4 of the 20 episodes in the
reference book no other detector fires at all — repeated losing attempts at flat
or falling size — so the quiet `caution` tier is the one carrying this
detector's unique signal, and several tests below exist to protect it.

Severity is one definitional comparison, `max(qty) > qty[0]`. A loss-count tier
was considered and rejected: the distribution is {3: 11, 4: 6, 5: 2, 6: 1}, a
smooth decay with no break anywhere, so any boundary would be a choice presented
as a fact.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.trading_defaults import COLD_START_DEFAULTS
from app.services.behavior_engine import BehaviorEngine, EngineContext
from app.tasks.trade_tasks import _WORSEN_METRIC, _pattern_dedup_key

engine = BehaviorEngine()
T0 = datetime(2026, 8, 24, 4, 0, tzinfo=timezone.utc)


def trade(symbol, qty, pnl, minute, dur=10):
    return SimpleNamespace(
        id=uuid4(), broker_account_id=None, tradingsymbol=symbol,
        exchange="NFO", product="MIS", instrument_type="CE", direction="LONG",
        total_quantity=qty, avg_entry_price=Decimal("50"),
        avg_exit_price=Decimal("45"), realized_pnl=Decimal(str(pnl)),
        pnl_pct=None, duration_minutes=dur,
        entry_time=T0 + timedelta(minutes=minute),
        exit_time=T0 + timedelta(minutes=minute + dur),
        num_entries=1, num_exits=1, closed_by_flip=False, status="closed",
        quality_score=None,
    )


def run(trades):
    ctx = EngineContext(
        broker_account_id=uuid4(),
        session=SimpleNamespace(session_pnl=Decimal("0"),
                                session_date=T0.date(), market_open=None),
        completed_trade=trades[-1], session_trades=trades[:-1],
        thresholds={},
    )
    return engine._detect_same_symbol_obsession(ctx)


def ladder(qtys, pnls=None, symbol="NIFTY25AUG24000CE", spacing=20):
    """One trade per quantity, all losses unless pnls says otherwise."""
    pnls = pnls or [-500.0] * len(qtys)
    return [trade(symbol, q, p, i * spacing)
            for i, (q, p) in enumerate(zip(qtys, pnls))]


# ── the two severity tiers ───────────────────────────────────────────────

class TestSeverity:

    def test_three_losses_at_constant_size_is_caution(self):
        """
        The unique contribution. Nothing escalated, nothing was added to an open
        position, nothing was fast — no other detector in the engine sees this.
        """
        r = run(ladder([75, 75, 75]))
        assert r is not None
        assert r.severity == "caution"
        assert r.context["size_rising"] is False
        assert r.context["losses"] == 3

    def test_three_losses_with_size_rising_is_danger(self):
        r = run(ladder([75, 150, 300]))
        assert r.severity == "danger"
        assert r.context["size_peak"] == 300
        assert r.context["size_first"] == 75

    def test_a_size_that_PEAKED_and_came_back_is_still_danger(self):
        """
        The bug this review fixed. `last > first` scored 75, 150, 375, 75 as
        caution, hiding a 5x spike because only the endpoints were compared.
        """
        r = run(ladder([75, 150, 375, 75]))
        assert r.severity == "danger"
        assert r.context["size_peak"] == 375

    def test_size_falling_throughout_is_caution(self):
        r = run(ladder([300, 150, 75]))
        assert r.severity == "caution"

    def test_severity_never_falls_as_the_episode_grows(self):
        """
        An episode only grows. A severity that can drop tells the trader their
        situation improved when it did not — which the old rule did on four of
        the twenty episodes in the book.
        """
        qtys = [75, 150, 375, 75, 150, 75, 75]
        seen = []
        for n in range(3, len(qtys) + 1):
            r = run(ladder(qtys[:n]))
            if r:
                seen.append(r.severity)
        assert seen, "the ladder should fire"
        ranks = {"caution": 1, "danger": 2}
        assert all(ranks[b] >= ranks[a] for a, b in zip(seen, seen[1:])), \
            f"severity fell during the episode: {seen}"


# ── what must not be counted ─────────────────────────────────────────────

class TestExclusions:

    def test_two_losses_is_below_the_minimum(self):
        assert run(ladder([75, 75], pnls=[-500.0, -500.0])) is None

    def test_winning_trades_do_not_count_toward_the_losses(self):
        """Three attempts but only two lost — not yet the pattern."""
        assert run(ladder([75, 75, 75], pnls=[-500.0, 400.0, -500.0])) is None

    def test_a_winning_current_trade_does_not_suppress_it(self):
        """
        The three losses happened. 16 of 49 firings in the book had a winning
        current trade, and the episode is reported either way — this detector
        states a fact and makes no predictive claim.
        """
        r = run(ladder([75, 75, 75, 75],
                       pnls=[-500.0, -500.0, -500.0, 900.0]))
        assert r is not None and r.context["losses"] == 3

    def test_a_different_underlying_is_a_different_episode(self):
        mixed = (ladder([75, 75], symbol="NIFTY25AUG24000CE")
                 + ladder([75, 75, 75], symbol="SENSEX25AUG80000CE", spacing=25))
        for t, m in zip(mixed, range(0, 200, 20)):
            t.entry_time = T0 + timedelta(minutes=m)
            t.exit_time = T0 + timedelta(minutes=m + 10)
        r = run(mixed)
        assert r is not None
        assert r.context["underlying"] == "SENSEX", "only the current underlying counts"
        assert r.context["attempts"] == 3


# ── the underlying, not the contract ─────────────────────────────────────

class TestDifferentStrikesAreOneEpisode:

    def test_three_strikes_of_one_underlying_are_one_episode(self):
        """43 of 49 firings in the book span two to five strikes."""
        trades = [
            trade("NIFTY25AUG24000CE", 75, -500.0, 0),
            trade("NIFTY25AUG24500CE", 75, -500.0, 20),
            trade("NIFTY25AUG23500PE", 75, -500.0, 40),
        ]
        r = run(trades)
        assert r is not None
        assert r.context["underlying"] == "NIFTY"
        assert r.context["attempts"] == 3

    def test_quantity_is_comparable_across_strikes(self):
        """Every strike and expiry of one underlying shares a lot size."""
        trades = [
            trade("NIFTY25AUG24000CE", 75, -500.0, 0),
            trade("NIFTY25AUG24500CE", 150, -500.0, 20),
            trade("NIFTY25SEP23500PE", 300, -500.0, 40),
        ]
        r = run(trades)
        assert r.severity == "danger" and r.context["size_peak"] == 300


# ── concurrent positions are counted, and said so ────────────────────────

def test_overlapping_attempts_are_recorded():
    """
    24 of 49 firings contain a pair where the next position opened before the
    previous closed. The count is unchanged — excluding them needs a rule no
    evidence supports — but the alert must not imply a sequence it has not
    checked.
    """
    trades = ladder([75, 75, 75])
    trades[1].entry_time = trades[0].exit_time - timedelta(minutes=5)
    r = run(trades)
    assert r.context["concurrent_pairs"] >= 1


def test_sequential_attempts_record_no_overlap():
    assert run(ladder([75, 75, 75])).context["concurrent_pairs"] == 0


# ── the dead constant ────────────────────────────────────────────────────

def test_obsession_min_reentries_is_gone():
    """
    It could never bind: losses is a subset of the attempts, so losses >= 3
    implies attempts >= 3 implies reentries >= 2.
    """
    assert "obsession_min_reentries" not in COLD_START_DEFAULTS


def test_obsession_min_losses_survives():
    assert COLD_START_DEFAULTS["obsession_min_losses"] == 3


# ── dedup: one alert per severity level per episode ──────────────────────

class TestEpisodeDedup:

    def test_each_underlying_is_its_own_dedup_stream(self):
        a = _pattern_dedup_key("same_symbol_obsession", {"underlying": "NIFTY"})
        b = _pattern_dedup_key("same_symbol_obsession", {"underlying": "SENSEX"})
        assert a != b, "two underlyings would suppress each other"

    def test_the_same_underlying_shares_one_key(self):
        a = _pattern_dedup_key("same_symbol_obsession", {"underlying": "NIFTY"})
        b = _pattern_dedup_key("same_symbol_obsession", {"underlying": "NIFTY"})
        assert a == b

    def test_it_no_longer_re_arms_on_a_growing_loss(self):
        """
        It re-armed when total_loss grew 20%, which let one episode alert
        several times at the SAME severity — ASIANPAINT produced four. Its
        re-arm is now severity escalation alone, which _is_deduped_full already
        allows.
        """
        assert "same_symbol_obsession" not in _WORSEN_METRIC


# ── nothing else moved ───────────────────────────────────────────────────

class TestOtherDetectorsAreUnaffected:

    # profit_giveaway left this list on 2026-08-27 when the detector was
    # retired; its _WORSEN_METRIC entry went with it.
    @pytest.mark.parametrize("pattern", [
        "martingale_behaviour", "premium_loss_event",
    ])
    def test_other_worsen_metrics_are_intact(self, pattern):
        assert pattern in _WORSEN_METRIC

    def test_the_constitution_dedup_key_is_unchanged(self):
        k = _pattern_dedup_key("constitution_violation", {"rule": "daily_loss"})
        assert k == "constitution_violation:daily_loss"

    def test_every_other_pattern_still_keys_on_its_type_alone(self):
        # profit_giveaway left this list on 2026-08-27: it now keys on its
        # episode, (session_date, peak_pnl). See test_profit_giveaway.py. The
        # subject of this test - that adding a per-episode key for one detector
        # does not quietly give one to the rest - is unchanged.
        for p in ("martingale_behaviour", "revenge_trade",
                  "adding_to_adverse_position"):
            assert _pattern_dedup_key(p, {"underlying": "NIFTY"}) == p
