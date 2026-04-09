import { useState, useEffect } from 'react';
import { X, TrendingUp, TrendingDown } from 'lucide-react';
import {
  AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, Cell,
} from 'recharts';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { formatCurrencyWithSign, formatCurrency } from '@/lib/formatters';
import { api } from '@/lib/api';

interface InstrumentPanelProps {
  underlying: string;
  days: number;
  onClose: () => void;
}

interface OptionTypeStat {
  trades: number; pnl: number; win_rate: number; avg_pnl: number;
}

interface InstrumentData {
  has_data: boolean;
  underlying: string;
  total_trades: number;
  total_pnl: number;
  win_rate: number;
  profit_factor: number;
  avg_hold_min: number;
  avg_win: number;
  avg_loss: number;
  by_option_type: Record<string, OptionTypeStat>;
  by_hour: { hour: number; label: string; trades: number; pnl: number; win_rate: number }[];
  equity_curve: { date: string; cumulative_pnl: number }[];
  trades: {
    id: string; tradingsymbol: string; direction: string;
    total_quantity: number; avg_entry_price: number; avg_exit_price: number;
    realized_pnl: number; duration_minutes: number | null;
    exit_time: string; option_type: string;
  }[];
}

function fmtDate(s: string) {
  return new Date(s).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
}
function fmtTime(s: string) {
  return new Date(s).toLocaleTimeString('en-IN', {
    hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'Asia/Kolkata',
  });
}
function fmtDur(m: number | null) {
  if (!m) return '—';
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60), rem = m % 60;
  return rem ? `${h}h ${rem}m` : `${h}h`;
}

const OPT_COLOR: Record<string, string> = {
  CE:  'tm-chip tm-chip-ce',
  PE:  'tm-chip tm-chip-pe',
  FUT: 'tm-chip bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300',
  EQ:  'tm-chip tm-chip-eq',
};

