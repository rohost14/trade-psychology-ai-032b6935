/**
 * Indian Exchange Market Hours and Zerodha Symbol Parser
 * =======================================================
 * Authoritative reference matching backend/app/core/exchange_constants.py
 *
 * Exchange codes (exact values from Trade.exchange in Zerodha API):
 *   NSE   — NSE Equity/Cash segment (stocks, ETFs)
 *   BSE   — BSE Equity/Cash segment (stocks, ETFs)
 *   NFO   — NSE F&O: NIFTY, BANKNIFTY, FINNIFTY, MIDCPNIFTY, stock F&O
 *   BFO   — BSE F&O: SENSEX options/futures, BANKEX options/futures
 *   CDS   — NSE Currency Derivatives (USDINR, EURINR, GBPINR, JPYINR)
 *   BCD   — BSE Currency Derivatives
 *   MCX   — Multi Commodity Exchange (metals, energy, agri)
 *   MCXSX — Legacy MCX-SX (merged into BSE; historical data only)
 *
 * Zerodha tradingsymbol formats:
 *   Monthly options:  SYMBOL + YY + MMM + STRIKE + CE/PE  (e.g., NIFTY25MAR22000CE)
 *   Monthly futures:  SYMBOL + YY + MMM + FUT              (e.g., NIFTY25MARFUT)
 *   Weekly options:   SYMBOL + YY + M + DD + STRIKE + CE/PE (e.g., NIFTY2531922000CE)
 *     Weekly month codes: 1–9 = Jan–Sep, O = Oct, N = Nov, D = Dec
 *   Equity:           Plain ticker                          (e.g., RELIANCE, INFY)
 *   MCX futures:      SYMBOL + YY + MMM + FUT               (e.g., CRUDEOIL25MARFUT)
 */

// ---------------------------------------------------------------------------
// Exchange market hours (IST, Mon–Fri; holidays not accounted for)
// ---------------------------------------------------------------------------

export interface ExchangeInfo {
  name: string;
  segment: 'Equity' | 'F&O' | 'Currency' | 'Commodity';
  openHour: number;   // IST hour (24h)
  openMin: number;
  closeHour: number;
  closeMin: number;
}

export const EXCHANGES: Record<string, ExchangeInfo> = {
  NSE:   { name: 'NSE Equity',              segment: 'Equity',    openHour: 9,  openMin: 15, closeHour: 15, closeMin: 30 },
  BSE:   { name: 'BSE Equity',              segment: 'Equity',    openHour: 9,  openMin: 15, closeHour: 15, closeMin: 30 },
  NFO:   { name: 'NSE F&O',                 segment: 'F&O',       openHour: 9,  openMin: 15, closeHour: 15, closeMin: 30 },
  BFO:   { name: 'BSE F&O (SENSEX/BANKEX)', segment: 'F&O',       openHour: 9,  openMin: 15, closeHour: 15, closeMin: 30 },
  CDS:   { name: 'NSE Currency',            segment: 'Currency',  openHour: 9,  openMin: 0,  closeHour: 17, closeMin: 0  },
  BCD:   { name: 'BSE Currency',            segment: 'Currency',  openHour: 9,  openMin: 0,  closeHour: 17, closeMin: 0  },
  MCX:   { name: 'MCX Commodity',           segment: 'Commodity', openHour: 9,  openMin: 0,  closeHour: 23, closeMin: 30 },
  // MCX note: Non-agri metals & energy trade until 23:30; agri until 17:00.
  // Using 23:30 for all MCX — never wrongly suppresses a metals/energy alert.
  MCXSX: { name: 'MCX-SX (legacy)',         segment: 'Currency',  openHour: 9,  openMin: 0,  closeHour: 17, closeMin: 0  },
};

/**
 * Returns true if the given exchange is currently in its trading session (IST).
 * Weekends always return false. Holidays not accounted for.
 */
export function isMarketOpen(exchange: string): boolean {
  const info = EXCHANGES[exchange?.toUpperCase()];

  // Compute current IST time without importing a library
  const now = new Date();
  const istOffset = 5 * 60 + 30; // IST = UTC+5:30 in minutes
  const utcMinutes = now.getUTCHours() * 60 + now.getUTCMinutes();
  const istMinutes = (utcMinutes + istOffset) % (24 * 60);
  // Day of week in IST
  const utcMs = now.getTime();
  const istMs = utcMs + istOffset * 60 * 1000;
  const istDate = new Date(istMs);
  const dayOfWeek = istDate.getUTCDay(); // 0=Sun, 6=Sat

  if (dayOfWeek === 0 || dayOfWeek === 6) return false;

  if (!info) {
    // Unknown exchange — default to NSE hours
    return istMinutes >= 9 * 60 + 15 && istMinutes <= 15 * 60 + 30;
  }

  const openMinutes  = info.openHour  * 60 + info.openMin;
  const closeMinutes = info.closeHour * 60 + info.closeMin;
  return istMinutes >= openMinutes && istMinutes <= closeMinutes;
}


