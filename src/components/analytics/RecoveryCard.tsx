import { useState, useEffect } from 'react';
import { TrendingDown } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { formatCurrency, formatCurrencyWithSign } from '@/lib/formatters';
import { api } from '@/lib/api';

interface RecoveryData {
  has_data: boolean;
  reason?: string;
  bad_day_threshold: number;
  bad_day_count: number;
  avg_normal_count: number;
  overall_win_rate: number;
  next_day: {
    avg_count: number;
    avg_wr: number;
    avg_pnl: number;
    overtrade_pct: number;
  };
  days_2_3: {
    avg_count: number;
    avg_wr: number;
  };
}

export default function RecoveryCard({ days }: { days: number }) {
  const [data, setData]       = useState<RecoveryData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    // Recovery needs 180d of history regardless of tab setting
    api.get('/api/analytics/recovery-pattern', { params: { days_back: Math.max(days, 90) } })
      .then(r => setData(r.data))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [days]);

  if (loading) return <Skeleton className="h-48 rounded-xl" />;
  if (!data?.has_data) {
    if (!data?.reason) return null;
    return null; // Silently hide if not enough data
  }

  const { bad_day_threshold, bad_day_count, avg_normal_count, overall_win_rate, next_day, days_2_3 } = data;
  const overtrade = next_day.overtrade_pct > 0;

  return (
    <div className="tm-card overflow-hidden">
      <div className="px-5 py-4 border-b border-border flex items-center gap-2">
        <TrendingDown className="h-4 w-4 text-tm-loss" />
        <div>
          <p className="text-sm font-medium text-foreground">Post-Bad-Day Pattern</p>
          <p className="text-[11px] text-muted-foreground mt-0.5">
            Based on {bad_day_count} sessions where you lost &gt; {formatCurrency(bad_day_threshold)}
          </p>
        </div>
      </div>

      <div className="p-5 space-y-4">
        {/* Day after comparison */}
        <div className="grid grid-cols-2 gap-3">
          {/* Normal day */}
          <div className="bg-muted/30 rounded-lg p-3 space-y-1">
            <p className="text-[10px] text-muted-foreground uppercase tracking-wide">Normal day</p>
            <div className="flex items-baseline gap-1">
              <p className="text-lg font-mono font-semibold text-foreground tabular-nums">
                {avg_normal_count}
              </p>
              <p className="text-[11px] text-muted-foreground">trades</p>
            </div>
            <p className="text-[11px] text-muted-foreground">{overall_win_rate}% win rate</p>
          </div>

          {/* Day after bad */}
          <div className={cn(
            'rounded-lg p-3 space-y-1 border',
            overtrade
              ? 'bg-red-50/50 dark:bg-red-900/10 border-red-200 dark:border-red-800/30'
              : 'bg-muted/30 border-transparent'
          )}>
            <p className="text-[10px] text-muted-foreground uppercase tracking-wide">Day after bad day</p>
            <div className="flex items-baseline gap-1">
              <p className={cn(
                'text-lg font-mono font-semibold tabular-nums',
                overtrade ? 'text-tm-loss' : 'text-foreground'
              )}>
                {next_day.avg_count}
              </p>
              <p className="text-[11px] text-muted-foreground">trades</p>
              {overtrade && (
                <span className="text-[10px] text-tm-loss font-medium ml-1">
                  +{next_day.overtrade_pct}%
                </span>
              )}
            </div>
            <p className={cn(
              'text-[11px]',
              next_day.avg_wr < overall_win_rate - 5 ? 'text-tm-loss' : 'text-muted-foreground'
            )}>
              {next_day.avg_wr}% win rate
            </p>
          </div>
        </div>

        {/* Bars for visual comparison */}
        <div className="space-y-2">
          <div>
            <div className="flex justify-between text-[10px] text-muted-foreground mb-1">
              <span>Trade count (day after vs normal)</span>
            </div>
            <div className="flex gap-1 h-2">
              <div className="rounded-sm bg-muted/60" style={{ width: `${Math.min(100, (avg_normal_count / Math.max(avg_normal_count, next_day.avg_count)) * 100)}%` }} />
            </div>
            <div className="flex gap-1 h-2 mt-0.5">
              <div
                className={cn('rounded-sm transition-all', overtrade ? 'bg-[#DC2626]/60' : 'bg-muted/60')}
                style={{ width: `${Math.min(100, (next_day.avg_count / Math.max(avg_normal_count, next_day.avg_count)) * 100)}%` }}
              />
            </div>
          </div>
        </div>

        {/* Days 2-3 recovery */}
        {days_2_3.avg_count > 0 && (
          <div className="border-t border-border pt-3">
            <p className="text-[11px] text-muted-foreground mb-1">Days 2–3 after bad day</p>
            <p className="text-[12px] text-foreground">
              Trade count: <span className="font-mono">{days_2_3.avg_count}</span>
              {' '}&nbsp;·&nbsp;{' '}
              Win rate: <span className={cn('font-mono', days_2_3.avg_wr >= overall_win_rate - 5 ? 'text-tm-profit' : 'text-tm-loss')}>
                {days_2_3.avg_wr}%
              </span>
              {days_2_3.avg_wr >= overall_win_rate - 5 && (
                <span className="text-[11px] text-muted-foreground ml-1">(normalized)</span>
              )}
            </p>
          </div>
        )}

        {/* Key insight */}
        {overtrade && next_day.avg_wr < overall_win_rate - 5 && (
          <div className="bg-amber-50 dark:bg-amber-900/10 border border-amber-200 dark:border-amber-800/30 rounded-lg px-3 py-2">
            <p className="text-[12px] text-tm-obs leading-relaxed">
              The day after a big loss, you trade {next_day.overtrade_pct}% more at {next_day.avg_wr}% win rate
              (your normal: {overall_win_rate}%). Consider sitting out day-after sessions.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
