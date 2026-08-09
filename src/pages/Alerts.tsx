/**
 * Alerts — the behavioural loop, and where patterns live.
 *
 * Merged with My Patterns 2026-08-01 (docs/ALERTS_PATTERNS_MERGE.md). After
 * Analytics took quantified cost, My Patterns held a duplicate of that card, an
 * alert-history block belonging here, a behaviour score backed by a constant,
 * and one genuine asset in the calendar. Not a page — so its content came here.
 *
 * Two things make this a loop rather than a log:
 *  - every alert can be answered in one tap (POST /api/risk/alerts/{id}/feedback,
 *    which existed all along and nothing called — the real reason the record
 *    read 55 alerts and 0 outcomes), and
 *  - every row carries the trader's own record with that pattern, from the same
 *    factual source Analytics uses.
 *
 * No coloured left edge and no tinted row. That treatment belongs to live
 * alerts on the Dashboard; on a page that is entirely alerts every row would
 * carry it, which distinguishes nothing. Severity is a dot, a chip, and order.
 */
import { useState, useMemo, useEffect, useCallback } from 'react';
import { Bell, BellOff, CheckCheck, Clock, TrendingUp, Shield } from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
// Merged in from My Patterns. BehaviorScoresCard is deliberately absent: its
// quality_score is populated by no service, so it is a number that never moves.
import BehaviourLead from '@/components/analytics/BehaviourLead';
import BehaviourCostCard from '@/components/patterns/BehaviourCostCard';
import PatternFrequencyCard from '@/components/patterns/PatternFrequencyCard';
import PatternCalendar from '@/components/patterns/PatternCalendar';
import CleanDayStreak from '@/components/patterns/CleanDayStreak';
import { Skeleton } from '@/components/ui/skeleton';
import ErrorState from '@/components/ErrorState';
import { cn } from '@/lib/utils';
import { api } from '@/lib/api';
import { useApiQuery } from '@/hooks/useApiQuery';
import { useAlerts, AlertNotification, formatPatternName } from '@/contexts/AlertContext';
import { PatternSeverity } from '@/types/patterns';
import AlertDetailSheet from '@/components/alerts/AlertDetailSheet';
import {
  SEV_DOT, SEV_LABEL, SEV_LABEL_COLOR,
  severityBorderClass, severityRowBg, normalizeSeverityStr,
} from '@/lib/alertSeverity';

function timeAgo(dateStr: string | undefined): string {
  if (!dateStr) return '—';
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  const hrs = Math.floor(mins / 60);
  const days = Math.floor(hrs / 24);
  if (mins < 1)  return 'just now';
  if (mins < 60) return `${mins}m ago`;
  if (hrs < 24)  return `${hrs}h ago`;
  return `${days}d ago`;
}

