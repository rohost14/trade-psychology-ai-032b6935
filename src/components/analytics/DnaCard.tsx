import { useState, useEffect } from 'react';
import { RefreshCw } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';

interface DnaData {
  has_data: boolean;
  narrative: string | null;
  stats?: {
    total_trades: number;
    overall_win_rate: number;
    best_hour?: { label: string; win_rate: number; avg_pnl: number };
    worst_hour?: { label: string; win_rate: number };
    best_instrument?: { symbol: string; win_rate: number };
    worst_instrument?: { symbol: string; win_rate: number };
  };
  reason?: string;
  trade_count?: number;
  min_trades?: number;
  cached_at?: string;
  refresh_limit_hit?: boolean;
}

export default function DnaCard({ days }: { days: number }) {
  const [data, setData]         = useState<DnaData | null>(null);
  const [loading, setLoading]   = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = (force = false) => {
    if (force) setRefreshing(true);
    else setLoading(true);

    api.get('/api/analytics/trading-dna', {
      params: { days_back: days, force_refresh: force },
    })
      .then(r => setData(r.data))
      .catch(() => setData(null))
      .finally(() => { setLoading(false); setRefreshing(false); });
  };

  useEffect(() => { load(false); }, [days]);

  if (loading) return <Skeleton className="h-36 rounded-xl" />;

  if (!data?.has_data) {
    const needed = (data?.min_trades ?? 30) - (data?.trade_count ?? 0);
    return (
      <div className="tm-card p-5">
        <p className="text-sm font-medium text-foreground mb-1">Your Trading Profile</p>
        <p className="text-[12px] text-muted-foreground">
          {needed > 0
            ? `${needed} more trade${needed !== 1 ? 's' : ''} needed to generate your profile.`
            : data?.reason ?? 'Not enough data yet.'}
        </p>
        {data?.trade_count !== undefined && (
          <div className="mt-3 bg-muted/40 rounded-full h-1.5 overflow-hidden">
            <div
              className="h-full bg-tm-brand transition-all"
              style={{ width: `${Math.min(100, ((data.trade_count ?? 0) / (data.min_trades ?? 30)) * 100)}%` }}
            />
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="tm-card overflow-hidden">
      <div className="px-5 py-4 border-b border-border flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-foreground">Your Trading Profile</p>
          {data.cached_at && (
            <p className="text-[10px] text-muted-foreground mt-0.5">
              Based on {data.stats?.total_trades} trades · {data.stats?.overall_win_rate}% overall WR
            </p>
          )}
        </div>
        <button
          onClick={() => load(true)}
          disabled={refreshing || data.refresh_limit_hit}
          title={data.refresh_limit_hit ? 'Refresh limit reached (3/day)' : 'Regenerate profile'}
          className={cn(
            'p-1.5 rounded-md text-muted-foreground hover:text-foreground transition-colors',
            (refreshing || data.refresh_limit_hit) && 'opacity-40 cursor-not-allowed'
          )}
        >
          <RefreshCw className={cn('h-3.5 w-3.5', refreshing && 'animate-spin')} />
        </button>
      </div>
      <div className="px-5 py-4">
        {data.narrative ? (
          <p className="text-[13px] text-foreground leading-relaxed whitespace-pre-line">
            {data.narrative}
          </p>
        ) : (
          <p className="text-[12px] text-muted-foreground italic">
            AI profile unavailable — check API key configuration.
          </p>
        )}
      </div>
    </div>
  );
}
