import { useState, useEffect, useCallback } from 'react';
import {
  Sunrise, BarChart2, CalendarDays, ChevronDown, ChevronUp,
  FileText, Printer, TrendingUp, TrendingDown,
  AlertTriangle, CheckCircle2, Target, Lightbulb, Shield, Link2,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { formatCurrency, formatCurrencyWithSign } from '@/lib/formatters';
import { Skeleton } from '@/components/ui/skeleton';
import { api } from '@/lib/api';
import { useBroker } from '@/contexts/BrokerContext';

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

const TYPE_META: Record<string, { label: string; icon: React.ComponentType<any>; color: string; bg: string }> = {
  morning_briefing: {
    label: 'Morning Brief',
    icon: Sunrise,
    color: 'text-tm-obs',
    bg: 'bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-800',
  },
  post_market: {
    label: 'End of Day',
    icon: BarChart2,
    color: 'text-blue-600 dark:text-blue-400',
    bg: 'bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800',
  },
  weekly_summary: {
    label: 'Weekly Summary',
    icon: CalendarDays,
    color: 'text-violet-600 dark:text-violet-400',
    bg: 'bg-violet-50 dark:bg-violet-900/20 border-violet-200 dark:border-violet-800',
  },
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
          { label: 'P&L', value: formatCurrency(s.total_pnl ?? 0), color: s.total_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss' },
          { label: 'Trades', value: s.total_trades ?? 0, color: 'text-foreground' },
          { label: 'Win Rate', value: `${s.win_rate ?? 0}%`, color: 'text-foreground' },
          { label: 'Profit Factor', value: s.profit_factor ?? '—', color: 'text-foreground' },
        ].map(stat => (
          <div key={stat.label} className="bg-muted/40 rounded-lg p-3">
            <p className="text-[10px] uppercase tracking-widest text-muted-foreground mb-1">{stat.label}</p>
            <p className={cn('text-xl font-bold font-mono tabular-nums', stat.color)}>{stat.value}</p>
          </div>
        ))}
      </div>

      {/* Emotional journey */}
      {journey.timeline?.length > 0 && (
        <div>
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-widest mb-2">Emotional Journey</p>
          <div className="flex flex-wrap gap-2">
            {journey.timeline.map((entry: any, i: number) => (
              <div key={i} className="flex items-center gap-1.5 bg-muted/40 rounded-lg px-2.5 py-1.5 text-xs">
                <span className="text-base">{entry.emoji}</span>
                <span className="font-medium text-foreground">{entry.symbol}</span>
                <span className={cn('font-mono tabular-nums', entry.pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
                  {entry.pnl >= 0 ? '+' : ''}{formatCurrency(entry.pnl)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Patterns */}
      {patterns.length > 0 && (
        <div>
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-widest mb-2">Patterns Detected</p>
          <div className="flex flex-wrap gap-2">
            {patterns.map((p: any, i: number) => (
              <span key={i} className={cn(
                'inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-medium border',
                p.severity === 'danger' ? 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400 border-red-200 dark:border-red-800' :
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
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-widest mb-2">Key Lessons</p>
          <div className="space-y-2">
            {lessons.slice(0, 3).map((l: any, i: number) => (
              <div key={i} className={cn(
                'flex gap-3 rounded-lg p-3 text-sm border',
                l.type === 'positive' ? 'bg-green-50 dark:bg-green-900/10 border-green-200 dark:border-green-800' :
                  l.type === 'warning' ? 'bg-amber-50 dark:bg-amber-900/10 border-amber-200 dark:border-amber-800' :
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
            <p className="text-xs font-semibold text-tm-brand uppercase tracking-widest">Tomorrow's Focus</p>
          </div>
          <p className="text-sm font-semibold text-foreground">{tomorrow.primary}</p>
          {tomorrow.rule && <p className="text-xs text-muted-foreground mt-1">Rule: {tomorrow.rule}</p>}
          {tomorrow.affirmation && <p className="text-xs italic text-muted-foreground mt-1">"{tomorrow.affirmation}"</p>}
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
  const dayWarning = data.day_warning;
  const trend = data.trend_stats;

  const scoreColor = readiness.status === 'warning' ? 'text-tm-loss' :
    readiness.status === 'caution' ? 'text-tm-obs' : 'text-tm-profit';

  return (
    <div className="space-y-5 pt-4 border-t border-border">
      {/* Readiness */}
      <div className="flex items-center gap-6">
        <div>
          <p className="text-[10px] uppercase tracking-widest text-muted-foreground mb-1">Readiness</p>
          <p className={cn('text-4xl font-bold font-mono tabular-nums', scoreColor)}>{readiness.score ?? '—'}<span className="text-lg">/100</span></p>
        </div>
        <div className="flex-1 text-sm text-muted-foreground">{readiness.message}</div>
      </div>

      {/* Day warning */}
      {dayWarning && (
        <div className={cn(
          'rounded-lg border p-3 text-sm',
          dayWarning.is_danger_day
            ? 'bg-red-50 dark:bg-red-900/10 border-red-200 dark:border-red-800 text-red-800 dark:text-red-300'
            : 'bg-green-50 dark:bg-green-900/10 border-green-200 dark:border-green-800 text-green-800 dark:text-green-300'
        )}>
          {dayWarning.message}
        </div>
      )}

      {/* Recent summary */}
      {recent.has_recent_trades && (
        <div className="text-sm text-muted-foreground bg-muted/40 rounded-lg p-3">{recent.message}</div>
      )}

      {/* Trend stats */}
      {trend && (trend.seven_day?.has_data || trend.thirty_day?.has_data) && (
        <div>
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-widest mb-2">Rolling Performance</p>
          <div className="grid grid-cols-2 gap-3">
            {[
              { label: '7-Day', data: trend.seven_day },
              { label: '30-Day', data: trend.thirty_day },
            ].map(({ label, data: d }) => d?.has_data ? (
              <div key={label} className="bg-muted/40 rounded-lg p-3">
                <p className="text-[10px] uppercase tracking-widest text-muted-foreground mb-1">{label}</p>
                <p className={cn('text-xl font-bold font-mono tabular-nums', (d.total_pnl ?? 0) >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
                  {formatCurrency(d.total_pnl ?? 0)}
                </p>
                <p className="text-xs text-muted-foreground mt-0.5">{d.win_rate}% win rate · {d.trade_count} trades</p>
              </div>
            ) : null)}
          </div>
          {trend.trend && (
            <p className={cn('text-xs mt-2', trend.trend === 'improving' ? 'text-tm-profit' : trend.trend === 'declining' ? 'text-tm-obs' : 'text-muted-foreground')}>
              {trend.trend === 'improving' ? '↑ Win rate improving vs 30-day average' : trend.trend === 'declining' ? '↓ Win rate declining vs 30-day average' : '→ Win rate stable vs 30-day average'}
            </p>
          )}
        </div>
      )}

      {/* Watch-outs */}
      {watchOuts.length > 0 && (
        <div>
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-widest mb-2">Watch-Outs</p>
          <div className="space-y-2">
            {watchOuts.map((wo: any, i: number) => (
              <div key={i} className={cn(
                'flex gap-2 rounded-lg border p-2.5 text-sm',
                wo.severity === 'high' ? 'bg-red-50 dark:bg-red-900/10 border-red-200 dark:border-red-800' :
                  wo.severity === 'medium' ? 'bg-amber-50 dark:bg-amber-900/10 border-amber-200 dark:border-amber-800' :
                    'bg-muted/40 border-border'
              )}>
                <span className="text-base">{wo.icon}</span>
                <p className="text-foreground">{wo.message}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Checklist */}
      {checklist.length > 0 && (
        <div>
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-widest mb-2">Mental Checklist</p>
          <div className="space-y-1.5">
            {checklist.map((item: any, i: number) => (
              <div key={i} className="flex items-start gap-2 text-sm text-foreground">
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
            <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">{label}</p>
            <p className={cn('text-2xl font-bold font-mono tabular-nums', (stats.total_pnl ?? 0) >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
              {formatCurrency(stats.total_pnl ?? 0)}
            </p>
            <div className="flex gap-4 text-xs text-muted-foreground">
              <span>{stats.total_trades ?? 0} trades</span>
              <span>{stats.win_rate ?? 0}% win rate</span>
              <span>{stats.danger_alerts ?? 0} alerts</span>
            </div>
          </div>
        ))}
      </div>

      {Object.keys(imp).length > 0 && (
        <div>
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-widest mb-2">Week-over-Week</p>
          <div className="space-y-1.5">
            {imp.pnl && (
              <div className="flex items-center gap-2 text-sm">
                {imp.pnl.improved ? <TrendingUp className="h-4 w-4 text-tm-profit" /> : <TrendingDown className="h-4 w-4 text-tm-loss" />}
                <span className="text-foreground">P&L {imp.pnl.improved ? 'up' : 'down'} {formatCurrency(Math.abs(imp.pnl.change))} vs last week</span>
              </div>
            )}
            {imp.win_rate && (
              <div className="flex items-center gap-2 text-sm">
                {imp.win_rate.improved ? <TrendingUp className="h-4 w-4 text-tm-profit" /> : <TrendingDown className="h-4 w-4 text-tm-loss" />}
                <span className="text-foreground">Win rate {imp.win_rate.improved ? '+' : ''}{imp.win_rate.change}pp vs last week</span>
              </div>
            )}
            {imp.danger_alerts && (
              <div className="flex items-center gap-2 text-sm">
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
    <div className="tm-card overflow-hidden animate-fade-in-up">
      {/* Header row */}
      <button
        onClick={handleExpand}
        className="w-full px-5 py-4 flex items-start gap-4 text-left hover:bg-muted/30 transition-colors"
      >
        {/* Type badge */}
        <div className={cn('flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 shrink-0', meta.bg)}>
          <Icon className={cn('h-3.5 w-3.5', meta.color)} />
          <span className={cn('text-[11px] font-semibold', meta.color)}>{meta.label}</span>
        </div>

        {/* Date + time */}
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-foreground">{formatDate(report.report_date)}</p>
          <p className="text-xs text-muted-foreground mt-0.5">Generated {formatTime(report.generated_at)}{report.sent_via ? ' · sent via WhatsApp' : ''}</p>
        </div>

        {/* Preview metrics */}
        <div className="flex items-center gap-4 shrink-0 mr-2">
          {report.report_type === 'post_market' && report.total_pnl !== undefined && (
            <>
              <div className="text-right">
                <p className="text-[10px] text-muted-foreground">P&L</p>
                <p className={cn('text-base font-bold font-mono tabular-nums', report.total_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
                  {formatCurrency(report.total_pnl)}
                </p>
              </div>
              <div className="text-right">
                <p className="text-[10px] text-muted-foreground">Win Rate</p>
                <p className="text-base font-bold font-mono tabular-nums text-foreground">{report.win_rate ?? 0}%</p>
              </div>
            </>
          )}
          {report.report_type === 'morning_briefing' && report.readiness_score !== undefined && (
            <div className="text-right">
              <p className="text-[10px] text-muted-foreground">Readiness</p>
              <p className={cn(
                'text-base font-bold font-mono tabular-nums',
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
              <p className={cn('text-base font-bold font-mono tabular-nums', report.total_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
                {formatCurrency(report.total_pnl)}
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
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const offset = reports.length;

  const fetchReports = useCallback(async (type: ReportType, currentOffset: number, append = false) => {
    if (currentOffset === 0) setIsLoading(true); else setLoadingMore(true);
    try {
      const params: Record<string, any> = { limit: 20, offset: currentOffset };
      if (type !== 'all') params.report_type = type;
      const res = await api.get('/api/reports/saved', { params });
      if (append) {
        setReports(prev => [...prev, ...res.data.reports]);
      } else {
        setReports(res.data.reports);
      }
      setTotal(res.data.total);
    } catch {
      if (!append) setReports([]);
    } finally {
      setIsLoading(false);
      setLoadingMore(false);
    }
  }, []);

  useEffect(() => {
    fetchReports(filter, 0, false);
  }, [filter, fetchReports]);

  const handleLoadMore = () => {
    fetchReports(filter, offset, true);
  };

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
      <div className="max-w-3xl mx-auto pb-12">
        <div className="mb-5"><h1 className="t-heading-lg text-foreground">Reports</h1></div>
        <div className="tm-card flex flex-col items-center justify-center min-h-[50vh] text-center py-16">
          <div className="p-4 rounded-full bg-teal-50 dark:bg-teal-900/20 mb-5">
            <Link2 className="h-10 w-10 text-tm-brand" />
          </div>
          <h2 className="text-base font-semibold text-foreground mb-1">Connect Your Broker</h2>
          <p className="text-sm text-muted-foreground text-center max-w-sm mb-5">
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
    <div className="max-w-3xl mx-auto px-4 py-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="t-heading-lg text-foreground">Reports</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Morning briefs, EOD reports, and weekly summaries
          </p>
        </div>
        <button
          onClick={() => window.print()}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border text-sm text-muted-foreground hover:text-foreground hover:border-foreground transition-colors"
        >
          <Printer className="h-4 w-4" />
          Print
        </button>
      </div>

      {/* Filter tabs */}
      <div className="flex gap-2 flex-wrap">
        {FILTER_TABS.map(tab => (
          <button
            key={tab.value}
            onClick={() => setFilter(tab.value)}
            className={cn(
              'px-4 py-1.5 rounded-full text-xs font-medium transition-all border',
              filter === tab.value
                ? 'bg-foreground text-background border-foreground'
                : 'bg-transparent text-muted-foreground border-border hover:border-foreground hover:text-foreground'
            )}
          >
            {tab.label}
          </button>
        ))}
        {total > 0 && (
          <span className="ml-auto text-xs text-muted-foreground self-center">{total} report{total !== 1 ? 's' : ''}</span>
        )}
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="space-y-3">
          {[1,2,3].map(i => <Skeleton key={i} className="h-16 rounded-xl" />)}
        </div>
      ) : reports.length === 0 ? (
        <div className="flex flex-col items-center justify-center min-h-[30vh] rounded-xl border border-border bg-card">
          <FileText className="h-10 w-10 text-muted-foreground/40 mb-3" />
          <p className="font-medium text-foreground">No reports yet</p>
          <p className="text-sm text-muted-foreground mt-1">
            Reports are saved automatically when your daily briefs are sent
          </p>
        </div>
      ) : (
        <div className="space-y-6">
          {sortedDates.map(date => (
            <div key={date}>
              {/* Date separator */}
              <div className="flex items-center gap-3 mb-3">
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-widest whitespace-nowrap">
                  {formatDate(date)}
                </p>
                <div className="flex-1 h-px bg-border" />
              </div>
              <div className="space-y-2">
                {grouped[date].map(r => (
                  <ReportCard key={r.id} report={r} />
                ))}
              </div>
            </div>
          ))}

          {/* Load more */}
          {reports.length < total && (
            <div className="flex justify-center pt-2">
              <button
                onClick={handleLoadMore}
                disabled={loadingMore}
                className="flex items-center gap-2 px-5 py-2 rounded-full border border-border text-sm text-muted-foreground hover:text-foreground hover:border-foreground transition-colors disabled:opacity-50"
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
