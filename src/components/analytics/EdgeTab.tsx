import { useState, useEffect } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, ReferenceLine,
} from 'recharts';
import { RefreshCw, AlertTriangle } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { formatCurrency, formatCurrencyWithSign } from '@/lib/formatters';
import { extractUnderlying, optionType, classifyExpiry } from '@/lib/symbolClassify';
import type { ChartTooltipProps } from '@/lib/chartTooltip';
import { api } from '@/lib/api';

interface EdgeTabProps {
  days: number;
  onInstrumentClick?: (underlying: string) => void;
}

interface PerfData {
  has_data: boolean;
  by_instrument: { symbol: string; trades: number; pnl: number; win_rate: number; avg_pnl: number; avg_duration_min: number }[];
  by_hour: { hour: number; label: string; trades: number; pnl: number; win_rate: number }[];
  // day is the numeric weekday (0=Mon … 6=Sun); name is "Monday"…
  by_day_of_week: { day: number; name: string; trades: number; pnl: number; win_rate: number }[];
  size_analysis: { bucket: string; trades: number; pnl: number; win_rate: number; avg_pnl: number }[];
}

interface HeatmapData {
  has_data: boolean;
  by_hour: { hour: number; label: string; trades: number; pnl: number; win_rate: number }[];
  by_day: { day: number; name: string; trades: number; pnl: number; win_rate: number }[];
}

// ── Symbol classification lives in @/lib/symbolClassify (shared with OverviewTab) ──

function groupByUnderlying(instruments: PerfData['by_instrument']) {
  const map: Record<string, { trades: number; pnl: number; wins: number }> = {};
  for (const instr of instruments) {
    const u = extractUnderlying(instr.symbol);
    if (!map[u]) map[u] = { trades: 0, pnl: 0, wins: 0 };
    map[u].trades += instr.trades;
    map[u].pnl    += instr.pnl;
    map[u].wins   += Math.round(instr.trades * instr.win_rate / 100);
  }
  return Object.entries(map)
    .map(([u, v]) => ({
      underlying: u,
      trades: v.trades,
      pnl: Math.round(v.pnl),
      win_rate: v.trades ? Math.round(v.wins / v.trades * 100) : 0,
      avg_pnl: v.trades ? Math.round(v.pnl / v.trades) : 0,
    }))
    .sort((a, b) => b.trades - a.trades)
    .slice(0, 10);
}

function pnlColor(v: number) { return v >= 0 ? '#16a34a' : '#dc2626'; }

const DAY_ORDER = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'];

// ── F&O Session Windows ──────────────────────────────────────────────────────
const SESSION_WINDOWS = [
  { label: 'Opening',   range: '9:15–10:00', hours: [9] },
  { label: 'Morning',   range: '10:00–12:00', hours: [10, 11] },
  { label: 'Afternoon', range: '12:00–14:00', hours: [12, 13] },
  { label: 'Close',     range: '14:00–15:30', hours: [14, 15] },
];

function buildSessionWindows(byHour: HeatmapData['by_hour']) {
  return SESSION_WINDOWS.map(sw => {
    const rows = byHour.filter(h => sw.hours.includes(h.hour));
    const trades = rows.reduce((s, r) => s + r.trades, 0);
    const totalPnl = rows.reduce((s, r) => s + r.pnl, 0);
    const wins = rows.reduce((s, r) => s + Math.round(r.trades * r.win_rate / 100), 0);
    const win_rate = trades > 0 ? Math.round(wins / trades * 100) : 0;
    const avg_pnl  = trades > 0 ? Math.round(totalPnl / trades) : 0;
    return { label: sw.label, range: sw.range, trades, pnl: Math.round(totalPnl), win_rate, avg_pnl };
  });
}

// ── Tooltips ─────────────────────────────────────────────────────────────────

interface BarRow {
  label: string;
  trades: number;
  avg_pnl: number;
  win_rate: number;
}

function BarTooltip({ active, payload }: ChartTooltipProps<BarRow>) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="bg-popover border border-border rounded-lg px-3 py-2 shadow-lg text-sm">
      <p className="font-medium mb-1">{d.label}</p>
      <p className={cn('font-mono tabular-nums', d.avg_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
        {formatCurrencyWithSign(d.avg_pnl)} avg
      </p>
      <p className="text-xs text-muted-foreground">{d.trades} trades · {d.win_rate}% WR</p>
    </div>
  );
}

