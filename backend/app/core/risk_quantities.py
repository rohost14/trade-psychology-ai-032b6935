"""
The one authoritative risk interface.

    THIS MODULE IS NOT WIRED TO ANY DETECTOR.

Three quantities, kept apart on purpose, because collapsing them is the root of
F3, F17 and the martingale comparability problem:

    A. ENTRY VALUE          price * quantity * multiplier
    B. P&L                  (exit - entry) * quantity * multiplier, RAW
    C. CAPITAL REQUIREMENT  what the account actually had to put up

Plus one flag, `DenominatorKind`, for whether the loss is bounded by C.

WHY A TYPE AND NOT THREE FLOATS
-------------------------------
A detector that wants "how big was this trade" and a detector that wants "how
much of my account is committed" both used to call one function and get one
number. That is how a writer's RECEIVED premium became their "capital at risk".

So the quantities are not interchangeable floats here. `entry_value` and
`capital_requirement` are different types, `Money` and `Capital`, and Python
will not let you add or compare them. Getting the wrong one is a TypeError at
the point of misuse rather than a wrong alert six months later.

    "Maximum theoretical loss" is deliberately NOT a quantity. For a long option
    it equals A; for a short option or a future it is unbounded, so it can be
    neither a denominator nor a displayed figure. Its whole information content
    is the bounded/unbounded flag, which already exists.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from app.core.contract_spec import ContractSpec, Reliability, Segment
from app.core.exchange_support import abstention_reason, may_compute_capital


class MarginSource(str, Enum):
    """Provenance. There is no default and no silent fallback."""
    BROKER = "broker"            # Kite /margins/orders, captured at order time
    COMPUTED = "computed"        # reconstructed by margin_model
    UNAVAILABLE = "unavailable"  # abstain


class DenominatorKind(str, Enum):
    LOSS_CEILING = "loss_ceiling"      # loss bounded by what was committed
    MARGIN_POSTED = "margin_posted"    # loss NOT bounded by what was committed
    NOTIONAL = "notional"              # equity
    UNRELIABLE = "unreliable"          # abstain


@dataclass(frozen=True)
class Money:
    """
    A trade-scale amount: premium, notional, P&L. NOT capital committed.

    Comparable only to other `Money` of a comparable basis (see `Comparability`).
    """
    amount: float
    label: str


@dataclass(frozen=True)
class Capital:
    """
    Capital the account had to put up. NOT the premium, and NOT interchangeable
    with `Money` — that is the whole point of the separate type.

    Always carries provenance. A `COMPUTED` value must never be described to a
    user as the margin the broker blocked: measured error is +5-7% on short
    options and sub-1% on futures and spreads.
    """
    amount: Optional[float]
    source: MarginSource
    #: What the number covers. Never collapse these into one field.
    scope: str = "position"      # position | order | portfolio | strategy
    note: Optional[str] = None

    @property
    def available(self) -> bool:
        return self.amount is not None and self.source is not MarginSource.UNAVAILABLE

    @staticmethod
    def unavailable(note: str) -> "Capital":
        return Capital(amount=None, source=MarginSource.UNAVAILABLE, note=note)


@dataclass(frozen=True)
class RiskQuantities:
    """
    Everything a detector may need about one position's size and cost.

    Ask for the quantity you actually want. `entry_value` will never silently
    stand in for `capital_requirement`.
    """
    entry_value: Money
    pnl: Optional[Money]
    capital_requirement: Capital
    denominator_kind: DenominatorKind
    reliability: Reliability
    spec: ContractSpec

    @property
    def loss_is_bounded(self) -> bool:
        return self.denominator_kind is DenominatorKind.LOSS_CEILING

    @property
    def usable_for_capital_rules(self) -> bool:
        """Gate for excess_exposure, constitution_violation and the like."""
        return (self.capital_requirement.available
                and self.reliability is not Reliability.UNRELIABLE)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

def quantities_for(
    spec: ContractSpec,
    direction: str,
    quantity: int,
    entry_price: float,
    exit_price: Optional[float] = None,
    margin: Optional[Capital] = None,
) -> RiskQuantities:
    """
    Build the three quantities for one leg.

    `direction` is exposure, not sentiment. LONG = bought exposure, SHORT =
    sold exposure. A long PE is not bearish behaviour and a short CE is not a
    hedge; whether anything is a hedge is a property of the portfolio, and the
    margin model answers it by scanning legs together rather than classifying
    them.

    `margin` is passed in rather than computed here. This module does not know
    how to compute a margin, and it must not: capital for a hedged book is a
    PORTFOLIO quantity, so a per-leg function is the wrong place to produce it.
    Callers supply BROKER margin when they captured it and COMPUTED margin
    otherwise; supplying neither yields an explicit abstention.
    """
    mult = spec.contract_multiplier or 1
    qty = abs(int(quantity or 0))
    is_long = (direction or "").upper() == "LONG"

    entry_value = Money(
        amount=float(entry_price or 0.0) * qty * mult,
        label=_entry_label(spec, is_long),
    )

    pnl = None
    if exit_price is not None:
        # RAW only. No brokerage, STT or tax, ever.
        sign = 1.0 if is_long else -1.0
        pnl = Money(
            amount=(float(exit_price) - float(entry_price or 0.0)) * qty * mult * sign,
            label="realised P&L (raw)",
        )

    kind = _denominator_kind(spec, is_long)
    capital = _capital_for(spec, is_long, entry_value, margin)

    reliability = spec.reliability
    if kind is DenominatorKind.UNRELIABLE:
        reliability = Reliability.UNRELIABLE

    return RiskQuantities(
        entry_value=entry_value, pnl=pnl, capital_requirement=capital,
        denominator_kind=kind, reliability=reliability, spec=spec,
    )


def quantities_for_trade(trade, margin: Optional[Capital] = None,
                         as_of=None) -> RiskQuantities:
    """
    The canonical entry point for a detector holding a CompletedTrade.

    F17. Detectors used to call `estimate_capital_at_risk` directly, which meant
    `risk_basis`, `is_comparable` and every UNRELIABLE marking were unreachable
    for them - the safety layer existed and was not consulted. Everything now
    goes through here so the answer arrives with its provenance and reliability
    attached, and a caller cannot obtain a bare float that hides either.

    Resolution is DERIVED, not exchange-stated: a detector runs on the live path
    where only a tradingsymbol exists. That is recorded on the spec, not hidden.
    """
    from datetime import date as _date
    from app.services.instrument_master import resolve

    on = as_of or getattr(trade, "exit_time", None) or getattr(trade, "entry_time", None)
    on = on.date() if hasattr(on, "date") else (on or _date.today())

    spec = resolve(getattr(trade, "tradingsymbol", "") or "",
                   getattr(trade, "exchange", "") or "", on)
    product = getattr(trade, "product", None)
    if product and spec.usable:
        spec = ContractSpec(**{**spec.__dict__, "product": product})

    return quantities_for(
        spec,
        direction=getattr(trade, "direction", None) or "LONG",
        quantity=int(getattr(trade, "total_quantity", 0) or 0),
        entry_price=float(getattr(trade, "avg_entry_price", 0) or 0),
        margin=margin,
    )


def _entry_label(spec: ContractSpec, is_long: bool) -> str:
    if spec.is_option:
        return "premium paid" if is_long else "premium received"
    if spec.is_future:
        return "contract notional"
    if spec.segment is Segment.EQUITY:
        return "notional"
    return "entry value"


def _denominator_kind(spec: ContractSpec, is_long: bool) -> DenominatorKind:
    if spec.reliability is Reliability.UNRELIABLE or spec.segment is Segment.UNKNOWN:
        return DenominatorKind.UNRELIABLE
    if spec.is_option:
        return DenominatorKind.LOSS_CEILING if is_long else DenominatorKind.MARGIN_POSTED
    if spec.is_future:
        return DenominatorKind.MARGIN_POSTED
    if spec.segment is Segment.EQUITY:
        # Long cash equity: notional is both the outlay and the loss ceiling.
        # SHORT equity is NOT the same thing and is not resolved - it posts
        # roughly 20% margin against an unbounded loss, so notional is neither
        # its capital nor its margin. Refusing beats a number we cannot defend.
        return DenominatorKind.NOTIONAL if is_long else DenominatorKind.UNRELIABLE
    return DenominatorKind.UNRELIABLE


def _capital_for(spec: ContractSpec, is_long: bool, entry_value: Money,
                 margin: Optional[Capital]) -> Capital:
    """
    Capital splits into two kinds of case, and only one of them needs a margin
    model at all.

    DEFINITIONAL - a bought option and long cash equity. The money left the
    account when the trade was put on and nothing further is blocked, so the
    capital IS the entry value. No scan range, no volatility, no exchange
    parameters. This holds on any exchange whose contract multiplier we know,
    including MCX, which is why the exchange-support gate is NOT applied here:
    a bought GOLDM call costs its premium regardless of MCX's scan ranges being
    unsourced.

    REQUIRES MARGIN - short options, futures, short equity. There is no way to
    derive these from the trade alone, and a percentage-of-notional stand-in is
    what F3 was. Verified: the old constant ran -35% to +158% across a strike
    ladder, and a price-scan floor understates a high-volatility stock future by
    about 21% (CDSL scans at 18.9%, not the 14.2% floor). Understating committed
    capital is the dangerous direction, so absent a real figure this abstains.
    """
    if spec.reliability is Reliability.UNRELIABLE:
        return Capital.unavailable(spec.note or "contract specification unavailable")

    if spec.is_option and is_long:
        return Capital(amount=entry_value.amount, source=MarginSource.COMPUTED,
                       scope="position", note="premium paid in full")

    if spec.segment is Segment.EQUITY and is_long:
        # MTF is part-funded by the broker, so the notional is NOT the trader's
        # committed capital. Kite exposes the product tag but no funded amount
        # or financing figure, and inventing a leverage ratio is exactly what
        # this layer exists to prevent. Abstain, keeping MTF identified.
        if (spec.product or "").upper() == "MTF":
            return Capital.unavailable(
                "MTF is part-funded by the broker and no funded-amount or "
                "financing figure is available, so committed capital cannot be "
                "determined - full notional would overstate it")
        return Capital(amount=entry_value.amount, source=MarginSource.COMPUTED,
                       scope="position", note="cash delivery value")

    # Everything else is margin. A supplied figure wins; BROKER outranks
    # COMPUTED and the caller decides which it passes.
    if margin is not None and margin.available:
        return margin

    if not may_compute_capital(spec.exchange):
        return Capital.unavailable(
            abstention_reason(spec.exchange) or "unsupported exchange")
    return Capital.unavailable(
        "a short option, future or short equity position requires a margin "
        "figure, which must come from the broker or the margin model - it "
        "cannot be derived from the trade")


# ---------------------------------------------------------------------------
# Comparability - a refusal is better than a false comparison
# ---------------------------------------------------------------------------

class Comparability(str, Enum):
    COMPARABLE = "comparable"
    NOT_COMPARABLE = "not_comparable"


def compare_sizes(a: RiskQuantities, b: RiskQuantities) -> tuple[Comparability, str]:
    """
    May "trade B was twice trade A" be said about these two?

    The bar is deliberately high, because the failure this prevents is silent.
    Rs 10,000 of premium against Rs 20,000 of premium is a real doubling. Rs
    10,000 of premium against Rs 2,00,000 of futures margin is not a twentyfold
    increase in anything; it is two different quantities being divided.

    Returns the verdict and a reason fit to log or show.
    """
    if a.reliability is Reliability.UNRELIABLE or b.reliability is Reliability.UNRELIABLE:
        return Comparability.NOT_COMPARABLE, "one side has no reliable specification"

    if a.denominator_kind is not b.denominator_kind:
        return Comparability.NOT_COMPARABLE, (
            f"different denominator kinds ({a.denominator_kind.value} vs "
            f"{b.denominator_kind.value}); premium and margin are not the same "
            f"quantity")

    if a.spec.segment is not b.spec.segment:
        return Comparability.NOT_COMPARABLE, (
            f"different instrument segments ({a.spec.segment.value} vs "
            f"{b.spec.segment.value})")

    if a.entry_value.label != b.entry_value.label:
        return Comparability.NOT_COMPARABLE, (
            f"different entry-value meanings ({a.entry_value.label} vs "
            f"{b.entry_value.label})")

    return Comparability.COMPARABLE, "same segment, direction sense and denominator kind"


def size_ratio(a: RiskQuantities, b: RiskQuantities) -> Optional[float]:
    """
    `b` relative to `a`, or **None** when the two must not be compared.

    None is a first-class answer here. A detector that treats it as 1.0, or as
    0, has reintroduced exactly the bug this function exists to prevent.
    """
    verdict, _ = compare_sizes(a, b)
    if verdict is not Comparability.COMPARABLE:
        return None
    if not a.entry_value.amount:
        return None
    return b.entry_value.amount / a.entry_value.amount
