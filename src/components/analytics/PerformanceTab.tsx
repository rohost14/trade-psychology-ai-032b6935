import { useState, useEffect } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, ReferenceLine,
} from 'recharts';
import { BarChart3, ArrowUpDown, TrendingUp, TrendingDown } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { formatCurrency } from '@/lib/formatters';
import { api } from '@/lib/api';
import { useOrderAnalytics } from '@/hooks/useOrderAnalytics';
import AINarrativeCard from './AINarrativeCard';
import { useBroker } from '@/contexts/BrokerContext';
import OrderAnalyticsCard from '@/components/analytics/OrderAnalyticsCard';

interface PerformanceTabProps {
  days: number;
}

interface InstrumentPerf {
  symbol: string;
  trades: number;
  pnl: number;
  win_rate: number;
  avg_pnl: number;
  avg_duration_min: number;
}

interface DirectionPerf {
  trades: number;
  pnl: number;
  win_rate: number;
}

interface ProductPerf {
  trades: number;
  pnl: number;
  wins: number;
  losses: number;
  win_rate: number;
  avg_pnl: number;
}

interface HourPerf {
  hour: number;
  label: string;
  trades: number;
  pnl: number;
  win_rate: number;
}

interface DayPerf {
  day: number;
  name: string;
  trades: number;
  pnl: number;
  win_rate: number;
}

interface SizeBucket {
  bucket: string;
  trades: number;
  pnl: number;
  win_rate: number;
  avg_pnl: number;
}

interface PerformanceData {
  has_data: boolean;
  period_days: number;
  total_trades: number;
  by_instrument: InstrumentPerf[];
  by_direction: Record<string, DirectionPerf>;
  by_product: Record<string, ProductPerf>;
  by_hour: HourPerf[];
  by_day_of_week: DayPerf[];
  size_analysis: SizeBucket[];
}

type SortKey = 'symbol' | 'trades' | 'pnl' | 'win_rate' | 'avg_pnl';

