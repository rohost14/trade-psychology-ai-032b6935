/**
 * Chart colours, resolved from design tokens at runtime.
 *
 * WHY THIS EXISTS
 * Recharts needs a concrete colour *string* — it cannot take a Tailwind class or
 * a `var(--x)` reference for `fill`, `stroke`, or gradient stops. Historically
 * that meant hard-coded hex literals scattered through the chart components,
 * which are wrong in one of the two themes by definition.
 *
 * This module reads the CSS custom properties that already define the palette
 * (see `src/index.css`) and hands back concrete `rgb()` strings for the theme
 * that is active right now. DESIGN_SYSTEM.md §20: chart colour comes from a
 * token-reading source, never a literal.
 *
 * USAGE
 *   const c = useChartColors();            // re-reads when the theme flips
 *   <Bar fill={c.profit} />
 *   <CartesianGrid stroke={c.grid} />
 *   <Cell fill={c.forValue(row.pnl)} />
 *
 * Outside React (rare), call `getChartColors()` for a one-shot read.
 */

/** Token names as they appear in `src/index.css`. Values are `R G B` triplets. */
const TOKEN = {
  profit: '--tm-profit',
  loss: '--tm-loss',
  warning: '--tm-obs',
  primary: '--tm-brand',
  grid: '--border',
  axis: '--muted-foreground',
  foreground: '--foreground',
  surface: '--card',
} as const;

type TokenName = keyof typeof TOKEN;

/**
 * Last-resort values, used only in environments that don't resolve CSS custom
 * properties — jsdom being the one that matters, since it returns '' for
 * `getPropertyValue('--x')`. Browsers never reach these.
 *
 * These MUST stay in sync with `src/index.css`. They are the single exception to
 * "no colour literals" and exist so tests and non-DOM renders produce something
 * sane rather than `rgb(NaN, NaN, NaN)`.
 */
const FALLBACK: Record<'light' | 'dark', Record<TokenName, [number, number, number]>> = {
  light: {
    profit: [34, 109, 79],
    loss: [175, 58, 49],
    warning: [177, 107, 27],
    primary: [21, 91, 86],
    grid: [220, 218, 214],
    axis: [96, 100, 108],
    foreground: [22, 24, 29],
    surface: [255, 255, 255],
  },
  dark: {
    profit: [71, 184, 142],
    loss: [207, 101, 89],
    warning: [211, 145, 69],
    primary: [89, 192, 180],
    grid: [42, 44, 50],
    axis: [147, 150, 159],
    foreground: [238, 236, 232],
    surface: [25, 27, 31],
  },
};

type Rgb = readonly [number, number, number];

function activeTheme(): 'light' | 'dark' {
  if (typeof document === 'undefined') return 'dark';
  return document.documentElement.classList.contains('dark') ? 'dark' : 'light';
}

/**
 * Parse a `R G B` custom-property value. Returns null when the property is
 * absent, empty, or still an unresolved `var()` chain.
 */
function parseTriplet(raw: string): Rgb | null {
  const parts = raw.trim().split(/[\s,]+/).filter(Boolean).map(Number);
  if (parts.length < 3) return null;
  const [r, g, b] = parts;
  if (!Number.isFinite(r) || !Number.isFinite(g) || !Number.isFinite(b)) return null;
  return [r, g, b];
}

function readToken(name: TokenName): Rgb {
  if (typeof document !== 'undefined' && typeof getComputedStyle === 'function') {
    const raw = getComputedStyle(document.documentElement).getPropertyValue(TOKEN[name]);
    const parsed = parseTriplet(raw);
    if (parsed) return parsed;
  }
  return FALLBACK[activeTheme()][name];
}

function rgb([r, g, b]: Rgb, alpha?: number): string {
  return alpha === undefined || alpha >= 1
    ? `rgb(${r}, ${g}, ${b})`
    : `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

export interface ChartColors {
  profit: string;
  loss: string;
  warning: string;
  primary: string;
  /** Grid lines. Horizontal only — §20. */
  grid: string;
  /** Axis tick and legend text. */
  axis: string;
  foreground: string;
  surface: string;
  /**
   * Sign-aware colour for a P&L value. Exactly zero is muted, never green (§6).
   * Use for `Cell fill`, a line stroke, or a value label.
   */
  forValue: (value: number) => string;
  /**
   * A single accent plus neutral steps, for the rare chart with more than one
   * series. §20: a series never introduces a new hue.
   */
  series: (index: number) => string;
  /** Any token at partial opacity — e.g. an area fill under its own line. */
  alpha: (token: TokenName, a: number) => string;
}

/** One-shot read of the active theme's chart palette. */
export function getChartColors(): ChartColors {
  const profit = readToken('profit');
  const loss = readToken('loss');
  const warning = readToken('warning');
  const primary = readToken('primary');
  const grid = readToken('grid');
  const axis = readToken('axis');
  const foreground = readToken('foreground');
  const surface = readToken('surface');

  // Accent first, then neutral steps at decreasing weight. No new hues.
  const steps: string[] = [
    rgb(primary),
    rgb(axis),
    rgb(primary, 0.55),
    rgb(axis, 0.55),
    rgb(primary, 0.3),
    rgb(axis, 0.3),
  ];

  return {
    profit: rgb(profit),
    loss: rgb(loss),
    warning: rgb(warning),
    primary: rgb(primary),
    grid: rgb(grid),
    axis: rgb(axis),
    foreground: rgb(foreground),
    surface: rgb(surface),
    forValue: (value: number) =>
      value > 0 ? rgb(profit) : value < 0 ? rgb(loss) : rgb(axis),
    series: (index: number) => steps[((index % steps.length) + steps.length) % steps.length],
    alpha: (token: TokenName, a: number) => rgb(readToken(token), a),
  };
}

export type { TokenName };
