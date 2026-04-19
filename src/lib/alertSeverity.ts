/**
 * Shared severity config for all alert components.
 * Single source of truth — import from here, never redeclare locally.
 *
 * Phase 6 visual language: 3px border + background tint per severity.
 * Makes danger/caution instantly visible even in peripheral vision.
 */
import type { PatternSeverity } from '@/types/patterns';

export const SEV_DOT: Record<PatternSeverity, string> = {
  critical: 'bg-tm-loss',
  high:     'bg-tm-loss/70',
  medium:   'bg-tm-obs',
  low:      'bg-muted-foreground/40',
};

export const SEV_LABEL: Record<PatternSeverity, string> = {
  critical: 'Critical',
  high:     'High',
  medium:   'Caution',
  low:      'Info',
};

export const SEV_LABEL_COLOR: Record<PatternSeverity, string> = {
  critical: 'text-tm-loss',
  high:     'text-tm-loss',
  medium:   'text-tm-obs',
  low:      'text-muted-foreground',
};

/** 3px left border — wider than 2px for clear visual anchor */
export const SEV_LEFT_BORDER: Record<PatternSeverity, string> = {
  critical: 'border-l-tm-loss',
  high:     'border-l-tm-loss',
  medium:   'border-l-tm-obs',
  low:      'border-l-border',
};

/** Background tint for rows — paired with SEV_LEFT_BORDER */
export const SEV_ROW_BG: Record<PatternSeverity, string> = {
  critical: 'bg-tm-status-danger/[0.05]',
  high:     'bg-tm-status-danger/[0.04]',
  medium:   'bg-tm-status-caution/[0.05]',
  low:      '',
};

/**
 * Returns dot class for an alert severity.
 * Accepts both PatternSeverity values and raw backend strings ('danger', 'caution', 'positive').
 */
export function severityDotClass(sev: string): string {
  if (sev === 'critical' || sev === 'danger') return 'bg-tm-loss';
  if (sev === 'high') return 'bg-tm-loss/70';
  if (sev === 'medium' || sev === 'caution') return 'bg-tm-obs';
  if (sev === 'positive') return 'bg-tm-profit';
  return 'bg-muted-foreground/40';
}

/** Row background tint based on string severity */
export function severityRowBg(sev: string): string {
  if (sev === 'critical' || sev === 'danger') return 'bg-tm-status-danger/[0.05]';
  if (sev === 'high') return 'bg-tm-status-danger/[0.04]';
  if (sev === 'medium' || sev === 'caution') return 'bg-tm-status-caution/[0.05]';
  return '';
}

/** 3px left border color class based on string severity */
export function severityBorderClass(sev: string): string {
  if (sev === 'critical' || sev === 'danger' || sev === 'high') return 'border-l-tm-loss';
  if (sev === 'medium' || sev === 'caution') return 'border-l-tm-obs';
  return 'border-l-transparent';
}
