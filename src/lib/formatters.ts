/**
 * TRUE MINUS (U+2212), not a hyphen-minus.
 *
 * DESIGN_SYSTEM.md §21: always show the sign, using a true minus. A hyphen is
 * narrower than the plus glyph, so in a tabular column of signed figures the
 * negatives sit a fraction out of alignment — exactly the comparison this
 * product exists to make easy. It also renders as a dash rather than an
 * operator at small sizes.
 *
 * Numbers are BUILT from Math.abs() plus this prefix, never handed to Intl
 * signed, because Intl emits the hyphen form.
 */
const MINUS = '−';

/** Sign prefix for a value: '+', a true minus, or nothing for exactly zero. */
function signOf(value: number): string {
  if (value > 0) return '+';
  if (value < 0) return MINUS;
  return '';
}

/** ₹ with Indian grouping (1,00,00,000 for a crore), always from an absolute value. */
function inr(abs: number, decimals: number): string {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(abs);
}

/**
 * Format number as Indian currency (₹). Negative values carry a true minus.
 */
export function formatCurrency(amount: number): string {
  const formatted = inr(Math.abs(amount), 2);
  return amount < 0 ? `${MINUS}${formatted}` : formatted;
}

/**
 * Format currency with an explicit sign. Exactly zero carries no sign.
 *
 * Two decimals are deliberate: paise must reconcile against the contract note,
 * and ₹918.75 must not read as ₹919. Compact and axis forms drop them.
 */
export function formatCurrencyWithSign(amount: number): string {
  return `${signOf(amount)}${inr(Math.abs(amount), 2)}`;
}

/**
 * Format number with Indian grouping (lakhs, crores)
 */
export function formatNumber(num: number): string {
  return new Intl.NumberFormat('en-IN').format(num);
}

/**
 * Format percentage — one decimal by default (§21), signed, true minus.
 * Exactly zero carries no sign, matching the currency formatters.
 */
export function formatPercentage(value: number, decimals: number = 1): string {
  return `${signOf(value)}${Math.abs(value).toFixed(decimals)}%`;
}

/**
 * Format a price. Two decimals always — a price is a quote, not a total (§21).
 */
export function formatPrice(price: number): string {
  const formatted = inr(Math.abs(price), 2);
  return price < 0 ? `${MINUS}${formatted}` : formatted;
}

/**
 * Format relative time (e.g., "2 hours ago")
 */
export function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins} minute${diffMins !== 1 ? 's' : ''} ago`;
  if (diffHours < 24) return `about ${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`;
  if (diffDays < 7) return `${diffDays} day${diffDays !== 1 ? 's' : ''} ago`;
  
  return date.toLocaleDateString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });
}

/**
 * Format date for display
 */
export function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });
}

/**
 * Format date with time
 */
export function formatDateTime(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/**
 * Compact currency for CHART AXIS ticks.
 *
 * Full currency ("−₹12,500.00") overflows a recharts YAxis at its default
 * width and gets clipped to the tail — axis labels rendered as "500.00", and
 * on signed axes the minus sign was cut off entirely, so a loss tick read as
 * a gain. Axis ticks need magnitude at a glance, not paise:
 *   1250 → ₹1.3k · -250000 → -₹2.5L · 0 → ₹0
 */
export function formatAxisCurrency(value: number): string {
  const abs = Math.abs(value);
  const sign = value < 0 ? MINUS : '';
  if (abs < 1) return '₹0';
  if (abs >= 1_00_00_000) return `${sign}₹${parseFloat((abs / 1_00_00_000).toFixed(1))}Cr`;
  if (abs >= 1_00_000)    return `${sign}₹${parseFloat((abs / 1_00_000).toFixed(1))}L`;
  if (abs >= 1_000)       return `${sign}₹${parseFloat((abs / 1_000).toFixed(1))}k`;
  return `${sign}₹${Math.round(abs)}`;
}

/**
 * Format currency in compact Indian notation (L for lakh, Cr for crore).
 * Used for large numbers where space is tight.
 * Examples: ₹1,50,000 → ₹1.5L  |  ₹1,20,00,000 → ₹1.2Cr
 */
export function formatCompactCurrency(amount: number): string {
  const abs = Math.abs(amount);
  const sign = amount < 0 ? MINUS : '';
  if (abs >= 1_00_00_000) {
    const cr = abs / 1_00_00_000;
    return `${sign}₹${parseFloat(cr.toFixed(2))}Cr`;
  }
  if (abs >= 1_00_000) {
    const l = abs / 1_00_000;
    return `${sign}₹${parseFloat(l.toFixed(2))}L`;
  }
  // Below 1L — show 2 decimal places to preserve paise accuracy
  return `${sign}${inr(abs, 2)}`;
}
