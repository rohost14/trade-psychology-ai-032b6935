import { ArrowRight, AlertOctagon, AlertTriangle, Info, Bell } from 'lucide-react';
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

const MAX_VISIBLE = 4;

// Derive a short category tag (SIZE/PACE/EMOTIONAL/RISK) from the pattern name,
// mirroring the Lovable alert cards. Falls back to PATTERN.
function tagFor(pattern: string): string {
  const p = pattern.toLowerCase();
  if (/(size|escalat|martingale|averag|qty)/.test(p)) return 'SIZE';
  if (/(overtrad|burst|pace|re-?entry|reentry|cooldown|rapid|fomo)/.test(p)) return 'PACE';
  if (/(revenge|loss|streak|meltdown|tilt|recovery|giveaway)/.test(p)) return 'EMOTIONAL';
  if (/(stop|\bsl\b|constitution|no_stoploss|limit|expiry)/.test(p)) return 'RISK';
  return 'PATTERN';
}

export default function RecentAlertsCard({ alerts, onOpen, onAcknowledge, loading }: RecentAlertsCardProps) {
  const visible = alerts.slice(0, MAX_VISIBLE);
  const hasMore = alerts.length > MAX_VISIBLE;
  const criticalCount = visible.filter(a => normalizeSeverityStr(a.severity) === 'danger').length;

  return (
    <section>
      <div className="section-head">
        <div className="flex items-center gap-2.5">
          <Bell className="h-3.5 w-3.5 text-muted-foreground" strokeWidth={2} />
          <span className="text-[11px] uppercase tracking-[0.12em] font-medium text-muted-foreground">Live Alerts</span>
          {!loading && alerts.length > 0 && (
            <span className="h-1.5 w-1.5 rounded-full bg-loss animate-pulse" />
          )}
          {criticalCount > 0 && (
            <span className="h-[18px] min-w-[18px] px-1.5 rounded-full bg-loss/10 text-loss text-[10px] font-semibold flex items-center justify-center font-tabular">
              {criticalCount}
            </span>
          )}
        </div>
        <Link to="/alerts" className="text-[11px] text-foreground hover:text-primary font-medium inline-flex items-center gap-1 transition-colors">
          View all <ArrowRight className="h-3 w-3" />
        </Link>
      </div>

      {loading ? (
        <div className="divide-y divide-border">
          {[1, 2, 3].map(i => (
            <div key={i} className="py-3.5 flex items-start gap-3">
              <Skeleton className="h-7 w-7 rounded-md shrink-0" />
              <div className="flex-1 space-y-2">
                <Skeleton className="h-3.5 w-40" />
                <Skeleton className="h-3 w-full" />
              </div>
            </div>
          ))}
        </div>
      ) : alerts.length === 0 ? (
        <div className="py-8 text-center">
          <p className="text-[13px] font-semibold text-foreground">No live alerts</p>
          <p className="text-[12px] text-muted-foreground mt-0.5">Behavioural alerts appear here as they fire.</p>
        </div>
      ) : (
        <div className="divide-y divide-border">
          {visible.map(alert => {
            const sev = normalizeSeverityStr(alert.severity);
            const isCritical = sev === 'danger';
            const isWarn = sev === 'caution';
            const borderColor = isCritical ? 'border-l-loss' : isWarn ? 'border-l-warning' : 'border-l-primary';
            const tagColor = isCritical ? 'text-loss' : isWarn ? 'text-warning' : 'text-primary';
            const iconBg = isCritical ? 'bg-loss/10 text-loss' : isWarn ? 'bg-warning/10 text-warning' : 'bg-primary/10 text-primary';
            const SevIcon = isCritical ? AlertOctagon : isWarn ? AlertTriangle : Info;

            return (
              <div
                key={alert.id}
                role="button"
                tabIndex={0}
                onClick={() => (onOpen ? onOpen(alert.id) : onAcknowledge?.(alert.id))}
                onKeyDown={e => (e.key === 'Enter' || e.key === ' ') && (onOpen ? onOpen(alert.id) : onAcknowledge?.(alert.id))}
                className={cn(
                  'py-3.5 border-l-2 animate-fade-in cursor-pointer transition-colors hover:bg-muted/40 focus:outline-none focus:bg-muted/40',
                  borderColor,
                  alert.acknowledged && 'opacity-60',
                )}
              >
                <div className="flex items-start gap-3">
                  <div className={cn('h-7 w-7 rounded-md flex items-center justify-center shrink-0', iconBg)}>
                    <SevIcon className="h-3.5 w-3.5" strokeWidth={2.25} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-[13.5px] font-semibold text-foreground">{alert.pattern}</span>
                      <span className={cn('text-[10px] font-semibold uppercase tracking-wider', tagColor)}>{tagFor(alert.pattern)}</span>
                      <span className="text-[10px] text-muted-foreground font-tabular uppercase tracking-wider ml-auto">
                        {formatRelativeTime(alert.timestamp)}
                      </span>
                    </div>
                    <p className="text-[12.5px] text-muted-foreground mt-1 leading-relaxed line-clamp-2">{alert.description}</p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {hasMore && (
        <Link to="/alerts" className="flex items-center justify-center gap-1.5 px-6 py-2.5 border-t border-border text-[11px] font-medium text-primary hover:bg-muted/40 transition-colors uppercase tracking-wider">
          View {alerts.length - MAX_VISIBLE} more <ArrowRight className="h-3 w-3" />
        </Link>
      )}
    </section>
  );
}