// ---------------------------------------------------------------------------
// Zerodha tradingsymbol parser
// ---------------------------------------------------------------------------

const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const MONTH_3LETTER = ['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC'];

// Weekly option month codes: single char → 0-based month index
const WEEKLY_MONTH_CODE: Record<string, number> = {
  '1': 0, '2': 1, '3': 2, '4': 3, '5': 4, '6': 5,
  '7': 6, '8': 7, '9': 8, 'O': 9, 'N': 10, 'D': 11,
};

export interface ParsedSymbol {
  underlying: string;     // NIFTY, BANKNIFTY, SENSEX, CRUDEOIL, RELIANCE, etc.
  expiry?: string;        // "Mar 19"  (weekly) | "Mar '25" (monthly)
  strike?: number;        // 22000
  optionType?: 'CE' | 'PE';
  isFuture?: boolean;
  isWeekly?: boolean;
}

// Patterns ordered by specificity: monthly options first, then monthly futures, then weekly.
const MONTHLY_OPTION_RE = /^([A-Z&]+?)(\d{2})(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)(\d+)(CE|PE)$/;
const MONTHLY_FUTURE_RE = /^([A-Z&]+?)(\d{2})(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)FUT$/;
const WEEKLY_OPTION_RE  = /^([A-Z&]+?)(\d{2})([1-9ONDond])(\d{2})(\d+)(CE|PE)$/;

export function parseZerodhaSymbol(sym: string): ParsedSymbol {
  const s = sym.trim().toUpperCase();

  // 1. Monthly option: NIFTY25MAR22000CE, SENSEX25MAR74000PE, CRUDEOIL25MAR6000CE
  const mo = MONTHLY_OPTION_RE.exec(s);
  if (mo) {
    const [, underlying, , mon, strike, type] = mo;
    const monIdx = MONTH_3LETTER.indexOf(mon);
    const yy = mo[2];
    return {
      underlying,
      expiry: `${MONTH_NAMES[monIdx]} '${yy}`,
      strike: parseInt(strike, 10),
      optionType: type as 'CE' | 'PE',
      isFuture: false,
      isWeekly: false,
    };
  }

  // 2. Monthly future: NIFTY25MARFUT, CRUDEOIL25MARFUT, RELIANCE25MARFUT
  const mf = MONTHLY_FUTURE_RE.exec(s);
  if (mf) {
    const [, underlying, yy, mon] = mf;
    const monIdx = MONTH_3LETTER.indexOf(mon);
    return {
      underlying,
      expiry: `${MONTH_NAMES[monIdx]} '${yy}`,
      isFuture: true,
      isWeekly: false,
    };
  }

  // 3. Weekly option: NIFTY2531922000CE, SENSEX2631974800PE, BANKNIFTY2531954000CE
  const wo = WEEKLY_OPTION_RE.exec(s);
  if (wo) {
    const [, underlying, , mCode, dd, strike, type] = wo;
    const monIdx = WEEKLY_MONTH_CODE[mCode.toUpperCase()] ?? 0;
    return {
      underlying,
      expiry: `${MONTH_NAMES[monIdx]} ${parseInt(dd, 10)}`,
      strike: parseInt(strike, 10),
      optionType: type as 'CE' | 'PE',
      isFuture: false,
      isWeekly: true,
    };
  }

  // 4. Plain equity / unrecognized
  return { underlying: s };
}

/**
 * Format a Zerodha tradingsymbol for human-readable display.
 *
 * Returns:
 *   primary  — the main label (e.g., "SENSEX 74,800 PE" or "NIFTY FUT")
 *   secondary — expiry/date label (e.g., "Mar 19" or "Mar '25"), or undefined for equity
 *
 * Examples:
 *   SENSEX2631974800PE → { primary: "SENSEX 74,800 PE", secondary: "Mar 19" }
 *   NIFTY25MAR22000CE  → { primary: "NIFTY 22,000 CE",  secondary: "Mar '25" }
 *   NIFTY25MARFUT      → { primary: "NIFTY FUT",         secondary: "Mar '25" }
 *   RELIANCE           → { primary: "RELIANCE" }
 *   CRUDEOIL25MARFUT   → { primary: "CRUDEOIL FUT",      secondary: "Mar '25" }
 */
export function formatSymbol(sym: string): { primary: string; secondary?: string } {
  const parsed = parseZerodhaSymbol(sym);

  if (!parsed.expiry) {
    return { primary: parsed.underlying };
  }

  if (parsed.isFuture) {
    return {
      primary: `${parsed.underlying} FUT`,
      secondary: parsed.expiry,
    };
  }

  // Option: format strike in Indian locale (e.g., 74,800 not 74800)
  const strikeStr = parsed.strike != null
    ? parsed.strike.toLocaleString('en-IN')
    : '';

  return {
    primary: `${parsed.underlying} ${strikeStr} ${parsed.optionType ?? ''}`.trim(),
    secondary: parsed.expiry,
  };
}
