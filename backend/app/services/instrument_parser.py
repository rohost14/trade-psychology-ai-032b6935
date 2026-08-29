"""
NSE/BSE Instrument Symbol Parser

Parses Kite Connect tradingsymbol strings into structured components.

NSE F&O symbol formats
----------------------
Weekly options:   {underlying}{yy}{m}{dd}{strike}{CE|PE}
                  e.g. NIFTY2532025000CE = NIFTY, 2025-03-20, strike=25000, CE
                  Month chars: 1-9 = Jan-Sep, O=Oct, N=Nov, D=Dec

Monthly options:  {underlying}{yy}{MMM}{strike}{CE|PE}
                  e.g. NIFTY25MAR25000CE = NIFTY, Mar-2025, strike=25000, CE

Futures:          {underlying}{yy}{MMM}FUT
                  e.g. BANKNIFTY25APRFUT = BANKNIFTY, Apr-2025, FUT

Equity:           {underlying}  (e.g. RELIANCE, INFY)
"""
import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional


# ---------------------------------------------------------------------------
# Month look-ups
# ---------------------------------------------------------------------------

_MONTHLY_MONTHS: dict[str, int] = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}

# Kite weekly-expiry single-char codes
_WEEKLY_MONTH_CHARS: dict[str, int] = {
    "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6,
    "7": 7, "8": 8, "9": 9, "O": 10, "N": 11, "D": 12,
}

# ---------------------------------------------------------------------------
# Compiled regexes
# ---------------------------------------------------------------------------

# Underlying character class. Hyphens occur in real NSE F&O underlyings
# (BAJAJ-AUTO, M&M-FIN), so excluding them silently dropped those contracts.
_UND = r"[A-Z&][A-Z&\-]*"

# Strike. NOT a fixed digit count: NSE lists 2-digit strikes (YESBANK25APR18CE,
# NMDC25APR74CE) and half-rupee strikes (ASHOKLEY25AUG122.5CE,
# NYKAA25JUL207.5CE). The old `\d{3,6}` rejected both, which sent 17 symbols /
# 38 fills of the reference book down the equity branch. (F15, 2026-08-29.)
_STRIKE = r"\d+(?:\.\d+)?"

# Monthly option: NIFTY25MAR25000CE  /  BANKNIFTY25APR48000PE
_RE_MONTHLY_OPT = re.compile(
    rf"^({_UND})(\d{{2}})(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)({_STRIKE})(CE|PE)$"
)

# Monthly future: BANKNIFTY25APRFUT  /  NIFTY25MARFUT
_RE_MONTHLY_FUT = re.compile(
    rf"^({_UND})(\d{{2}})(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)FUT$"
)

# Weekly option: NIFTY2532025000CE  (yy + single-month-char + 2-digit-day)
_RE_WEEKLY_OPT = re.compile(
    rf"^({_UND})(\d{{2}})([1-9ONDond])(\d{{2}})({_STRIKE})(CE|PE)$"
)


def _parse_strike(strike_str: str) -> float:
    """
    Strikes are not always whole rupees. NSE lists half-rupee strikes on several
    stock options (ASHOKLEY 122.5, NYKAA 207.5), so this returns a float and the
    caller must not assume an integer. Truncating to int would silently collapse
    122.5 and 122 onto the same contract. (F15, 2026-08-29.)
    """
    return float(strike_str)


# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------

