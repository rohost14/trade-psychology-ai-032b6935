import { describe, it, expect } from 'vitest';
import { deriveStreak } from '@/components/patterns/CleanDayStreak';

/**
 * The streak derivation, lifted out of MyPatterns during the Alerts merge.
 *
 * Worth testing on the way out because it carries two corrections that are easy
 * to silently undo: only danger/critical break a streak (an earlier version
 * checked 'high', which the backend never emits, so danger days counted clean
 * and the streak read high), and weekends are skipped because NSE does not
 * trade on them.
 */

const TODAY = new Date('2026-08-05T12:00:00Z');   // a Wednesday

function alertOn(daysAgo: number, severity: string) {
  const d = new Date(TODAY);
  d.setDate(d.getDate() - daysAgo);
  return { detected_at: d.toISOString(), severity };
}

describe('deriveStreak', () => {
  it('counts every weekday clean when nothing fired', () => {
    const s = deriveStreak([], TODAY);
    expect(s.current_streak_days).toBeGreaterThan(0);
    expect(s.current_streak_days).toBe(s.daily_status.length);
  });

  it('breaks the streak on a danger alert', () => {
    const s = deriveStreak([alertOn(0, 'danger')], TODAY);
    expect(s.current_streak_days).toBe(0);
  });

  it('breaks the streak on a critical alert', () => {
    const s = deriveStreak([alertOn(0, 'critical')], TODAY);
    expect(s.current_streak_days).toBe(0);
  });

  it('does NOT break on caution or info', () => {
    const s = deriveStreak([alertOn(0, 'caution'), alertOn(1, 'info')], TODAY);
    expect(s.current_streak_days).toBeGreaterThan(0);
  });

  it("ignores 'high', which the backend never emits", () => {
    // The original bug ran the other way: it looked for 'high' and therefore
    // treated real danger days as clean. Asserting the severity vocabulary is
    // exactly danger/critical stops that regressing in either direction.
    const s = deriveStreak([alertOn(0, 'high')], TODAY);
    expect(s.current_streak_days).toBeGreaterThan(0);
  });

  it('excludes weekends from the day list', () => {
    const s = deriveStreak([], TODAY);
    for (const day of s.daily_status) {
      const [y, m, d] = day.date.split('-').map(Number);
      const dow = new Date(y, m - 1, d).getDay();
      expect(dow).not.toBe(0);
      expect(dow).not.toBe(6);
    }
  });

  it('reports the longest run independently of the current one', () => {
    // Danger today ends the current streak but must not erase history.
    const s = deriveStreak([alertOn(0, 'danger')], TODAY);
    expect(s.current_streak_days).toBe(0);
    expect(s.longest_streak_days).toBeGreaterThan(0);
  });

  it('awards milestones only once the longest run reaches them', () => {
    const clean = deriveStreak([], TODAY);
    const days = clean.longest_streak_days;
    for (const m of clean.milestones_achieved) {
      expect(days).toBeGreaterThanOrEqual(m.days);
    }
  });

  it('survives alerts with no timestamp', () => {
    expect(() => deriveStreak([{ severity: 'danger' }], TODAY)).not.toThrow();
  });
});
