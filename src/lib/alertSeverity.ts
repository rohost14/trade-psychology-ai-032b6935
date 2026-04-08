/**
 * Shared severity config for all alert components.
 * Single source of truth — import from here, never redeclare locally.
 */
import type { PatternSeverity } from '@/types/patterns';

export const SEV_DOT: Record<PatternSeverity, string> = {
  critical: 'bg-tm-loss',
  high:     'bg-tm-loss/70',
  medium:   'bg-tm-obs',
  low:      'bg-slate-400',
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

export const SEV_LEFT_BORDER: Record<PatternSeverity, string> = {
  critical: 'border-l-tm-loss',
  high:     'border-l-tm-loss',
  medium:   'border-l-tm-obs',
  low:      'border-l-slate-300 dark:border-l-slate-600',
};

/**
 * Returns the Tailwind dot class for an alert severity.
 * Accepts both PatternSeverity values and raw backend strings ('danger', 'caution', 'positive').
 */
export function severityDotClass(sev: string): string {
  if (sev === 'critical' || sev === 'danger') return 'bg-tm-loss';
  if (sev === 'high') return 'bg-tm-loss/70';
  if (sev === 'medium' || sev === 'caution') return 'bg-tm-obs';
  if (sev === 'positive') return 'bg-tm-profit';
  return 'bg-slate-400';
}
