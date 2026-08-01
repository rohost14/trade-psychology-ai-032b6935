import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { RefreshCw, AlertTriangle, Link as LinkIcon, ArrowRight } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import ErrorState from '@/components/ErrorState';
import { cn } from '@/lib/utils';
import { formatCurrencyWithSign } from '@/lib/formatters';
import { api } from '@/lib/api';
import OptionsBehaviorCard from './OptionsBehaviorCard';
import { useBroker } from '@/contexts/BrokerContext';
import { PredictiveContextStrip } from '@/components/dashboard/PredictiveContextStrip';

interface BehaviorTabProps { days: number }

// Shape of GET /api/analytics/risk-metrics → alerts_summary
interface PatternRow {
  pattern_type: string;
  count: number;
  last_detected: string | null;
}

interface RiskMetrics {
  has_data: boolean;
  alerts_summary: PatternRow[];
}

// Shape of GET /api/analytics/conditional-performance
interface Condition {
  key: string;
  label: string;
  win_rate: number;
  avg_pnl: number;
  trade_count: number;
  delta_vs_baseline: number;
  narrative: string;
}

interface ConditionalData {
  has_data: boolean;
  total_trades: number;
  baseline_win_rate: number;
  baseline_avg_pnl: number;
  conditions: Condition[];
}

// Shape of GET /api/analytics/journal-correlation → by_emotion
interface EmotionRow {
  emotion: string;
  trade_count: number;
  avg_pnl: number;
  total_pnl: number;
  win_rate: number;
}

interface JournalCorrData {
  has_data: boolean;
  total_journaled: number;
  by_emotion: EmotionRow[];
}

// Per-condition help copy — the backend narrative carries the numbers; this
// carries the definition.
const CONDITION_DESCRIPTIONS: Record<string, string> = {
  after_loss:     'Trades entered shortly after a losing trade.',
  first_30min:    'Trades entered between 9:15–9:45 AM IST.',
  expiry_day:     'Trades taken on an option-expiry day.',
  large_position: 'Trades sized above 1.5× your average.',
  quick_reentry:  'Re-entries within 20 minutes of your last round-trip.',
};

const TAG_COLORS: Record<string, string> = {
  frustrated:    'bg-red-500/10 text-tm-loss',
  anxious:       'bg-red-500/10 text-tm-loss',
  fearful:       'bg-red-500/10 text-tm-loss',
  angry:         'bg-red-500/10 text-tm-loss',
  revenge:       'bg-red-500/10 text-tm-loss',
  confident:     'bg-green-500/10 text-tm-profit',
  focused:       'bg-green-500/10 text-tm-profit',
  calm:          'bg-green-500/10 text-tm-profit',
  greedy:        'bg-amber-500/10 text-tm-obs',
  fomo:          'bg-amber-500/10 text-tm-obs',
  overconfident: 'bg-amber-500/10 text-tm-obs',
};

function tagColor(tag: string) {
  return TAG_COLORS[tag.toLowerCase()] ?? 'bg-muted/60 text-foreground';
}

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return '—';
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  const hrs  = Math.floor(mins / 60);
  const days = Math.floor(hrs / 24);
  if (mins < 1)  return 'just now';
  if (mins < 60) return `${mins}m ago`;
  if (hrs < 24)  return `${hrs}h ago`;
  return `${days}d ago`;
}

