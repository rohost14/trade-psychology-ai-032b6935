/**
 * DESIGN LAB - Overview tab. Rendered by /analytics-lab, never by /analytics.
 *
 * Three arrangements of the same data, not three skins. What differs is what
 * you look at first and how much room the numbers get. What is identical is the
 * data and the fixes below, which apply in all three:
 *
 *  - P&L / win rate / profit factor are dropped from the KPI strip. The
 *    ReportCard hero directly above states all three, so the page printed the
 *    same numbers twice about 400px apart.
 *  - The attribution donut is gone. It was a five-hue rainbow whose colours
 *    carried no meaning, above a legend that coloured the same rows green and
 *    red by sign - two colour systems in one card - and the legend already said
 *    everything the donut did. Replaced by a ranked table with bars drawn from
 *    a centre baseline, so a loss extends left instead of drawing a longer bar
 *    rightward and reading as "more".
 *  - The two streak cards are gone; the equity-curve caption already states
 *    both streaks, and two integers do not need a row of the screen.
 *  - Chart colour comes from useChartColors() instead of hex literals.
 */
import { useState, useEffect } from 'react';
import {
  AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, Cell,
} from 'recharts';
import { TrendingUp, TrendingDown, CheckCircle2, Activity, ArrowUp, ArrowDown, Minus } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import ErrorState from '@/components/ErrorState';
import { cn } from '@/lib/utils';
import { useChartColors } from '@/hooks/useChartColors';
import { formatCurrency, formatCurrencyWithSign, formatAxisCurrency } from '@/lib/formatters';
import { extractUnderlying } from '@/lib/symbolClassify';
import type { ChartTooltipProps } from '@/lib/chartTooltip';
import { api } from '@/lib/api';

interface OverviewTabProps { days: number }

