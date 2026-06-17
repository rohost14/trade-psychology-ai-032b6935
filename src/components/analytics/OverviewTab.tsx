import { useState, useEffect } from 'react';
import {
  AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, Cell,
  PieChart, Pie, Legend,
} from 'recharts';
import { TrendingUp, TrendingDown, RefreshCw, AlertTriangle, CheckCircle2, Activity, ArrowUp, ArrowDown, Minus } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { formatCurrency, formatCurrencyWithSign } from '@/lib/formatters';
import { api } from '@/lib/api';

interface OverviewTabProps { days: number }

interface Kpis {
  total_pnl: number; total_trades: number; win_rate: number;
  profit_factor: number; expectancy: number;
  max_drawdown: number; trading_days: number; win_days: number;
  max_win_streak: number; max_loss_streak: number;
  avg_win: number; avg_loss: number; winners: number; losers: number;
}

interface OverviewData {
  has_data: boolean;
  kpis: Kpis | null;
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
  by_product: Record<string, { trades: number; pnl: number; win_rate: number }>;
  by_instrument: { symbol: string; trades: number; pnl: number; win_rate: number; avg_pnl: number; avg_duration_min: number }[];
}

// ── helpers ──────────────────────────────────────────────────────────────────

function fmtDate(s: string) {
  return new Date(s).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
}

function extractUnderlying(sym: string): string {
  const m1 = sym.match(/^([A-Z\-]+?)\d{5}\d+(CE|PE)$/);
  if (m1) return m1[1];
  const mDD = sym.match(/^([A-Z\-]+?)\d{2}[A-Z]{3}\d{2}\d+(?:\.\d+)?(CE|PE)$/);
  if (mDD) return mDD[1];
  const m2 = sym.match(/^([A-Z\-]+?)\d{2}[A-Z]{3}\d+(CE|PE)$/);
  if (m2) return m2[1];
  const m3 = sym.match(/^([A-Z\-]+?)(?:\d{5}|\d{2}[A-Z]{3}(?:\d{2})?)FUT$/);
  if (m3) return m3[1];
  return sym;
}

function buildPieData(instruments: PerfData['by_instrument']) {
  const map: Record<string, number> = {};
  for (const i of instruments) {
    const u = extractUnderlying(i.symbol);
    map[u] = (map[u] ?? 0) + i.pnl;
  }
  const entries = Object.entries(map)
    .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]));
  const top5 = entries.slice(0, 5);
  const others = entries.slice(5).reduce((s, [, v]) => s + v, 0);
  const result = top5.map(([name, pnl]) => ({ name, pnl, value: Math.abs(pnl) }));
  if (others !== 0) result.push({ name: 'Others', pnl: others, value: Math.abs(others) });
  return result;
}

const PIE_COLORS = ['#0d9488', '#0891b2', '#7c3aed', '#d97706', '#dc2626', '#6b7280'];

// ── sub-components ───────────────────────────────────────────────────────────

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

function PieTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="bg-popover border border-border rounded-lg px-3 py-2 shadow-lg text-sm">
      <p className="font-medium mb-1">{d.name}</p>
      <p className={cn('font-mono tabular-nums', d.pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
        {formatCurrencyWithSign(Math.round(d.pnl))}
      </p>
    </div>
  );
}

// Delta indicator between current and prev period
function DeltaChip({ current, prev, higherIsBetter = true, format = 'number' }: {
  current: number; prev: number; higherIsBetter?: boolean; format?: 'number' | 'percent' | 'currency'
}) {
  if (prev === 0 && current === 0) return null;
  const delta = current - prev;
  const improved = higherIsBetter ? delta > 0 : delta < 0;
  const neutral = Math.abs(delta) < 0.01;
  const fmt = (v: number) => {
    if (format === 'currency') return formatCurrencyWithSign(Math.round(Math.abs(v)));
    if (format === 'percent') return `${Math.abs(v).toFixed(1)}%`;
    return String(Math.round(Math.abs(v)));
  };
  return (
    <div className={cn(
      'flex items-center gap-0.5 text-[10px] font-medium mt-1',
      neutral ? 'text-muted-foreground' : improved ? 'text-tm-profit' : 'text-tm-loss',
    )}>
      {neutral
        ? <Minus className="h-2.5 w-2.5 shrink-0" />
        : improved
        ? <ArrowUp className="h-2.5 w-2.5 shrink-0" />
        : <ArrowDown className="h-2.5 w-2.5 shrink-0" />
      }
      <span>{neutral ? 'flat' : `${fmt(delta)} vs prev`}</span>
    </div>
  );
}

