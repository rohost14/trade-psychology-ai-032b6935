import { useState, useEffect } from 'react';
import {
  AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, Cell,
} from 'recharts';
import { Trophy, Flame, ChevronRight, ArrowRight, TrendingUp, TrendingDown, BarChart2, AlertTriangle, RefreshCw } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import AttributionCard from '@/components/analytics/_archive/AttributionCard';
import { cn } from '@/lib/utils';
import { formatCurrency, formatCurrencyWithSign } from '@/lib/formatters';
import { api } from '@/lib/api';

interface SummaryTabProps {
  days: number;
  onInstrumentClick: (underlying: string) => void;
  onTabChange: (tab: string) => void;
}

interface OverviewData {
  has_data: boolean;
  kpis: {
    total_pnl: number; total_trades: number; win_rate: number;
    winners: number; losers: number; profit_factor: number;
    expectancy: number; avg_win: number; avg_loss: number;
    largest_win: number; largest_loss: number;
    best_day: { date: string; pnl: number; trades: number } | null;
    worst_day: { date: string; pnl: number; trades: number } | null;
    max_win_streak: number; max_loss_streak: number;
    trading_days: number; win_days: number; loss_days: number;
    avg_duration_min: number;
  } | null;
  equity_curve: { date: string; cumulative_pnl: number; trade_count: number }[];
  daily_pnl: { date: string; pnl: number; trades: number; win_rate: number }[];
}

interface PerfData {
  has_data: boolean;
  by_instrument: {
    symbol: string; trades: number; pnl: number;
    win_rate: number; avg_pnl: number; avg_duration_min: number;
  }[];
  by_product: Record<string, {
    trades: number; pnl: number; wins: number; losses: number;
    win_rate: number; avg_pnl: number;
  }>;
  by_hour: { hour: number; label: string; trades: number; pnl: number; win_rate: number }[];
}

interface DeltaInfo {
  text: string;
  improved: boolean | null;
}

function fmtDate(s: string) {
  return new Date(s).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
}
function fmtDur(m: number) {
  if (!m) return '—';
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60), rem = m % 60;
  return rem ? `${h}h ${rem}m` : `${h}h`;
}

function extractUnderlying(sym: string): string {
  // Weekly index options: 5-digit numeric expiry
  const m1 = sym.match(/^([A-Z\-]+?)\d{5}\d+(CE|PE)$/);
  if (m1) return m1[1];
  // Stock options: DDMMMYY expiry (specific date, may have decimal strike)
  // e.g. ADANIPOWER26JUN242.5CE → underlying = ADANIPOWER
  const mDD = sym.match(/^([A-Z\-]+?)\d{2}[A-Z]{3}\d{2}\d+(?:\.\d+)?(CE|PE)$/);
  if (mDD) return mDD[1];
  // Monthly options: YYMMM expiry
  const m2 = sym.match(/^([A-Z\-]+?)\d{2}[A-Z]{3}\d+(CE|PE)$/);
  if (m2) return m2[1];
  // Futures
  const m3 = sym.match(/^([A-Z\-]+?)(?:\d{5}|\d{2}[A-Z]{3}(?:\d{2})?)FUT$/);
  if (m3) return m3[1];
  return sym;
}

function groupByUnderlying(instruments: PerfData['by_instrument']) {
  const map: Record<string, { trades: number; pnl: number; wins: number; dur_sum: number }> = {};
  for (const instr of instruments) {
    const u = extractUnderlying(instr.symbol);
    if (!map[u]) map[u] = { trades: 0, pnl: 0, wins: 0, dur_sum: 0 };
    map[u].trades  += instr.trades;
    map[u].pnl     += instr.pnl;
    map[u].wins    += Math.round(instr.trades * instr.win_rate / 100);
    map[u].dur_sum += instr.avg_duration_min * instr.trades;
  }
  return Object.entries(map)
    .map(([u, v]) => ({
      underlying: u,
      trades:   v.trades,
      pnl:      Math.round(v.pnl),
      win_rate: v.trades ? Math.round(v.wins / v.trades * 100) : 0,
      avg_pnl:  v.trades ? Math.round(v.pnl / v.trades) : 0,
      avg_dur:  v.trades ? Math.round(v.dur_sum / v.trades) : 0,
    }))
    .sort((a, b) => b.trades - a.trades);
}

