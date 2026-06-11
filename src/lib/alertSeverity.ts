/**
 * Shared severity config for all alert components.
 * Single source of truth — import from here, never redeclare locally.
 *
 * Phase 6 visual language: 3px border + background tint per severity.
 * Makes danger/caution instantly visible even in peripheral vision.
 */
import type { PatternSeverity } from '@/types/patterns';

export const SEV_DOT: Record<PatternSeverity, string> = {
  danger:   'bg-tm-loss',
  caution:  'bg-tm-obs',
  positive: 'bg-tm-profit',
};

export const SEV_LABEL: Record<PatternSeverity, string> = {
  danger:   'Danger',
  caution:  'Caution',
  positive: 'Positive',
};

export const SEV_LABEL_COLOR: Record<PatternSeverity, string> = {
  danger:   'text-tm-loss',
  caution:  'text-tm-obs',
  positive: 'text-tm-profit',
};

/** 3px left border — wider than 2px for clear visual anchor */
export const SEV_LEFT_BORDER: Record<PatternSeverity, string> = {
  danger:   'border-l-tm-loss',
  caution:  'border-l-tm-obs',
  positive: 'border-l-tm-profit',
};

/** Background tint for rows — paired with SEV_LEFT_BORDER */
export const SEV_ROW_BG: Record<PatternSeverity, string> = {
  danger:   'bg-tm-status-danger/[0.05]',
  caution:  'bg-tm-status-caution/[0.05]',
  positive: '',
};

/** Normalise any raw backend or legacy severity string to a PatternSeverity. */
export function normalizeSeverityStr(sev: string): PatternSeverity {
  const s = sev.toLowerCase();
  if (s === 'danger' || s === 'critical' || s === 'high') return 'danger';
  if (s === 'positive') return 'positive';
  return 'caution'; // caution / medium / low / unknown
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
