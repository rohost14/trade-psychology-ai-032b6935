"""
Infrastructure semantics — the risk layer, in process.

No database, no Redis, no synthetic rows, no network. Every case below is
constructed in memory and run through the real modules.

What this suite is for: proving the layer ABSTAINS when it should. Coverage is
not the goal — a wrong confident answer is worse than no answer, so most of
these assert a refusal rather than a value.
"""
from __future__ import annotations

from datetime import date

import pytest

from app.core.contract_spec import (
    ContractSpec, Reliability, Segment, SpecSource,
)
from app.core.exchange_support import Support, may_compute_capital, support_for
from app.core.risk_quantities import (
    Capital, Comparability, DenominatorKind, MarginSource,
    compare_sizes, quantities_for, size_ratio,
)
from app.services.instrument_master import (
    InstrumentMaster, derive_spec, resolve,
)

DAY = date(2026, 8, 28)


def spec(segment, *, exchange="NFO", lot=65, strike=24200.0, opt="CE",
         reliability=Reliability.AUTHORITATIVE, mult=None):
    return ContractSpec(
        tradingsymbol="TEST", exchange=exchange, effective_date=DAY,
        segment=segment, underlying="NIFTY", expiry=date(2026, 9, 29),
        strike=strike, option_type=opt, lot_size=lot, contract_multiplier=mult,
        source=SpecSource.EXCHANGE, reliability=reliability,
    )


MARGIN = Capital(amount=175747.0, source=MarginSource.BROKER, scope="position")


# ---------------------------------------------------------------------------
# The eight instrument x direction combinations
# ---------------------------------------------------------------------------

CASES = [
    # segment,               direction, expected kind,                  bounded
    (Segment.INDEX_OPTION,  "LONG",  DenominatorKind.LOSS_CEILING,  True),
    (Segment.INDEX_OPTION,  "SHORT", DenominatorKind.MARGIN_POSTED, False),
    (Segment.STOCK_OPTION,  "LONG",  DenominatorKind.LOSS_CEILING,  True),
    (Segment.STOCK_OPTION,  "SHORT", DenominatorKind.MARGIN_POSTED, False),
    (Segment.INDEX_FUTURE,  "LONG",  DenominatorKind.MARGIN_POSTED, False),
    (Segment.INDEX_FUTURE,  "SHORT", DenominatorKind.MARGIN_POSTED, False),
    (Segment.STOCK_FUTURE,  "LONG",  DenominatorKind.MARGIN_POSTED, False),
    (Segment.STOCK_FUTURE,  "SHORT", DenominatorKind.MARGIN_POSTED, False),
]


@pytest.mark.parametrize("segment,direction,kind,bounded", CASES)
def test_every_instrument_direction_combination(segment, direction, kind, bounded):
    q = quantities_for(spec(segment), direction, 65, 120.0, margin=MARGIN)
    assert q.denominator_kind is kind
    assert q.loss_is_bounded is bounded


def test_ce_and_pe_are_treated_identically_for_a_given_direction():
    """
    Direction is exposure, never sentiment. A long PE is not bearish behaviour
    and a short CE is not a hedge. The engine must not be able to tell CE from
    PE when deciding what kind of risk a position carries.
    """
    for direction in ("LONG", "SHORT"):
        call = quantities_for(spec(Segment.INDEX_OPTION, opt="CE"), direction,
                              65, 120.0, margin=MARGIN)
        put = quantities_for(spec(Segment.INDEX_OPTION, opt="PE"), direction,
                             65, 120.0, margin=MARGIN)
        assert call.denominator_kind is put.denominator_kind
        assert call.entry_value.label == put.entry_value.label


# ---------------------------------------------------------------------------
# A, B and C stay separate
# ---------------------------------------------------------------------------

