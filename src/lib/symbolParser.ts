// Parse a Zerodha tradingsymbol into display parts.
//
// Shared by OpenPositionsTable and ClosedTradesTable (previously duplicated —
// the two copies could drift and mis-parse the same symbol differently).
//
// Zerodha uses two option expiry formats that share a \d{2}[A-Z]{3} prefix:
//
//   YYMMM   (2-digit year + 3-char month BEFORE strike)
//     → Index monthly options:  NIFTY25MAR23000CE, ICICIGI24JUN1640PE
//     → Weekly index:           NIFTY25415XXXXXCE (5-digit numeric expiry)
//
//   DDMMMYY (day + month + 2-digit year AFTER month, BEFORE strike)
//     → Stock options with specific-date/weekly expiry: ADANIPOWER26JUN242.5CE
//     → Strike may be decimal for low-priced stocks (2.5, 7.5, …)
//
// Strategy: for non-index symbols try DDMMMYY first with year-range validation
// (≥24); index symbols never use DDMMMYY, so skip straight to YYMMM.

const INDEX_PREFIXES = ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY', 'SENSEX', 'BANKEX'];

function fmtStrike(raw: string): string {
  const n = parseFloat(raw);
  return Number.isInteger(n)
    ? n.toLocaleString('en-IN')
    : n.toLocaleString('en-IN', { minimumFractionDigits: 1, maximumFractionDigits: 2 });
}

export interface ParsedSymbol {
  name: string;
  chip: string;   // CE | PE | FUT | EQ | instrument type
  sub: string;    // strike / expiry sub-line (empty for futures/equity)
}

export function parseSymbol(sym: string, instrType?: string): ParsedSymbol {
  // ── Weekly index options: 5-digit numeric expiry ──────────────────────────
  // e.g. NIFTY2541524600CE, NIFTY25415100000CE
  const mw = sym.match(/^([A-Z]+)\d{5}(\d{5,6})(CE|PE)$/);
  if (mw) return { name: mw[1], chip: mw[3], sub: parseInt(mw[2], 10).toLocaleString('en-IN') };

  // ── Stock options with DDMMMYY expiry (specific date, decimal strikes OK) ─
  // e.g. ADANIPOWER26JUN242.5CE  →  DD=26, MON=JUN, YY=24, strike=2.5, type=CE
  // Skip for known index underlyings — they never use this format.
  const isIndex = INDEX_PREFIXES.some(p => sym.startsWith(p));
  if (!isIndex) {
    const mDD = sym.match(/^([A-Z]+)(\d{2})([A-Z]{3})(\d{2})(\d+(?:\.\d+)?)(CE|PE)$/);
    if (mDD) {
      const expYear = parseInt(mDD[4], 10);
      const strike  = parseFloat(mDD[5]);
      // expYear must be a plausible options year (2024–2040); strike must be positive.
      // Rejects cases where \d{2}[A-Z]{3}\d{2} accidentally captures two year-digits
      // from a YYMMM symbol (e.g. ICICIGI24JUN → year parsed as "16" < 24 → falls through).
      if (expYear >= 24 && expYear <= 40 && strike > 0) {
        return { name: mDD[1], chip: mDD[6], sub: fmtStrike(mDD[5]) };
      }
    }
  }

  // ── Monthly options: YYMMM expiry ─────────────────────────────────────────
  // e.g. NIFTY25MAR23000CE, ICICIGI24JUN1640PE, KALYANKJIL24JUN370CE
  const mm = sym.match(/^([A-Z]+)\d{2}[A-Z]{3}(\d{3,6})(CE|PE)$/);
  if (mm) return { name: mm[1], chip: mm[3], sub: parseInt(mm[2], 10).toLocaleString('en-IN') };

  // ── Futures ───────────────────────────────────────────────────────────────
  // e.g. NIFTY25MARFUT, BANKNIFTY25APR25FUT, CRUDEOIL25MARFUT
  const mf = sym.match(/^([A-Z0-9]+)(?:\d{5}|\d{2}[A-Z]{3}(?:\d{2})?)FUT$/);
  if (mf) return { name: mf[1], chip: 'FUT', sub: '' };

  // ── Equity / unknown fallback ─────────────────────────────────────────────
  return { name: sym, chip: instrType && instrType !== 'EQ' ? instrType : 'EQ', sub: '' };
}