export default function BehaviorTab({ days }: BehaviorTabProps) {
  const { account } = useBroker();
  const [metrics, setMetrics]       = useState<RiskMetrics | null>(null);
  const [conditional, setCond]      = useState<ConditionalData | null>(null);
  const [emotions, setEmotions]     = useState<JournalCorrData | null>(null);
  const [hasOptions, setHasOptions] = useState(false);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState<unknown>(null);
  const [retry, setRetry]           = useState(0);

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
      if (m.status === 'rejected') setError(m.reason);
    }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [days, retry]);

  if (loading) return (
    <div className="space-y-4 animate-pulse">
      <Skeleton className="h-[200px] rounded-lg" />
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Skeleton className="h-32 rounded-lg" />
        <Skeleton className="h-32 rounded-lg" />
        <Skeleton className="h-32 rounded-lg" />
      </div>
      <Skeleton className="h-24 rounded-lg" />
    </div>
  );

  if (error) return <ErrorState error={error} onRetry={() => setRetry(r => r + 1)} />;

  // Pattern frequency, most frequent first
  const patterns = [...(metrics?.alerts_summary ?? [])].sort((a, b) => b.count - a.count);
  const maxCount = Math.max(...patterns.map(p => p.count), 1);

  const conditions = conditional?.has_data ? (conditional.conditions ?? []) : [];
  const baselineWR = conditional?.baseline_win_rate ?? 0;

  const emotionRows = emotions?.has_data ? (emotions.by_emotion ?? []) : [];

  return (
    <div className="space-y-5">

      {/* Conditional performance — win rate under specific behavioural conditions */}
      {conditions.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {conditions.map(c => {
            const isRisky = c.delta_vs_baseline < -5;
            return (
              <div
                key={c.key}
                className="tm-card overflow-hidden"
              >
                <div className="px-4 pt-4 pb-3">
                  <p className="text-xs text-muted-foreground uppercase tracking-wide mb-2">{c.label}</p>
                  <div className="flex items-end gap-2 mb-1">
                    <span className={cn(
                      'text-3xl font-mono font-black tabular-nums',
                      isRisky ? 'text-tm-loss' : 'text-tm-profit',
                    )}>
                      {Math.round(c.win_rate)}%
                    </span>
                    <span className="text-sm text-muted-foreground pb-0.5">win rate</span>
                  </div>
                  <p className={cn('text-[12px] font-medium', c.delta_vs_baseline < 0 ? 'text-tm-loss' : 'text-tm-profit')}>
                    {c.delta_vs_baseline > 0 ? '+' : ''}{c.delta_vs_baseline.toFixed(1)}% vs your baseline ({Math.round(baselineWR)}%)
                  </p>
                  {CONDITION_DESCRIPTIONS[c.key] && (
                    <p className="text-[11px] text-muted-foreground mt-2">{CONDITION_DESCRIPTIONS[c.key]}</p>
                  )}
                  <p className="text-[11px] text-muted-foreground mt-0.5">
                    {c.trade_count} trades · {formatCurrencyWithSign(Math.round(c.avg_pnl))} avg
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Options-specific behaviour — renders nothing when no options patterns fired */}
      <OptionsBehaviorCard days={days} onHasData={setHasOptions} />

      {/* Emotion Summary */}
      {emotionRows.length > 0 && (
        <div className="tm-card overflow-hidden">
          <div className="px-5 py-3.5 border-b border-border flex items-center justify-between">
            <p className="font-semibold text-sm">Emotion vs P&L (top tags)</p>
            <Link to="/journal" className="flex items-center gap-1 text-xs text-tm-brand hover:underline">
              <LinkIcon className="h-3 w-3" /> See full journal
            </Link>
          </div>
          <div className="px-5 py-4 flex flex-wrap gap-2">
            {emotionRows.slice(0, 8).map(e => (
              <div
                key={e.emotion}
                className={cn('flex items-center gap-2 px-3 py-2 rounded-lg border', tagColor(e.emotion))}
              >
                <span className="text-sm font-medium capitalize">{e.emotion}</span>
                <span className="text-[11px] font-mono tabular-nums">
                  {formatCurrencyWithSign(Math.round(e.avg_pnl))} avg
                </span>
                <span className="text-[10px] text-muted-foreground">
                  {e.trade_count}× · {Math.round(e.win_rate)}% WR
                </span>
              </div>
            ))}
          </div>
          <p className="px-5 pb-3.5 text-[11px] text-muted-foreground">
            Based on the emotions you tagged when journaling each trade
            ({emotions?.total_journaled ?? 0} journaled trades in this period).
          </p>
        </div>
      )}

      {!patterns.length && !conditions.length && !emotionRows.length && !hasOptions && (
        <div className="tm-card px-5 py-12 text-center text-sm text-muted-foreground">
          No behavioral data available for this period.
        </div>
      )}

    </div>
  );
}