def test_entry_value_is_premium_and_is_labelled_by_direction():
    long_ce = quantities_for(spec(Segment.INDEX_OPTION), "LONG", 65, 120.0)
    short_ce = quantities_for(spec(Segment.INDEX_OPTION), "SHORT", 65, 120.0,
                              margin=MARGIN)
    assert long_ce.entry_value.amount == pytest.approx(7800.0)
    assert short_ce.entry_value.amount == pytest.approx(7800.0)
    assert long_ce.entry_value.label == "premium paid"
    assert short_ce.entry_value.label == "premium received"


def test_a_margin_change_is_not_a_pnl_change():
    """
    The distinction the brief insists on. Sell NIFTY CE at 120 x 65, buy back at
    200. P&L is -5,200 whatever the margin requirement happens to be, and it
    does not move when the margin figure moves.
    """
    cheap = Capital(amount=10_000.0, source=MarginSource.BROKER)
    dear = Capital(amount=225_000.0, source=MarginSource.COMPUTED)

    a = quantities_for(spec(Segment.INDEX_OPTION), "SHORT", 65, 120.0,
                       exit_price=200.0, margin=cheap)
    b = quantities_for(spec(Segment.INDEX_OPTION), "SHORT", 65, 120.0,
                       exit_price=200.0, margin=dear)

    assert a.pnl.amount == pytest.approx(-5200.0)
    assert b.pnl.amount == pytest.approx(-5200.0)
    assert a.capital_requirement.amount != b.capital_requirement.amount


def test_long_option_pnl_and_entry_value():
    q = quantities_for(spec(Segment.INDEX_OPTION), "LONG", 65, 50.0, exit_price=45.0)
    assert q.entry_value.amount == pytest.approx(3250.0)
    assert q.pnl.amount == pytest.approx(-325.0)
    # For a bought option, capital and entry value coincide - and only here.
    assert q.capital_requirement.amount == pytest.approx(3250.0)


def test_entry_value_and_capital_are_different_types():
    """
    The type separation is the mechanism, not a convention. A detector that
    reaches for the wrong quantity gets a TypeError at the point of misuse.
    """
    q = quantities_for(spec(Segment.INDEX_OPTION), "SHORT", 65, 120.0, margin=MARGIN)
    with pytest.raises(TypeError):
        _ = q.entry_value < q.capital_requirement       # type: ignore[operator]


# ---------------------------------------------------------------------------
# Abstention
# ---------------------------------------------------------------------------

def test_short_position_without_a_margin_figure_abstains():
    """No margin supplied means no capital answer. Never a substituted percentage."""
    q = quantities_for(spec(Segment.INDEX_OPTION), "SHORT", 65, 120.0, margin=None)
    assert not q.capital_requirement.available
    assert q.capital_requirement.source is MarginSource.UNAVAILABLE
    assert not q.usable_for_capital_rules


def test_short_equity_is_unresolved_and_says_so():
    eq = ContractSpec(tradingsymbol="RELIANCE", exchange="NSE", effective_date=DAY,
                      segment=Segment.EQUITY, underlying="RELIANCE",
                      source=SpecSource.EXCHANGE, reliability=Reliability.AUTHORITATIVE)
    long_eq = quantities_for(eq, "LONG", 100, 2900.0)
    short_eq = quantities_for(eq, "SHORT", 100, 2900.0)
    assert long_eq.denominator_kind is DenominatorKind.NOTIONAL
    assert short_eq.denominator_kind is DenominatorKind.UNRELIABLE
    assert not short_eq.usable_for_capital_rules


def test_unknown_contract_abstains_and_is_never_equity():
    unknown = ContractSpec.unavailable("GARBAGE25XYZ99CE", "NFO", DAY, "unreadable")
    q = quantities_for(unknown, "LONG", 65, 120.0)
    assert q.denominator_kind is DenominatorKind.UNRELIABLE
    assert unknown.segment is not Segment.EQUITY
    assert not q.usable_for_capital_rules


