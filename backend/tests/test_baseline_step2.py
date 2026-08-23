"""
Step 2: harmful-sequence exclusion, and two distributions recorded but not active.

WHY THE EXCLUSION MATTERS

`reentry_after_loss_p25` is the fast end of a trader's own re-entry pace, and it
feeds `revenge_window_caution_min`. Learning it from every re-entry — including
the ones that were themselves harmful — drags "normal" downward until nothing
looks fast any more. The detector's own subject matter teaches it to stop
noticing.

WHERE THE EXCLUSION COMES FROM, AND WHERE IT MUST NOT

Defined from the trade record alone: a loss, a re-entry, and that re-entry also
closed at a loss. No alert, no threshold, no detector verdict.

Reading our own `RiskAlert`s instead would build
`detector → RiskAlert → baseline → detector`. The baseline would then depend on
what the detector previously decided, so a threshold change would silently
rewrite the history it is measured against, and a detector that mis-fired once
would go on teaching itself that it was right. `test_the_exclusion_does_not_read_alerts`
holds that line.

WHY THE DISTRIBUTIONS ARE INERT

`own_loss_size` and `own_position_risk` record what the trader did. Which
percentile marks "unusual" is P1, an unapproved decision, so nothing reads them.
Storing the shape means that decision can later be argued from this trader's real
distribution instead of guessed — and audited afterwards.
"""
from datetime import timedelta
from decimal import Decimal

import pytest

from app.core import session_facts
from app.models.completed_trade import CompletedTrade
from app.services.baseline_service import _distribution, compute_baseline
from tests.helpers import now_utc


async def _trade(db, broker, pnl, *, day, entry_min, exit_min, qty=50, price=200):
    """
    One round-trip on a given day.

    entry and exit are given explicitly because the gap baseline only records a
    re-entry when the NEXT trade's entry falls after the previous trade's exit —
    a fixture that overlaps them produces no observations at all, which is a
    silent way for these tests to prove nothing.
    """
    base = now_utc().replace(hour=6, minute=0, second=0, microsecond=0) - timedelta(days=day)
    entry_at = base + timedelta(minutes=entry_min)
    exit_at = base + timedelta(minutes=exit_min)
    ct = CompletedTrade(
        broker_account_id=broker.id,
        tradingsymbol="NIFTY25SEP24000CE",
        exchange="NFO",
        instrument_type="CE",
        product="MIS",
        direction="LONG",
        total_quantity=qty,
        num_entries=1,
        num_exits=1,
        avg_entry_price=Decimal(str(price)),
        avg_exit_price=Decimal(str(round(price + pnl / qty, 2))),
        realized_pnl=Decimal(str(pnl)),
        entry_time=entry_at,
        exit_time=exit_at,
        duration_minutes=max(1, exit_min - entry_min),
        status="closed",
    )
    db.add(ct)
    await db.flush()
    return ct


# ── the recorded distributions ─────────────────────────────────────────────


def test_a_distribution_records_shape_not_a_threshold():
    d = _distribution([100.0, 200.0, 300.0, 400.0, 500.0], "rupees")
    assert d["active"] is False, "a distribution must not present itself as active"
    assert "P1 unresolved" in d["provenance"]
    assert set(d["percentiles"]) == {"p25", "p50", "p60", "p75", "p85", "p95"}


def test_it_carries_counts_so_the_exclusion_is_auditable():
    """
    Note the spread. With identical values MAD is 0 and `is_outlier` returns
    False for everything — a perfectly consistent trader excludes nothing, which
    is correct and is also how a fixture can accidentally prove nothing.
    """
    values = [100.0 + i * 7 for i in range(20)] + [999999.0]
    d = _distribution(values, "rupees")
    assert d["n"] == 21
    assert d["n_learned"] < d["n"], "the outlier should not have trained it"
    assert d["n_excluded"] == d["n"] - d["n_learned"]


def test_it_uses_median_and_mad_not_mean():
    """One catastrophe must not redefine what is typical."""
    values = [100.0 + i * 7 for i in range(20)] + [500000.0]
    d = _distribution(values, "rupees")
    assert d["median"] < 200.0, "a mean would have been dragged into the thousands"


def test_an_empty_distribution_is_none_not_zero():
    assert _distribution([], "rupees") is None


