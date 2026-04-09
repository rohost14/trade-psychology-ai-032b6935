"""
Market Hours Configuration for Indian Markets

Supports all segments:
- NSE/BSE Equity: 9:15 AM - 3:30 PM
- NSE/BSE F&O: 9:15 AM - 3:30 PM
- MCX Commodity: 9:00 AM - 11:30 PM (next day for different commodities)
- Currency (CDS): 9:00 AM - 5:00 PM
"""

from datetime import datetime, time, date, timezone, timedelta
from typing import Dict, Optional, Tuple, Set
from enum import Enum
import pytz

IST = pytz.timezone('Asia/Kolkata')

# ---------------------------------------------------------------------------
# NSE/BSE Trading Holidays
# Source: NSE official holiday list. Update annually from:
#   https://www.nseindia.com/resources/exchange-communication-holidays
#
# To override at runtime (e.g., unscheduled closures), set NSE_EXTRA_HOLIDAYS
# in .env as a comma-separated list of YYYY-MM-DD dates.
# ---------------------------------------------------------------------------
NSE_HOLIDAYS_2025: Set[date] = {
    date(2025, 2, 26),   # Mahashivratri
    date(2025, 3, 14),   # Holi
    date(2025, 3, 31),   # Id-Ul-Fitr (Ramadan Eid) — tentative, moon-sighting
    date(2025, 4, 14),   # Dr. Baba Saheb Ambedkar Jayanti / Ram Navami
    date(2025, 4, 18),   # Good Friday
    date(2025, 5, 1),    # Maharashtra Day
    date(2025, 8, 15),   # Independence Day
    date(2025, 8, 27),   # Ganesh Chaturthi
    date(2025, 10, 2),   # Mahatma Gandhi Jayanti
    date(2025, 10, 21),  # Diwali Laxmi Pujan (Muhurat Trading session — NOT regular trading)
    date(2025, 10, 22),  # Diwali Balipratipada
    date(2025, 11, 5),   # Guru Nanak Jayanti
    date(2025, 12, 25),  # Christmas
}

NSE_HOLIDAYS_2026: Set[date] = {
    date(2026, 1, 26),   # Republic Day
    date(2026, 3, 20),   # Holi (approx)
    date(2026, 4, 3),    # Good Friday (approx)
    date(2026, 8, 15),   # Independence Day
    date(2026, 10, 2),   # Mahatma Gandhi Jayanti
    date(2026, 12, 25),  # Christmas
}

# Combined holiday set — all years known
NSE_HOLIDAYS: Set[date] = NSE_HOLIDAYS_2025 | NSE_HOLIDAYS_2026


def _load_extra_holidays() -> Set[date]:
    """Load any extra/unscheduled holidays from NSE_EXTRA_HOLIDAYS env var."""
    try:
        import os
        extra = os.environ.get("NSE_EXTRA_HOLIDAYS", "")
        result: Set[date] = set()
        for s in extra.split(","):
            s = s.strip()
            if s:
                result.add(date.fromisoformat(s))
        return result
    except Exception:
        return set()


def is_trading_holiday(check_date: date) -> bool:
    """Return True if check_date is a NSE/BSE trading holiday."""
    all_holidays = NSE_HOLIDAYS | _load_extra_holidays()
    return check_date in all_holidays


class MarketSegment(str, Enum):
    EQUITY = "EQUITY"           # NSE, BSE cash
    FNO = "FNO"                 # NSE F&O, BSE F&O
    COMMODITY = "COMMODITY"     # MCX, NCDEX
    CURRENCY = "CURRENCY"       # NSE CDS, BSE CDS


class Exchange(str, Enum):
    NSE = "NSE"
    BSE = "BSE"
    NFO = "NFO"         # NSE F&O
    BFO = "BFO"         # BSE F&O
    MCX = "MCX"         # Multi Commodity Exchange
    NCDEX = "NCDEX"     # National Commodity & Derivatives Exchange
    CDS = "CDS"         # Currency Derivatives


# Market hours configuration (IST)
MARKET_HOURS: Dict[MarketSegment, Dict[str, time]] = {
    MarketSegment.EQUITY: {
        "open": time(9, 15),
        "close": time(15, 30),
        "pre_open_start": time(9, 0),
        "pre_open_end": time(9, 8),
    },
    MarketSegment.FNO: {
        "open": time(9, 15),
        "close": time(15, 30),
        "pre_open_start": time(9, 0),
        "pre_open_end": time(9, 8),
    },
    MarketSegment.COMMODITY: {
        "open": time(9, 0),
        "close": time(23, 30),  # 11:30 PM
        # Note: Some commodities have different sessions
        # Morning: 9:00 AM - 5:00 PM
        # Evening: 5:00 PM - 11:30 PM (11:55 PM for some)
    },
    MarketSegment.CURRENCY: {
        "open": time(9, 0),
        "close": time(17, 0),  # 5:00 PM
    },
}

