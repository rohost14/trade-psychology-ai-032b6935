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
from datetime import date
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

# Monthly option: NIFTY25MAR25000CE  /  BANKNIFTY25APR48000PE
_RE_MONTHLY_OPT = re.compile(
    r"^([A-Z&]+)(\d{2})(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)(\d{3,6})(CE|PE)$"
)

# Monthly future: BANKNIFTY25APRFUT  /  NIFTY25MARFUT
_RE_MONTHLY_FUT = re.compile(
    r"^([A-Z&]+)(\d{2})(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)FUT$"
)

# Weekly option: NIFTY2532025000CE  (yy + single-month-char + 2-digit-day)
_RE_WEEKLY_OPT = re.compile(
    r"^([A-Z&]+)(\d{2})([1-9ONDond])(\d{2})(\d{3,6})(CE|PE)$"
)


# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------

@dataclass
class ParsedSymbol:
    raw: str
    underlying: str            # NIFTY, BANKNIFTY, RELIANCE …
    instrument_type: str       # CE | PE | FUT | EQ
    expiry_date: Optional[date]
    strike: Optional[int]      # option strike price
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
            strike=int(strike_str),
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
            strike=int(strike_str),
            expiry_key=expiry_key,
        )

    # 4. Equity / unknown
    return ParsedSymbol(
        raw=symbol,
        underlying=symbol,
        instrument_type="EQ",
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
    Return the last Thursday of the given month.

    This is the default NSE monthly F&O expiry date when there is no holiday.
    A full trading-calendar integration would adjust for holidays, but this is
    dramatically more accurate than hardcoding weekday() == 3.
    """
    import calendar as _cal
    # Find the last day of the month
    last_day = _cal.monthrange(year, month)[1]
    d = date(year, month, last_day)
    # Walk backwards until we hit Thursday (weekday 3)
    while d.weekday() != 3:
        d = date(year, month, d.day - 1)
    return d


def is_expiry_day(symbol: str, trade_date: date) -> bool:
    """
    Return True if trade_date is the expiry date of the given derivative symbol.

    Replaces the hardcoded `entry_ist.weekday() == 3` pattern in behavior_engine.

    Logic:
    - Weekly option (expiry_key is "YYYY-MM-DD"): exact match on expiry_date.
    - Monthly option/future (expiry_key is "YYYY-MM"): compare against
      last Thursday of the contract month (NSE standard monthly expiry).
    - EQ / unknown: returns False.

    NOTE: Does not account for NSE holiday adjustments. When the last Thursday
    is a market holiday, NSE moves expiry to Wednesday. To handle this correctly
    a trading calendar API or a maintained holiday list is needed. This is still
    far more accurate than hardcoded Thursday (weekday==3) which fires on EVERY
    Thursday regardless of whether it is an expiry.
    """
    parsed = parse_symbol(symbol)
    if not parsed.expiry_date:
        return False  # EQ or unrecognised

    if len(parsed.expiry_key) == 10:
        # Weekly: "YYYY-MM-DD" — exact date from symbol
        return parsed.expiry_date == trade_date

    # Monthly: "YYYY-MM" — compute last Thursday of the contract month
    expected_expiry = _last_thursday_of_month(parsed.expiry_date.year, parsed.expiry_date.month)
    return expected_expiry == trade_date
