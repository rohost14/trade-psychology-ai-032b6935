import { useState, useEffect } from 'react';
import { ArrowUpRight, ArrowDownRight } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { formatCurrencyWithSign } from '@/lib/formatters';
import { api } from '@/lib/api';

// "Where you make money / where you lose money" — a factual ranking of the trader's
// own realized P&L by bucket (instrument, time, day, product, type). Sample-gated
// server-side (min trades) so nothing here is a fluke. No estimate, no attribution.

interface Item { dimension: string; label: string; trades: number; pnl: number; win_rate: number }
interface Data { has_data: boolean; min_trades: number; edges: Item[]; leaks: Item[] }
interface Props { days: number }

function Row({ item, good }: { item: Item; good: boolean }) {
  return (
    <div className="flex items-center justify-between gap-3 px-4 py-2.5">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-[13px] font-medium text-foreground truncate">{item.label}</span>
          <span className="text-[9px] uppercase tracking-wide text-muted-foreground border border-border rounded px-1 py-px shrink-0">
            {item.dimension}
          </span>
        </div>
        <p className="text-[11px] text-muted-foreground">{item.trades} trades · {Math.round(item.win_rate)}% WR</p>
      </div>
      <span className={cn('font-mono font-semibold tabular-nums text-sm shrink-0', good ? 'text-tm-profit' : 'text-tm-loss')}>
        {formatCurrencyWithSign(Math.round(item.pnl))}
      </span>
    </div>
  );
}

function Column({ title, icon: Icon, items, good, empty }: {
  title: string; icon: typeof ArrowUpRight; items: Item[]; good: boolean; empty: string;
}) {
  return (
    <div className="tm-card overflow-hidden">
      <div className="px-4 py-3 border-b border-border flex items-center gap-2">
        <Icon className={cn('h-4 w-4', good ? 'text-tm-profit' : 'text-tm-loss')} />
        <p className="font-semibold text-sm">{title}</p>
      </div>
      {items.length > 0 ? (
        <div className="divide-y divide-border">
          {items.map(it => <Row key={`${it.dimension}-${it.label}`} item={it} good={good} />)}
        </div>
      ) : (
        <p className="px-4 py-6 text-center text-[12px] text-muted-foreground">{empty}</p>
      )}
    </div>
  );
}

export default function EdgeLeakCard({ days }: Props) {
  const [data, setData] = useState<Data | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api.get('/api/analytics/edge-leak', { params: { days } })
      .then(r => { if (!cancelled) setData(r.data); })
      .catch(() => { if (!cancelled) setData(null); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [days]);

  if (loading) return <Skeleton className="h-56 rounded-xl" />;
  if (!data?.has_data) return null;

  return (
    <div className="space-y-2.5">
      <p className="text-[12px] text-muted-foreground">
        Where your money actually comes from and goes — buckets with at least {data.min_trades} trades.
      </p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Column title="Where you make money" icon={ArrowUpRight} items={data.edges} good empty="No consistently profitable bucket yet." />
        <Column title="Where you lose money"  icon={ArrowDownRight} items={data.leaks} good={false} empty="No consistent leak — nice." />
      </div>
    </div>
  );
}
