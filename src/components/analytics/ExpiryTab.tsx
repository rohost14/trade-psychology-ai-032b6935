import { useState, useEffect } from 'react';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { api } from '@/lib/api';
import { formatCurrencyWithSign } from '@/lib/formatters';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from 'recharts';

interface BucketStats {
  trade_count: number;
  win_rate: number;
  avg_pnl: number;
  total_pnl: number;
}

interface HourBucket {
  hour: number;
  label: string;
  expiry_count: number;
  expiry_avg_pnl: number;
  non_expiry_count: number;
  non_expiry_avg_pnl: number;
}

interface ExpiryData {
  has_data: boolean;
  period_days: number;
  expiry: BucketStats;
  non_expiry: BucketStats;
  by_hour: HourBucket[];
  worst_expiry_trades: { pnl: number; hour: number; symbol: string }[];
}

function StatCard({ label, stats, accent }: { label: string; stats: BucketStats; accent: string }) {
  return (
    <div className={cn('tm-card overflow-hidden')}>
      <div className="px-5 py-3.5 border-b border-border">
        <span className={cn('text-xs font-semibold uppercase tracking-wide', accent)}>{label}</span>
      </div>
      <div className="p-5 grid grid-cols-2 gap-4">
        <div>
          <p className="text-xs text-muted-foreground mb-1">Trades</p>
          <p className="t-mono-lg text-foreground">{stats.trade_count}</p>
        </div>
        <div>
          <p className="text-xs text-muted-foreground mb-1">Win Rate</p>
          <p className={cn('t-mono-lg', stats.win_rate >= 50 ? 'text-tm-profit' : 'text-tm-loss')}>
            {stats.win_rate}%
          </p>
        </div>
        <div>
          <p className="text-xs text-muted-foreground mb-1">Avg P&L</p>
          <p className={cn('t-mono-lg', stats.avg_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
            {formatCurrencyWithSign(stats.avg_pnl)}
          </p>
        </div>
        <div>
          <p className="text-xs text-muted-foreground mb-1">Total P&L</p>
          <p className={cn('t-mono-lg', stats.total_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
            {formatCurrencyWithSign(stats.total_pnl)}
          </p>
        </div>
      </div>
    </div>
  );
}

function HourTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-card border border-border rounded-md px-3 py-2 text-xs shadow-md space-y-1">
      <p className="font-semibold text-foreground">{label}</p>
      {payload.map((p: any) => (
        <p key={p.dataKey} style={{ color: p.color }}>
          {p.name}: {formatCurrencyWithSign(p.value)}
        </p>
      ))}
    </div>
  );
}

export default function ExpiryTab({ days }: { days: number }) {
  const [data, setData]       = useState<ExpiryData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api.get('/api/analytics/expiry-pattern', { params: { days } })
      .then(r => setData(r.data))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [days]);

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Skeleton className="h-44 rounded-xl" />
          <Skeleton className="h-44 rounded-xl" />
        </div>
        <Skeleton className="h-64 rounded-xl" />
      </div>
    );
  }

  if (!data?.has_data) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <p className="text-sm font-medium text-foreground mb-1">No expiry data yet</p>
        <p className="text-xs text-muted-foreground max-w-xs">
          After {days} days of trading, expiry vs non-expiry breakdown will appear here.
        </p>
      </div>
    );
  }

  const expDelta = data.expiry.win_rate - data.non_expiry.win_rate;
  const expAvgDelta = data.expiry.avg_pnl - data.non_expiry.avg_pnl;

  return (
    <div className="space-y-5">
      {/* Insight banner */}
      {data.expiry.trade_count >= 3 && (
        <div className={cn(
          'rounded-xl px-4 py-3 text-sm border',
          expDelta < -5
            ? 'bg-red-500/10 border-red-500/20 text-red-600 dark:text-red-400'
            : expDelta > 5
              ? 'bg-green-500/10 border-green-500/20 text-green-600 dark:text-green-400'
              : 'bg-muted border-border text-muted-foreground'
        )}>
          {expDelta < -5
            ? `Expiry days hurt: win rate drops ${Math.abs(expDelta).toFixed(1)}% vs non-expiry (avg P&L ${formatCurrencyWithSign(expAvgDelta)} worse).`
            : expDelta > 5
              ? `Expiry edge: win rate improves ${expDelta.toFixed(1)}% vs non-expiry (avg P&L ${formatCurrencyWithSign(expAvgDelta)} better).`
              : `Expiry days show similar performance to non-expiry days.`
          }
        </div>
      )}

      {/* Stat cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <StatCard label="Expiry Days" stats={data.expiry} accent="text-tm-obs" />
        <StatCard label="Non-Expiry Days" stats={data.non_expiry} accent="text-tm-brand" />
      </div>

      {/* Intraday breakdown by hour */}
      {data.by_hour.length > 0 && (
        <div className="tm-card overflow-hidden">
          <div className="px-5 py-3.5 border-b border-border">
            <p className="text-sm font-semibold text-foreground">Avg P&L by Hour</p>
            <p className="text-xs text-muted-foreground mt-0.5">Expiry vs non-expiry, intraday</p>
          </div>
          <div className="p-5">
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={data.by_hour} barGap={4}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} tickFormatter={v => `₹${v}`} />
                <Tooltip content={<HourTooltip />} />
                <ReferenceLine y={0} stroke="hsl(var(--border))" />
                <Bar dataKey="expiry_avg_pnl" name="Expiry" fill="#D97706" radius={[3,3,0,0]} />
                <Bar dataKey="non_expiry_avg_pnl" name="Non-Expiry" fill="#0F766E" radius={[3,3,0,0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Worst expiry trades */}
      {data.worst_expiry_trades.length > 0 && (
        <div className="tm-card overflow-hidden">
          <div className="px-5 py-3.5 border-b border-border">
            <p className="text-sm font-semibold text-foreground">Worst Expiry Trades</p>
          </div>
          <div className="divide-y divide-border">
            {data.worst_expiry_trades.map((t, i) => (
              <div key={i} className="px-5 py-3 flex items-center justify-between text-sm">
                <span className="text-muted-foreground font-mono text-xs">
                  {t.symbol || '—'} · {t.hour != null ? `${t.hour}:xx` : '—'}
                </span>
                <span className={cn('font-mono font-semibold', t.pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
                  {formatCurrencyWithSign(t.pnl)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
