import { describe, it, expect, afterEach } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { getChartColors } from '@/lib/chartColors';

/**
 * These run in jsdom, which does not resolve CSS custom properties — so they
 * exercise the documented fallback path in `chartColors.ts`. That is the point:
 * the fallback is what keeps charts rendering in tests and must stay in sync
 * with `src/index.css`, and the theme-awareness and sign rules must hold either
 * way.
 */

function setTheme(theme: 'light' | 'dark') {
  document.documentElement.classList.remove('light', 'dark');
  document.documentElement.classList.add(theme);
}

afterEach(() => {
  document.documentElement.classList.remove('light', 'dark');
});

describe('chart colours', () => {
  it('resolves every token to a concrete rgb string, never a var() or a class', () => {
    setTheme('dark');
    const c = getChartColors();

    for (const [name, value] of Object.entries(c)) {
      if (typeof value !== 'string') continue; // skip the helper functions
      expect(value, name).toMatch(/^rgba?\(/);
      expect(value, name).not.toContain('var(');
      expect(value, name).not.toContain('NaN');
    }
  });

  it('returns different values per theme — a chart cannot be hard-coded for one', () => {
    setTheme('dark');
    const dark = getChartColors();
    setTheme('light');
    const light = getChartColors();

    expect(dark.profit).not.toBe(light.profit);
    expect(dark.loss).not.toBe(light.loss);
    expect(dark.grid).not.toBe(light.grid);
  });

  describe('forValue — the P&L sign rule (DESIGN_SYSTEM.md §6)', () => {
    it('colours a gain as profit and a loss as loss', () => {
      setTheme('dark');
      const c = getChartColors();

      expect(c.forValue(1240)).toBe(c.profit);
      expect(c.forValue(-890)).toBe(c.loss);
    });

    it('colours exactly zero as muted, never as profit', () => {
      setTheme('dark');
      const c = getChartColors();

      expect(c.forValue(0)).toBe(c.axis);
      expect(c.forValue(0)).not.toBe(c.profit);
    });

    it('treats -0 as zero rather than as a loss', () => {
      setTheme('dark');
      const c = getChartColors();

      expect(c.forValue(-0)).toBe(c.axis);
    });
  });

  describe('series — no new hues (DESIGN_SYSTEM.md §20)', () => {
    it('starts on the accent and cycles instead of running out', () => {
      setTheme('dark');
      const c = getChartColors();

      expect(c.series(0)).toBe(c.primary);
      expect(c.series(6)).toBe(c.series(0));
      expect(c.series(-1)).toMatch(/^rgba?\(/); // negative index must not crash
    });

    it('draws only from the accent and neutral steps', () => {
      setTheme('dark');
      const c = getChartColors();

      // Every step is a tint of either the accent or the neutral axis colour,
      // so the rgb triplet must match one of those two.
      const accent = c.primary.match(/\d+, \d+, \d+/)?.[0];
      const neutral = c.axis.match(/\d+, \d+, \d+/)?.[0];

      for (let i = 0; i < 6; i++) {
        const triplet = c.series(i).match(/\d+, \d+, \d+/)?.[0];
        expect([accent, neutral]).toContain(triplet);
      }
    });
  });

  it('alpha() produces a transparent variant of a token', () => {
    setTheme('dark');
    const c = getChartColors();

    expect(c.alpha('profit', 0.2)).toMatch(/^rgba\(.+, 0\.2\)$/);
    expect(c.alpha('profit', 1)).toBe(c.profit);
  });
});

/**
 * The fallback table in `chartColors.ts` is the one place in `src/` that holds
 * colour literals, and its only failure mode is drifting out of sync with
 * `index.css` — silently, because browsers never read it. This parses the real
 * stylesheet and compares, so drift breaks a test instead of a theme.
 */
describe('fallback table stays in sync with index.css', () => {
  const css = readFileSync(resolve(__dirname, '../index.css'), 'utf8');

  /** Read a token from either the `:root` (light) or `.dark` block. */
  function cssToken(theme: 'light' | 'dark', token: string): string | null {
    // `:root { … }` holds light; `.dark { … }` holds dark. Take the first block
    // for the theme, then the last declaration of the token inside it.
    const blockRe = theme === 'light' ? /:root\s*\{([\s\S]*?)\n\s*\}/ : /\.dark\s*\{([\s\S]*?)\n\s*\}/;
    const block = css.match(blockRe)?.[1];
    if (!block) return null;

    const decls = [...block.matchAll(new RegExp(`${token}\\s*:\\s*([^;]+);`, 'g'))];
    if (decls.length === 0) return null;

    let value = decls[decls.length - 1][1].trim();
    // Resolve a single level of var() indirection, e.g. --border: var(--layer-border)
    const indirect = value.match(/^var\((--[\w-]+)\)$/);
    if (indirect) {
      const inner = [...block.matchAll(new RegExp(`${indirect[1]}\\s*:\\s*([^;]+);`, 'g'))];
      if (inner.length === 0) return null;
      value = inner[inner.length - 1][1].trim();
    }
    return value.replace(/\s*\/\*[\s\S]*?\*\//g, '').trim();
  }

  const TOKENS = {
    profit: '--tm-profit',
    loss: '--tm-loss',
    warning: '--tm-obs',
    primary: '--tm-brand',
    grid: '--border',
    axis: '--muted-foreground',
    foreground: '--foreground',
    surface: '--card',
  } as const;

  for (const theme of ['light', 'dark'] as const) {
    it(`${theme}: every fallback value matches the stylesheet`, () => {
      setTheme(theme);
      const c = getChartColors();

      for (const [name, token] of Object.entries(TOKENS)) {
        const declared = cssToken(theme, token);
        expect(declared, `${token} not found in index.css ${theme} block`).toBeTruthy();

        const [r, g, b] = declared!.split(/[\s,]+/).map(Number);
        expect(c[name as keyof typeof TOKENS], `${theme}.${name}`).toBe(`rgb(${r}, ${g}, ${b})`);
      }
    });
  }
});
