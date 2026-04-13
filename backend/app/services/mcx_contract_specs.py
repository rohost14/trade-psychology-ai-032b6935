"""
MCX and CDS contract multipliers for correct P&L calculation.

WHY THIS EXISTS
---------------
Zerodha's instruments CSV sets lot_size = 1 for every MCX instrument.
Reference: https://kite.trade/forum/discussion/14531/lot-size-of-all-mcx-instruments-are-1

MCX fill quantities are sent in LOTS (not total units), unlike NSE F&O where
Kite expands the quantity (1 NIFTY lot → qty=50).  This means the P&L formula
for MCX is:

    P&L = (exit_price - entry_price) × qty_in_lots × MCX_MULTIPLIERS[prefix]

The multiplier is the number of price-quotation units per 1 lot.

Example:
  CRUDEOIL  — 100 barrel lot, price per barrel  → multiplier = 100
  GOLD      — 1 kg lot, price per 10 grams      → multiplier = 100  (1 kg = 100×10g)
  GOLDM     — 100 gram lot, price per 10 grams  → multiplier = 10   (100g = 10×10g)
  ZINC      — 5 MT lot, price per kg            → multiplier = 5000 (5 MT = 5000 kg)

SOURCES
-------
- Zerodha Z-Connect: https://zerodha.com/z-connect/general/mcx-profitloss-for-every-1-rs-change
  (P&L-per-₹1-move = multiplier for all contracts listed)
- Dhan MCX lot size chart: https://dhan.co/commodities-lot-size/  (current as of 2024)
- MCX official contract specs: https://mcxindia.com/products/

MAINTENANCE
-----------
MCX rarely revises lot sizes — COPPER changed from 1 MT to 2500 kg in 2022.
MCX announces revisions months in advance in circulars at mcxindia.com.
Update this file when a revision circular is published.
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# MCX contract multipliers
# Key   = symbol prefix (all uppercase letters before the expiry date/digits)
# Value = units of price-quotation per 1 lot  =  P&L per ₹1 price move
# ─────────────────────────────────────────────────────────────────────────────
MCX_MULTIPLIERS: dict[str, int] = {

    # ── Bullion ───────────────────────────────────────────────────────────────
    # Gold price is quoted per 10 grams on MCX
    "GOLD":         100,    # 1 kg lot  = 100 × 10g  → ₹100/₹1 move
    "GOLDM":        10,     # 100 g lot = 10  × 10g  → ₹10/₹1 move
    "GOLDPETAL":    1,      # 1 g lot,  price per 1g → ₹1/₹1 move
    "GOLDPTLDEL":   1,      # Same contract, Delhi delivery variant
    "GOLDGUINEA":   8,      # 8 g lot,  price per 1g → ₹8/₹1 move
    "GOLDTEN":      1,      # 10 g lot, price per 10g → ₹1/₹1 move
    "GOLDGLOBAL":   20,     # 200 g lot = 20 × 10g  → ₹20/₹1 move

    # Silver price is quoted per 1 kg on MCX
    "SILVER":       30,     # 30 kg lot   → ₹30/₹1 move
    "SILVERM":      5,      # 5 kg lot    → ₹5/₹1 move
    "SILVERMIC":    1,      # 1 kg lot    → ₹1/₹1 move
    "SILVER1000":   1,      # 1 kg lot    → ₹1/₹1 move  (alternate delivery)

    # ── Energy ───────────────────────────────────────────────────────────────
    # Crude oil price is per barrel
    "CRUDEOIL":     100,    # 100 barrel lot → ₹100/₹1 move
    "CRUDEOILM":    10,     # 10 barrel lot  → ₹10/₹1 move
    "CRUDEOILMINI": 10,     # Alternate symbol (same contract)
    "BRENTCRUDE":   100,    # 100 barrel lot → ₹100/₹1 move

    # Natural gas price is per mmBtu
    "NATURALGAS":   1250,   # 1250 mmBtu lot → ₹1250/₹1 move
    "NATGASMINI":   250,    # 250  mmBtu lot → ₹250/₹1 move

    # ── Base Metals ──────────────────────────────────────────────────────────
    # All base metal prices are per kg
    "COPPER":       2500,   # 2500 kg lot  (revised from 1 MT in 2022) → ₹2500/₹1
    "COPPERM":      250,    # 250 kg lot   → ₹250/₹1 move
    "ALUMINIUM":    5000,   # 5 MT lot = 5000 kg → ₹5000/₹1 move
    "ALUMINI":      1000,   # 1 MT lot = 1000 kg → ₹1000/₹1 move
    "ZINC":         5000,   # 5 MT lot = 5000 kg → ₹5000/₹1 move
    "ZINCMINI":     1000,   # 1 MT lot = 1000 kg → ₹1000/₹1 move
    "LEAD":         5000,   # 5 MT lot = 5000 kg → ₹5000/₹1 move
    "LEADMINI":     1000,   # 1 MT lot = 1000 kg → ₹1000/₹1 move
    "NICKEL":       250,    # 250 kg lot → ₹250/₹1 move
    "NICKELM":      100,    # 100 kg lot → ₹100/₹1 move
    "STEELREBAR":   5000,   # 5 MT lot = 5000 kg → ₹5000/₹1 move

    # ── Agricultural ─────────────────────────────────────────────────────────
    "MENTHAOIL":    360,    # 360 kg lot, price per kg → ₹360/₹1 move
    "COTTON":       25,     # 25 bales lot, price per bale → ₹25/₹1 move
    "CARDAMOM":     100,    # 100 kg lot, price per kg → ₹100/₹1 move
    # CPO: 10 MT lot, price per 10 kg → 10000 kg / 10 = 1000 units
    "CPO":          1000,   # ₹1000/₹1 move
    # KAPAS: 4 MT = 4000 kg lot, price per 20 kg → 200 units
    "KAPAS":        200,    # ₹200/₹1 move
    "COTTONOIL":    5000,   # 5 MT = 5000 kg, price per kg → ₹5000/₹1

    # ── Electricity ──────────────────────────────────────────────────────────
    "ELECDMBL":     50,     # 50 MWh lot, price per MWh → ₹50/₹1 move
}

# ─────────────────────────────────────────────────────────────────────────────
# CDS (Currency Derivatives) on NSE — segment code "CDS"
# Unlike MCX, Zerodha's instruments CSV *may* have correct lot_size for CDS,
# but we maintain this table as an authoritative fallback.
# Source: NSE contract specifications
# ─────────────────────────────────────────────────────────────────────────────
CDS_MULTIPLIERS: dict[str, int] = {
    "USDINR":   1000,   # 1000 USD per lot, price per USD        → ₹1000/₹1
    "EURINR":   1000,   # 1000 EUR per lot, price per EUR        → ₹1000/₹1
    "GBPINR":   1000,   # 1000 GBP per lot, price per GBP        → ₹1000/₹1
    "JPYINR":   1000,   # 100,000 JPY per lot, price per 100 JPY → ₹1000/₹1
}

# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def _extract_prefix(tradingsymbol: str) -> str:
    """
    Strip expiry date, strike, and option-type suffix to get the instrument prefix.

    Examples:
        GOLDM24AUGFUT     → GOLDM
        CRUDEOIL24SEP     → CRUDEOIL
        NATURALGAS24OCT   → NATURALGAS
        USDINR24OCTFUT    → USDINR
        COPPERM24NOV3CE   → COPPERM  (options)
    """
    m = re.match(r'^([A-Z]+)', tradingsymbol.upper().strip())
    return m.group(1) if m else tradingsymbol.upper()


def get_mcx_multiplier(tradingsymbol: str) -> int:
    """
    Return the P&L multiplier for an MCX futures/options instrument.

    If the symbol is not in the table the function returns 1 and logs a WARNING.
    A multiplier of 1 produces incorrect P&L for unknown MCX contracts — add
    the contract to MCX_MULTIPLIERS when you first see that warning.
    """
    prefix = _extract_prefix(tradingsymbol)
    mult = MCX_MULTIPLIERS.get(prefix)
    if mult is None:
        logger.warning(
            "[mcx_specs] Unknown MCX contract %r (prefix=%r). "
            "P&L will be WRONG. Add it to MCX_MULTIPLIERS in mcx_contract_specs.py. "
            "Reference: https://zerodha.com/z-connect/general/mcx-profitloss-for-every-1-rs-change",
            tradingsymbol, prefix,
        )
        return 1
    return mult


def get_cds_multiplier(tradingsymbol: str) -> int:
    """
    Return the P&L multiplier for a CDS (currency derivatives) instrument.
    Defaults to 1000 — the standard lot size for all NSE CDS pairs.
    """
    prefix = _extract_prefix(tradingsymbol)
    mult = CDS_MULTIPLIERS.get(prefix)
    if mult is None:
        logger.info(
            "[mcx_specs] CDS contract %r not in table — defaulting to 1000 (standard lot).",
            tradingsymbol,
        )
        return 1000
    return mult


def get_lot_multiplier(exchange: str, tradingsymbol: str) -> int:
    """
    Unified entry point: return the correct lot multiplier for any exchange.

    NSE / BSE / NFO / BFO:
        Kite sends fill quantity already expanded to total units
        (e.g. 1 NIFTY lot → qty=50). Multiplier = 1.

    MCX:
        Kite sends fill quantity in LOTS. Multiplier from MCX_MULTIPLIERS.

    CDS:
        Kite sends fill quantity in LOTS. Multiplier from CDS_MULTIPLIERS.
    """
    exch = (exchange or "").upper()
    if exch == "MCX":
        return get_mcx_multiplier(tradingsymbol)
    if exch == "CDS":
        return get_cds_multiplier(tradingsymbol)
    # NSE, BSE, NFO, BFO — quantity already in units
    return 1
