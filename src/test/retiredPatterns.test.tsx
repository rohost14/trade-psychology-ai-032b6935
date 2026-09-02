/**
 * A retired detector's stored alerts stay visible — and stay historical.
 *
 * `death_spiral` was retired 2026-09-02. Its rows are the trader's own
 * history and are NOT deleted: deleting them to tidy a vocabulary would be
 * worse than keeping a name. But a stored row must not read as a rule that is
 * still watching them, which is what the badge is for.
 *
 * The name map is the other half. A pattern_type missing from it renders as a
 * title-cased raw key — "Death Spiral" — which is how every previous
 * retirement would have leaked into the UI if the entry had been removed with
 * the detector.
 */
import { describe, it, expect } from 'vitest';
import {
  formatPatternName,
  isRetiredPattern,
  RETIRED_PATTERN_TYPES,
} from '@/contexts/AlertContext';

describe('retired patterns still render', () => {
  it('keeps the display name for a retired detector', () => {
    expect(formatPatternName('death_spiral')).toBe('Multi-domain breakdown');
  });

  it('does not fall back to a title-cased raw key', () => {
    // What a missing entry would have produced.
    expect(formatPatternName('death_spiral')).not.toBe('Death Spiral');
  });

  it('still names the other retired detectors whose rows exist', () => {
    for (const [type, name] of [
      ['options_premium_avg_down', 'Premium Averaging Down'],
      ['opening_5min_trap', 'Opening 5-Min Trap'],
      ['cooldown_violation', 'Cooldown ignored'],
      ['time_of_day_bias', 'Time-of-day pattern'],
    ] as const) {
      expect(formatPatternName(type)).toBe(name);
    }
  });
});

describe('retired patterns are marked as history', () => {
  it('marks death_spiral retired', () => {
    expect(isRetiredPattern('death_spiral')).toBe(true);
    expect(RETIRED_PATTERN_TYPES.has('death_spiral')).toBe(true);
  });

  it('does not mark a live detector retired', () => {
    for (const live of [
      'revenge_trade', 'martingale_behaviour', 'same_symbol_obsession',
      'constitution_violation', 'fomo_entry', 'overtrading_burst',
    ]) {
      expect(isRetiredPattern(live)).toBe(false);
    }
  });

  it('is safe on a missing pattern type', () => {
    expect(isRetiredPattern(undefined)).toBe(false);
    expect(isRetiredPattern(null)).toBe(false);
    expect(isRetiredPattern('')).toBe(false);
  });
});
