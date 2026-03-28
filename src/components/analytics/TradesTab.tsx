import { useState, useEffect } from 'react';
import { Skeleton } from '@/components/ui/skeleton';
import { Loader2, AlertTriangle, TrendingDown, Zap, Clock } from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatCurrency } from '@/lib/formatters';
import { api } from '@/lib/api';

interface CriticalTradeReason {
  type: 'large_loss' | 'behavioral_alert' | 'oversized' | 'quick_reentry';
  label: string;
  pattern_type?: string;
  severity?: string;
}

interface CriticalTrade {
  id: string;
  tradingsymbol: string;
  entry_time: string | null;
  exit_time: string | null;
  direction: string;
  realized_pnl: number;
  duration_minutes: number | null;
  reasons: CriticalTradeReason[];
  severity: 'critical' | 'high' | 'medium';
}

interface CriticalTradesData {
  has_data: boolean;
  total_critical: number;
  avg_loss_threshold: number;
  trades: CriticalTrade[];
}

const reasonIcons: Record<string, React.ComponentType<{ className?: string }>> = {
  large_loss: TrendingDown,
  behavioral_alert: AlertTriangle,
  oversized: Zap,
  quick_reentry: Clock,
};

const reasonColors: Record<string, string> = {
  large_loss: 'text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20',
  behavioral_alert: 'text-orange-600 dark:text-orange-400 bg-orange-50 dark:bg-orange-900/20',
  oversized: 'text-violet-600 dark:text-violet-400 bg-violet-50 dark:bg-violet-900/20',
  quick_reentry: 'text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20',
};

function formatTime(isoStr: string | null): string {
  if (!isoStr) return '—';
  const d = new Date(isoStr);
  return (
    d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' }) +
    ' ' +
    d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false })
  );
}

function formatDuration(minutes: number | null): string {
  if (!minutes) return '—';
  if (minutes < 60) return `${minutes}m`;
  return `${Math.floor(minutes / 60)}h ${minutes % 60}m`;
}

type FilterValue = 'all' | 'critical' | 'high' | 'medium';

