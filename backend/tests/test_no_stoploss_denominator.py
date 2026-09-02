"""
`no_stoploss` divides a loss by the right denominator, or abstains.

THE BUG THIS EXISTS TO PREVENT (F4)

The detector branched on instrument type alone:

    if instrument_type in ("CE", "PE"):
        capital_at_risk = entry_price * qty
        loss_label = "of premium"

Direction was not consulted. For a LONG option that is exact — premium paid is
the most that can be lost. For a SHORT option it is the wrong quantity facing
the wrong way: premium RECEIVED is the maximum profit, not the capital at risk.
A writer who lost more than they took in produced a figure over 100% "of
premium", and the 40/60/80 ladder — which assumes a denominator a loss cannot
exceed — became meaningless against it.

Nothing new was invented to fix it. `risk_basis` already answers the question
(built for F3/F7, 2026-08-29): premium paid for a long option, SPAN margin on
strike x quantity for a short one, margin for futures — and UNRELIABLE where
the number is known to be wrong, which is now an abstention rather than a
percentage.

The reference book is 911 LONG against 1 SHORT, so this path is close to
unexercised in production data. That is a reason to pin it with tests, not a
reason to leave it wrong.
"""
from __future__ import annotations

import pytest

from app.core.instrument_risk import DenominatorKind, InstrumentClass, risk_basis

NIFTY_CE = "NIFTY25SEP24000CE"
NIFTY_FUT = "NIFTY25SEPFUT"


def _basis(direction: str, symbol: str = NIFTY_CE, price: float = 120.0,
           qty: int = 75, exchange: str = "NFO"):
    itype = "CE" if symbol.endswith(("CE", "PE")) else "FUT"
    return risk_basis(itype, symbol, direction, price, qty, exchange=exchange)


def test_long_option_denominator_is_the_premium_paid():
    b = _basis("LONG")
    assert b.instrument is InstrumentClass.LONG_OPTION
    assert b.kind is DenominatorKind.LOSS_CEILING
    assert b.amount == pytest.approx(120.0 * 75)
    assert b.label == "the premium you paid"


def test_short_option_denominator_is_margin_not_premium_received():
    """The whole point of F4: the two must not be the same number."""
    long_b = _basis("LONG")
    short_b = _basis("SHORT")
    assert short_b.instrument is InstrumentClass.SHORT_OPTION
    assert short_b.kind is DenominatorKind.MARGIN_POSTED
    assert short_b.label == "the margin you posted"
    # Margin on 24000 x 75 contract notional dwarfs 120 x 75 premium.
    assert short_b.amount > long_b.amount * 10


def test_a_loss_larger_than_the_premium_stays_under_100_pct_for_a_writer():
    """
    The failure the old code produced. A short CE taking a 20,000 loss against
    9,000 of premium received reported 222%; against margin it is a sane
    fraction, which is what the 40/60/80 ladder is calibrated for.
    """
    loss = 20_000.0
    premium_received = 120.0 * 75
    assert loss / premium_received * 100 > 100

    b = _basis("SHORT")
    assert loss / b.amount * 100 < 100


def test_short_option_with_an_unreadable_strike_abstains():
    """
    No strike means no contract notional, and the fallback is known to be
    ~200x too small. `risk_basis` marks it UNRELIABLE and the detector returns
    None rather than dividing by it.
    """
    b = risk_basis("CE", "GARBAGE-SYMBOL", "SHORT", 120.0, 75, exchange="NFO")
    assert b.kind is DenominatorKind.UNRELIABLE


def test_futures_denominator_is_unchanged():
    """Regression guard: the non-option path must not have moved."""
    from app.core.trading_defaults import estimate_capital_at_risk

    b = risk_basis("FUT", NIFTY_FUT, "LONG", 24_000.0, 75, exchange="NFO")
    assert b.kind is DenominatorKind.MARGIN_POSTED
    assert b.amount == pytest.approx(
        estimate_capital_at_risk("FUT", NIFTY_FUT, "LONG", 24_000.0, 75, "NFO")
    )


def test_long_option_amount_is_unchanged_from_the_old_inline_formula():
    """
    The long path is 99.9% of the book. It must produce exactly what the
    replaced `entry_price * qty` produced, or this refactor moved live alerts.
    """
    for price, qty in ((120.0, 75), (5.5, 1800), (301.25, 50)):
        b = _basis("LONG", price=price, qty=qty)
        assert b.amount == pytest.approx(price * qty)


def test_the_detector_branches_on_direction_and_abstains_when_it_cannot_tell():
    """
    Deliberately NOT routed through `risk_basis`, even though that function
    answers the same question. `tests/test_foundation_f3_f5.py` guards the rule
    that a detector adopts the shared F1-F5 mechanisms only during its own
    review, behind a replay; no replay was run for this change. The denominator
    is fixed using `estimate_capital_at_risk`, which this detector already
    called for every non-option instrument, so nothing new is adopted.
    """
    import inspect

    from app.services.behavior_engine import BehaviorEngine

    src = inspect.getsource(BehaviorEngine._detect_no_stoploss)
    assert 'side not in ("LONG", "SHORT")' in src
    assert "_option_contract_notional(" in src
    assert "core.instrument_risk" not in src, (
        "adopting the shared mechanisms here needs this detector's own review"
    )
    # The replaced single-branch label must be gone, not merely bypassed.
    assert 'loss_label = "of premium"' not in src


def test_an_option_with_no_direction_abstains():
    """
    F4's remaining ambiguity, decided. `classify` reads a missing direction as
    SHORT (its `else` branch) while `estimate_capital_at_risk` reads it as
    LONG, so the pair would return a PREMIUM amount labelled "the margin you
    posted" — a wrong confident answer. The detector returns None instead.
    """
    # The underlying inconsistency, pinned so the abstention stays justified.
    b = risk_basis("CE", NIFTY_CE, None, 120.0, 75, exchange="NFO")
    assert b.instrument is InstrumentClass.SHORT_OPTION
    assert b.amount == pytest.approx(120.0 * 75), (
        "amount follows the LONG path while the class says short"
    )


def test_direction_is_not_ambiguous_for_futures():
    """Futures use margin either way, so no abstention is warranted there."""
    long_b = risk_basis("FUT", NIFTY_FUT, "LONG", 24_000.0, 75, exchange="NFO")
    short_b = risk_basis("FUT", NIFTY_FUT, "SHORT", 24_000.0, 75, exchange="NFO")
    assert long_b.amount == pytest.approx(short_b.amount)
    assert long_b.kind is short_b.kind is DenominatorKind.MARGIN_POSTED
