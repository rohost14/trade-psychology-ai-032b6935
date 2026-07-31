import { ArrowRight, AlertOctagon, AlertTriangle, Info, Bell } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
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

/**
 * "12h", not "about 12 hours ago". A feed row has one job: let the eye land on
 * the pattern name. A nine-character timestamp competing with it does not help,
 * and the long form was wrapping the row on narrow screens.
 */
function compactAgo(ts: string): string {
  const mins = Math.floor((Date.now() - new Date(ts).getTime()) / 60000);
  if (mins < 1) return 'now';
  if (mins < 60) return `${mins}m`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h`;
  return `${Math.floor(hrs / 24)}d`;
}

export default function RecentAlertsCard({ alerts, onOpen, onAcknowledge, loading }: RecentAlertsCardProps) {
  /**
   * Collapse repeats of the same pattern into one row carrying a count.
   *
   * The same detector firing twice on the same condition produced two
   * identical rows minutes apart, which reads as a bug and spends a row
   * saying nothing new. Repeats keep the newest timestamp, and count as
   * unreviewed if any occurrence is.
   *
   * Danger sorts above caution, because a feed ordered purely by time buries
   * the thing that matters under the thing that is recent.
   */
  const grouped = (() => {
    const byPattern = new Map<string, { alert: typeof alerts[number]; count: number }>();
    for (const a of alerts) {
      const hit = byPattern.get(a.pattern);
      if (!hit) { byPattern.set(a.pattern, { alert: a, count: 1 }); continue; }
      hit.count += 1;
      if (!a.acknowledged) hit.alert = { ...hit.alert, acknowledged: false };
      if (new Date(a.timestamp) > new Date(hit.alert.timestamp)) {
        hit.alert = { ...a, acknowledged: hit.alert.acknowledged };
      }
    }
    const rank = (a: typeof alerts[number]) => (normalizeSeverityStr(a.severity) === 'danger' ? 0 : 1);
    return [...byPattern.values()].sort((x, y) =>
      rank(x.alert) - rank(y.alert) ||
      new Date(y.alert.timestamp).getTime() - new Date(x.alert.timestamp).getTime(),
    );
  })();

  const visible = grouped.slice(0, MAX_VISIBLE);
  const hasMore = grouped.length > MAX_VISIBLE;
  const criticalCount = visible.filter(g => normalizeSeverityStr(g.alert.severity) === 'danger').length;

  return (
    <section className="rounded-lg border border-border bg-card overflow-hidden">
      <div className="card-head">
        <div className="flex items-center gap-2.5">
          <Bell className="h-3.5 w-3.5 text-loss" strokeWidth={2} />
          <span className="text-[11px] uppercase tracking-[0.12em] font-semibold text-foreground">
            What we caught today
          </span>
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
            <div key={i} className="px-5 sm:px-6 py-3.5 flex items-start gap-3">
              <Skeleton className="h-7 w-7 rounded-md shrink-0" />
              <div className="flex-1 space-y-2">
                <Skeleton className="h-3.5 w-40" />
                <Skeleton className="h-3 w-full" />
              </div>
            </div>
          ))}
        </div>
      ) : alerts.length === 0 ? (
        <div className="px-5 sm:px-6 py-8 text-center">
          <p className="text-[13px] font-semibold text-foreground">No live alerts</p>
          <p className="text-[12px] text-muted-foreground mt-0.5">Behavioural alerts appear here as they fire.</p>
        </div>
      ) : (
        <div className="divide-y divide-border">
          {visible.map(({ alert, count }) => {
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
                  'px-5 sm:px-6 py-3.5 border-l-[3px] animate-fade-in cursor-pointer transition-colors hover:bg-muted/40 focus:outline-none focus:bg-muted/40',
                  borderColor,
                  // Unreviewed danger carries a faint wash so the eye lands on
                  // it first. Reviewed rows recede rather than vanish.
                  !alert.acknowledged && isCritical && 'bg-loss/[0.04]',
                  alert.acknowledged && 'opacity-55',
                )}
              >
                <div className="flex items-start gap-3">
                  <div className={cn('h-7 w-7 rounded-md flex items-center justify-center shrink-0', iconBg)}>
                    <SevIcon className="h-3.5 w-3.5" strokeWidth={2.25} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-[14px] font-semibold text-foreground tracking-tight">{alert.pattern}</span>
                      {count > 1 && (
                        <span className="text-[10px] font-semibold text-muted-foreground font-tabular bg-muted px-1.5 py-0.5 rounded" title={`Fired ${count} times today`}>
                          {count}×
                        </span>
                      )}
                      <span className={cn(
                        'text-[9.5px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded',
                        isCritical ? 'bg-loss/10 text-loss' : isWarn ? 'bg-warning/10 text-warning' : 'bg-primary/10 text-primary',
                      )}>
                        {tagFor(alert.pattern)}
                      </span>
                      {!alert.acknowledged && (
                        <span className="h-1.5 w-1.5 rounded-full bg-primary shrink-0" title="Unreviewed" />
                      )}
                      <span className="text-[11px] text-muted-foreground font-tabular ml-auto shrink-0">
                        {compactAgo(alert.timestamp)}
                      </span>
                    </div>
                    {/* One line, not two. The full text lives in the detail
                        sheet a click away; two wrapped lines per row turned
                        four alerts into a screenful. */}
                    <p className="text-[12.5px] text-muted-foreground mt-0.5 leading-snug truncate">{alert.description}</p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {hasMore && (
        <Link to="/alerts" className="flex items-center justify-center gap-1.5 px-6 py-2.5 border-t border-border text-[11px] font-medium text-primary hover:bg-muted/40 transition-colors uppercase tracking-wider">
          View {grouped.length - MAX_VISIBLE} more <ArrowRight className="h-3 w-3" />
        </Link>
      )}
    </section>
  );
}

