import { useState, useEffect } from 'react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from 'recharts';
import { ShieldAlert, AlertTriangle, TrendingDown, Activity, Shield } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { formatCurrency } from '@/lib/formatters';
import { api } from '@/lib/api';
import AINarrativeCard from './AINarrativeCard';

interface RiskTabProps {
  days: number;
}

interface DrawdownPeriod {
  start: string;
  end: string;
  depth: number;
  duration_days: number;
}

interface AlertSummary {
  pattern_type: string;
  count: number;
  last_detected: string | null;
}

interface RecentAlert {
  id: string;
  pattern_type: string;
  severity: string;
  message: string;
  detected_at: string | null;
  acknowledged: boolean;
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
  alerts_summary: AlertSummary[];
  recent_alerts: RecentAlert[];
}

interface RiskScore {
  score: number;
  components?: Record<string, number>;
}

interface OverviewData {
  has_data: boolean;
  equity_curve: { date: string; cumulative_pnl: number }[];
}

function formatDateShort(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
}

const severityColors: Record<string, string> = {
  critical: 'text-red-700 bg-red-100 dark:text-red-400 dark:bg-red-900/30',
  high: 'text-tm-loss bg-red-50 dark:text-red-400 dark:bg-red-900/20',
  danger: 'text-tm-loss bg-red-50 dark:text-red-400 dark:bg-red-900/20',
  medium: 'text-amber-600 bg-amber-50 dark:text-amber-400 dark:bg-amber-900/20',
  warning: 'text-amber-600 bg-amber-50 dark:text-amber-400 dark:bg-amber-900/20',
  low: 'text-blue-600 bg-blue-50 dark:text-blue-400 dark:bg-blue-900/20',
};