@pytest.mark.parametrize("exchange,expected", [
    ("NFO", Support.SUPPORTED),
    ("NSE", Support.IDENTITY_ONLY),
    ("BFO", Support.IDENTITY_ONLY),
    ("CDS", Support.UNSUPPORTED),
    ("MCX", Support.IDENTITY_ONLY),   # was UNSUPPORTED; multiplier now sourced
                                      # from MCX contract specs. Capital still refused.
    (None, Support.UNSUPPORTED),
    ("NONSENSE", Support.UNSUPPORTED),
])
def test_exchange_coverage_is_explicit(exchange, expected):
    assert support_for(exchange).support is expected


def test_only_nfo_may_compute_capital():
    assert may_compute_capital("NFO")
    for x in ("NSE", "BFO", "CDS", "MCX", None, "NONSENSE"):
        assert not may_compute_capital(x), x


def test_mcx_identity_works_but_capital_still_abstains():
    """
    MCX moved to IDENTITY_ONLY once the multiplier was sourced from MCX's own
    published contract specification (GOLDM: 100 gram trading unit, price quoted
    per 10 grams, so multiplier 10).

    Entry value is now right and capital is still refused, because MCX sets its
    own scan ranges and NSE's 9.3%/14.2% equity-derivative floors do not apply
    to bullion. Applying them would be a fabrication.
    """
    mcx = support_for("MCX")
    assert mcx.support is Support.IDENTITY_ONLY
    assert not may_compute_capital("MCX")

    got = resolve("GOLDM26SEPFUT", "MCX", DAY)
    assert got.contract_multiplier == 10
    q = quantities_for(got, "LONG", 1, 155999.0)
    # 1 lot = 100 grams, quoted per 10 grams -> 155,999 x 10, NOT 155,999.
    assert q.entry_value.amount == pytest.approx(1_559_990.0)
    assert not q.capital_requirement.available


def test_an_mcx_contract_with_no_tabulated_multiplier_abstains_entirely():
    """
    The guard that must never be loosened for coverage. Falling back to a
    multiplier of 1 is a 5000x error on ZINC.
    """
    got = resolve("SOMETHINGNEW26SEPFUT", "MCX", DAY)
    assert got.reliability is Reliability.UNRELIABLE
    assert got.contract_multiplier is None
    q = quantities_for(got, "LONG", 1, 700.0)
    assert not q.usable_for_capital_rules


def test_mcx_expiry_is_never_computed_from_a_weekday_rule():
    """
    GOLDM's September 2026 contract expires 2026-09-04 - the 5th of the expiry
    month, not any weekday rule. A derived spec must therefore claim no expiry
    DATE at all, the same discipline that NSE's Tuesday expiries forced.
    """
    got = resolve("GOLDM26SEPFUT", "MCX", DAY)
    assert got.expiry is None


def test_mtf_is_not_given_an_invented_leverage():
    """
    MTF is identified, never modelled. With no funded-fraction data, capital is
    unavailable rather than a guessed percentage of notional.
    """
    cash = ContractSpec(tradingsymbol="RELIANCE", exchange="NSE", effective_date=DAY,
                        segment=Segment.EQUITY, underlying="RELIANCE", product="CNC",
                        source=SpecSource.EXCHANGE, reliability=Reliability.AUTHORITATIVE)
    mtf = ContractSpec(**{**cash.__dict__, "product": "MTF"})

    # Cash equity bought outright: the notional IS the committed capital.
    assert quantities_for(cash, "LONG", 100, 2900.0).capital_requirement.available
    # The same position on MTF is part-funded, so committed capital is unknown.
    q = quantities_for(mtf, "LONG", 100, 2900.0)
    assert not q.capital_requirement.available
    assert "MTF" in (q.capital_requirement.note or "")


# ---------------------------------------------------------------------------
# Comparability - refusal beats a false comparison
# ---------------------------------------------------------------------------

def test_premium_against_premium_is_comparable():
    a = quantities_for(spec(Segment.INDEX_OPTION), "LONG", 65, 100.0)
    b = quantities_for(spec(Segment.INDEX_OPTION), "LONG", 65, 200.0)
    assert compare_sizes(a, b)[0] is Comparability.COMPARABLE
    assert size_ratio(a, b) == pytest.approx(2.0)


