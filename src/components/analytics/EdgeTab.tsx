import { useState, useEffect } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell,
} from 'recharts';
import { RefreshCw, AlertTriangle } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { formatCurrency, formatCurrencyWithSign } from '@/lib/formatters';
import { api } from '@/lib/api';

interface EdgeTabProps {
  days: number;
  onInstrumentClick?: (underlying: string) => void;
}

interface PerfData {
  has_data: boolean;
  by_instrument: { symbol: string; trades: number; pnl: number; win_rate: number; avg_pnl: number; avg_duration_min: number }[];
  by_hour: { hour: number; label: string; trades: number; pnl: number; win_rate: number }[];
  by_day_of_week: { day: string; trades: number; pnl: number; win_rate: number }[];
  size_analysis: { bucket: string; trades: number; pnl: number; win_rate: number; avg_pnl: number }[];
}

interface HeatmapData {
  has_data: boolean;
  by_hour: { hour: number; trades: number; pnl: number; win_rate: number }[];
  by_day: { day: string; trades: number; pnl: number; win_rate: number }[];
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

function optionType(sym: string): 'CE' | 'PE' | 'FUT' | 'EQ' {
  if (sym.endsWith('CE')) return 'CE';
  if (sym.endsWith('PE')) return 'PE';
  if (sym.endsWith('FUT')) return 'FUT';
  return 'EQ';
}

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
function heatColor(pnl: number, trades: number, maxAbsPnl: number): string {
  if (trades === 0) return 'rgba(0,0,0,0.04)';
  const intensity = Math.min(1, Math.abs(pnl) / (maxAbsPnl || 1));
  if (pnl > 0) return `rgba(22,163,74,${0.15 + intensity * 0.5})`;
  return `rgba(220,38,38,${0.15 + intensity * 0.5})`;
}

const DAY_ORDER = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'];

function SizeTooltip({ active, payload }: any) {
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

export default function EdgeTab({ days, onInstrumentClick }: EdgeTabProps) {
  const [perf, setPerf]         = useState<PerfData | null>(null);
  const [heatmap, setHeatmap]   = useState<HeatmapData | null>(null);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState<string | null>(null);
  const [retry, setRetry]       = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.allSettled([
      api.get('/api/analytics/performance', { params: { days } }),
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
      <Skeleton className="h-[120px] rounded-xl" />
      <Skeleton className="h-[180px] rounded-xl" />
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
  const cePnl   = byInstrument.filter(i => optionType(i.symbol) === 'CE').reduce((s, i) => s + i.pnl, 0);
  const pePnl   = byInstrument.filter(i => optionType(i.symbol) === 'PE').reduce((s, i) => s + i.pnl, 0);
  const futPnl  = byInstrument.filter(i => optionType(i.symbol) === 'FUT').reduce((s, i) => s + i.pnl, 0);
  const ceTrades  = byInstrument.filter(i => optionType(i.symbol) === 'CE').reduce((s, i) => s + i.trades, 0);
  const peTrades  = byInstrument.filter(i => optionType(i.symbol) === 'PE').reduce((s, i) => s + i.trades, 0);
  const futTrades = byInstrument.filter(i => optionType(i.symbol) === 'FUT').reduce((s, i) => s + i.trades, 0);

  const grouped = groupByUnderlying(byInstrument);
  const maxAbsPnl = Math.max(...grouped.map(g => Math.abs(g.pnl)), 1);

  // Heatmap
  const byHour = heatmap?.by_hour ?? [];
  const byDay  = heatmap?.by_day  ?? [];
  const maxHourPnl = Math.max(...byHour.map(h => Math.abs(h.pnl)), 1);
  const maxDayPnl  = Math.max(...byDay.map(d => Math.abs(d.pnl)), 1);

  // Day of week
  const dowData = (perf?.by_day_of_week ?? []).filter(d => DAY_ORDER.includes(d.day));
  dowData.sort((a, b) => DAY_ORDER.indexOf(a.day) - DAY_ORDER.indexOf(b.day));

  // Size analysis
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

      {/* Time-of-Day Grid */}
      {byHour.length > 0 && (
        <div className="tm-card overflow-hidden">
          <div className="px-5 py-3.5 border-b border-border">
            <p className="font-semibold text-sm">Hour-of-Day Performance</p>
          </div>
          <div className="p-4">
            <div className="grid gap-1.5" style={{ gridTemplateColumns: `repeat(${byHour.length}, 1fr)` }}>
              {byHour.map(h => (
                <div key={h.hour} className="flex flex-col items-center gap-1">
                  <div
                    className="w-full rounded-md flex items-center justify-center text-[10px] font-mono font-semibold"
                    style={{
                      height: 40,
                      backgroundColor: heatColor(h.pnl, h.trades, maxHourPnl),
                      color: Math.abs(h.pnl) / (maxHourPnl || 1) > 0.4 ? 'white' : undefined,
                    }}
                    title={`${String(h.hour).padStart(2,'0')}:00 — ${formatCurrencyWithSign(Math.round(h.pnl))} · ${h.trades} trades · ${Math.round(h.win_rate)}% WR`}
                  >
                    {h.trades > 0 ? `${Math.round(h.win_rate)}%` : ''}
                  </div>
                  <span className="text-[9px] text-muted-foreground">{String(h.hour).padStart(2,'0')}</span>
                </div>
              ))}
            </div>
            <div className="flex items-center gap-4 mt-3 text-[10px] text-muted-foreground">
              <div className="flex items-center gap-1"><div className="w-3 h-3 rounded" style={{ backgroundColor: 'rgba(22,163,74,0.6)' }} /> Profitable</div>
              <div className="flex items-center gap-1"><div className="w-3 h-3 rounded" style={{ backgroundColor: 'rgba(220,38,38,0.6)' }} /> Losing</div>
              <div className="flex items-center gap-1"><div className="w-3 h-3 rounded" style={{ backgroundColor: 'rgba(0,0,0,0.06)' }} /> No trades</div>
            </div>
          </div>
          <p className="px-5 pb-3.5 text-[11px] text-muted-foreground">
            {byHour.length > 0 && (() => {
              const best = [...byHour].sort((a, b) => b.pnl - a.pnl)[0];
              const worst = [...byHour].sort((a, b) => a.pnl - b.pnl)[0];
              return `Best hour: ${String(best.hour).padStart(2,'0')}:00 (${formatCurrencyWithSign(Math.round(best.pnl))}) · Worst: ${String(worst.hour).padStart(2,'0')}:00 (${formatCurrencyWithSign(Math.round(worst.pnl))})`;
            })()}
          </p>
        </div>
      )}

      {/* Day of Week */}
      {dowData.length > 0 && (
        <div className="tm-card overflow-hidden">
          <div className="px-5 py-3.5 border-b border-border">
            <p className="font-semibold text-sm">Day of Week</p>
          </div>
          <div className="p-4">
            <div className="grid grid-cols-5 gap-2">
              {DAY_ORDER.map(day => {
                const d = dowData.find(x => x.day === day);
                if (!d) return (
                  <div key={day} className="flex flex-col items-center gap-1">
                    <div className="w-full h-12 rounded-lg bg-muted/30" />
                    <span className="text-[11px] text-muted-foreground">{day}</span>
                  </div>
                );
                return (
                  <div key={day} className="flex flex-col items-center gap-1">
                    <div
                      className="w-full h-12 rounded-lg flex flex-col items-center justify-center gap-0.5"
                      style={{ backgroundColor: heatColor(d.pnl, d.trades, maxDayPnl) }}
                    >
                      <span className="text-[10px] font-mono font-semibold">{Math.round(d.win_rate)}%</span>
                      <span className="text-[9px] text-muted-foreground">{d.trades}t</span>
                    </div>
                    <span className="text-[11px] text-muted-foreground">{day}</span>
                  </div>
                );
              })}
            </div>
          </div>
          <p className="px-5 pb-3.5 text-[11px] text-muted-foreground">
            {dowData.length > 0 && (() => {
              const best = [...dowData].sort((a, b) => b.pnl - a.pnl)[0];
              return `${best.day} is your most profitable trading day (${formatCurrencyWithSign(Math.round(best.pnl))} total).`;
            })()}
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
