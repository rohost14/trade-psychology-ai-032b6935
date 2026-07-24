/**
 * Session tagging — each trading DAY labelled by its dominant behaviour (from the patterns
 * that fired that day) with the day's realized P&L, plus what the worst days share. Factual,
 * 0-input, raw P&L. Built from trading_sessions + behavior_events (data already stored).
 */
import { useEffect, useState } from 'react';
import { CalendarDays, Info } from 'lucide-react';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';

interface Day { date: string; pnl: number; trades: number; alerts: number; peak_risk: number; tag: string; top_patterns: string[]; }
interface Data { has_data: boolean; days: Day[]; insight: { tag: string; count: number; of: number } | null; }

const TAG: Record<string, { label: string; cls: string }> = {
  clean:       { label: 'Clean',       cls: 'text-tm-profit bg-tm-profit/10' },
  revenge:     { label: 'Revenge / tilt', cls: 'text-tm-loss bg-tm-loss/10' },
  size_tilt:   { label: 'Size tilt',   cls: 'text-tm-loss bg-tm-loss/10' },
  overtrading: { label: 'Overtrading', cls: 'text-tm-obs bg-tm-obs/10' },
  flagged:     { label: 'Flagged',     cls: 'text-tm-obs bg-tm-obs/10' },
  normal:      { label: 'Normal',      cls: 'text-muted-foreground bg-muted' },
};
const inr = (n: number) => (n < 0 ? '-' : '') + '₹' + Math.abs(Math.round(n)).toLocaleString('en-IN');
const fmtDay = (iso: string) => new Date(iso + 'T00:00:00').toLocaleDateString('en-IN', { day: '2-digit', month: 'short', weekday: 'short' });

export default function SessionLog({ days = 60 }: { days?: number }) {
  const [data, setData] = useState<Data | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api.get<Data>(`/api/analytics/session-log?days=${days}`)
      .then(res => { if (!cancelled) setData(res.data); })
      .catch(() => { if (!cancelled) setData(null); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [days]);

  if (loading || !data || !data.has_data) return null;

  const tag = (t: string) => TAG[t] ?? TAG.normal;

  return (
    <div className="tm-card overflow-hidden">
      <div className="px-5 py-3.5 border-b border-border">
        <p className="text-sm font-semibold text-foreground flex items-center gap-2">
          <CalendarDays className="h-4 w-4 text-tm-brand" /> Your trading days
        </p>
        <p className="text-xs text-muted-foreground mt-0.5">Each day tagged by its dominant behaviour, with realized P&amp;L.</p>
      </div>

      <div className="p-5 space-y-4">
        {data.insight && (
          <div className="flex items-start gap-2 text-[13px] rounded-lg px-3.5 py-2.5 bg-tm-loss/8 border border-tm-loss/20">
            <Info className="h-4 w-4 text-tm-loss shrink-0 mt-0.5" />
            <span className="text-foreground">
              <strong>{data.insight.count} of your {data.insight.of} worst days</strong> were{' '}
              <strong>{tag(data.insight.tag).label}</strong> days. That's the pattern to break.
            </span>
          </div>
        )}

        <div className="space-y-1.5 max-h-[420px] overflow-y-auto">
          {data.days.map(d => (
            <div key={d.date} className="grid items-center gap-3 py-1.5 border-b border-border last:border-0 [grid-template-columns:96px_110px_1fr_92px]">
              <span className="text-xs text-muted-foreground">{fmtDay(d.date)}</span>
              <span className={cn('text-[11px] font-semibold px-2 py-0.5 rounded-full w-fit', tag(d.tag).cls)}>{tag(d.tag).label}</span>
              <span className="text-[11px] text-muted-foreground truncate">
                {d.trades} trades{d.alerts > 0 ? ` · ${d.alerts} alerts` : ''}
              </span>
              <span className={cn('text-[13px] font-semibold tabular-nums text-right', d.pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>{inr(d.pnl)}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
