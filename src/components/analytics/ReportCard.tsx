import { useState, useEffect } from 'react';
import { TrendingUp, TrendingDown, Target, Award, AlertTriangle } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { formatCurrencyWithSign } from '@/lib/formatters';
import { api } from '@/lib/api';

// The Analytics front door: a plain-language, factual synthesis of the period.
// Everything here is the trader's own realized numbers — P&L, win rate, and the
// single strongest place they make money (edge) and lose money (leak). No grade,
// no estimate, no attribution.

interface Kpis {
  total_pnl: number; total_trades: number; win_rate: number;
  /** null = no losing trades in the period (infinite PF — best case) */
  profit_factor: number | null;
  expectancy: number; max_drawdown: number;
}
interface EdgeLeakItem { dimension: string; label: string; trades: number; pnl: number; win_rate: number }

interface Props { days: number }

function Pillar({ icon: Icon, tone, label, value, sub }: {
  icon: typeof Award; tone: 'good' | 'bad' | 'neutral'; label: string; value: string; sub?: string;
}) {
  const toneCls = tone === 'good' ? 'text-tm-profit' : tone === 'bad' ? 'text-tm-loss' : 'text-foreground';
  const bgCls   = tone === 'good' ? 'bg-tm-profit/10' : tone === 'bad' ? 'bg-tm-loss/10' : 'bg-muted';
  return (
    <div className="flex items-start gap-2.5 min-w-0">
      <div className={cn('mt-0.5 h-7 w-7 rounded-lg flex items-center justify-center shrink-0', bgCls)}>
        <Icon className={cn('h-3.5 w-3.5', toneCls)} />
      </div>
      <div className="min-w-0">
        <p className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</p>
        <p className={cn('text-[13px] font-semibold truncate', toneCls)}>{value}</p>
        {sub && <p className="text-[11px] text-muted-foreground truncate">{sub}</p>}
      </div>
    </div>
  );
}

export default function ReportCard({ days }: Props) {
  const [kpis, setKpis]   = useState<Kpis | null>(null);
  const [edge, setEdge]   = useState<EdgeLeakItem | null>(null);
  const [leak, setLeak]   = useState<EdgeLeakItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [empty, setEmpty] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    Promise.allSettled([
      api.get('/api/analytics/overview', { params: { days } }),
      api.get('/api/analytics/edge-leak', { params: { days } }),
    ]).then(([ov, el]) => {
      if (cancelled) return;
      const k = ov.status === 'fulfilled' ? ov.value.data?.kpis : null;
      setKpis(k ?? null);
      setEmpty(!k);
      if (el.status === 'fulfilled' && el.value.data?.has_data) {
        setEdge(el.value.data.edges?.[0] ?? null);
        setLeak(el.value.data.leaks?.[0] ?? null);
      } else { setEdge(null); setLeak(null); }
    }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [days]);

  if (loading) return <Skeleton className="h-40 rounded-2xl" />;
  if (empty || !kpis) return null;

  const positive = kpis.total_pnl >= 0;
  // profit_factor is null when there were NO losing trades — infinite PF,
  // the strongest possible reading, not a missing one.
  const pf = kpis.profit_factor;
  const pfStrong = pf === null || pf >= 1.5;
  const verdict =
    kpis.total_trades < 10 ? 'Early days — not enough trades yet to read a clear trend.'
    : positive && pfStrong ? 'Profitable with a real edge this period.'
    : positive ? 'Net positive, but the edge is thin — protect it.'
    : (pf ?? 0) >= 0.9 ? 'Close to break-even — a small leak is the difference.'
    : 'Losing period. The leak below is where to start.';

  // One factual focus line, derived from the biggest leak (no attribution).
  const focus = leak
    ? `Your biggest drain is ${leak.label.toLowerCase()} (${formatCurrencyWithSign(Math.round(leak.pnl))}).`
    : edge
    ? `Lean into ${edge.label} — your most profitable area.`
    : 'Keep trading to unlock your edge/leak breakdown.';

  return (
    <div className="relative overflow-hidden rounded-2xl border border-border bg-gradient-to-br from-card to-muted/30 px-5 py-5 sm:px-6 sm:py-6">
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
        <div className="min-w-0">
          <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
            Your {days}-day report
          </p>
          <div className="flex items-baseline gap-2.5 mt-1">
            <span className={cn(
              'font-mono font-black tabular-nums leading-none',
              positive ? 'text-tm-profit' : 'text-tm-loss',
            )} style={{ fontSize: 'clamp(30px, 7vw, 44px)' }}>
              {formatCurrencyWithSign(Math.round(kpis.total_pnl))}
            </span>
            {positive
              ? <TrendingUp className="h-5 w-5 text-tm-profit shrink-0" />
              : <TrendingDown className="h-5 w-5 text-tm-loss shrink-0" />}
          </div>
          <p className="text-[13px] text-foreground mt-1.5 max-w-md">{verdict}</p>
        </div>
        <div className="flex items-center gap-4 text-right shrink-0">
          <div>
            <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Win rate</p>
            <p className="text-lg font-mono font-bold tabular-nums text-foreground">{Math.round(kpis.win_rate)}%</p>
          </div>
          <div className="h-8 w-px bg-border" />
          <div>
            <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Profit factor</p>
            <p className={cn('text-lg font-mono font-bold tabular-nums',
              pf === null || pf >= 1.5 ? 'text-tm-profit' : pf >= 1 ? 'text-tm-obs' : 'text-tm-loss')}>
              {pf === null ? '∞' : pf > 0 ? pf.toFixed(2) : '—'}
            </p>
          </div>
        </div>
      </div>

      {/* Pillars: strength / leak / focus — all factual */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-5 pt-4 border-t border-border/70">
        <Pillar
          icon={Award} tone="good" label="Biggest strength"
          value={edge ? `${edge.label}` : '—'}
          sub={edge ? `${formatCurrencyWithSign(Math.round(edge.pnl))} · ${edge.trades} trades` : 'Not enough data'}
        />
        <Pillar
          icon={AlertTriangle} tone="bad" label="Biggest leak"
          value={leak ? `${leak.label}` : '—'}
          sub={leak ? `${formatCurrencyWithSign(Math.round(leak.pnl))} · ${leak.trades} trades` : 'None found'}
        />
        <Pillar
          icon={Target} tone="neutral" label="Where to focus"
          value={focus}
        />
      </div>
    </div>
  );
}
