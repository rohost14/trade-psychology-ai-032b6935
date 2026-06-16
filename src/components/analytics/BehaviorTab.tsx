import { useState, useEffect } from 'react';
import { RefreshCw, AlertTriangle, Link as LinkIcon } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { formatCurrencyWithSign } from '@/lib/formatters';
import { api } from '@/lib/api';
import { Link } from 'react-router-dom';

interface BehaviorTabProps { days: number }

interface PatternRow {
  pattern_type: string;
  display_name: string;
  alerts: number;
  heeded: number;
  continued: number;
  heeded_pct: number;
  post_alert_pnl: number;
}

interface RiskMetrics {
  has_data: boolean;
  alerts_summary: PatternRow[];
  total_alerts: number;
  total_heeded: number;
  total_continued: number;
  estimated_cost_of_ignoring: number;
}

interface ScenarioResult {
  trades: number;
  win_rate: number;
  avg_pnl: number;
  baseline_win_rate?: number;
  baseline_avg_pnl?: number;
}

interface ConditionalData {
  has_data: boolean;
  after_loss: ScenarioResult;
  first_30min: ScenarioResult;
  quick_reentry: ScenarioResult;
  large_position?: ScenarioResult;
}

interface EmotionRow {
  tag: string; trades: number; avg_pnl: number; baseline_avg_pnl: number;
}

interface JournalCorrData {
  has_data: boolean;
  data: EmotionRow[];
}

const SCENARIO_META: Record<string, { label: string; description: string; riskyIfBelow: boolean }> = {
  after_loss: {
    label: 'After a Loss',
    description: 'Win rate on trades entered within 30 min of a losing trade.',
    riskyIfBelow: true,
  },
  first_30min: {
    label: 'First 30 Minutes',
    description: 'Performance on trades entered between 9:15–9:45 AM IST.',
    riskyIfBelow: true,
  },
  quick_reentry: {
    label: 'Quick Re-entry',
    description: 'Win rate when re-entering the same symbol within 5 minutes of exiting.',
    riskyIfBelow: true,
  },
};

const TAG_COLORS: Record<string, string> = {
  frustrated: 'bg-red-500/10 text-tm-loss',
  anxious:    'bg-red-500/10 text-tm-loss',
  fearful:    'bg-red-500/10 text-tm-loss',
  angry:      'bg-red-500/10 text-tm-loss',
  confident:  'bg-green-500/10 text-tm-profit',
  focused:    'bg-green-500/10 text-tm-profit',
  calm:       'bg-green-500/10 text-tm-profit',
  greedy:     'bg-amber-500/10 text-tm-obs',
  fomo:       'bg-amber-500/10 text-tm-obs',
};

function tagColor(tag: string) {
  return TAG_COLORS[tag.toLowerCase()] ?? 'bg-muted/60 text-foreground';
}