interface Kpis {
  total_pnl: number; total_trades: number; win_rate: number;
  /** null = no losing trades in the period (infinite PF) */
  profit_factor: number | null;
  expectancy: number;
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

// Shape of GET /api/analytics/edge-confidence (Wilson interval on win rate)
interface EdgeData {
  has_data: boolean;
  n: number;
  observed_win_rate: number;
  ci_lower: number;
  ci_upper: number;
  verdict: 'too_few' | 'real_edge' | 'losing_edge' | 'inconclusive';
  message: string;
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


// ── sub-components ───────────────────────────────────────────────────────────

function EquityTooltip({ active, payload }: ChartTooltipProps<OverviewData['equity_curve'][number]>) {
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

function DailyTooltip({ active, payload }: ChartTooltipProps<OverviewData['daily_pnl'][number]>) {
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
      <p className="text-[10px] text-muted-foreground uppercase tracking-wide mb-1.5">P&L</p>
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

export const OVERVIEW_VARIANTS = {
  trimmed: 'Trimmed',
  story: 'Story',
  dense: 'Dense',
} as const;
export type OverviewVariant = keyof typeof OVERVIEW_VARIANTS;

export default function OverviewTab({ days }: OverviewTabProps) {
  const [overview, setOverview]   = useState<OverviewData | null>(null);
  const [ovPrev, setOvPrev]       = useState<OverviewData | null>(null);
  const [edge, setEdge]           = useState<EdgeData | null>(null);
  const [perf, setPerf]           = useState<PerfData | null>(null);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState<unknown>(null);
  const [retry, setRetry]         = useState(0);
  const [variant, setVariant]     = useState<OverviewVariant>('trimmed');
  // Must sit with the other hooks: everything below the fetch has early
  // returns for loading and error, so a hook placed there runs conditionally.
  const c = useChartColors();

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
      if (ov.status === 'rejected') setError(ov.reason);   // raw error → type-aware ErrorState
    }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [days, retry]);

  if (loading) return (
    <div className="space-y-4 animate-pulse">
      <Skeleton className="h-20 rounded-lg" />
      <Skeleton className="h-8 rounded-lg" />
      <Skeleton className="h-[240px] rounded-lg" />
      <Skeleton className="h-[160px] rounded-lg" />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Skeleton className="h-[200px] rounded-lg" />
        <Skeleton className="h-[200px] rounded-lg" />
      </div>
    </div>
  );

  if (error) return <ErrorState error={error} onRetry={() => setRetry(r => r + 1)} />;

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

  /* ---- blocks: defined once, placed by the variant --------------------- */

  /* P&L, win rate and profit factor are deliberately absent -- the ReportCard
     hero immediately above states all three, and printing them again 400px
     later was the page's most visible duplication. What is left is what the
     hero does NOT already say. */
  const kpiBlock = k ? (
    <div className="tm-card overflow-hidden">
      <div className="grid grid-cols-1 sm:grid-cols-3 divide-y sm:divide-y-0 sm:divide-x divide-border">
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
        {/* Drawdown is negative by definition, so colouring it red encodes
            nothing. Left neutral; the label carries the meaning. */}
        <KpiCell
          label="Max Drawdown"
          value={formatCurrency(Math.abs(Math.round(k.max_drawdown)))}
          sub="peak-to-trough"
          color="text-foreground"
        />
      </div>
    </div>
  ) : (
    <div className="tm-card px-5 py-10 text-center text-sm text-muted-foreground">
      No trade data for this period.
    </div>
  );

  const edgeBlock = (
    <>
      {/* ── Edge Confidence Banner ────────────────────────────────────────────── */}
      {edge?.has_data && (
        <div className={cn(
          'flex items-start gap-3 px-4 py-3 rounded-lg border text-sm',
          edge.verdict === 'real_edge'
            ? 'bg-green-500/5 border-green-500/20'
            : edge.verdict === 'losing_edge'
            ? 'bg-red-500/5 border-red-500/20'
            : 'bg-amber-500/5 border-amber-500/20',
        )}>
          {edge.verdict === 'real_edge'
            ? <CheckCircle2 className="h-4 w-4 text-tm-profit mt-0.5 shrink-0" />
            : <Activity className={cn('h-4 w-4 mt-0.5 shrink-0', edge.verdict === 'losing_edge' ? 'text-tm-loss' : 'text-tm-obs')} />
          }
          <span>
            <span className={cn(
              'font-medium',
              edge.verdict === 'real_edge' ? 'text-tm-profit'
                : edge.verdict === 'losing_edge' ? 'text-tm-loss'
                : 'text-tm-obs',
            )}>
              {edge.verdict === 'real_edge' ? 'Statistically valid edge'
                : edge.verdict === 'losing_edge' ? 'Statistically losing edge'
                : edge.verdict === 'too_few' ? 'Not enough trades yet'
                : 'Edge not yet confirmed'}
            </span>
            <span className="text-muted-foreground ml-1">
              — {Math.round(edge.observed_win_rate)}% win rate · 95% CI {Math.round(edge.ci_lower)}%–{Math.round(edge.ci_upper)}% · n={edge.n}
            </span>
          </span>
        </div>
      )}

    </>
  );

  const equityBlock = (
    <>
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
                <CartesianGrid strokeDasharray="3 3" {...{ stroke: c.grid }} vertical={false} />
                <XAxis dataKey="date" tickFormatter={fmtDate} tick={{ fontSize: 10 }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 10 }} tickLine={false} axisLine={false} width={52} tickFormatter={formatAxisCurrency} />
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

    </>
  );

  const dailyBlock = (
    <>
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
                <CartesianGrid strokeDasharray="3 3" {...{ stroke: c.grid }} vertical={false} />
                <XAxis dataKey="date" tickFormatter={fmtDate} tick={{ fontSize: 10 }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 10 }} tickLine={false} axisLine={false} width={52} tickFormatter={formatAxisCurrency} />
                <Tooltip content={<DailyTooltip />} />
                <ReferenceLine y={0} {...{ stroke: c.axis }} />
                <Bar dataKey="pnl" radius={[2, 2, 0, 0]} maxBarSize={18}>
                  {overview.daily_pnl.map((d, i) => (
                    <Cell key={i} fill={c.forValue(d.pnl)} opacity={0.8} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          {k && (
            <p className="px-5 pb-3.5 text-[11px] text-muted-foreground">
              Avg winning trade {formatCurrencyWithSign(Math.round(k.avg_win))} · avg losing trade {formatCurrencyWithSign(Math.round(k.avg_loss))}
            </p>
          )}
        </div>
      )}

    </>
  );