export default function InstrumentPanel({ underlying, days, onClose }: InstrumentPanelProps) {
  const [data, setData]         = useState<InstrumentData | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    api.get('/api/analytics/instrument', { params: { underlying, days } })
      .then(r => { if (!cancelled) setData(r.data); })
      .catch(() => {})
      .finally(() => { if (!cancelled) setIsLoading(false); });
    return () => { cancelled = true; };
  }, [underlying, days]);

  const isProfit = (data?.total_pnl ?? 0) >= 0;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/30 backdrop-blur-[2px] z-40"
        onClick={onClose}
      />

      {/* Panel — slides in from the right */}
      <div className="fixed top-0 right-0 h-full w-full max-w-[480px] bg-background border-l border-border shadow-2xl z-50 flex flex-col overflow-hidden animate-slide-in-right" style={{ animation: 'slideInRight 0.28s cubic-bezier(0.16,1,0.3,1) both' }}>

        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border shrink-0">
          <div>
            <h2 className="text-base font-bold text-foreground tracking-tight">{underlying}</h2>
            <p className="text-xs text-muted-foreground">Last {days} days</p>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-muted/60 transition-colors"
          >
            <X className="h-4 w-4 text-muted-foreground" />
          </button>
        </div>

        {/* Scrollable content */}
        <div className="flex-1 overflow-y-auto">
          {isLoading ? (
            <div className="p-5 space-y-4">
              <div className="grid grid-cols-2 gap-3">
                {[1,2,3,4].map(i => <Skeleton key={i} className="h-20 rounded-xl" />)}
              </div>
              <Skeleton className="h-[180px] rounded-xl" />
              <Skeleton className="h-[120px] rounded-xl" />
            </div>
          ) : !data?.has_data ? (
            <div className="flex flex-col items-center justify-center h-64">
              <p className="text-sm font-medium text-foreground">No data for {underlying}</p>
              <p className="text-xs text-muted-foreground mt-1">in the last {days} days</p>
            </div>
          ) : (
            <div className="p-5 space-y-4">

              {/* KPI grid */}
              <div className="grid grid-cols-2 gap-px bg-border rounded-lg overflow-hidden">
                <div className="bg-card px-4 py-3">
                  <p className="text-xs text-muted-foreground mb-1">Total P&L</p>
                  <p className={cn('text-xl font-bold font-mono tabular-nums',
                    isProfit ? 'text-tm-profit' : 'text-tm-loss')}>
                    {formatCurrencyWithSign(data.total_pnl)}
                  </p>
                  <p className="text-[11px] text-muted-foreground mt-0.5">{data.total_trades} trades</p>
                </div>
                <div className="bg-card px-4 py-3">
                  <p className="text-xs text-muted-foreground mb-1">Win Rate</p>
                  <p className={cn('text-xl font-bold font-mono tabular-nums',
                    data.win_rate >= 50 ? 'text-tm-profit' : 'text-tm-loss')}>
                    {data.win_rate}%
                  </p>
                  <p className="text-[11px] text-muted-foreground mt-0.5">
                    PF: {data.profit_factor > 0 ? data.profit_factor.toFixed(2) : '—'}
                  </p>
                </div>
                <div className="bg-card px-4 py-3">
                  <p className="text-xs text-muted-foreground mb-1">Avg Win</p>
                  <p className="text-xl font-bold font-mono tabular-nums text-tm-profit">
                    {formatCurrency(data.avg_win)}
                  </p>
                  <p className="text-[11px] text-muted-foreground mt-0.5">Avg hold: {fmtDur(data.avg_hold_min)}</p>
                </div>
                <div className="bg-card px-4 py-3">
                  <p className="text-xs text-muted-foreground mb-1">Avg Loss</p>
                  <p className="text-xl font-bold font-mono tabular-nums text-tm-loss">
                    {formatCurrency(Math.abs(data.avg_loss))}
                  </p>
                  <p className={cn('text-[11px] font-mono mt-0.5',
                    data.avg_win > Math.abs(data.avg_loss) ? 'text-tm-profit' : 'text-tm-loss')}>
                    Ratio {data.avg_loss !== 0
                      ? (data.avg_win / Math.abs(data.avg_loss)).toFixed(2)
                      : '—'}:1
                  </p>
                </div>
              </div>

              {/* CE / PE / FUT split */}
              {Object.keys(data.by_option_type).length > 1 && (
                <div className="tm-card overflow-hidden">
                  <div className="px-4 py-3 border-b border-border">
                    <p className="tm-label">By Option Type</p>
                  </div>
                  <div className="divide-y divide-border">
                    {(['CE','PE','FUT','EQ'] as const)
                      .filter(k => data.by_option_type[k])
                      .map(k => {
                        const v = data.by_option_type[k];
                        return (
                          <div key={k} className="px-4 py-3 flex items-center justify-between">
                            <div className="flex items-center gap-2.5">
                              <span className={OPT_COLOR[k] ?? 'tm-chip tm-chip-eq'}>{k}</span>
                              <span className="text-xs text-muted-foreground">
                                {v.trades}T · {v.win_rate}% WR
                              </span>
                            </div>
                            <div className="text-right">
                              <p className={cn('text-sm font-bold font-mono tabular-nums',
                                v.pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
                                {formatCurrencyWithSign(v.pnl)}
                              </p>
                              <p className={cn('text-[11px] font-mono tabular-nums',
                                v.avg_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
                                {formatCurrencyWithSign(v.avg_pnl)}/trade
                              </p>
                            </div>
                          </div>
                        );
                      })}
                  </div>
                </div>
              )}

              {/* Equity curve */}
              {data.equity_curve.length > 1 && (
                <div className="tm-card overflow-hidden">
                  <div className="px-4 py-3 border-b border-border">
                    <p className="tm-label">Cumulative P&L</p>
                  </div>
                  <div className="px-3 py-3">
                    <div className="h-[140px]">
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={data.equity_curve}>
                          <defs>
                            <linearGradient id="instrGrad" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="5%"  stopColor={isProfit ? '#16A34A' : '#DC2626'} stopOpacity={0.18} />
                              <stop offset="95%" stopColor={isProfit ? '#16A34A' : '#DC2626'} stopOpacity={0} />
                            </linearGradient>
                          </defs>
                          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" strokeOpacity={0.5} vertical={false} />
                          <XAxis dataKey="date" tickFormatter={fmtDate} axisLine={false} tickLine={false}
                            tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 10 }} interval="preserveStartEnd" />
                          <YAxis axisLine={false} tickLine={false}
                            tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 10 }}
                            tickFormatter={(v) => `₹${(v/1000).toFixed(0)}k`} width={40} />
                          <Tooltip
                            content={({ active, payload }: any) => {
                              if (!active || !payload?.length) return null;
                              const d = payload[0].payload;
                              return (
                                <div className="bg-popover border border-border rounded px-2.5 py-1.5 text-xs shadow">
                                  <p className="text-muted-foreground">{fmtDate(d.date)}</p>
                                  <p className={cn('font-mono tabular-nums font-medium',
                                    d.cumulative_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
                                    {formatCurrencyWithSign(d.cumulative_pnl)}
                                  </p>
                                </div>
                              );
                            }}
                          />
                          <ReferenceLine y={0} stroke="hsl(var(--border))" strokeWidth={1.5} />
                          <Area type="monotone" dataKey="cumulative_pnl"
                            stroke={isProfit ? '#16A34A' : '#DC2626'} strokeWidth={1.5}
                            fill="url(#instrGrad)" />
                        </AreaChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                </div>
              )}

              {/* By hour */}
              {data.by_hour.length > 1 && (
                <div className="tm-card overflow-hidden">
                  <div className="px-4 py-3 border-b border-border">
                    <p className="tm-label">P&L by Entry Hour (IST)</p>
                  </div>
                  <div className="px-3 py-3">
                    <div className="h-[120px]">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={data.by_hour}>
                          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" strokeOpacity={0.5} vertical={false} />
                          <XAxis dataKey="label" axisLine={false} tickLine={false}
                            tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 10 }} />
                          <YAxis axisLine={false} tickLine={false}
                            tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 10 }}
                            tickFormatter={(v) => `₹${(v/1000).toFixed(0)}k`} width={40} />
                          <Tooltip
                            content={({ active, payload }: any) => {
                              if (!active || !payload?.length) return null;
                              const d = payload[0].payload;
                              return (
                                <div className="bg-popover border border-border rounded px-2.5 py-1.5 text-xs shadow">
                                  <p className="text-muted-foreground">{d.label} IST</p>
                                  <p className={cn('font-mono tabular-nums font-medium',
                                    d.pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
                                    {formatCurrencyWithSign(d.pnl)}
                                  </p>
                                  <p className="text-muted-foreground">{d.trades}T · {d.win_rate}% WR</p>
                                </div>
                              );
                            }}
                          />
                          <ReferenceLine y={0} stroke="hsl(var(--border))" strokeWidth={1.5} />
                          <Bar dataKey="pnl" radius={[2,2,0,0]}>
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

              {/* Recent trades */}
              {data.trades.length > 0 && (
                <div className="tm-card overflow-hidden">
                  <div className="px-4 py-3 border-b border-border">
                    <p className="tm-label">Recent Trades</p>
                  </div>
                  <table className="w-full">
                    <thead>
                      <tr className="border-b-2 border-b-slate-200 dark:border-b-neutral-700/80">
                        <th className="px-4 py-2 text-left table-header">Symbol</th>
                        <th className="px-3 py-2 text-right table-header">P&L</th>
                        <th className="px-3 py-2 text-right table-header">Hold</th>
                        <th className="px-4 py-2 text-right table-header">Time</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.trades.map((t, i) => (
                        <tr
                          key={t.id}
                          className={cn(
                            'transition-colors hover:bg-slate-50 dark:hover:bg-neutral-700/20',
                            i < data.trades.length - 1 && 'border-b border-slate-50 dark:border-neutral-700/30'
                          )}
                        >
                          <td className="px-4 py-2.5">
                            <div className="flex items-center gap-1.5">
                              <span className={cn('text-[11px]',
                                t.direction === 'LONG' ? 'text-tm-profit' : 'text-tm-loss')}>
                                {t.direction === 'LONG' ? 'B' : 'S'}
                              </span>
                              <span className={OPT_COLOR[t.option_type] ?? 'tm-chip tm-chip-eq'}>
                                {t.option_type}
                              </span>
                            </div>
                            <p className="text-xs text-muted-foreground font-mono mt-0.5">
                              {fmtDate(t.exit_time)} {fmtTime(t.exit_time)}
                            </p>
                          </td>
                          <td className={cn('px-3 py-2.5 text-right text-sm font-mono tabular-nums font-semibold',
                            t.realized_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
                            {formatCurrencyWithSign(t.realized_pnl)}
                          </td>
                          <td className="px-3 py-2.5 text-right text-sm font-mono tabular-nums text-muted-foreground">
                            {fmtDur(t.duration_minutes)}
                          </td>
                          <td className="px-4 py-2.5 text-right text-xs text-muted-foreground font-mono">
                            {t.avg_entry_price.toLocaleString('en-IN', { maximumFractionDigits: 1 })}
                            {' → '}
                            {t.avg_exit_price.toLocaleString('en-IN', { maximumFractionDigits: 1 })}
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
      </div>
    </>
  );
}
