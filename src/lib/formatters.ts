/**
 * Format number as Indian currency (₹)
 * Uses Indian number system: 1,00,00,000 for 1 crore
 */
export function formatCurrency(amount: number): string {
  const absAmount = Math.abs(amount);
  const formatted = new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(absAmount);
  return amount >= 0 ? formatted : `-${formatted}`;
}

/**
 * Format currency with sign (+ or -)
 */
export function formatCurrencyWithSign(amount: number): string {
  const absAmount = Math.abs(amount);
  const sign = amount > 0 ? '+' : amount < 0 ? '-' : '';
  // Show 2 decimal places so ₹918.75 doesn't round to ₹919
  const formatted = new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(absAmount);

  return `${sign}${formatted}`;
}

/**
 * Format number with Indian grouping (lakhs, crores)
 */
export function formatNumber(num: number): string {
  return new Intl.NumberFormat('en-IN').format(num);
}

/**
 * Format percentage
 */
export function formatPercentage(value: number, decimals: number = 1): string {
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(decimals)}%`;
}

/**
 * Format price with 2 decimal places
 */
export function formatPrice(price: number): string {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(price);
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
  const sign = value < 0 ? '-' : '';
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
  const sign = amount < 0 ? '-' : '';
  if (abs >= 1_00_00_000) {
    const cr = abs / 1_00_00_000;
    return `${sign}₹${parseFloat(cr.toFixed(2))}Cr`;
  }
  if (abs >= 1_00_000) {
    const l = abs / 1_00_000;
    return `${sign}₹${parseFloat(l.toFixed(2))}L`;
  }
  // Below 1L — show 2 decimal places to preserve paise accuracy
  const formatted = new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(abs);
  return amount < 0 ? `-${formatted}` : formatted;
}
