import { useState, useEffect } from 'react';
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine, Cell,
} from 'recharts';
import {
  TrendingUp, TrendingDown, BarChart3,
  Flame, Trophy, Clock, Zap,
} from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { formatCurrency } from '@/lib/formatters';
import { api } from '@/lib/api';
import AINarrativeCard from './AINarrativeCard';

interface OverviewTabProps {
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

export default function OverviewTab({ days }: OverviewTabProps) {
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
      <div className="space-y-3">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-border rounded-lg overflow-hidden">
          {[1,2,3,4].map(i => <Skeleton key={i} className="h-16 rounded-none" />)}
        </div>
        <Skeleton className="h-[300px] rounded-xl" />
        <Skeleton className="h-[240px] rounded-xl" />
      </div>
    );
  }

  if (!data?.has_data || !data.kpis) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[40vh] tm-card overflow-hidden">
        <BarChart3 className="h-10 w-10 text-muted-foreground/40 mb-3" />
        <p className="font-medium text-foreground">No trading data for this period</p>
        <p className="text-sm text-muted-foreground mt-1">Complete some trades to see analytics</p>
      </div>
    );
  }

  const { kpis, equity_curve, daily_pnl } = data;
  const isProfit = kpis.total_pnl >= 0;

  return (
    <div className="space-y-4">
      {/* AI Narrative */}
      <AINarrativeCard tab="overview" days={days} />

      {/* KPI Strip — Row 1: Core metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-border rounded-lg overflow-hidden">
        <KPICell
          label="Total P&L"
          value={formatCurrency(kpis.total_pnl)}
          color={isProfit ? 'text-tm-profit' : 'text-tm-loss'}
          icon={isProfit ? TrendingUp : TrendingDown}
          highlight
        />
        <KPICell
          label="Win Rate"
          value={`${kpis.win_rate}%`}
          color={kpis.win_rate >= 50 ? 'text-tm-profit' : 'text-tm-loss'}
          sub={`${kpis.winners}W / ${kpis.losers}L of ${kpis.total_trades}`}
        />
        <KPICell
          label="Profit Factor"
          value={kpis.profit_factor > 0 ? kpis.profit_factor.toFixed(2) : '—'}
          color={kpis.profit_factor >= 1.5 ? 'text-tm-profit' : kpis.profit_factor >= 1 ? 'text-foreground' : 'text-tm-loss'}
          sub={kpis.profit_factor >= 1.5 ? 'Good edge' : kpis.profit_factor >= 1 ? 'Breakeven zone' : 'Losing edge'}
        />
        <KPICell
          label="Expectancy"
          value={formatCurrency(kpis.expectancy)}
          color={kpis.expectancy >= 0 ? 'text-tm-profit' : 'text-tm-loss'}
          sub="Avg P&L per trade"
          icon={Zap}
        />
      </div>

      {/* KPI Strip — Row 2: Win/Loss details */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-border rounded-lg overflow-hidden">
        <KPICell
          label="Avg Win"
          value={formatCurrency(kpis.avg_win)}
          color="text-tm-profit"
          sub={`Largest: ${formatCurrency(kpis.largest_win)}`}
        />
        <KPICell
          label="Avg Loss"
          value={formatCurrency(kpis.avg_loss)}
          color="text-tm-loss"
          sub={`Largest: ${formatCurrency(kpis.largest_loss)}`}
        />
        <KPICell
          label="Best Day"
          value={kpis.best_day ? formatCurrency(kpis.best_day.pnl) : '—'}
          color="text-tm-profit"
          sub={kpis.best_day ? `${formatDateShort(kpis.best_day.date)} (${kpis.best_day.trades} trades)` : ''}
          icon={Trophy}
        />
        <KPICell
          label="Worst Day"
          value={kpis.worst_day ? formatCurrency(kpis.worst_day.pnl) : '—'}
          color="text-tm-loss"
          sub={kpis.worst_day ? `${formatDateShort(kpis.worst_day.date)} (${kpis.worst_day.trades} trades)` : ''}
          icon={Flame}
        />
      </div>

      {/* KPI Strip — Row 3: Activity + Streaks */}
      <div className="grid grid-cols-3 md:grid-cols-6 gap-px bg-border rounded-lg overflow-hidden">
        <div className="bg-card px-4 py-3">
          <p className="text-xs text-muted-foreground">Trading Days</p>
          <p className="text-lg font-bold tabular-nums text-foreground">
            {kpis.trading_days}
            <span className="text-xs text-muted-foreground font-normal ml-1">
              ({kpis.win_days}W / {kpis.loss_days}L)
            </span>
          </p>
        </div>
        <div className="bg-card px-4 py-3">
          <div className="flex items-center gap-1 mb-0.5">
            <Clock className="h-3 w-3 text-muted-foreground" />
            <p className="text-xs text-muted-foreground">Avg Duration</p>
          </div>
          <p className="text-lg font-bold tabular-nums text-foreground">
            {formatDuration(kpis.avg_duration_min)}
          </p>
        </div>
        <div className="bg-card px-4 py-3">
          <p className="text-xs text-muted-foreground">Avg Trades/Day</p>
          <p className="text-lg font-bold tabular-nums text-foreground">
            {kpis.trading_days > 0 ? (kpis.total_trades / kpis.trading_days).toFixed(1) : '—'}
          </p>
        </div>
        <div className="bg-card px-4 py-3">
          <p className="text-xs text-muted-foreground">Win Streak</p>
          <p className="text-lg font-bold tabular-nums text-tm-profit">{kpis.max_win_streak}</p>
        </div>
        <div className="bg-card px-4 py-3">
          <p className="text-xs text-muted-foreground">Loss Streak</p>
          <p className="text-lg font-bold tabular-nums text-tm-loss">{kpis.max_loss_streak}</p>
        </div>
        <div className="bg-card px-4 py-3">
          <p className="text-xs text-muted-foreground">Current Streak</p>
          <p className={cn(
            'text-lg font-bold tabular-nums',
            kpis.current_streak_type === 'win' ? 'text-tm-profit' : 'text-tm-loss'
          )}>
            {kpis.current_streak} {kpis.current_streak_type === 'win' ? 'W' : kpis.current_streak_type === 'loss' ? 'L' : '—'}
          </p>
        </div>
      </div>

      {/* Equity Curve */}
      {equity_curve.length > 1 && (
        <div className="tm-card overflow-hidden">
          <div className="px-4 py-3 border-b border-border flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-foreground">Equity Curve</h3>
              <p className="text-xs text-muted-foreground">Cumulative P&L over time</p>
            </div>
            <div className={cn(
              'text-sm font-bold tabular-nums font-mono',
              isProfit ? 'text-tm-profit' : 'text-tm-loss'
            )}>
              {isProfit ? '+' : ''}{formatCurrency(kpis.total_pnl)}
            </div>
          </div>
          <div className="px-4 py-4">
            <div className="h-[260px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={equity_curve}>
                  <defs>
                    <linearGradient id="equityGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={isProfit ? '#16A34A' : '#DC2626'} stopOpacity={0.2} />
                      <stop offset="100%" stopColor={isProfit ? '#16A34A' : '#DC2626'} stopOpacity={0} />
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
                    stroke={isProfit ? '#16A34A' : '#DC2626'}
                    strokeWidth={2}
                    fill="url(#equityGradient)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}

      {/* Daily P&L Bar Chart */}
      {daily_pnl.length > 0 && (
        <div className="tm-card overflow-hidden">
          <div className="px-4 py-3 border-b border-border flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-foreground">Daily P&L</h3>
              <p className="text-xs text-muted-foreground">Profit and loss by trading day</p>
            </div>
            <div className="flex items-center gap-3 text-xs text-muted-foreground">
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-tm-profit" />
                {kpis.win_days} green
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-tm-loss" />
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
                        fill={entry.pnl >= 0 ? '#16A34A' : '#DC2626'}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Daily P&L table for data-density */}
          {daily_pnl.length <= 20 && (
            <div className="border-t border-border overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="bg-muted/30">
                    <th className="px-4 py-1.5 text-left text-[10px] font-medium uppercase tracking-wide text-muted-foreground">Date</th>
                    <th className="px-3 py-1.5 text-right text-[10px] font-medium uppercase tracking-wide text-muted-foreground">P&L</th>
                    <th className="px-3 py-1.5 text-right text-[10px] font-medium uppercase tracking-wide text-muted-foreground">Trades</th>
                    <th className="px-3 py-1.5 text-right text-[10px] font-medium uppercase tracking-wide text-muted-foreground">Win Rate</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {[...daily_pnl].reverse().map((day) => (
                    <tr key={day.date} className="hover:bg-muted/30">
                      <td className="px-4 py-1.5 text-xs text-foreground">{formatDateShort(day.date)}</td>
                      <td className={cn(
                        'px-3 py-1.5 text-right text-xs tabular-nums font-mono font-medium',
                        day.pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss'
                      )}>
                        {day.pnl >= 0 ? '+' : ''}{formatCurrency(day.pnl)}
                      </td>
                      <td className="px-3 py-1.5 text-right text-xs tabular-nums text-muted-foreground">{day.trades}</td>
                      <td className={cn(
                        'px-3 py-1.5 text-right text-xs tabular-nums',
                        day.win_rate >= 50 ? 'text-tm-profit' : 'text-tm-loss'
                      )}>
                        {day.win_rate}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Sub-components ──────────────────────────────────────────────────────────

function KPICell({
  label,
  value,
  color,
  sub,
  icon: Icon,
  highlight,
}: {
  label: string;
  value: string;
  color: string;
  sub?: string;
  icon?: React.ComponentType<{ className?: string }>;
  highlight?: boolean;
}) {
  return (
    <div className={cn('bg-card px-4 py-3', highlight && 'bg-card')}>
      <div className="flex items-center gap-1.5 mb-1">
        {Icon && <Icon className="h-3.5 w-3.5 text-muted-foreground" />}
        <p className="text-xs text-muted-foreground">{label}</p>
      </div>
      <p className={cn('text-xl font-bold tabular-nums font-mono', color)}>{value}</p>
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
      <p className={cn('tabular-nums font-mono', d.cumulative_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
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
      <p className={cn('tabular-nums font-mono', d.pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
        {d.pnl >= 0 ? '+' : ''}{formatCurrency(d.pnl)}
      </p>
      <p className="text-xs text-muted-foreground">{d.trades} trades &middot; {d.win_rate}% WR</p>
    </div>
  );
}