def test_premium_against_futures_margin_refuses_to_compare():
    """Rs 10,000 of premium against Rs 2,00,000 of futures margin is not a 20x."""
    prem = quantities_for(spec(Segment.INDEX_OPTION), "LONG", 65, 154.0)
    fut = quantities_for(spec(Segment.INDEX_FUTURE, opt=None), "LONG",
                         65, 24342.0, margin=MARGIN)
    verdict, reason = compare_sizes(prem, fut)
    assert verdict is Comparability.NOT_COMPARABLE
    assert size_ratio(prem, fut) is None
    assert "denominator" in reason or "segment" in reason


def test_long_premium_against_short_premium_refuses_to_compare():
    """Premium paid and premium received are opposite transactions."""
    paid = quantities_for(spec(Segment.INDEX_OPTION), "LONG", 65, 120.0)
    received = quantities_for(spec(Segment.INDEX_OPTION), "SHORT", 65, 120.0,
                              margin=MARGIN)
    assert compare_sizes(paid, received)[0] is Comparability.NOT_COMPARABLE


def test_unreliable_side_refuses_to_compare():
    good = quantities_for(spec(Segment.INDEX_OPTION), "LONG", 65, 120.0)
    bad = quantities_for(ContractSpec.unavailable("X", "NFO", DAY, "unreadable"),
                         "LONG", 65, 120.0)
    assert compare_sizes(good, bad)[0] is Comparability.NOT_COMPARABLE
    assert size_ratio(good, bad) is None


# ---------------------------------------------------------------------------
# Effective dating and immutability
# ---------------------------------------------------------------------------

def test_a_historical_trade_uses_the_lot_size_of_its_own_date():
    """
    The rule the brief states outright: never today's lot size for an old trade.
    NIFTY has been 75 and is 65.
    """
    m = InstrumentMaster()
    old = ContractSpec(tradingsymbol="NIFTY26SEP24200CE", exchange="NFO",
                       effective_date=date(2025, 1, 1), segment=Segment.INDEX_OPTION,
                       underlying="NIFTY", lot_size=75, source=SpecSource.EXCHANGE,
                       reliability=Reliability.AUTHORITATIVE)
    new = ContractSpec(**{**old.__dict__, "effective_date": date(2026, 1, 1),
                          "lot_size": 65})
    m.add(old)
    m.add(new)

    assert m.as_of("NIFTY26SEP24200CE", "NFO", date(2025, 6, 1)).lot_size == 75
    assert m.as_of("NIFTY26SEP24200CE", "NFO", date(2026, 6, 1)).lot_size == 65
    # Before any record exists, there is no answer - not a default.
    assert m.as_of("NIFTY26SEP24200CE", "NFO", date(2024, 1, 1)) is None


def test_records_are_immutable():
    m = InstrumentMaster()
    a = ContractSpec(tradingsymbol="X", exchange="NFO", effective_date=DAY,
                     segment=Segment.INDEX_OPTION, lot_size=65,
                     source=SpecSource.EXCHANGE, reliability=Reliability.AUTHORITATIVE)
    m.add(a)
    m.add(a)                                   # identical re-add is a no-op
    with pytest.raises(ValueError, match="immutability"):
        m.add(ContractSpec(**{**a.__dict__, "lot_size": 75}))


def test_historical_resolution_refuses_to_derive():
    """
    A derived answer is a quiet downgrade from a fact to a guess. For historical
    work that must be refused, not silently accepted.
    """
    got = resolve("NIFTY25MAR25000CE", "NFO", DAY, master=InstrumentMaster(),
                  allow_derived=False)
    assert got.reliability is Reliability.UNRELIABLE
    assert got.source is SpecSource.UNAVAILABLE


