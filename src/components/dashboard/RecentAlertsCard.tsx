import { useState } from 'react';
import { CheckCircle2, Check, ChevronDown, ChevronRight, Link as LinkIcon } from 'lucide-react';
import { Link } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { formatRelativeTime } from '@/lib/formatters';
import type { Alert } from '@/types/api';

// ─── Detail renderer (shared logic with Alerts.tsx) ──────────────────────────
const DETAIL_LABELS: Record<string, string> = {
  streak:           'Consecutive losses',
  total_loss:       'Total loss',
  gap_minutes:      'Time since last loss',
  prior_loss:       'Prior trade loss',
  prior_symbol:     'Prior symbol',
  trades_in_window: 'Trades in 30 min',
  daily_count:      'Trades today',
  danger_limit:     'Danger limit',
  caution_limit:    'Caution limit',
  escalation_pct:   'Size escalation',
  drawdown_pct:     'Drawdown from peak',
  position_pct:     'Position size',
  hold_minutes:     'Hold duration',
};
const HIDDEN_KEYS = new Set(['insight', 'historical_insight', 'estimated_cost', 'exchange', 'threshold',
  'caution_window', 'danger_window', 'window_minutes', 'threshold_pct', 'daily_caution', 'daily_danger']);

function fmtVal(key: string, val: unknown): string {
  if (val === null || val === undefined) return '—';
  if (key.endsWith('_loss') || key.endsWith('_pnl') || key === 'total_loss' || key === 'prior_loss')
    return `₹${Number(val).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;
  if (key.endsWith('_minutes') || key === 'gap_minutes' || key === 'hold_minutes') return `${val} min`;
  if (key.endsWith('_pct')) return `${val}%`;
  if (Array.isArray(val)) return val.join(' → ');
  if (typeof val === 'number') return val.toLocaleString('en-IN', { maximumFractionDigits: 1 });
  return String(val);
}

function DetailGrid({ details }: { details?: Record<string, unknown> }) {
  if (!details) return null;
  const entries = Object.entries(details).filter(([k]) => !HIDDEN_KEYS.has(k) && DETAIL_LABELS[k]);
  if (!entries.length) return null;
  return (
    <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 mt-2.5 pt-2.5 border-t border-slate-100 dark:border-neutral-700/40">
      {entries.map(([k, v]) => (
        <div key={k}>
          <p className="text-[10px] text-muted-foreground uppercase tracking-wide">{DETAIL_LABELS[k]}</p>
          <p className="text-[12px] font-mono tabular-nums text-foreground font-medium">{fmtVal(k, v)}</p>
        </div>
      ))}
    </div>
  );
}

interface RecentAlertsCardProps {
  alerts: (Alert & { pattern: string; description: string; why_it_matters?: string })[];
  onAcknowledge?: (alertId: string) => void;
  onOpen?: (alertId: string) => void;
}

function severityDot(sev: string): string {
  if (sev === 'critical' || sev === 'danger') return 'bg-tm-loss';
  if (sev === 'high') return 'bg-tm-loss';
  if (sev === 'medium' || sev === 'caution') return 'bg-tm-obs';
  if (sev === 'positive') return 'bg-tm-profit';
  return 'bg-slate-400';
}

function patternWeight(sev: string): string {
  if (sev === 'critical' || sev === 'high' || sev === 'danger') return 'font-semibold text-foreground';
  if (sev === 'medium' || sev === 'caution') return 'font-medium text-foreground/90 dark:text-foreground/80';
  return 'font-normal text-muted-foreground';
}

const unreadCount = (alerts: RecentAlertsCardProps['alerts']) =>
  alerts.filter(a => !a.acknowledged).length;

export default function RecentAlertsCard({ alerts, onAcknowledge, onOpen }: RecentAlertsCardProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [localAckedIds, setLocalAckedIds] = useState<Set<string>>(new Set());

  const handleAcknowledge = (alertId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setLocalAckedIds(prev => new Set([...prev, alertId]));
    onAcknowledge?.(alertId);
  };

  const handleRowClick = (alertId: string) => {
    if (onOpen) {
      onOpen(alertId);
    } else {
      setExpandedId(prev => prev === alertId ? null : alertId);
    }
  };

  const unread = unreadCount(alerts);

  return (
    <div className="tm-card">

      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-slate-100 dark:border-neutral-700/60">
        <div className="flex items-center gap-3">
          <span className="tm-label">Behavioral Alerts</span>
          {unread > 0 && (
            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-amber-100 text-amber-700 dark:bg-amber-800/40 dark:text-amber-300">
              {unread} unread
            </span>
          )}
        </div>
        {alerts.length > 4 && (
          <Link to="/alerts" className="text-[13px] font-medium text-tm-brand hover:underline">
            View all →
          </Link>
        )}
      </div>

      {/* Alert list */}
      {alerts.length > 0 ? (
        <div>
          {alerts.slice(0, 5).map((alert, i) => {
            const isExpanded = expandedId === alert.id;
            const isAcked = alert.acknowledged || localAckedIds.has(alert.id);

            return (
              <div key={alert.id}>
                <button
                  onClick={() => handleRowClick(alert.id)}
                  className={cn(
                    'w-full flex items-start gap-4 px-5 py-3.5 text-left transition-colors',
                    'hover:bg-slate-50 dark:hover:bg-slate-700/40',
                    i < Math.min(alerts.length, 5) - 1 && !isExpanded
                      ? 'border-b border-slate-50 dark:border-neutral-700/40'
                      : '',
                    isAcked && 'opacity-50',
                  )}
                >
                  {/* Severity dot */}
                  <span
                    className={cn('mt-[5px] shrink-0 rounded-full', severityDot(alert.severity))}
                    style={{ width: 7, height: 7, minWidth: 7 }}
                  />

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <p className={cn('text-sm leading-snug', patternWeight(alert.severity))}>
                      {alert.pattern}
                      {isAcked && (
                        <Check className="inline ml-1.5 h-3 w-3 text-tm-profit align-middle" />
                      )}
                    </p>
                    <p className="text-[13px] text-muted-foreground mt-0.5 leading-snug">
                      {alert.description}
                    </p>
                  </div>

                  {/* Time + chevron */}
                  <div className="shrink-0 flex items-center gap-1.5 pt-0.5">
                    <span className="text-[12px] text-muted-foreground font-mono tabular-nums">
                      {formatRelativeTime(alert.timestamp)}
                    </span>
                    <ChevronDown className={cn(
                      'w-3.5 h-3.5 text-muted-foreground/50 transition-transform duration-150',
                      isExpanded && 'rotate-180',
                    )} />
                  </div>
                </button>

                {/* Expanded detail */}
                {isExpanded && (
                  <div className="px-5 pb-3.5 border-b border-slate-50 dark:border-neutral-700/40 bg-muted/20">
                    <div className="pl-[calc(7px+1rem)] space-y-2">
                      <DetailGrid details={alert.details} />
                      {!isAcked && (
                        <button
                          onClick={(e) => handleAcknowledge(alert.id, e)}
                          className="flex items-center gap-1.5 text-[13px] font-medium text-tm-brand hover:underline mt-2"
                        >
                          <Check className="h-3.5 w-3.5" />
                          Mark acknowledged
                        </button>
                      )}
                    </div>
                  </div>
                )}
              </div>
            );
          })}

          {/* Footer link */}
          {alerts.length > 0 && (
            <div className="px-5 py-2.5 border-t border-slate-100 dark:border-neutral-700/60">
              <Link
                to="/alerts"
                className="flex items-center gap-1 text-[13px] font-medium text-tm-brand hover:underline"
              >
                <LinkIcon className="w-3 h-3" />
                View full alert history
                <ChevronRight className="w-3.5 h-3.5" />
              </Link>
            </div>
          )}
        </div>
      ) : (
        <div className="py-10 text-center">
          <CheckCircle2 className="h-8 w-8 text-tm-profit/30 mx-auto mb-2.5" />
          <p className="text-sm font-medium text-foreground">All clear</p>
          <p className="text-[13px] text-muted-foreground mt-0.5">No behavioral alerts detected</p>
        </div>
      )}
    </div>
  );
}
