import { useState, useEffect, useCallback } from 'react';
import {
  Sunrise, BarChart2, CalendarDays, ChevronDown, ChevronUp,
  FileText, TrendingUp, TrendingDown, Loader2,
  AlertTriangle, CheckCircle2, Target, Lightbulb, Shield, Link2,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { formatCurrency, formatCurrencyWithSign, formatCurrencyWhole } from '@/lib/formatters';
import { Skeleton } from '@/components/ui/skeleton';
import ErrorState from '@/components/ErrorState';
import { api } from '@/lib/api';
import { useApiInfiniteQuery } from '@/hooks/useApiInfiniteQuery';
import { useBroker } from '@/contexts/BrokerContext';
import { EodComparisonCard } from '@/components/dashboard/EodComparisonCard';

// ─── Types ──────────────────────────────────────────────────────────────────

type ReportType = 'all' | 'morning_briefing' | 'post_market' | 'weekly_summary';

interface ReportSummary {
  id: string;
  report_type: string;
  report_date: string;
  generated_at: string;
  sent_via: string | null;
  // type-specific preview fields
  total_pnl?: number;
  total_trades?: number;
  win_rate?: number;
  readiness_score?: number;
  watch_out_count?: number;
}

interface ReportDetail extends ReportSummary {
  report_data: Record<string, any>;
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

const TYPE_META: Record<string, { label: string; icon: React.ComponentType<any> }> = {
  morning_briefing: { label: 'Morning brief', icon: Sunrise },
  post_market:      { label: 'End of day',    icon: BarChart2 },
  weekly_summary:   { label: 'Weekly',        icon: CalendarDays },
};

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString('en-IN', {
    day: 'numeric', month: 'short', year: 'numeric',
  });
}

function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString('en-IN', {
    hour: '2-digit', minute: '2-digit', hour12: false,
  });
}

// ─── Detail Renderers ─────────────────────────────────────────────────────────