export default function PerformanceTab({ days }: PerformanceTabProps) {
  const { account } = useBroker();
  const [data, setData] = useState<PerformanceData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [sortKey, setSortKey] = useState<SortKey>('pnl');
  const [sortAsc, setSortAsc] = useState(false);
  const [orderPeriod, setOrderPeriod] = useState(days);
  const { analytics: orderAnalytics, isLoading: orderLoading, refetch: refetchOrders } = useOrderAnalytics(account?.id, orderPeriod);

  useEffect(() => {
    let cancelled = false;
    const fetchData = async () => {
      setIsLoading(true);
      try {
        const res = await api.get('/api/analytics/performance', { params: { days } });
        if (!cancelled) setData(res.data);
      } catch (e) {
        console.error('Failed to fetch performance:', e);
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
        <Skeleton className="h-48 rounded-xl" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <Skeleton className="h-32 rounded-xl" />
          <Skeleton className="h-32 rounded-xl" />
        </div>
        <Skeleton className="h-56 rounded-xl" />
      </div>
    );
  }

  if (!data?.has_data) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[40vh] tm-card overflow-hidden">
        <BarChart3 className="h-10 w-10 text-muted-foreground/40 mb-3" />
        <p className="font-medium text-foreground">No performance data for this period</p>
        <p className="text-sm text-muted-foreground mt-1">Complete some trades to see analysis</p>
      </div>
    );
  }

  // Sort instruments
  const handleSort = (key: SortKey) => {
    if (sortKey === key) setSortAsc(!sortAsc);
    else { setSortKey(key); setSortAsc(false); }
  };

  const sortedInstruments = [...data.by_instrument].sort((a, b) => {
    const mul = sortAsc ? 1 : -1;
    if (sortKey === 'symbol') return mul * a.symbol.localeCompare(b.symbol);
    return mul * ((a[sortKey] ?? 0) - (b[sortKey] ?? 0));
  });

  // Find best/worst hour and day
  const bestHour = data.by_hour.length > 0 ? data.by_hour.reduce((a, b) => a.pnl > b.pnl ? a : b) : null;
  const worstHour = data.by_hour.length > 0 ? data.by_hour.reduce((a, b) => a.pnl < b.pnl ? a : b) : null;
  const bestDay = data.by_day_of_week.length > 0 ? data.by_day_of_week.reduce((a, b) => a.pnl > b.pnl ? a : b) : null;
  const worstDay = data.by_day_of_week.length > 0 ? data.by_day_of_week.reduce((a, b) => a.pnl < b.pnl ? a : b) : null;

  return (
    <div className="space-y-4">
      {/* AI Narrative */}
      <AINarrativeCard tab="performance" days={days} />

      {/* By Instrument */}
      <div className="tm-card overflow-hidden">
        <div className="px-4 py-3 border-b border-border flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-foreground">By Instrument</h3>
            <p className="text-xs text-muted-foreground">{data.by_instrument.length} instruments traded</p>
          </div>
          <p className="text-xs text-muted-foreground">{data.total_trades} total trades</p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-border bg-muted/30">
                {([
                  ['symbol', 'Symbol', 'left'],
                  ['trades', 'Trades', 'right'],
                  ['pnl', 'P&L', 'right'],
                  ['win_rate', 'Win%', 'right'],
                  ['avg_pnl', 'Avg P&L', 'right'],
                ] as [SortKey, string, string][]).map(([key, label, align]) => (
                  <th
                    key={key}
                    className={cn(
                      'px-4 py-2 text-[11px] font-medium uppercase tracking-wide text-muted-foreground cursor-pointer hover:text-foreground',
                      align === 'right' ? 'text-right' : 'text-left'
                    )}
                    onClick={() => handleSort(key)}
                  >
                    <span className="inline-flex items-center gap-1">
                      {label}
                      {sortKey === key && <ArrowUpDown className="h-3 w-3" />}
                    </span>
                  </th>
                ))}
                <th className="px-3 py-2 text-right text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Avg Dur</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {sortedInstruments.slice(0, 20).map((inst) => (
                <tr key={inst.symbol} className="hover:bg-muted/30">
                  <td className="px-4 py-2.5 text-sm font-medium text-foreground">{inst.symbol}</td>
                  <td className="px-4 py-2.5 text-right text-sm tabular-nums">{inst.trades}</td>
                  <td className={cn(
                    'px-4 py-2.5 text-right text-sm tabular-nums font-mono font-medium',
                    inst.pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss'
                  )}>
                    {inst.pnl >= 0 ? '+' : ''}{formatCurrency(inst.pnl)}
                  </td>
                  <td className={cn(
                    'px-4 py-2.5 text-right text-sm tabular-nums',
                    inst.win_rate >= 50 ? 'text-tm-profit' : 'text-tm-loss'
                  )}>
                    {inst.win_rate}%
                  </td>
                  <td className={cn(
                    'px-4 py-2.5 text-right text-sm tabular-nums font-mono',
                    inst.avg_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss'
                  )}>
                    {inst.avg_pnl >= 0 ? '+' : ''}{formatCurrency(inst.avg_pnl)}
                  </td>
                  <td className="px-3 py-2.5 text-right text-xs text-muted-foreground">
                    {formatDuration(inst.avg_duration_min)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* By Direction + By Product */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Direction */}
        {Object.entries(data.by_direction).map(([dir, stats]) => (
          <div key={dir} className="tm-card overflow-hidden">
            <div className={cn(
              'px-4 py-3 border-b border-border flex items-center gap-2',
              dir === 'LONG' ? 'bg-teal-50/50 dark:bg-teal-900/10' : 'bg-red-50/50 dark:bg-red-900/10'
            )}>
              {dir === 'LONG' ? <TrendingUp className="h-4 w-4 text-tm-profit" /> : <TrendingDown className="h-4 w-4 text-tm-loss" />}
              <h3 className="text-sm font-semibold text-foreground">{dir}</h3>
            </div>
            <div className="grid grid-cols-3 divide-x divide-border">
              <div className="px-4 py-3 text-center">
                <p className="text-xs text-muted-foreground">Trades</p>
                <p className="text-lg font-bold tabular-nums">{stats.trades}</p>
              </div>
              <div className="px-4 py-3 text-center">
                <p className="text-xs text-muted-foreground">P&L</p>
                <p className={cn(
                  'text-lg font-bold tabular-nums font-mono',
                  stats.pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss'
                )}>
                  {formatCurrency(stats.pnl)}
                </p>
              </div>
              <div className="px-4 py-3 text-center">
                <p className="text-xs text-muted-foreground">Win Rate</p>
                <p className={cn(
                  'text-lg font-bold tabular-nums',
                  stats.win_rate >= 50 ? 'text-tm-profit' : 'text-tm-loss'
                )}>
                  {stats.win_rate}%
                </p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* By Product Type (MIS vs NRML vs MTF) */}
      {Object.keys(data.by_product).length > 0 && (
        <div className="tm-card overflow-hidden">
          <div className="px-4 py-3 border-b border-border">
            <h3 className="text-sm font-semibold text-foreground">By Product Type</h3>
            <p className="text-xs text-muted-foreground">Intraday (MIS) vs Positional (NRML) performance</p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border bg-muted/30">
                  <th className="px-4 py-2 text-left text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Product</th>
                  <th className="px-3 py-2 text-right text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Trades</th>
                  <th className="px-3 py-2 text-right text-[11px] font-medium uppercase tracking-wide text-muted-foreground">W/L</th>
                  <th className="px-3 py-2 text-right text-[11px] font-medium uppercase tracking-wide text-muted-foreground">P&L</th>
                  <th className="px-3 py-2 text-right text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Win Rate</th>
                  <th className="px-3 py-2 text-right text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Avg P&L</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {Object.entries(data.by_product).map(([product, stats]) => (
                  <tr key={product} className="hover:bg-muted/30">
                    <td className="px-4 py-2.5 text-sm font-medium text-foreground">
                      {product}
                      <span className="text-xs text-muted-foreground ml-1.5">
                        {product === 'MIS' ? '(Intraday)' : product === 'NRML' ? '(Positional)' : product === 'MTF' ? '(Margin)' : ''}
                      </span>
                    </td>
                    <td className="px-3 py-2.5 text-right text-sm tabular-nums">{stats.trades}</td>
                    <td className="px-3 py-2.5 text-right text-sm tabular-nums text-muted-foreground">
                      <span className="text-green-600">{stats.wins}</span>
                      <span className="mx-0.5">/</span>
                      <span className="text-red-600">{stats.losses}</span>
                    </td>
                    <td className={cn(
                      'px-3 py-2.5 text-right text-sm tabular-nums font-mono font-medium',
                      stats.pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss'
                    )}>
                      {stats.pnl >= 0 ? '+' : ''}{formatCurrency(stats.pnl)}
                    </td>
                    <td className={cn(
                      'px-3 py-2.5 text-right text-sm tabular-nums',
                      stats.win_rate >= 50 ? 'text-tm-profit' : 'text-tm-loss'
                    )}>
                      {stats.win_rate}%
                    </td>
                    <td className={cn(
                      'px-3 py-2.5 text-right text-sm tabular-nums font-mono',
                      stats.avg_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss'
                    )}>
                      {stats.avg_pnl >= 0 ? '+' : ''}{formatCurrency(stats.avg_pnl)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* By Hour + By Day of Week */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* By Hour */}
        {data.by_hour.length > 0 && (
          <div className="tm-card overflow-hidden">
            <div className="px-4 py-3 border-b border-border flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-foreground">P&L by Hour</h3>
                <p className="text-xs text-muted-foreground">Entry time analysis (IST)</p>
              </div>
              {bestHour && worstHour && (
                <div className="text-right">
                  <p className="text-[10px] text-green-600">Best: {bestHour.label}</p>
                  <p className="text-[10px] text-red-600">Worst: {worstHour.label}</p>
                </div>
              )}
            </div>
            <div className="px-4 py-4">
              <div className="h-[220px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={data.by_hour}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" strokeOpacity={0.5} vertical={false} />
                    <XAxis
                      dataKey="label"
                      axisLine={false}
                      tickLine={false}
                      tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 10 }}
                    />
                    <YAxis
                      axisLine={false}
                      tickLine={false}
                      tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 10 }}
                      tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`}
                    />
                    <Tooltip content={<HourTooltip />} />
                    <ReferenceLine y={0} stroke="hsl(var(--border))" strokeWidth={1.5} />
                    <Bar dataKey="pnl" radius={[2, 2, 0, 0]}>
                      {data.by_hour.map((entry, i) => (
                        <Cell key={i} fill={entry.pnl >= 0 ? '#16A34A' : '#DC2626'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
            {/* Hour data table */}
            <div className="border-t border-border overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="bg-muted/30">
                    <th className="px-3 py-1.5 text-left text-[10px] font-medium uppercase tracking-wide text-muted-foreground">Hour</th>
                    <th className="px-3 py-1.5 text-right text-[10px] font-medium uppercase tracking-wide text-muted-foreground">Trades</th>
                    <th className="px-3 py-1.5 text-right text-[10px] font-medium uppercase tracking-wide text-muted-foreground">P&L</th>
                    <th className="px-3 py-1.5 text-right text-[10px] font-medium uppercase tracking-wide text-muted-foreground">Win%</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {data.by_hour.map((h) => (
                    <tr key={h.hour} className="hover:bg-muted/30">
                      <td className="px-3 py-1.5 text-xs font-medium text-foreground">{h.label}</td>
                      <td className="px-3 py-1.5 text-right text-xs tabular-nums">{h.trades}</td>
                      <td className={cn(
                        'px-3 py-1.5 text-right text-xs tabular-nums font-mono',
                        h.pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss'
                      )}>
                        {formatCurrency(h.pnl)}
                      </td>
                      <td className={cn(
                        'px-3 py-1.5 text-right text-xs tabular-nums',
                        h.win_rate >= 50 ? 'text-tm-profit' : 'text-tm-loss'
                      )}>
                        {h.win_rate}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* By Day of Week */}
        {data.by_day_of_week.length > 0 && (
          <div className="tm-card overflow-hidden">
            <div className="px-4 py-3 border-b border-border flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-foreground">P&L by Day</h3>
                <p className="text-xs text-muted-foreground">Day of week analysis</p>
              </div>
              {bestDay && worstDay && (
                <div className="text-right">
                  <p className="text-[10px] text-green-600">Best: {bestDay.name.slice(0, 3)}</p>
                  <p className="text-[10px] text-red-600">Worst: {worstDay.name.slice(0, 3)}</p>
                </div>
              )}
            </div>
            <div className="px-4 py-4">
              <div className="h-[220px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={data.by_day_of_week}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" strokeOpacity={0.5} vertical={false} />
                    <XAxis
                      dataKey="name"
                      axisLine={false}
                      tickLine={false}
                      tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 10 }}
                      tickFormatter={(v) => v.slice(0, 3)}
                    />
                    <YAxis
                      axisLine={false}
                      tickLine={false}
                      tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 10 }}
                      tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`}
                    />
                    <Tooltip content={<DayTooltip />} />
                    <ReferenceLine y={0} stroke="hsl(var(--border))" strokeWidth={1.5} />
                    <Bar dataKey="pnl" radius={[2, 2, 0, 0]}>
                      {data.by_day_of_week.map((entry, i) => (
                        <Cell key={i} fill={entry.pnl >= 0 ? '#16A34A' : '#DC2626'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
            {/* Day data table */}
            <div className="border-t border-border overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="bg-muted/30">
                    <th className="px-3 py-1.5 text-left text-[10px] font-medium uppercase tracking-wide text-muted-foreground">Day</th>
                    <th className="px-3 py-1.5 text-right text-[10px] font-medium uppercase tracking-wide text-muted-foreground">Trades</th>
                    <th className="px-3 py-1.5 text-right text-[10px] font-medium uppercase tracking-wide text-muted-foreground">P&L</th>
                    <th className="px-3 py-1.5 text-right text-[10px] font-medium uppercase tracking-wide text-muted-foreground">Win%</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {data.by_day_of_week.map((d) => (
                    <tr key={d.day} className="hover:bg-muted/30">
                      <td className="px-3 py-1.5 text-xs font-medium text-foreground">{d.name}</td>
                      <td className="px-3 py-1.5 text-right text-xs tabular-nums">{d.trades}</td>
                      <td className={cn(
                        'px-3 py-1.5 text-right text-xs tabular-nums font-mono',
                        d.pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss'
                      )}>
                        {formatCurrency(d.pnl)}
                      </td>
                      <td className={cn(
                        'px-3 py-1.5 text-right text-xs tabular-nums',
                        d.win_rate >= 50 ? 'text-tm-profit' : 'text-tm-loss'
                      )}>
                        {d.win_rate}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* Position Size Analysis */}
      {data.size_analysis.length > 0 && (
        <div className="tm-card overflow-hidden">
          <div className="px-4 py-3 border-b border-border">
            <h3 className="text-sm font-semibold text-foreground">Position Size Analysis</h3>
            <p className="text-xs text-muted-foreground">How position sizing affects your outcomes</p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border bg-muted/30">
                  <th className="px-4 py-2 text-left text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Size Bucket</th>
                  <th className="px-3 py-2 text-right text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Trades</th>
                  <th className="px-3 py-2 text-right text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Total P&L</th>
                  <th className="px-3 py-2 text-right text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Win Rate</th>
                  <th className="px-3 py-2 text-right text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Avg P&L</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data.size_analysis.map((bucket) => (
                  <tr key={bucket.bucket} className="hover:bg-muted/30">
                    <td className="px-4 py-2.5 text-sm font-medium text-foreground">{bucket.bucket}</td>
                    <td className="px-3 py-2.5 text-right text-sm tabular-nums">{bucket.trades}</td>
                    <td className={cn(
                      'px-3 py-2.5 text-right text-sm tabular-nums font-mono font-medium',
                      bucket.pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss'
                    )}>
                      {bucket.pnl >= 0 ? '+' : ''}{formatCurrency(bucket.pnl)}
                    </td>
                    <td className={cn(
                      'px-3 py-2.5 text-right text-sm tabular-nums',
                      bucket.win_rate >= 50 ? 'text-tm-profit' : 'text-tm-loss'
                    )}>
                      {bucket.win_rate}%
                    </td>
                    <td className={cn(
                      'px-3 py-2.5 text-right text-sm tabular-nums font-mono',
                      bucket.avg_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss'
                    )}>
                      {bucket.avg_pnl >= 0 ? '+' : ''}{formatCurrency(bucket.avg_pnl)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {/* Size insight */}
          {data.size_analysis.length > 1 && (() => {
            const best = data.size_analysis.reduce((a, b) => a.avg_pnl > b.avg_pnl ? a : b);
            return best.avg_pnl > 0 ? (
              <div className="border-t border-border px-4 py-2.5 bg-teal-50/40 dark:bg-teal-900/10">
                <p className="text-xs text-tm-brand">
                  You perform best with <span className="font-medium">{best.bucket}</span> positions
                  ({best.win_rate}% win rate, avg {formatCurrency(best.avg_pnl)}/trade)
                </p>
              </div>
            ) : null;
          })()}
        </div>
      )}

      {/* Order Analytics */}
      <OrderAnalyticsCard
        analytics={orderAnalytics}
        isLoading={orderLoading}
        onPeriodChange={(d) => {
          setOrderPeriod(d);
          refetchOrders(d);
        }}
        selectedPeriod={orderPeriod}
      />
    </div>
  );
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatDuration(minutes: number): string {
  if (!minutes) return '—';
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  if (hours < 24) return mins > 0 ? `${hours}h ${mins}m` : `${hours}h`;
  const days = Math.floor(hours / 24);
  return `${days}d`;
}

function HourTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="bg-popover border border-border rounded-lg p-3 shadow-lg text-sm">
      <p className="font-medium text-foreground">{d.label} IST</p>
      <p className={cn('tabular-nums font-mono', d.pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
        {d.pnl >= 0 ? '+' : ''}{formatCurrency(d.pnl)}
      </p>
      <p className="text-xs text-muted-foreground">{d.trades} trades &middot; {d.win_rate}% WR</p>
    </div>
  );
}

function DayTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="bg-popover border border-border rounded-lg p-3 shadow-lg text-sm">
      <p className="font-medium text-foreground">{d.name}</p>
      <p className={cn('tabular-nums font-mono', d.pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
        {d.pnl >= 0 ? '+' : ''}{formatCurrency(d.pnl)}
      </p>
      <p className="text-xs text-muted-foreground">{d.trades} trades &middot; {d.win_rate}% WR</p>
    </div>
  );
}
