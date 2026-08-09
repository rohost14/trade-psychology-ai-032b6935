/**
 * The frontend half of the pattern contract.
 *
 * The backend test guarantees every pattern the engine can emit has copy. This
 * one guards the seam on this side: that the demo fixtures speak the same
 * vocabulary as the API, and that severity normalisation no longer throws away
 * the level the engine worked to compute.
 *
 * Both were real defects. `AlertDetailSheet` carried three local maps keyed on
 * engine v1 names, so an overtrading alert opened a panel with nothing in it.
 * The demo alerts used `high` / `medium`, a vocabulary the API has not returned
 * since engine v2 — and per the guest-fixture rule, a mock that does not mirror
 * its endpoint is a bug waiting to ship.
 */
import { describe, it, expect } from 'vitest';

import { DEMO_PATTERN_CATALOGUE, DEMO_RISK_ALERTS } from '@/lib/demoData';
import { SEV_LABEL, isSevere, normalizeSeverityStr } from '@/lib/alertSeverity';
import type { PatternSeverity } from '@/types/patterns';

/** Mirrors app/core/severity.py, minus `info` which never reaches a user. */
const BACKEND_SEVERITIES = ['critical', 'danger', 'caution'];

describe('pattern catalogue fixture', () => {
  it('covers every pattern the demo alerts use', () => {
    const known = new Set(DEMO_PATTERN_CATALOGUE.patterns.map(p => p.pattern_type));
    const missing = DEMO_RISK_ALERTS
      .map(a => a.pattern_type)
      .filter(t => !known.has(t));
    expect(missing).toEqual([]);
  });

  it('gives every pattern substantive copy', () => {
    for (const p of DEMO_PATTERN_CATALOGUE.patterns) {
      expect(p.label.length).toBeGreaterThan(0);
      expect(p.observes.length).toBeGreaterThan(20);
      expect(p.explanation.length).toBeGreaterThan(20);
    }
  });

  it('reports the real catalogue size, not the trimmed fixture length', () => {
    // The fixture is a subset; `count` must still describe the endpoint, or a
    // "showing 14 of 14" claim would be wrong in the app.
    expect(DEMO_PATTERN_CATALOGUE.count).toBeGreaterThan(
      DEMO_PATTERN_CATALOGUE.patterns.length,
    );
  });

  it('carries no invented statistics', () => {
    // The copy this replaced shipped precise unsourced claims presented as
    // measurement. Where a number belongs, it is the trader's own.
    const statShaped = /\b\d+(\.\d+)?\s*%|\b\d+×|\b\d+x\b/i;
    for (const p of DEMO_PATTERN_CATALOGUE.patterns) {
      expect(statShaped.test(p.observes)).toBe(false);
      expect(statShaped.test(p.explanation)).toBe(false);
    }
  });
});

describe('demo alerts speak the API vocabulary', () => {
  it('uses only severities the backend emits', () => {
    const offenders = DEMO_RISK_ALERTS
      .map(a => a.severity)
      .filter(s => !BACKEND_SEVERITIES.includes(s));
    expect(offenders).toEqual([]);
  });

  it('exercises critical, so the level is not dead in the fixtures', () => {
    expect(DEMO_RISK_ALERTS.some(a => a.severity === 'critical')).toBe(true);
  });
});

describe('severity normalisation', () => {
  it('keeps critical distinct from danger', () => {
    // This is the regression. critical used to fold into danger, so a trader
    // 120% past their own loss limit saw the same row as one at 100%.
    expect(normalizeSeverityStr('critical')).toBe('critical');
    expect(normalizeSeverityStr('danger')).toBe('danger');
    expect(SEV_LABEL.critical).toBe('Critical');
    expect(SEV_LABEL.critical).not.toBe(SEV_LABEL.danger);
  });

  it('treats both critical and danger as needing attention', () => {
    expect(isSevere('critical')).toBe(true);
    expect(isSevere('danger')).toBe(true);
    expect(isSevere('caution')).toBe(false);
  });

  it('still renders the legacy vocabulary rather than dropping it', () => {
    // Stored alerts from before the rename must not render as unknown.
    expect(normalizeSeverityStr('high')).toBe('danger');
    expect(normalizeSeverityStr('medium')).toBe('caution');
  });

  it('falls back to caution for anything unrecognised', () => {
    for (const value of ['', 'nonsense', 'info']) {
      expect(normalizeSeverityStr(value)).toBe('caution');
    }
  });

  it('has styling for every severity, so none renders unstyled', () => {
    const severities: PatternSeverity[] = ['critical', 'danger', 'caution', 'positive'];
    for (const s of severities) {
      expect(SEV_LABEL[s]).toBeTruthy();
    }
  });
});
