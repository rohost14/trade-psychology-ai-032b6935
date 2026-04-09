import { useState, useEffect } from 'react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from 'recharts';
import {
  ShieldAlert, TrendingDown, Shield, ArrowUp, ArrowDown,
} from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { formatCurrency, formatCurrencyWithSign } from '@/lib/formatters';
import { api } from '@/lib/api';
import AINarrativeCard from './AINarrativeCard';

interface ProgressTabProps {
  days: number;
}

interface DrawdownPeriod {
  start: string;
  end: string;
  depth: number;
  duration_days: number;
}

interface DrawdownPoint {
  date: string;
  cumulative_pnl: number;
  drawdown: number;
}

interface RiskData {
  has_data: boolean;
  period_days: number;
  max_drawdown: {
    amount: number;
    start_date: string | null;
    end_date: string | null;
  };
  drawdown_periods: DrawdownPeriod[];
  daily_volatility: number;
  var_95: number;
  risk_reward_ratio: number;
  consecutive_max: {
    wins: number;
    losses: number;
  };
  alerts_summary: { pattern_type: string; count: number; last_detected: string | null }[];
  recent_alerts: {
    id: string;
    pattern_type: string;
    severity: string;
    message: string;
    detected_at: string | null;
    acknowledged: boolean;
  }[];
}

interface RiskScore {
  score: number;
  components?: Record<string, number>;
}

interface OverviewData {
  has_data: boolean;
  equity_curve: { date: string; cumulative_pnl: number }[];
}

interface ProgressMetric {
  value: number | null;
  improved: boolean;
  pct_change: number | null;
}

interface ProgressData {
  has_data: boolean;
  this_week: {
    pnl: number | null;
    win_rate: number | null;
    trade_count: number | null;
    danger_alerts: number | null;
  };
  last_week: {
    pnl: number | null;
    win_rate: number | null;
    trade_count: number | null;
    danger_alerts: number | null;
  };
  alerts: {
    this_week: number;
    last_week: number;
  };
  comparison: {
    pnl: ProgressMetric;
    win_rate: ProgressMetric;
    trade_count: ProgressMetric;
    danger_alerts: ProgressMetric;
  };
}

function formatDateShort(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
}

// ─── Period Comparison Cards ───────────────────────────────────────────────────

