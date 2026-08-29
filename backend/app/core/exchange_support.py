"""
Which exchanges this system can actually reason about, and what is missing on
the ones it cannot.

    THIS MODULE IS NOT WIRED TO ANY DETECTOR.

The rule, stated once and enforced by `assert_supported`:

    Optimise for correct behaviour and explicit abstention, never for coverage.
    A wrong confident answer is worse than no answer.

Nothing here is a guess. Where a fact has not been established from a primary
source, the entry says so and the exchange is unsupported until it has been.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Support(str, Enum):
    #: Semantics verified AND the margin model validated against real broker
    #: margins. Calculations may proceed.
    SUPPORTED = "supported"

    #: Contract semantics readable, but the risk/margin model is NOT validated
    #: here. Identity is fine; capital requirement must abstain.
    IDENTITY_ONLY = "identity_only"

    #: Quantity or multiplier semantics not established from a primary source.
    #: Abstain from anything numeric.
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class ExchangeSupport:
    exchange: str
    support: Support
    #: What has actually been verified, with how.
    verified: tuple[str, ...] = ()
    #: What is NOT established. Each is a blocker, not a nice-to-have.
    unknown: tuple[str, ...] = ()
    note: str = ""


_NFO = ExchangeSupport(
    exchange="NFO",
    support=Support.SUPPORTED,
    verified=(
        "quantity semantics: Kite expands to UNITS, not lots (1 NIFTY lot -> qty 65)",
        "lot size: bhavcopy NewBrdLotQty, stated per contract per date",
        "contract multiplier: not applicable; quantities are already in units",
        "price quotation: rupees per unit of the underlying",
        "expiry: bhavcopy XpryDt / FininstrmActlXpryDt, stated, NOT computed "
        "(NIFTY 2026 monthlies are TUESDAYS, not the last Thursday)",
        "instrument classification: bhavcopy FinInstrmTp = IDF/IDO/STF/STO",
        "effective-date changes: bhavcopy is published per date and archived",
        "margin: validated against real broker margins, median error 4.0%",
    ),
    unknown=(
        "tick size is not in the bhavcopy; Kite's instruments dump carries it "
        "but only for currently-active contracts",
    ),
    note="The only exchange where a capital requirement may be computed.",
)

_NSE = ExchangeSupport(
    exchange="NSE",
    support=Support.IDENTITY_ONLY,
    verified=("cash equity: quantity is shares, no lot or multiplier",),
    unknown=(
        "short equity denominator: full notional is used today, but a short "
        "posts roughly 20% margin with unbounded loss, so notional is neither "
        "its capital nor its margin",
        "MTF funded fraction: see RISK_LAYER_ARCHITECTURE.md section 10",
    ),
    note="Identity is reliable. Capital requirement is only correct for LONG cash.",
)

_BFO = ExchangeSupport(
    exchange="BFO",
    support=Support.IDENTITY_ONLY,
    verified=("instrument identity is readable from the tradingsymbol",),
    unknown=(
        "BSE expiry rule: no sourced weekday rule was found. NSE's last-Thursday "
        "rule demonstrably does not apply, which is why F11 made it abstain",
        "BSE SPAN parameters: BSE/ICCL publishes its own; ours are NSE's",
        "whether the BSE bhavcopy carries the same exchange-stated fields",
        "margin model: never validated against a BFO position",
    ),
    note="SENSEX and BANKEX are traded. Identity only until the above are sourced.",
)

_CDS = ExchangeSupport(
    exchange="CDS",
    support=Support.UNSUPPORTED,
    unknown=(
        "quantity semantics: lots or units, not established",
        "contract multiplier: currency contracts quote per unit of foreign "
        "currency with a lot of 1000; the interaction with Kite's quantity is "
        "not established",
        "price quotation unit and tick value",
        "margin: currency derivatives have their own scan ranges, not ours",
    ),
    note="Not researched. Unsupported rather than assumed to behave like NFO.",
)

_MCX = ExchangeSupport(
    exchange="MCX",
    support=Support.UNSUPPORTED,
    verified=(
        "Kite's instruments dump reports lot_size = 1 for every MCX instrument",
    ),
    unknown=(
        "whether Kite's fill quantity for MCX is LOTS or UNITS, confirmed "
        "against a real fill rather than a forum post",
        "whether lot_size = 1 is a data gap or a deliberate encoding",
        "the multipliers themselves: app/services/mcx_contract_specs.py carries "
        "a hardcoded table sourced from Z-Connect, a third-party 2024 lot-size "
        "chart and mcxindia.com/products - NOT from MCX contract specifications "
        "read directly",
        "how multiplier revisions are dated (COPPER moved from 1 MT to 2500 kg "
        "in 2022; under effective dating, pre-2022 trades must keep the old "
        "value)",
        "tick value and price quotation unit per contract",
    ),
    note=(
        "MCX stays UNSUPPORTED until quantity and multiplier semantics are "
        "verified from MCX primary sources. The existing behaviour - abstain on "
        "unknown contracts - is correct and must not be loosened to improve "
        "coverage. A wrong multiplier is a 5000x error on ZINC."
    ),
)

SUPPORT: dict[str, ExchangeSupport] = {
    e.exchange: e for e in (_NFO, _NSE, _BFO, _CDS, _MCX)
}


def support_for(exchange: Optional[str]) -> ExchangeSupport:
    """Unknown exchanges are unsupported, not optimistically treated as NFO."""
    if not exchange:
        return ExchangeSupport(
            exchange="?", support=Support.UNSUPPORTED,
            unknown=("no exchange was supplied",),
            note="An absent exchange is not a default; it is missing information.")
    key = exchange.strip().upper()
    return SUPPORT.get(key, ExchangeSupport(
        exchange=key, support=Support.UNSUPPORTED,
        unknown=(f"{key} has never been researched",),
        note="Unrecognised exchange."))


def may_compute_capital(exchange: Optional[str]) -> bool:
    """
    The single gate for 'is a capital requirement meaningful here'.

    Only NFO passes today. Everything else abstains, including NSE cash, whose
    long-equity notional happens to be right but whose short side is not.
    """
    return support_for(exchange).support is Support.SUPPORTED


def abstention_reason(exchange: Optional[str]) -> Optional[str]:
    """A sentence fit to put in front of a user, or None when supported."""
    s = support_for(exchange)
    if s.support is Support.SUPPORTED:
        return None
    first = s.unknown[0] if s.unknown else "not established"
    return f"{s.exchange} is not supported for capital calculations: {first}"
