import { useState, useEffect } from 'react';
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine, Cell,
} from 'recharts';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Loader2, TrendingUp, TrendingDown, Target, BarChart3,
  Flame, Trophy, Clock, Zap, CheckCircle2,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatCurrency } from '@/lib/formatters';
import { api } from '@/lib/api';

interface SummaryTabProps {
  days: number;
}

interface KPIs {
  total_pnl: number;
  total_trades: number;
  winners: number;
  losers: number;
  win_rate: number;
  avg_win: number;
  avg_loss: number;
  profit_factor: number;
  expectancy: number;
  best_day: { date: string; pnl: number; trades: number } | null;
  worst_day: { date: string; pnl: number; trades: number } | null;
  max_win_streak: number;
  max_loss_streak: number;
  current_streak: number;
  current_streak_type: string | null;
  avg_duration_min: number;
  win_days: number;
  loss_days: number;
  trading_days: number;
  largest_win: number;
  largest_loss: number;
}

interface DailyPnl {
  date: string;
  pnl: number;
  trades: number;
  win_rate: number;
}

interface EquityCurvePoint {
  date: string;
  cumulative_pnl: number;
  trade_count: number;
}

interface OverviewData {
  has_data: boolean;
  period_days: number;
  kpis: KPIs | null;
  equity_curve: EquityCurvePoint[];
  daily_pnl: DailyPnl[];
}

interface EdgeConfidenceData {
  has_data: boolean;
  verdict: 'real_edge' | 'losing_edge' | 'inconclusive' | 'too_few';
  observed_win_rate: number;
  ci_lower: number;
  ci_upper: number;
  n: number;
  message: string;
}

function formatDateShort(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
}

function formatDuration(minutes: number): string {
  if (!minutes) return '—';
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  if (hours < 24) return mins > 0 ? `${hours}h ${mins}m` : `${hours}h`;
  const days = Math.floor(hours / 24);
  return `${days}d`;
}

// ─── Edge Confidence Widget ────────────────────────────────────────────────────