function PeriodComparisonCards() {
  const [data, setData] = useState<ProgressData | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setIsLoading(true);
      try {
        const res = await api.get('/api/analytics/progress');
        if (!cancelled) setData(res.data);
      } catch {
        if (!cancelled) setData(null);
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  if (isLoading || !data?.has_data) return null;

  const metrics = [
    {
      label: 'P&L',
      current: data.this_week.pnl ?? 0,
      prev: data.last_week.pnl ?? 0,
      improved: data.comparison.pnl.improved,
      format: (v: number) => formatCurrency(v),
      colorize: true,
    },
    {
      label: 'Win Rate',
      current: data.this_week.win_rate ?? 0,
      prev: data.last_week.win_rate ?? 0,
      improved: data.comparison.win_rate.improved,
      format: (v: number) => `${v.toFixed(1)}%`,
      colorize: false,
    },
    {
      label: 'Trades',
      current: data.this_week.trade_count ?? 0,
      prev: data.last_week.trade_count ?? 0,
      improved: data.comparison.trade_count.improved,
      format: (v: number) => String(v),
      colorize: false,
    },
    {
      label: 'Danger Alerts',
      current: data.alerts.this_week,
      prev: data.alerts.last_week,
      improved: data.comparison.danger_alerts.improved,
      format: (v: number) => String(v),
      colorize: false,
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {metrics.map((m) => (
        <div key={m.label} className="tm-card p-5">
          <p className="tm-label mb-2">{m.label}</p>
          <p className={cn(
            'text-3xl font-bold font-mono tabular-nums',
            m.colorize
              ? (m.current >= 0 ? 'text-tm-profit' : 'text-tm-loss')
              : 'text-foreground'
          )}>
            {m.format(m.current)}
          </p>
          <div className="flex items-center gap-1 mt-1.5">
            {m.improved ? (
              <ArrowUp className="h-3 w-3 text-tm-profit" />
            ) : (
              <ArrowDown className="h-3 w-3 text-tm-loss" />
            )}
            <p className="text-xs text-muted-foreground">vs {m.format(m.prev)} last week</p>
          </div>
        </div>
      ))}
    </div>
  );
}

// ─── Main Tab ─────────────────────────────────────────────────────────────────

export default function ProgressTab({ days }: ProgressTabProps) {
  const [data, setData] = useState<RiskData | null>(null);
  const [riskScore, setRiskScore] = useState<RiskScore | null>(null);
  const [drawdownData, setDrawdownData] = useState<DrawdownPoint[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const fetchData = async () => {
      setIsLoading(true);
      try {
        const [metricsRes, scoreRes, overviewRes] = await Promise.allSettled([
          api.get('/api/analytics/risk-metrics', { params: { days } }),
          api.get('/api/analytics/risk-score'),
          api.get('/api/analytics/overview', { params: { days } }),
        ]);

        if (!cancelled) {
          if (metricsRes.status === 'fulfilled') setData(metricsRes.value.data);
          if (scoreRes.status === 'fulfilled') setRiskScore(scoreRes.value.data);

          if (overviewRes.status === 'fulfilled') {
            const overview = overviewRes.value.data as OverviewData;
            if (overview?.has_data && overview.equity_curve?.length > 0) {
              let peak = 0;
              const ddData: DrawdownPoint[] = overview.equity_curve.map((point) => {
                if (point.cumulative_pnl > peak) peak = point.cumulative_pnl;
                const dd = point.cumulative_pnl - peak;
                return {
                  date: point.date,
                  cumulative_pnl: point.cumulative_pnl,
                  drawdown: Math.round(dd * 100) / 100,
                };
              });
              setDrawdownData(ddData);
            }
          }
        }
      } catch (e) {
        console.error('Failed to fetch risk data:', e);
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
          {[1,2,3,4].map(i => <Skeleton key={i} className="h-24 rounded-xl" />)}
        </div>
        <Skeleton className="h-48 rounded-xl" />
        <Skeleton className="h-32 rounded-xl" />
      </div>
    );
  }

  if (!data?.has_data) {
    return (
      <div className="tm-card flex flex-col items-center justify-center min-h-[40vh]">
        <ShieldAlert className="h-10 w-10 text-muted-foreground/40 mb-3" />
        <p className="font-medium text-foreground">No risk data for this period</p>
        <p className="text-sm text-muted-foreground mt-1">Complete some trades to see risk metrics</p>
      </div>
    );
  }

  return (
    <div className="space-y-5 animate-fade-in">
      {/* Period Comparison — Stripe-style metric cards */}
      <PeriodComparisonCards />

      {/* AI Narrative — left border accent */}
      <div className="border-l-4 border-tm-brand rounded-r-xl overflow-hidden">
        <AINarrativeCard tab="risk" days={days} />
      </div>

      {/* Risk KPI — 3 individual cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="tm-card p-5">
          <p className="tm-label mb-2">VaR (95%)</p>
          <p className="text-3xl font-bold font-mono tabular-nums text-tm-loss">
            {formatCurrency(data.var_95)}
          </p>
          <p className="text-xs text-muted-foreground mt-1">Worst daily expected (5th pctile)</p>
        </div>

        <div className="tm-card p-5">
          <p className="tm-label mb-2">Daily Volatility</p>
          <p className="text-3xl font-bold font-mono tabular-nums text-foreground">
            {formatCurrency(data.daily_volatility)}
          </p>
          <p className="text-xs text-muted-foreground mt-1">Std dev of daily P&L</p>
        </div>

        <div className="tm-card p-5">
          <p className="tm-label mb-2">Risk-Reward Ratio</p>
          <p className={cn(
            'text-3xl font-bold font-mono tabular-nums',
            data.risk_reward_ratio >= 1.5 ? 'text-tm-profit' :
              data.risk_reward_ratio >= 1 ? 'text-foreground' :
                'text-tm-loss'
          )}>
            {data.risk_reward_ratio > 0 ? data.risk_reward_ratio.toFixed(2) : '—'}
          </p>
          <p className="text-xs text-muted-foreground mt-1">
            {data.risk_reward_ratio >= 1.5 ? 'Good risk management' :
              data.risk_reward_ratio >= 1 ? 'Breakeven risk' : 'Risking more than gaining'}
          </p>
        </div>
      </div>

      {/* Max Drawdown card + Discipline Score */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="tm-card p-5">
          <p className="tm-label mb-2">Max Drawdown</p>
          <p className="text-3xl font-bold font-mono tabular-nums text-tm-loss">
            {formatCurrency(data.max_drawdown.amount)}
          </p>
          {data.max_drawdown.start_date && (
            <p className="text-xs text-muted-foreground mt-1">
              {formatDateShort(data.max_drawdown.start_date)}
              {data.max_drawdown.end_date && ` – ${formatDateShort(data.max_drawdown.end_date)}`}
            </p>
          )}
        </div>

        {riskScore && (
          <div className="tm-card p-5">
            <div className="flex items-center gap-1.5 mb-2">
              <Shield className="h-3.5 w-3.5 text-muted-foreground" />
              <p className="text-xs font-medium uppercase tracking-widest text-muted-foreground">Discipline Score</p>
            </div>
            <div className="flex items-end gap-2">
              <p className={cn(
                'text-3xl font-bold font-mono tabular-nums',
                (riskScore.score ?? 0) >= 70 ? 'text-tm-profit' :
                  (riskScore.score ?? 0) >= 40 ? 'text-tm-obs' : 'text-tm-loss'
              )}>
                {riskScore.score ?? '—'}
              </p>
              <p className="text-base text-muted-foreground mb-0.5">/100</p>
            </div>
            {riskScore.components && Object.keys(riskScore.components).length > 0 && (
              <div className="mt-2 space-y-1">
                {Object.entries(riskScore.components).slice(0, 3).map(([key, val]) => (
                  <div key={key} className="flex items-center justify-between">
                    <span className="text-[10px] text-muted-foreground capitalize">{key.replace(/_/g, ' ')}</span>
                    <span className="text-[10px] tabular-nums font-mono text-muted-foreground">{val}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Placeholder slot when no riskScore to keep grid aligned */}
        {!riskScore && <div />}
      </div>

      {/* Consecutive Streaks — 2 small cards */}
      <div className="grid grid-cols-2 gap-4">
        <div className="tm-card p-5">
          <p className="tm-label mb-2">Max Win Streak</p>
          <p className="text-3xl font-bold font-mono tabular-nums text-tm-profit">
            {data.consecutive_max.wins}
          </p>
          <p className="text-xs text-muted-foreground mt-1">Consecutive winning trades</p>
        </div>
        <div className="tm-card p-5">
          <p className="tm-label mb-2">Max Loss Streak</p>
          <p className="text-3xl font-bold font-mono tabular-nums text-tm-loss">
            {data.consecutive_max.losses}
          </p>
          <p className="text-xs text-muted-foreground mt-1">Consecutive losing trades</p>
        </div>
      </div>

      {/* Drawdown Chart */}
      {drawdownData.length > 1 && (
        <div className="tm-card overflow-hidden">
          <div className="px-5 py-4 border-b border-border">
            <div className="flex items-center gap-2">
              <TrendingDown className="h-4 w-4 text-tm-loss" />
              <div>
                <p className="text-xs font-medium uppercase tracking-widest text-muted-foreground">Drawdown Chart</p>
                <p className="text-xs text-muted-foreground mt-0.5">Distance from equity peak over time</p>
              </div>
            </div>
          </div>
          <div className="px-5 py-4">
            <div className="h-[200px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={drawdownData}>
                  <defs>
                    <linearGradient id="drawdownGradientProgress" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="hsl(0, 84%, 60%)" stopOpacity={0.3} />
                      <stop offset="100%" stopColor="hsl(0, 84%, 60%)" stopOpacity={0} />
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
                  <Tooltip content={<DrawdownTooltip />} />
                  <ReferenceLine y={0} stroke="hsl(var(--border))" strokeWidth={1.5} />
                  <Area
                    type="monotone"
                    dataKey="drawdown"
                    stroke="hsl(0, 84%, 60%)"
                    strokeWidth={2}
                    fill="url(#drawdownGradientProgress)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}

      {/* Drawdown Periods */}
      {data.drawdown_periods.length > 0 && (
        <div className="tm-card overflow-hidden">
          <div className="px-5 py-4 border-b border-border">
            <div className="flex items-center gap-2">
              <TrendingDown className="h-4 w-4 text-tm-loss" />
              <p className="text-xs font-medium uppercase tracking-widest text-muted-foreground">Drawdown Periods</p>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border bg-muted/30">
                  <th className="px-5 py-2 text-left text-[11px] font-medium uppercase tracking-widest text-muted-foreground">Period</th>
                  <th className="px-3 py-2 text-right text-[11px] font-medium uppercase tracking-widest text-muted-foreground">Depth</th>
                  <th className="px-3 py-2 text-right text-[11px] font-medium uppercase tracking-widest text-muted-foreground">Duration</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data.drawdown_periods.map((dd, i) => (
                  <tr key={i} className="hover:bg-muted/40 transition-colors">
                    <td className="px-5 py-2.5 text-sm text-foreground">
                      {dd.start ? formatDateShort(dd.start) : '—'}
                      {' \u2192 '}
                      {dd.end ? formatDateShort(dd.end) : 'ongoing'}
                    </td>
                    <td className="px-3 py-2.5 text-right text-sm tabular-nums font-mono text-tm-loss font-medium">
                      {formatCurrency(dd.depth)}
                    </td>
                    <td className="px-3 py-2.5 text-right text-sm text-muted-foreground">
                      {dd.duration_days} day{dd.duration_days !== 1 ? 's' : ''}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Risk Alert Summary */}
      {data.alerts_summary.length > 0 && (
        <div className="tm-card overflow-hidden">
          <div className="px-5 py-4 border-b border-border flex items-center gap-2">
            <p className="text-xs font-medium uppercase tracking-widest text-muted-foreground">Risk Alert Summary</p>
            <span className="text-xs text-muted-foreground">
              ({data.alerts_summary.reduce((s, a) => s + a.count, 0)} total)
            </span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border bg-muted/30">
                  <th className="px-5 py-2 text-left text-[11px] font-medium uppercase tracking-widest text-muted-foreground">Pattern</th>
                  <th className="px-3 py-2 text-right text-[11px] font-medium uppercase tracking-widest text-muted-foreground">Count</th>
                  <th className="px-3 py-2 text-right text-[11px] font-medium uppercase tracking-widest text-muted-foreground">Last Detected</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data.alerts_summary.map((a, i) => (
                  <tr key={i} className="hover:bg-muted/40 transition-colors">
                    <td className="px-5 py-2.5 text-sm font-medium text-foreground capitalize">
                      {a.pattern_type.replace(/_/g, ' ')}
                    </td>
                    <td className="px-3 py-2.5 text-right text-sm tabular-nums font-mono">{a.count}</td>
                    <td className="px-3 py-2.5 text-right text-sm text-muted-foreground">
                      {a.last_detected ? formatDateShort(a.last_detected) : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function DrawdownTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="bg-popover border border-border rounded-lg p-3 shadow-lg text-sm">
      <p className="font-medium text-foreground mb-1">{formatDateShort(d.date)}</p>
      <div className="space-y-0.5">
        <p className="text-xs text-muted-foreground">
          Drawdown: <span className="tabular-nums font-mono text-tm-loss">{formatCurrency(d.drawdown)}</span>
        </p>
        <p className="text-xs text-muted-foreground">
          Equity: <span className={cn('tabular-nums font-mono', d.cumulative_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
            {formatCurrency(d.cumulative_pnl)}
          </span>
        </p>
      </div>
    </div>
  );
}