# Exchange to segment mapping
EXCHANGE_SEGMENT_MAP: Dict[str, MarketSegment] = {
    "NSE": MarketSegment.EQUITY,
    "BSE": MarketSegment.EQUITY,
    "NFO": MarketSegment.FNO,
    "BFO": MarketSegment.FNO,
    "MCX": MarketSegment.COMMODITY,
    "NCDEX": MarketSegment.COMMODITY,
    "CDS": MarketSegment.CURRENCY,
}

# High-risk time windows (segment-specific)
HIGH_RISK_WINDOWS: Dict[MarketSegment, list] = {
    MarketSegment.EQUITY: [
        {"start": time(9, 15), "end": time(9, 30), "name": "Market Open Volatility"},
        {"start": time(15, 0), "end": time(15, 30), "name": "Market Close Rush"},
    ],
    MarketSegment.FNO: [
        {"start": time(9, 15), "end": time(9, 30), "name": "F&O Open Volatility"},
        {"start": time(15, 0), "end": time(15, 30), "name": "Expiry/Close Rush"},
    ],
    MarketSegment.COMMODITY: [
        {"start": time(9, 0), "end": time(9, 15), "name": "Commodity Open"},
        {"start": time(17, 0), "end": time(17, 30), "name": "Evening Session Start"},
        {"start": time(23, 0), "end": time(23, 30), "name": "Commodity Close Rush"},
    ],
    MarketSegment.CURRENCY: [
        {"start": time(9, 0), "end": time(9, 15), "name": "Currency Open"},
        {"start": time(16, 30), "end": time(17, 0), "name": "Currency Close"},
    ],
}


def get_segment_from_exchange(exchange: str) -> MarketSegment:
    """Get market segment from exchange code."""
    return EXCHANGE_SEGMENT_MAP.get(exchange.upper(), MarketSegment.EQUITY)


def get_market_hours(segment: MarketSegment) -> Tuple[time, time]:
    """Get market open and close times for a segment."""
    hours = MARKET_HOURS.get(segment, MARKET_HOURS[MarketSegment.EQUITY])
    return hours["open"], hours["close"]


def is_market_open(segment: MarketSegment, check_time: Optional[datetime] = None) -> bool:
    """Check if market is currently open for the given segment."""
    if check_time is None:
        check_time = datetime.now(IST)
    elif check_time.tzinfo is None:
        check_time = IST.localize(check_time)
    else:
        check_time = check_time.astimezone(IST)

    # Weekend check
    if check_time.weekday() >= 5:  # Saturday = 5, Sunday = 6
        return False

    # Holiday check (NSE/BSE scheduled + any extra holidays in env)
    if is_trading_holiday(check_time.date()):
        return False

    current_time = check_time.time()
    open_time, close_time = get_market_hours(segment)

    # Handle commodity market which can cross midnight
    if segment == MarketSegment.COMMODITY:
        # Commodity market: 9:00 AM to 11:30 PM (same day)
        return open_time <= current_time <= close_time

    return open_time <= current_time <= close_time


def market_minutes(
    entry_dt: datetime,
    exit_dt: datetime,
    exchange: str = "NFO",
) -> int:
    """
    Return actual trading minutes between two datetimes.

    Strips overnight gaps, weekends, and NSE/BSE holidays — so a 4-day NRML
    hold reports ~1,500 minutes (actual exposure) not ~5,760 minutes (wall-clock).

    Uses the exchange's trading window from MARKET_HOURS.
    Falls back to NSE/NFO hours (9:15–15:30) for unknown exchanges.
    Returns at least 1 (zero-duration trades are still 1 minute).
    """
    if not entry_dt or not exit_dt or exit_dt <= entry_dt:
        return 1

    segment = get_segment_from_exchange(exchange)
    market_open, market_close = get_market_hours(segment)

    entry_ist = entry_dt.astimezone(IST)
    exit_ist  = exit_dt.astimezone(IST)

    total = 0
    current_date = entry_ist.date()

    while current_date <= exit_ist.date():
        # Skip weekends and holidays
        if current_date.weekday() < 5 and not is_trading_holiday(current_date):
            day_open  = IST.localize(datetime.combine(current_date, market_open))
            day_close = IST.localize(datetime.combine(current_date, market_close))

            # Clamp to the actual entry/exit on their respective days
            period_start = max(entry_ist, day_open)  if current_date == entry_ist.date() else day_open
            period_end   = min(exit_ist,  day_close) if current_date == exit_ist.date()  else day_close

            if period_end > period_start:
                total += int((period_end - period_start).total_seconds() / 60)

        current_date += timedelta(days=1)

    return max(1, total)


