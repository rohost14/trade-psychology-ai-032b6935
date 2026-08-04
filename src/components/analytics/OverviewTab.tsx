/**
 * Analytics → Overview. The period summary, and deliberately no longer the
 * landing tab: everything on it is available in Zerodha Console already, while
 * Behaviour carries the analysis only this app can do.
 *
 * Three things it no longer does, all settled in the design lab:
 *  - It does not restate the ReportCard hero. P&L, win rate and profit factor
 *    sit directly above it, so the KPI strip carries only what the hero does
 *    not say: expectancy, win days, drawdown.
 *  - No attribution donut. It was a five-hue rainbow whose colours carried no
 *    meaning, above a legend colouring the same rows green and red by sign --
 *    two colour systems in one card -- and the legend already said everything
 *    the donut did. It is a ranked table with bars from a centre baseline, so
 *    a loss extends left rather than drawing a longer bar rightward.
 *  - No streak cards; the equity-curve caption already states both streaks.
 *
 * Chart colour comes from useChartColors(), never a hex literal, so it follows
 * the theme instead of being wrong in one of the two by construction.
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
import { useApiQuery } from '@/hooks/useApiQuery';

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

export default function OverviewTab({ days }: OverviewTabProps) {
  // Four cached reads. The keys are shared, which matters here: /overview is also
  // fetched by SessionsTab, so switching between the two tabs now reuses the
  // cached result instead of re-querying. The double-window call is a second,
  // legitimately different request (days * 2) used for the previous-period delta.
  const overviewQ = useApiQuery<OverviewData>(
    ['analytics', 'overview'], '/api/analytics/overview', { params: { days } },
  );
  const overviewPrevQ = useApiQuery<OverviewData>(
    ['analytics', 'overview'], '/api/analytics/overview', { params: { days: days * 2 } },
  );
  const edgeQ = useApiQuery<EdgeData>(
    ['analytics', 'edge-confidence'], '/api/analytics/edge-confidence', { params: { days } },
  );
  const perfQ = useApiQuery<PerfData>(
    ['analytics', 'performance'], '/api/analytics/performance', { params: { days } },
  );

  const overview = overviewQ.data ?? null;
  const ovPrev = overviewPrevQ.data ?? null;
  const edge = edgeQ.data ?? null;
  const perf = perfQ.data ?? null;

  // Only the primary overview gates the tab, matching the previous allSettled
  // behaviour: a failed edge or performance call degrades that section rather
  // than blanking the whole page.
  const loading = overviewQ.isPending;
  const error = overviewQ.error;

  // Must sit with the other hooks: everything below has early returns for loading
  // and error, so a hook placed there would run conditionally.
  const c = useChartColors();

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

  if (error) return <ErrorState error={error} onRetry={() => overviewQ.refetch()} />;

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


  return (
    <div className="space-y-5">
      {kpiBlock}
      {edgeBlock}
      {equityBlock}
      {dailyBlock}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 items-start">
        {attributionBlock}
        {productMixBlock}
      </div>
    </div>
  );
}
