from typing import Dict, Any

def classify_trade(trade_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Classify trade based on exchange and symbol.
    
    Examples:
    - NIFTY25JANFUT on NFO -> EQUITY, FUTURE, NRML
    - NIFTY 18500 CE on NFO -> EQUITY, OPTION, NRML
    - RELIANCE on NSE -> EQUITY, SPOT, CNC
    - GOLDM FEB FUT on MCX -> COMMODITY, FUTURE, NRML
    """
    exchange = trade_data.get("exchange", "UNKNOWN")
    symbol = trade_data.get("tradingsymbol", "")
    product = trade_data.get("product", "")
    
    # 1. Asset Class
    if exchange in ["NSE", "BSE", "NFO", "BFO"]:
        asset_class = "EQUITY"
    elif exchange == "MCX":
        asset_class = "COMMODITY"
    elif exchange == "CDS":
        asset_class = "FOREX"
    else:
        asset_class = "UNKNOWN"
        
    # 2. Instrument Type
    if symbol.endswith("CE") or symbol.endswith("PE"):
        instrument_type = "OPTION"
    elif exchange in ["NFO", "BFO", "MCX", "CDS"]:
        instrument_type = "FUTURE"
    else:
        instrument_type = "SPOT"
        
    # 3. Product Type
    product_type = product
    
    return {
        "asset_class": asset_class,
        "instrument_type": instrument_type,
        "product_type": product_type
    }