function EdgeConfidenceCard({ days }: { days: number }) {
  const [data, setData] = useState<EdgeConfidenceData | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setIsLoading(true);
      try {
        const res = await api.get('/api/analytics/edge-confidence', { params: { days } });
        if (!cancelled) setData(res.data);
      } catch {
        if (!cancelled) setData(null);
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [days]);

  if (isLoading || !data?.has_data) return null;

  const verdictConfig = {
    real_edge: {
      color: 'text-green-600 dark:text-green-400',
      bg: 'bg-green-50 dark:bg-green-900/20',
      border: 'border-green-200 dark:border-green-800',
      barColor: 'rgba(34, 197, 94, 0.7)',
      label: 'Real Edge',
    },
    losing_edge: {
      color: 'text-red-600 dark:text-red-400',
      bg: 'bg-red-50 dark:bg-red-900/20',
      border: 'border-red-200 dark:border-red-800',
      barColor: 'rgba(239, 68, 68, 0.7)',
      label: 'Losing Edge',
    },
    inconclusive: {
      color: 'text-amber-600 dark:text-amber-400',
      bg: 'bg-amber-50 dark:bg-amber-900/20',
      border: 'border-amber-200 dark:border-amber-800',
      barColor: 'rgba(234, 179, 8, 0.7)',
      label: 'Inconclusive',
    },
    too_few: {
      color: 'text-muted-foreground',
      bg: 'bg-muted',
      border: 'border-border',
      barColor: 'rgba(107, 114, 128, 0.5)',
      label: 'Need More Data',
    },
  };

  const cfg = verdictConfig[data.verdict] ?? verdictConfig.inconclusive;
  const containerPct = (v: number) => `${Math.max(0, Math.min(100, v))}%`;

  return (
    <div className={cn('rounded-lg border overflow-hidden border-l-2', cfg.border)}>
      <div className="px-5 py-4">
        <div className="flex items-start justify-between mb-3">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <CheckCircle2 className={cn('h-4 w-4', cfg.color)} />
              <span className="text-xs font-medium uppercase tracking-widest text-muted-foreground">Edge Confidence</span>
            </div>
            <p className="text-sm font-medium text-foreground leading-snug">{data.message}</p>
          </div>
          <span className={cn('text-xs font-semibold uppercase tracking-wide', cfg.color)}>
            {cfg.label}
          </span>
        </div>

        <div className="mt-4 mb-2">
          <div className="flex items-center justify-between text-[10px] text-muted-foreground mb-1">
            <span>0%</span>
            <span className="font-medium">50% breakeven</span>
            <span>100%</span>
          </div>
          <div className="relative h-6 bg-muted/60 rounded-full overflow-hidden border border-border">
            <div
              className="absolute top-0 bottom-0 rounded-full opacity-60"
              style={{
                left: containerPct(data.ci_lower),
                width: `${Math.max(0, Math.min(100, data.ci_upper) - Math.max(0, data.ci_lower))}%`,
                backgroundColor: cfg.barColor,
              }}
            />
            <div className="absolute top-0 bottom-0 w-px bg-border z-10" style={{ left: '50%' }} />
            <div
              className="absolute top-1/2 -translate-y-1/2 w-3 h-3 rounded-full border-2 border-background shadow-sm z-20"
              style={{
                left: `calc(${containerPct(data.observed_win_rate)} - 6px)`,
                backgroundColor: cfg.barColor.replace(/[\d.]+\)$/, '1)'),
              }}
              title={`Observed: ${data.observed_win_rate}%`}
            />
          </div>
          <div className="flex items-center justify-between text-[10px] text-muted-foreground mt-1">
            <span>CI lower: {data.ci_lower}%</span>
            <span className={cn('font-semibold', cfg.color)}>Observed: {data.observed_win_rate}%</span>
            <span>CI upper: {data.ci_upper}%</span>
          </div>
        </div>

        <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
          <span><span className="font-medium text-foreground">{data.n}</span> trades analyzed</span>
          <span>95% confidence interval</span>
        </div>
      </div>
    </div>
  );
}

// ─── Main Tab ─────────────────────────────────────────────────────────────────