function PostMarketDetail({ data }: { data: Record<string, any> }) {
  const s = data.summary || {};
  const lessons = data.key_lessons || [];
  const tomorrow = data.tomorrow_focus || {};
  const journey = data.emotional_journey || {};
  const patterns = data.patterns_detected || [];

  return (
    <div className="space-y-5 pt-4 border-t border-border">
      {/* Stats row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: 'P&L', value: formatCurrencyWhole((s.total_pnl ?? 0)), color: s.total_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss' },
          { label: 'Trades', value: s.total_trades ?? 0, color: 'text-foreground' },
          { label: 'Win Rate', value: `${s.win_rate ?? 0}%`, color: 'text-foreground' },
          { label: 'Profit Factor', value: s.profit_factor ?? '—', color: 'text-foreground' },
        ].map(stat => (
          <div key={stat.label} className="bg-muted/40 rounded-lg p-3">
            <p className="text-[10px] uppercase tracking-widest text-muted-foreground mb-1">{stat.label}</p>
            <p className={cn('text-[20px] font-bold font-mono tabular-nums', stat.color)}>{stat.value}</p>
          </div>
        ))}
      </div>

      {/* Peak vs close — the giveback, as a reported fact. `profit_giveaway`
          was retired as an alert (the drawdown is arithmetic); the number is
          still worth seeing after the close. */}
      {journey.peak_pnl > 0 && (
        <div>
          <p className="text-[12px] font-medium text-muted-foreground mb-2">Peak vs close</p>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {[
              { label: 'Session peak', value: formatCurrencyWhole(journey.peak_pnl), color: 'text-tm-profit' },
              { label: 'Finished', value: formatCurrencyWhole(journey.final_pnl),
                color: journey.finished_green ? 'text-tm-profit' : 'text-tm-loss' },
              { label: 'Given back', value: formatCurrencyWhole(journey.given_back ?? 0),
                color: (journey.given_back ?? 0) > 0 ? 'text-tm-loss' : 'text-foreground' },
              { label: '% of peak', value: journey.given_back_pct != null ? `${journey.given_back_pct}%` : '—',
                color: 'text-foreground' },
            ].map(stat => (
              <div key={stat.label} className="bg-muted/40 rounded-lg p-3">
                <p className="text-[10px] uppercase tracking-widest text-muted-foreground mb-1">{stat.label}</p>
                <p className={cn('text-[20px] font-bold font-mono tabular-nums', stat.color)}>{stat.value}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Emotional journey */}
      {journey.timeline?.length > 0 && (
        <div>
          <p className="text-[12px] font-medium text-muted-foreground mb-2">Emotional Journey</p>
          <div className="flex flex-wrap gap-2">
            {journey.timeline.map((entry: any, i: number) => (
              <div key={i} className="flex items-center gap-1.5 bg-muted/40 rounded-lg px-2.5 py-1.5 text-[12px]">
                <span className="text-[16px]">{entry.emoji}</span>
                <span className="font-medium text-foreground">{entry.symbol}</span>
                <span className={cn('font-mono tabular-nums', entry.pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
                  {formatCurrencyWhole((entry.pnl))}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Patterns */}
      {patterns.length > 0 && (
        <div>
          <p className="text-[12px] font-medium text-muted-foreground mb-2">Patterns Detected</p>
          <div className="flex flex-wrap gap-2">
            {patterns.map((p: any, i: number) => (
              <span key={i} className={cn(
                'inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-medium border',
                p.severity === 'danger' ? 'bg-red-50 dark:bg-red-900/20 text-tm-loss border-red-200 dark:border-red-800' :
                  'bg-orange-50 dark:bg-orange-900/20 text-orange-700 dark:text-orange-400 border-orange-200 dark:border-orange-800'
              )}>
                <AlertTriangle className="h-3 w-3" />
                {p.pattern?.replace(/_/g, ' ')} · {p.time}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Lessons */}
      {lessons.length > 0 && (
        <div>
          <p className="text-[12px] font-medium text-muted-foreground mb-2">Key Lessons</p>
          <div className="space-y-2">
            {lessons.slice(0, 3).map((l: any, i: number) => (
              <div key={i} className={cn(
                'flex gap-3 rounded-lg p-3 text-[14px] border',
                l.type === 'positive' ? 'bg-tm-profit/10 border-tm-profit/20' :
                  l.type === 'warning' ? 'bg-tm-obs/10 border-tm-obs/20' :
                    'bg-muted/40 border-border'
              )}>
                <Lightbulb className="h-4 w-4 mt-0.5 shrink-0 text-muted-foreground" />
                <p className="text-foreground">{l.lesson}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tomorrow focus */}
      {tomorrow.primary && (
        <div className="rounded-lg border border-tm-brand/20 bg-teal-50/50 dark:bg-teal-900/10 p-4">
          <div className="flex items-center gap-2 mb-2">
            <Target className="h-4 w-4 text-tm-brand" />
            <p className="text-[12px] font-semibold text-tm-brand uppercase tracking-widest">Tomorrow's Focus</p>
          </div>
          <p className="text-[14px] font-semibold text-foreground">{tomorrow.primary}</p>
          {tomorrow.rule && <p className="text-[12px] text-muted-foreground mt-1">Rule: {tomorrow.rule}</p>}
          {tomorrow.affirmation && <p className="text-[12px] italic text-muted-foreground mt-1">"{tomorrow.affirmation}"</p>}
        </div>
      )}
    </div>
  );
}

function MorningBriefDetail({ data }: { data: Record<string, any> }) {
  const readiness = data.readiness_score || {};
  const watchOuts = data.watch_outs || [];
  const checklist = data.checklist || [];
  const recent = data.recent_summary || {};
  const trend = data.trend_stats;

  const scoreColor = readiness.status === 'warning' ? 'text-tm-loss' :
    readiness.status === 'caution' ? 'text-tm-obs' : 'text-tm-profit';

  return (
    <div className="space-y-5 pt-4 border-t border-border">
      {/* Readiness */}
      <div className="flex items-center gap-6">
        <div>
          <p className="text-[10px] uppercase tracking-widest text-muted-foreground mb-1">Readiness</p>
          <p className={cn('text-4xl font-bold font-mono tabular-nums', scoreColor)}>{readiness.score ?? '—'}<span className="text-[18px]">/100</span></p>
        </div>
        <div className="flex-1 text-[14px] text-muted-foreground">{readiness.message}</div>
      </div>

      {/* The day_warning banner - "Friday is historically your WORST trading
          day" / the BEST-day mirror - was removed 2026-09-01 with the retirement
          of the learned danger_days / best_days.
          See docs/patterns/25-27-performance-trio/. */}

      {/* Recent summary */}
      {recent.has_recent_trades && (
        <div className="text-[14px] text-muted-foreground bg-muted/40 rounded-lg p-3">{recent.message}</div>
      )}

      {/* Trend stats */}
      {trend && (trend.seven_day?.has_data || trend.thirty_day?.has_data) && (
        <div>
          <p className="text-[12px] font-medium text-muted-foreground mb-2">Rolling Performance</p>
          <div className="grid grid-cols-2 gap-3">
            {[
              { label: '7-Day', data: trend.seven_day },
              { label: '30-Day', data: trend.thirty_day },
            ].map(({ label, data: d }) => d?.has_data ? (
              <div key={label} className="bg-muted/40 rounded-lg p-3">
                <p className="text-[10px] uppercase tracking-widest text-muted-foreground mb-1">{label}</p>
                <p className={cn('text-[20px] font-bold font-mono tabular-nums', (d.total_pnl ?? 0) >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
                  {formatCurrencyWhole((d.total_pnl ?? 0))}
                </p>
                <p className="text-[12px] text-muted-foreground mt-0.5">{d.win_rate}% win rate · {d.trade_count} trades</p>
              </div>
            ) : null)}
          </div>
          {trend.trend && (
            <p className={cn('text-[12px] mt-2', trend.trend === 'improving' ? 'text-tm-profit' : trend.trend === 'declining' ? 'text-tm-obs' : 'text-muted-foreground')}>
              {trend.trend === 'improving' ? '↑ Win rate improving vs 30-day average' : trend.trend === 'declining' ? '↓ Win rate declining vs 30-day average' : '→ Win rate stable vs 30-day average'}
            </p>
          )}
        </div>
      )}

      {/* Watch-outs */}
      {watchOuts.length > 0 && (
        <div>
          <p className="text-[12px] font-medium text-muted-foreground mb-2">Watch-Outs</p>
          <div className="space-y-2">
            {watchOuts.map((wo: any, i: number) => (
              <div key={i} className={cn(
                'flex gap-2 rounded-lg border p-2.5 text-[14px]',
                wo.severity === 'high' ? 'bg-tm-loss/10 border-tm-loss/20' :
                  wo.severity === 'medium' ? 'bg-tm-obs/10 border-tm-obs/20' :
                    'bg-muted/40 border-border'
              )}>
                <span className="text-[16px]">{wo.icon}</span>
                <p className="text-foreground">{wo.message}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Checklist */}
      {checklist.length > 0 && (
        <div>
          <p className="text-[12px] font-medium text-muted-foreground mb-2">Mental Checklist</p>
          <div className="space-y-1.5">
            {checklist.map((item: any, i: number) => (
              <div key={i} className="flex items-start gap-2 text-[14px] text-foreground">
                <CheckCircle2 className="h-4 w-4 mt-0.5 shrink-0 text-muted-foreground" />
                {item.item}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function WeeklySummaryDetail({ data }: { data: Record<string, any> }) {
  const tw = data.this_week || {};
  const lw = data.last_week || {};
  const imp = data.improvements || {};

  return (
    <div className="space-y-5 pt-4 border-t border-border">
      <div className="grid grid-cols-2 gap-4">
        {[
          { label: 'This Week', stats: tw },
          { label: 'Last Week', stats: lw },
        ].map(({ label, stats }) => (
          <div key={label} className="bg-muted/40 rounded-lg p-4 space-y-2">
            <p className="text-[12px] font-semibold uppercase tracking-widest text-muted-foreground">{label}</p>
            <p className={cn('text-[24px] font-bold font-mono tabular-nums', (stats.total_pnl ?? 0) >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
              {formatCurrencyWhole((stats.total_pnl ?? 0))}
            </p>
            <div className="flex gap-4 text-[12px] text-muted-foreground">
              <span>{stats.total_trades ?? 0} trades</span>
              <span>{stats.win_rate ?? 0}% win rate</span>
              <span>{stats.danger_alerts ?? 0} alerts</span>
            </div>
          </div>
        ))}
      </div>

      {Object.keys(imp).length > 0 && (
        <div>
          <p className="text-[12px] font-medium text-muted-foreground mb-2">Week-over-Week</p>
          <div className="space-y-1.5">
            {imp.pnl && (
              <div className="flex items-center gap-2 text-[14px]">
                {imp.pnl.improved ? <TrendingUp className="h-4 w-4 text-tm-profit" /> : <TrendingDown className="h-4 w-4 text-tm-loss" />}
                <span className="text-foreground">P&L {imp.pnl.improved ? 'up' : 'down'} {formatCurrency(Math.abs(imp.pnl.change))} vs last week</span>
              </div>
            )}
            {imp.win_rate && (
              <div className="flex items-center gap-2 text-[14px]">
                {imp.win_rate.improved ? <TrendingUp className="h-4 w-4 text-tm-profit" /> : <TrendingDown className="h-4 w-4 text-tm-loss" />}
                <span className="text-foreground">Win rate {imp.win_rate.improved ? '+' : ''}{imp.win_rate.change}pp vs last week</span>
              </div>
            )}
            {imp.danger_alerts && (
              <div className="flex items-center gap-2 text-[14px]">
                {imp.danger_alerts.improved ? <Shield className="h-4 w-4 text-tm-profit" /> : <AlertTriangle className="h-4 w-4 text-tm-obs" />}
                <span className="text-foreground">{imp.danger_alerts.message}</span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Report Card ──────────────────────────────────────────────────────────────

function ReportCard({ report }: { report: ReportSummary }) {
  const [expanded, setExpanded] = useState(false);
  const [detail, setDetail] = useState<ReportDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  const meta = TYPE_META[report.report_type] ?? TYPE_META.post_market;
  const Icon = meta.icon;

  const handleExpand = useCallback(async () => {
    if (!expanded && !detail) {
      setLoadingDetail(true);
      try {
        const res = await api.get(`/api/reports/saved/${report.id}`);
        setDetail(res.data);
      } catch {
        // ignore — expand still opens, just no detail
      } finally {
        setLoadingDetail(false);
      }
    }
    setExpanded(v => !v);
  }, [expanded, detail, report.id]);

  return (
    <div className="border-b border-border last:border-b-0">
      {/* Header row */}
      <button
        onClick={handleExpand}
        className="w-full px-5 py-4 flex items-start gap-4 text-left hover:bg-muted/60 transition-colors"
      >
        {/* Type badge */}
        <div className="flex items-center gap-1.5 rounded-md border border-border px-2 py-1 shrink-0 text-muted-foreground">
          <Icon className={cn('h-3.5 w-3.5', 'text-muted-foreground')} />
          <span className={cn('text-[11px] font-semibold', 'text-muted-foreground')}>{meta.label}</span>
        </div>

        {/* Date + time */}
        <div className="flex-1 min-w-0">
          <p className="text-[14px] font-semibold text-foreground">{formatDate(report.report_date)}</p>
          <p className="text-[12px] text-muted-foreground mt-0.5">Generated {formatTime(report.generated_at)}{report.sent_via ? ' · sent via WhatsApp' : ''}</p>
        </div>

        {/* Preview metrics */}
        <div className="flex items-center gap-4 shrink-0 mr-2">
          {report.report_type === 'post_market' && report.total_pnl !== undefined && (
            <>
              <div className="text-right">
                <p className="text-[10px] text-muted-foreground">P&L</p>
                <p className={cn('text-[16px] font-bold font-mono tabular-nums', report.total_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
                  {formatCurrencyWhole((report.total_pnl))}
                </p>
              </div>
              <div className="text-right">
                <p className="text-[10px] text-muted-foreground">Win Rate</p>
                <p className="text-[16px] font-bold font-mono tabular-nums text-foreground">{report.win_rate ?? 0}%</p>
              </div>
            </>
          )}
          {report.report_type === 'morning_briefing' && report.readiness_score !== undefined && (
            <div className="text-right">
              <p className="text-[10px] text-muted-foreground">Readiness</p>
              <p className={cn(
                'text-[16px] font-bold font-mono tabular-nums',
                report.readiness_score >= 80 ? 'text-tm-profit' :
                  report.readiness_score >= 60 ? 'text-tm-obs' : 'text-tm-loss'
              )}>
                {report.readiness_score}/100
              </p>
            </div>
          )}
          {report.report_type === 'weekly_summary' && report.total_pnl !== undefined && (
            <div className="text-right">
              <p className="text-[10px] text-muted-foreground">Week P&L</p>
              <p className={cn('text-[16px] font-bold font-mono tabular-nums', report.total_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
                {formatCurrencyWhole((report.total_pnl))}
              </p>
            </div>
          )}
        </div>

        {/* Expand chevron */}
        <div className="text-muted-foreground shrink-0 mt-0.5">
          {loadingDetail ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : expanded ? (
            <ChevronUp className="h-4 w-4" />
          ) : (
            <ChevronDown className="h-4 w-4" />
          )}
        </div>
      </button>

      {/* Expanded detail */}
      {expanded && detail && (
        <div className="overflow-hidden animate-fade-in">
          <div className="px-5 pb-5">
            {detail.report_type === 'post_market' && (
              <PostMarketDetail data={detail.report_data} />
            )}
            {detail.report_type === 'morning_briefing' && (
              <MorningBriefDetail data={detail.report_data} />
            )}
            {detail.report_type === 'weekly_summary' && (
              <WeeklySummaryDetail data={detail.report_data} />
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

const FILTER_TABS: { value: ReportType; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'morning_briefing', label: 'Morning Brief' },
  { value: 'post_market', label: 'End of Day' },
  { value: 'weekly_summary', label: 'Weekly' },
];

export default function Reports() {
  const { isConnected } = useBroker();
  const [filter, setFilter] = useState<ReportType>('all');
  // The filter is part of the key, so switching back to a filter you already
  // viewed reads its cached pages instead of starting over at page one.
  const reportsQ = useApiInfiniteQuery<
    { reports: ReportSummary[]; total: number },
    ReportSummary
  >(
    ['reports', 'saved'],
    '/api/reports/saved',
    {
      pageSize: 20,
      getItems: page => page.reports ?? [],
      params: filter !== 'all' ? { report_type: filter } : undefined,
    },
  );

  const reports = reportsQ.items;
  const total = reportsQ.data?.pages[0]?.total ?? 0;
  const isLoading = reportsQ.isPending;
  const loadingMore = reportsQ.isFetchingNextPage;
  // Still never fake "no reports" on a failed load.
  const error = reportsQ.error;

  const handleLoadMore = () => reportsQ.fetchNextPage();

  // Group reports by date
  const grouped: Record<string, ReportSummary[]> = {};
  for (const r of reports) {
    const d = r.report_date;
    if (!grouped[d]) grouped[d] = [];
    grouped[d].push(r);
  }
  const sortedDates = Object.keys(grouped).sort((a, b) => b.localeCompare(a));

  if (!isConnected) {
    return (
      <div className="pb-12">
        <div className="mb-5"><h1 className="t-heading-lg text-foreground">Reports</h1></div>
        <div className="tm-card flex flex-col items-center justify-center min-h-[50vh] text-center py-16">
          <div className="p-4 rounded-full bg-teal-50 dark:bg-teal-900/20 mb-5">
            <Link2 className="h-10 w-10 text-tm-brand" />
          </div>
          <h2 className="text-[16px] font-semibold text-foreground mb-1">Connect Your Broker</h2>
          <p className="text-[14px] text-muted-foreground text-center max-w-sm mb-5">
            Connect your Zerodha account to view your saved reports.
          </p>
          <Link to="/settings">
            <Button size="sm" className="gap-2 bg-tm-brand hover:bg-tm-brand/90 text-white">
              <Link2 className="h-4 w-4" />
              Connect Zerodha
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-12">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="t-heading-lg text-foreground">Reports</h1>
          <p className="text-[14px] text-muted-foreground mt-0.5">
          </p>
        </div>
      </div>

      {/* Today vs last session — moved here from the Dashboard (EOD lives in Reports) */}
      <EodComparisonCard />

      {/* Filter tabs */}
      <div className="flex gap-2 flex-wrap">
        {FILTER_TABS.map(tab => (
          <button
            key={tab.value}
            onClick={() => setFilter(tab.value)}
            className={cn(
              'h-8 px-3 rounded-md text-[12.5px] font-medium transition-colors border',
              filter === tab.value
                ? 'bg-muted text-foreground border-border'
                : 'bg-transparent text-muted-foreground border-border hover:text-foreground'
            )}
          >
            {tab.label}
          </button>
        ))}
        {total > 0 && (
          <span className="ml-auto text-[12px] text-muted-foreground self-center">{total} report{total !== 1 ? 's' : ''}</span>
        )}
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="space-y-3">
          {[1,2,3].map(i => <Skeleton key={i} className="h-16 rounded-lg" />)}
        </div>
      ) : error ? (
        <ErrorState error={error} onRetry={() => reportsQ.refetch()} />
      ) : reports.length === 0 ? (
        <div className="flex flex-col items-center justify-center min-h-[30vh] rounded-lg border border-border bg-card">
          <FileText className="h-10 w-10 text-muted-foreground/40 mb-3" />
          <p className="font-medium text-foreground">No reports yet</p>
          <p className="text-[14px] text-muted-foreground mt-1">
            Reports are saved automatically when your daily briefs are sent
          </p>
        </div>
      ) : (
        <div className="space-y-6">
          {sortedDates.map(date => (
            <div key={date}>
              {/* Date separator */}
              <div className="flex items-center gap-3 mb-3">
                <p className="text-[12px] font-semibold text-muted-foreground uppercase tracking-widest whitespace-nowrap">
                  {formatDate(date)}
                </p>
                <div className="flex-1 h-px bg-border" />
              </div>
              <div className="tm-card overflow-hidden">
                {grouped[date].map(r => (
                  <ReportCard key={r.id} report={r} />
                ))}
              </div>
            </div>
          ))}

          {/* Load more */}
          {reportsQ.hasNextPage && (
            <div className="flex justify-center pt-2">
              <button
                onClick={handleLoadMore}
                disabled={loadingMore}
                className="flex items-center gap-2 px-5 py-2 rounded-full border border-border text-[14px] text-muted-foreground hover:text-foreground hover:border-foreground transition-colors disabled:opacity-50"
              >
                {loadingMore ? <span className="h-4 w-4 animate-spin inline-block border-2 border-current border-t-transparent rounded-full" /> : null}
                Load more ({total - reports.length} remaining)
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