def is_high_risk_window(segment: MarketSegment, check_time: Optional[datetime] = None) -> Tuple[bool, Optional[str]]:
    """Check if current time is in a high-risk trading window."""
    if check_time is None:
        check_time = datetime.now(IST)
    elif check_time.tzinfo is None:
        check_time = IST.localize(check_time)
    else:
        check_time = check_time.astimezone(IST)

    current_time = check_time.time()
    windows = HIGH_RISK_WINDOWS.get(segment, [])

    for window in windows:
        if window["start"] <= current_time <= window["end"]:
            return True, window["name"]

    return False, None


def get_trading_session(segment: MarketSegment, check_time: Optional[datetime] = None) -> str:
    """Get current trading session name."""
    if check_time is None:
        check_time = datetime.now(IST)
    elif check_time.tzinfo is None:
        check_time = IST.localize(check_time)
    else:
        check_time = check_time.astimezone(IST)

    current_time = check_time.time()

    if segment == MarketSegment.COMMODITY:
        if time(9, 0) <= current_time < time(17, 0):
            return "Morning Session"
        elif time(17, 0) <= current_time <= time(23, 30):
            return "Evening Session"
        else:
            return "Market Closed"

    open_time, close_time = get_market_hours(segment)

    if current_time < open_time:
        return "Pre-Market"
    elif open_time <= current_time < time(12, 0):
        return "Morning Session"
    elif time(12, 0) <= current_time < time(14, 0):
        return "Afternoon Session"
    elif time(14, 0) <= current_time <= close_time:
        return "Closing Session"
    else:
        return "Post-Market"


def get_allowed_trading_hours(segment: MarketSegment) -> Dict[str, str]:
    """Get allowed trading hours as strings for goals."""
    hours = MARKET_HOURS.get(segment, MARKET_HOURS[MarketSegment.EQUITY])
    return {
        "start": hours["open"].strftime("%H:%M"),
        "end": hours["close"].strftime("%H:%M"),
    }


# Helper for trade classifier
def classify_segment_from_symbol(tradingsymbol: str, exchange: str) -> Dict[str, str]:
    """
    Classify trading segment from symbol and exchange.

    Returns:
        Dict with asset_class, instrument_type, segment
    """
    segment = get_segment_from_exchange(exchange)

    # Determine instrument type from symbol patterns
    symbol_upper = tradingsymbol.upper()

    if any(x in symbol_upper for x in ["CE", "PE"]):
        instrument_type = "OPTION"
    elif any(x in symbol_upper for x in ["FUT", "FUTURE"]):
        instrument_type = "FUTURE"
    elif exchange in ["MCX", "NCDEX"]:
        # Commodities - check for month codes
        if any(month in symbol_upper for month in ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
                                                     "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]):
            instrument_type = "FUTURE"
        else:
            instrument_type = "SPOT"
    else:
        instrument_type = "SPOT"

    return {
        "asset_class": segment.value,
        "instrument_type": instrument_type,
        "segment": segment.value,
    }


def get_session_boundaries(
    segment: MarketSegment = MarketSegment.FNO,
    for_date: Optional[date] = None,
) -> Tuple[datetime, datetime]:
    """
    Get trading session start/end as UTC datetimes for a given date.

    Session = market open to market close in IST, converted to UTC.

    ALL services MUST use this for session P&L calculations.
    Session P&L = realized P&L only.
    Unrealized P&L is used ONLY for live risk checks, not session totals.

    Args:
        segment: Market segment (default FNO for F&O traders)
        for_date: Date in IST to get session for (default: today IST)

    Returns:
        Tuple of (session_start_utc, session_end_utc)
    """
    if for_date is None:
        for_date = datetime.now(IST).date()

    open_time, close_time = get_market_hours(segment)

    session_start_ist = IST.localize(datetime.combine(for_date, open_time))
    session_end_ist = IST.localize(datetime.combine(for_date, close_time))

    return (
        session_start_ist.astimezone(timezone.utc),
        session_end_ist.astimezone(timezone.utc),
    )
