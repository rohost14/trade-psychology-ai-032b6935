import { useState, useEffect } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, ReferenceLine,
} from 'recharts';
import { Skeleton } from '@/components/ui/skeleton';
import { Loader2, BarChart3, Clock } from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatCurrencyWithSign } from '@/lib/formatters';
import { api } from '@/lib/api';
import { useOrderAnalytics } from '@/hooks/useOrderAnalytics';
import { useBroker } from '@/contexts/BrokerContext';
import OrderAnalyticsCard from '@/components/analytics/OrderAnalyticsCard';

interface TimingTabProps {
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

interface PerformanceData {
  has_data: boolean;
  period_days: number;
  total_trades: number;
  by_instrument: InstrumentPerf[];
  by_direction: Record<string, { trades: number; pnl: number; win_rate: number }>;
  by_product: Record<string, { trades: number; pnl: number; wins: number; losses: number; win_rate: number; avg_pnl: number }>;
  by_hour: HourPerf[];
  by_day_of_week: DayPerf[];
  size_analysis: { bucket: string; trades: number; pnl: number; win_rate: number; avg_pnl: number }[];
}

interface HeatmapCell {
  hour: number;
  day: number;
  trades: number;
  avg_pnl: number;
  win_rate: number;
}

interface HeatmapData {
  has_data: boolean;
  cells: HeatmapCell[];
}

// ─── Heatmap Grid ─────────────────────────────────────────────────────────────

function HeatmapGrid({ days }: { days: number }) {
  const [data, setData] = useState<HeatmapData | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setIsLoading(true);
      try {
        const res = await api.get('/api/analytics/timing-heatmap', { params: { days } });
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

  const hours = [9, 10, 11, 12, 13, 14, 15];
  const daysArr = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'];

  const cellMap = new Map(data.cells.map((c) => [`${c.hour}-${c.day}`, c]));
  const maxAbs = Math.max(...data.cells.map((c) => Math.abs(c.avg_pnl)), 1);

  const getCellStyle = (cell: HeatmapCell | undefined): React.CSSProperties => {
    if (!cell || cell.trades === 0) return {};
    const intensity = Math.min(Math.abs(cell.avg_pnl) / maxAbs, 1);
    const alpha = 0.15 + intensity * 0.65;
    const color = cell.avg_pnl > 0
      ? `rgba(34, 197, 94, ${alpha})`
      : `rgba(239, 68, 68, ${alpha})`;
    return { backgroundColor: color };
  };

  return (
    <div className="tm-card overflow-hidden">
      <div className="px-5 py-4 border-b border-border flex items-center gap-2">
        <Clock className="h-4 w-4 text-muted-foreground" />
        <div>
          <p className="tm-label">Hour × Day Performance</p>
          <p className="text-xs text-muted-foreground mt-0.5">Average P&L by entry time (IST)</p>
        </div>
      </div>
      <div className="px-5 py-4 overflow-x-auto">
        <table className="w-full border-collapse">
          <thead>
            <tr>
              <th className="text-xs text-muted-foreground w-12 text-left pb-2">Hour</th>
              {daysArr.map((d) => (
                <th key={d} className="text-xs text-muted-foreground text-center pb-2 w-20">{d}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {hours.map((h) => (
              <tr key={h}>
                <td className="text-xs text-muted-foreground py-1 pr-2">{h}:00</td>
                {[0, 1, 2, 3, 4].map((d) => {
                  const cell = cellMap.get(`${h}-${d}`);
                  return (
                    <td key={d} className="p-0.5">
                      <div
                        className="rounded h-14 w-full flex flex-col items-center justify-center text-center cursor-default transition-all hover:opacity-80"
                        style={getCellStyle(cell)}
                        title={
                          cell
                            ? `${cell.trades} trades, WR ${cell.win_rate}%, Avg ₹${cell.avg_pnl}`
                            : 'No trades'
                        }
                      >
                        {cell && cell.trades > 0 ? (
                          <>
                            <span className="text-xs font-mono font-semibold leading-none">
                              {cell.avg_pnl >= 0 ? '+' : ''}₹{(cell.avg_pnl / 1000).toFixed(1)}k
                            </span>
                            <span className="text-[10px] text-muted-foreground leading-none mt-0.5">
                              {cell.win_rate}%
                            </span>
                          </>
                        ) : (
                          <span className="text-[9px] text-muted-foreground/40">—</span>
                        )}
                      </div>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
        <div className="flex items-center gap-3 mt-3 text-[10px] text-muted-foreground">
          <span className="flex items-center gap-1">
            <span className="w-3 h-3 rounded bg-green-500/60" />
            Profitable
          </span>
          <span className="flex items-center gap-1">
            <span className="w-3 h-3 rounded bg-red-500/60" />
            Loss-making
          </span>
          <span className="flex items-center gap-1">
            <span className="w-3 h-3 rounded bg-muted/20 border border-border" />
            No trades
          </span>
        </div>
      </div>
    </div>
  );
}

// ─── Main Tab ─────────────────────────────────────────────────────────────────

export default function TimingTab({ days }: TimingTabProps) {
  const { account } = useBroker();
  const [data, setData] = useState<PerformanceData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
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
      <div className="space-y-4">
        <Skeleton className="h-64 rounded-lg" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[1,2,3,4].map(i => <Skeleton key={i} className="h-20 rounded-lg" />)}
        </div>
        <Skeleton className="h-48 rounded-lg" />
      </div>
    );
  }

  if (!data?.has_data) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[40vh] bg-card rounded-lg border border-border">
        <BarChart3 className="h-10 w-10 text-muted-foreground/40 mb-3" />
        <p className="font-medium text-foreground">No performance data for this period</p>
        <p className="text-sm text-muted-foreground mt-1">Complete some trades to see analysis</p>
      </div>
    );
  }

  const bestHour = data.by_hour.length > 0 ? data.by_hour.reduce((a, b) => a.pnl > b.pnl ? a : b) : null;
  const worstHour = data.by_hour.length > 0 ? data.by_hour.reduce((a, b) => a.pnl < b.pnl ? a : b) : null;
  const bestDay = data.by_day_of_week.length > 0 ? data.by_day_of_week.reduce((a, b) => a.pnl > b.pnl ? a : b) : null;
  const worstDay = data.by_day_of_week.length > 0 ? data.by_day_of_week.reduce((a, b) => a.pnl < b.pnl ? a : b) : null;

  const sortedInstruments = [...data.by_instrument].sort((a, b) => b.pnl - a.pnl);

  return (
    <div className="space-y-5 animate-fade-in">
      {/* Heatmap — hero section */}
      <HeatmapGrid days={days} />

      {/* By Hour + By Day — horizontal bar charts side by side */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {data.by_hour.length > 0 && (
          <div className="tm-card overflow-hidden">
            <div className="px-5 py-4 border-b border-border flex items-center justify-between">
              <p className="tm-label">By Hour (IST)</p>
              {bestHour && worstHour && (
                <div className="text-right">
                  <p className="text-[10px] text-tm-profit">Best: {bestHour.label}</p>
                  <p className="text-[10px] text-tm-loss">Worst: {worstHour.label}</p>
                </div>
              )}
            </div>
            <div className="px-4 py-4">
              <div className="h-[280px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={data.by_hour} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" strokeOpacity={0.5} vertical={true} horizontal={false} />
                    <XAxis
                      type="number"
                      axisLine={false}
                      tickLine={false}
                      tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 10 }}
                      tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`}
                    />
                    <YAxis
                      dataKey="label"
                      type="category"
                      axisLine={false}
                      tickLine={false}
                      tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 10 }}
                      width={40}
                    />
                    <Tooltip content={<HourTooltip />} />
                    <ReferenceLine x={0} stroke="hsl(var(--border))" strokeWidth={1.5} />
                    <Bar dataKey="pnl" radius={[0, 3, 3, 0]}>
                      {data.by_hour.map((entry, i) => (
                        <Cell key={i} fill={entry.pnl >= 0 ? '#16A34A' : '#DC2626'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        )}

        {data.by_day_of_week.length > 0 && (
          <div className="tm-card overflow-hidden">
            <div className="px-5 py-4 border-b border-border flex items-center justify-between">
              <p className="tm-label">By Day of Week</p>
              {bestDay && worstDay && (
                <div className="text-right">
                  <p className="text-[10px] text-tm-profit">Best: {bestDay.name.slice(0, 3)}</p>
                  <p className="text-[10px] text-tm-loss">Worst: {worstDay.name.slice(0, 3)}</p>
                </div>
              )}
            </div>
            <div className="px-4 py-4">
              <div className="h-[280px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={data.by_day_of_week} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" strokeOpacity={0.5} vertical={true} horizontal={false} />
                    <XAxis
                      type="number"
                      axisLine={false}
                      tickLine={false}
                      tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 10 }}
                      tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`}
                    />
                    <YAxis
                      dataKey="name"
                      type="category"
                      axisLine={false}
                      tickLine={false}
                      tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 10 }}
                      width={40}
                      tickFormatter={(v: string) => v.slice(0, 3)}
                    />
                    <Tooltip content={<DayTooltip />} />
                    <ReferenceLine x={0} stroke="hsl(var(--border))" strokeWidth={1.5} />
                    <Bar dataKey="pnl" radius={[0, 3, 3, 0]}>
                      {data.by_day_of_week.map((entry, i) => (
                        <Cell key={i} fill={entry.pnl >= 0 ? '#16A34A' : '#DC2626'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Instrument Leaderboard — Zerodha holdings style */}
      {data.by_instrument.length > 0 && (
        <div className="tm-card overflow-hidden">
          <div className="px-5 py-4 border-b border-border flex items-center justify-between">
            <p className="tm-label">Instruments</p>
            <p className="text-xs text-muted-foreground">{data.by_instrument.length} symbols</p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border">
                  <th className="px-5 py-2 text-left text-[11px] font-medium uppercase tracking-widest text-muted-foreground">#</th>
                  <th className="px-3 py-2 text-left text-[11px] font-medium uppercase tracking-widest text-muted-foreground">Symbol</th>
                  <th className="px-3 py-2 text-right text-[11px] font-medium uppercase tracking-widest text-muted-foreground">P&L</th>
                  <th className="px-3 py-2 text-right text-[11px] font-medium uppercase tracking-widest text-muted-foreground">Win%</th>
                  <th className="px-3 py-2 text-right text-[11px] font-medium uppercase tracking-widest text-muted-foreground">Trades</th>
                  <th className="px-5 py-2 text-right text-[11px] font-medium uppercase tracking-widest text-muted-foreground">Avg</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {sortedInstruments.slice(0, 10).map((instr, i) => (
                  <tr key={instr.symbol} className="hover:bg-muted/40 transition-colors">
                    <td className="px-5 py-3 text-sm font-mono text-muted-foreground">{i + 1}</td>
                    <td className="px-3 py-3 text-sm font-medium text-foreground">{instr.symbol}</td>
                    <td className={cn(
                      'px-3 py-3 text-right text-sm font-mono tabular-nums font-medium',
                      instr.pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss'
                    )}>
                      {formatCurrencyWithSign(instr.pnl)}
                    </td>
                    <td className={cn(
                      'px-3 py-3 text-right text-sm tabular-nums',
                      instr.win_rate >= 50 ? 'text-tm-profit' : 'text-tm-loss'
                    )}>
                      {instr.win_rate}%
                    </td>
                    <td className="px-3 py-3 text-right text-sm tabular-nums text-muted-foreground">{instr.trades}</td>
                    <td className={cn(
                      'px-5 py-3 text-right text-sm font-mono tabular-nums',
                      instr.avg_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss'
                    )}>
                      {formatCurrencyWithSign(instr.avg_pnl)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
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

function HourTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="bg-popover border border-border rounded-lg p-3 shadow-lg text-sm">
      <p className="font-medium text-foreground">{d.label} IST</p>
      <p className={cn('tabular-nums font-mono', d.pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
        {formatCurrencyWithSign(d.pnl)}
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
        {formatCurrencyWithSign(d.pnl)}
      </p>
      <p className="text-xs text-muted-foreground">{d.trades} trades &middot; {d.win_rate}% WR</p>
    </div>
  );
}
