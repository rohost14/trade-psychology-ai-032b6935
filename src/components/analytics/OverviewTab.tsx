import { useState, useEffect } from 'react';
import {
  AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, Cell,
} from 'recharts';
import { TrendingUp, TrendingDown, RefreshCw, AlertTriangle, CheckCircle2, Activity } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { formatCurrency, formatCurrencyWithSign } from '@/lib/formatters';
import { api } from '@/lib/api';

interface OverviewTabProps { days: number }

interface OverviewData {
  has_data: boolean;
  kpis: {
    total_pnl: number; total_trades: number; win_rate: number;
    profit_factor: number; expectancy: number;
    max_drawdown: number; trading_days: number; win_days: number;
    max_win_streak: number; max_loss_streak: number;
    avg_win: number; avg_loss: number;
  } | null;
  equity_curve: { date: string; cumulative_pnl: number; trade_count: number }[];
  daily_pnl: { date: string; pnl: number; trades: number; win_rate: number }[];
}

interface EdgeData {
  has_data: boolean;
  win_rate: number; lower_ci: number; upper_ci: number;
  sample_size: number; is_valid: boolean;
}

interface PerfData {
  has_data: boolean;
  by_product: Record<string, { trades: number; pnl: number; win_rate: number; avg_pnl: number }>;
  by_hour: { hour: number; label: string; trades: number; pnl: number; win_rate: number }[];
}

function fmtDate(s: string) {
  return new Date(s).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
}

function EquityTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="bg-popover border border-border rounded-lg px-3 py-2 shadow-lg text-sm">
      <p className="font-medium mb-1">{fmtDate(d.date)}</p>
      <p className={cn('font-mono tabular-nums', d.cumulative_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
        {formatCurrencyWithSign(d.cumulative_pnl)}
      </p>
      <p className="text-xs text-muted-foreground">{d.trade_count} trades</p>
    </div>
  );
}

function DailyTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="bg-popover border border-border rounded-lg px-3 py-2 shadow-lg text-sm">
      <p className="font-medium mb-1">{fmtDate(d.date)}</p>
      <p className={cn('font-mono tabular-nums', d.pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
        {formatCurrencyWithSign(d.pnl)}
      </p>
      <p className="text-xs text-muted-foreground">{d.trades} trades · {d.win_rate}% WR</p>
    </div>
  );
}

function KpiCell({ label, value, sub, color }: { label: string; value: string; sub?: string; color?: string }) {
  return (
    <div className="flex flex-col justify-center px-4 py-3.5 min-w-0">
      <p className="text-[10px] text-muted-foreground uppercase tracking-wide mb-1.5 truncate">{label}</p>
      <p className={cn('text-[17px] font-mono font-semibold tabular-nums leading-none', color ?? 'text-foreground')}>{value}</p>
      {sub && <p className="text-[11px] text-muted-foreground mt-1 truncate">{sub}</p>}
    </div>
  );
}

