import { useState, useEffect } from 'react';
import { Layers } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { useChartColors } from '@/hooks/useChartColors';
import { formatCurrencyWithSign } from '@/lib/formatters';
import { api } from '@/lib/api';

// Realized P&L by STRATEGY — multi-leg (straddle/strangle/spread, from the strategy
// detector) and single-leg (Call/Put buys/sells, Futures, Equity). Brokers don't
// show this. All figures are the trader's own realized P&L.

interface Strat {
  kind: 'multi_leg' | 'single_leg';
  key: string; label: string;
  trades: number; pnl: number; win_rate: number; avg_pnl: number;
}
interface Data { has_data: boolean; strategies: Strat[] }
interface Props { days: number }

export default function StrategyCard({ days }: Props) {
  const c = useChartColors();
  const [data, setData] = useState<Data | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api.get('/api/analytics/strategy-performance', { params: { days } })
      .then(r => { if (!cancelled) setData(r.data); })
      .catch(() => { if (!cancelled) setData(null); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [days]);

  if (loading) return <Skeleton className="h-52 rounded-lg" />;
  if (!data?.has_data) return null;

  const rows = data.strategies.filter(s => s.trades > 0);
  const maxAbs = Math.max(...rows.map(s => Math.abs(s.pnl)), 1);

  return (
    <div className="tm-card overflow-hidden">
      <div className="px-5 py-3.5 border-b border-border flex items-center gap-2">
        <Layers className="h-4 w-4 text-tm-brand" />
        <p className="font-semibold text-sm">Performance by strategy</p>
      </div>
      <div className="divide-y divide-border">
        {rows.map(s => {
          const good = s.pnl >= 0;
          const barPct = Math.round(Math.abs(s.pnl) / maxAbs * 100);
          return (
            <div key={`${s.kind}-${s.key}`} className="px-5 py-3">
              <div className="flex items-center justify-between gap-3 mb-1.5">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="text-[13px] font-medium text-foreground truncate">{s.label}</span>
                  {s.kind === 'multi_leg' && (
                    <span className="text-[9px] uppercase tracking-wide text-tm-brand border border-tm-brand/30 rounded px-1 py-px shrink-0">
                      multi-leg
                    </span>
                  )}
                </div>
                <span className={cn('font-mono font-semibold tabular-nums text-sm shrink-0', good ? 'text-tm-profit' : 'text-tm-loss')}>
                  {formatCurrencyWithSign(Math.round(s.pnl))}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <div className="flex-1 h-1 rounded-full bg-muted/60 overflow-hidden">
                  <div className="h-full rounded-full" style={{ width: `${barPct}%`, backgroundColor: good ? c.profit : c.loss }} />
                </div>
                <span className="text-[10px] text-muted-foreground w-28 text-right shrink-0">
                  {s.trades} trades · {Math.round(s.win_rate)}% WR
                </span>
              </div>
            </div>
          );
        })}
      </div>
      <p className="px-5 py-3 text-[11px] text-muted-foreground border-t border-border">
        Multi-leg strategies are auto-detected (straddle, strangle, spread…). Single-leg trades are grouped by shape.
      </p>
    </div>
  );
}
