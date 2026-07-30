import { describe, it, expect } from 'vitest';
import {
  formatCurrency,
  formatCurrencyWithSign,
  formatPercentage,
  formatPrice,
  formatAxisCurrency,
  formatCompactCurrency,
  formatNumber,
} from '@/lib/formatters';

/**
 * Every money figure in the product passes through this module and it had no
 * tests. The sign rules in particular are load-bearing: a dropped or mistyped
 * minus turns a loss into a gain, which is the worst defect this UI can ship.
 */

const MINUS = '−'; // U+2212, not a hyphen

describe('sign handling (DESIGN_SYSTEM.md §21)', () => {
  it('uses a true minus, never a hyphen-minus', () => {
    for (const s of [
      formatCurrency(-1240),
      formatCurrencyWithSign(-1240),
      formatPrice(-182.4),
      formatPercentage(-3.2),
      formatAxisCurrency(-250000),
      formatCompactCurrency(-250000),
    ]) {
      expect(s, s).toContain(MINUS);
      expect(s, s).not.toContain('-'); // ASCII hyphen
    }
  });

  it('always shows an explicit + on gains', () => {
    expect(formatCurrencyWithSign(1240)).toMatch(/^\+/);
    expect(formatPercentage(3.2)).toMatch(/^\+/);
  });

  it('gives exactly zero no sign at all — never +0 or −0', () => {
    expect(formatCurrencyWithSign(0)).toBe('₹0.00');
    expect(formatPercentage(0)).toBe('0.0%');
    expect(formatCurrencyWithSign(0)).not.toContain('+');
    expect(formatCurrencyWithSign(0)).not.toContain(MINUS);
  });

  it('treats -0 as zero, not as a loss', () => {
    expect(formatCurrencyWithSign(-0)).toBe('₹0.00');
    expect(formatPercentage(-0)).toBe('0.0%');
  });
});

describe('currency', () => {
  it('groups in the Indian system — lakhs and crores, not thousands', () => {
    expect(formatCurrency(1234567)).toContain('12,34,567');
    expect(formatNumber(10000000)).toBe('1,00,00,000');
  });

  it('keeps paise, so a figure reconciles against the contract note', () => {
    expect(formatCurrencyWithSign(918.75)).toBe('+₹918.75');
    expect(formatCurrencyWithSign(918.75)).not.toContain('919');
  });

  it('formats a loss with the sign ahead of the symbol', () => {
    expect(formatCurrencyWithSign(-890)).toBe(`${MINUS}₹890.00`);
  });
});

describe('formatPercentage', () => {
  it('defaults to one decimal and honours an override', () => {
    expect(formatPercentage(62.53)).toBe('+62.5%');
    expect(formatPercentage(62.53, 2)).toBe('+62.53%');
    expect(formatPercentage(-8.17)).toBe(`${MINUS}8.2%`);
  });
});

describe('formatAxisCurrency — chart ticks', () => {
  it('compacts to k, L and Cr rather than overflowing an axis', () => {
    expect(formatAxisCurrency(1250)).toBe('₹1.3k');
    expect(formatAxisCurrency(250000)).toBe('₹2.5L');
    expect(formatAxisCurrency(12000000)).toBe('₹1.2Cr');
  });

  it('collapses sub-rupee values to a plain zero, with no sign', () => {
    expect(formatAxisCurrency(0)).toBe('₹0');
    expect(formatAxisCurrency(-0.4)).toBe('₹0');
  });

  it('keeps the minus on negative ticks — the clipped-sign bug this exists for', () => {
    expect(formatAxisCurrency(-250000)).toBe(`${MINUS}₹2.5L`);
    expect(formatAxisCurrency(-1250)).toBe(`${MINUS}₹1.3k`);
  });

  it('never emits decimals for a tick, which is what overflowed the axis', () => {
    expect(formatAxisCurrency(-12500)).not.toContain('.00');
  });
});

describe('formatCompactCurrency', () => {
  it('compacts above a lakh and keeps paise below it', () => {
    expect(formatCompactCurrency(150000)).toBe('₹1.5L');
    expect(formatCompactCurrency(12000000)).toBe('₹1.2Cr');
    expect(formatCompactCurrency(4500.5)).toBe('₹4,500.50');
  });

  it('signs a compacted loss', () => {
    expect(formatCompactCurrency(-150000)).toBe(`${MINUS}₹1.5L`);
  });
});