def test_live_path_may_derive_but_is_labelled_derived():
    got = resolve("NIFTY25MAR25000CE", "NFO", DAY)
    assert got.source is SpecSource.DERIVED
    assert got.reliability is Reliability.DERIVED
    assert got.segment is Segment.INDEX_OPTION
    assert got.usable
    # A derived record must NOT claim a lot size or an expiry DATE it cannot know.
    assert got.lot_size is None
    assert got.expiry is None


def test_derived_unreadable_derivative_is_unavailable_not_equity():
    got = derive_spec("GARBAGE25XYZ99CE", "NFO", DAY)
    assert got.segment is Segment.UNKNOWN
    assert got.segment is not Segment.EQUITY
    assert got.reliability is Reliability.UNRELIABLE


def test_unsupported_exchange_short_circuits_resolution():
    # CDS, not MCX. MCX moved to IDENTITY_ONLY once its multiplier was sourced;
    # CDS is still genuinely unresearched, so it is the honest example here.
    got = resolve("USDINR26SEPFUT", "CDS", DAY)
    assert got.reliability is Reliability.UNRELIABLE
    assert got.source is SpecSource.UNAVAILABLE


def test_contract_multiplier_is_applied_when_present():
    got = quantities_for(spec(Segment.STOCK_FUTURE, mult=100), "LONG", 1, 700.0,
                         margin=MARGIN)
    assert got.entry_value.amount == pytest.approx(70_000.0)


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------

def test_computed_is_never_labelled_broker():
    computed = Capital(amount=175747.0, source=MarginSource.COMPUTED)
    assert computed.source is not MarginSource.BROKER
    assert computed.available


def test_capital_scope_is_carried_not_collapsed():
    """
    Single-position, order, portfolio and strategy margins are different
    numbers. A field that does not say which one it holds is how they get
    confused.
    """
    for scope in ("position", "order", "portfolio", "strategy"):
        assert Capital(amount=1.0, source=MarginSource.BROKER, scope=scope).scope == scope


# ---------------------------------------------------------------------------
# Margin model - portfolio shapes the model must REFUSE
#
# Both were found by measuring against a real broker, and both fail in the same
# direction: the model comes out LOW. Understating committed capital is the
# unsafe direction, so these assert an abstention, not a value.
# ---------------------------------------------------------------------------

def test_multi_expiry_portfolio_abstains():
    """No inter-month charge. Measured 29.6% low on a NIFTY SEP/OCT spread."""
    from app.core.margin_model import Leg, Segment as MSeg, compute_margin
    m = compute_margin(
        [Leg("OPT", -65, 351.9, 32, "CE", 24200.0, 65),
         Leg("OPT", 65, 470.0, 60, "CE", 24200.0, 65)],
        underlying=24341.9, annualised_vol=0.162, segment=MSeg.INDEX)
    assert m.calendar_spread_unmodelled
    assert not m.reliable


def test_futures_with_a_long_option_abstains():
    """
    HAL SEP future long + 4600 put long. Broker 86,243; model 67,321, 16% low.

    The cause is established: the combination cannot lose more than
    (F - K) * qty + premium = 46,185, yet the broker's implied scanning risk is
    60,647. The exchange charges above the arithmetic maximum loss, so it
    withholds part of the hedge credit by a rule we have not found published.
    """
    from app.core.margin_model import Leg, Segment as MSeg, compute_margin
    m = compute_margin(
        [Leg("OPT", 150, 32.50, 32, "PE", 4600.0, 150),
         Leg("FUT", 150, 4875.40, 32, None, None, 150)],
        underlying=4875.40, annualised_vol=0.3616, segment=MSeg.STOCK)
    assert m.futures_long_option_hedge
    assert not m.reliable


