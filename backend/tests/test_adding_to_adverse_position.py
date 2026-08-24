"""
Pattern #1 — adding_to_adverse_position.

The 24 cases here are the ones the contract was validated against before any
code was written (docs/contracts/adding_to_adverse_position_validation.md).
They are the specification, not a retrofit: each was chosen to pin a decision
the contract makes, and several exist only to prove the detector stays SILENT.

The severity matrix is deliberately not a score. Two ordinal axes, both
definitional — how many times the trader added while under water, and whether
any add was at least as large as the position it was added to. No percentage
appears anywhere in this file, because the review measured every candidate and
found no defensible cut point in any of them.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.position_fills import (
    PositionFill,
    adverse_adds,
    deepens_each_time,
)
from app.services.behavior_engine import BehaviorEngine, EngineContext

engine = BehaviorEngine()
T0 = datetime(2026, 8, 24, 4, 0, tzinfo=timezone.utc)


# ── helpers ──────────────────────────────────────────────────────────────

def fills(*specs):
    """
    Build a ledger-shaped fill sequence.

    Each spec is (entry_type, signed_qty, price). Running position and average
    are computed the way position_ledger computes them, so these rows are the
    same shape the production query returns.
    """
    out, held, avg = [], 0, 0.0
    for et, qty, price in specs:
        if et == "OPEN" or (et == "FLIP"):
            held, avg = qty, price
        elif et == "INCREASE":
            new = held + qty
            avg = (avg * abs(held) + price * abs(qty)) / abs(new)
            held = new
        elif et == "DECREASE":
            held += qty
        elif et == "CLOSE":
            held, avg = 0, 0.0
        out.append(PositionFill(
            entry_type=et, fill_qty=qty, fill_price=price,
            position_qty_after=held,
            avg_entry_price_after=avg if held else None,
            occurred_at=T0 + timedelta(minutes=len(out) * 5),
        ))
    return out


def ctx(position_fills, *, itype="CE", symbol="NIFTY25AUG24000CE",
        direction="LONG", qty=150, entry=45.0, spread=False, num_entries=None):
    ct = SimpleNamespace(
        id=uuid4(), broker_account_id=uuid4(), tradingsymbol=symbol,
        exchange="NFO", product="MIS", instrument_type=itype,
        direction=direction, total_quantity=qty,
        avg_entry_price=Decimal(str(entry)), avg_exit_price=Decimal("30"),
        realized_pnl=Decimal("-2000"), pnl_pct=None, duration_minutes=60,
        entry_time=T0, exit_time=T0 + timedelta(hours=2),
        num_entries=num_entries if num_entries is not None
        else max(1, sum(1 for f in position_fills
                        if f.entry_type in ("OPEN", "INCREASE"))),
        num_exits=1, closed_by_flip=False, status="closed", quality_score=None,
    )
    return EngineContext(
        broker_account_id=ct.broker_account_id,
        session=SimpleNamespace(session_pnl=Decimal("0"),
                                session_date=T0.date(), market_open=None),
        completed_trade=ct, session_trades=[], active_cooldowns=[],
        thresholds={}, position_fills=position_fills,
        strategy_group=SimpleNamespace(strategy_type="straddle", net_pnl=None)
        if spread else None,
    )


def run(position_fills, **kw):
    return engine._detect_adding_to_adverse_position(ctx(position_fills, **kw))


# ── 1-8. directional symmetry, every instrument class ────────────────────

class TestDirectionalSymmetry:
    """
    A long filling lower and a short filling higher are the same event. If this
    class ever fails asymmetrically, the sign handling has broken.
    """

    @pytest.mark.parametrize("itype,symbol,long_prices,short_prices", [
        ("EQ", "RELIANCE", (100.0, 90.0), (100.0, 110.0)),
        ("FUT", "NIFTY25AUGFUT", (24000.0, 23760.0), (24000.0, 24240.0)),
        ("CE", "NIFTY25AUG24000CE", (50.0, 40.0), (50.0, 60.0)),
        ("PE", "NIFTY25AUG24000PE", (50.0, 40.0), (50.0, 60.0)),
    ])
    def test_long_and_short_produce_the_same_adverse_move(
            self, itype, symbol, long_prices, short_prices):
        lo, ladd = long_prices
        so, sadd = short_prices
        long_res = run(fills(("OPEN", 100, lo), ("INCREASE", 100, ladd)),
                       itype=itype, symbol=symbol, direction="LONG")
        short_res = run(fills(("OPEN", -100, so), ("INCREASE", -100, sadd)),
                        itype=itype, symbol=symbol, direction="SHORT")
        assert long_res.fired and short_res.fired
        assert (long_res.context["deepest_adverse_pct"]
                == short_res.context["deepest_adverse_pct"])


# ── 9-11. the size of the add does not decide whether it happened ────────

class TestAddSizeIsNotTheTrigger:
    """
    The finding this whole review turned on: 95 of 96 real adverse adds were
    smaller than 1.5x the position held. Size may not gate detection.
    """

    def test_add_smaller_than_held_is_detected(self):
        r = run(fills(("OPEN", 150, 50.0), ("INCREASE", 50, 40.0)))
        assert r.fired and r.context["adverse_add_count"] == 1
        assert r.context["at_least_doubled_down"] is False

    def test_add_same_size_as_held_is_detected(self):
        r = run(fills(("OPEN", 75, 50.0), ("INCREASE", 75, 40.0)))
        assert r.fired
        assert r.context["at_least_doubled_down"] is True

    def test_add_larger_than_held_is_detected(self):
        r = run(fills(("OPEN", 75, 50.0), ("INCREASE", 225, 40.0)))
        assert r.fired and r.context["at_least_doubled_down"] is True


# ── 12-13. repetition and escalation drive severity ──────────────────────

class TestSeverityMatrix:
    """
    Three adverse adds at constant size is the ASIANPAINT ladder from the real
    book: 200 @5.05 -> 200 @4.55 -> 200 @4.00 -> 200 @3.50, -Rs 2,810.
    """

    def test_one_adverse_add_smaller_than_held_is_info(self):
        r = run(fills(("OPEN", 150, 50.0), ("INCREASE", 50, 40.0)))
        assert r.severity == "info"

    def test_one_adverse_add_at_least_doubling_down_is_caution(self):
        r = run(fills(("OPEN", 75, 50.0), ("INCREASE", 75, 40.0)))
        assert r.severity == "caution"

    def test_two_adverse_adds_smaller_than_held_is_caution(self):
        r = run(fills(("OPEN", 300, 50.0), ("INCREASE", 75, 45.0),
                      ("INCREASE", 75, 40.0)))
        assert r.severity == "caution"
        assert r.context["adverse_add_count"] == 2

    def test_two_adverse_adds_with_doubling_down_is_danger(self):
        r = run(fills(("OPEN", 75, 50.0), ("INCREASE", 75, 45.0),
                      ("INCREASE", 150, 40.0)))
        assert r.severity == "danger"

    def test_three_constant_size_adverse_adds_is_danger(self):
        r = run(fills(("OPEN", 200, 5.05), ("INCREASE", 200, 4.55),
                      ("INCREASE", 200, 4.00), ("INCREASE", 200, 3.50)))
        assert r.severity == "critical", "constant-size adds still double down"
        assert r.context["adverse_add_count"] == 3
        assert r.context["deepens_each_time"] is True

    def test_three_adverse_adds_all_smaller_than_held_is_danger(self):
        r = run(fills(("OPEN", 900, 50.0), ("INCREASE", 75, 45.0),
                      ("INCREASE", 75, 40.0), ("INCREASE", 75, 35.0)))
        assert r.severity == "danger"
        assert r.context["at_least_doubled_down"] is False

    def test_severity_never_exceeds_critical_however_many_adds(self):
        r = run(fills(("OPEN", 75, 50.0), *[
            ("INCREASE", 75, 50.0 - i) for i in range(1, 9)
        ]))
        assert r.severity == "critical"
        assert r.context["a_level"] == 3, "the repetition axis saturates at 3"


# ── 14-17. favourable and break-even adds must never fire ────────────────

class TestFavourableAddsAreNotThisPattern:

    def test_long_adding_after_a_favourable_move_is_silent(self):
        r = run(fills(("OPEN", 75, 50.0), ("INCREASE", 75, 60.0)))
        assert not r.fired

    def test_short_adding_after_a_favourable_move_is_silent(self):
        r = run(fills(("OPEN", -75, 50.0), ("INCREASE", -75, 40.0)),
                direction="SHORT")
        assert not r.fired

    def test_break_even_add_is_silent(self):
        r = run(fills(("OPEN", 75, 50.0), ("INCREASE", 75, 50.0)))
        assert not r.fired

    def test_favourable_then_adverse_reports_only_the_adverse_one(self):
        r = run(fills(("OPEN", 75, 50.0), ("INCREASE", 75, 55.0),
                      ("INCREASE", 75, 40.0)))
        assert r.fired and r.context["adverse_add_count"] == 1


# ── 18-22. reductions, closes, flips, re-entry ───────────────────────────

class TestPositionLifecycle:

    def test_partial_exit_is_not_an_add(self):
        r = run(fills(("OPEN", 150, 50.0), ("DECREASE", -75, 45.0)))
        assert not r.fired

    def test_partial_exit_then_readd_while_adverse_is_detected(self):
        r = run(fills(("OPEN", 150, 50.0), ("DECREASE", -75, 45.0),
                      ("INCREASE", 75, 40.0)))
        assert r.fired and r.context["adverse_add_count"] == 1

    def test_close_then_reentry_is_not_an_add(self):
        r = run(fills(("OPEN", 75, 50.0), ("CLOSE", -75, 45.0),
                      ("OPEN", 75, 44.0)))
        assert not r.fired

    def test_flip_resets_the_counter(self):
        """The trader who reverses is not still adding to what they closed."""
        r = run(fills(("OPEN", 75, 50.0), ("INCREASE", 75, 45.0),
                      ("FLIP", -150, 40.0), ("INCREASE", -75, 45.0)),
                direction="SHORT")
        assert r.fired
        assert r.context["adverse_add_count"] == 1, "pre-flip adds do not carry over"

    def test_single_fill_position_is_a_clean_non_detection(self):
        r = run(fills(("OPEN", 75, 50.0), ("CLOSE", -75, 40.0)))
        assert not r.fired
        assert not r.abstained, "a single-entry position is a real negative"


# ── 23-24. exposure that cannot be trusted ───────────────────────────────

class TestAbstention:

    def test_spread_leg_abstains_rather_than_guessing(self):
        r = run(fills(("OPEN", 75, 50.0), ("INCREASE", 75, 40.0)), spread=True)
        assert r.abstained
        assert not r.fired

    def test_hedged_multileg_abstains_however_many_adds(self):
        r = run(fills(("OPEN", 75, 50.0), ("INCREASE", 75, 45.0),
                      ("INCREASE", 75, 40.0)), spread=True)
        assert r.abstained

    def test_multi_entry_position_with_no_fills_abstains(self):
        """
        The loader only queries when num_entries > 1. If it queried and got
        nothing, the sequence is genuinely unreadable and saying "did not
        happen" would be a lie.
        """
        r = run([], num_entries=3)
        assert r.abstained

    def test_single_entry_position_with_no_fills_is_negative_not_abstained(self):
        r = run([], num_entries=1)
        assert not r.abstained and not r.fired


# ── the walker itself ────────────────────────────────────────────────────

class TestAdverseAddWalker:

    def test_deepening_is_detected(self):
        adds = adverse_adds(fills(
            ("OPEN", 75, 59.0), ("INCREASE", 75, 50.0),
            ("INCREASE", 75, 42.7), ("INCREASE", 75, 34.35)))
        assert len(adds) == 3
        assert deepens_each_time(adds)
        assert [a.index for a in adds] == [1, 2, 3]

    def test_non_deepening_is_not_reported_as_deepening(self):
        # Second add is adverse against the NEW average of 45, but only just -
        # shallower than the first, so the ladder is not deepening.
        adds = adverse_adds(fills(
            ("OPEN", 75, 50.0), ("INCREASE", 75, 40.0),
            ("INCREASE", 75, 44.0)))
        assert len(adds) == 2
        assert adds[1].adverse_pct < adds[0].adverse_pct
        assert not deepens_each_time(adds)

    def test_the_real_nifty_ladder_from_the_book(self):
        """
        2025-11-25 NIFTY25NOV26000CE, the largest single loss in the tradebook
        at -Rs 8,835, straight from position_ledger.
        """
        adds = adverse_adds(fills(
            ("OPEN", 75, 59.00), ("INCREASE", 75, 50.00),
            ("INCREASE", 75, 42.70), ("INCREASE", 75, 34.35),
            ("INCREASE", 75, 30.50), ("CLOSE", -375, 19.75)))
        assert len(adds) == 4
        assert deepens_each_time(adds)
        assert round(adds[0].adverse_pct) == 15
        assert round(adds[-1].adverse_pct) == 34
        assert all(a.at_least_doubled_down is False for a in adds[1:]), \
            "each add is smaller than the position it was added to by then"
