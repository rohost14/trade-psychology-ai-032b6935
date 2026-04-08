import { useState, useEffect, useMemo } from 'react';
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine, Cell,
} from 'recharts';
import {
  TrendingUp, TrendingDown, Target, Clock, Trophy, Flame,
  Zap, CheckCircle2, AlertTriangle, Lightbulb, BarChart3,
  CalendarDays, ArrowUp, ArrowDown, Minus,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatCurrencyWithSign } from '@/lib/formatters';
import { api } from '@/lib/api';

// ─── Interfaces ───────────────────────────────────────────────────────────────

interface KPIs {
  total_pnl: number;
  total_trades?: number;
  trade_count?: number;
  winners: number;
  losers: number;
  win_rate: number;
  avg_win: number;
  avg_loss: number;
  profit_factor: number;
  expectancy: number;
  best_day: { date: string; pnl: number; trades?: number } | null;
  worst_day: { date: string; pnl: number; trades?: number } | null;
  max_win_streak: number;
  max_loss_streak: number;
  current_streak: number;
  current_streak_type: string | null;
  avg_duration_min?: number;
  win_days?: number;
  loss_days?: number;
  trading_days?: number;
  largest_win?: number;
  largest_loss?: number;
}

interface DailyPnl { date: string; pnl: number; trades?: number; win_rate?: number }
interface EquityPoint { date: string; cumulative_pnl: number; trade_count?: number }

interface OverviewData {
  has_data: boolean;
  kpis: KPIs | null;
  equity_curve: EquityPoint[];
  daily_pnl: DailyPnl[];
}

interface EdgeData {
  has_data: boolean;
  verdict: 'real_edge' | 'losing_edge' | 'inconclusive' | 'too_few';
  observed_win_rate: number;
  ci_lower: number;
  ci_upper: number;
  n: number;
  message: string;
}

interface SessionStat { hour: number; label: string; pnl: number; trades: number; win_rate: number }
interface InstrumentStat { symbol: string; pnl: number; trades: number; win_rate: number; avg_pnl?: number }
interface MonthlyPnl { month: string; pnl: number }

interface PerformanceData {
  has_data: boolean;
  by_session?: SessionStat[];
  by_instrument?: InstrumentStat[];
  monthly_pnl?: MonthlyPnl[];
}