@dataclass
class ParsedSymbol:
    raw: str
    underlying: str            # NIFTY, BANKNIFTY, RELIANCE …
    instrument_type: str       # CE | PE | FUT | EQ
    expiry_date: Optional[date]
    strike: Optional[float]    # option strike price — float: NSE lists half-rupee strikes
    expiry_key: str            # canonical key for grouping (ISO date or "YYYY-MM" for monthlies)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_symbol(symbol: str) -> ParsedSymbol:
    """
    Parse an NSE/BSE tradingsymbol into structured components.

    Never raises — returns EQ for any unrecognised format.
    """
    symbol = symbol.strip().upper()

    # 1. Monthly option: NIFTY25MAR25000CE
    m = _RE_MONTHLY_OPT.match(symbol)
    if m:
        underlying, yy, mon_str, strike_str, opt_type = m.groups()
        year = 2000 + int(yy)
        month = _MONTHLY_MONTHS[mon_str]
        expiry_key = f"{year}-{month:02d}"          # e.g. "2025-03"
        return ParsedSymbol(
            raw=symbol,
            underlying=underlying,
            instrument_type=opt_type,
            expiry_date=date(year, month, 1),       # day=1 proxy (last Thu isn't needed for grouping)
            strike=_parse_strike(strike_str),
            expiry_key=expiry_key,
        )

    # 2. Monthly future: BANKNIFTY25APRFUT
    m = _RE_MONTHLY_FUT.match(symbol)
    if m:
        underlying, yy, mon_str = m.groups()
        year = 2000 + int(yy)
        month = _MONTHLY_MONTHS[mon_str]
        expiry_key = f"{year}-{month:02d}"
        return ParsedSymbol(
            raw=symbol,
            underlying=underlying,
            instrument_type="FUT",
            expiry_date=date(year, month, 1),
            strike=None,
            expiry_key=expiry_key,
        )

    # 3. Weekly option: NIFTY2532025000CE
    m = _RE_WEEKLY_OPT.match(symbol)
    if m:
        underlying, yy, mon_char, dd_str, strike_str, opt_type = m.groups()
        year = 2000 + int(yy)
        month = _WEEKLY_MONTH_CHARS.get(mon_char.upper(), 0)
        day = int(dd_str)
        expiry: Optional[date] = None
        if month and 1 <= day <= 31:
            try:
                expiry = date(year, month, day)
            except ValueError:
                pass
        expiry_key = expiry.isoformat() if expiry else f"{yy}{mon_char}{dd_str}"
        return ParsedSymbol(
            raw=symbol,
            underlying=underlying,
            instrument_type=opt_type,
            expiry_date=expiry,
            strike=_parse_strike(strike_str),
            expiry_key=expiry_key,
        )

    # 4. Equity — or a derivative we failed to read
    #
    # FIXED 2026-08-29 (Phase 1, F9). This branch returned "EQ" for everything
    # it could not parse, so an unreadable derivative silently became equity and
    # was given a delivery-value denominator. The comment here used to say
    # "Equity / unknown", which records that the conflation was known.
    #
    # The test is deliberately narrow and provable rather than a general
    # classifier: a symbol that CONTAINS A DIGIT and ENDS IN CE/PE/FUT is not an
    # NSE equity ticker. Real tickers ending in those letters exist (ACE), which
    # is why the digit is required; derivative symbols always carry a strike or
    # an expiry year. Anything else is still EQ, exactly as before.
    #
    # `instrument_type=None` routes these to InstrumentClass.UNKNOWN, whose
    # RiskBasis is non-comparable (F8), so detectors abstain instead of dividing
    # by a delivery value. A wrong UNKNOWN costs an abstention; a wrong EQ costs
    # a false claim — the failure directions are not symmetric.
    upper = symbol.upper()
    looks_derivative = (
        any(ch.isdigit() for ch in upper)
        and (upper.endswith("CE") or upper.endswith("PE") or upper.endswith("FUT"))
    )
    return ParsedSymbol(
        raw=symbol,
        underlying=symbol,
        instrument_type=None if looks_derivative else "EQ",
        expiry_date=None,
        strike=None,
        expiry_key="",
    )


def same_expiry(a: ParsedSymbol, b: ParsedSymbol) -> bool:
    """
    True if two symbols share the same contract expiry.

    Monthlies use "YYYY-MM"; weeklies use "YYYY-MM-DD".
    Strict equality required — mixing monthly vs weekly is a calendar spread, not same expiry.
    """
    return bool(a.expiry_key and b.expiry_key and a.expiry_key == b.expiry_key)


