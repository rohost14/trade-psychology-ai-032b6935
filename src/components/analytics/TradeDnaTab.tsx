import { useState, useEffect } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, ReferenceLine,
} from 'recharts';
import { RefreshCw, AlertTriangle, Search, TrendingUp, TrendingDown, Shield, AlertCircle } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { formatCurrency, formatCurrencyWithSign } from '@/lib/formatters';
import { api } from '@/lib/api';

interface TradeDnaTabProps { days: number }

interface QualityData {
  has_data: boolean;
  period_days: number;
  clean: { count: number; avg_pnl: number; win_rate: number } | null;
  flagged: { count: number; avg_pnl: number; win_rate: number } | null;
  trades: { id: string; tradingsymbol: string; score: number; realized_pnl: number; entry_time: string; exit_time: string }[];
}

interface CriticalTrade {
  id: string; tradingsymbol: string; realized_pnl: number;
  entry_time: string; exit_time: string;
  flag_reasons: { type: string; label: string }[];
}

interface CriticalData {
  has_data: boolean;
  total_critical: number;
  trades: CriticalTrade[];
}

interface PnlPctData {
  has_data: boolean;
  avg_win_pct: number; avg_loss_pct: number; rr_ratio: number;
  disposition_ratio: number;
  by_hold_time: { bucket: string; trades: number; win_rate: number; avg_pnl: number }[];
}

interface SequenceData {
  has_data: boolean;
  baseline_win_rate: number;
  baseline_avg_pnl: number;
  sequence: { ordinal: number; label: string; trade_count: number; win_rate: number; avg_pnl: number; delta_win_rate: number }[];
}

function fmtTime(s: string) {
  return new Date(s).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
}

