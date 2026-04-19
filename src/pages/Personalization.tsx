import { useState, useEffect, useCallback } from 'react';
import { Clock, TrendingUp, TrendingDown, AlertTriangle, RefreshCw, Brain, ChevronRight, Zap } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { api } from '@/lib/api';
import { useBroker } from '@/contexts/BrokerContext';

// ─── Types ────────────────────────────────────────────────────────────────────

interface Insight {
  type: string;
  icon: string;
  title: string;
  value: string;
  detail: string;
  recommendation: string;
}

interface PredictiveAlert {
  type: string;
  message: string;
  severity: 'caution' | 'danger';
  trigger_symbol?: string;
  trigger_day?: string;
  trigger_time?: string;
}

interface InsightsData {
  has_data: boolean;
  message?: string;
  trades_analyzed?: number;
  last_updated?: string;
  insights: Insight[];
  predictive_alerts: PredictiveAlert[];
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

const TYPE_ICON: Record<string, React.ReactNode> = {
  danger_time:   <Clock className="h-4 w-4 text-tm-loss" />,
  best_time:     <Clock className="h-4 w-4 text-tm-profit" />,
  problem_symbol:<TrendingDown className="h-4 w-4 text-tm-loss" />,
  strong_symbol: <TrendingUp className="h-4 w-4 text-tm-profit" />,
  revenge_window:<Zap className="h-4 w-4 text-tm-obs" />,
};

const TYPE_BORDER: Record<string, string> = {
  danger_time:   'border-l-tm-loss',
  problem_symbol:'border-l-tm-loss',
  best_time:     'border-l-tm-profit',
  strong_symbol: 'border-l-tm-profit',
  revenge_window:'border-l-tm-obs',
};

const SEVERITY_DOT: Record<string, string> = {
  danger:  'bg-tm-loss',
  caution: 'bg-tm-obs',
};

function fmtUpdated(iso: string | undefined): string {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleString('en-IN', {
    timeZone: 'Asia/Kolkata',
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

// ─── Skeleton ─────────────────────────────────────────────────────────────────

function PageSkeleton() {
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {[1, 2, 3, 4, 5].map(i => (
          <div key={i} className="tm-card border-l-2 border-l-border px-4 py-4 space-y-2">
            <Skeleton className="h-3 w-20 rounded" />
            <Skeleton className="h-6 w-24 rounded" />
            <Skeleton className="h-3 w-full rounded" />
          </div>
        ))}
      </div>
      <div className="tm-card p-4 space-y-2">
        <Skeleton className="h-3 w-32 rounded" />
        {[1, 2].map(i => <Skeleton key={i} className="h-10 w-full rounded-lg" />)}
      </div>
    </div>
  );
}

// ─── Main ─────────────────────────────────────────────────────────────────────

export default function Personalization() {
  const { account } = useBroker();
  const [data, setData] = useState<InsightsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [learning, setLearning] = useState(false);
  const [learnError, setLearnError] = useState<string | null>(null);

  const fetchInsights = useCallback(async () => {
    if (!account?.id) return;
    setLoading(true);
    try {
      const res = await api.get('/api/personalization/insights', {
        params: { broker_account_id: account.id },
      });
      setData(res.data);
    } catch {
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [account?.id]);

  useEffect(() => { fetchInsights(); }, [fetchInsights]);

  const handleLearn = async () => {
    if (!account?.id || learning) return;
    setLearning(true);
    setLearnError(null);
    try {
      await api.post('/api/personalization/learn', null, {
        params: { broker_account_id: account.id, days_back: 90 },
      });
      await fetchInsights();
    } catch {
      setLearnError('Pattern learning failed. Try again later.');
    } finally {
      setLearning(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto pb-12">
      {/* Header */}
      <div className="mb-5 flex items-center justify-between">
        <div>
          <h1 className="t-heading-lg text-foreground">My Patterns</h1>
          {data?.last_updated && (
            <p className="text-[11px] text-muted-foreground mt-0.5">
              Last analysed {fmtUpdated(data.last_updated)}
              {data.trades_analyzed ? ` · ${data.trades_analyzed} trades` : ''}
            </p>
          )}
        </div>
        <button
          onClick={handleLearn}
          disabled={learning || loading}
          aria-label="Refresh pattern analysis"
          className={cn(
            'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] font-medium border transition-colors',
            'border-border text-muted-foreground hover:text-foreground hover:border-tm-brand/40',
            (learning || loading) && 'opacity-50 cursor-not-allowed',
          )}
        >
          <RefreshCw className={cn('h-3.5 w-3.5', learning && 'animate-spin')} />
          {learning ? 'Analysing…' : 'Refresh'}
        </button>
      </div>

      {learnError && (
        <div className="mb-4 px-4 py-3 rounded-lg bg-tm-loss/10 border border-tm-loss/20 text-sm text-tm-loss">
          {learnError}
        </div>
      )}

      {loading ? (
        <PageSkeleton />
      ) : !data?.has_data ? (
        /* ── Empty / insufficient data ── */
        <div className="tm-card flex flex-col items-center justify-center py-16 text-center px-6">
          <div className="w-12 h-12 rounded-full bg-teal-50 dark:bg-teal-900/20 flex items-center justify-center mb-4">
            <Brain className="h-6 w-6 text-tm-brand" />
          </div>
          <p className="text-[14px] font-semibold text-foreground mb-1">Not enough data yet</p>
          <p className="text-[13px] text-muted-foreground max-w-sm leading-relaxed">
            {data?.message ?? 'Keep trading to build your personal pattern profile. Analysis runs after 20+ completed trades.'}
          </p>
          {(data?.trades_analyzed ?? 0) > 0 && (
            <p className="text-[11px] text-muted-foreground mt-2">
              {data!.trades_analyzed} of 20 trades recorded
            </p>
          )}
          <button
            onClick={handleLearn}
            disabled={learning}
            className="mt-5 px-4 py-2 rounded-lg bg-tm-brand text-white text-[13px] font-medium hover:bg-tm-brand/90 transition-colors disabled:opacity-50"
          >
            {learning ? 'Analysing…' : 'Run Analysis Now'}
          </button>
        </div>
      ) : (
        <div className="space-y-5">

          {/* ── Insight cards ── */}
          {data.insights.length > 0 && (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {data.insights.map((ins) => (
                <div
                  key={ins.type}
                  className={cn(
                    'tm-card overflow-hidden border-l-2 px-4 py-4',
                    TYPE_BORDER[ins.type] ?? 'border-l-border',
                  )}
                >
                  <div className="flex items-center gap-2 mb-2">
                    {TYPE_ICON[ins.type] ?? <AlertTriangle className="h-4 w-4 text-muted-foreground" />}
                    <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">
                      {ins.title}
                    </span>
                  </div>
                  <p className="text-2xl font-bold font-mono tabular-nums text-foreground mb-0.5">
                    {ins.value}
                  </p>
                  <p className="text-[12px] text-muted-foreground mb-2">{ins.detail}</p>
                  <div className="flex items-start gap-1.5">
                    <ChevronRight className="h-3 w-3 text-tm-brand mt-0.5 flex-shrink-0" />
                    <p className="text-[11px] text-muted-foreground leading-relaxed">{ins.recommendation}</p>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* ── Predictive alerts ── */}
          {data.predictive_alerts.length > 0 && (
            <div className="tm-card overflow-hidden">
              <div className="px-5 py-3 border-b border-border">
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                  Predictive Warnings
                </p>
              </div>
              <div className="divide-y divide-border/50">
                {data.predictive_alerts.map((alert, i) => (
                  <div key={i} className="flex items-start gap-3 px-5 py-3">
                    <span
                      className={cn('w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0', SEVERITY_DOT[alert.severity] ?? 'bg-tm-obs')}
                    />
                    <p className="text-[13px] text-foreground leading-relaxed">{alert.message}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ── No insights yet after learning ── */}
          {data.insights.length === 0 && data.predictive_alerts.length === 0 && (
            <div className="tm-card flex flex-col items-center justify-center py-12 text-center px-6">
              <Brain className="h-8 w-8 text-muted-foreground/30 mb-3" />
              <p className="text-sm font-medium text-foreground">No distinct patterns found yet</p>
              <p className="text-[13px] text-muted-foreground mt-1 max-w-xs">
                Need at least 5 trades per hour/symbol to flag a pattern.
                Keep trading and refresh in a few days.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