export default function SummaryTab({ days }: SummaryTabProps) {
  const [data, setData] = useState<OverviewData | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const fetchData = async () => {
      setIsLoading(true);
      try {
        const res = await api.get('/api/analytics/overview', { params: { days } });
        if (!cancelled) setData(res.data);
      } catch (e) {
        console.error('Failed to fetch overview:', e);
        if (!cancelled) setData(null);
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    };
    fetchData();
    return () => { cancelled = true; };
  }, [days]);

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[1,2,3,4].map(i => <Skeleton key={i} className="h-24 rounded-lg" />)}
        </div>
        <Skeleton className="h-56 rounded-lg" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[1,2,3,4].map(i => <Skeleton key={i} className="h-20 rounded-lg" />)}
        </div>
      </div>
    );
  }

  if (!data?.has_data || !data.kpis) {
    return (
      <div className="bg-card rounded-lg border border-border px-6 py-10">
        <div className="flex flex-col items-center mb-8">
          <BarChart3 className="h-6 w-6 text-muted-foreground/40 mb-3" />
          <p className="font-semibold text-foreground">No trading data for this period</p>
          <p className="text-sm text-muted-foreground mt-1">Complete some trades to see analytics</p>
        </div>
        <div className="grid grid-cols-2 gap-3 max-w-sm mx-auto">
          {[
            { stat: '89%', label: 'of F&O traders lose money', source: 'SEBI FY2023' },
            { stat: '5×', label: 'avg loss vs gain for retail intraday traders', source: 'SEBI data' },
            { stat: '40%', label: 'of losses come from revenge trades after a bad day', source: 'Behavioral research' },
            { stat: '2 min', label: 'median time before an emotional re-entry after a stop-loss', source: 'SEBI FY2022' },
          ].map((item, i) => (
            <div key={i} className="p-3 rounded-lg bg-muted/50 border border-border/60">
              <p className="text-lg font-bold text-primary">{item.stat}</p>
              <p className="text-xs text-muted-foreground mt-0.5">{item.label}</p>
              <p className="text-[10px] text-muted-foreground/60 mt-1">{item.source}</p>
            </div>
          ))}
        </div>
      </div>
    );
  }

  const { kpis, equity_curve, daily_pnl } = data;
  const isProfit = kpis.total_pnl >= 0;

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Edge Confidence — top of page */}
      <div className="animate-fade-in-up">
        <EdgeConfidenceCard days={days} />
      </div>

      {/* KPI Grid Row 1 — Core metrics */}
      <div
        className="grid grid-cols-2 md:grid-cols-4 gap-4 animate-fade-in-up"
        style={{ animationDelay: '60ms' }}
      >
        <KPICard
          label="Total P&L"
          value={formatCurrency(kpis.total_pnl)}
          color={isProfit ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}
          icon={isProfit ? TrendingUp : TrendingDown}
          sub={`${kpis.total_trades} trades`}
        />
        <KPICard
          label="Win Rate"
          value={`${kpis.win_rate}%`}
          color={kpis.win_rate >= 50 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}
          sub={`${kpis.winners}W / ${kpis.losers}L`}
        />
        <KPICard
          label="Profit Factor"
          value={kpis.profit_factor > 0 ? kpis.profit_factor.toFixed(2) : '—'}
          color={kpis.profit_factor >= 1.5 ? 'text-green-600 dark:text-green-400' : kpis.profit_factor >= 1 ? 'text-foreground' : 'text-red-600 dark:text-red-400'}
          sub={kpis.profit_factor >= 1.5 ? 'Good edge' : kpis.profit_factor >= 1 ? 'Breakeven zone' : 'Losing edge'}
          icon={Target}
        />
        <KPICard
          label="Expectancy"
          value={formatCurrency(kpis.expectancy)}
          color={kpis.expectancy >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}
          sub="Avg P&L per trade"
          icon={Zap}
        />
      </div>

      {/* KPI Grid Row 2 — Win/Loss details */}
      <div
        className="grid grid-cols-2 md:grid-cols-4 gap-4 animate-fade-in-up"
        style={{ animationDelay: '120ms' }}
      >
        <KPICard
          label="Avg Win"
          value={formatCurrency(kpis.avg_win)}
          color="text-green-600 dark:text-green-400"
          sub={`Largest: ${formatCurrency(kpis.largest_win)}`}
        />
        <KPICard
          label="Avg Loss"
          value={formatCurrency(kpis.avg_loss)}
          color="text-red-600 dark:text-red-400"
          sub={`Largest: ${formatCurrency(kpis.largest_loss)}`}
        />
        <KPICard
          label="Avg Duration"
          value={formatDuration(kpis.avg_duration_min)}
          color="text-foreground"
          sub="Per trade"
          icon={Clock}
        />
        <KPICard
          label="Trading Days"
          value={String(kpis.trading_days)}
          color="text-foreground"
          sub={`${kpis.win_days}W / ${kpis.loss_days}L days`}
        />
      </div>

      {/* Bento grid: Equity curve + Sidebar */}
      <div
        className="grid grid-cols-12 gap-4 animate-fade-in-up"
        style={{ animationDelay: '180ms' }}
      >
        {/* Equity Curve — 8 cols */}
        {equity_curve.length > 1 && (
          <div className="col-span-12 md:col-span-8 bg-card rounded-lg border border-border">
            <div className="px-5 py-4 border-b border-border flex items-center justify-between">
              <div>
                <p className="text-xs font-medium uppercase tracking-widest text-muted-foreground">Equity Curve</p>
                <p className="text-xs text-muted-foreground mt-0.5">Cumulative P&L over time</p>
              </div>
              <div className={cn(
                'text-sm font-bold tabular-nums font-mono',
                isProfit ? 'text-green-600' : 'text-red-600'
              )}>
                {isProfit ? '+' : ''}{formatCurrency(kpis.total_pnl)}
              </div>
            </div>
            <div className="px-4 py-4">
              <div className="h-[260px]">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={equity_curve}>
                    <defs>
                      <linearGradient id="equityGradientSummary" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor={isProfit ? 'hsl(142, 71%, 45%)' : 'hsl(0, 84%, 60%)'} stopOpacity={0.2} />
                        <stop offset="100%" stopColor={isProfit ? 'hsl(142, 71%, 45%)' : 'hsl(0, 84%, 60%)'} stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" strokeOpacity={0.5} vertical={false} />
                    <XAxis
                      dataKey="date"
                      tickFormatter={formatDateShort}
                      axisLine={false}
                      tickLine={false}
                      tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }}
                      interval="preserveStartEnd"
                    />
                    <YAxis
                      axisLine={false}
                      tickLine={false}
                      tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }}
                      tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`}
                    />
                    <Tooltip content={<EquityTooltip />} />
                    <ReferenceLine y={0} stroke="hsl(var(--border))" strokeWidth={1.5} />
                    <Area
                      type="monotone"
                      dataKey="cumulative_pnl"
                      stroke={isProfit ? 'hsl(142, 71%, 45%)' : 'hsl(0, 84%, 60%)'}
                      strokeWidth={2}
                      fill="url(#equityGradientSummary)"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        )}

        {/* Sidebar — 4 cols: Best/Worst Day + Streaks */}
        <div className="col-span-12 md:col-span-4 bg-card rounded-lg border border-border px-5 py-4 flex flex-col gap-4">
          {/* Best Day */}
          <div>
            <div className="flex items-center gap-2 mb-2">
              <Trophy className="h-3.5 w-3.5 text-green-500" />
              <p className="text-xs font-medium uppercase tracking-widest text-muted-foreground">Best Day</p>
            </div>
            {kpis.best_day ? (
              <>
                <p className="text-2xl font-semibold font-mono text-green-600 dark:text-green-400 tabular-nums">
                  {formatCurrency(kpis.best_day.pnl)}
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  {formatDateShort(kpis.best_day.date)} · {kpis.best_day.trades} trades
                </p>
              </>
            ) : (
              <p className="text-2xl font-semibold font-mono text-muted-foreground">—</p>
            )}
          </div>

          <div className="border-t border-border" />

          {/* Worst Day */}
          <div>
            <div className="flex items-center gap-2 mb-2">
              <Flame className="h-3.5 w-3.5 text-red-500" />
              <p className="text-xs font-medium uppercase tracking-widest text-muted-foreground">Worst Day</p>
            </div>
            {kpis.worst_day ? (
              <>
                <p className="text-2xl font-semibold font-mono text-red-600 dark:text-red-400 tabular-nums">
                  {formatCurrency(kpis.worst_day.pnl)}
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  {formatDateShort(kpis.worst_day.date)} · {kpis.worst_day.trades} trades
                </p>
              </>
            ) : (
              <p className="text-2xl font-semibold font-mono text-muted-foreground">—</p>
            )}
          </div>

          <div className="border-t border-border" />

          {/* Streaks */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-xs font-medium uppercase tracking-widest text-muted-foreground mb-1">Win Streak</p>
              <p className="text-xl font-semibold font-mono text-green-600 dark:text-green-400 tabular-nums">
                {kpis.max_win_streak}
              </p>
            </div>
            <div>
              <p className="text-xs font-medium uppercase tracking-widest text-muted-foreground mb-1">Loss Streak</p>
              <p className="text-xl font-semibold font-mono text-red-600 dark:text-red-400 tabular-nums">
                {kpis.max_loss_streak}
              </p>
            </div>
          </div>

          {kpis.current_streak > 0 && kpis.current_streak_type && (
            <div className={cn(
              'rounded-lg px-3 py-2 text-center',
              kpis.current_streak_type === 'win'
                ? 'bg-green-50 dark:bg-green-900/20'
                : 'bg-red-50 dark:bg-red-900/20'
            )}>
              <p className="text-[10px] text-muted-foreground uppercase tracking-widest mb-0.5">Current Streak</p>
              <p className={cn(
                'text-xl font-bold font-mono tabular-nums',
                kpis.current_streak_type === 'win' ? 'text-green-600' : 'text-red-600'
              )}>
                {kpis.current_streak} {kpis.current_streak_type === 'win' ? 'W' : 'L'}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Daily P&L Bar Chart */}
      {daily_pnl.length > 0 && (
        <div
          className="bg-card rounded-lg border border-border animate-fade-in-up"
          style={{ animationDelay: '240ms' }}
        >
          <div className="px-5 py-4 border-b border-border flex items-center justify-between">
            <div>
              <p className="text-xs font-medium uppercase tracking-widest text-muted-foreground">Daily P&L</p>
              <p className="text-xs text-muted-foreground mt-0.5">Profit and loss by trading day</p>
            </div>
            <div className="flex items-center gap-3 text-xs text-muted-foreground">
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-green-500" />
                {kpis.win_days} green
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-red-500" />
                {kpis.loss_days} red
              </span>
            </div>
          </div>
          <div className="px-4 py-4">
            <div className="h-[200px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={daily_pnl}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" strokeOpacity={0.5} vertical={false} />
                  <XAxis
                    dataKey="date"
                    tickFormatter={formatDateShort}
                    axisLine={false}
                    tickLine={false}
                    tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }}
                    interval="preserveStartEnd"
                  />
                  <YAxis
                    axisLine={false}
                    tickLine={false}
                    tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }}
                    tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`}
                  />
                  <Tooltip content={<DailyTooltip />} />
                  <ReferenceLine y={0} stroke="hsl(var(--border))" strokeWidth={1.5} />
                  <Bar dataKey="pnl" radius={[2, 2, 0, 0]}>
                    {daily_pnl.map((entry, index) => (
                      <Cell
                        key={index}
                        fill={entry.pnl >= 0 ? 'hsl(142, 71%, 45%)' : 'hsl(0, 84%, 60%)'}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Sub-components ──────────────────────────────────────────────────────────

function KPICard({
  label,
  value,
  color,
  sub,
  icon: Icon,
}: {
  label: string;
  value: string;
  color: string;
  sub?: string;
  icon?: React.ComponentType<{ className?: string }>;
}) {
  return (
    <div className="bg-card rounded-lg border border-border px-4 py-3">
      <div className="flex items-center gap-1.5 mb-1.5">
        {Icon && <Icon className="h-3 w-3 text-muted-foreground" />}
        <p className="text-xs text-muted-foreground">{label}</p>
      </div>
      <p className={cn('text-2xl font-semibold tabular-nums font-mono', color)}>{value}</p>
      {sub && <p className="text-xs text-muted-foreground mt-0.5">{sub}</p>}
    </div>
  );
}

function EquityTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="bg-popover border border-border rounded-lg p-3 shadow-lg text-sm">
      <p className="font-medium text-foreground mb-1">{formatDateShort(d.date)}</p>
      <p className={cn('tabular-nums font-mono', d.cumulative_pnl >= 0 ? 'text-green-600' : 'text-red-600')}>
        {d.cumulative_pnl >= 0 ? '+' : ''}{formatCurrency(d.cumulative_pnl)}
      </p>
      <p className="text-xs text-muted-foreground">{d.trade_count} trades</p>
    </div>
  );
}

function DailyTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="bg-popover border border-border rounded-lg p-3 shadow-lg text-sm">
      <p className="font-medium text-foreground mb-1">{formatDateShort(d.date)}</p>
      <p className={cn('tabular-nums font-mono', d.pnl >= 0 ? 'text-green-600' : 'text-red-600')}>
        {d.pnl >= 0 ? '+' : ''}{formatCurrency(d.pnl)}
      </p>
      <p className="text-xs text-muted-foreground">{d.trades} trades &middot; {d.win_rate}% WR</p>
    </div>
  );
}
