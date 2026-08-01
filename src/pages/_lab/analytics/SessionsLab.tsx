/**
 * DESIGN LAB — SessionsTab with the P&L calendar removed, because the calendar
 * has been promoted to the Behaviour tab. Everything else is the original.
 */
import { useState, useEffect } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, ReferenceLine,
} from 'recharts';
import { RefreshCw, AlertTriangle, Clock } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import ErrorState from '@/components/ErrorState';
import { cn } from '@/lib/utils';
import { formatCurrencyWithSign, formatAxisCurrency } from '@/lib/formatters';
import type { ChartTooltipProps } from '@/lib/chartTooltip';
import { api } from '@/lib/api';

interface SessionsTabProps { days: number }

interface OverviewData {
  has_data: boolean;
  daily_pnl: { date: string; pnl: number; trades: number; win_rate: number }[];
}

interface ExpiryWeekDow {
  day: string;
  trade_count: number;
  win_rate: number;
  avg_pnl: number;
  total_pnl: number;
}

interface ExpiryData {
  has_data: boolean;
  period_days: number;
  expiry: { trade_count: number; win_rate: number; avg_pnl: number; total_pnl: number };
  non_expiry: { trade_count: number; win_rate: number; avg_pnl: number; total_pnl: number };
  by_hour: { hour: number; label: string; expiry_count: number; expiry_avg_pnl: number; non_expiry_count: number; non_expiry_avg_pnl: number }[];
  worst_expiry_trades: { symbol: string; pnl: number; hour: number }[];
  by_expiry_week_dow?: ExpiryWeekDow[];
}

// Shape of GET /api/analytics/conditional-performance
interface Condition {
  key: string;
  label: string;
  win_rate: number;
  avg_pnl: number;
  trade_count: number;
  delta_vs_baseline: number;
  narrative: string;
}

interface ConditionalData {
  has_data: boolean;
  total_trades: number;
  baseline_win_rate: number;
  baseline_avg_pnl: number;
  conditions: Condition[];
}

function pnlColorClass(pnl: number) {
  if (pnl > 0) return 'text-tm-profit';
  if (pnl < 0) return 'text-tm-loss';
  return 'text-muted-foreground';
}


const DOW_ORDER = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'];



function DowTooltip({ active, payload }: ChartTooltipProps<ExpiryWeekDow>) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="bg-popover border border-border rounded-lg px-3 py-2 shadow-lg text-sm">
      <p className="font-medium mb-1">{d.day} (expiry weeks)</p>
      <p className={cn('font-mono tabular-nums', d.avg_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
        {formatCurrencyWithSign(Math.round(d.avg_pnl))} avg
      </p>
      <p className="text-xs text-muted-foreground">{d.trade_count} trades · {d.win_rate}% WR</p>
    </div>
  );
}

