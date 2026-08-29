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

        FIXED 2026-08-29 (Phase 1, F8). The second half of that promise was not
        implemented: the check was `kind not in (UNRELIABLE,)`, and an
        unclassifiable instrument is given `NOTIONAL`, so it read as comparable.
        Three detectors — revenge_trade, martingale_behaviour and
        adding_to_adverse_position — relied on the documented behaviour.

        `parse_symbol` returns `EQ` for anything it cannot read, so the UNKNOWN
        class is reached only when `instrument_type` is genuinely absent. That is
        exactly the case the docstring meant.
        """
        return (self.kind is not DenominatorKind.UNRELIABLE
                and self.instrument is not InstrumentClass.UNKNOWN)


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
               total_quantity: int, is_spread: bool = False,
               exchange: Optional[str] = None) -> RiskBasis:
    """
    Capital at risk, labelled.

    The amount is exactly what `estimate_capital_at_risk` has always returned —
    this adds the label, never a different number, so nothing that reads the
    figure changes.
    """
    from app.core.trading_defaults import estimate_capital_at_risk

    amount = estimate_capital_at_risk(
        instrument_type, tradingsymbol, direction or "LONG",
        avg_entry_price, total_quantity, exchange,
    )
    cls = classify(instrument_type, direction, is_spread)
    kind = _KINDS[cls]

    # An MCX contract we have no multiplier for (Phase 1, F7). The quantity is
    # in lots and we cannot convert it, so `amount` is understated by an unknown
    # factor — known to be wrong, in a known direction, which is exactly what
    # UNRELIABLE means. Guessing 1 is how the pre-fix code produced a ZINC
    # denominator 5000x too small.
    if exchange and (exchange or "").upper() in ("MCX", "CDS"):
        from app.services.mcx_contract_specs import get_lot_multiplier_or_none
        if get_lot_multiplier_or_none(exchange, tradingsymbol or "") is None:
            kind = DenominatorKind.UNRELIABLE

    # A short option whose strike we cannot read (Phase 1, F3). Its denominator
    # falls back to a percentage of the premium received, which is known to be
    # ~200x too small. Same reasoning as the MCX case above: known to be wrong,
    # in a known direction, so abstain rather than report it.
    if cls is InstrumentClass.SHORT_OPTION:
        from app.core.trading_defaults import _option_contract_notional
        if _option_contract_notional(tradingsymbol or "", total_quantity,
                                     exchange) is None:
            kind = DenominatorKind.UNRELIABLE

    return RiskBasis(
        amount=float(amount),
        instrument=cls,
        kind=kind,
        label=_LABELS[cls],
    )
