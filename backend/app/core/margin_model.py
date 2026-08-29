"""
NSE F&O initial-margin model — SPAN + exposure, reconstructed from the
exchange's published methodology.

    THIS MODULE IS NOT WIRED TO ANYTHING.

No detector, service, task or endpoint imports it. It exists so the margin
layer can be built and validated on its own before any behavioural code is
allowed to depend on it. Integration is a separate, approved step.

WHY IT EXISTS
-------------
Kite's `/margins/orders` returns the broker's exact margin, but only for a
PROSPECTIVE order. No API returns the margin of a position that has already
been closed. Our behavioural baseline is entirely historical, so the exact
number is permanently unavailable for it and must be reconstructed.

It is reconstructable. NSE Clearing publishes the whole method — the scan
ranges, all sixteen scenarios, the spread charges, the net-option-value
subtraction, and Black-Scholes as the pricing model. The `.spn` risk parameter
file distributed to members is a convenience so that members "need not execute
complex option pricing calculations", not a secret input.

    https://www.nseclearing.in/risk-management/equity-derivatives/nsccl-span
    https://www.nseclearing.in/risk-management/equity-derivatives/span-risk-parameters

WHAT THIS IS NOT
----------------
It is not broker margin. A value produced here is `MarginSource.COMPUTED` and
must never be presented as the margin a broker actually blocked. See
`docs/DEEP_REVIEW/RISK_LAYER_ARCHITECTURE.md`.

Measured accuracy against Zerodha's published margins is in
`docs/DEEP_REVIEW/MARGIN_VALIDATION_MATRIX.md`. Read it before trusting a
number from here; the error is not uniform across the cases.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Literal, Optional, Sequence


# ---------------------------------------------------------------------------
# Published exchange parameters
#
# Every constant below is a published exchange figure with a source, NOT a
# tuned value. Nothing here may be adjusted to make a validation case pass —
# a mismatch is a finding about the model, not licence to fit the constant.
# ---------------------------------------------------------------------------

class Segment(str, Enum):
    INDEX = "index"                 # IDF / IDO
    STOCK = "stock"                 # STF / STO
    INDEX_LONG_DATED = "index_long_dated"   # index options, residual maturity > 9 months


#: Price Scan Range floor. NSE: "six standard deviations (6 sigma) scaled up by
#: sqrt(2) subject to <floor> of underlying price". "Subject to" is a MINIMUM —
#: NSE's own stock-derivatives wording is "subject to at least 14.2%".
PSR_FLOOR = {
    Segment.INDEX: 0.093,
    Segment.INDEX_LONG_DATED: 0.177,
    Segment.STOCK: 0.142,
}

#: Volatility Scan Range: "25% of annualized EWMA volatility subject to minimum".
VSR_RATE = 0.25
VSR_MIN = {
    Segment.INDEX: 0.04,
    Segment.INDEX_LONG_DATED: 0.04,
    Segment.STOCK: 0.10,
}

#: Exposure margin, of contract value. Zerodha's published figures, which are
#: what OUR users are actually charged. Note that generic NSE-guidance sources
#: quote 3% / 5%; the discrepancy is recorded in RISK_AND_MARGIN_VERIFICATION.md
#: and is NOT resolved by picking the one that validates better.
EXPOSURE_RATE = {
    Segment.INDEX: 0.02,
    Segment.INDEX_LONG_DATED: 0.02,
    Segment.STOCK: 0.035,
}

#: Calendar / inter-month spread charge, of the far-month contract.
#: Published, but NOT implemented below — see `UNIMPLEMENTED` at the bottom.
CALENDAR_SPREAD_CHARGE = {Segment.INDEX: 0.0175, Segment.STOCK: 0.022}

#: The 16 standard scenarios, verbatim from NSE Clearing, as
#: (price move in PSR units, volatility move in VSR units, loss weight).
#: The two extreme moves are double the PSR and cover only 35% of the loss.
SCENARIOS: tuple[tuple[float, float, float], ...] = (
    ( 0.0,  1.0, 1.00), ( 0.0, -1.0, 1.00),
    ( 1/3,  1.0, 1.00), ( 1/3, -1.0, 1.00),
    (-1/3,  1.0, 1.00), (-1/3, -1.0, 1.00),
    ( 2/3,  1.0, 1.00), ( 2/3, -1.0, 1.00),
    (-2/3,  1.0, 1.00), (-2/3, -1.0, 1.00),
    ( 1.0,  1.0, 1.00), ( 1.0, -1.0, 1.00),
    (-1.0,  1.0, 1.00), (-1.0, -1.0, 1.00),
    ( 2.0,  0.0, 0.35), (-2.0,  0.0, 0.35),
)

DAYS_PER_YEAR = 365.0     # NSE annualises with sqrt(365), per the FOVOLT header


# ---------------------------------------------------------------------------
# Inputs and outputs
# ---------------------------------------------------------------------------

class MarginSource(str, Enum):
    """Provenance. Never render COMPUTED as if it were BROKER."""
    BROKER = "broker"        # from Kite /margins/orders, exact
    COMPUTED = "computed"    # reconstructed here
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class Leg:
    """
    One position leg.

    `qty` is SIGNED and in UNITS, not lots — positive long, negative short —
    matching `CompletedTrade.total_quantity` semantics. `lot_size` is carried
    only so the caller can be explicit about it; the arithmetic here is per
    unit throughout.

    `price` is the contract's own current price: the option's premium, or the
    futures price. For a historical reconstruction this is the bhavcopy
    settlement price on the trade date.
    """
    kind: Literal["OPT", "FUT"]
    qty: int
    price: float
    expiry_days: float
    option_type: Optional[Literal["CE", "PE"]] = None
    strike: Optional[float] = None
    lot_size: Optional[int] = None


@dataclass(frozen=True)
class MarginBreakdown:
    scanning_risk: float
    net_option_value: float
    span: float
    exposure: float
    total: float
    psr: float
    vsr: float
    source: MarginSource = MarginSource.COMPUTED
    #: True when the portfolio contains more than one expiry, which this model
    #: does NOT charge a calendar spread for. The number is then understated.
    calendar_spread_unmodelled: bool = False

    #: True when a futures leg is held alongside a LONG option leg. The exchange
    #: does not credit that hedge in full and this model does. See `reliable`.
    futures_long_option_hedge: bool = False

    @property
    def reliable(self) -> bool:
        """
        Whether this figure may be used as a capital requirement.

        Two portfolio shapes are refused, both because the model comes out LOW.
        Understating committed capital is the dangerous direction for every rule
        that asks "how much of my account is tied up", so a flag on a returned
        number is not enough — callers must test this and abstain.

        **Multi-expiry.** No inter-month charge is implemented. Measured: a
        NIFTY SEP/OCT calendar spread came out at 32,404 against the broker's
        46,019, **29.6% low**.

        **Futures held with a long option.** Measured against a real Kite
        account: HAL September futures long plus a long 4600 put came out at
        67,321 against the broker's 86,243, **16% low on the total and 23% low
        on the scan**.

        The cause there is established and it is not a bug in the scan. The
        combination's maximum possible loss is (F - K) x qty + premium =
        46,185, and the broker's implied scanning risk is 60,647 — the exchange
        charges **14,462 more than the position can possibly lose**. No price
        scan range can reproduce that while crediting the option in full,
        because once the put is in the money the loss is capped by arithmetic.
        The exchange is deliberately withholding part of the hedge credit, and
        no rule for how much is published in the material we have read.

        Deliberately narrow. Futures with a SHORT option validated at +2.5% and
        +3.5%, and option-against-option offsets at -0.3% and +0.3%, so neither
        is refused. Only a long option offsetting a futures leg is.
        """
        return not (self.calendar_spread_unmodelled or self.futures_long_option_hedge)


# ---------------------------------------------------------------------------
# Option pricing
#
# NSE names Black-Scholes as the model. We use its Black-76 form, which is the
# same model written on a FORWARD rather than a spot price, because the
# underlying reference in this module is the futures price (see
# `compute_margin`).
#
# This is a correctness fix, not a refinement. Feeding a futures price into the
# spot form leaves an exp(r*T) carry term in the calculation that the futures
# price already contains, counting it twice. The resulting error is asymmetric
# — it inflates calls and deflates puts — and validation showed precisely that
# shape: with the spot form, short puts landed within 2.5% of the broker while
# short calls ran 5% to 14% high across the entire strike ladder.
# ---------------------------------------------------------------------------

def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def black_76(forward: float, strike: float, years: float, rate: float,
             vol: float, option_type: str) -> float:
    """European option on a forward/futures price. Intrinsic at expiry."""
    if years <= 0 or vol <= 0 or forward <= 0 or strike <= 0:
        intrinsic = (forward - strike) if option_type == "CE" else (strike - forward)
        return max(intrinsic, 0.0)
    sqrt_t = math.sqrt(years)
    d1 = (math.log(forward / strike) + (vol * vol / 2.0) * years) / (vol * sqrt_t)
    d2 = d1 - vol * sqrt_t
    discount = math.exp(-rate * years)
    if option_type == "CE":
        return discount * (forward * _norm_cdf(d1) - strike * _norm_cdf(d2))
    return discount * (strike * _norm_cdf(-d2) - forward * _norm_cdf(-d1))


#: Alias kept so the module reads the way NSE's own documentation describes it.
black_scholes = black_76


# ---------------------------------------------------------------------------
# Scan ranges
# ---------------------------------------------------------------------------

def implied_vol(market_price: float, underlying: float, strike: float,
                years: float, rate: float, option_type: str,
                fallback: float) -> float:
    """
    Back the option's own volatility out of its traded price, by bisection.

    WHY THIS IS HERE, since NSE's published method speaks of the UNDERLYING's
    volatility. Validation showed a clean call-versus-put split that a single
    underlying-level volatility cannot explain: with one shared vol the model
    over-stated short calls by 13-17% while short puts landed within 2%. That
    is the volatility skew. Real options on the same underlying and expiry
    trade at different implied volatilities by strike, and NSE's risk arrays
    are computed per contract, so they carry it; a single EWMA number does not.

    Using the contract's own implied volatility makes the model agree with the
    market price of its own leg at the unshocked scenario, which is the
    baseline every one of the sixteen is measured against. The VSR shock is
    then applied on top, exactly as before.

    Returns `fallback` when the price carries no usable information — below
    intrinsic, at or past expiry, or so small that any volatility fits.
    """
    if years <= 0 or market_price <= 0 or underlying <= 0 or strike <= 0:
        return fallback
    intrinsic = max((underlying - strike) if option_type == "CE"
                    else (strike - underlying), 0.0)
    # A price at intrinsic has no time value to invert, and near-worthless
    # contracts are numerically flat in vol — both fall back rather than
    # returning whatever the solver happens to land on.
    if market_price <= intrinsic * 1.0001 or market_price < 0.05 * underlying / 1000.0:
        return fallback

    low, high = 1e-4, 5.0
    if black_scholes(underlying, strike, years, rate, high, option_type) < market_price:
        return fallback          # price is outside the model's range entirely
    for _ in range(60):
        mid = (low + high) / 2.0
        if black_scholes(underlying, strike, years, rate, mid, option_type) < market_price:
            low = mid
        else:
            high = mid
    return (low + high) / 2.0


def price_scan_range(annualised_vol: float, segment: Segment) -> float:
    """
    Six sigma scaled by sqrt(2), floored. NSE quotes sigma daily and annualises
    by sqrt(365), so we invert that to get back to the daily figure.
    """
    daily = annualised_vol / math.sqrt(DAYS_PER_YEAR)
    return max(6.0 * daily * math.sqrt(2.0), PSR_FLOOR[segment])


def volatility_scan_range(annualised_vol: float, segment: Segment) -> float:
    return max(VSR_RATE * annualised_vol, VSR_MIN[segment])


# ---------------------------------------------------------------------------
# The portfolio calculation
# ---------------------------------------------------------------------------

def compute_margin(
    legs: Sequence[Leg],
    underlying: float,
    annualised_vol: float,
    segment: Segment,
    rate: float = 0.065,
) -> MarginBreakdown:
    """
    SPAN + exposure for a portfolio of legs on ONE underlying.

    `underlying` is the FUTURES price of the matching expiry, not the spot
    index. This is not a tuning choice. Indian SPAN scans a "combined
    commodity" whose price is the futures price, and each expiry carries its
    own forward: on 2026-08-28 NIFTY spot was 24,175.65 while the September,
    October and November futures settled at 24,341.90, 24,454.40 and
    24,570.70. Option prices embed that forward, so scanning against spot puts
    the model out of step with the market price of its own legs at the
    unshocked scenario and biases every result. Validation showed exactly that:
    a long and a short future, which the broker charges almost identically,
    came out 21,612 apart. Fall back to spot only when the underlying has no
    futures contract.

    Spread benefit is not a special case and is not a rule we invented: it
    falls out of scanning the legs TOGETHER. A long leg's gain in a scenario
    offsets the short leg's loss inside the same sum, so the worst case over
    the sixteen is smaller than the sum of the individual worst cases. That is
    how the exchange gets it too.

    All legs must share an underlying. Mixing underlyings would need the
    inter-commodity spread credit, which is not modelled.
    """
    psr = price_scan_range(annualised_vol, segment)
    vsr = volatility_scan_range(annualised_vol, segment)

    # Each option leg is scanned at its OWN implied volatility. The scan
    # ranges above stay on the underlying's volatility, because that is what
    # NSE defines them against.
    leg_vol = {
        id(leg): implied_vol(
            leg.price, underlying, float(leg.strike or 0.0),
            leg.expiry_days / DAYS_PER_YEAR, rate,
            leg.option_type or "CE", annualised_vol)
        for leg in legs if leg.kind == "OPT"
    }

    scanning_risk = 0.0
    for price_move, vol_move, weight in SCENARIOS:
        shocked_underlying = underlying * (1.0 + price_move * psr)

        portfolio_loss = 0.0
        for leg in legs:
            if leg.kind == "FUT":
                new_value = shocked_underlying
            else:
                shocked_vol = max(leg_vol[id(leg)] + vol_move * vsr, 1e-9)
                # One-day look-ahead. NSE: the risk array "represents how a
                # specific derivative instrument will gain or lose value from
                # the current point in time to a specific point in the near
                # future (typically it calculates risk over a one day period
                # called the 'look ahead time')". So the shocked leg is priced
                # with one day less to run, not at today's maturity.
                #
                # It is here because it is what NSE documents, NOT because it
                # improved the numbers: measured, it moved the validation set
                # by about 0.02%. One day of decay out of thirty is negligible
                # against a 9.3% price shock. The residual bias on short
                # options has a different cause, still unidentified — see
                # MARGIN_VALIDATION_MATRIX.md.
                new_value = black_scholes(
                    shocked_underlying, float(leg.strike or 0.0),
                    max(leg.expiry_days - 1.0, 0.0) / DAYS_PER_YEAR,
                    rate, shocked_vol, leg.option_type or "CE",
                )
            # Loss is positive. A long position loses when value falls.
            portfolio_loss += -(new_value - leg.price) * leg.qty
        scanning_risk = max(scanning_risk, portfolio_loss * weight)

    # Net option value: long options minus short options, at current price.
    # Negative for a net-short book. SPAN subtracts it, so a short's received
    # premium is ADDED to the requirement.
    net_option_value = sum(leg.qty * leg.price for leg in legs if leg.kind == "OPT")

    # Floored at zero. For a bought option the premium is paid up front and no
    # margin is blocked at all; without the floor the net-option-value credit
    # drives the requirement negative, which is not a smaller margin but a
    # meaningless one. Verified against the broker: every long-only position in
    # the validation set returns exactly 0, including a long straddle that this
    # model otherwise reported as -36,189.
    span = max(scanning_risk - net_option_value, 0.0)

    # Exposure is charged on short option legs and on futures, both directions.
    # Long options carry none. Verified empirically against the broker: the
    # figure is invariant to strike and to expiry, and a call spread pays the
    # same exposure as its short leg alone.
    exposed_qty = sum(
        abs(leg.qty) for leg in legs
        if leg.kind == "FUT" or (leg.kind == "OPT" and leg.qty < 0)
    )
    exposure = EXPOSURE_RATE[segment] * underlying * exposed_qty

    expiries = {round(leg.expiry_days, 6) for leg in legs}
    has_future = any(leg.kind == "FUT" for leg in legs)
    has_long_option = any(leg.kind == "OPT" and leg.qty > 0 for leg in legs)

    return MarginBreakdown(
        scanning_risk=scanning_risk,
        net_option_value=net_option_value,
        span=span,
        exposure=exposure,
        total=span + exposure,
        psr=psr,
        vsr=vsr,
        source=MarginSource.COMPUTED,
        calendar_spread_unmodelled=len(expiries) > 1,
        futures_long_option_hedge=has_future and has_long_option,
    )


# ---------------------------------------------------------------------------
# UNIMPLEMENTED — known gaps, stated rather than silently approximated
# ---------------------------------------------------------------------------
#
#   calendar / inter-month spread charge
#       Published (1.75% index, 2.2% stock of the far month) but needs the
#       composite delta per month, which is a weighted average of the deltas
#       at each price scan point. `calendar_spread_unmodelled` flags any
#       portfolio this would apply to.
#
#   inter-commodity spread credit
#       Requires the exchange's tier and credit-rate tables. Not attempted;
#       `compute_margin` is single-underlying by contract.
#
#   short option minimum charge
#       A real SPAN component. The parameter has not been retrieved, so it is
#       not applied. Deep-OTM shorts are therefore the cases most likely to be
#       UNDER-stated here.
#
#   additional ELM near index expiry
#       Zerodha documents an extra margin on index options close to expiry.
#       Not modelled.
#
#   the exchange's partial credit for a long option hedging a future
#       Measured, not derived: the exchange charges above the combination's
#       arithmetic maximum loss, so it withholds part of the offset. The rule
#       is not in the published material we have read. `reliable` is False for
#       these portfolios rather than returning a number known to be low.
#
#   physical delivery margin on stock F&O expiry week
#       Escalates sharply in the last days for in-the-money stock contracts.
#       Not modelled.
