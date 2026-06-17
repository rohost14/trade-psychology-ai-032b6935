import { CheckCircle2, Check, ChevronRight, Link as LinkIcon } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { formatRelativeTime } from '@/lib/formatters';
import type { Alert } from '@/types/api';
import { normalizeSeverityStr } from '@/lib/alertSeverity';

interface RecentAlertsCardProps {
  alerts: (Alert & { pattern: string; description: string; why_it_matters?: string })[];
  onAcknowledge?: (alertId: string) => void;
  onOpen?: (alertId: string) => void;
  loading?: boolean;
}

function SeverityChip({ sev }: { sev: string }) {
  const normalized = normalizeSeverityStr(sev);
  if (normalized === 'danger') {
    return (
      <span className="inline-flex items-center text-[9.5px] font-bold px-1.5 py-0.5 rounded bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-400 uppercase tracking-[0.06em] shrink-0">
        High
      </span>
    );
  }
  if (normalized === 'positive') {
    return (
      <span className="inline-flex items-center text-[9.5px] font-bold px-1.5 py-0.5 rounded bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-400 uppercase tracking-[0.06em] shrink-0">
        Good
      </span>
    );
  }
  return (
    <span className="inline-flex items-center text-[9.5px] font-bold px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-400 uppercase tracking-[0.06em] shrink-0">
      Med
    </span>
  );
}

function patternWeight(sev: string): string {
  const normalized = normalizeSeverityStr(sev);
  if (normalized === 'danger') return 'font-semibold text-foreground';
  if (normalized === 'caution') return 'font-medium text-foreground/90';
  return 'font-normal text-muted-foreground';
}

const unreadCount = (alerts: RecentAlertsCardProps['alerts']) =>
  alerts.filter(a => !a.acknowledged).length;

export default function RecentAlertsCard({ alerts, onAcknowledge, onOpen, loading }: RecentAlertsCardProps) {
  const unread = unreadCount(alerts);

  return (
    <div className="tm-card">

      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3.5 border-b border-border">
        <div className="flex items-center gap-2.5">
          {!loading && unread > 0 && (
            <span className="w-2 h-2 rounded-full bg-tm-obs animate-pulse shrink-0" />
          )}
          <span className="tm-label">Behavioral Alerts</span>
          {!loading && unread > 0 && (
            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10.5px] font-semibold bg-amber-100 text-amber-700 dark:bg-amber-800/40 dark:text-amber-300">
              {unread} active
            </span>
          )}
        </div>
        {!loading && alerts.length > 4 && (
          <Link to="/alerts" className="text-[13px] font-medium text-tm-brand hover:underline">
            View all →
          </Link>
        )}
      </div>

      {/* Skeleton */}
      {loading ? (
        <div className="divide-y divide-border">
          {[1, 2, 3].map(i => (
            <div key={i} className="flex items-start gap-4 px-5 py-4">
              <div className="flex-1 space-y-2">
                <Skeleton className="h-3.5 w-32 rounded" />
                <Skeleton className="h-3 w-full rounded" />
              </div>
              <Skeleton className="h-3 w-12 rounded flex-shrink-0" />
            </div>
          ))}
        </div>
      ) : alerts.length > 0 ? (
        <div>
          {alerts.slice(0, 5).map((alert, i) => {
            const isAcked = alert.acknowledged;
            return (
              <button
                key={alert.id}
                onClick={() => onOpen ? onOpen(alert.id) : onAcknowledge?.(alert.id)}
                aria-label={`${alert.pattern}${isAcked ? ', reviewed' : ', tap to review'}`}
                className={cn(
                  'w-full flex items-start gap-3 px-5 py-3.5 text-left',
                  'transition-colors duration-100',
                  'hover:bg-muted/40 dark:hover:bg-muted/20',
                  i < Math.min(alerts.length, 5) - 1 ? 'border-b border-border' : '',
                  isAcked && 'opacity-50',
                )}
              >
                {/* Content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-0.5">
                    <p className={cn('t-body-sm leading-snug', patternWeight(alert.severity))}>
                      {alert.pattern}
                      {isAcked && (
                        <Check className="inline ml-1.5 h-3 w-3 text-tm-profit align-middle" />
                      )}
                    </p>
                  </div>
                  <p className="t-caption text-muted-foreground leading-snug">
                    {alert.description}
                  </p>
                </div>

                {/* Right side: chip + time + chevron */}
                <div className="shrink-0 flex flex-col items-end gap-1 pt-0.5">
                  <SeverityChip sev={alert.severity} />
                  <div className="flex items-center gap-1">
                    <span className="t-mono-sm text-muted-foreground">
                      {formatRelativeTime(alert.timestamp)}
                    </span>
                    <ChevronRight className="w-3.5 h-3.5 text-muted-foreground/50" />
                  </div>
                </div>
              </button>
            );
          })}

          {/* Footer */}
          <div className="px-5 py-2.5 border-t border-border">
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
          <p className="text-[13px] text-muted-foreground mt-0.5">No behavioral alerts detected today</p>
        </div>
      )}
    </div>
  );
}
