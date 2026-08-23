"""
What kind of number is "capital at risk"? It depends on the instrument.

THE PROBLEM

`estimate_capital_at_risk` returns a rupee figure for any trade, and that figure
means different things:

    long option    the premium paid — the MAXIMUM POSSIBLE LOSS
    short option   SPAN margin      — MARGIN POSTED; the loss is unbounded
    futures        SPAN margin      — MARGIN POSTED
    equity         full notional    — delivery value, not risk in any real sense

Nothing labelled which. So "this trade lost 80% of its capital at risk" reads as
one statement and is two: a long-option buyer having an ordinary bad day —
options expire worthless every week — and a short seller in serious trouble,
because 80% of posted margin is most of the way to a margin call with no floor
under it.

Any detector reasoning trade-relative has to know which it is holding. Without a
label, each one re-derives it, and the first that forgets ships a threshold that
is right for one class and wrong for three.

WHAT THIS ADDS

A name for the class and a name for what the denominator MEANS, carried
alongside the number. No thresholds: this module says what kind of quantity you
have, never whether it is too big.

SPREADS ARE NOT AN INSTRUMENT TYPE

A spread is a relationship between trades, not a property of one, so it cannot be
derived from a single `CompletedTrade`. `estimate_capital_at_risk` already warns
that hedged positions are over-estimated — the denominator is too large, so any
ratio against it is understated, which is a confident false negative rather than
a near miss. The caller knows about the hedge (`ctx.strategy_group`) and must
supply it; `SPREAD` exists here so that answer has somewhere to go.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class InstrumentClass(str, Enum):
    LONG_OPTION = "long_option"
    SHORT_OPTION = "short_option"
    FUTURES = "futures"
    EQUITY = "equity"
    #: Determined by the caller from the strategy group, never from one trade.
    SPREAD = "spread"
    UNKNOWN = "unknown"


class DenominatorKind(str, Enum):
    """
    What the capital-at-risk figure IS. The distinction the ratio depends on.
    """

    #: The most that could ever be lost. A 100% loss is possible and ordinary.
    LOSS_CEILING = "loss_ceiling"
    #: Margin posted to hold the position. Losses are NOT bounded by it, so
    #: losing a large fraction of it is a far more serious event.
    MARGIN_POSTED = "margin_posted"
    #: Full contract value. Not a risk measure; a ratio against it is close to
    #: meaningless for anything but delivery equity.
    NOTIONAL = "notional"
    #: Known to be wrong for this trade — over-estimated on a hedged position.
    UNRELIABLE = "unreliable"


#: How a class should be spoken about, when an alert has to name its denominator.
_LABELS = {
    InstrumentClass.LONG_OPTION: "the premium you paid",
    InstrumentClass.SHORT_OPTION: "the margin you posted",
    InstrumentClass.FUTURES: "the margin you posted",
    InstrumentClass.EQUITY: "the value of the position",
    InstrumentClass.SPREAD: "the margin for this spread",
    InstrumentClass.UNKNOWN: "the capital at risk",
}

_KINDS = {
    InstrumentClass.LONG_OPTION: DenominatorKind.LOSS_CEILING,
    InstrumentClass.SHORT_OPTION: DenominatorKind.MARGIN_POSTED,
    InstrumentClass.FUTURES: DenominatorKind.MARGIN_POSTED,
    InstrumentClass.EQUITY: DenominatorKind.NOTIONAL,
    InstrumentClass.SPREAD: DenominatorKind.UNRELIABLE,
    InstrumentClass.UNKNOWN: DenominatorKind.NOTIONAL,
}


@dataclass(frozen=True)
class RiskBasis:
    """A capital-at-risk figure that knows what kind of figure it is."""

    amount: float
    instrument: InstrumentClass
    kind: DenominatorKind
    label: str

    @property
    def is_comparable(self) -> bool:
        """
        May a ratio against this denominator be compared to a threshold at all?

        False for a spread, where the denominator is known to be over-estimated,
        and for an unclassifiable instrument. In both cases the honest response is
        to abstain rather than to report a ratio that is quietly wrong in a known
        direction.
        """
        return self.kind not in (DenominatorKind.UNRELIABLE,)


def classify(instrument_type: Optional[str], direction: Optional[str],
             is_spread: bool = False) -> InstrumentClass:
    """
    The class of one trade. `is_spread` comes from the caller's strategy group.
    """
    if is_spread:
        return InstrumentClass.SPREAD

    itype = (instrument_type or "").upper()
    side = (direction or "").upper()

    if itype in ("CE", "PE"):
        return (InstrumentClass.LONG_OPTION if side == "LONG"
                else InstrumentClass.SHORT_OPTION)
    if itype == "FUT":
        return InstrumentClass.FUTURES
    if itype == "EQ":
        return InstrumentClass.EQUITY
    return InstrumentClass.UNKNOWN


def risk_basis(instrument_type: Optional[str], tradingsymbol: str,
               direction: Optional[str], avg_entry_price: float,
               total_quantity: int, is_spread: bool = False) -> RiskBasis:
    """
    Capital at risk, labelled.

    The amount is exactly what `estimate_capital_at_risk` has always returned —
    this adds the label, never a different number, so nothing that reads the
    figure changes.
    """
    from app.core.trading_defaults import estimate_capital_at_risk

    amount = estimate_capital_at_risk(
        instrument_type, tradingsymbol, direction or "LONG",
        avg_entry_price, total_quantity,
    )
    cls = classify(instrument_type, direction, is_spread)
    return RiskBasis(
        amount=float(amount),
        instrument=cls,
        kind=_KINDS[cls],
        label=_LABELS[cls],
    )