export default function SessionsTab({ days }: SessionsTabProps) {
  const [overview, setOverview]   = useState<OverviewData | null>(null);
  const [expiry, setExpiry]       = useState<ExpiryData | null>(null);
  const [conditional, setCond]    = useState<ConditionalData | null>(null);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState<unknown>(null);
  const [retry, setRetry]         = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.allSettled([
      api.get('/api/analytics/overview',                { params: { days: 90 } }),
      api.get('/api/analytics/expiry-pattern',          { params: { days } }),
      api.get('/api/analytics/conditional-performance', { params: { days } }),
    ]).then(([ov, ex, co]) => {
      if (cancelled) return;
      if (ov.status === 'fulfilled') setOverview(ov.value.data);
      if (ex.status === 'fulfilled') setExpiry(ex.value.data);
      if (co.status === 'fulfilled') setCond(co.value.data);
      if (ov.status === 'rejected') setError(ov.reason);
    }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [days, retry]);

  if (loading) return (
    <div className="space-y-4 animate-pulse">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Skeleton className="h-[220px] rounded-lg" />
        <Skeleton className="h-[220px] rounded-lg" />
        <Skeleton className="h-[220px] rounded-lg" />
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Skeleton className="h-28 rounded-lg" />
        <Skeleton className="h-28 rounded-lg" />
      </div>
      <Skeleton className="h-[200px] rounded-lg" />
      <Skeleton className="h-[180px] rounded-lg" />
    </div>
  );

  if (error) return <ErrorState error={error} onRetry={() => setRetry(r => r + 1)} />;
  // conditional-performance returns a `conditions` ARRAY keyed by `key` —
  // pick the two session-relevant ones (absent when below the sample gate).
  const conditions = conditional?.has_data ? (conditional.conditions ?? []) : [];
  const first30    = conditions.find(c => c.key === 'first_30min') ?? null;
  const expiryDay  = conditions.find(c => c.key === 'expiry_day') ?? null;
  const baselineWR = conditional?.baseline_win_rate ?? null;

  // Expiry week DOW bar data — sort by Mon→Fri
  const dowRaw  = (expiry?.by_expiry_week_dow ?? []).filter(d => DOW_ORDER.includes(d.day));
  dowRaw.sort((a, b) => DOW_ORDER.indexOf(a.day) - DOW_ORDER.indexOf(b.day));
  const bestDow  = [...dowRaw].sort((a, b) => b.avg_pnl - a.avg_pnl)[0];
  const worstDow = [...dowRaw].sort((a, b) => a.avg_pnl - b.avg_pnl)[0];

  // Expiry hourly avg pnl (for personalized insight)
  const bestExpiryHour = expiry?.by_hour
    ? [...expiry.by_hour].filter(h => h.expiry_count > 0).sort((a, b) => b.expiry_avg_pnl - a.expiry_avg_pnl)[0]
    : null;

  return (
    <div className="space-y-5">

      {/* The P&L calendar was here. It is now the second block on Behaviour --
          see _lab/analytics/PnlCalendar.tsx. Rendering it in both places would
          recompute the same story twice, which the page-ownership rule forbids. */}
      {/* Opening Trap + Expiry Day */}
      {(first30 || expiryDay) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

          {first30 && first30.trade_count > 0 && (
            <div className={cn(
              'tm-card overflow-hidden border-l-4',
              first30.delta_vs_baseline < -5 ? 'border-l-tm-loss' : 'border-l-tm-profit',
            )}>
              <div className="px-4 pt-4 pb-1 flex items-center gap-2">
                <Clock className="h-4 w-4 text-muted-foreground" />
                <p className="text-xs text-muted-foreground uppercase tracking-wide">Opening 30 Minutes (9:15–9:45)</p>
              </div>
              <div className="px-4 pb-4">
                <div className="flex items-end gap-2 my-2">
                  <span className={cn(
                    'text-4xl font-mono font-black tabular-nums',
                    first30.delta_vs_baseline >= 0 ? 'text-tm-profit' : 'text-tm-loss',
                  )}>
                    {Math.round(first30.win_rate)}%
                  </span>
                  <span className="text-sm text-muted-foreground pb-1">win rate</span>
                </div>
                {baselineWR != null && (
                  <p className={cn(
                    'text-[12px] font-medium',
                    first30.delta_vs_baseline < 0 ? 'text-tm-loss' : 'text-tm-profit',
                  )}>
                    {first30.delta_vs_baseline > 0 ? '+' : ''}{first30.delta_vs_baseline.toFixed(1)}% vs your overall ({Math.round(baselineWR)}%)
                  </p>
                )}
                <p className="text-[11px] text-muted-foreground mt-2">
                  {first30.trade_count} trades · {formatCurrencyWithSign(Math.round(first30.avg_pnl))} avg P&L
                </p>
                {first30.delta_vs_baseline < -5 && (
                  <p className="text-[11px] text-tm-loss mt-2">
                    Opening trap: you underperform in the first 30 minutes. Consider waiting for the first candle to close.
                  </p>
                )}
              </div>
            </div>
          )}

          {expiryDay && expiryDay.trade_count > 0 && (
            <div className={cn(
              'tm-card overflow-hidden border-l-4',
              expiryDay.delta_vs_baseline < -5 ? 'border-l-tm-loss' : 'border-l-tm-profit',
            )}>
              <div className="px-4 pt-4 pb-1 flex items-center gap-2">
                <Clock className="h-4 w-4 text-muted-foreground" />
                <p className="text-xs text-muted-foreground uppercase tracking-wide">Expiry Day Trades</p>
              </div>
              <div className="px-4 pb-4">
                <div className="flex items-end gap-2 my-2">
                  <span className={cn(
                    'text-4xl font-mono font-black tabular-nums',
                    expiryDay.delta_vs_baseline >= 0 ? 'text-tm-profit' : 'text-tm-loss',
                  )}>
                    {Math.round(expiryDay.win_rate)}%
                  </span>
                  <span className="text-sm text-muted-foreground pb-1">win rate</span>
                </div>
                {baselineWR != null && (
                  <p className={cn(
                    'text-[12px] font-medium',
                    expiryDay.delta_vs_baseline < 0 ? 'text-tm-loss' : 'text-tm-profit',
                  )}>
                    {expiryDay.delta_vs_baseline > 0 ? '+' : ''}{expiryDay.delta_vs_baseline.toFixed(1)}% vs your overall ({Math.round(baselineWR)}%)
                  </p>
                )}
                <p className="text-[11px] text-muted-foreground mt-2">
                  {expiryDay.trade_count} trades · {formatCurrencyWithSign(Math.round(expiryDay.avg_pnl))} avg P&L
                </p>
              </div>
            </div>
          )}

        </div>
      )}

      {/* Expiry vs Non-Expiry Comparison */}
      {expiry?.has_data && (
        <div className="tm-card overflow-hidden">
          <div className="px-5 py-3.5 border-b border-border">
            <p className="font-semibold text-sm">Expiry vs Non-Expiry Performance</p>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 divide-y sm:divide-y-0 sm:divide-x divide-border">
            {[
              { label: 'Expiry Days', s: expiry.expiry },
              { label: 'Non-Expiry Days', s: expiry.non_expiry },
            ].map(({ label, s }) => (
              <div key={label} className="px-5 py-4">
                <p className="text-[11px] text-muted-foreground uppercase tracking-wide mb-2">{label}</p>
                <p className="text-2xl font-mono font-bold tabular-nums text-foreground">{s.trade_count}</p>
                <p className="text-[12px] text-muted-foreground mt-0.5">trades</p>
                <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1">
                  <div>
                    <p className="text-[10px] text-muted-foreground">Win rate</p>
                    <p className={cn('text-sm font-mono font-semibold', s.win_rate >= 50 ? 'text-tm-profit' : 'text-tm-loss')}>
                      {s.win_rate}%
                    </p>
                  </div>
                  <div>
                    <p className="text-[10px] text-muted-foreground">Avg P&L</p>
                    <p className={cn('text-sm font-mono font-semibold', s.avg_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
                      {formatCurrencyWithSign(Math.round(s.avg_pnl))}
                    </p>
                  </div>
                  <div>
                    <p className="text-[10px] text-muted-foreground">Total P&L</p>
                    <p className={cn('text-sm font-mono font-semibold', s.total_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
                      {formatCurrencyWithSign(Math.round(s.total_pnl))}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Hourly breakdown on expiry days */}
          {expiry.by_hour && expiry.by_hour.length > 0 && (
            <div className="border-t border-border px-5 py-3">
              <p className="text-[11px] text-muted-foreground mb-2">Expiry vs non-expiry by hour</p>
              <div className="space-y-1.5">
                {expiry.by_hour.map(h => (
                  <div key={h.hour} className="flex items-center gap-2 text-[11px]">
                    <span className="w-10 text-muted-foreground font-mono shrink-0">
                      {String(h.hour).padStart(2,'0')}:00
                    </span>
                    <div className="flex-1 grid grid-cols-2 gap-2">
                      <div className="flex items-center gap-1">
                        <div className="w-1.5 h-1.5 rounded-full bg-tm-brand shrink-0" />
                        <span className={cn('font-mono', h.expiry_avg_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
                          {formatCurrencyWithSign(Math.round(h.expiry_avg_pnl))}
                        </span>
                        <span className="text-muted-foreground">({h.expiry_count})</span>
                      </div>
                      <div className="flex items-center gap-1">
                        <div className="w-1.5 h-1.5 rounded-full bg-muted-foreground/40 shrink-0" />
                        <span className={cn('font-mono', h.non_expiry_avg_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
                          {formatCurrencyWithSign(Math.round(h.non_expiry_avg_pnl))}
                        </span>
                        <span className="text-muted-foreground">({h.non_expiry_count})</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
              <div className="flex items-center gap-4 mt-2 text-[10px] text-muted-foreground">
                <div className="flex items-center gap-1"><div className="w-1.5 h-1.5 rounded-full bg-tm-brand" /> Expiry</div>
                <div className="flex items-center gap-1"><div className="w-1.5 h-1.5 rounded-full bg-muted-foreground/40" /> Non-expiry</div>
              </div>
            </div>
          )}

          <p className="px-5 pb-3.5 text-[11px] text-muted-foreground">
            {expiry.expiry.avg_pnl < expiry.non_expiry.avg_pnl
              ? `You underperform on expiry days by ${formatCurrencyWithSign(Math.round(expiry.non_expiry.avg_pnl - expiry.expiry.avg_pnl))} per trade. Consider reducing size on expiry.`
              : `You perform better on expiry days than non-expiry days. Your edge is stronger near settlement.`
            }
          </p>
        </div>
      )}

      {/* Expiry Week DOW Breakdown */}
      {dowRaw.length > 0 && (
        <div className="tm-card overflow-hidden">
          <div className="px-5 py-3.5 border-b border-border">
            <p className="font-semibold text-sm">Expiry Week by Day</p>
          </div>
          <p className="px-5 pt-3 text-[11px] text-muted-foreground">
            All trades taken during expiry weeks, broken down by weekday. Mon–Wed is pre-theta, Thu is settlement.
          </p>
          <div className="p-4">
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={dowRaw} margin={{ top: 4, right: 4, left: -16, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" vertical={false} />
                <XAxis dataKey="day" tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fontSize: 10 }} tickLine={false} axisLine={false} width={52} tickFormatter={formatAxisCurrency} />
                <Tooltip content={<DowTooltip />} />
                <ReferenceLine y={0} stroke="rgba(0,0,0,0.15)" />
                <Bar dataKey="avg_pnl" radius={[3, 3, 0, 0]} maxBarSize={44}>
                  {dowRaw.map((d, i) => (
                    <Cell key={i} fill={d.avg_pnl >= 0 ? '#16a34a' : '#dc2626'} opacity={0.8} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <p className="px-5 pb-3.5 text-[11px] text-muted-foreground">
            {bestDow && worstDow
              ? `Your edge during expiry weeks is strongest on ${bestDow.day} (${formatCurrencyWithSign(Math.round(bestDow.avg_pnl))} avg). Weakest on ${worstDow.day} (${formatCurrencyWithSign(Math.round(worstDow.avg_pnl))} avg).`
              : 'Day-by-day breakdown of expiry week performance.'}
            {bestExpiryHour && ` Best expiry hour: ${String(bestExpiryHour.hour).padStart(2,'0')}:00.`}
          </p>
        </div>
      )}

    </div>
  );
}