function formatIST(dateStr: string | undefined): string {
  if (!dateStr) return '—';
  return new Date(dateStr).toLocaleString('en-IN', {
    timeZone: 'Asia/Kolkata',
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

// ─── Frequency helper ─────────────────────────────────────────────────────────

const WEEK_MS = 7 * 24 * 60 * 60 * 1000;

function buildWeekCounts(alertList: AlertNotification[]): Record<string, number> {
  const cutoff = Date.now() - WEEK_MS;
  const counts: Record<string, number> = {};
  for (const a of alertList) {
    if (new Date(a.shown_at ?? 0).getTime() < cutoff) continue;
    const key = a.pattern.type ?? a.pattern.backend_type;
    counts[key] = (counts[key] ?? 0) + 1;
  }
  return counts;
}


type Outcome = 'stopped' | 'took_anyway' | 'not_useful';

const OUTCOME_LABEL: Record<Outcome, string> = {
  stopped: 'I stood down',
  took_anyway: 'Took it anyway',
  not_useful: 'Not useful',
};

/**
 * One-tap response on the alert itself.
 *
 * Deliberately no confirm step and no text field: the measured evidence is 55
 * alerts and 0 outcomes recorded, and the product constraint is that any
 * feature needing typed input will not be used. Optimistic, because the value
 * is the habit of answering, not the write.
 *
 * "Took it anyway" is not scolded. The charter is mirror-not-blocker, so the
 * honest answer has to be as easy to give as the flattering one.
 */
function AlertResponse({ alertId, current }: { alertId: string; current?: Outcome | null }) {
  const [saved, setSaved] = useState<Outcome | null>(current ?? null);
  const [pending, setPending] = useState<Outcome | null>(null);

  const send = (outcome: Outcome) => (e: React.MouseEvent) => {
    e.stopPropagation();          // the whole row is a button; do not open the sheet
    if (saved === outcome) return;
    setPending(outcome);
    setSaved(outcome);            // optimistic
    api.post(`/api/risk/alerts/${alertId}/feedback`, { outcome })
      .catch(() => setSaved(current ?? null))
      .finally(() => setPending(null));
  };

  if (saved) {
    return (
      <div className="flex items-center gap-2 mt-2.5">
        <span className="text-[11px] text-muted-foreground">
          You said: <span className="text-foreground font-medium">{OUTCOME_LABEL[saved]}</span>
        </span>
        <button
          onClick={send(saved === 'stopped' ? 'took_anyway' : 'stopped')}
          className="text-[11px] text-muted-foreground underline underline-offset-2 hover:text-foreground"
        >
          change
        </button>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 mt-2.5 flex-wrap">
      <span className="text-[11px] text-muted-foreground mr-0.5">What did you do?</span>
      {(['stopped', 'took_anyway'] as Outcome[]).map(o => (
        <button
          key={o}
          onClick={send(o)}
          disabled={pending !== null}
          className={cn(
            'h-7 px-2.5 rounded-md text-[11.5px] font-medium border transition-colors',
            'border-border text-foreground hover:bg-muted',
            'disabled:opacity-50',
          )}
        >
          {OUTCOME_LABEL[o]}
        </button>
      ))}
      <button
        onClick={send('not_useful')}
        disabled={pending !== null}
        className="h-7 px-2 text-[11.5px] text-muted-foreground hover:text-foreground disabled:opacity-50"
      >
        Not useful
      </button>
    </div>
  );
}


interface RecordRow { pattern_type?: string; alert_count?: number; trade_count: number; realized_pnl: number }

/** pattern_type -> that pattern's realized record, fetched once for the page. */
function usePatternRecord() {
  const [byPattern, setByPattern] = useState<Record<string, RecordRow>>({});
  useEffect(() => {
    api.get<{ patterns?: RecordRow[] }>('/api/analytics/behaviour-cost', { params: { days: 90 } })
      .then(r => {
        const map: Record<string, RecordRow> = {};
        for (const row of r.data?.patterns ?? []) {
          if (row.pattern_type) map[row.pattern_type] = row;
        }
        setByPattern(map);
      })
      .catch(() => {});
  }, []);
  return byPattern;
}

const recordInr = (n: number) =>
  (n < 0 ? '\u2212' : '+') + '\u20b9' + Math.abs(Math.round(n)).toLocaleString('en-IN');

/**
 * "Last 3 times: -Rs13,000." Shown only when the pattern has actually repeated,
 * because a record of one is not a record.
 */
function PatternRecord({ row }: { row?: RecordRow }) {
  if (!row || (row.alert_count ?? 0) < 2) return null;
  const losing = row.realized_pnl < 0;
  return (
    <p className="text-[11.5px] text-muted-foreground mt-1.5">
      Your record: <span className="text-foreground font-medium">{row.alert_count} times</span> in 90 days,{' '}
      <span className={cn('font-medium font-tabular', losing ? 'text-tm-loss' : 'text-tm-profit')}>
        {recordInr(row.realized_pnl)}
      </span>{' '}
      realized on those trades.
    </p>
  );
}

// ─── Alert row ────────────────────────────────────────────────────────────────

function AlertRow({
  alert,
  onOpen,
  weekCount = 0,
  record,
}: {
  alert: AlertNotification;
  onOpen: (alert: AlertNotification) => void;
  weekCount?: number;
  record?: RecordRow;
}) {
  const sev = alert.pattern.severity;

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => onOpen(alert)}
      onKeyDown={e => (e.key === 'Enter' || e.key === ' ') && onOpen(alert)}
      aria-label={`${alert.pattern.name} - ${SEV_LABEL[sev]}${alert.acknowledged ? ', reviewed' : ', unreviewed'}`}
      className={cn(
        // No coloured edge, no tinted row. On a page that is entirely alerts,
        // every row would carry both, so neither distinguishes anything -- it
        // just reads as severity theatre. Severity is the dot, the category
        // chip and the order. Rows are separated by a hairline, and the whole
        // list is one surface rather than a stack of cards.
        'w-full text-left px-4 py-3.5 min-h-[44px] transition-colors',
        'border-b border-border last:border-b-0',
        'hover:bg-muted/40 focus-visible:outline-none focus-visible:bg-muted/40',
        alert.acknowledged && 'opacity-55',
      )}
    >
      <div className="flex items-start gap-3 px-4 py-4">
        <span className={cn('w-2 h-2 rounded-full flex-shrink-0 mt-1.5', SEV_DOT[sev])} />

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span className="text-[13px] font-medium text-foreground">{alert.pattern.name}</span>
            {/* The category is the primary scan target, GitHub-inbox style:
                a reason label lets dozens of rows be triaged in seconds. */}
            <span className={cn('text-[10px] font-semibold uppercase tracking-wider', SEV_LABEL_COLOR[sev])}>
              {SEV_LABEL[sev]}
            </span>
            {weekCount >= 2 && (
              <span className="text-[10px] font-semibold text-tm-obs bg-tm-obs/10 rounded px-1.5 py-0.5">
                {weekCount}× this week
              </span>
            )}
            {!alert.acknowledged && (
              <span className="text-[10px] font-medium text-primary bg-primary/10 rounded px-1.5 py-0.5">
                New
              </span>
            )}
          </div>

          {/* Evidence line — dynamic, generated by behavior_engine with real trade numbers */}
          <p className="text-[12px] text-muted-foreground leading-relaxed line-clamp-2">
            {alert.pattern.description}
          </p>

          <div className="flex items-center gap-2 mt-1.5 text-[11px] text-muted-foreground">
            <Clock className="h-3 w-3 flex-shrink-0" />
            <span>{timeAgo(alert.shown_at)}</span>
          </div>

          {/* Their own tape, on the row that fired. */}
          <PatternRecord row={record} />

          {/* The loop. Without this the page is a log of things already done. */}
          <AlertResponse alertId={alert.id} current={alert.pattern.outcome as Outcome | undefined} />
        </div>

        <span className="text-muted-foreground/40 text-[11px] flex-shrink-0 mt-0.5">›</span>
      </div>
    </div>
  );
}

// ─── Response-stats card ("You & your alerts") ─────────────────────────────────
// Surfaces the accountability metric: how the user actually responds to their own
// alerts. "You took the trade anyway 12 times" is the honest behavioural mirror.

interface ResponseStatRow {
  pattern: string;
  total: number;
  ignored: number;
  stopped: number;
  took_anyway: number;
}
interface ResponseStats {
  patterns: ResponseStatRow[];
  total_ignored: number;
  total_took_anyway: number;
  total_stopped: number;
}

function ResponseStatsCard() {
  const { data: stats } = useApiQuery<ResponseStats>(
    ['risk', 'alert-response-stats'],
    '/api/risk/alert-response-stats',
    { params: { days: 30 } },
  );

  // Same trap as BehaviorScoresCard: {} is truthy, so this used to reach
  // `stats.patterns.length` on undefined and take the whole tab down. The
  // optional chain is the guard — never `if (!stats)`, because guest mode
  // answers an unmocked GET with {}.
  //
  // No error branch on purpose: this is a supplementary card above the alert
  // list. If it cannot load, showing nothing is right; an error block here would
  // sit on top of a working page and imply the alerts below are broken too.
  if (!stats?.patterns?.length) return null;
  // Only worth showing once there's a signal (something ignored or overridden).
  const top = stats.patterns.filter(p => p.took_anyway > 0 || p.ignored > 0).slice(0, 3);
  if (top.length === 0) return null;

  return (
    <div className="tm-card px-4 py-3.5 mb-4">
      <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">
        You &amp; your alerts · last 30 days
      </p>
      <p className="text-[13px] text-foreground leading-relaxed mb-3">
        {stats.total_took_anyway > 0 ? (
          <>You took the trade anyway <span className="font-semibold text-tm-loss">{stats.total_took_anyway}</span> time{stats.total_took_anyway !== 1 ? 's' : ''} after an alert
            {stats.total_stopped > 0 && <> · stopped <span className="font-semibold text-tm-profit">{stats.total_stopped}</span></>}.</>
        ) : (
          <><span className="font-semibold text-tm-obs">{stats.total_ignored}</span> alert{stats.total_ignored !== 1 ? 's' : ''} you never reviewed.</>
        )}
      </p>
      <div className="space-y-1.5">
        {top.map(p => (
          <div key={p.pattern} className="flex items-center justify-between text-[12px]">
            <span className="text-foreground">{formatPatternName(p.pattern)}</span>
            <span className="text-muted-foreground font-mono tabular-nums">
              {p.took_anyway > 0 && <span className="text-tm-loss">{p.took_anyway} took anyway</span>}
              {p.took_anyway > 0 && p.ignored > 0 && ' · '}
              {p.ignored > 0 && <span>{p.ignored} ignored</span>}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Live Tab ─────────────────────────────────────────────────────────────────

function AlertSkeleton() {
  return (
    <div className="space-y-2.5">
      {[1, 2, 3].map(i => (
        <div key={i} className="tm-card px-4 py-4 flex items-start gap-3">
          <Skeleton className="w-0.5 h-5 rounded flex-shrink-0 mt-0.5" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-3.5 w-36 rounded" />
            <Skeleton className="h-3 w-full rounded" />
            <Skeleton className="h-3 w-48 rounded" />
          </div>
        </div>
      ))}
    </div>
  );
}

function LiveTab({ onOpen }: { onOpen: (a: AlertNotification) => void }) {
  const patternRecord = usePatternRecord();
  const { alerts, isLoading, acknowledgeAll } = useAlerts();
  const weekCounts = useMemo(() => buildWeekCounts(alerts), [alerts]);
  const live = useMemo(
    () => alerts
      .filter(a => !a.acknowledged)
      .sort((a, b) => new Date(b.shown_at ?? 0).getTime() - new Date(a.shown_at ?? 0).getTime()),
    [alerts]
  );

  if (isLoading) return <AlertSkeleton />;

  if (live.length === 0) {
    // "Nothing left to review" is NOT the same as "you traded well". Only praise a
    // genuinely clean window (no alerts fired at all). If alerts fired and were merely
    // acknowledged, stay neutral — praising discipline on a day with danger alerts
    // contradicts the alert stream and the whole "mirror" premise.
    const totalFired = alerts.length;
    const dangerFired = alerts.filter(a => a.pattern.severity === 'danger').length;
    const cleanWindow = totalFired === 0;
    return (
      <div className="tm-card px-5 py-6 flex items-start gap-4">
        <div className="w-8 h-8 rounded-full bg-teal-50 dark:bg-teal-900/20 flex items-center justify-center flex-shrink-0 mt-0.5">
          <Shield className="h-4 w-4 text-tm-brand" />
        </div>
        <div>
          <p className="text-[13px] font-semibold text-foreground">
            {cleanWindow ? 'Clean session' : 'All caught up'}
          </p>
          <p className="text-[12px] text-muted-foreground mt-0.5 leading-relaxed">
            {cleanWindow
              ? "No active behavioral alerts. You're trading with discipline — keep it up."
              : `You've reviewed all ${totalFired} alert${totalFired !== 1 ? 's' : ''} from this period${dangerFired > 0 ? ` (${dangerFired} danger)` : ''}. Nothing left to review.`}
          </p>
          <p className="text-[11px] text-muted-foreground/60 mt-2">
            Alerts appear here as they fire. Check History to review past patterns.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-2.5">
      <div className="flex items-center justify-between">
        <p className="text-[12px] text-muted-foreground">
          {live.length} unreviewed alert{live.length !== 1 ? 's' : ''} · tap to open
        </p>
        <button
          onClick={acknowledgeAll}
          className="flex items-center gap-1.5 text-[11px] text-muted-foreground hover:text-foreground transition-colors"
        >
          <CheckCheck className="h-3.5 w-3.5" />
          Mark all reviewed
        </button>
      </div>
      <div className="tm-card overflow-hidden">
        {live.map(alert => (
          <AlertRow
            key={alert.id}
            alert={alert}
            onOpen={onOpen}
            weekCount={weekCounts[alert.pattern.type ?? alert.pattern.backend_type] ?? 0}
            record={patternRecord[alert.pattern.backend_type ?? alert.pattern.type ?? '']}
          />
        ))}
      </div>
    </div>
  );
}

// ─── History Tab ──────────────────────────────────────────────────────────────

// Severity vocabulary is the app-wide 3-level scale (danger/caution/positive).
// The backend's info/critical collapse into caution/danger via normalizeSeverityStr.
const SEVERITY_OPTIONS = [
  { value: 'all',     label: 'All' },
  { value: 'danger',  label: 'Danger' },
  { value: 'caution', label: 'Caution' },
];

const PERIOD_OPTIONS = [
  { label: '7d',  hours: 168  },
  { label: '30d', hours: 720  },
  { label: '90d', hours: 2160 },
] as const;

function HistoryTab({ onOpen }: { onOpen: (a: AlertNotification) => void }) {
  const patternRecord = usePatternRecord();
  // History has its own data source — loads independently of AlertContext
  // so users can see alerts beyond the 7-day live window.
  const [hours, setHours] = useState(168);
  const [sevFilter, setSevFilter] = useState('all');
  // History is a SEPARATE data source from AlertContext on purpose: the context
  // holds the live 7-day window fed by the WebSocket, this reads further back.
  // Only this historical read is cached — the live alert stream stays entirely
  // on the socket, because a cache in front of it would be a second source of
  // truth for the same alerts.
  const historyQ = useApiQuery<{ alerts: unknown[] }>(
    ['risk', 'alerts', 'history'],
    '/api/risk/alerts',
    { params: { hours } },
  );

  const loading = historyQ.isPending;
  const error = historyQ.error;

  const allAlerts = useMemo<AlertNotification[]>(() => {
    // Never fall back to [] on failure — the error branch above owns that case,
    // and an empty list here would render "no alerts in this period".
    const raw = historyQ.data?.alerts ?? [];
    // Use the same shape AlertContext uses — map raw to AlertNotification
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const mapped: AlertNotification[] = raw.map((a: any) => ({
        id: String(a.id),
        pattern: {
          id:                  String(a.id),
          type:                a.pattern_type,
          backend_type:        a.pattern_type,
          name:                formatPatternName(a.pattern_type),
          severity:            normalizeSeverityStr(a.severity),
          description:         a.message,
          detected_at:         a.detected_at || a.created_at,
          insight:             a.details?.insight || '',
          historical_insight:  a.details?.historical_insight || '',
          estimated_cost:      (a.details?.estimated_cost as number) ?? 0,
          trades_involved:     [],
          frequency_this_week:  0,
          frequency_this_month: 0,
          confidence:          a.confidence ?? null,
          outcome:             a.outcome ?? null,
          details:             a.details ?? {},
        },
        shown_at:     a.detected_at || a.created_at,
        acknowledged: a.acknowledged ?? (a.acknowledged_at != null),
      }));
    mapped.sort((a, b) => new Date(b.shown_at ?? 0).getTime() - new Date(a.shown_at ?? 0).getTime());
    return mapped;
  }, [historyQ.data]);

  const weekCounts = useMemo(() => buildWeekCounts(allAlerts), [allAlerts]);
  const filtered = useMemo(
    () => sevFilter === 'all' ? allAlerts : allAlerts.filter(a => a.pattern.severity === sevFilter),
    [allAlerts, sevFilter]
  );

  return (
    <div className="space-y-4">
      {/* Controls row */}
      <div className="flex items-center gap-3 flex-wrap">
        {/* Period selector */}
        <div className="flex items-center gap-0.5 p-0.5 bg-muted rounded-lg">
          {PERIOD_OPTIONS.map(opt => (
            <button
              key={opt.hours}
              onClick={() => setHours(opt.hours)}
              aria-pressed={hours === opt.hours}
              className={cn(
                'px-3 py-1 text-[11px] font-medium rounded-md transition-all',
                hours === opt.hours
                  ? 'bg-card text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              )}
            >
              {opt.label}
            </button>
          ))}
        </div>

        {/* Severity filter */}
        <div className="flex items-center gap-0.5 p-0.5 bg-muted rounded-lg">
          {SEVERITY_OPTIONS.map(opt => (
            <button
              key={opt.value}
              onClick={() => setSevFilter(opt.value)}
              aria-pressed={sevFilter === opt.value}
              className={cn(
                'px-3 py-1 text-[11px] font-medium rounded-md transition-all',
                sevFilter === opt.value
                  ? 'bg-card text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              )}
            >
              {opt.label}
            </button>
          ))}
        </div>

        {!loading && (
          <p className="text-[11px] text-muted-foreground ml-auto">
            {filtered.length} alert{filtered.length !== 1 ? 's' : ''}
          </p>
        )}
      </div>

      {loading ? <AlertSkeleton /> : error ? (
        <ErrorState error={error} onRetry={() => historyQ.refetch()} />
      ) : filtered.length === 0 ? (
        <div className="tm-card flex flex-col items-center justify-center py-12 text-center">
          <BellOff className="h-8 w-8 text-muted-foreground/30 mb-3" />
          <p className="text-sm text-muted-foreground">
            {allAlerts.length === 0 ? 'No alerts in this period' : 'No alerts match this filter'}
          </p>
        </div>
      ) : (
        <div className="tm-card overflow-hidden">
          {filtered.map(alert => (
            <AlertRow
              key={alert.id}
              alert={alert}
              onOpen={onOpen}
              weekCount={weekCounts[alert.pattern.type ?? alert.pattern.backend_type] ?? 0}
              record={patternRecord[alert.pattern.backend_type ?? alert.pattern.type ?? '']}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Patterns Tab ─────────────────────────────────────────────────────────────

interface PatternSummary {
  type: string;
  name: string;
  count: number;
  latestAt: string | undefined;
  severities: Record<PatternSeverity, number>;
  worstSeverity: PatternSeverity;
}

// Worst → least severe (index 0 = worst). Matches the app-wide 3-level scale.
// Worst first — index order IS the ranking (see worstSeverity below), so
// critical has to lead. Omitting it did not just hide a badge: indexOf
// returned -1 and the alert was skipped when picking a group's worst.
const SEVERITY_ORDER: PatternSeverity[] = ['critical', 'danger', 'caution', 'positive'];

function PatternsTab() {
  const { alerts, isLoading } = useAlerts();

  const summaries = useMemo<PatternSummary[]>(() => {
    const map = new Map<string, PatternSummary>();
    for (const alert of alerts) {
      const key = alert.pattern.type;
      const existing = map.get(key) ?? {
        type: key,
        name: alert.pattern.name,
        count: 0,
        latestAt: undefined,
        severities: { critical: 0, danger: 0, caution: 0, positive: 0 },
        worstSeverity: 'positive' as PatternSeverity,
      };
      existing.count++;
      existing.severities[alert.pattern.severity]++;
      const dt = alert.shown_at;
      if (!existing.latestAt || (dt && dt > existing.latestAt)) existing.latestAt = dt;
      const idx = SEVERITY_ORDER.indexOf(alert.pattern.severity);
      if (idx !== -1 && idx < SEVERITY_ORDER.indexOf(existing.worstSeverity)) {
        existing.worstSeverity = alert.pattern.severity;
      }
      map.set(key, existing);
    }
    return Array.from(map.values()).sort((a, b) => b.count - a.count);
  }, [alerts]);

  if (isLoading) return <AlertSkeleton />;

  if (summaries.length === 0) {
    return (
      <div className="tm-card flex flex-col items-center justify-center py-16 text-center">
        <TrendingUp className="h-8 w-8 text-muted-foreground/30 mb-3" />
        <p className="text-sm font-medium text-foreground">No pattern data yet</p>
        <p className="text-sm text-muted-foreground mt-1">Patterns appear here as the engine detects behaviors</p>
      </div>
    );
  }

  const maxCount = Math.max(...summaries.map(x => x.count));

  return (
    <div className="space-y-2.5">
      <p className="text-[12px] text-muted-foreground">
        {summaries.length} distinct pattern{summaries.length !== 1 ? 's' : ''} detected in the last 7 days
      </p>
      {summaries.map(s => (
        <div key={s.type} className={cn(
          'tm-card border-l-[3px] px-4 py-3.5',
          severityBorderClass(s.worstSeverity),
          severityRowBg(s.worstSeverity),
        )}>
          <div className="flex items-start justify-between gap-3 mb-2.5">
            <div className="flex items-center gap-2 min-w-0">
              <span className={cn('w-2 h-2 rounded-full flex-shrink-0', SEV_DOT[s.worstSeverity])} />
              <span className="text-[13px] font-semibold text-foreground">{s.name}</span>
              <span className={cn('text-[10px] font-semibold uppercase', SEV_LABEL_COLOR[s.worstSeverity])}>
                {SEV_LABEL[s.worstSeverity]}
              </span>
            </div>
            <div className="text-right flex-shrink-0">
              <span className="t-mono-lg text-foreground">{s.count}</span>
              <span className="text-[11px] text-muted-foreground ml-1">×</span>
            </div>
          </div>

          {/* Frequency bar */}
          <div className="w-full bg-muted rounded-full h-1 mb-2.5">
            <div
              className={cn('h-1 rounded-full transition-all', SEV_DOT[s.worstSeverity])}
              style={{ width: `${Math.min((s.count / maxCount) * 100, 100)}%` }}
            />
          </div>

          <div className="flex items-center justify-between text-[11px] text-muted-foreground">
            <div className="flex items-center gap-2">
              {SEVERITY_ORDER.map(sev => s.severities[sev] > 0 && (
                <span key={sev} className="flex items-center gap-1">
                  <span className={cn('w-1.5 h-1.5 rounded-full', SEV_DOT[sev])} />
                  {s.severities[sev]} {SEV_LABEL[sev]}
                </span>
              ))}
            </div>
            {s.latestAt && (
              <span title={formatIST(s.latestAt)}>Last: {timeAgo(s.latestAt)}</span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function AlertsPage() {
  const { alerts, acknowledgeAlert } = useAlerts();
  const [selectedAlert, setSelectedAlert] = useState<AlertNotification | null>(null);

  // Page-local unreviewed count over the SAME window the Unreviewed tab lists
  // (7 days). The context's unacknowledgedCount is today-only (nav badge) —
  // using it here made the badge read 0 while the list showed older rows.
  const stats = useMemo(() => ({
    total:   alerts.length,
    danger:  alerts.filter(a => a.pattern.severity === 'danger').length,
    unacked: alerts.filter(a => !a.acknowledged).length,
  }), [alerts]);

  return (
    <div className="pb-12">
      {/* Page header */}
      <div className="mb-5 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h1 className="t-heading-lg text-foreground">Behavioral Alerts</h1>
          {stats.unacked > 0 && (
            <span className="bg-tm-loss text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full leading-none">
              {stats.unacked}
            </span>
          )}
        </div>
        {/* Inline stat strip */}
        {stats.total > 0 && (
          <div className="flex items-center gap-3 text-[12px] text-muted-foreground">
            <span>{stats.total} total</span>
            {stats.danger > 0 && <><span className="text-muted-foreground/40">·</span><span className="text-tm-loss">{stats.danger} danger</span></>}
            {stats.unacked > 0 && <><span className="text-muted-foreground/40">·</span><span className="text-tm-obs">{stats.unacked} unread</span></>}
          </div>
        )}
      </div>

      {/* Tabs */}
      <Tabs defaultValue="live">
        <TabsList className="w-full justify-start rounded-none bg-transparent border-b border-border p-0 h-auto gap-0 mb-6">
          {([
            { value: 'live',     label: 'Unreviewed', badge: stats.unacked },
            { value: 'history',  label: 'History',    badge: 0 },
            { value: 'patterns', label: 'Patterns',   badge: 0 },
          ] as const).map(({ value, label, badge }) => (
            <TabsTrigger
              key={value}
              value={value}
              className="relative rounded-none bg-transparent border-b-2 border-transparent px-4 py-2.5 text-sm text-muted-foreground hover:text-foreground transition-colors data-[state=active]:border-tm-brand data-[state=active]:bg-transparent data-[state=active]:text-foreground data-[state=active]:shadow-none"
            >
              {label}
              {badge > 0 && (
                <span className="ml-1.5 bg-tm-loss text-white text-[9px] font-bold px-1.5 py-0.5 rounded-full leading-none">
                  {badge}
                </span>
              )}
            </TabsTrigger>
          ))}
        </TabsList>

        <TabsContent value="live"><LiveTab onOpen={setSelectedAlert} /></TabsContent>
        <TabsContent value="history"><HistoryTab onOpen={setSelectedAlert} /></TabsContent>
        <TabsContent value="patterns">
          <div className="space-y-5">
            {/* One dominant region first: the leak worth acting on, and the
                rule that constrains it. Everything below supports it. */}
            <BehaviourLead days={30} />

            {/* What keeps repeating -- counts and recency, no money. Analytics
                owns quantified cost; this page owns the loop and the
                repetition, so neither recomputes the other's story. */}
            <PatternFrequencyCard days={30} />

            {/* How you actually responded: the accountability half of the loop. */}
            <ResponseStatsCard />

            {/* Behaviour to realized money, kept here now that patterns live on
                this page rather than in Analytics. */}
            <BehaviourCostCard days={90} />

            {/* When the patterns fired, as a calendar. */}
            <PatternCalendar />
            {/* Consecutive clean days. Now self-contained, so it can live on
                this page without forking MyPatterns' derivation. */}
            <CleanDayStreak />

            <PatternsTab />
          </div>
        </TabsContent>
      </Tabs>

      {/* Alert detail sheet */}
      <AlertDetailSheet
        alert={selectedAlert}
        open={selectedAlert !== null}
        onClose={() => setSelectedAlert(null)}
        onAcknowledge={acknowledgeAlert}
      />
    </div>
  );
}