@pytest.mark.asyncio
async def test_the_distributions_are_computed_from_real_trades(db, broker):
    for i in range(12):
        await _trade(db, broker, -1000 - i * 50, day=i + 1,
                     entry_min=20, exit_min=30)
    baseline = await compute_baseline(broker.id, db)
    metrics = baseline["metrics"]

    loss = metrics["own_loss_size"]
    assert loss is not None and loss["n"] == 12
    assert loss["unit"] == "losing trades, rupees"
    assert loss["active"] is False

    risk = metrics["own_position_risk"]
    assert risk is not None and risk["n"] == 12, (
        "capital at risk needs no declared capital and must be recorded for "
        "every trader"
    )


@pytest.mark.asyncio
async def test_nothing_consumes_the_new_distributions_yet(db, broker):
    """
    P1 is unapproved. If a threshold starts resolving from these, it happened
    without the decision being made.

    Compares two profiles that differ ONLY by the new keys — comparing against
    cold start would differ for unrelated reasons and prove nothing.
    """
    from app.core.threshold_resolution import resolve_thresholds

    shared = {"version": 2, "metrics": {"daily_trades_p75": {"value": 8.0,
                                                             "confidence": 1.0, "n": 60}}}

    class _Without:
        detected_patterns = {"baseline": shared}
        trading_capital = None

    with_dist = {"version": 2, "metrics": dict(shared["metrics"])}
    with_dist["metrics"]["own_loss_size"] = {
        "median": 5000.0, "percentiles": {"p60": 9000.0}, "active": False,
    }
    with_dist["metrics"]["own_position_risk"] = {"median": 20000.0, "active": False}

    class _With:
        detected_patterns = {"baseline": with_dist}
        trading_capital = None

    assert resolve_thresholds(_Without()).values == resolve_thresholds(_With()).values, (
        "a recorded distribution moved a threshold; P1 has not been approved"
    )


# ── harmful-sequence exclusion ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_losing_reentry_does_not_train_the_gap_baseline(db, broker):
    """
    Twelve calm days with slow re-entries, then a run of fast re-entries that
    themselves lost. Without the exclusion the fast harmful gaps pull p25 down
    and the detector stops noticing them.
    """
    day = 1
    for _ in range(12):
        await _trade(db, broker, -800, day=day, entry_min=10, exit_min=30)
        # slow re-entry, and it won
        await _trade(db, broker, 600, day=day, entry_min=75, exit_min=95)
        day += 1
    for _ in range(6):
        await _trade(db, broker, -900, day=day, entry_min=10, exit_min=30)
        # fast re-entry, and it lost — the harmful sequence
        await _trade(db, broker, -900, day=day, entry_min=31, exit_min=40)
        day += 1

    baseline = await compute_baseline(broker.id, db)
    gap = baseline["metrics"]["reentry_after_loss_p25"]

    assert gap is not None
    assert gap["n_excluded_harmful"] >= 6, (
        "the losing re-entries were allowed to train the gap baseline"
    )


@pytest.mark.asyncio
async def test_a_profitable_reentry_still_trains_it(db, broker):
    """
    The exclusion is narrow on purpose. A fast re-entry that worked out is part
    of how this trader normally trades, and removing it would bias the baseline
    the other way.
    """
    day = 1
    for _ in range(14):
        await _trade(db, broker, -800, day=day, entry_min=10, exit_min=30)
        # fast re-entry, and it worked
        await _trade(db, broker, 700, day=day, entry_min=31, exit_min=45)
        day += 1

    baseline = await compute_baseline(broker.id, db)
    gap = baseline["metrics"]["reentry_after_loss_p25"]

    assert gap is not None
    assert gap["n_excluded_harmful"] == 0


def test_the_exclusion_does_not_read_alerts():
    """
    The circularity guard, asserted rather than promised. If baseline_service
    starts reading RiskAlert, the baseline depends on what the detector decided
    and a threshold change rewrites the history it is judged against.
    """
    import inspect

    import app.services.baseline_service as mod

    src = inspect.getsource(mod)
    assert "RiskAlert" not in src, (
        "baseline_service reads RiskAlert - that is detector -> alert -> baseline "
        "-> detector. Derive harmful sequences from CompletedTrade instead."
    )