def test_the_refusal_is_narrow():
    """
    Futures with a SHORT option validated at +2.5% and +3.5%, and
    option-against-option offsets at -0.3% and +0.3%. Neither may be refused -
    an over-broad abstention silently removes working coverage.
    """
    from app.core.margin_model import Leg, Segment as MSeg, compute_margin

    fut_short_put = compute_margin(
        [Leg("FUT", 65, 24341.9, 32, None, None, 65),
         Leg("OPT", -65, 300.0, 32, "PE", 24200.0, 65)],
        underlying=24341.9, annualised_vol=0.162, segment=MSeg.INDEX)
    assert fut_short_put.reliable

    call_spread = compute_margin(
        [Leg("OPT", 65, 51.0, 4, "CE", 24300.0, 65),
         Leg("OPT", -65, 97.2, 4, "CE", 24200.0, 65)],
        underlying=24231.52, annualised_vol=0.162, segment=MSeg.INDEX)
    assert call_spread.reliable

    naked_future = compute_margin(
        [Leg("FUT", 65, 24349.0, 32, None, None, 65)],
        underlying=24349.0, annualised_vol=0.162, segment=MSeg.INDEX)
    assert naked_future.reliable


# ---------------------------------------------------------------------------
# Margin model - two numbers, because the broker reports two
#
# Every expectation below is a real figure from a live Kite account.
# ---------------------------------------------------------------------------

def _mm(legs, underlying, vol, seg):
    from app.core.margin_model import compute_margin
    return compute_margin(legs, underlying=underlying, annualised_vol=vol, segment=seg)


def test_futures_final_and_required_are_the_same_number():
    """No option premium in play, so there is nothing to fund separately."""
    from app.core.margin_model import Leg, Segment as MSeg
    m = _mm([Leg("FUT", 65, 24349.0, 32, None, None, 65)], 24349.0, 0.162, MSeg.INDEX)
    assert m.final_margin == pytest.approx(m.required_margin)
    assert m.final_margin == pytest.approx(178_663, rel=0.02)     # Kite: 178,663


def test_option_spread_reproduces_BOTH_kite_numbers():
    """
    NIFTY 01SEP, buy 24300CE at 51 and sell 24200CE at 97.20, one lot each.
    Kite: required 41,430, final 35,112. Both to within 0.5%.

    The single-number model matched neither - it sat between them.
    """
    from app.core.margin_model import Leg, Segment as MSeg
    m = _mm([Leg("OPT", 65, 51.0, 4, "CE", 24300.0, 65),
             Leg("OPT", -65, 97.2, 4, "CE", 24200.0, 65)],
            24231.52, 0.162, MSeg.INDEX)
    assert m.final_margin == pytest.approx(35_112, rel=0.005)
    assert m.required_margin == pytest.approx(41_430, rel=0.005)


def test_the_gap_between_them_is_exactly_the_short_premium():
    """
    Measured: Kite's required minus final was 6,318 on one short lot and 12,636
    on two, which is 97.20 x 65 and 97.20 x 130 exactly. It is the premium the
    trader has not received yet at the moment the order is placed.
    """
    from app.core.margin_model import Leg, Segment as MSeg
    one = _mm([Leg("OPT", 65, 51.0, 4, "CE", 24300.0, 65),
               Leg("OPT", -65, 97.2, 4, "CE", 24200.0, 65)],
              24231.52, 0.162, MSeg.INDEX)
    two = _mm([Leg("OPT", 65, 51.0, 4, "CE", 24300.0, 65),
               Leg("OPT", -130, 97.2, 4, "CE", 24200.0, 65)],
              24231.52, 0.162, MSeg.INDEX)
    assert one.required_margin - one.final_margin == pytest.approx(97.2 * 65)
    assert two.required_margin - two.final_margin == pytest.approx(97.2 * 130)


def test_a_long_only_book_requires_nothing():
    """
    The premium was paid in full; there is no ongoing obligation to
    collateralise. The broker returned exactly zero for 11 of 11 long-only
    positions, so this is a rule and not a rounding.
    """
    from app.core.margin_model import Leg, Segment as MSeg
    for legs in ([Leg("OPT", 65, 51.0, 4, "CE", 24300.0, 65)],
                 [Leg("OPT", 65, 51.0, 4, "CE", 24300.0, 65),
                  Leg("OPT", 65, 60.0, 4, "PE", 24100.0, 65)]):
        m = _mm(legs, 24231.52, 0.162, MSeg.INDEX)
        assert m.final_margin == 0.0
        assert m.required_margin == 0.0