function StatCell({ label, value, color, sub, delta }: {
  label: string; value: string; color?: string; sub?: string; delta?: DeltaInfo;
}) {
  return (
    <div className="bg-card px-4 py-3">
      <p className="text-xs text-muted-foreground mb-1">{label}</p>
      <p className={cn('t-mono-lg', color ?? 'text-foreground')}>{value}</p>
      {delta && (
        <p className={cn(
          'text-[10px] font-medium mt-0.5 flex items-center gap-0.5',
          delta.improved === true  ? 'text-tm-profit' :
          delta.improved === false ? 'text-tm-loss'   : 'text-muted-foreground'
        )}>
          {delta.improved === true  && <TrendingUp  className="h-2.5 w-2.5 shrink-0" />}
          {delta.improved === false && <TrendingDown className="h-2.5 w-2.5 shrink-0" />}
          {delta.text} vs prev
        </p>
      )}
      {sub && <p className="text-[11px] text-muted-foreground mt-0.5">{sub}</p>}
    </div>
  );
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

export default function SummaryTab({ days, onInstrumentClick, onTabChange }: SummaryTabProps) {
  const [overview, setOverview]         = useState<OverviewData | null>(null);
  const [prevOverview, setPrevOverview] = useState<OverviewData | null>(null);
  const [perf, setPerf]                 = useState<PerfData | null>(null);
  const [isLoading, setIsLoading]       = useState(true);
  const [error, setError]               = useState<string | null>(null);
  const [retryKey, setRetryKey]         = useState(0);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    setError(null);
    Promise.allSettled([
      api.get('/api/analytics/overview',    { params: { days } }),
      api.get('/api/analytics/overview',    { params: { days: days * 2 } }),
      api.get('/api/analytics/performance', { params: { days } }),
    ]).then(([ov, prevOv, pf]) => {
      if (cancelled) return;
      if (ov.status === 'fulfilled') setOverview(ov.value.data);
      if (prevOv.status === 'fulfilled') setPrevOverview(prevOv.value.data);
      if (pf.status === 'fulfilled') setPerf(pf.value.data);
      if (ov.status === 'rejected') {
        const err = ov.reason as any;
        setError(err?.response?.status === 401
          ? 'Session expired — please reconnect Zerodha.'
          : 'Failed to load analytics data.');
      }
    }).finally(() => {
      if (!cancelled) setIsLoading(false);
    });
    return () => { cancelled = true; };
  }, [days, retryKey]);

  if (isLoading) return (
    <div className="space-y-3 animate-pulse">
      <Skeleton className="h-[280px] rounded-xl" />
      <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-border rounded-lg overflow-hidden">
        {[1,2,3,4].map(i => <Skeleton key={i} className="h-20 rounded-none" />)}
      </div>
      <Skeleton className="h-[200px] rounded-xl" />
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
        <Skeleton className="md:col-span-3 h-[220px] rounded-xl" />
        <div className="md:col-span-2 space-y-4">
          <Skeleton className="h-[100px] rounded-xl" />
          <Skeleton className="h-[80px] rounded-xl" />
        </div>
      </div>
    </div>
  );

  if (error) return (
    <div className="tm-card flex flex-col items-center justify-center py-16 text-center">
      <AlertTriangle className="h-8 w-8 text-tm-loss mb-3" />
      <p className="font-medium text-foreground">Failed to load analytics</p>
      <p className="text-sm text-muted-foreground mt-1 max-w-xs">{error}</p>
      <button
        onClick={() => setRetryKey(k => k + 1)}
        className="mt-4 flex items-center gap-1.5 text-sm text-tm-brand hover:underline"
      >
        <RefreshCw className="h-3.5 w-3.5" /> Try again
      </button>
    </div>
  );

  const kpis = overview?.kpis;
  if (!overview?.has_data || !kpis) {
    return (
      <div className="tm-card flex flex-col items-center justify-center py-16 text-center">
        <BarChart2 className="h-10 w-10 text-muted-foreground/30 mb-3" />
        <p className="font-medium text-foreground">No trades in this period</p>
        <p className="text-sm text-muted-foreground mt-1 max-w-sm">
          Sync your trades from Settings, then come back — analytics build automatically from your trade history.
        </p>
      </div>
    );
  }

  const isProfit    = kpis.total_pnl >= 0;
  const instruments = groupByUnderlying(perf?.by_instrument ?? []);
  const products    = perf?.by_product ?? {};
  const byHour      = perf?.by_hour ?? [];
  const bestHour    = byHour.length ? byHour.reduce((a, b) => a.pnl > b.pnl ? a : b) : null;
  const worstHour   = byHour.length ? byHour.reduce((a, b) => a.pnl < b.pnl ? a : b) : null;

  // Prior-period deltas: fetch 2x window, prior period = (2x total) - (current)
  const prevPeriodKpis = (() => {
    if (!prevOverview?.kpis || !kpis) return null;
    const pk = prevOverview.kpis;
    const prevTrades  = pk.total_trades - kpis.total_trades;
    const prevWinners = pk.winners - kpis.winners;
    const prevPnl     = pk.total_pnl - kpis.total_pnl;
    const prevWinRate = prevTrades > 0 ? Math.round(prevWinners / prevTrades * 100) : null;
    return { pnl: prevPnl, win_rate: prevWinRate, total_trades: prevTrades };
  })();

  const pnlDelta: DeltaInfo | undefined = prevPeriodKpis && prevPeriodKpis.total_trades > 0
    ? {
        text: formatCurrencyWithSign(kpis.total_pnl - prevPeriodKpis.pnl),
        improved: kpis.total_pnl > prevPeriodKpis.pnl
          ? true : kpis.total_pnl < prevPeriodKpis.pnl ? false : null,
      }
    : undefined;

  const wrDelta: DeltaInfo | undefined = prevPeriodKpis?.win_rate != null && prevPeriodKpis.total_trades > 0
    ? {
        text: `${kpis.win_rate - prevPeriodKpis.win_rate > 0 ? '+' : ''}${kpis.win_rate - prevPeriodKpis.win_rate}%`,
        improved: kpis.win_rate > prevPeriodKpis.win_rate
          ? true : kpis.win_rate < prevPeriodKpis.win_rate ? false : null,
      }
    : undefined;

  const winDayPct = kpis.trading_days > 0
    ? Math.round(kpis.win_days / kpis.trading_days * 100)
    : 0;

  return (
    <div className="space-y-4 animate-fade-in-up">

      {/* ── HERO: Equity Curve ─────────────────────────────────────────── */}
      {(overview.equity_curve?.length ?? 0) > 1 && (
        <div className="tm-card overflow-hidden">
          <div className="px-5 py-3.5 border-b border-border flex items-center justify-between">
            <div>
              <p className="tm-label">Equity Curve</p>
              <p className="text-xs text-muted-foreground">Cumulative P&L — last {days} days</p>
            </div>
            <span className={cn('text-base font-bold font-mono tabular-nums',
              isProfit ? 'text-tm-profit' : 'text-tm-loss')}>
              {formatCurrencyWithSign(kpis.total_pnl)}
            </span>
          </div>
          <div className="px-4 pt-4 pb-2">
            <div className="h-[280px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={overview.equity_curve} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
                  <defs>
                    <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor={isProfit ? '#16A34A' : '#DC2626'} stopOpacity={0.18} />
                      <stop offset="95%" stopColor={isProfit ? '#16A34A' : '#DC2626'} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" strokeOpacity={0.5} vertical={false} />
                  <XAxis dataKey="date" tickFormatter={fmtDate} axisLine={false} tickLine={false}
                    tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }} interval="preserveStartEnd" />
                  <YAxis axisLine={false} tickLine={false}
                    tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }}
                    tickFormatter={(v) => `₹${(v/1000).toFixed(0)}k`} width={44} />
                  <Tooltip content={<EquityTooltip />} />
                  <ReferenceLine y={0} stroke="hsl(var(--border))" strokeWidth={1.5} />
                  <Area type="monotone" dataKey="cumulative_pnl"
                    stroke={isProfit ? '#16A34A' : '#DC2626'} strokeWidth={2}
                    fill="url(#eqGrad)" dot={false} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
          {/* Equity insight sentence */}
          <div className={cn(
            'mx-5 mb-4 px-4 py-2.5 rounded-lg text-[12px] leading-relaxed',
            isProfit
              ? 'bg-emerald-50/60 dark:bg-emerald-950/20 text-emerald-700 dark:text-emerald-300'
              : 'bg-red-50/60 dark:bg-red-950/20 text-red-700 dark:text-red-400'
          )}>
            {isProfit
              ? <>Up <strong>{formatCurrencyWithSign(kpis.total_pnl)}</strong> over {days} days across {kpis.total_trades} trades.
                  {kpis.best_day && <> Best day: <strong>{formatCurrencyWithSign(kpis.best_day.pnl)}</strong> on {fmtDate(kpis.best_day.date)}.</>}</>
              : <>Down <strong>{formatCurrencyWithSign(Math.abs(kpis.total_pnl))}</strong> over {days} days.
                  {kpis.worst_day && <> Worst day: <strong>{formatCurrencyWithSign(kpis.worst_day.pnl)}</strong> on {fmtDate(kpis.worst_day.date)}.</>}</>
            }
          </div>
        </div>
      )}

      {/* ── Row 1: Core KPIs (with prior-period deltas) ────────────────── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-border rounded-lg overflow-hidden">
        <StatCell
          label="Total P&L"
          value={formatCurrencyWithSign(kpis.total_pnl)}
          color={isProfit ? 'text-tm-profit' : 'text-tm-loss'}
          delta={pnlDelta}
          sub={`${kpis.total_trades} trades · ${kpis.trading_days} days`}
        />
        <StatCell
          label="Win Rate"
          value={`${kpis.win_rate}%`}
          color={kpis.win_rate >= 50 ? 'text-tm-profit' : 'text-tm-loss'}
          delta={wrDelta}
          sub={`${kpis.winners}W / ${kpis.losers}L`}
        />
        <StatCell
          label="Profit Factor"
          value={kpis.profit_factor > 0 ? kpis.profit_factor.toFixed(2) : '—'}
          color={kpis.profit_factor >= 1.5 ? 'text-tm-profit' : kpis.profit_factor >= 1 ? 'text-foreground' : 'text-tm-loss'}
          sub={kpis.profit_factor >= 1.5 ? 'Strong edge' : kpis.profit_factor >= 1 ? 'Breakeven zone' : 'No edge yet'}
        />
        <StatCell
          label="Avg Per Trade"
          value={formatCurrencyWithSign(kpis.expectancy)}
          color={kpis.expectancy >= 0 ? 'text-tm-profit' : 'text-tm-loss'}
          sub={`Hold: ${fmtDur(kpis.avg_duration_min)}`}
        />
      </div>

      {/* ── Row 2: Win / Loss detail ───────────────────────────────────── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-border rounded-lg overflow-hidden">
        <StatCell
          label="Avg Win"
          value={formatCurrency(kpis.avg_win)}
          color="text-tm-profit"
          sub={`Largest: ${formatCurrency(kpis.largest_win)}`}
        />
        <StatCell
          label="Avg Loss"
          value={formatCurrency(Math.abs(kpis.avg_loss))}
          color="text-tm-loss"
          sub={`Largest: ${formatCurrency(Math.abs(kpis.largest_loss))}`}
        />
        <StatCell
          label="Best Day"
          value={kpis.best_day ? formatCurrencyWithSign(kpis.best_day.pnl) : '—'}
          color="text-tm-profit"
          sub={kpis.best_day ? `${fmtDate(kpis.best_day.date)} · ${kpis.best_day.trades}T` : ''}
        />
        <StatCell
          label="Worst Day"
          value={kpis.worst_day ? formatCurrencyWithSign(kpis.worst_day.pnl) : '—'}
          color="text-tm-loss"
          sub={kpis.worst_day ? `${fmtDate(kpis.worst_day.date)} · ${kpis.worst_day.trades}T` : ''}
        />
      </div>

      {/* ── Daily P&L ─────────────────────────────────────────────────── */}
      {(overview.daily_pnl?.length ?? 0) > 0 && (
        <div className="tm-card overflow-hidden">
          <div className="px-5 py-3.5 border-b border-border flex items-center justify-between">
            <div>
              <p className="tm-label">Daily P&L</p>
              <p className="text-xs text-muted-foreground">Profit and loss per trading day</p>
            </div>
            <div className="flex items-center gap-3 text-xs text-muted-foreground">
              <span className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-tm-profit inline-block" />{kpis.win_days}W
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-tm-loss inline-block" />{kpis.loss_days}L
              </span>
            </div>
          </div>
          <div className="px-4 pt-4 pb-2">
            <div className="h-[200px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={overview.daily_pnl} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" strokeOpacity={0.5} vertical={false} />
                  <XAxis dataKey="date" tickFormatter={fmtDate} axisLine={false} tickLine={false}
                    tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }} interval="preserveStartEnd" />
                  <YAxis axisLine={false} tickLine={false}
                    tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }}
                    tickFormatter={(v) => `₹${(v/1000).toFixed(0)}k`} width={44} />
                  <Tooltip content={<DailyTooltip />} />
                  <ReferenceLine y={0} stroke="hsl(var(--border))" strokeWidth={1.5} />
                  <Bar dataKey="pnl" radius={[2,2,0,0]}>
                    {overview.daily_pnl.map((entry, i) => (
                      <Cell key={i} fill={entry.pnl >= 0 ? '#16A34A' : '#DC2626'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
          {/* Daily P&L insight */}
          <p className="text-[11px] text-muted-foreground text-center px-5 pb-3.5">
            {kpis.win_days} of {kpis.trading_days} trading days were profitable
            {kpis.trading_days > 0 && <> ({winDayPct}% green days)</>}
          </p>
        </div>
      )}

      {/* ── Bottom grid: Instruments (3/5) + Right column (2/5) ───────── */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">

        {/* Instrument Leaderboard */}
        {instruments.length > 0 && (
          <div className="md:col-span-3 tm-card overflow-hidden">
            <div className="px-5 py-3.5 border-b border-border flex items-center justify-between">
              <div>
                <p className="tm-label">Instruments</p>
                <p className="text-xs text-muted-foreground">Click any row for full breakdown</p>
              </div>
              <button
                onClick={() => onTabChange('edgemap')}
                className="flex items-center gap-1 text-xs text-tm-brand hover:text-tm-brand/80 font-medium transition-colors shrink-0"
              >
                Edge Map <ArrowRight className="h-3 w-3" />
              </button>
            </div>
            <table className="w-full">
              <thead>
                <tr className="border-b-2 border-b-slate-200 dark:border-b-neutral-700/80">
                  <th className="px-5 py-2 text-left table-header">Name</th>
                  <th className="px-3 py-2 text-right table-header">Trades</th>
                  <th className="px-3 py-2 text-right table-header">P&L</th>
                  <th className="px-3 py-2 text-right table-header">WR%</th>
                  <th className="px-3 py-2 text-right table-header">Avg</th>
                  <th className="w-8" />
                </tr>
              </thead>
              <tbody>
                {instruments.map((instr, i) => (
                  <tr
                    key={instr.underlying}
                    onClick={() => onInstrumentClick(instr.underlying)}
                    className={cn(
                      'cursor-pointer hover:bg-slate-50 dark:hover:bg-neutral-700/30 transition-colors',
                      i < instruments.length - 1 && 'border-b border-slate-50 dark:border-neutral-700/30'
                    )}
                  >
                    <td className="px-5 py-3">
                      <span className="text-sm font-semibold text-foreground">{instr.underlying}</span>
                      <span className="ml-1.5 text-[11px] text-muted-foreground font-mono">{fmtDur(instr.avg_dur)}</span>
                    </td>
                    <td className="px-3 py-3 text-right text-sm font-mono tabular-nums text-muted-foreground">{instr.trades}</td>
                    <td className={cn('px-3 py-3 text-right text-sm font-mono tabular-nums font-medium',
                      instr.pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
                      {formatCurrencyWithSign(instr.pnl)}
                    </td>
                    <td className={cn('px-3 py-3 text-right text-sm tabular-nums',
                      instr.win_rate >= 50 ? 'text-tm-profit' : 'text-tm-loss')}>
                      {instr.win_rate}%
                    </td>
                    <td className={cn('px-3 py-3 text-right text-sm font-mono tabular-nums',
                      instr.avg_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
                      {formatCurrencyWithSign(instr.avg_pnl)}
                    </td>
                    <td className="pr-4 py-3 text-right">
                      <ChevronRight className="h-3.5 w-3.5 text-muted-foreground/40 inline-block" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {/* Instruments insight */}
            {instruments[0] && (
              <div className="px-5 py-2.5 border-t border-border/50 bg-slate-50/50 dark:bg-neutral-800/20">
                <p className="text-[11px] text-muted-foreground">
                  <strong className="text-foreground">{instruments[0].underlying}</strong> is your most-traded
                  — {instruments[0].win_rate}% WR across {instruments[0].trades} trades.
                  {instruments[0].pnl < 0
                    ? ' Despite high volume, it\'s in the red — consider whether overexposure is helping.'
                    : instruments[0].avg_pnl > 0
                    ? ` Avg ${formatCurrencyWithSign(instruments[0].avg_pnl)}/trade.`
                    : ''
                  }
                </p>
              </div>
            )}
          </div>
        )}

        {/* Right column */}
        <div className="md:col-span-2 space-y-4">

          {/* MIS / NRML / MTF */}
          {Object.keys(products).length > 0 && (
            <div className="tm-card overflow-hidden">
              <div className="px-5 py-3.5 border-b border-border">
                <p className="tm-label">Product Type</p>
                <p className="text-xs text-muted-foreground">Intraday vs overnight</p>
              </div>
              <div className="divide-y divide-border">
                {(['MIS','NRML','MTF'] as const).filter(p => products[p]).map(p => {
                  const v = products[p];
                  return (
                    <div key={p} className="px-5 py-3 flex items-center justify-between">
                      <div>
                        <p className="text-sm font-semibold text-foreground">{p}</p>
                        <p className="text-xs text-muted-foreground">{v.trades} trades · {v.win_rate}% WR</p>
                      </div>
                      <div className="text-right">
                        <p className={cn('text-sm font-bold font-mono tabular-nums',
                          v.pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
                          {formatCurrencyWithSign(v.pnl)}
                        </p>
                        <p className={cn('text-xs font-mono tabular-nums',
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

          {/* Best & Worst Hours */}
          {(bestHour || worstHour) && (
            <div className="tm-card overflow-hidden">
              <div className="px-5 py-3.5 border-b border-border">
                <p className="tm-label">Best & Worst Hours</p>
                <p className="text-xs text-muted-foreground">Entry time performance (IST)</p>
              </div>
              <div className="divide-y divide-border">
                {bestHour && (
                  <div className="px-5 py-3 flex items-center justify-between">
                    <div className="flex items-center gap-2.5">
                      <Trophy className="h-4 w-4 text-tm-profit shrink-0" />
                      <div>
                        <p className="text-sm font-medium text-foreground">{bestHour.label}</p>
                        <p className="text-xs text-muted-foreground">{bestHour.trades}T · {bestHour.win_rate}% WR</p>
                      </div>
                    </div>
                    <p className="text-sm font-bold font-mono tabular-nums text-tm-profit">
                      {formatCurrencyWithSign(bestHour.pnl)}
                    </p>
                  </div>
                )}
                {worstHour && (
                  <div className="px-5 py-3 flex items-center justify-between">
                    <div className="flex items-center gap-2.5">
                      <Flame className="h-4 w-4 text-tm-loss shrink-0" />
                      <div>
                        <p className="text-sm font-medium text-foreground">{worstHour.label}</p>
                        <p className="text-xs text-muted-foreground">{worstHour.trades}T · {worstHour.win_rate}% WR</p>
                      </div>
                    </div>
                    <p className="text-sm font-bold font-mono tabular-nums text-tm-loss">
                      {formatCurrencyWithSign(worstHour.pnl)}
                    </p>
                  </div>
                )}
                {bestHour && worstHour && bestHour.label !== worstHour.label && (
                  <div className="px-5 py-2.5 bg-slate-50/50 dark:bg-neutral-800/20">
                    <p className="text-[11px] text-muted-foreground">
                      Trade more at {bestHour.label} and less at {worstHour.label}.
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}

          <AttributionCard days={days} />

          {/* Streaks */}
          <div className="tm-card overflow-hidden">
            <div className="px-5 py-3.5 border-b border-border">
              <p className="tm-label">Streaks</p>
            </div>
            <div className="grid grid-cols-2 divide-x divide-border">
              <div className="px-5 py-4">
                <p className="text-xs text-muted-foreground mb-1">Best win streak</p>
                <p className="t-mono-lg text-tm-profit">{kpis.max_win_streak}</p>
                <p className="text-[11px] text-muted-foreground mt-0.5">in a row</p>
              </div>
              <div className="px-5 py-4">
                <p className="text-xs text-muted-foreground mb-1">Worst loss streak</p>
                <p className="t-mono-lg text-tm-loss">{kpis.max_loss_streak}</p>
                <p className="text-[11px] text-muted-foreground mt-0.5">in a row</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
