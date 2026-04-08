import { CheckCircle2, Check, ChevronRight, Link as LinkIcon } from 'lucide-react';
import { Link } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { formatRelativeTime } from '@/lib/formatters';
import type { Alert } from '@/types/api';
import { severityDotClass } from '@/lib/alertSeverity';

interface RecentAlertsCardProps {
  alerts: (Alert & { pattern: string; description: string; why_it_matters?: string })[];
  onAcknowledge?: (alertId: string) => void;
  onOpen?: (alertId: string) => void;
}

function patternWeight(sev: string): string {
  if (sev === 'critical' || sev === 'high' || sev === 'danger') return 'font-semibold text-foreground';
  if (sev === 'medium' || sev === 'caution') return 'font-medium text-foreground/90 dark:text-foreground/80';
  return 'font-normal text-muted-foreground';
}

const unreadCount = (alerts: RecentAlertsCardProps['alerts']) =>
  alerts.filter(a => !a.acknowledged).length;

export default function RecentAlertsCard({ alerts, onAcknowledge, onOpen }: RecentAlertsCardProps) {
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
            const isAcked = alert.acknowledged;
            return (
              <button
                key={alert.id}
                onClick={() => onOpen ? onOpen(alert.id) : onAcknowledge?.(alert.id)}
                className={cn(
                  'w-full flex items-start gap-4 px-5 py-4 text-left transition-colors',
                  'hover:bg-slate-50 dark:hover:bg-slate-700/40',
                  i < Math.min(alerts.length, 5) - 1
                    ? 'border-b border-slate-50 dark:border-neutral-700/40'
                    : '',
                  isAcked && 'opacity-50',
                )}
              >
                {/* Severity pip — vertical bar encodes urgency without decorating the row */}
                <span
                  className={cn('shrink-0', severityDotClass(alert.severity))}
                  style={{ width: 3, height: 20, minWidth: 3, borderRadius: 2, marginTop: 2 }}
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
                  <ChevronRight className="w-3.5 h-3.5 text-muted-foreground/50" />
                </div>
              </button>
            );
          })}

          {/* Footer link */}
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