interface WeekStats { total_pnl: number; trade_count: number; win_rate: number; winners: number; losers: number; avg_win?: number; avg_loss?: number }
interface ProgressData {
  this_week: WeekStats;
  last_week: WeekStats;
  comparison: { pnl: { improved: boolean; percent: number }; win_rate: { improved: boolean; percent: number }; trade_count: { improved: boolean; percent: number }; danger_alerts: { improved: boolean; percent: number } };
  alerts: { this_week: number; last_week: number };
  streaks: { days_without_revenge: number; current_streak: number; best_streak: number };
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

const PROFIT_COLOR = '#16A34A';
const LOSS_COLOR   = '#DC2626';
const OBS_COLOR    = '#D97706';
const BRAND_COLOR  = '#0D9488';

function fmtDate(d: string) {
  return new Date(d).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
}

function fmtDuration(min?: number) {
  if (!min) return '—';
  if (min < 60) return `${min}m`;
  const h = Math.floor(min / 60), m = min % 60;
  if (h < 24) return m > 0 ? `${h}h ${m}m` : `${h}h`;
  return `${Math.floor(h / 24)}d`;
}

function daysAgoLabel(dateStr: string) {
  const diff = Math.floor((Date.now() - new Date(dateStr).getTime()) / 86400000);
  if (diff === 0) return 'today';
  if (diff === 1) return 'yesterday';
  return `${diff}d ago`;
}

// ─── Edge Strip ───────────────────────────────────────────────────────────────

function EdgeStrip({ days }: { days: number }) {
  const [data, setData] = useState<EdgeData | null>(null);
  useEffect(() => {
    let c = false;
    api.get('/api/analytics/edge-confidence', { params: { days } })
      .then(r => { if (!c) setData(r.data); })
      .catch(() => {});
    return () => { c = true; };
  }, [days]);

  if (!data?.has_data) return null;

  const cfg = {
    real_edge:   { color: 'text-tm-profit', bg: 'bg-teal-50 dark:bg-teal-900/20', border: 'border-teal-200 dark:border-teal-800/40', label: 'Real Edge', dot: 'bg-tm-profit' },
    losing_edge: { color: 'text-tm-loss',   bg: 'bg-red-50 dark:bg-red-900/20',   border: 'border-red-200 dark:border-red-800/40',   label: 'Losing Edge', dot: 'bg-tm-loss' },
    inconclusive:{ color: 'text-tm-obs',    bg: 'bg-amber-50 dark:bg-amber-900/20',border: 'border-amber-200 dark:border-amber-800/40',label: 'Inconclusive', dot: 'bg-tm-obs' },
    too_few:     { color: 'text-muted-foreground', bg: 'bg-slate-50 dark:bg-neutral-700/30', border: 'border-slate-200 dark:border-neutral-700/60', label: 'Need More Data', dot: 'bg-slate-400' },
  }[data.verdict] ?? { color: 'text-tm-obs', bg: 'bg-amber-50 dark:bg-amber-900/20', border: 'border-amber-200 dark:border-amber-800/40', label: 'Inconclusive', dot: 'bg-tm-obs' };

  return (
    <div className={cn('tm-card flex items-center gap-4 px-5 py-3', cfg.bg, cfg.border)}>
      <div className="flex items-center gap-2 shrink-0">
        <span className={cn('w-2 h-2 rounded-full', cfg.dot)} />
        <span className="tm-label">Edge Confidence</span>
        <span className={cn('text-[11px] font-bold uppercase tracking-wide', cfg.color)}>{cfg.label}</span>
      </div>
      <p className="text-[12px] text-muted-foreground leading-snug flex-1 min-w-0 truncate">{data.message}</p>
      <div className="shrink-0 flex items-center gap-3 text-[11px] text-muted-foreground font-mono tabular-nums">
        <span>CI {data.ci_lower}–{data.ci_upper}%</span>
        <span className={cn('font-semibold', cfg.color)}>obs {data.observed_win_rate}%</span>
        <span>{data.n} trades</span>
      </div>
    </div>
  );
}

// ─── KPI Card ────────────────────────────────────────────────────────────────

function KPICard({ label, value, valueCls, sub, subCls, icon: Icon }: {
  label: string; value: string; valueCls?: string; sub?: string; subCls?: string;
  icon?: React.ComponentType<{ className?: string }>;
}) {
  return (
    <div className="tm-card px-4 py-3.5">
      <div className="flex items-center gap-1.5 mb-2">
        {Icon && <Icon className="h-3 w-3 text-muted-foreground/70" />}
        <span className="tm-label">{label}</span>
      </div>
      <p className={cn('text-2xl font-semibold font-mono tabular-nums leading-none', valueCls ?? 'text-foreground')}>{value}</p>
      {sub && <p className={cn('text-[11px] mt-1', subCls ?? 'text-muted-foreground')}>{sub}</p>}
    </div>
  );
}

// ─── Tooltips ────────────────────────────────────────────────────────────────

function ChartTooltip({ active, payload, type }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  const val = type === 'equity' ? d.cumulative_pnl : d.pnl;
  return (
    <div className="tm-card px-3 py-2.5 shadow-lg text-sm min-w-[120px]">
      <p className="font-medium text-foreground mb-1">{fmtDate(d.date)}</p>
      <p className={cn('font-mono tabular-nums font-semibold', val >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
        {formatCurrencyWithSign(val)}
      </p>
      {d.trade_count != null && <p className="text-[11px] text-muted-foreground mt-0.5">{d.trade_count} trades</p>}
      {d.trades != null && d.win_rate != null && (
        <p className="text-[11px] text-muted-foreground mt-0.5">{d.trades} trades · {d.win_rate}% WR</p>
      )}
    </div>
  );
}

// ─── Week Comparison Cell ─────────────────────────────────────────────────────

function WkCell({ label, a, b, format, lessIsBetter = false }: {
  label: string; a: number; b: number;
  format: (v: number) => string;
  lessIsBetter?: boolean;
}) {
  const diff = a - b;
  const improved = lessIsBetter ? diff < 0 : diff > 0;
  const pct = b !== 0 ? Math.abs(Math.round((diff / Math.abs(b)) * 100)) : 0;
  const ArrowIcon = diff === 0 ? Minus : improved ? ArrowUp : ArrowDown;
  const arrowCls = diff === 0 ? 'text-muted-foreground/50' : improved ? 'text-tm-profit' : 'text-tm-loss';
  return (
    <div className="text-center">
      <p className="tm-label mb-2">{label}</p>
      <div className="flex items-end justify-center gap-2">
        <p className={cn('text-xl font-semibold font-mono tabular-nums', a >= 0 && !lessIsBetter ? (a > b ? 'text-tm-profit' : 'text-foreground') : a < 0 ? 'text-tm-loss' : 'text-foreground')}>
          {format(a)}
        </p>
        {diff !== 0 && (
          <div className={cn('flex items-center gap-0.5 text-[11px] font-mono pb-0.5', arrowCls)}>
            <ArrowIcon className="w-3 h-3" />
            <span>{pct}%</span>
          </div>
        )}
      </div>
      <p className="text-[11px] text-muted-foreground mt-0.5 font-mono tabular-nums">{format(b)} prior</p>
    </div>
  );
}

// ─── Outlier Detection ───────────────────────────────────────────────────────

interface OutlierFlag { type: 'positive' | 'warning' | 'critical'; msg: string }

function computeOutliers(
  kpis: KPIs | null,
  perf: PerformanceData | null,
  prog: ProgressData | null,
  days: number,
): OutlierFlag[] {
  const flags: OutlierFlag[] = [];
  if (!kpis) return flags;

  const tradeCount = kpis.total_trades ?? kpis.trade_count ?? 0;

  // 1. Win rate this week vs period average
  if (prog) {
    const { this_week, last_week } = prog;
    const periodWR = kpis.win_rate;
    if (this_week.win_rate < periodWR * 0.7 && this_week.trade_count >= 3) {
      flags.push({ type: 'warning', msg: `Win rate this week (${this_week.win_rate}%) is well below your ${days}d average (${periodWR}%)` });
    } else if (this_week.win_rate > periodWR * 1.3 && this_week.trade_count >= 3) {
      flags.push({ type: 'positive', msg: `Win rate this week (${this_week.win_rate}%) is above your ${days}d average (${periodWR}%) — performing well` });
    }

    // 2. Trade count spike
    if (this_week.trade_count > last_week.trade_count * 1.6 && last_week.trade_count > 0) {
      flags.push({ type: 'warning', msg: `${this_week.trade_count} trades this week vs ${last_week.trade_count} last week — higher volume than usual` });
    }

    // 3. Alert spike
    if (prog.alerts.this_week > prog.alerts.last_week * 2 && prog.alerts.this_week >= 2) {
      flags.push({ type: 'warning', msg: `${prog.alerts.this_week} behavioral alerts this week vs ${prog.alerts.last_week} last week — pattern activity up` });
    }

    // 4. Revenge-free streak highlight
    if (prog.streaks.days_without_revenge >= 5) {
      flags.push({ type: 'positive', msg: `${prog.streaks.days_without_revenge} days without a revenge trade — personal best streak territory` });
    }
  }

  // 5. Worst day recency
  if (kpis.worst_day) {
    const diff = Math.floor((Date.now() - new Date(kpis.worst_day.date).getTime()) / 86400000);
    if (diff <= 2) {
      flags.push({ type: 'critical', msg: `Your worst day this period (${formatCurrencyWithSign(kpis.worst_day.pnl)}) was ${diff === 0 ? 'today' : diff === 1 ? 'yesterday' : '2 days ago'}` });
    }
  }

  // 6. Current losing streak
  if (kpis.current_streak >= 3 && kpis.current_streak_type === 'loss') {
    flags.push({ type: 'critical', msg: `Currently on a ${kpis.current_streak}-trade losing streak — consider pausing and reviewing` });
  } else if (kpis.current_streak >= 2 && kpis.current_streak_type === 'loss') {
    flags.push({ type: 'warning', msg: `${kpis.current_streak} consecutive losses — stay disciplined before the next trade` });
  }

  // 7. Dead hour from performance data
  if (perf?.by_session) {
    const deadHours = perf.by_session.filter(s => s.trades >= 2 && s.win_rate === 0 && s.pnl < 0);
    if (deadHours.length > 0) {
      const worst = deadHours.sort((a, b) => a.pnl - b.pnl)[0];
      flags.push({ type: 'warning', msg: `${worst.label} IST: 0% win rate across ${worst.trades} trades — consider avoiding this hour` });
    }
    const bestHours = perf.by_session.filter(s => s.trades >= 2 && s.win_rate >= 75);
    if (bestHours.length > 0) {
      const best = bestHours.sort((a, b) => b.win_rate - a.win_rate)[0];
      flags.push({ type: 'positive', msg: `${best.label} IST: ${best.win_rate}% win rate — your strongest trading hour` });
    }
  }

  // 8. Avg win vs avg loss ratio
  if (kpis.avg_win && kpis.avg_loss && kpis.avg_loss < 0) {
    const ratio = kpis.avg_win / Math.abs(kpis.avg_loss);
    if (ratio < 0.6) {
      flags.push({ type: 'warning', msg: `Avg win (${formatCurrencyWithSign(kpis.avg_win)}) is ${(ratio * 100).toFixed(0)}% of avg loss (${formatCurrencyWithSign(kpis.avg_loss)}) — winners too small relative to losers` });
    } else if (ratio >= 1.5) {
      flags.push({ type: 'positive', msg: `Avg win (${formatCurrencyWithSign(kpis.avg_win)}) is ${ratio.toFixed(1)}× your avg loss — strong risk/reward discipline` });
    }
  }

  return flags.slice(0, 5); // max 5 to keep the section clean
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function SummaryTab({ days }: { days: number }) {
  const [overview, setOverview]   = useState<OverviewData | null>(null);
  const [perf, setPerf]           = useState<PerformanceData | null>(null);
  const [progress, setProgress]   = useState<ProgressData | null>(null);
  const [loading, setLoading]     = useState(true);

  useEffect(() => {
    let c = false;
    setLoading(true);
    Promise.allSettled([
      api.get('/api/analytics/overview',     { params: { days } }),
      api.get('/api/analytics/performance',  { params: { days } }),
      api.get('/api/analytics/progress'),
    ]).then(([r1, r2, r3]) => {
      if (c) return;
      if (r1.status === 'fulfilled') setOverview(r1.value.data);
      if (r2.status === 'fulfilled') setPerf(r2.value.data);
      if (r3.status === 'fulfilled') setProgress(r3.value.data);
      setLoading(false);
    });
    return () => { c = true; };
  }, [days]);

  if (loading) {
    return (
      <div className="space-y-4 animate-pulse">
        <div className="h-12 tm-card" />
        <div className="grid grid-cols-4 gap-4">{[1,2,3,4].map(i => <div key={i} className="h-24 tm-card" />)}</div>
        <div className="grid grid-cols-12 gap-4">
          <div className="col-span-8 h-64 tm-card" />
          <div className="col-span-4 h-64 tm-card" />
        </div>
        <div className="grid grid-cols-4 gap-4">{[1,2,3,4].map(i => <div key={i} className="h-20 tm-card" />)}</div>
      </div>
    );
  }

  if (!overview?.has_data || !overview.kpis) {
    return (
      <div className="tm-card px-6 py-10">
        <div className="flex flex-col items-center mb-8">
          <BarChart3 className="h-6 w-6 text-muted-foreground/40 mb-3" />
          <p className="font-semibold text-foreground">No trading data for this period</p>
          <p className="text-[13px] text-muted-foreground mt-1">Complete some trades to see analytics</p>
        </div>
        <div className="grid grid-cols-2 gap-3 max-w-sm mx-auto">
          {[
            { stat: '89%', label: 'of F&O traders lose money', source: 'SEBI FY2023' },
            { stat: '5×',  label: 'avg loss vs gain for retail intraday traders', source: 'SEBI data' },
            { stat: '40%', label: 'of losses come from revenge trades after a bad day', source: 'Behavioral research' },
            { stat: '2 min', label: 'median time before an emotional re-entry after a stop-loss', source: 'SEBI FY2022' },
          ].map((item, i) => (
            <div key={i} className="p-3 rounded-lg bg-slate-50 dark:bg-neutral-700/30 border border-slate-100 dark:border-neutral-700/60">
              <p className="text-base font-bold text-tm-brand">{item.stat}</p>
              <p className="text-xs text-foreground mt-0.5 leading-snug">{item.label}</p>
              <p className="text-[10px] text-muted-foreground mt-1">{item.source}</p>
            </div>
          ))}
        </div>
      </div>
    );
  }

  const { kpis, equity_curve, daily_pnl } = overview;
  const isProfit  = kpis.total_pnl >= 0;
  const tradeCount = kpis.total_trades ?? kpis.trade_count ?? 0;

  // Most active hour and best hour from performance data
  const bySession = perf?.by_session ?? [];
  const mostActiveHour = bySession.length > 0
    ? bySession.reduce((a, b) => b.trades > a.trades ? b : a, bySession[0])
    : null;
  const bestHour = bySession.filter(s => s.trades >= 2).length > 0
    ? bySession.filter(s => s.trades >= 2).reduce((a, b) => b.win_rate > a.win_rate ? b : a, bySession.filter(s => s.trades >= 2)[0])
    : null;

  const avgTradesPerDay = kpis.trading_days && kpis.trading_days > 0
    ? (tradeCount / kpis.trading_days).toFixed(1)
    : tradeCount > 0 && daily_pnl.length > 0
      ? (tradeCount / daily_pnl.length).toFixed(1)
      : '—';

  const outliers = computeOutliers(kpis, perf, progress, days);

  const pfColor = kpis.profit_factor >= 1.5 ? 'text-tm-profit' : kpis.profit_factor >= 1 ? 'text-foreground' : 'text-tm-loss';
  const pfSub   = kpis.profit_factor >= 1.5 ? 'Good edge' : kpis.profit_factor >= 1 ? 'Breakeven zone' : 'Losing edge';

  return (
    <div className="space-y-4">

      {/* ── Edge Confidence Strip ──────────────────────────────────────── */}
      <EdgeStrip days={days} />

      {/* ── Hero KPIs ─────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KPICard
          label="Total P&L"
          value={formatCurrencyWithSign(kpis.total_pnl)}
          valueCls={isProfit ? 'text-tm-profit' : 'text-tm-loss'}
          icon={isProfit ? TrendingUp : TrendingDown}
          sub={`${tradeCount} trades`}
        />
        <KPICard
          label="Win Rate"
          value={`${kpis.win_rate}%`}
          valueCls={kpis.win_rate >= 50 ? 'text-tm-profit' : 'text-tm-loss'}
          sub={`${kpis.winners}W / ${kpis.losers}L`}
          icon={Target}
        />
        <KPICard
          label="Profit Factor"
          value={kpis.profit_factor > 0 ? kpis.profit_factor.toFixed(2) : '—'}
          valueCls={pfColor}
          sub={pfSub}
          icon={BarChart3}
        />
        <KPICard
          label="Expectancy"
          value={formatCurrencyWithSign(kpis.expectancy)}
          valueCls={kpis.expectancy >= 0 ? 'text-tm-profit' : 'text-tm-loss'}
          sub="Avg P&L per trade"
          icon={Zap}
        />
      </div>

      {/* ── Equity Curve + Sidebar ────────────────────────────────────── */}
      <div className="grid grid-cols-12 gap-4">

        {/* Equity Curve */}
        {equity_curve.length > 1 && (
          <div className="col-span-12 md:col-span-8 tm-card">
            <div className="flex items-center justify-between px-5 py-3 border-b border-slate-100 dark:border-neutral-700/60">
              <span className="tm-label">Equity Curve</span>
              <span className={cn('text-sm font-semibold font-mono tabular-nums', isProfit ? 'text-tm-profit' : 'text-tm-loss')}>
                {formatCurrencyWithSign(kpis.total_pnl)}
              </span>
            </div>
            <div className="px-4 pt-3 pb-4 h-[260px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={equity_curve}>
                  <defs>
                    <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={isProfit ? PROFIT_COLOR : LOSS_COLOR} stopOpacity={0.18} />
                      <stop offset="100%" stopColor={isProfit ? PROFIT_COLOR : LOSS_COLOR} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" strokeOpacity={0.4} vertical={false} />
                  <XAxis dataKey="date" tickFormatter={fmtDate} axisLine={false} tickLine={false}
                    tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }} interval="preserveStartEnd" />
                  <YAxis axisLine={false} tickLine={false}
                    tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }}
                    tickFormatter={v => `₹${(v / 1000).toFixed(0)}k`} />
                  <Tooltip content={<ChartTooltip type="equity" />} />
                  <ReferenceLine y={0} stroke="hsl(var(--border))" strokeWidth={1.5} />
                  <Area type="monotone" dataKey="cumulative_pnl"
                    stroke={isProfit ? PROFIT_COLOR : LOSS_COLOR} strokeWidth={2}
                    fill="url(#eqGrad)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {/* Sidebar: Best/Worst + Streaks */}
        <div className="col-span-12 md:col-span-4 tm-card px-5 py-4 flex flex-col gap-4">
          {/* Best Day */}
          <div>
            <div className="flex items-center gap-1.5 mb-2">
              <Trophy className="h-3.5 w-3.5 text-tm-profit" />
              <span className="tm-label">Best Day</span>
            </div>
            {kpis.best_day ? (
              <>
                <p className="text-2xl font-semibold font-mono tabular-nums text-tm-profit">
                  {formatCurrencyWithSign(kpis.best_day.pnl)}
                </p>
                <p className="text-[11px] text-muted-foreground mt-1 font-mono">
                  {fmtDate(kpis.best_day.date)} · {daysAgoLabel(kpis.best_day.date)}
                  {kpis.best_day.trades ? ` · ${kpis.best_day.trades} trades` : ''}
                </p>
              </>
            ) : <p className="text-2xl font-mono text-muted-foreground">—</p>}
          </div>

          <div className="border-t border-slate-100 dark:border-neutral-700/60" />

          {/* Worst Day */}
          <div>
            <div className="flex items-center gap-1.5 mb-2">
              <Flame className="h-3.5 w-3.5 text-tm-loss" />
              <span className="tm-label">Worst Day</span>
            </div>
            {kpis.worst_day ? (
              <>
                <p className="text-2xl font-semibold font-mono tabular-nums text-tm-loss">
                  {formatCurrencyWithSign(kpis.worst_day.pnl)}
                </p>
                <p className="text-[11px] text-muted-foreground mt-1 font-mono">
                  {fmtDate(kpis.worst_day.date)} · {daysAgoLabel(kpis.worst_day.date)}
                  {kpis.worst_day.trades ? ` · ${kpis.worst_day.trades} trades` : ''}
                </p>
              </>
            ) : <p className="text-2xl font-mono text-muted-foreground">—</p>}
          </div>

          <div className="border-t border-slate-100 dark:border-neutral-700/60" />

          {/* Streaks */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <span className="tm-label">Best Win Streak</span>
              <p className="text-xl font-semibold font-mono tabular-nums text-tm-profit mt-1">{kpis.max_win_streak}</p>
            </div>
            <div>
              <span className="tm-label">Worst Loss Streak</span>
              <p className="text-xl font-semibold font-mono tabular-nums text-tm-loss mt-1">{kpis.max_loss_streak}</p>
            </div>
          </div>

          {kpis.current_streak > 0 && kpis.current_streak_type && (
            <div className={cn(
              'rounded-lg px-3 py-2.5 text-center',
              kpis.current_streak_type === 'win' ? 'bg-teal-50 dark:bg-teal-900/20' : 'bg-red-50 dark:bg-red-900/20',
            )}>
              <span className="tm-label block mb-1">Current Streak</span>
              <p className={cn(
                'text-xl font-bold font-mono tabular-nums',
                kpis.current_streak_type === 'win' ? 'text-tm-profit' : 'text-tm-loss',
              )}>
                {kpis.current_streak} {kpis.current_streak_type === 'win' ? 'W' : 'L'}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* ── Performance Snapshot ──────────────────────────────────────── */}
      <div className="tm-card">
        <div className="flex items-center justify-between px-5 py-3 border-b border-slate-100 dark:border-neutral-700/60">
          <span className="tm-label">Performance Snapshot</span>
          <span className="text-[12px] text-muted-foreground">Last {days} days</span>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 divide-x divide-y divide-slate-100 dark:divide-slate-700/60">
          {[
            { label: 'Avg Win', value: formatCurrencyWithSign(kpis.avg_win), cls: 'text-tm-profit', sub: kpis.largest_win ? `Best: ${formatCurrencyWithSign(kpis.largest_win)}` : `${kpis.winners} winners` },
            { label: 'Avg Loss', value: formatCurrencyWithSign(kpis.avg_loss), cls: 'text-tm-loss', sub: kpis.largest_loss ? `Worst: ${formatCurrencyWithSign(kpis.largest_loss)}` : `${kpis.losers} losers` },
            { label: 'Avg Hold Time', value: fmtDuration(kpis.avg_duration_min), cls: 'text-foreground', sub: 'Per trade', icon: Clock },
            { label: 'Total Trades', value: String(tradeCount), cls: 'text-foreground', sub: `${kpis.winners}W · ${kpis.losers}L` },
            { label: 'Total P&L (W)', value: formatCurrencyWithSign(kpis.avg_win * kpis.winners), cls: 'text-tm-profit', sub: 'From winners' },
            { label: 'Total P&L (L)', value: formatCurrencyWithSign(kpis.avg_loss * kpis.losers), cls: 'text-tm-loss', sub: 'From losers' },
            { label: 'Win Days', value: String(kpis.win_days ?? '—'), cls: 'text-tm-profit', sub: kpis.trading_days ? `of ${kpis.trading_days} trading days` : undefined },
            { label: 'Loss Days', value: String(kpis.loss_days ?? '—'), cls: 'text-tm-loss', sub: kpis.trading_days ? `of ${kpis.trading_days} trading days` : undefined },
          ].map(({ label, value, cls, sub, icon: Icon }: any) => (
            <div key={label} className="px-5 py-3.5">
              <div className="flex items-center gap-1.5 mb-1.5">
                {Icon && <Icon className="h-3 w-3 text-muted-foreground/70" />}
                <span className="tm-label">{label}</span>
              </div>
              <p className={cn('text-xl font-semibold font-mono tabular-nums', cls)}>{value}</p>
              {sub && <p className="text-[11px] text-muted-foreground mt-0.5">{sub}</p>}
            </div>
          ))}
        </div>
      </div>

      {/* ── Week-over-Week Comparison ─────────────────────────────────── */}
      {progress && (
        <div className="tm-card">
          <div className="flex items-center justify-between px-5 py-3 border-b border-slate-100 dark:border-neutral-700/60">
            <span className="tm-label">Week over Week</span>
            <div className="flex items-center gap-3 text-[11px]">
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-tm-brand" />This week</span>
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-slate-300 dark:bg-neutral-600" />Last week</span>
            </div>
          </div>

          {/* This week vs Last week side by side */}
          <div className="grid grid-cols-2 divide-x divide-slate-100 dark:divide-slate-700/60">
            {[
              { label: 'This Week', data: progress.this_week, alerts: progress.alerts.this_week, highlight: true },
              { label: 'Last Week', data: progress.last_week, alerts: progress.alerts.last_week, highlight: false },
            ].map(({ label, data, alerts, highlight }) => (
              <div key={label} className="px-5 py-4">
                <p className={cn('text-[11px] font-semibold mb-3', highlight ? 'text-tm-brand' : 'text-muted-foreground')}>{label}</p>
                <div className="space-y-2.5">
                  <div className="flex items-center justify-between">
                    <span className="text-[12px] text-muted-foreground">P&L</span>
                    <span className={cn('text-sm font-semibold font-mono tabular-nums', data.total_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
                      {formatCurrencyWithSign(data.total_pnl)}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-[12px] text-muted-foreground">Trades</span>
                    <span className="text-sm font-semibold font-mono tabular-nums text-foreground">{data.trade_count}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-[12px] text-muted-foreground">Win Rate</span>
                    <span className={cn('text-sm font-semibold font-mono tabular-nums', data.win_rate >= 50 ? 'text-tm-profit' : 'text-tm-loss')}>
                      {data.win_rate}%
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-[12px] text-muted-foreground">W / L</span>
                    <span className="text-sm font-mono tabular-nums text-foreground">
                      <span className="text-tm-profit">{data.winners}W</span>
                      <span className="text-muted-foreground/40 mx-1">·</span>
                      <span className="text-tm-loss">{data.losers}L</span>
                    </span>
                  </div>
                  {data.avg_win != null && (
                    <div className="flex items-center justify-between">
                      <span className="text-[12px] text-muted-foreground">Avg Win</span>
                      <span className="text-sm font-semibold font-mono tabular-nums text-tm-profit">{formatCurrencyWithSign(data.avg_win)}</span>
                    </div>
                  )}
                  {data.avg_loss != null && (
                    <div className="flex items-center justify-between">
                      <span className="text-[12px] text-muted-foreground">Avg Loss</span>
                      <span className="text-sm font-semibold font-mono tabular-nums text-tm-loss">{formatCurrencyWithSign(data.avg_loss)}</span>
                    </div>
                  )}
                  <div className="flex items-center justify-between">
                    <span className="text-[12px] text-muted-foreground">Alerts</span>
                    <span className={cn('text-sm font-semibold font-mono tabular-nums', alerts > 0 ? 'text-tm-obs' : 'text-tm-profit')}>
                      {alerts > 0 ? alerts : '—'}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Delta row */}
          <div className="border-t border-slate-100 dark:border-neutral-700/60 px-5 py-3 grid grid-cols-4 gap-4">
            {[
              { label: 'P&L Δ', a: progress.this_week.total_pnl, b: progress.last_week.total_pnl, fmt: (v: number) => formatCurrencyWithSign(v), lessIsBetter: false },
              { label: 'Win Rate Δ', a: progress.this_week.win_rate, b: progress.last_week.win_rate, fmt: (v: number) => `${v > 0 ? '+' : ''}${v.toFixed(0)}pp`, lessIsBetter: false },
              { label: 'Trades Δ', a: progress.this_week.trade_count, b: progress.last_week.trade_count, fmt: (v: number) => `${v > 0 ? '+' : ''}${v}`, lessIsBetter: true },
              { label: 'Alerts Δ', a: progress.alerts.this_week, b: progress.alerts.last_week, fmt: (v: number) => `${v > 0 ? '+' : ''}${v}`, lessIsBetter: true },
            ].map(({ label, a, b, fmt, lessIsBetter }) => {
              const delta = a - b;
              const improved = lessIsBetter ? delta <= 0 : delta >= 0;
              const cls = delta === 0 ? 'text-muted-foreground' : improved ? 'text-tm-profit' : 'text-tm-loss';
              return (
                <div key={label} className="text-center">
                  <span className="tm-label block mb-1">{label}</span>
                  <span className={cn('text-sm font-semibold font-mono tabular-nums', cls)}>{fmt(delta)}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── Trading Habits ────────────────────────────────────────────── */}
      <div className="tm-card">
        <div className="flex items-center justify-between px-5 py-3 border-b border-slate-100 dark:border-neutral-700/60">
          <span className="tm-label">Trading Habits</span>
          <span className="text-[12px] text-muted-foreground">Patterns in how you trade</span>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 divide-x divide-slate-100 dark:divide-slate-700/60">
          <div className="px-5 py-4">
            <div className="flex items-center gap-1.5 mb-1.5">
              <Clock className="h-3 w-3 text-muted-foreground/70" />
              <span className="tm-label">Most Active Hour</span>
            </div>
            <p className="text-xl font-semibold font-mono tabular-nums text-foreground">
              {mostActiveHour ? mostActiveHour.label : '—'}
            </p>
            <p className="text-[11px] text-muted-foreground mt-0.5">
              {mostActiveHour ? `${mostActiveHour.trades} trades · ${mostActiveHour.win_rate}% WR` : 'No data'}
            </p>
          </div>
          <div className="px-5 py-4">
            <div className="flex items-center gap-1.5 mb-1.5">
              <Trophy className="h-3 w-3 text-muted-foreground/70" />
              <span className="tm-label">Best Hour</span>
            </div>
            <p className={cn('text-xl font-semibold font-mono tabular-nums', bestHour ? 'text-tm-profit' : 'text-foreground')}>
              {bestHour ? bestHour.label : '—'}
            </p>
            <p className="text-[11px] text-muted-foreground mt-0.5">
              {bestHour ? `${bestHour.win_rate}% WR · ${formatCurrencyWithSign(bestHour.pnl)}` : 'Need ≥2 trades/hour'}
            </p>
          </div>
          <div className="px-5 py-4">
            <div className="flex items-center gap-1.5 mb-1.5">
              <BarChart3 className="h-3 w-3 text-muted-foreground/70" />
              <span className="tm-label">Avg Trades / Day</span>
            </div>
            <p className="text-xl font-semibold font-mono tabular-nums text-foreground">{avgTradesPerDay}</p>
            <p className="text-[11px] text-muted-foreground mt-0.5">
              {kpis.trading_days ? `Over ${kpis.trading_days} active days` : `${tradeCount} total trades`}
            </p>
          </div>
          <div className="px-5 py-4">
            <div className="flex items-center gap-1.5 mb-1.5">
              <CalendarDays className="h-3 w-3 text-muted-foreground/70" />
              <span className="tm-label">Revenge-Free Streak</span>
            </div>
            <p className={cn('text-xl font-semibold font-mono tabular-nums', (progress?.streaks.days_without_revenge ?? 0) >= 3 ? 'text-tm-profit' : 'text-foreground')}>
              {progress?.streaks.days_without_revenge ?? '—'}
              {progress?.streaks.days_without_revenge != null && <span className="text-sm font-normal text-muted-foreground ml-1">days</span>}
            </p>
            <p className="text-[11px] text-muted-foreground mt-0.5">
              {progress?.streaks.best_streak ? `Best: ${progress.streaks.best_streak} days` : 'No revenge trades logged'}
            </p>
          </div>
        </div>

        {/* By-hour mini bar chart */}
        {bySession.length > 0 && (
          <div className="px-5 pb-4 pt-2 border-t border-slate-100 dark:border-neutral-700/60">
            <p className="tm-label mb-3">P&L by Hour (IST)</p>
            <div className="h-[100px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={bySession} barSize={24}>
                  <XAxis dataKey="label" axisLine={false} tickLine={false}
                    tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }} />
                  <YAxis hide tickFormatter={v => `${(v / 1000).toFixed(0)}k`} />
                  <Tooltip content={({ active, payload }) => {
                    if (!active || !payload?.length) return null;
                    const d = payload[0].payload as SessionStat;
                    return (
                      <div className="tm-card px-3 py-2 shadow-lg text-xs">
                        <p className="font-medium text-foreground">{d.label} IST</p>
                        <p className={cn('font-mono tabular-nums', d.pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>{formatCurrencyWithSign(d.pnl)}</p>
                        <p className="text-muted-foreground">{d.trades} trades · {d.win_rate}% WR</p>
                      </div>
                    );
                  }} />
                  <ReferenceLine y={0} stroke="hsl(var(--border))" strokeWidth={1} />
                  <Bar dataKey="pnl" radius={[2, 2, 0, 0]}>
                    {bySession.map((s, i) => (
                      <Cell key={i} fill={s.pnl >= 0 ? PROFIT_COLOR : LOSS_COLOR} fillOpacity={s.trades === 0 ? 0.3 : 0.85} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}
      </div>

      {/* ── Outlier Detection ─────────────────────────────────────────── */}
      {outliers.length > 0 && (
        <div className="tm-card">
          <div className="flex items-center gap-2 px-5 py-3 border-b border-slate-100 dark:border-neutral-700/60">
            <Lightbulb className="h-3.5 w-3.5 text-tm-brand" />
            <span className="tm-label">What's Different From Usual</span>
            <span className="text-[11px] text-muted-foreground ml-1">Deviations flagged from your {days}d baseline</span>
          </div>
          <div className="divide-y divide-slate-50 dark:divide-slate-700/30">
            {outliers.map((flag, i) => {
              const dotCls = flag.type === 'positive' ? 'bg-tm-profit' : flag.type === 'critical' ? 'bg-tm-loss' : 'bg-tm-obs';
              const textCls = flag.type === 'positive' ? 'text-tm-profit' : flag.type === 'critical' ? 'text-tm-loss' : 'text-tm-obs';
              const Icon = flag.type === 'positive' ? CheckCircle2 : flag.type === 'critical' ? AlertTriangle : Lightbulb;
              return (
                <div key={i} className="flex items-start gap-3 px-5 py-3">
                  <Icon className={cn('h-3.5 w-3.5 mt-0.5 shrink-0', textCls)} />
                  <p className="text-[13px] text-foreground leading-snug">{flag.msg}</p>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── Daily P&L Bars ────────────────────────────────────────────── */}
      {daily_pnl.length > 0 && (
        <div className="tm-card">
          <div className="flex items-center justify-between px-5 py-3 border-b border-slate-100 dark:border-neutral-700/60">
            <span className="tm-label">Daily P&L</span>
            <div className="flex items-center gap-3 text-[11px] text-muted-foreground">
              <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-tm-profit" />{kpis.win_days ?? '—'} green days</span>
              <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-tm-loss" />{kpis.loss_days ?? '—'} red days</span>
            </div>
          </div>
          <div className="px-4 pt-3 pb-4 h-[200px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={daily_pnl}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" strokeOpacity={0.4} vertical={false} />
                <XAxis dataKey="date" tickFormatter={fmtDate} axisLine={false} tickLine={false}
                  tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }} interval="preserveStartEnd" />
                <YAxis axisLine={false} tickLine={false}
                  tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }}
                  tickFormatter={v => `₹${(v / 1000).toFixed(0)}k`} />
                <Tooltip content={<ChartTooltip type="daily" />} />
                <ReferenceLine y={0} stroke="hsl(var(--border))" strokeWidth={1.5} />
                <Bar dataKey="pnl" radius={[2, 2, 0, 0]}>
                  {daily_pnl.map((d, i) => (
                    <Cell key={i} fill={d.pnl >= 0 ? PROFIT_COLOR : LOSS_COLOR} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* ── Top Instruments ───────────────────────────────────────────── */}
      {perf?.by_instrument && perf.by_instrument.length > 0 && (
        <div className="tm-card">
          <div className="px-5 py-3 border-b border-slate-100 dark:border-neutral-700/60">
            <span className="tm-label">Top Instruments</span>
          </div>
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-100 dark:border-neutral-700/60">
                {['Symbol', 'Trades', 'Win Rate', 'P&L'].map((h, i) => (
                  <th key={i} className={cn('py-2.5 table-header', i === 0 ? 'px-5 text-left' : 'px-4 text-right')}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {perf.by_instrument.slice(0, 6).map((ins, i) => (
                <tr key={ins.symbol} className={cn(
                  'transition-colors hover:bg-slate-50 dark:hover:bg-slate-700/30',
                  i < Math.min(perf.by_instrument!.length, 6) - 1 && 'border-b border-slate-50 dark:border-neutral-700/30',
                )}>
                  <td className="px-5 py-2.5 text-sm font-semibold text-foreground">{ins.symbol}</td>
                  <td className="px-4 py-2.5 text-right text-sm font-mono tabular-nums text-muted-foreground">{ins.trades}</td>
                  <td className="px-4 py-2.5 text-right">
                    <span className={cn('text-sm font-mono tabular-nums font-semibold', ins.win_rate >= 50 ? 'text-tm-profit' : 'text-tm-loss')}>
                      {ins.win_rate}%
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    <span className={cn('text-sm font-mono tabular-nums font-semibold', ins.pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
                      {formatCurrencyWithSign(ins.pnl)}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

    </div>
  );
}