function SeqTooltip({ active, payload, baseline }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="bg-popover border border-border rounded-lg px-3 py-2 shadow-lg text-sm">
      <p className="font-medium mb-1">Trade {d.label}</p>
      <p className={cn('font-mono tabular-nums', d.win_rate >= baseline ? 'text-tm-profit' : 'text-tm-loss')}>
        {d.win_rate}% WR
      </p>
      <p className="text-xs text-muted-foreground">{d.trade_count} trades · {formatCurrencyWithSign(d.avg_pnl)} avg</p>
      <p className={cn('text-xs mt-0.5', d.delta_win_rate >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
        {d.delta_win_rate > 0 ? '+' : ''}{d.delta_win_rate}% vs baseline
      </p>
    </div>
  );
}

function HoldTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="bg-popover border border-border rounded-lg px-3 py-2 shadow-lg text-sm">
      <p className="font-medium mb-1">{d.bucket}</p>
      <p className={cn('font-mono tabular-nums', d.avg_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
        {formatCurrencyWithSign(d.avg_pnl)} avg
      </p>
      <p className="text-xs text-muted-foreground">{d.trades} trades · {Math.round(d.win_rate)}% WR</p>
    </div>
  );
}

export default function TradeDnaTab({ days }: TradeDnaTabProps) {
  const [quality, setQuality]     = useState<QualityData | null>(null);
  const [critical, setCritical]   = useState<CriticalData | null>(null);
  const [pnlPct, setPnlPct]       = useState<PnlPctData | null>(null);
  const [sequence, setSequence]   = useState<SequenceData | null>(null);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState<string | null>(null);
  const [retry, setRetry]         = useState(0);
  const [search, setSearch]       = useState('');

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.allSettled([
      api.get('/api/analytics/quality-breakdown', { params: { days_back: days } }),
      api.get('/api/analytics/critical-trades',   { params: { days } }),
      api.get('/api/analytics/pnl-percent',       { params: { days } }),
      api.get('/api/analytics/trade-sequence',    { params: { days } }),
    ]).then(([q, c, p, s]) => {
      if (cancelled) return;
      if (q.status === 'fulfilled') setQuality(q.value.data);
      if (c.status === 'fulfilled') {
        const d = c.value.data;
        // API returns trades sorted worst-first; derive best_5 from quality breakdown below
        setCritical(d);
      }
      if (p.status === 'fulfilled') setPnlPct(p.value.data);
      if (s.status === 'fulfilled') setSequence(s.value.data);
      if (q.status === 'rejected') setError('Failed to load trade DNA data.');
    }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [days, retry]);

  if (loading) return (
    <div className="space-y-4 animate-pulse">
      <Skeleton className="h-24 rounded-xl" />
      <div className="grid grid-cols-2 gap-4">
        <Skeleton className="h-[220px] rounded-xl" />
        <Skeleton className="h-[220px] rounded-xl" />
      </div>
      <Skeleton className="h-[200px] rounded-xl" />
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

  const baseline = sequence?.baseline_win_rate ?? 0;
  const hasSeq   = sequence?.has_data && (sequence.sequence?.length ?? 0) > 1;

  // Worst 5 from critical-trades (already sorted worst-first)
  const worst5 = (critical?.trades ?? []).slice(0, 5);
  // Best 5 derived from quality breakdown trades sorted by pnl desc
  const best5  = [...(quality?.trades ?? [])].sort((a, b) => b.realized_pnl - a.realized_pnl).slice(0, 5);

  // Trade log from quality data
  const allTrades = quality?.trades ?? [];
  const filtered  = search
    ? allTrades.filter(t => t.tradingsymbol.toLowerCase().includes(search.toLowerCase()))
    : allTrades;

  return (
    <div className="space-y-5">

      {/* Quality Banner */}
      {quality?.has_data && quality.clean && quality.flagged && (
        <div className="tm-card overflow-hidden">
          <div className="px-5 py-3.5 border-b border-border">
            <p className="font-semibold text-sm">Trade Quality</p>
          </div>
          <div className="grid grid-cols-2 divide-x divide-border">
            <div className="px-5 py-4">
              <div className="flex items-center gap-2 mb-2">
                <Shield className="h-4 w-4 text-tm-profit" />
                <span className="text-sm font-medium text-tm-profit">Clean trades</span>
              </div>
              <p className="text-2xl font-mono font-bold tabular-nums text-foreground">{quality.clean.count}</p>
              <p className="text-sm text-muted-foreground mt-0.5">
                Avg {formatCurrencyWithSign(Math.round(quality.clean.avg_pnl))} · {Math.round(quality.clean.win_rate)}% WR
              </p>
            </div>
            <div className="px-5 py-4">
              <div className="flex items-center gap-2 mb-2">
                <AlertCircle className="h-4 w-4 text-tm-obs" />
                <span className="text-sm font-medium text-tm-obs">Flagged trades</span>
              </div>
              <p className="text-2xl font-mono font-bold tabular-nums text-foreground">{quality.flagged.count}</p>
              <p className="text-sm text-muted-foreground mt-0.5">
                Avg {formatCurrencyWithSign(Math.round(quality.flagged.avg_pnl))} · {Math.round(quality.flagged.win_rate)}% WR
              </p>
            </div>
          </div>
          {quality.clean.avg_pnl > quality.flagged.avg_pnl && (
            <div className="px-5 py-3 border-t border-border bg-green-500/5">
              <p className="text-[12px] text-tm-profit">
                Clean trades return {formatCurrencyWithSign(Math.round(quality.clean.avg_pnl - quality.flagged.avg_pnl))} more per trade on average.
                Ignoring behavioral alerts costs you.
              </p>
            </div>
          )}
        </div>
      )}

      {/* Best 5 / Worst 5 */}
      {(worst5.length > 0 || best5.length > 0) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

          {worst5.length > 0 && (
            <div className="tm-card overflow-hidden">
              <div className="px-5 py-3.5 border-b border-border flex items-center gap-2">
                <TrendingDown className="h-4 w-4 text-tm-loss" />
                <p className="font-semibold text-sm">Worst 5 Trades</p>
              </div>
              <div className="divide-y divide-border">
                {worst5.map(t => (
                  <div key={t.id} className="px-5 py-3">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="text-sm font-semibold truncate">{t.tradingsymbol}</p>
                        <p className="text-[11px] text-muted-foreground">{fmtTime(t.entry_time)}</p>
                        {t.flag_reasons?.length > 0 && (
                          <div className="flex flex-wrap gap-1 mt-1">
                            {t.flag_reasons.slice(0, 2).map(r => (
                              <span key={r.type} className="text-[10px] bg-tm-obs/10 text-tm-obs px-1.5 py-0.5 rounded-full">{r.label}</span>
                            ))}
                          </div>
                        )}
                      </div>
                      <p className="text-sm font-mono font-semibold text-tm-loss shrink-0">
                        {formatCurrencyWithSign(Math.round(t.realized_pnl))}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {best5.length > 0 && (
            <div className="tm-card overflow-hidden">
              <div className="px-5 py-3.5 border-b border-border flex items-center gap-2">
                <TrendingUp className="h-4 w-4 text-tm-profit" />
                <p className="font-semibold text-sm">Best 5 Trades</p>
              </div>
              <div className="divide-y divide-border">
                {best5.map(t => (
                  <div key={t.id} className="px-5 py-3">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="text-sm font-semibold truncate">{t.tradingsymbol}</p>
                        <p className="text-[11px] text-muted-foreground">{fmtTime(t.entry_time)}</p>
                      </div>
                      <p className="text-sm font-mono font-semibold text-tm-profit shrink-0">
                        {formatCurrencyWithSign(Math.round(t.realized_pnl))}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* R:R + Disposition */}
      {pnlPct?.has_data && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="tm-card overflow-hidden">
            <div className="px-5 py-3.5 border-b border-border">
              <p className="font-semibold text-sm">Risk : Reward</p>
            </div>
            <div className="p-5 space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-sm text-muted-foreground">Avg win</span>
                <span className="font-mono font-semibold text-tm-profit">+{pnlPct.avg_win_pct?.toFixed(1)}%</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-muted-foreground">Avg loss</span>
                <span className="font-mono font-semibold text-tm-loss">{pnlPct.avg_loss_pct?.toFixed(1)}%</span>
              </div>
              <div className="border-t border-border pt-3 flex justify-between items-center">
                <span className="text-sm font-medium">R:R Ratio</span>
                <span className={cn('text-lg font-mono font-bold', (pnlPct.rr_ratio ?? 0) >= 1 ? 'text-tm-profit' : 'text-tm-loss')}>
                  1 : {pnlPct.rr_ratio?.toFixed(2) ?? '—'}
                </span>
              </div>
            </div>
            <p className="px-5 pb-3.5 text-[11px] text-muted-foreground">
              {(pnlPct.rr_ratio ?? 0) >= 2
                ? 'Strong R:R. Winners significantly outpace losers.'
                : (pnlPct.rr_ratio ?? 0) >= 1
                ? 'Positive R:R. Each winner covers more than one loser.'
                : 'Negative R:R. Losers cost more than winners earn — win rate must be high to survive.'}
            </p>
          </div>

          <div className="tm-card overflow-hidden">
            <div className="px-5 py-3.5 border-b border-border">
              <p className="font-semibold text-sm">Disposition Effect</p>
            </div>
            <div className="p-5">
              <div className="flex items-end gap-2 mb-3">
                <span className={cn(
                  'text-4xl font-mono font-black tabular-nums',
                  (pnlPct.disposition_ratio ?? 0) > 1.2 ? 'text-tm-loss' : 'text-tm-profit',
                )}>
                  {pnlPct.disposition_ratio?.toFixed(2) ?? '—'}
                </span>
                <span className="text-sm text-muted-foreground pb-1">ratio</span>
              </div>
              <p className="text-[12px] text-muted-foreground">
                {(pnlPct.disposition_ratio ?? 0) > 1.5
                  ? 'Strong disposition effect: you sell winners too early and hold losers too long. This is costing you significantly.'
                  : (pnlPct.disposition_ratio ?? 0) > 1.1
                  ? 'Mild disposition effect: slight tendency to exit winners early and let losers run.'
                  : 'No significant disposition effect. You let winners run as long as losers.'}
              </p>
            </div>
            <p className="px-5 pb-3.5 text-[11px] text-muted-foreground">
              {'>1.0'} = cut winners early · {'<1.0'} = cut losers early
            </p>
          </div>
        </div>
      )}

      {/* Trade Sequence Chart */}
      {hasSeq && (
        <div className="tm-card overflow-hidden">
          <div className="px-5 py-3.5 border-b border-border">
            <p className="font-semibold text-sm">Intraday Trade Sequence</p>
          </div>
          <div className="p-4">
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={sequence!.sequence} margin={{ top: 4, right: 4, left: -16, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" vertical={false} />
                <XAxis dataKey="label" tick={{ fontSize: 10 }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fontSize: 10 }} tickLine={false} axisLine={false} unit="%" domain={[0, 100]} />
                <Tooltip content={<SeqTooltip baseline={baseline} />} />
                <ReferenceLine y={baseline} stroke="#0d9488" strokeDasharray="4 4" label={{ value: `Baseline ${baseline}%`, position: 'insideTopRight', fontSize: 10, fill: '#0d9488' }} />
                <Bar dataKey="win_rate" radius={[3, 3, 0, 0]} maxBarSize={40}>
                  {sequence!.sequence.map((d, i) => (
                    <Cell key={i} fill={d.win_rate >= baseline ? '#16a34a' : '#dc2626'} opacity={0.8} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <p className="px-5 pb-3.5 text-[11px] text-muted-foreground">
            {(() => {
              const degraded = sequence!.sequence.find(s => s.delta_win_rate < -10);
              if (degraded) return `Win rate drops below baseline after trade ${degraded.label}. Consider stopping at ${degraded.ordinal - 1} trades per day.`;
              return `Win rate remains consistent across all trade ordinals — no overtrading signal detected.`;
            })()}
          </p>
        </div>
      )}

      {/* Hold-time breakdown */}
      {pnlPct?.has_data && pnlPct.by_hold_time && pnlPct.by_hold_time.length > 0 && (
        <div className="tm-card overflow-hidden">
          <div className="px-5 py-3.5 border-b border-border">
            <p className="font-semibold text-sm">Hold Time vs Performance</p>
          </div>
          <div className="p-4">
            <ResponsiveContainer width="100%" height={160}>
              <BarChart data={pnlPct.by_hold_time} margin={{ top: 4, right: 4, left: -16, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" vertical={false} />
                <XAxis dataKey="bucket" tick={{ fontSize: 10 }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={v => formatCurrency(v)} />
                <Tooltip content={<HoldTooltip />} />
                <ReferenceLine y={0} stroke="rgba(0,0,0,0.15)" />
                <Bar dataKey="avg_pnl" radius={[3, 3, 0, 0]} maxBarSize={36}>
                  {pnlPct.by_hold_time.map((d, i) => (
                    <Cell key={i} fill={d.avg_pnl >= 0 ? '#16a34a' : '#dc2626'} opacity={0.8} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <p className="px-5 pb-3.5 text-[11px] text-muted-foreground">
            {(() => {
              const best = [...pnlPct.by_hold_time].sort((a, b) => b.avg_pnl - a.avg_pnl)[0];
              return `Best avg P&L in "${best.bucket}" hold-time bucket (${formatCurrencyWithSign(Math.round(best.avg_pnl))}).`;
            })()}
          </p>
        </div>
      )}

      {/* Compact Trade Log */}
      {allTrades.length > 0 && (
        <div className="tm-card overflow-hidden">
          <div className="px-5 py-3.5 border-b border-border flex items-center justify-between gap-3">
            <p className="font-semibold text-sm">Trade Log</p>
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground pointer-events-none" />
              <input
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Search symbol…"
                className="pl-8 pr-3 py-1.5 text-[12px] rounded-lg border border-border bg-muted/40 focus:outline-none focus:ring-1 focus:ring-tm-brand w-40"
              />
            </div>
          </div>
          <div className="divide-y divide-border max-h-[400px] overflow-y-auto">
            {filtered.slice(0, 50).map(t => (
              <div key={t.id} className="px-5 py-2.5 flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-sm font-medium truncate">{t.tradingsymbol}</p>
                  <p className="text-[11px] text-muted-foreground">{fmtTime(t.entry_time)}</p>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <span className={cn(
                    'text-[10px] px-1.5 py-0.5 rounded-full',
                    t.score >= 6 ? 'bg-green-500/10 text-tm-profit' :
                    t.score >= 4 ? 'bg-amber-500/10 text-tm-obs' : 'bg-red-500/10 text-tm-loss',
                  )}>
                    Q{t.score}
                  </span>
                  <span className={cn('text-sm font-mono font-semibold', t.realized_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
                    {formatCurrencyWithSign(Math.round(t.realized_pnl))}
                  </span>
                </div>
              </div>
            ))}
            {filtered.length > 50 && (
              <div className="px-5 py-3 text-center text-xs text-muted-foreground">
                Showing 50 of {filtered.length} trades. Narrow your search.
              </div>
            )}
          </div>
        </div>
      )}

    </div>
  );
}