// Large KPI cell — P&L gets special treatment (full-width first cell on mobile)
function KpiCell({
  label, value, color, sub, delta,
}: {
  label: string; value: string; color?: string; sub?: string;
  delta?: { current: number; prev: number; higherIsBetter?: boolean; format?: 'number' | 'percent' | 'currency' };
}) {
  return (
    <div className="flex flex-col justify-center px-4 py-3.5 min-w-0">
      <p className="text-[10px] text-muted-foreground uppercase tracking-wide mb-1.5 truncate">{label}</p>
      <p className={cn('font-mono font-bold tabular-nums leading-none', color ?? 'text-foreground')}
        style={{ fontSize: 'clamp(16px, 3.5vw, 21px)' }}>
        {value}
      </p>
      {sub && <p className="text-[11px] text-muted-foreground mt-0.5 truncate">{sub}</p>}
      {delta && (
        <DeltaChip
          current={delta.current}
          prev={delta.prev}
          higherIsBetter={delta.higherIsBetter}
          format={delta.format}
        />
      )}
    </div>
  );
}

// Hero P&L cell — larger than the rest
function PnlHeroCell({
  value, color, sub, delta,
}: {
  value: string; color: string; sub?: string;
  delta?: { current: number; prev: number; higherIsBetter?: boolean; format?: 'number' | 'percent' | 'currency' };
}) {
  return (
    <div className="flex flex-col justify-center px-4 py-3.5 col-span-2 md:col-span-1 min-w-0 border-b md:border-b-0 md:border-r border-border">
      <p className="text-[10px] text-muted-foreground uppercase tracking-wide mb-1.5">Net P&L</p>
      <p className={cn('font-mono font-black tabular-nums leading-none', color)}
        style={{ fontSize: 'clamp(22px, 5vw, 28px)' }}>
        {value}
      </p>
      {sub && <p className="text-[11px] text-muted-foreground mt-0.5">{sub}</p>}
      {delta && (
        <DeltaChip
          current={delta.current}
          prev={delta.prev}
          higherIsBetter={delta.higherIsBetter}
          format={delta.format}
        />
      )}
    </div>
  );
}

// ── main component ───────────────────────────────────────────────────────────