export default function BehaviorTab({ days }: BehaviorTabProps) {
  const [metrics, setMetrics]     = useState<RiskMetrics | null>(null);
  const [conditional, setCond]    = useState<ConditionalData | null>(null);
  const [emotions, setEmotions]   = useState<JournalCorrData | null>(null);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState<string | null>(null);
  const [retry, setRetry]         = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.allSettled([
      api.get('/api/analytics/risk-metrics',            { params: { days } }),
      api.get('/api/analytics/conditional-performance', { params: { days } }),
      api.get('/api/analytics/journal-correlation',     { params: { days } }),
    ]).then(([m, c, e]) => {
      if (cancelled) return;
      if (m.status === 'fulfilled') setMetrics(m.value.data);
      if (c.status === 'fulfilled') setCond(c.value.data);
      if (e.status === 'fulfilled') setEmotions(e.value.data);
      if (m.status === 'rejected') setError('Failed to load behavior data.');
    }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [days, retry]);

  if (loading) return (
    <div className="space-y-4 animate-pulse">
      <Skeleton className="h-[200px] rounded-xl" />
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Skeleton className="h-32 rounded-xl" />
        <Skeleton className="h-32 rounded-xl" />
        <Skeleton className="h-32 rounded-xl" />
      </div>
      <Skeleton className="h-24 rounded-xl" />
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

  const patterns = (metrics?.alerts_summary ?? []).sort((a, b) => b.post_alert_pnl - a.post_alert_pnl);
  const maxCost = Math.max(...patterns.map(p => Math.abs(p.post_alert_pnl)), 1);

  return (
    <div className="space-y-5">

      {/* Pattern Cost Table */}
      {patterns.length > 0 && (
        <div className="tm-card overflow-hidden">
          <div className="px-5 py-3.5 border-b border-border flex items-center justify-between">
            <p className="font-semibold text-sm">Pattern Cost Breakdown</p>
            {metrics && metrics.estimated_cost_of_ignoring !== 0 && (
              <span className="text-xs text-tm-loss font-mono font-semibold">
                {formatCurrencyWithSign(Math.round(metrics.estimated_cost_of_ignoring))} total ignored cost
              </span>
            )}
          </div>

          {/* Header row */}
          <div className="grid grid-cols-[1fr_auto_auto_auto] gap-x-4 px-5 py-2 border-b border-border bg-muted/30">
            {['Pattern', 'Alerts', 'Heeded', 'P&L cost'].map(h => (
              <span key={h} className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">{h}</span>
            ))}
          </div>

          <div className="divide-y divide-border">
            {patterns.map(p => {
              const barPct = Math.round(Math.abs(p.post_alert_pnl) / maxCost * 100);
              const isBad  = p.post_alert_pnl < 0;
              return (
                <div key={p.pattern_type} className="px-5 py-3">
                  <div className="grid grid-cols-[1fr_auto_auto_auto] gap-x-4 items-center mb-1.5">
                    <span className="text-sm font-medium truncate">{p.display_name}</span>
                    <span className="text-sm font-mono text-muted-foreground">{p.alerts}</span>
                    <span className="text-sm font-mono">
                      <span className={p.heeded_pct >= 50 ? 'text-tm-profit' : 'text-tm-obs'}>
                        {Math.round(p.heeded_pct)}%
                      </span>
                    </span>
                    <span className={cn('text-sm font-mono font-semibold', isBad ? 'text-tm-loss' : 'text-tm-profit')}>
                      {formatCurrencyWithSign(Math.round(p.post_alert_pnl))}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-1 rounded-full bg-muted/60 overflow-hidden">
                      <div
                        className="h-full rounded-full"
                        style={{ width: `${barPct}%`, backgroundColor: isBad ? '#dc2626' : '#16a34a' }}
                      />
                    </div>
                    <span className="text-[10px] text-muted-foreground w-16 text-right shrink-0">
                      {p.continued} ignored
                    </span>
                  </div>
                </div>
              );
            })}
          </div>

          <p className="px-5 py-3 text-[11px] text-muted-foreground border-t border-border">
            P&L cost = realized P&L on trades where alert was ignored (continued).
            Heeded trades avoid this exposure entirely.
          </p>
        </div>
      )}

      {/* Scenario Cards */}
      {conditional?.has_data && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {Object.entries(SCENARIO_META).map(([key, meta]) => {
            const s = conditional[key as keyof ConditionalData] as ScenarioResult | undefined;
            if (!s || s.trades === 0) return null;
            const baseline = s.baseline_win_rate ?? 0;
            const delta    = s.win_rate - baseline;
            const isRisky  = meta.riskyIfBelow ? delta < -5 : delta > 5;
            return (
              <div
                key={key}
                className={cn(
                  'tm-card overflow-hidden border-l-4',
                  isRisky ? 'border-l-tm-loss' : 'border-l-tm-profit',
                )}
              >
                <div className="px-4 pt-4 pb-3">
                  <p className="text-xs text-muted-foreground uppercase tracking-wide mb-2">{meta.label}</p>
                  <div className="flex items-end gap-2 mb-1">
                    <span className={cn(
                      'text-3xl font-mono font-black tabular-nums',
                      isRisky ? 'text-tm-loss' : 'text-tm-profit',
                    )}>
                      {Math.round(s.win_rate)}%
                    </span>
                    <span className="text-sm text-muted-foreground pb-0.5">win rate</span>
                  </div>
                  {baseline > 0 && (
                    <p className={cn('text-[12px] font-medium', delta < 0 ? 'text-tm-loss' : 'text-tm-profit')}>
                      {delta > 0 ? '+' : ''}{delta.toFixed(1)}% vs your baseline ({Math.round(baseline)}%)
                    </p>
                  )}
                  <p className="text-[11px] text-muted-foreground mt-2">{meta.description}</p>
                  <p className="text-[11px] text-muted-foreground mt-0.5">{s.trades} trades · {formatCurrencyWithSign(Math.round(s.avg_pnl))} avg</p>
                </div>
              </div>
            );
          }).filter(Boolean)}
        </div>
      )}

      {/* Emotion Summary */}
      {emotions?.has_data && emotions.data?.length > 0 && (
        <div className="tm-card overflow-hidden">
          <div className="px-5 py-3.5 border-b border-border flex items-center justify-between">
            <p className="font-semibold text-sm">Emotion vs P&L (top tags)</p>
            <Link to="/journal" className="flex items-center gap-1 text-xs text-tm-brand hover:underline">
              <LinkIcon className="h-3 w-3" /> See full journal
            </Link>
          </div>
          <div className="px-5 py-4 flex flex-wrap gap-2">
            {emotions.data.slice(0, 8).map(e => {
              const delta = e.avg_pnl - e.baseline_avg_pnl;
              return (
                <div
                  key={e.tag}
                  className={cn('flex items-center gap-2 px-3 py-2 rounded-xl border', tagColor(e.tag))}
                >
                  <span className="text-sm font-medium capitalize">{e.tag}</span>
                  <span className="text-[11px] font-mono tabular-nums">
                    {formatCurrencyWithSign(Math.round(e.avg_pnl))} avg
                  </span>
                  {delta !== 0 && (
                    <span className={cn('text-[10px]', delta >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
                      ({delta > 0 ? '+' : ''}{formatCurrencyWithSign(Math.round(delta))})
                    </span>
                  )}
                </div>
              );
            })}
          </div>
          <p className="px-5 pb-3.5 text-[11px] text-muted-foreground">
            Based on journal entries tagged within ±20 min of each trade.
            Full correlation data available in the Journal page.
          </p>
        </div>
      )}

      {!patterns.length && !conditional?.has_data && !emotions?.has_data && (
        <div className="tm-card px-5 py-12 text-center text-sm text-muted-foreground">
          No behavioral data available for this period.
        </div>
      )}

    </div>
  );
}