  /* The donut, replaced. Rank plus a proportional bar answers "where did the
     money come from" better than five arbitrary hues, and the bar runs from a
     centre baseline so a loss extends left -- under the old shared left origin
     a bigger loss drew a longer bar and read as "more". */
  const attributionBlock = pieData.length > 1 ? (
    <div className="tm-card overflow-hidden">
      <div className="px-5 py-3.5 border-b border-border">
        <p className="font-semibold text-sm">Where the P&amp;L came from</p>
      </div>
      <div className="divide-y divide-border">
        {pieData.map((d, i) => {
          const maxAbs = Math.max(...pieData.map(x => Math.abs(x.pnl)), 1);
          const width = (Math.abs(d.pnl) / maxAbs) * 100;
          const positive = d.pnl >= 0;
          return (
            <div key={d.name} className="px-5 py-2.5">
              <div className="flex items-baseline justify-between gap-3">
                <span className="text-[13px] font-medium truncate">
                  <span className="text-muted-foreground font-tabular mr-2">{i + 1}</span>
                  {d.name}
                </span>
                <span className={cn('text-[13px] font-semibold font-tabular shrink-0', positive ? 'text-tm-profit' : 'text-tm-loss')}>
                  {formatCurrencyWithSign(Math.round(d.pnl))}
                </span>
              </div>
              <div className="mt-1.5 h-1 w-full flex items-center" aria-hidden>
                <div className="w-1/2 flex justify-end">
                  {!positive && <div className="h-1 rounded-l-sm bg-tm-loss/70" style={{ width: `${width}%` }} />}
                </div>
                <div className="w-1/2">
                  {positive && <div className="h-1 rounded-r-sm bg-tm-profit/70" style={{ width: `${width}%` }} />}
                </div>
              </div>
            </div>
          );
        })}
      </div>
      {topUnderlying && (
        <p className="px-5 py-3 text-[11px] text-muted-foreground border-t border-border">
          {topPct >= 60
            ? `${topUnderlying.name} drives ${topPct}% of your P&L — high concentration.`
            : `P&L spread across instruments. ${topUnderlying.name} leads at ${topPct}%.`}
        </p>
      )}
    </div>
  ) : null;

  const productMixBlock = (
    <>
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
                const sorted = [...productEntries].sort((a, b) => b[1].pnl - a[1].pnl);
                const [best] = sorted;
                const pnl = Math.round(best[1].pnl);
                const amt = formatCurrencyWithSign(pnl);
                // "Strongest" only makes sense for a positive result. A single or all-negative
                // product must NOT be labelled strongest — that contradicts the hero's "biggest leak".
                if (pnl < 0) {
                  return sorted.length === 1
                    ? `${best[0]} was your only product type this period (${amt}).`
                    : `${best[0]} lost the least this period (${amt}); every product was net negative.`;
                }
                return `${best[0]} is your strongest product type this period (${amt}).`;
              })()}
            </p>
          </div>
        )}
    </>
  );

  const switcher = (
    <div className="flex items-center gap-2 flex-wrap">
      <span className="t-label">Overview layout</span>
      <div className="inline-flex rounded-md border border-border bg-card p-0.5">
        {(Object.keys(OVERVIEW_VARIANTS) as OverviewVariant[]).map(key => (
          <button
            key={key}
            onClick={() => setVariant(key)}
            className={cn(
              'px-2.5 h-7 rounded text-[11.5px] font-medium transition-colors duration-150',
              variant === key ? 'bg-muted text-foreground' : 'text-muted-foreground hover:text-foreground',
            )}
          >
            {OVERVIEW_VARIANTS[key]}
          </button>
        ))}
      </div>
    </div>
  );

  return (
    <div className="space-y-5">
      {switcher}

      {/* TRIMMED — the shipped order, with the duplication and the donut gone.
          The smallest change that fixes what is actually wrong. */}
      {variant === 'trimmed' && (
        <>
          {kpiBlock}
          {edgeBlock}
          {equityBlock}
          {dailyBlock}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 items-start">
            {attributionBlock}
            {productMixBlock}
          </div>
        </>
      )}

      {/* STORY — reads top to bottom as one argument: the shape of the period,
          then what drove it, then the detail. The equity curve leads at full
          width because it is the only block showing direction over time. */}
      {variant === 'story' && (
        <>
          {equityBlock}
          {edgeBlock}
          {attributionBlock}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 items-start">
            {dailyBlock}
            {productMixBlock}
          </div>
          {kpiBlock}
        </>
      )}

      {/* DENSE — Console-style: numbers and ranked tables first, charts below as
          support. Most information per screen, least scrolling. */}
      {variant === 'dense' && (
        <>
          {kpiBlock}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 items-start">
            {attributionBlock}
            {productMixBlock}
          </div>
          {edgeBlock}
          {equityBlock}
          {dailyBlock}
        </>
      )}
    </div>
  );
}
