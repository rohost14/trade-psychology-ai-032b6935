"""
`ctx.concluded_before_entry` — the outcome-known-before-this-decision relation.

WHY IT EXISTS (2026-08-30)

`session_trades` answers OCCURRED: did this trade happen in the session by now.
That is the right relation for counting, and a trade entered after this one but
closed before it is still one of today's trades.

It is the WRONG relation for a CAUSAL claim. A detector whose message says
"after X, you did Y" asserts the trader could see X when they decided Y, and
that is only true if X CLOSED STRICTLY BEFORE this position was ENTERED.

Two live detectors read `session_trades` for a causal claim:

    martingale_behaviour      9 of 32 firings on the reference book rested on a
                              loss that concluded AFTER the entry it explained -
                              the worst by 125 minutes. A live danger-tier alert
                              naming a cause that had not happened.
    post_loss_recovery_bet    identical unguarded shape, identical causal claim,
                              0 of 7 affected on this book. Luck, not protection.

Measured after the migration, on 175 sessions / 740 rounds:

    martingale_behaviour     32 -> 26      (as predicted)
    post_loss_recovery_bet    7 ->  7      (latent defect closed)
    revenge_trade           182 -> 182     PRESERVED
    rapid_reentry            14 ->  14     PRESERVED
    every existence detector       unchanged

THE FIVE SHAPES below are the real Pattern 20 cases that exposed this. Every one
of them was called "a re-entry after a loss" by a detector, and in none of them
was the loss knowable at the entry being described.

See docs/patterns/00-shared/TEMPORAL_CONTRACT_INVESTIGATION.md.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.trading_defaults import COLD_START_DEFAULTS
from app.services.behavior_engine import BehaviorEngine, EngineContext

engine = BehaviorEngine()
DAY = datetime(2026, 4, 15, tzinfo=timezone.utc)
ACCT = uuid4()


def at(h, m):
    return DAY.replace(hour=h, minute=m)


def trade(sym, entry, exit_, pnl, qty=75, price="100"):
    return SimpleNamespace(
        id=uuid4(), broker_account_id=ACCT, tradingsymbol=sym,
        exchange="NFO", product="MIS",
        instrument_type="CE" if sym.endswith("CE") else ("PE" if sym.endswith("PE") else "FUT"),
        direction="LONG", total_quantity=qty,
        avg_entry_price=Decimal(price), avg_exit_price=Decimal("90"),
        realized_pnl=Decimal(str(pnl)), pnl_pct=None,
        duration_minutes=int((exit_ - entry).total_seconds() // 60),
        entry_time=entry, exit_time=exit_,
        num_entries=1, num_exits=1, status="closed", quality_score=None)


def ctx(current, priors):
    return EngineContext(
        broker_account_id=ACCT,
        session=SimpleNamespace(
            session_pnl=Decimal(str(sum(float(t.realized_pnl) for t in priors))),
            session_date=DAY.date(), market_open=None),
        completed_trade=current, session_trades=list(priors),
        thresholds=dict(COLD_START_DEFAULTS))


def names(trades):
    return [t.tradingsymbol for t in trades]


# ── THE FIVE PATTERN-20 SHAPES ─────────────────────────────────────────────
#
# Each is the real case, with its real times.

def test_shape_1_same_minute_entry_is_not_prior():
    """
    2025-04-03. NIFTY…23300CE entered 13:29, and a PE on the same underlying
    entered THE SAME MINUTE and closed at 13:33.

    A CE and a PE opened in the same minute is a STRADDLE - one decision
    expressed as two rows. It is neither prior nor subsequent.
    """
    current = trade("NIFTY2540323300CE", at(13, 29), at(13, 34), -100)
    leg = trade("NIFTY2540323200PE", at(13, 29), at(13, 33), -562)

    assert names(ctx(current, [leg]).concluded_before_entry) == []


def test_shape_2_identical_lifetime_is_not_prior():
    """
    2025-05-13. Current 11:13->11:28; the cited PE also 11:13->11:28. The
    earlier CE (09:26->09:33) IS legitimately prior and must survive - this
    case is the one that mixes both.
    """
    current = trade("SENSEX2551382700CE", at(11, 13), at(11, 28), -200)
    real_prior = trade("SENSEX2551383000CE", at(9, 26), at(9, 33), -1113)
    straddle_leg = trade("SENSEX2551380700PE", at(11, 13), at(11, 28), -476)

    got = names(ctx(current, [real_prior, straddle_leg]).concluded_before_entry)
    assert got == ["SENSEX2551383000CE"], (
        "the genuinely earlier trade must stay; the concurrent leg must go")


def test_shape_3_still_open_at_entry_and_closing_together():
    """
    2025-05-21. DIXON 17500CE open 11:01->15:09. Current entered 12:08 while it
    was still open, and both closed at 15:09.

    "Eventually closed" is satisfied and the trader still could not have known
    the loss at 12:08 - which is why the predicate is against ENTRY, not exit.
    """
    current = trade("DIXON25MAY18000CE", at(12, 8), at(15, 9), -75)
    still_open = trade("DIXON25MAY17500CE", at(11, 1), at(15, 9), -1120)

    assert names(ctx(current, [still_open]).concluded_before_entry) == []


def test_shape_4_still_open_at_entry_closing_earlier():
    """
    2025-09-09. NIFTY 25000CE open 09:15->14:03. Current entered 09:26 - while
    the first was open - and exited 14:25. The prior closes FIRST, so an
    exit-ordered list puts it before the current trade and it reads as prior.
    """
    current = trade("NIFTY2590924950CE", at(9, 26), at(14, 25), -300)
    still_open = trade("NIFTY2590925000CE", at(9, 15), at(14, 3), -2509)

    assert names(ctx(current, [still_open]).concluded_before_entry) == []


def test_shape_5_prior_entered_after_the_current_trade():
    """
    2025-09-16. Current entered 10:16; the "prior" was entered at 10:17 - a
    minute LATER - and both closed 11:22. Adjacent strikes, same type, closed
    together: a spread or a scale-in, not a sequence.
    """
    current = trade("NIFTY2591625100PE", at(10, 16), at(11, 22), -150)
    later = trade("NIFTY2591625000PE", at(10, 17), at(11, 22), -956)

    assert names(ctx(current, [later]).concluded_before_entry) == []


# ── the relation's own edges ───────────────────────────────────────────────

def test_a_genuinely_earlier_trade_is_included():
    current = trade("NIFTY25APR24000CE", at(11, 0), at(11, 30), -500)
    earlier = trade("NIFTY25APR23900CE", at(9, 30), at(10, 0), -800)

    assert names(ctx(current, [earlier]).concluded_before_entry) == ["NIFTY25APR23900CE"]


def test_the_boundary_is_strict():
    """
    A position closed in the same instant the next was entered was not
    information the trader acted on. `<`, not `<=`.
    """
    current = trade("NIFTY25APR24000CE", at(11, 0), at(11, 30), -500)
    exact = trade("NIFTY25APR23900CE", at(10, 0), at(11, 0), -800)

    assert names(ctx(current, [exact]).concluded_before_entry) == []


def test_the_result_is_ordered_by_close():
    current = trade("NIFTY25APR24000CE", at(14, 0), at(14, 30), -500)
    a = trade("A25APR100CE", at(9, 20), at(11, 0), -100)
    b = trade("B25APR100CE", at(9, 30), at(10, 0), -200)

    assert names(ctx(current, [b, a]).concluded_before_entry) == [
        "B25APR100CE", "A25APR100CE"]


def test_a_missing_entry_time_yields_nothing_rather_than_guessing():
    current = trade("NIFTY25APR24000CE", at(11, 0), at(11, 30), -500)
    current.entry_time = None
    earlier = trade("NIFTY25APR23900CE", at(9, 30), at(10, 0), -800)

    assert ctx(current, [earlier]).concluded_before_entry == []


def test_session_trades_is_NOT_narrowed():
    """
    The migration is causal-detectors-only. Counting detectors must still see
    every trade that occurred, including a concurrent one.
    """
    current = trade("NIFTY25APR24000CE", at(11, 0), at(11, 30), -500)
    concurrent = trade("NIFTY25APR23900PE", at(11, 0), at(11, 30), -800)

    c = ctx(current, [concurrent])
    assert len(c.session_trades) == 1, "OCCURRED must be untouched"
    assert c.concluded_before_entry == [], "CONCLUDED must exclude it"


# ── the detectors that were fixed ──────────────────────────────────────────

def _loss_run(current, *priors):
    return ctx(current, list(priors))


def test_martingale_does_not_count_an_unconcluded_loss():
    """
    The live defect. A loss that closes AFTER this trade was entered cannot be
    part of the run that explains it.
    """
    current = trade("NIFTY25APR24000CE", at(9, 15), at(15, 0), -1000, qty=300)
    # both "losses" close long after the 09:15 entry they would explain
    late1 = trade("ALKEM25APR5100CE", at(9, 0), at(10, 43), -2000, qty=75)
    late2 = trade("DIXON25APR17000CE", at(9, 0), at(10, 32), -2000, qty=75)

    c = _loss_run(current, late1, late2)
    assert c.concluded_before_entry == []
    result = engine._detect_martingale_behaviour(c)
    assert not getattr(result, "fired", bool(result)), (
        "a run built from losses the trader could not see is not a run")


def test_martingale_still_fires_on_a_real_run():
    current = trade("NIFTY25APR24000CE", at(12, 0), at(12, 30), -1000, qty=300)
    l1 = trade("NIFTY25APR23900CE", at(9, 30), at(10, 0), -2000, qty=75)
    l2 = trade("NIFTY25APR23800CE", at(10, 10), at(11, 0), -2500, qty=75)

    c = _loss_run(current, l1, l2)
    assert len(c.concluded_before_entry) == 2
    result = engine._detect_martingale_behaviour(c)
    assert getattr(result, "fired", bool(result)), (
        "the real behaviour must still be caught")


def test_post_loss_recovery_bet_reads_the_same_relation():
    """Its latent defect: same shape, unaffected on this book by luck."""
    import inspect

    src = inspect.getsource(BehaviorEngine._detect_post_loss_recovery_bet)
    assert "ctx.concluded_before_entry" in src
    assert "for t in trades" not in src, "the unguarded pool must be gone"


# ── the detectors that must NOT have moved ─────────────────────────────────

def test_revenge_trade_uses_the_shared_relation_with_identical_semantics():
    """
    It was already right, spelled inline. Same predicate, one definition. Its
    firing set on the reference book is 182 before and after.
    """
    import inspect

    src = inspect.getsource(BehaviorEngine._detect_revenge_trade)
    assert "ctx.concluded_before_entry" in src
    assert "t.exit_time < ct.entry_time" not in src, "no second spelling"


def test_revenge_trade_still_fires_on_a_concluded_loss():
    current = trade("NIFTY25APR24000CE", at(10, 5), at(10, 30), -500, qty=150)
    loss = trade("NIFTY25APR23900CE", at(9, 30), at(10, 0), -3000, qty=75)

    result = engine._detect_revenge_trade(_loss_run(current, loss))
    assert result is not None


def test_rapid_reentry_keeps_its_own_zero_guard():
    """
    The `0 <= gap_min` was the ONLY protection and was incidental. It stays as
    belt-and-braces; removing it would leave the guarantee resting on the pool
    alone.
    """
    import inspect

    src = inspect.getsource(BehaviorEngine._detect_rapid_reentry)
    assert "ctx.concluded_before_entry" in src
    assert "0 <= gap_min" in src


@pytest.mark.parametrize("method", [
    "_detect_overtrading_burst", "_detect_fomo_entry",
    "_detect_same_symbol_obsession", "_detect_end_of_session_mis_panic",
    "_detect_win_rate_collapse", "_detect_strategy_breakdown",
])
def test_existence_detectors_were_not_migrated(method):
    """
    Counting is not a causal claim. Applying CONCLUDED to these was measured
    and rejected - it changes `overtrading_burst` 13 -> 2 on the reference book
    for a burst that genuinely happened.
    """
    import inspect

    src = inspect.getsource(getattr(BehaviorEngine, method))
    assert "concluded_before_entry" not in src, (
        f"{method} counts trades; it must keep reading session_trades")
