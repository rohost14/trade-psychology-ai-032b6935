"""
Contract specification — what a traded instrument actually is.

    THIS MODULE IS NOT WIRED TO ANY DETECTOR.

The engine's long-standing mistake is DERIVING contract facts that the exchange
PUBLISHES. Instrument type, underlying, expiry, strike, option type and lot size
are all stated per contract per date in the NSE F&O bhavcopy; inferring them
from a tradingsymbol produced F9, F11, F15 and F16, and inferring expiry from a
weekday rule is wrong outright — NIFTY's 2026 monthlies fall on Tuesdays.

The rule this module exists to enforce:

    Read what the exchange states. Derive only what it does not.
    When neither is possible, say UNAVAILABLE. Never guess.

EFFECTIVE DATING
----------------
A specification is valid from a date, not forever. Lot sizes change (NIFTY has
been 75 and is 65), MCX has revised contract sizes, and expiry rules move. A
historical trade must be valued with the specification in force on ITS OWN trade
date. Resolution therefore always takes a date, and there is no signature that
lets a caller forget to pass one.

Records are immutable. A revision is a new record with a later effective date;
it never rewrites an older one and never triggers recomputation of a closed
trade.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Optional


class SpecSource(str, Enum):
    """Where a fact came from. Never inferred silently."""

    #: Stated by the exchange for that contract on that date (bhavcopy).
    #: The only source that can be trusted for a historical trade.
    EXCHANGE = "exchange"

    #: Derived from the tradingsymbol. The live path often has nothing else —
    #: an order postback carries a symbol, not a contract specification.
    DERIVED = "derived"

    #: Nothing usable. The caller must abstain.
    UNAVAILABLE = "unavailable"


class Reliability(str, Enum):
    """
    How much weight a caller may put on the record.

    Deliberately three states and not a score. A number invites a threshold,
    and a threshold invites using a value that should have been refused.
    """
    AUTHORITATIVE = "authoritative"   # exchange-stated, for the right date
    DERIVED = "derived"               # parsed; usable, but not stated
    UNRELIABLE = "unreliable"         # do not compute with this


class Segment(str, Enum):
    INDEX_OPTION = "index_option"      # IDO
    INDEX_FUTURE = "index_future"      # IDF
    STOCK_OPTION = "stock_option"      # STO
    STOCK_FUTURE = "stock_future"      # STF
    EQUITY = "equity"
    UNKNOWN = "unknown"


#: Bhavcopy `FinInstrmTp` -> segment. Exchange-stated, so no parsing involved.
FIN_INSTRM_TP = {
    "IDO": Segment.INDEX_OPTION,
    "IDF": Segment.INDEX_FUTURE,
    "STO": Segment.STOCK_OPTION,
    "STF": Segment.STOCK_FUTURE,
}


@dataclass(frozen=True)
class ContractSpec:
    """
    One contract, as of one date. Frozen: a spec is a historical fact.

    `lot_size` is the value IN FORCE on `effective_date`, never today's.
    `contract_multiplier` is separate from lot size and is None for NSE F&O,
    where quantities already arrive in units. It exists for MCX, where it is
    not currently establishable from a primary source — see
    `exchange_support.py`.
    """
    tradingsymbol: str
    exchange: str
    effective_date: date

    segment: Segment
    underlying: Optional[str] = None
    expiry: Optional[date] = None
    strike: Optional[float] = None
    option_type: Optional[str] = None          # CE | PE
    lot_size: Optional[int] = None
    contract_multiplier: Optional[int] = None
    tick_size: Optional[float] = None
    #: MIS | NRML | MTF | CNC. Not a property of the contract but of how it is
    #: held, and it changes what capital means: an MTF position is part-funded
    #: by the broker, so its notional is NOT the trader's committed capital.
    product: Optional[str] = None

    source: SpecSource = SpecSource.UNAVAILABLE
    reliability: Reliability = Reliability.UNRELIABLE
    #: Why a record is unreliable or unavailable, for the message a user sees.
    note: Optional[str] = None

    @property
    def is_option(self) -> bool:
        return self.segment in (Segment.INDEX_OPTION, Segment.STOCK_OPTION)

    @property
    def is_future(self) -> bool:
        return self.segment in (Segment.INDEX_FUTURE, Segment.STOCK_FUTURE)

    @property
    def is_index(self) -> bool:
        return self.segment in (Segment.INDEX_OPTION, Segment.INDEX_FUTURE)

    @property
    def usable(self) -> bool:
        """
        Whether a calculation may proceed. The one gate callers should test.

        DERIVED counts as usable: the live path frequently has only a
        tradingsymbol, and refusing everything there would make the engine
        silent in real time. UNRELIABLE never counts.
        """
        return self.reliability is not Reliability.UNRELIABLE

    @staticmethod
    def unavailable(tradingsymbol: str, exchange: str, on: date,
                    note: str) -> "ContractSpec":
        """
        The explicit refusal. Preferred over any fabricated default.

        Note there is no zero here and no 'EQ' here. A missing lot size is not
        1, a missing segment is not equity, and a missing expiry is not today.
        Those substitutions are exactly how F9 and F11 happened.
        """
        return ContractSpec(
            tradingsymbol=tradingsymbol, exchange=exchange, effective_date=on,
            segment=Segment.UNKNOWN, source=SpecSource.UNAVAILABLE,
            reliability=Reliability.UNRELIABLE, note=note,
        )
