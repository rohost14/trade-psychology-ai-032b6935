/**
 * Shared severity config for all alert components.
 * Single source of truth — import from here, never redeclare locally.
 *
 * Visual language: 3px border + background tint per severity, so danger and
 * caution are separable in peripheral vision.
 *
 * `critical` is its own level, not a synonym for danger. The engine raises it
 * for the two things it treats as past the point the rule was written for —
 * 80% of an option's premium gone, or 120% of the trader's own limit — and it
 * is the severity that reaches an accountability partner. This file used to map
 * it onto danger, which threw that distinction away at the last step.
 */
import type { PatternSeverity } from '@/types/patterns';

export const SEV_DOT: Record<PatternSeverity, string> = {
  critical: 'bg-tm-loss',
  danger:   'bg-tm-loss',
  caution:  'bg-tm-obs',
  positive: 'bg-tm-profit',
};

export const SEV_LABEL: Record<PatternSeverity, string> = {
  critical: 'Critical',
  danger:   'Danger',
  caution:  'Caution',
  positive: 'Positive',
};

export const SEV_LABEL_COLOR: Record<PatternSeverity, string> = {
  critical: 'text-tm-loss',
  danger:   'text-tm-loss',
  caution:  'text-tm-obs',
  positive: 'text-tm-profit',
};

/** 3px left border — wider than 2px for clear visual anchor */
export const SEV_LEFT_BORDER: Record<PatternSeverity, string> = {
  critical: 'border-l-tm-loss',
  danger:   'border-l-tm-loss',
  caution:  'border-l-tm-obs',
  positive: 'border-l-tm-profit',
};

/** Background tint for rows — paired with SEV_LEFT_BORDER. Critical sits
 *  deeper than danger; that difference is the only thing carrying the level
 *  once the label is out of view. */
export const SEV_ROW_BG: Record<PatternSeverity, string> = {
  critical: 'bg-tm-status-danger/[0.11]',
  danger:   'bg-tm-status-danger/[0.05]',
  caution:  'bg-tm-status-caution/[0.05]',
  positive: '',
};

/**
 * Normalise a raw backend severity to a PatternSeverity.
 *
 * `high` / `medium` / `low` are a legacy vocabulary the API has not emitted
 * since engine v2; they are still accepted so old stored alerts render, but
 * nothing should be producing them.
 */
export function normalizeSeverityStr(sev: string): PatternSeverity {
  const s = (sev || '').toLowerCase();
  if (s === 'critical') return 'critical';
  if (s === 'danger' || s === 'high') return 'danger';
  if (s === 'positive') return 'positive';
  return 'caution'; // caution / info / medium / low / unknown
}

/** True when this severity is one of the two the engine notifies on. */
export function isSevere(sev: string): boolean {
  const s = normalizeSeverityStr(sev);
  return s === 'critical' || s === 'danger';
}

export function severityDotClass(sev: string): string {
  return SEV_DOT[normalizeSeverityStr(sev)] ?? 'bg-muted-foreground/40';
}

export function severityRowBg(sev: string): string {
  return SEV_ROW_BG[normalizeSeverityStr(sev)] ?? '';
}

export function severityBorderClass(sev: string): string {
  return SEV_LEFT_BORDER[normalizeSeverityStr(sev)] ?? 'border-l-transparent';
}
