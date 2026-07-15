// Zerodha tradingsymbol classification helpers for analytics.
//
// Shared by OverviewTab / EdgeTab (previously duplicated — the copies could drift
// and classify the same symbol differently). Distinct from lib/symbolParser
// (which produces display parts name/chip/sub); these return the underlying and
// instrument/expiry classification used for grouping.

/** The underlying root of an F&O symbol (e.g. NIFTY25MAR23000CE → NIFTY). */
export function extractUnderlying(sym: string): string {
  const m1 = sym.match(/^([A-Z\-]+?)\d{5}\d+(CE|PE)$/);
  if (m1) return m1[1];
  const mDD = sym.match(/^([A-Z\-]+?)\d{2}[A-Z]{3}\d{2}\d+(?:\.\d+)?(CE|PE)$/);
  if (mDD) return mDD[1];
  const m2 = sym.match(/^([A-Z\-]+?)\d{2}[A-Z]{3}\d+(CE|PE)$/);
  if (m2) return m2[1];
  const m3 = sym.match(/^([A-Z\-]+?)(?:\d{5}|\d{2}[A-Z]{3}(?:\d{2})?)FUT$/);
  if (m3) return m3[1];
  return sym;
}

/** CE / PE / FUT / EQ from the symbol suffix. */
export function optionType(sym: string): 'CE' | 'PE' | 'FUT' | 'EQ' {
  if (sym.endsWith('CE')) return 'CE';
  if (sym.endsWith('PE')) return 'PE';
  if (sym.endsWith('FUT')) return 'FUT';
  return 'EQ';
}

/** Weekly vs monthly vs future expiry family. */
export function classifyExpiry(sym: string): 'weekly' | 'monthly' | 'fut' | 'other' {
  if (sym.endsWith('FUT')) return 'fut';
  // Weekly: 5-6 consecutive digits as expiry code (YYMDD / YYMMDD)
  if (/^[A-Z\-]+\d{5,6}\d+(CE|PE)$/.test(sym)) return 'weekly';
  // Monthly: DDMON or DDMONYY with an alpha month
  if (/^[A-Z\-]+\d{2}[A-Z]{3}(\d{2})?\d+(CE|PE)$/.test(sym)) return 'monthly';
  return 'other';
}