# ---------------------------------------------------------------------------
# F17 - capital-relative consumers go through the canonical layer
#
# The point of F17 is not a better number. It is that a rule which divides by
# capital must ABSTAIN when capital is unknown, instead of dividing by premium,
# notional or a percentage stand-in.
# ---------------------------------------------------------------------------

def _trade(symbol, exchange, direction, qty, price, product="MIS"):
    from types import SimpleNamespace
    from datetime import datetime
    return SimpleNamespace(
        tradingsymbol=symbol, exchange=exchange, direction=direction,
        total_quantity=qty, avg_entry_price=price, product=product,
        exit_time=datetime(2026, 8, 28), instrument_type=None)


def test_long_option_capital_is_available_without_any_margin_model():
    """
    The definitional case. A bought option's capital IS its premium: the money
    left the account and nothing further is blocked. No scan range needed, so
    this must keep working on every exchange whose multiplier we know.
    """
    from app.core.risk_quantities import quantities_for_trade
    q = quantities_for_trade(_trade("NIFTY25MAR25000CE", "NFO", "LONG", 75, 120.0))
    assert q.usable_for_capital_rules
    assert q.capital_requirement.amount == pytest.approx(9000.0)


@pytest.mark.parametrize("symbol,exchange,direction,qty,price,product,why", [
    ("NIFTY25MAR25000CE", "NFO", "SHORT", 75, 120.0, "NRML", "short option needs margin"),
    ("NIFTY25MARFUT",     "NFO", "LONG",  75, 24000.0, "NRML", "future needs margin"),
    ("RELIANCE",          "NSE", "LONG", 100, 2900.0, "MTF",  "MTF is part-funded"),
    ("GOLDM26SEPFUT",     "MCX", "LONG",   1, 155999.0, "NRML", "MCX margin unsourced"),
    ("GARBAGE25XYZ99CE",  "NFO", "LONG",  75, 120.0, "MIS",  "contract unreadable"),
])
def test_capital_abstains_rather_than_substituting(symbol, exchange, direction,
                                                   qty, price, product, why):
    from app.core.risk_quantities import quantities_for_trade
    q = quantities_for_trade(_trade(symbol, exchange, direction, qty, price, product))
    assert not q.usable_for_capital_rules, why
    assert q.capital_requirement.amount is None
    # The entry value is still there - abstention is about CAPITAL only, and
    # premium-based behavioural work must not be collateral damage.
    assert q.entry_value.amount > 0


def test_mcx_entry_value_carries_the_multiplier_into_the_risk_layer():
    """One GOLDM lot at 155,999 is 15,59,990 of exposure, not 1,55,999."""
    from app.core.risk_quantities import quantities_for_trade
    q = quantities_for_trade(_trade("GOLDM26SEPFUT", "MCX", "LONG", 1, 155999.0, "NRML"))
    assert q.entry_value.amount == pytest.approx(1_559_990.0)


def test_exposure_value_helper_applies_the_multiplier():
    """
    overexposure and portfolio_concentration measure market exposure, not
    margin - F17 corrects their arithmetic, not the question they ask. An MCX
    leg previously contributed a tenth of its real weight.
    """
    from app.tasks.position_monitor_tasks import _exposure_value
    nfo, ok = _exposure_value("NIFTY25MARFUT", "NFO", 24000.0, 75)
    assert ok and nfo == pytest.approx(1_800_000.0)

    mcx, ok = _exposure_value("GOLDM26SEPFUT", "MCX", 155999.0, 1)
    assert ok and mcx == pytest.approx(1_559_990.0)

    _, ok = _exposure_value("GARBAGE25XYZ99CE", "NFO", 100.0, 1)
    assert not ok, "an unresolvable contract must abstain, not contribute a wrong weight"