def _last_thursday_of_month(year: int, month: int) -> date:
    """
    Return the NSE monthly F&O expiry date for the given month.

    Normally this is the last Thursday. When the last Thursday is a trading
    holiday, NSE moves expiry one calendar day earlier (usually to Wednesday).
    Walks back until it lands on a trading day.
    """
    import calendar as _cal
    from app.core.market_hours import is_trading_holiday
    last_day = _cal.monthrange(year, month)[1]
    d = date(year, month, last_day)
    while d.weekday() != 3:
        d = date(year, month, d.day - 1)
    # If last Thursday is a holiday, move expiry to prior trading day
    while is_trading_holiday(d):
        d -= timedelta(days=1)
    return d


#: BSE index derivatives (BFO). Their monthly expiry is NOT NSE's last Thursday,
#: and this module cannot establish what it is — see is_expiry_day. Listing them
#: explicitly rather than guessing a rule; the list is not claimed exhaustive.
_BSE_INDEX_UNDERLYINGS = frozenset({"SENSEX", "BANKEX", "SENSEX50"})


def is_expiry_day(symbol: str, trade_date: date) -> bool:
    """
    Return True if trade_date is the expiry date of the given derivative symbol.

    Replaces the hardcoded `entry_ist.weekday() == 3` pattern in behavior_engine.

    Logic:
    - Weekly option (expiry_key is "YYYY-MM-DD"): exact match on expiry_date.
    - Monthly option/future (expiry_key is "YYYY-MM"): compare against
      last Thursday of the contract month (NSE standard monthly expiry).
    - EQ / unknown: returns False.

    Monthly expiry uses _last_thursday_of_month() which already walks back
    past NSE holidays, so holiday-adjusted expiries (e.g. Wednesday when
    last Thursday is a holiday) are handled correctly.

    BSE INDEX MONTHLIES ABSTAIN (Phase 1, F11, 2026-08-29)
    ------------------------------------------------------
    The last-Thursday rule is NSE's. It was applied to every underlying and
    every exchange, so `is_expiry_day("SENSEX25MARFUT", <a Thursday>)` returned
    True — and `exchange_constants` documents in its own comments that BSE runs
    different expiry days (SENSEX weekly on Friday, BANKEX weekly on Monday).

    What is provable is that the NSE rule does not apply to a BSE index. What is
    NOT established here is what the BSE monthly rule IS: this module has no
    exchange parameter, `exchange_constants` records the weekly days only in
    prose, and BSE has revised its expiry days more than once. Inventing a
    weekday would replace a wrong answer with a differently wrong one.

    So a BSE index MONTHLY returns False — no claim — rather than a confident
    wrong True. The consumers are all modifiers (premium_loss_event's +15pp band
    shift, no_stoploss's expiry thresholds, fomo_entry's context note), and not
    applying a leniency is the conservative direction.

    BSE WEEKLIES ARE UNAFFECTED — their symbols carry an exact date, which is
    matched directly and never goes through the monthly path.

    Sourcing the real BFO monthly rule is recorded as a DESIGN item.
    """
    parsed = parse_symbol(symbol)
    if not parsed.expiry_date:
        return False  # EQ or unrecognised

    if len(parsed.expiry_key) == 10:
        # Weekly: "YYYY-MM-DD" — exact date from symbol, exchange-independent
        return parsed.expiry_date == trade_date

    if (parsed.underlying or "").upper() in _BSE_INDEX_UNDERLYINGS:
        return False

    # Monthly: "YYYY-MM" — compute last Thursday of the contract month
    expected_expiry = _last_thursday_of_month(parsed.expiry_date.year, parsed.expiry_date.month)
    return expected_expiry == trade_date
