"""
Indian Exchange Market Hours and Codes
======================================
Authoritative reference for all exchanges available on Zerodha KiteConnect.

Exchange codes used by Zerodha (these are the actual values in Trade.exchange):
  NSE   — NSE Equity/Cash segment
  BSE   — BSE Equity/Cash segment
  NFO   — NSE Futures & Options (index + stock derivatives)
  BFO   — BSE Futures & Options (SENSEX, BANKEX derivatives)
  CDS   — NSE Currency Derivatives
  BCD   — BSE Currency Derivatives
  MCX   — Multi Commodity Exchange (metals, energy, agri)
  MCXSX — Legacy MCX-SX (merged into BSE for currency; no longer active)

Market hours are IST (Asia/Kolkata, UTC+5:30), Monday–Friday.
These hours do NOT account for exchange-declared holidays or special sessions
(Muhurat trading, budget day short sessions, etc.).
For behavioral alert gating, this is accurate enough — holiday suppression
would require a live holiday calendar lookup and is not worth the complexity.

Sources:
  NSE/BSE equity/F&O: NSE circular NSE/MSD/52994; BSE circular 20230101-7
  MCX: MCX circular MCX/CS/178/2023 and MCX website
  Currency: SEBI circular CIR/MRD/DRMNP/26/2013

MCX note: Non-agri commodities (metals: Gold, Silver, Copper, Zinc, Lead,
  Nickel, Aluminium; energy: Crude Oil, Natural Gas) trade until 23:30 IST.
  Agri commodities (Castor Seed, Cardamom, Mentha Oil, CPO, Cottonseed,
  Kapas, Rubber, Pepper, Guar) close at 17:00 IST.
  We use 23:30 for ALL MCX (conservative — never wrongly suppresses a
  metals/energy trader working the legitimate evening session; an agri
  trader at 22:00 is an edge case we can tolerate).
"""

from datetime import datetime, time
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