export default function OverviewTab({ days }: OverviewTabProps) {
  const [overview, setOverview]   = useState<OverviewData | null>(null);
  const [ovPrev, setOvPrev]       = useState<OverviewData | null>(null);
  const [edge, setEdge]           = useState<EdgeData | null>(null);
  const [perf, setPerf]           = useState<PerfData | null>(null);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState<string | null>(null);
  const [retry, setRetry]         = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.allSettled([
      api.get('/api/analytics/overview', { params: { days } }),
      api.get('/api/analytics/overview', { params: { days: days * 2 } }),
      api.get('/api/analytics/edge-confidence', { params: { days } }),
      api.get('/api/analytics/performance', { params: { days } }),
    ]).then(([ov, ovP, ed, pf]) => {
      if (cancelled) return;
      if (ov.status === 'fulfilled') setOverview(ov.value.data);
      if (ovP.status === 'fulfilled') setOvPrev(ovP.value.data);
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
      <Skeleton className="h-20 rounded-xl" />
      <Skeleton className="h-8 rounded-xl" />
      <Skeleton className="h-[240px] rounded-xl" />
      <Skeleton className="h-[160px] rounded-xl" />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Skeleton className="h-[200px] rounded-xl" />
        <Skeleton className="h-[200px] rounded-xl" />
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

  const k  = overview?.kpis;
  const kP = ovPrev?.kpis;

  // ── Prev period approximation ─────────────────────────────────────────────
  // 2x window includes both current + prev. Subtract current to get prev.
  const prevPnl    = kP && k ? kP.total_pnl - k.total_pnl : 0;
  const prevTrades = kP && k ? kP.total_trades - k.total_trades : 0;
  const prevWins   = kP && k
    ? Math.round(kP.total_trades * kP.win_rate / 100) - Math.round(k.total_trades * k.win_rate / 100)
    : 0;
  const prevWR     = prevTrades > 0 ? prevWins / prevTrades * 100 : 0;
  const prevPF     = kP && k ? kP.profit_factor : 0; // rough — use 2x pf as prev
  const prevExp    = kP && k ? kP.expectancy : 0;

  const winDaysPct = k && k.trading_days > 0 ? Math.round(k.win_days / k.trading_days * 100) : 0;
  const lastPnl    = overview?.equity_curve?.at(-1)?.cumulative_pnl ?? 0;
  const equityColor = lastPnl >= 0 ? '#16a34a' : '#dc2626';

  // P&L attribution donut
  const pieData = perf?.by_instrument ? buildPieData(perf.by_instrument) : [];

  // Product mix
  const products = perf?.by_product ?? {};
  const productEntries = Object.entries(products).sort((a, b) => b[1].trades - a[1].trades);

  // ── Personalized insights ─────────────────────────────────────────────────
  const topUnderlying = pieData[0];
  const topPct = pieData.length > 0
    ? Math.round(Math.abs(topUnderlying?.pnl ?? 0) / Math.max(pieData.reduce((s, d) => s + d.value, 0), 1) * 100)
    : 0;

  return (
    <div className="space-y-5">

      {/* ── KPI Strip ────────────────────────────────────────────────────────── */}
      {k ? (
        <div className="tm-card overflow-hidden">
          {/* Mobile: 2-col grid. P&L spans full width. Desktop: 6 equal cols */}
          <div className="grid grid-cols-2 md:grid-cols-6 divide-y md:divide-y-0 divide-x divide-border">
            <PnlHeroCell
              value={formatCurrencyWithSign(Math.round(k.total_pnl))}
              color={k.total_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss'}
              sub={`${k.total_trades} trades`}
              delta={{ current: k.total_pnl, prev: prevPnl, higherIsBetter: true, format: 'currency' }}
            />
            <KpiCell
              label="Win Rate"
              value={`${Math.round(k.win_rate)}%`}
              sub={`${k.winners}W · ${k.losers}L`}
              color={k.win_rate >= 50 ? 'text-tm-profit' : 'text-tm-loss'}
              delta={{ current: k.win_rate, prev: prevWR, higherIsBetter: true, format: 'percent' }}
            />
            <KpiCell
              label="Profit Factor"
              value={k.profit_factor > 0 ? k.profit_factor.toFixed(2) : '—'}
              sub={k.profit_factor >= 1.5 ? 'Strong edge' : k.profit_factor >= 1 ? 'Marginal' : 'Losing edge'}
              color={k.profit_factor >= 1.5 ? 'text-tm-profit' : k.profit_factor >= 1 ? 'text-tm-obs' : 'text-tm-loss'}
              delta={kP ? { current: k.profit_factor, prev: prevPF, higherIsBetter: true, format: 'number' } : undefined}
            />
            <KpiCell
              label="Expectancy"
              value={k.expectancy != null ? formatCurrencyWithSign(Math.round(k.expectancy)) : '—'}
              sub="per trade"
              color={k.expectancy >= 0 ? 'text-tm-profit' : 'text-tm-loss'}
              delta={kP ? { current: k.expectancy, prev: prevExp, higherIsBetter: true, format: 'currency' } : undefined}
            />
            <KpiCell
              label="Win Days"
              value={`${winDaysPct}%`}
              sub={`${k.win_days} / ${k.trading_days} days`}
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

      {/* ── Edge Confidence Banner ────────────────────────────────────────────── */}
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
              {edge.is_valid ? 'Statistically valid edge' : 'Edge not yet confirmed'}
            </span>
            <span className="text-muted-foreground ml-1">
              — {Math.round(edge.win_rate)}% win rate · 95% CI {Math.round(edge.lower_ci)}%–{Math.round(edge.upper_ci)}% · n={edge.sample_size}
            </span>
          </span>
        </div>
      )}

      {/* ── Equity Curve ──────────────────────────────────────────────────────── */}
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
          {k && (k.max_win_streak > 1 || k.max_loss_streak > 1) && (
            <p className="px-5 pb-3.5 text-[11px] text-muted-foreground">
              {k.max_win_streak > 1 && `Best streak: ${k.max_win_streak} consecutive wins`}
              {k.max_win_streak > 1 && k.max_loss_streak > 1 && ' · '}
              {k.max_loss_streak > 1 && `Worst streak: ${k.max_loss_streak} consecutive losses`}
            </p>
          )}
        </div>
      )}

      {/* ── Daily P&L ─────────────────────────────────────────────────────────── */}
      {overview?.daily_pnl && overview.daily_pnl.length > 0 && (
        <div className="tm-card overflow-hidden">
          <div className="px-5 py-3.5 border-b border-border flex items-center justify-between">
            <p className="font-semibold text-sm">Daily P&L</p>
            {k && <span className="text-xs text-muted-foreground">{winDaysPct}% profitable days</span>}
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

      {/* ── P&L Attribution + Product Mix ─────────────────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

        {/* P&L Attribution Donut */}
        {pieData.length > 1 && (
          <div className="tm-card overflow-hidden">
            <div className="px-5 py-3.5 border-b border-border">
              <p className="font-semibold text-sm">P&L Attribution</p>
            </div>
            <div className="p-4">
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie
                    data={pieData}
                    cx="50%"
                    cy="50%"
                    innerRadius={55}
                    outerRadius={80}
                    paddingAngle={2}
                    dataKey="value"
                  >
                    {pieData.map((_, i) => (
                      <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} opacity={0.85} />
                    ))}
                  </Pie>
                  <Tooltip content={<PieTooltip />} />
                </PieChart>
              </ResponsiveContainer>
              <div className="space-y-1.5 mt-1">
                {pieData.map((d, i) => {
                  const totalAbs = pieData.reduce((s, x) => s + x.value, 0);
                  const pct = totalAbs > 0 ? Math.round(d.value / totalAbs * 100) : 0;
                  return (
                    <div key={d.name} className="flex items-center justify-between text-[12px]">
                      <div className="flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: PIE_COLORS[i % PIE_COLORS.length] }} />
                        <span className="font-medium">{d.name}</span>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="text-muted-foreground font-mono">{pct}%</span>
                        <span className={cn('font-mono font-semibold', d.pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
                          {formatCurrencyWithSign(Math.round(d.pnl))}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
            {topUnderlying && (
              <p className="px-5 pb-3.5 text-[11px] text-muted-foreground">
                {topPct >= 60
                  ? `${topUnderlying.name} drives ${topPct}% of your P&L — high concentration. Consider diversifying.`
                  : `P&L spread across instruments. ${topUnderlying.name} leads at ${topPct}%.`
                }
              </p>
            )}
          </div>
        )}

        {/* Product Mix */}
        {productEntries.length > 0 && (
          <div className="tm-card overflow-hidden">
            <div className="px-5 py-3.5 border-b border-border">
              <p className="font-semibold text-sm">Product Mix</p>
            </div>
            <div className="p-4 space-y-4">
              {productEntries.map(([product, stats]) => (
                <div key={product}>
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-sm font-semibold">{product}</span>
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
            <p className="px-5 pb-3.5 text-[11px] text-muted-foreground">
              {productEntries.length > 0 && (() => {
                const [best] = productEntries.sort((a, b) => b[1].pnl - a[1].pnl);
                return `${best[0]} is your strongest product type this period (${formatCurrencyWithSign(Math.round(best[1].pnl))}).`;
              })()}
            </p>
          </div>
        )}
      </div>

      {/* ── Streak summary ─────────────────────────────────────────────────────── */}
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