export default function TradesTab({ days }: { days: number }) {
  const [data, setData] = useState<CriticalTradesData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [filter, setFilter] = useState<FilterValue>('all');

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setIsLoading(true);
      try {
        const res = await api.get('/api/analytics/critical-trades', { params: { days } });
        if (!cancelled) setData(res.data);
      } catch {
        if (!cancelled) setData(null);
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [days]);

  if (isLoading) {
    return (
      <div className="space-y-3">
        {[1,2,3,4,5].map(i => <Skeleton key={i} className="h-20 rounded-xl" />)}
      </div>
    );
  }

  if (!data?.has_data) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[40vh] bg-card rounded-xl border border-border">
        <TrendingDown className="h-10 w-10 text-muted-foreground/40 mb-3" />
        <p className="font-medium text-foreground">No critical trades in this period</p>
        <p className="text-sm text-muted-foreground mt-1">Keep it up — clean trading leaves no entries here</p>
      </div>
    );
  }

  const filtered = filter === 'all' ? data.trades : data.trades.filter((t) => t.severity === filter);
  const counts: Record<FilterValue, number> = {
    all: data.trades.length,
    critical: data.trades.filter((t) => t.severity === 'critical').length,
    high: data.trades.filter((t) => t.severity === 'high').length,
    medium: data.trades.filter((t) => t.severity === 'medium').length,
  };

  const totalLoss = data.trades.reduce((s, t) => s + Math.min(0, t.realized_pnl), 0);
  const behavioralAlertCount = data.trades.reduce(
    (s, t) => s + t.reasons.filter((r) => r.type === 'behavioral_alert').length,
    0
  );

  return (
    <div className="space-y-5 animate-fade-in">
      {/* Header stats — 4 individual Stripe-style cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-card rounded-xl border border-border p-5">
          <p className="text-xs font-medium uppercase tracking-widest text-muted-foreground mb-2">Critical Trades</p>
          <p className="text-4xl font-bold font-mono tabular-nums text-foreground">{data.total_critical}</p>
          <p className="text-xs text-muted-foreground mt-1">in {days} days</p>
        </div>
        <div className="bg-card rounded-xl border border-border p-5">
          <p className="text-xs font-medium uppercase tracking-widest text-muted-foreground mb-2">Total Loss</p>
          <p className="text-4xl font-bold font-mono tabular-nums text-red-600 dark:text-red-400">
            {formatCurrency(totalLoss)}
          </p>
          <p className="text-xs text-muted-foreground mt-1">from flagged trades</p>
        </div>
        <div className="bg-card rounded-xl border border-border p-5">
          <p className="text-xs font-medium uppercase tracking-widest text-muted-foreground mb-2">Behavioral Alerts</p>
          <p className="text-4xl font-bold font-mono tabular-nums text-orange-600 dark:text-orange-400">
            {behavioralAlertCount}
          </p>
          <p className="text-xs text-muted-foreground mt-1">during trades</p>
        </div>
        <div className="bg-card rounded-xl border border-border p-5">
          <p className="text-xs font-medium uppercase tracking-widest text-muted-foreground mb-2">Worst Trade</p>
          <p className="text-4xl font-bold font-mono tabular-nums text-red-600 dark:text-red-400">
            {data.trades.length > 0 ? formatCurrency(data.trades[0].realized_pnl) : '—'}
          </p>
          <p className="text-xs text-muted-foreground mt-1">{data.trades[0]?.tradingsymbol ?? ''}</p>
        </div>
      </div>

      {/* Filter chips — pill style */}
      <div className="flex items-center gap-2 flex-wrap">
        {(['all', 'critical', 'high', 'medium'] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={cn(
              'px-4 py-1.5 rounded-full text-xs font-medium transition-all border',
              filter === f
                ? f === 'critical' ? 'bg-red-500 text-white border-red-500'
                  : f === 'high' ? 'bg-orange-500 text-white border-orange-500'
                    : f === 'medium' ? 'bg-amber-500 text-white border-amber-500'
                      : 'bg-foreground text-background border-foreground'
                : 'bg-transparent text-muted-foreground border-border hover:border-foreground hover:text-foreground'
            )}
          >
            {f === 'all'
              ? `All (${counts.all})`
              : `${f.charAt(0).toUpperCase() + f.slice(1)} (${counts[f]})`
            }
          </button>
        ))}
      </div>

      {/* Trade list — Zerodha order book style */}
      <div className="space-y-3">
        {filtered.map((trade, index) => {
          const Icon = AlertTriangle;
          return (
            <div
              key={trade.id}
              className={cn(
                'bg-card rounded-xl border border-l-4 overflow-hidden animate-fade-in-up',
                trade.severity === 'critical' ? 'border-l-red-500' :
                  trade.severity === 'high' ? 'border-l-orange-500' : 'border-l-amber-500',
                'border-border'
              )}
              style={{ animationDelay: `${index * 60}ms` }}
            >
              <div className="px-5 py-4">
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-base font-semibold text-foreground">{trade.tradingsymbol}</span>
                      <span className={cn(
                        'text-[10px] font-semibold px-1.5 py-0.5 rounded uppercase tracking-wide',
                        trade.direction === 'LONG'
                          ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                          : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                      )}>
                        {trade.direction}
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {formatTime(trade.entry_time)} → {formatTime(trade.exit_time)} · {formatDuration(trade.duration_minutes)}
                    </p>
                  </div>
                  <span className={cn(
                    'text-xl font-bold font-mono tabular-nums',
                    trade.realized_pnl >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
                  )}>
                    {trade.realized_pnl >= 0 ? '+' : ''}{formatCurrency(trade.realized_pnl)}
                  </span>
                </div>
                {trade.reasons.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mt-3">
                    {trade.reasons.map((reason, i) => {
                      const ReasonIcon = reasonIcons[reason.type] || Icon;
                      return (
                        <span
                          key={i}
                          className={cn(
                            'inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-medium',
                            reasonColors[reason.type] ?? 'text-muted-foreground bg-muted'
                          )}
                        >
                          <ReasonIcon className="h-3 w-3" />
                          {reason.label}
                        </span>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          );
        })}

        {filtered.length === 0 && (
          <div className="flex flex-col items-center justify-center py-12 bg-card rounded-xl border border-border">
            <p className="text-sm text-muted-foreground">No trades match this filter</p>
          </div>
        )}
      </div>
    </div>
  );
}