# ---------------------------------------------------------------------------
# Exchange definitions
# ---------------------------------------------------------------------------
EXCHANGES: dict[str, dict] = {
    "NSE": {
        "name": "National Stock Exchange",
        "full_name": "NSE Equity Cash Segment",
        "description": "NSE equity / cash — stocks, ETFs, sovereign gold bonds",
        "segment": "Equity",
        "instruments": ["EQ", "BE", "SM"],   # BE = Book Entry (T+0); SM = SME IPO
        "open_time":   time(9, 15),
        "close_time":  time(15, 30),
        "pre_open":    time(9, 0),            # Call auction 09:00–09:15, no continuous executions
    },
    "BSE": {
        "name": "Bombay Stock Exchange",
        "full_name": "BSE Equity Cash Segment",
        "description": "BSE equity / cash — stocks, ETFs, mutual fund units",
        "segment": "Equity",
        "instruments": ["EQ", "BE", "SM"],
        "open_time":   time(9, 15),
        "close_time":  time(15, 30),
        "pre_open":    time(9, 0),
    },
    "NFO": {
        "name": "NSE Futures & Options",
        "full_name": "NSE Futures & Options Segment",
        "description": (
            "NSE derivatives — index futures/options (NIFTY 50, BANK NIFTY, "
            "FINNIFTY, MIDCPNIFTY, NIFTY IT) and single-stock F&O. "
            "Weekly and monthly expiry contracts."
        ),
        "segment": "F&O",
        "instruments": ["FUT", "CE", "PE"],
        "open_time":   time(9, 15),
        "close_time":  time(15, 30),
        "pre_open":    None,
        # Weekly expiry: every Thursday (index options); monthly: last Thursday of month
        # Expiry day trading continues until 15:30 — no special close time
    },
    "BFO": {
        "name": "BSE Futures & Options",
        "full_name": "BSE Futures & Options Segment",
        "description": (
            "BSE derivatives — SENSEX futures/options (BSE Sensex 30 index), "
            "BANKEX futures/options (BSE banking index). "
            "Weekly and monthly expiry contracts."
        ),
        "segment": "F&O",
        "instruments": ["FUT", "CE", "PE"],
        "open_time":   time(9, 15),
        "close_time":  time(15, 30),
        "pre_open":    None,
        # SENSEX weekly expiry: every Friday
        # BANKEX weekly expiry: every Monday
    },
    "CDS": {
        "name": "NSE Currency Derivatives",
        "full_name": "NSE Currency Derivatives Segment",
        "description": (
            "NSE currency F&O — USDINR, EURINR, GBPINR, JPYINR "
            "(futures and options). Extended session vs equity."
        ),
        "segment": "Currency",
        "instruments": ["FUT", "CE", "PE"],
        "open_time":   time(9, 0),
        "close_time":  time(17, 0),
        "pre_open":    None,
    },
    "BCD": {
        "name": "BSE Currency Derivatives",
        "full_name": "BSE Currency Derivatives Segment",
        "description": "BSE currency derivatives — parallel to CDS, lower liquidity",
        "segment": "Currency",
        "instruments": ["FUT", "CE", "PE"],
        "open_time":   time(9, 0),
        "close_time":  time(17, 0),
        "pre_open":    None,
    },
    "MCX": {
        "name": "Multi Commodity Exchange",
        "full_name": "MCX Commodity Derivatives",
        "description": (
            "MCX commodity futures and options. "
            "Non-agri metals (Gold, GoldM, GoldPetal, Silver, SilverM, SilverMic, "
            "Copper, Zinc, Lead, Nickel, Aluminium) and energy (CrudeOil, CrudeOilM, "
            "NaturalGas, NaturalGasMini) trade 09:00–23:30 IST. "
            "Agri commodities (Castorseed, Cardamom, MenthOil, CPO, "
            "CottonseedOilcake, Kapas, Rubber, Pepper, GuarSeed, GuarGum) "
            "trade 09:00–17:00 IST. "
            "Using 23:30 as effective close for ALL MCX in this codebase."
        ),
        "segment": "Commodity",
        "instruments": ["FUT", "CE", "PE"],
        "open_time":   time(9, 0),
        "close_time":  time(23, 30),
        "pre_open":    None,
        # NON-AGRI commodities traded on MCX (trade until 23:30 IST):
        #   Metals: GOLD, GOLDM, GOLDPETAL, SILVER, SILVERM, SILVERMIC,
        #           COPPER, ZINC, LEAD, NICKEL, ALUMINIUM
        #   Energy: CRUDEOIL, CRUDEOILM, NATURALGAS, NATURALGASM
        # AGRI commodities (technically close at 17:00 but using 23:30 as ceiling):
        #   CASTORSEED, CARDAMOM, MENTHAOIL, CPO, COTTONSEED,
        #   KAPAS, RUBBER, PEPPER, GUARSEED, GUARGUM
    },
    "MCXSX": {
        "name": "MCX-SX (legacy)",
        "full_name": "MCX Stock Exchange — Currency Segment (legacy)",
        "description": (
            "MCX-SX was a separate exchange for currency derivatives. "
            "Merged into BSE's currency segment; no longer active. "
            "Kept for backward-compatibility with historical trade data."
        ),
        "segment": "Currency",
        "instruments": ["FUT", "CE", "PE"],
        "open_time":   time(9, 0),
        "close_time":  time(17, 0),
        "pre_open":    None,
    },
}


# ---------------------------------------------------------------------------
# Market hours helper
# ---------------------------------------------------------------------------

def is_market_open(exchange: str, dt: datetime | None = None) -> bool:
    """
    Return True if the exchange is in its active trading session at `dt`.
    Defaults to now (IST). Weekends always return False.
    Does NOT account for exchange holidays or special sessions.

    Usage:
        from app.core.exchange_constants import is_market_open
        if is_market_open("NFO"):
            ...  # alert is actionable right now
    """
    if dt is None:
        dt = datetime.now(IST)
    elif dt.tzinfo is None:
        dt = dt.replace(tzinfo=IST)
    else:
        dt = dt.astimezone(IST)

    # Weekends: Saturday=5, Sunday=6
    if dt.weekday() >= 5:
        return False

    info = EXCHANGES.get(exchange.upper())
    if not info:
        # Unknown exchange — fall back to NSE hours as a safe default
        return time(9, 15) <= dt.time() <= time(15, 30)

    return info["open_time"] <= dt.time() <= info["close_time"]


def get_close_time(exchange: str) -> time:
    """Return the market close time (IST) for an exchange."""
    info = EXCHANGES.get(exchange.upper(), {})
    return info.get("close_time", time(15, 30))


def get_open_time(exchange: str) -> time:
    """Return the market open time (IST) for an exchange."""
    info = EXCHANGES.get(exchange.upper(), {})
    return info.get("open_time", time(9, 15))
