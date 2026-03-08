from typing import Dict, Any
from app.core.market_hours import MarketSegment, get_segment_from_exchange


def classify_trade(trade_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Classify trade based on exchange and symbol.

    Supports all Indian market segments:
    - EQUITY: NSE, BSE cash segment
    - FNO: NSE F&O, BSE F&O (NFO, BFO)
    - COMMODITY: MCX, NCDEX
    - CURRENCY: CDS (Currency Derivatives)

    Examples:
    - NIFTY25JANFUT on NFO -> FNO, FUTURE, NRML
    - NIFTY 18500 CE on NFO -> FNO, OPTION, NRML
    - RELIANCE on NSE -> EQUITY, SPOT, CNC
    - GOLDM FEB FUT on MCX -> COMMODITY, FUTURE, NRML
    - USDINR FEB FUT on CDS -> CURRENCY, FUTURE, NRML
    """
    exchange = trade_data.get("exchange", "UNKNOWN").upper()
    symbol = trade_data.get("tradingsymbol", "").upper()
    product = trade_data.get("product", "")

    # 1. Get Market Segment from exchange
    segment = get_segment_from_exchange(exchange)
    asset_class = segment.value

    # 2. Instrument Type based on symbol patterns
    # Option CE/PE check only applies to F&O exchanges — NSE/BSE equities like
    # "RELIANCE" or "PACE" end in CE/PE but are NOT options.
    FNO_EXCHANGES = {"NFO", "BFO", "MCX", "NCDEX", "CDS"}
    is_fno_exchange = exchange in FNO_EXCHANGES

    if is_fno_exchange and (
        symbol.endswith("CE") or symbol.endswith("PE")
        or " CE" in symbol or " PE" in symbol
    ):
        instrument_type = "OPTION"
    elif any(x in symbol for x in ["FUT", "FUTURE"]):
        instrument_type = "FUTURE"
    elif exchange in ["NFO", "BFO"]:
        # F&O exchange but not option - likely future
        instrument_type = "FUTURE"
    elif exchange in ["MCX", "NCDEX"]:
        # Commodity - check for month codes indicating futures
        month_codes = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
                       "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
        if any(month in symbol for month in month_codes):
            instrument_type = "FUTURE"
        else:
            instrument_type = "SPOT"
    elif exchange == "CDS":
        # Currency derivatives - typically futures
        instrument_type = "FUTURE"
    else:
        instrument_type = "SPOT"

    # 3. Product Type (MIS = Intraday, CNC = Delivery, NRML = F&O Normal)
    product_type = product.upper() if product else "NRML"

    return {
        "asset_class": asset_class,
        "instrument_type": instrument_type,
        "product_type": product_type,
        "segment": asset_class,  # Alias for clarity
    }