function SizeTooltip({ active, payload }: ChartTooltipProps<PerfData['size_analysis'][number]>) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="bg-popover border border-border rounded-lg px-3 py-2 shadow-lg text-sm">
      <p className="font-medium mb-1">{d.bucket}</p>
      <p className={cn('font-mono tabular-nums', d.avg_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
        {formatCurrencyWithSign(d.avg_pnl)} avg P&L
      </p>
      <p className="text-xs text-muted-foreground">{d.trades} trades · {Math.round(d.win_rate)}% WR</p>
    </div>
  );
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function EdgeTab({ days, onInstrumentClick }: EdgeTabProps) {
  const [perf, setPerf]       = useState<PerfData | null>(null);
  const [heatmap, setHeatmap] = useState<HeatmapData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);
  const [retry, setRetry]     = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.allSettled([
      api.get('/api/analytics/performance',    { params: { days } }),
      api.get('/api/analytics/timing-heatmap', { params: { days } }),
    ]).then(([pf, hm]) => {
      if (cancelled) return;
      if (pf.status === 'fulfilled') setPerf(pf.value.data);
      if (hm.status === 'fulfilled') setHeatmap(hm.value.data);
      if (pf.status === 'rejected') setError('Failed to load edge data.');
    }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [days, retry]);

  if (loading) return (
    <div className="space-y-4 animate-pulse">
      <div className="grid grid-cols-2 gap-4">
        <Skeleton className="h-24 rounded-xl" />
        <Skeleton className="h-24 rounded-xl" />
      </div>
      <Skeleton className="h-[260px] rounded-xl" />
      <Skeleton className="h-[200px] rounded-xl" />
      <Skeleton className="h-[200px] rounded-xl" />
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

  // CE/PE/FUT split
  const byInstrument = perf?.by_instrument ?? [];
  const cePnl    = byInstrument.filter(i => optionType(i.symbol) === 'CE').reduce((s, i) => s + i.pnl, 0);
  const pePnl    = byInstrument.filter(i => optionType(i.symbol) === 'PE').reduce((s, i) => s + i.pnl, 0);
  const futPnl   = byInstrument.filter(i => optionType(i.symbol) === 'FUT').reduce((s, i) => s + i.pnl, 0);
  const ceTrades  = byInstrument.filter(i => optionType(i.symbol) === 'CE').reduce((s, i) => s + i.trades, 0);
  const peTrades  = byInstrument.filter(i => optionType(i.symbol) === 'PE').reduce((s, i) => s + i.trades, 0);
  const futTrades = byInstrument.filter(i => optionType(i.symbol) === 'FUT').reduce((s, i) => s + i.trades, 0);

  const grouped = groupByUnderlying(byInstrument);
  const maxAbsPnl = Math.max(...grouped.map(g => Math.abs(g.pnl)), 1);

  // Weekly vs Monthly split
  const weeklyInstr  = byInstrument.filter(i => classifyExpiry(i.symbol) === 'weekly');
  const monthlyInstr = byInstrument.filter(i => classifyExpiry(i.symbol) === 'monthly');
  const wTrades = weeklyInstr.reduce((s, i) => s + i.trades, 0);
  const mTrades = monthlyInstr.reduce((s, i) => s + i.trades, 0);
  const wPnl    = weeklyInstr.reduce((s, i) => s + i.pnl, 0);
  const mPnl    = monthlyInstr.reduce((s, i) => s + i.pnl, 0);
  const wWins   = weeklyInstr.reduce((s, i) => s + Math.round(i.trades * i.win_rate / 100), 0);
  const mWins   = monthlyInstr.reduce((s, i) => s + Math.round(i.trades * i.win_rate / 100), 0);
  const wWR     = wTrades > 0 ? Math.round(wWins / wTrades * 100) : 0;
  const mWR     = mTrades > 0 ? Math.round(mWins / mTrades * 100) : 0;

  // Hour-of-day bar data
  const byHour = heatmap?.by_hour ?? [];
  const hourBarData = byHour.map(h => ({
    label: `${String(h.hour).padStart(2,'0')}:00`,
    hour: h.hour,
    trades: h.trades,
    avg_pnl: h.trades > 0 ? Math.round(h.pnl / h.trades) : 0,
    win_rate: Math.round(h.win_rate),
  }));
  const bestHour  = [...hourBarData].sort((a, b) => b.avg_pnl - a.avg_pnl)[0];
  const worstHour = [...hourBarData].sort((a, b) => a.avg_pnl - b.avg_pnl)[0];

  // Day-of-week bar data — backend `day` is numeric (0=Mon … 6=Sun); keep
  // trading weekdays only. (The old filter compared 'Mon'-style strings
  // against the number, so this chart never rendered.)
  const dowBarData = (perf?.by_day_of_week ?? [])
    .filter(d => d.day >= 0 && d.day <= 4)
    .sort((a, b) => a.day - b.day)
    .map(d => ({
      label: d.name?.slice(0, 3) ?? DAY_ORDER[d.day],
      trades: d.trades,
      avg_pnl: d.trades > 0 ? Math.round(d.pnl / d.trades) : 0,
      win_rate: Math.round(d.win_rate),
    }));
  const bestDow = [...dowBarData].sort((a, b) => b.avg_pnl - a.avg_pnl)[0];

  // F&O session windows
  const sessionWindows = buildSessionWindows(byHour);
  const bestSession  = [...sessionWindows].sort((a, b) => b.avg_pnl - a.avg_pnl)[0];
  const worstSession = [...sessionWindows].sort((a, b) => a.avg_pnl - b.avg_pnl)[0];

  // Position size
  const sizeData = perf?.size_analysis ?? [];

  return (
    <div className="space-y-5">

      {/* CE / PE / FUT Split */}
      {(ceTrades + peTrades + futTrades > 0) && (
        <div className="tm-card overflow-hidden">
          <div className="px-5 py-3.5 border-b border-border">
            <p className="font-semibold text-sm">Options P&L Split</p>
          </div>
          <div className="grid grid-cols-3 divide-x divide-border">
            {[
              { label: 'CALLS (CE)', trades: ceTrades, pnl: cePnl },
              { label: 'PUTS (PE)',  trades: peTrades,  pnl: pePnl },
              { label: 'FUTURES',   trades: futTrades,  pnl: futPnl },
            ].map(({ label, trades, pnl }) => (
              <div key={label} className="px-4 py-3.5">
                <p className="text-[10px] text-muted-foreground uppercase tracking-wide mb-1.5">{label}</p>
                <p className={cn('text-[18px] font-mono font-semibold tabular-nums', pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
                  {formatCurrencyWithSign(Math.round(pnl))}
                </p>
                <p className="text-[11px] text-muted-foreground mt-0.5">{trades} trades</p>
              </div>
            ))}
          </div>
          <p className="px-5 pb-3.5 text-[11px] text-muted-foreground">
            {cePnl + pePnl > 0
              ? cePnl > pePnl ? 'You earn more from calls than puts this period.' : 'You earn more from puts than calls this period.'
              : 'Both calls and puts are net-negative. Review entry criteria.'}
          </p>
        </div>
      )}

      {/* Weekly vs Monthly Options */}
      {(wTrades + mTrades > 0) && (
        <div className="tm-card overflow-hidden">
          <div className="px-5 py-3.5 border-b border-border">
            <p className="font-semibold text-sm">Weekly vs Monthly Options</p>
          </div>
          <div className="grid grid-cols-2 divide-x divide-border">
            {[
              { label: 'Weekly Expiry', trades: wTrades, pnl: wPnl, wr: wWR },
              { label: 'Monthly Expiry', trades: mTrades, pnl: mPnl, wr: mWR },
            ].map(({ label, trades, pnl, wr }) => (
              <div key={label} className="px-5 py-4">
                <p className="text-[11px] text-muted-foreground uppercase tracking-wide mb-2">{label}</p>
                <p className={cn('text-2xl font-mono font-bold tabular-nums', pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
                  {formatCurrencyWithSign(Math.round(pnl))}
                </p>
                <p className="text-[12px] text-muted-foreground mt-0.5">{trades} trades · {wr}% WR</p>
              </div>
            ))}
          </div>
          <p className="px-5 pb-3.5 text-[11px] text-muted-foreground">
            {wTrades > 0 && mTrades > 0
              ? wPnl / Math.max(wTrades, 1) > mPnl / Math.max(mTrades, 1)
                ? `Weekly options give better avg P&L (${formatCurrencyWithSign(Math.round(wPnl / wTrades))} vs ${formatCurrencyWithSign(Math.round(mPnl / mTrades))} per trade).`
                : `Monthly options give better avg P&L (${formatCurrencyWithSign(Math.round(mPnl / mTrades))} vs ${formatCurrencyWithSign(Math.round(wPnl / wTrades))} per trade).`
              : 'Track both weekly and monthly options to discover where your edge lies.'
            }
          </p>
        </div>
      )}

      {/* Instrument Leaderboard */}
      {grouped.length > 0 && (
        <div className="tm-card overflow-hidden">
          <div className="px-5 py-3.5 border-b border-border">
            <p className="font-semibold text-sm">Instrument Leaderboard</p>
          </div>
          <div className="divide-y divide-border">
            {grouped.map((g, i) => {
              const barPct = Math.round(Math.abs(g.pnl) / maxAbsPnl * 100);
              return (
                <button
                  key={g.underlying}
                  onClick={() => onInstrumentClick?.(g.underlying)}
                  className="w-full flex items-center gap-3 px-5 py-3 hover:bg-muted/40 transition-colors text-left"
                >
                  <span className="w-5 text-[12px] text-muted-foreground font-mono shrink-0">{i + 1}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm font-semibold truncate">{g.underlying}</span>
                      <div className="flex items-center gap-3 shrink-0 ml-2">
                        <span className="text-xs text-muted-foreground font-mono">{g.trades} trades</span>
                        <span className={cn('text-sm font-mono font-semibold', g.pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
                          {formatCurrencyWithSign(g.pnl)}
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-1 rounded-full bg-muted/60 overflow-hidden">
                        <div
                          className="h-full rounded-full"
                          style={{ width: `${barPct}%`, backgroundColor: pnlColor(g.pnl) }}
                        />
                      </div>
                      <span className="text-[10px] text-muted-foreground w-10 text-right font-mono shrink-0">
                        {g.win_rate}% WR
                      </span>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
          <p className="px-5 py-3 text-[11px] text-muted-foreground">
            Tap an instrument for a detailed breakdown.
          </p>
        </div>
      )}

      {/* F&O Session Windows */}
      {sessionWindows.some(sw => sw.trades > 0) && (
        <div className="tm-card overflow-hidden">
          <div className="px-5 py-3.5 border-b border-border">
            <p className="font-semibold text-sm">F&O Session Windows</p>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 divide-y md:divide-y-0 divide-x divide-border">
            {sessionWindows.map(sw => (
              <div key={sw.label} className="px-4 py-3.5">
                <p className="text-[10px] text-muted-foreground uppercase tracking-wide mb-0.5">{sw.label}</p>
                <p className="text-[9px] text-muted-foreground/70 mb-2">{sw.range}</p>
                {sw.trades > 0 ? (
                  <>
                    <p className={cn('text-[17px] font-mono font-bold tabular-nums', sw.avg_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
                      {formatCurrencyWithSign(sw.avg_pnl)}
                    </p>
                    <p className="text-[11px] text-muted-foreground mt-0.5">{sw.trades}t · {sw.win_rate}% WR</p>
                  </>
                ) : (
                  <p className="text-[13px] text-muted-foreground/50 font-mono">—</p>
                )}
              </div>
            ))}
          </div>
          <p className="px-5 pb-3.5 text-[11px] text-muted-foreground">
            {bestSession && worstSession && bestSession.trades > 0 && worstSession.trades > 0
              ? `${bestSession.label} is your strongest session (${formatCurrencyWithSign(bestSession.avg_pnl)} avg). ${worstSession.label} is weakest (${formatCurrencyWithSign(worstSession.avg_pnl)} avg).`
              : 'Session performance by time block — where your edge is concentrated.'
            }
          </p>
        </div>
      )}

      {/* Hour-of-Day Bar Chart */}
      {hourBarData.length > 0 && (
        <div className="tm-card overflow-hidden">
          <div className="px-5 py-3.5 border-b border-border">
            <p className="font-semibold text-sm">Hour-of-Day Performance</p>
          </div>
          <div className="p-4">
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={hourBarData} margin={{ top: 4, right: 4, left: -16, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" vertical={false} />
                <XAxis dataKey="label" tick={{ fontSize: 10 }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={v => formatCurrency(v)} />
                <Tooltip content={<BarTooltip />} />
                <ReferenceLine y={0} stroke="rgba(0,0,0,0.15)" />
                <Bar dataKey="avg_pnl" radius={[3, 3, 0, 0]} maxBarSize={36}>
                  {hourBarData.map((d, i) => (
                    <Cell key={i} fill={d.avg_pnl >= 0 ? '#16a34a' : '#dc2626'} opacity={0.8} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <p className="px-5 pb-3.5 text-[11px] text-muted-foreground">
            {bestHour && worstHour
              ? `Best: ${bestHour.label} (${formatCurrencyWithSign(bestHour.avg_pnl)} avg) · Worst: ${worstHour.label} (${formatCurrencyWithSign(worstHour.avg_pnl)} avg)`
              : 'Avg P&L per trade by hour of entry.'
            }
          </p>
        </div>
      )}

      {/* Day-of-Week Bar Chart */}
      {dowBarData.length > 0 && (
        <div className="tm-card overflow-hidden">
          <div className="px-5 py-3.5 border-b border-border">
            <p className="font-semibold text-sm">Day of Week</p>
          </div>
          <div className="p-4">
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={dowBarData} margin={{ top: 4, right: 4, left: -16, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" vertical={false} />
                <XAxis dataKey="label" tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={v => formatCurrency(v)} />
                <Tooltip content={<BarTooltip />} />
                <ReferenceLine y={0} stroke="rgba(0,0,0,0.15)" />
                <Bar dataKey="avg_pnl" radius={[3, 3, 0, 0]} maxBarSize={40}>
                  {dowBarData.map((d, i) => (
                    <Cell key={i} fill={d.avg_pnl >= 0 ? '#16a34a' : '#dc2626'} opacity={0.8} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <p className="px-5 pb-3.5 text-[11px] text-muted-foreground">
            {bestDow
              ? `${bestDow.label} is your best trading day (${formatCurrencyWithSign(bestDow.avg_pnl)} avg per trade · ${bestDow.win_rate}% WR).`
              : 'Avg P&L per trade by day of week.'
            }
          </p>
        </div>
      )}

      {/* Position Size Analysis */}
      {sizeData.length > 0 && (
        <div className="tm-card overflow-hidden">
          <div className="px-5 py-3.5 border-b border-border">
            <p className="font-semibold text-sm">Position Size vs Performance</p>
          </div>
          <div className="p-4">
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={sizeData} margin={{ top: 4, right: 4, left: -16, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" vertical={false} />
                <XAxis dataKey="bucket" tick={{ fontSize: 10 }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={v => formatCurrency(v)} />
                <Tooltip content={<SizeTooltip />} />
                <Bar dataKey="avg_pnl" radius={[3, 3, 0, 0]} maxBarSize={40}>
                  {sizeData.map((d, i) => (
                    <Cell key={i} fill={d.avg_pnl >= 0 ? '#16a34a' : '#dc2626'} opacity={0.8} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <p className="px-5 pb-3.5 text-[11px] text-muted-foreground">
            {sizeData.length > 1 && (() => {
              const best = [...sizeData].sort((a, b) => b.avg_pnl - a.avg_pnl)[0];
              const worst = [...sizeData].sort((a, b) => a.avg_pnl - b.avg_pnl)[0];
              return `Best avg P&L at "${best.bucket}" size (${formatCurrencyWithSign(Math.round(best.avg_pnl))}). Worst at "${worst.bucket}" (${formatCurrencyWithSign(Math.round(worst.avg_pnl))}).`;
            })()}
          </p>
        </div>
      )}

    </div>
  );
}