export default function RiskTab({ days }: RiskTabProps) {
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

          // Calculate drawdown curve from equity curve
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
      <div className="space-y-3">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-border rounded-lg overflow-hidden">
          {[1,2,3,4].map(i => <Skeleton key={i} className="h-16 rounded-none" />)}
        </div>
        <Skeleton className="h-[280px] rounded-xl" />
        <Skeleton className="h-48 rounded-xl" />
      </div>
    );
  }

  if (!data?.has_data) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[40vh] tm-card overflow-hidden">
        <ShieldAlert className="h-10 w-10 text-muted-foreground/40 mb-3" />
        <p className="font-medium text-foreground">No risk data for this period</p>
        <p className="text-sm text-muted-foreground mt-1">Complete some trades to see risk metrics</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* AI Narrative */}
      <AINarrativeCard tab="risk" days={days} />

      {/* Risk KPI Strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-border rounded-lg overflow-hidden">
        <div className="bg-card px-4 py-3">
          <p className="text-xs text-muted-foreground">Max Drawdown</p>
          <p className="text-xl font-bold tabular-nums font-mono text-tm-loss">
            {formatCurrency(data.max_drawdown.amount)}
          </p>
          {data.max_drawdown.start_date && (
            <p className="text-xs text-muted-foreground mt-0.5">
              {formatDateShort(data.max_drawdown.start_date)}
              {data.max_drawdown.end_date && ` – ${formatDateShort(data.max_drawdown.end_date)}`}
            </p>
          )}
        </div>
        <div className="bg-card px-4 py-3">
          <p className="text-xs text-muted-foreground">VaR (95%)</p>
          <p className="text-xl font-bold tabular-nums font-mono text-tm-loss">
            {formatCurrency(data.var_95)}
          </p>
          <p className="text-xs text-muted-foreground mt-0.5">Worst daily expected (5th pctile)</p>
        </div>
        <div className="bg-card px-4 py-3">
          <p className="text-xs text-muted-foreground">Daily Volatility</p>
          <p className="text-xl font-bold tabular-nums font-mono text-foreground">
            {formatCurrency(data.daily_volatility)}
          </p>
          <p className="text-xs text-muted-foreground mt-0.5">Std dev of daily P&L</p>
        </div>
        <div className="bg-card px-4 py-3">
          <p className="text-xs text-muted-foreground">Risk-Reward Ratio</p>
          <p className={cn(
            'text-xl font-bold tabular-nums font-mono',
            data.risk_reward_ratio >= 1.5 ? 'text-tm-profit' :
            data.risk_reward_ratio >= 1 ? 'text-foreground' :
            'text-tm-loss'
          )}>
            {data.risk_reward_ratio > 0 ? data.risk_reward_ratio.toFixed(2) : '—'}
          </p>
          <p className="text-xs text-muted-foreground mt-0.5">
            {data.risk_reward_ratio >= 1.5 ? 'Good risk management' :
             data.risk_reward_ratio >= 1 ? 'Breakeven risk' : 'Risking more than gaining'}
          </p>
        </div>
      </div>

      {/* Discipline Score + Streaks */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-px bg-border rounded-lg overflow-hidden">
        {riskScore && (
          <div className="bg-card px-5 py-4">
            <div className="flex items-center gap-2 mb-1">
              <Shield className="h-4 w-4 text-muted-foreground" />
              <p className="text-xs text-muted-foreground">Discipline Score</p>
            </div>
            <p className={cn(
              'text-3xl font-bold tabular-nums font-mono',
              (riskScore.score ?? 0) >= 70 ? 'text-tm-profit' :
              (riskScore.score ?? 0) >= 40 ? 'text-amber-600' : 'text-tm-loss'
            )}>
              {riskScore.score ?? '—'}
              <span className="text-base text-muted-foreground font-normal">/100</span>
            </p>
            {/* Score components */}
            {riskScore.components && Object.keys(riskScore.components).length > 0 && (
              <div className="mt-2 space-y-1">
                {Object.entries(riskScore.components).slice(0, 4).map(([key, val]) => (
                  <div key={key} className="flex items-center justify-between">
                    <span className="text-[10px] text-muted-foreground capitalize">{key.replace(/_/g, ' ')}</span>
                    <span className="text-[10px] tabular-nums font-mono text-muted-foreground">{val}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
        <div className="bg-card px-5 py-4">
          <p className="text-xs text-muted-foreground mb-1">Max Win Streak</p>
          <p className="text-3xl font-bold tabular-nums font-mono text-tm-profit">
            {data.consecutive_max.wins}
          </p>
          <p className="text-xs text-muted-foreground mt-1">Consecutive winning trades</p>
        </div>
        <div className="bg-card px-5 py-4">
          <p className="text-xs text-muted-foreground mb-1">Max Loss Streak</p>
          <p className="text-3xl font-bold tabular-nums font-mono text-tm-loss">
            {data.consecutive_max.losses}
          </p>
          <p className="text-xs text-muted-foreground mt-1">Consecutive losing trades</p>
        </div>
      </div>

      {/* Drawdown Chart */}
      {drawdownData.length > 1 && (
        <div className="tm-card overflow-hidden overflow-hidden">
          <div className="px-4 py-3 border-b border-border">
            <div className="flex items-center gap-2">
              <TrendingDown className="h-4 w-4 text-tm-loss" />
              <div>
                <h3 className="text-sm font-semibold text-foreground">Drawdown Chart</h3>
                <p className="text-xs text-muted-foreground">Distance from equity peak over time</p>
              </div>
            </div>
          </div>
          <div className="px-4 py-4">
            <div className="h-[200px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={drawdownData}>
                  <defs>
                    <linearGradient id="drawdownGradient" x1="0" y1="0" x2="0" y2="1">
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
                    fill="url(#drawdownGradient)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}

      {/* Drawdown Periods */}
      {data.drawdown_periods.length > 0 && (
        <div className="tm-card overflow-hidden overflow-hidden">
          <div className="px-4 py-3 border-b border-border">
            <div className="flex items-center gap-2">
              <TrendingDown className="h-4 w-4 text-tm-loss" />
              <h3 className="text-sm font-semibold text-foreground">Drawdown Periods</h3>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border bg-muted/30">
                  <th className="px-4 py-2 text-left text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Period</th>
                  <th className="px-3 py-2 text-right text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Depth</th>
                  <th className="px-3 py-2 text-right text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Duration</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data.drawdown_periods.map((dd, i) => (
                  <tr key={i} className="hover:bg-muted/30">
                    <td className="px-4 py-2.5 text-sm text-foreground">
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
        <div className="tm-card overflow-hidden overflow-hidden">
          <div className="px-4 py-3 border-b border-border">
            <div className="flex items-center gap-2">
              <Activity className="h-4 w-4 text-muted-foreground" />
              <h3 className="text-sm font-semibold text-foreground">Risk Alert Summary</h3>
              <span className="text-xs text-muted-foreground">({data.alerts_summary.reduce((s, a) => s + a.count, 0)} total alerts)</span>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border bg-muted/30">
                  <th className="px-4 py-2 text-left text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Pattern</th>
                  <th className="px-3 py-2 text-right text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Count</th>
                  <th className="px-3 py-2 text-right text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Last Detected</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data.alerts_summary.map((a, i) => (
                  <tr key={i} className="hover:bg-muted/30">
                    <td className="px-4 py-2.5 text-sm font-medium text-foreground capitalize">
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

      {/* Recent Alerts */}
      {data.recent_alerts.length > 0 && (
        <div className="tm-card overflow-hidden overflow-hidden">
          <div className="px-4 py-3 border-b border-border">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-amber-600" />
              <h3 className="text-sm font-semibold text-foreground">Recent Alerts</h3>
              <span className="text-xs text-muted-foreground">Last {data.recent_alerts.length}</span>
            </div>
          </div>
          <div className="divide-y divide-border max-h-[400px] overflow-y-auto">
            {data.recent_alerts.map((alert) => (
              <div key={alert.id} className="px-4 py-3 hover:bg-muted/30">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className={cn(
                        'px-1.5 py-0.5 rounded text-[10px] font-medium uppercase',
                        severityColors[alert.severity] || severityColors.medium
                      )}>
                        {alert.severity}
                      </span>
                      <span className="text-sm font-medium text-foreground capitalize">
                        {alert.pattern_type.replace(/_/g, ' ')}
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground truncate">{alert.message}</p>
                  </div>
                  <div className="text-right flex-shrink-0">
                    <p className="text-xs text-muted-foreground">
                      {alert.detected_at ? formatDateShort(alert.detected_at) : '—'}
                    </p>
                    {alert.acknowledged && (
                      <span className="text-[10px] text-tm-profit">Ack'd</span>
                    )}
                  </div>
                </div>
              </div>
            ))}
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