export default function OverviewTab({ days }: OverviewTabProps) {
  const [overview, setOverview] = useState<OverviewData | null>(null);
  const [edge, setEdge]         = useState<EdgeData | null>(null);
  const [perf, setPerf]         = useState<PerfData | null>(null);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState<string | null>(null);
  const [retry, setRetry]       = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.allSettled([
      api.get('/api/analytics/overview', { params: { days } }),
      api.get('/api/analytics/edge-confidence', { params: { days } }),
      api.get('/api/analytics/performance', { params: { days } }),
    ]).then(([ov, ed, pf]) => {
      if (cancelled) return;
      if (ov.status === 'fulfilled') setOverview(ov.value.data);
      if (ed.status === 'fulfilled') setEdge(ed.value.data);
      if (pf.status === 'fulfilled') setPerf(pf.value.data);
      if (ov.status === 'rejected') {
        const err = ov.reason as any;
        setError(err?.response?.status === 401 ? 'Session expired — reconnect Zerodha.' : 'Failed to load overview data.');
      }
    }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [days, retry]);

  if (loading) return (
    <div className="space-y-4 animate-pulse">
      <Skeleton className="h-16 rounded-xl" />
      <Skeleton className="h-8 rounded-xl" />
      <Skeleton className="h-[240px] rounded-xl" />
      <Skeleton className="h-[160px] rounded-xl" />
      <div className="grid grid-cols-2 gap-4">
        <Skeleton className="h-28 rounded-xl" />
        <Skeleton className="h-28 rounded-xl" />
      </div>
    </div>
  );

  if (error) return (
    <div className="tm-card flex flex-col items-center py-16 text-center">
      <AlertTriangle className="h-8 w-8 text-tm-loss mb-3" />
      <p className="font-medium">{error}</p>
      <button onClick={() => setRetry(r => r + 1)} className="mt-4 text-sm text-tm-brand hover:underline flex items-center gap-1.5">
        <RefreshCw className="h-3.5 w-3.5" /> Try again
      </button>
    </div>
  );

  const k = overview?.kpis;
  const winDaysPct = k && k.trading_days > 0 ? Math.round(k.win_days / k.trading_days * 100) : 0;
  const lastPnl = overview?.equity_curve?.at(-1)?.cumulative_pnl ?? 0;
  const equityColor = lastPnl >= 0 ? '#16a34a' : '#dc2626';
  const products = perf?.by_product ?? {};
  const productEntries = Object.entries(products).sort((a, b) => b[1].trades - a[1].trades);
  const byHour = perf?.by_hour ?? [];
  const bestHour = byHour.length > 0 ? [...byHour].sort((a, b) => b.pnl - a.pnl)[0] : null;

  return (
    <div className="space-y-5">

      {/* KPI Strip */}
      {k ? (
        <div className="tm-card overflow-hidden">
          <div className="grid grid-cols-3 md:grid-cols-6 divide-x divide-y md:divide-y-0 divide-border">
            <KpiCell
              label="Net P&L"
              value={formatCurrencyWithSign(Math.round(k.total_pnl))}
              sub={`${k.total_trades} trades`}
              color={k.total_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss'}
            />
            <KpiCell
              label="Win Rate"
              value={`${Math.round(k.win_rate)}%`}
              sub={`${k.total_trades} trades`}
              color={k.win_rate >= 50 ? 'text-tm-profit' : 'text-tm-loss'}
            />
            <KpiCell
              label="Profit Factor"
              value={k.profit_factor > 0 ? k.profit_factor.toFixed(2) : '—'}
              sub={k.profit_factor >= 1.5 ? 'Strong edge' : k.profit_factor >= 1 ? 'Marginal edge' : 'Losing edge'}
              color={k.profit_factor >= 1.5 ? 'text-tm-profit' : k.profit_factor >= 1 ? 'text-tm-obs' : 'text-tm-loss'}
            />
            <KpiCell
              label="Expectancy"
              value={k.expectancy != null ? formatCurrencyWithSign(Math.round(k.expectancy)) : '—'}
              sub="avg per trade"
              color={k.expectancy >= 0 ? 'text-tm-profit' : 'text-tm-loss'}
            />
            <KpiCell
              label="Win Days"
              value={`${winDaysPct}%`}
              sub={`${k.win_days} of ${k.trading_days} days`}
              color={winDaysPct >= 55 ? 'text-tm-profit' : 'text-foreground'}
            />
            <KpiCell
              label="Max Drawdown"
              value={formatCurrency(Math.abs(Math.round(k.max_drawdown)))}
              sub="peak-to-trough"
              color="text-tm-loss"
            />
          </div>
        </div>
      ) : (
        <div className="tm-card px-5 py-10 text-center text-sm text-muted-foreground">
          No trade data for this period.
        </div>
      )}

      {/* Edge Confidence Banner */}
      {edge?.has_data && (
        <div className={cn(
          'flex items-start gap-3 px-4 py-3 rounded-xl border text-sm',
          edge.is_valid ? 'bg-green-500/5 border-green-500/20' : 'bg-amber-500/5 border-amber-500/20',
        )}>
          {edge.is_valid
            ? <CheckCircle2 className="h-4 w-4 text-tm-profit mt-0.5 shrink-0" />
            : <Activity className="h-4 w-4 text-tm-obs mt-0.5 shrink-0" />
          }
          <span>
            <span className={cn('font-medium', edge.is_valid ? 'text-tm-profit' : 'text-tm-obs')}>
              {edge.is_valid ? 'Statistically valid edge' : 'Edge not yet statistically confirmed'}
            </span>
            <span className="text-muted-foreground ml-1">
              — {Math.round(edge.win_rate)}% win rate (
              {Math.round(edge.lower_ci)}%–{Math.round(edge.upper_ci)}% 95% CI, n={edge.sample_size})
            </span>
          </span>
        </div>
      )}

      {/* Equity Curve */}
      {overview?.equity_curve && overview.equity_curve.length > 1 && (
        <div className="tm-card overflow-hidden">
          <div className="px-5 py-3.5 border-b border-border flex items-center justify-between">
            <p className="font-semibold text-sm">Equity Curve</p>
            <span className={cn('text-xs font-mono font-semibold tabular-nums', lastPnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
              {formatCurrencyWithSign(Math.round(lastPnl))} cumulative
            </span>
          </div>
          <div className="p-4">
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={overview.equity_curve} margin={{ top: 4, right: 4, left: -16, bottom: 0 }}>
                <defs>
                  <linearGradient id="eq-grad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor={equityColor} stopOpacity={0.2} />
                    <stop offset="95%" stopColor={equityColor} stopOpacity={0.01} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" vertical={false} />
                <XAxis dataKey="date" tickFormatter={fmtDate} tick={{ fontSize: 10 }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={v => formatCurrency(v)} />
                <Tooltip content={<EquityTooltip />} />
                <ReferenceLine y={0} stroke="rgba(0,0,0,0.12)" strokeDasharray="3 3" />
                <Area type="monotone" dataKey="cumulative_pnl" stroke={equityColor} strokeWidth={2} fill="url(#eq-grad)" dot={false} activeDot={{ r: 4 }} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          {k && (k.max_win_streak > 0 || k.max_loss_streak > 0) && (
            <p className="px-5 pb-3.5 text-[11px] text-muted-foreground">
              {k.max_win_streak > 0 && `Best streak: ${k.max_win_streak} wins`}
              {k.max_win_streak > 0 && k.max_loss_streak > 0 && ' · '}
              {k.max_loss_streak > 0 && `Worst streak: ${k.max_loss_streak} consecutive losses`}
            </p>
          )}
        </div>
      )}

      {/* Daily P&L */}
      {overview?.daily_pnl && overview.daily_pnl.length > 0 && (
        <div className="tm-card overflow-hidden">
          <div className="px-5 py-3.5 border-b border-border flex items-center justify-between">
            <p className="font-semibold text-sm">Daily P&L</p>
            {k && (
              <span className="text-xs text-muted-foreground">{winDaysPct}% profitable days</span>
            )}
          </div>
          <div className="p-4">
            <ResponsiveContainer width="100%" height={160}>
              <BarChart data={overview.daily_pnl} margin={{ top: 4, right: 4, left: -16, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" vertical={false} />
                <XAxis dataKey="date" tickFormatter={fmtDate} tick={{ fontSize: 10 }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={v => formatCurrency(v)} />
                <Tooltip content={<DailyTooltip />} />
                <ReferenceLine y={0} stroke="rgba(0,0,0,0.15)" />
                <Bar dataKey="pnl" radius={[2, 2, 0, 0]} maxBarSize={18}>
                  {overview.daily_pnl.map((d, i) => (
                    <Cell key={i} fill={d.pnl >= 0 ? '#16a34a' : '#dc2626'} opacity={0.8} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          {k && (
            <p className="px-5 pb-3.5 text-[11px] text-muted-foreground">
              Avg win day {formatCurrencyWithSign(Math.round(k.avg_win))} · avg loss day {formatCurrencyWithSign(Math.round(k.avg_loss))}
            </p>
          )}
        </div>
      )}

      {/* Product Mix + Peak Hour */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

        {productEntries.length > 0 && (
          <div className="tm-card overflow-hidden">
            <div className="px-5 py-3.5 border-b border-border">
              <p className="font-semibold text-sm">Product Mix</p>
            </div>
            <div className="p-4 space-y-3">
              {productEntries.map(([product, stats]) => (
                <div key={product}>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-medium">{product}</span>
                    <div className="flex items-center gap-3 text-xs">
                      <span className="text-muted-foreground font-mono">{stats.trades} trades</span>
                      <span className={cn('font-mono font-semibold', stats.pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
                        {formatCurrencyWithSign(Math.round(stats.pnl))}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-1.5 rounded-full bg-muted/60 overflow-hidden">
                      <div
                        className={cn('h-full rounded-full', stats.win_rate >= 50 ? 'bg-tm-profit' : 'bg-tm-loss')}
                        style={{ width: `${Math.min(100, Math.round(stats.win_rate))}%` }}
                      />
                    </div>
                    <span className="text-[11px] text-muted-foreground w-12 text-right font-mono">{Math.round(stats.win_rate)}% WR</span>
                  </div>
                </div>
              ))}
            </div>
            <p className="px-5 pb-3.5 text-[11px] text-muted-foreground">MIS = intraday · NRML = overnight/CNC</p>
          </div>
        )}

        {bestHour && (
          <div className="tm-card overflow-hidden">
            <div className="px-5 py-3.5 border-b border-border">
              <p className="font-semibold text-sm">Peak Trading Hour</p>
            </div>
            <div className="p-5">
              <div className="flex items-end gap-3 mb-4">
                <span className="text-4xl font-black font-mono tabular-nums">
                  {String(bestHour.hour).padStart(2, '0')}:00
                </span>
                <span className={cn('text-lg font-mono font-semibold pb-0.5', bestHour.pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
                  {formatCurrencyWithSign(Math.round(bestHour.pnl))}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-3 mb-4">
                <div>
                  <p className="text-[11px] text-muted-foreground mb-0.5">Win rate</p>
                  <p className="font-mono font-semibold text-sm">{Math.round(bestHour.win_rate)}%</p>
                </div>
                <div>
                  <p className="text-[11px] text-muted-foreground mb-0.5">Trade count</p>
                  <p className="font-mono font-semibold text-sm">{bestHour.trades}</p>
                </div>
              </div>
              <p className="text-[11px] text-muted-foreground">
                Most P&L comes from the {String(bestHour.hour).padStart(2,'0')}:00 candle.
                Focus your attention here and be more selective in other hours.
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Streak summary */}
      {k && (k.max_win_streak > 1 || k.max_loss_streak > 1) && (
        <div className="grid grid-cols-2 gap-4">
          <div className="tm-card p-4 flex items-center gap-3">
            <TrendingUp className="h-5 w-5 text-tm-profit shrink-0" />
            <div>
              <p className="text-[11px] text-muted-foreground">Longest win streak</p>
              <p className="text-2xl font-mono font-bold text-tm-profit">{k.max_win_streak}</p>
            </div>
          </div>
          <div className="tm-card p-4 flex items-center gap-3">
            <TrendingDown className="h-5 w-5 text-tm-loss shrink-0" />
            <div>
              <p className="text-[11px] text-muted-foreground">Longest loss streak</p>
              <p className="text-2xl font-mono font-bold text-tm-loss">{k.max_loss_streak}</p>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
