import { useState, useEffect } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, ReferenceLine,
} from 'recharts';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Loader2, AlertTriangle, CheckCircle2, Brain, BookOpen,
  ArrowUpRight, ArrowDownRight, Shield, Clock, AlertCircle,
  TrendingDown, Lightbulb, BarChart3, Zap, RefreshCw, Activity,
  Moon, Sunrise,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatCurrency } from '@/lib/formatters';
import { api } from '@/lib/api';

interface BehaviorTabProps {
  days: number;
}

interface DetectedPattern {
  name: string;
  category: string;
  is_positive: boolean;
  frequency: number;
  severity: string;
  pnl_impact: number;
  description: string;
  recommendation: string;
}

interface BehavioralData {
  behavior_score: number | null;
  patterns_detected: DetectedPattern[];
  emotional_tax: number;
  emotional_breakdown: Record<string, number>;
  top_strength: string;
  focus_area: string;
  trading_persona?: string | {
    persona: string;
    description: string;
    strengths: string[];
    weaknesses: string[];
    next_steps: string[];
  };
  total_trades_analyzed: number;
}

interface EmotionCorrelation {
  emotion: string;
  trade_count: number;
  avg_pnl: number;
  total_pnl: number;
  win_rate: number;
}

interface JournalData {
  has_data: boolean;
  total_journaled: number;
  by_emotion: EmotionCorrelation[];
}

interface PredictionEntry {
  probability: number;
  severity: string;
  triggers: string[];
}

interface AIInsightsData {
  has_data: boolean;
  personalization: any;
  pattern_frequency: { pattern: string; occurrences: number }[];
  trading_intensity: {
    avg_daily_trades: number;
    max_daily_trades: number;
    active_days: number;
    overtrade_days: number;
  } | null;
  predictions?: Record<string, PredictionEntry>;
  risk_assessment?: {
    overall_risk: string;
    risk_score: number;
    message: string;
  };
}

const severityColors: Record<string, string> = {
  critical: 'text-red-700 dark:text-red-400',
  high: 'text-red-600 dark:text-red-400',
  medium: 'text-amber-600 dark:text-amber-400',
  low: 'text-blue-600 dark:text-blue-400',
  positive: 'text-green-600 dark:text-green-400',
};

const severityOrder: Record<string, number> = {
  critical: 0, high: 1, medium: 2, low: 3, positive: 4,
};

export default function BehaviorTab({ days }: BehaviorTabProps) {
  const [behavioral, setBehavioral] = useState<BehavioralData | null>(null);
  const [journal, setJournal] = useState<JournalData | null>(null);
  const [aiInsights, setAiInsights] = useState<AIInsightsData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [showPatterns, setShowPatterns] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const fetchData = async () => {
      setIsLoading(true);
      try {
        const [behavioralRes, journalRes, aiRes] = await Promise.allSettled([
          api.get('/api/behavioral/analysis', { params: { time_window_days: days } }),
          api.get('/api/analytics/journal-correlation', { params: { days } }),
          api.get('/api/analytics/ai-insights', { params: { days } }),
        ]);

        if (!cancelled) {
          if (behavioralRes.status === 'fulfilled') setBehavioral(behavioralRes.value.data);
          if (journalRes.status === 'fulfilled') setJournal(journalRes.value.data);
          if (aiRes.status === 'fulfilled') setAiInsights(aiRes.value.data);
        }
      } catch (e) {
        console.error('Failed to fetch behavior data:', e);
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    };
    fetchData();
    return () => { cancelled = true; };
  }, [days]);

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Skeleton className="h-32 rounded-lg md:col-span-1" />
          <Skeleton className="h-32 rounded-lg md:col-span-2" />
        </div>
        {[1,2,3].map(i => <Skeleton key={i} className="h-20 rounded-lg" />)}
      </div>
    );
  }

  if (!behavioral || !behavioral.patterns_detected || (behavioral.total_trades_analyzed < 5 && behavioral.patterns_detected.length === 0)) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[40vh] bg-card rounded-lg border border-border">
        <Brain className="h-10 w-10 text-muted-foreground/40 mb-3" />
          <p className="font-semibold text-foreground">Not enough data for behavioral analysis</p>
          <p className="text-sm text-muted-foreground mt-1">Need at least 5 completed trades</p>
          <div className="grid grid-cols-2 gap-3 mt-6 max-w-sm">
            {[
              { stat: '89%', label: 'of F&O traders lose money in India', source: 'SEBI FY2023' },
              { stat: '73%', label: 'of trades placed within 15 min of a loss are also losing', source: 'SEBI data' },
            ].map((item, i) => (
              <div key={i} className="p-3 rounded-lg bg-muted/50 border border-border/60 text-left">
                <p className="text-lg font-bold text-primary">{item.stat}</p>
                <p className="text-xs text-muted-foreground mt-0.5">{item.label}</p>
                <p className="text-[10px] text-muted-foreground/60 mt-1">{item.source}</p>
              </div>
            ))}
          </div>
      </div>
    );
  }

  const score = behavioral.behavior_score;
  const dangers = behavioral.patterns_detected
    .filter(p => !p.is_positive)
    .sort((a, b) => (severityOrder[a.severity] ?? 3) - (severityOrder[b.severity] ?? 3));
  const strengths = behavioral.patterns_detected.filter(p => p.is_positive);

  const emotionalBreakdown = Object.entries(behavioral.emotional_breakdown || {})
    .map(([name, amount]) => ({ name: name.replace(/_/g, ' '), value: Math.abs(amount) }))
    .filter(d => d.value > 0)
    .sort((a, b) => b.value - a.value);

  const maxTax = Math.max(...emotionalBreakdown.map(e => e.value), 1);

  const predictions = aiInsights?.predictions || {};
  const sortedPredictions = Object.entries(predictions)
    .map(([key, val]) => ({ pattern: key.replace(/_/g, ' '), ...val }))
    .sort((a, b) => b.probability - a.probability)
    .filter(p => p.probability > 0);

  const sortedPatterns = [...behavioral.patterns_detected].sort(
    (a, b) => (severityOrder[a.severity] ?? 3) - (severityOrder[b.severity] ?? 3)
  );
  const visiblePatterns = showPatterns ? sortedPatterns : sortedPatterns.slice(0, 3);

  return (
    <div className="space-y-5 animate-fade-in">
      {/* Predictive Warnings */}
      {sortedPredictions.length > 0 && (
        <div className="bg-card rounded-lg border border-border px-5 py-4">
          <div className="flex items-center gap-2 mb-3">
            <Shield className="h-3.5 w-3.5 text-amber-500" />
            <p className="text-xs text-muted-foreground">Real-Time Pattern Predictions</p>
            {aiInsights?.risk_assessment?.overall_risk && (
              <span className={cn(
                'text-[10px] font-semibold px-1.5 py-0.5 rounded uppercase tracking-wide',
                aiInsights.risk_assessment.overall_risk === 'critical' ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' :
                  aiInsights.risk_assessment.overall_risk === 'high' ? 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400' :
                    aiInsights.risk_assessment.overall_risk === 'medium' ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400' :
                      'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
              )}>
                {aiInsights.risk_assessment.overall_risk} risk
              </span>
            )}
          </div>
          <div className="space-y-3">
            {sortedPredictions.map((pred) => (
              <div key={pred.pattern} className="flex items-center gap-3">
                <span className="text-xs text-muted-foreground w-32 truncate capitalize">{pred.pattern}</span>
                <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
                  <div
                    className={cn(
                      'h-full rounded-full transition-all',
                      pred.probability >= 60 ? 'bg-red-500' :
                        pred.probability >= 30 ? 'bg-amber-500' : 'bg-green-500'
                    )}
                    style={{ width: `${Math.min(pred.probability, 100)}%` }}
                  />
                </div>
                <span className={cn(
                  'text-xs font-mono tabular-nums w-10 text-right',
                  pred.probability >= 60 ? 'text-red-600 dark:text-red-400' :
                    pred.probability >= 30 ? 'text-amber-600 dark:text-amber-400' :
                      'text-green-600 dark:text-green-400'
                )}>
                  {pred.probability}%
                </span>
              </div>
            ))}
          </div>
          {aiInsights?.risk_assessment?.message && (
            <p className="text-xs text-muted-foreground mt-3 italic">
              {aiInsights.risk_assessment.message}
            </p>
          )}
        </div>
      )}

      {/* Top 3 Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-card rounded-lg border border-border px-4 py-3">
          <p className="text-xs text-muted-foreground mb-1.5">Behavior Score</p>
          <div className="flex items-baseline gap-1.5">
            <p className={cn(
              'text-3xl font-semibold font-mono tabular-nums',
              score == null ? 'text-muted-foreground' :
                score >= 70 ? 'text-green-600 dark:text-green-400' :
                  score >= 40 ? 'text-amber-500' : 'text-red-600 dark:text-red-400'
            )}>
              {score == null ? '—' : score}
            </p>
            {score != null && <p className="text-sm text-muted-foreground">/100</p>}
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">
            {score == null ? 'Need 5+ trades'
              : score >= 70 ? 'Disciplined'
              : score >= 40 ? 'Improving'
              : 'High interference'}
          </p>
        </div>

        <div className="bg-card rounded-lg border border-border px-4 py-3">
          <p className="text-xs text-muted-foreground mb-1.5">Emotional Tax</p>
          <p className="text-3xl font-semibold font-mono tabular-nums text-red-600 dark:text-red-400">
            {formatCurrency(behavioral.emotional_tax)}
          </p>
          <p className="text-xs text-muted-foreground mt-0.5">Lost to patterns in {days}d</p>
        </div>

        <div className="bg-card rounded-lg border border-border px-4 py-3">
          <p className="text-xs text-muted-foreground mb-1.5">Analyzed</p>
          <p className="text-3xl font-semibold font-mono tabular-nums text-foreground">
            {behavioral.total_trades_analyzed}
          </p>
          <p className="text-xs text-muted-foreground mt-0.5">
            {dangers.length} risk{dangers.length !== 1 ? 's' : ''} · {strengths.length} strength{strengths.length !== 1 ? 's' : ''}
          </p>
        </div>
      </div>

      {/* Emotional Tax Breakdown — horizontal bar list */}
      {emotionalBreakdown.length > 0 && (
        <div className="bg-card rounded-lg border border-border overflow-hidden">
          <div className="px-5 py-4 border-b border-border">
            <p className="text-xs font-medium uppercase tracking-widest text-muted-foreground">Where You're Bleeding</p>
          </div>
          <div className="divide-y divide-border">
            {emotionalBreakdown.map((item) => {
              const pct = maxTax > 0 ? (item.value / maxTax) * 100 : 0;
              return (
                <div key={item.name} className="px-5 py-3 flex items-center gap-3">
                  <span className="text-sm text-foreground capitalize w-36 flex-shrink-0">{item.name}</span>
                  <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
                    <div className="h-full bg-red-500 rounded-full" style={{ width: `${pct}%` }} />
                  </div>
                  <span className="text-sm font-mono tabular-nums text-red-600 dark:text-red-400 w-24 text-right">
                    -{formatCurrency(item.value)}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Detected Patterns — collapsible */}
      {behavioral.patterns_detected.length > 0 && (
        <div className="bg-card rounded-lg border border-border overflow-hidden">
          <div className="px-5 py-4 border-b border-border flex items-center justify-between">
            <p className="text-xs font-medium uppercase tracking-widest text-muted-foreground">
              Detected Patterns
            </p>
            {behavioral.patterns_detected.length > 3 && (
              <button
                onClick={() => setShowPatterns(!showPatterns)}
                className="text-xs text-muted-foreground hover:text-foreground transition-colors"
              >
                {showPatterns ? 'Show less' : `Show all ${behavioral.patterns_detected.length}`}
              </button>
            )}
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border bg-muted/30">
                  <th className="px-4 py-2 text-left text-[11px] font-medium uppercase tracking-widest text-muted-foreground">Pattern</th>
                  <th className="px-3 py-2 text-left text-[11px] font-medium uppercase tracking-widest text-muted-foreground">Category</th>
                  <th className="px-3 py-2 text-center text-[11px] font-medium uppercase tracking-widest text-muted-foreground">Severity</th>
                  <th className="px-3 py-2 text-right text-[11px] font-medium uppercase tracking-widest text-muted-foreground">Freq</th>
                  <th className="px-3 py-2 text-right text-[11px] font-medium uppercase tracking-widest text-muted-foreground">P&L Impact</th>
                  <th className="px-4 py-2 text-left text-[11px] font-medium uppercase tracking-widest text-muted-foreground">Recommendation</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {visiblePatterns.map((pattern, i) => (
                  <tr key={i} className="hover:bg-muted/40 transition-colors">
                    <td className="px-4 py-2.5">
                      <div className="flex items-center gap-2">
                        {pattern.is_positive ? (
                          <CheckCircle2 className="h-3.5 w-3.5 text-green-600 flex-shrink-0" />
                        ) : (
                          <AlertTriangle className="h-3.5 w-3.5 text-red-600 flex-shrink-0" />
                        )}
                        <span className="text-sm font-medium text-foreground">{pattern.name}</span>
                      </div>
                    </td>
                    <td className="px-3 py-2.5 text-sm text-muted-foreground capitalize">{pattern.category}</td>
                    <td className="px-3 py-2.5 text-center">
                      <span className={cn(
                        'text-[10px] font-semibold uppercase tracking-wide',
                        severityColors[pattern.severity] || severityColors.medium
                      )}>
                        {pattern.severity}
                      </span>
                    </td>
                    <td className="px-3 py-2.5 text-right text-sm tabular-nums font-mono">{pattern.frequency}x</td>
                    <td className="px-3 py-2.5 text-right">
                      {pattern.pnl_impact > 0 ? (
                        <span className="text-sm tabular-nums font-mono text-red-600 dark:text-red-400">
                          -{formatCurrency(pattern.pnl_impact)}
                        </span>
                      ) : (
                        <span className="text-sm text-muted-foreground">—</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-xs text-muted-foreground max-w-[250px] truncate" title={pattern.recommendation}>
                      {pattern.recommendation}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Strengths vs Weaknesses */}
      {(dangers.length > 0 || strengths.length > 0) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-card rounded-lg border border-border overflow-hidden">
            <div className="px-5 py-3 border-b border-border flex items-center gap-2">
              <AlertTriangle className="h-3.5 w-3.5 text-red-500" />
              <p className="text-xs text-muted-foreground">
                Areas to Improve <span className="text-foreground font-medium">({dangers.length})</span>
              </p>
            </div>
            <div className="divide-y divide-border">
              {dangers.length > 0 ? dangers.map((p, i) => (
                <div key={i} className="px-5 py-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-medium text-foreground">{p.name}</span>
                    <div className="flex items-center gap-2">
                      {p.pnl_impact > 0 && (
                        <span className="text-xs tabular-nums font-mono text-red-600">-{formatCurrency(p.pnl_impact)}</span>
                      )}
                      <span className="text-xs tabular-nums font-mono text-muted-foreground">{p.frequency}x</span>
                    </div>
                  </div>
                  <p className="text-xs text-muted-foreground">{p.description}</p>
                </div>
              )) : (
                <div className="px-5 py-6 text-center">
                  <CheckCircle2 className="h-6 w-6 text-green-600 mx-auto mb-1" />
                  <p className="text-sm text-muted-foreground">No concerning patterns</p>
                </div>
              )}
            </div>
          </div>

          <div className="bg-card rounded-lg border border-border overflow-hidden">
            <div className="px-5 py-3 border-b border-border flex items-center gap-2">
              <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
              <p className="text-xs text-muted-foreground">
                Your Strengths <span className="text-foreground font-medium">({strengths.length})</span>
              </p>
            </div>
            <div className="divide-y divide-border">
              {strengths.length > 0 ? strengths.map((p, i) => (
                <div key={i} className="px-5 py-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-medium text-foreground">{p.name}</span>
                    <span className="text-xs tabular-nums font-mono text-green-600">{p.frequency}x</span>
                  </div>
                  <p className="text-xs text-muted-foreground">{p.description}</p>
                </div>
              )) : (
                <div className="px-5 py-6 text-center">
                  <p className="text-sm text-muted-foreground">Keep trading to build strengths</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* AI Personalized Insights */}
      {aiInsights?.has_data && aiInsights.personalization && (
        <div className="bg-card rounded-lg border border-border overflow-hidden">
          <div className="px-5 py-3 border-b border-border flex items-center gap-2">
            <Lightbulb className="h-3.5 w-3.5 text-primary" />
            <p className="text-xs text-muted-foreground">Personalized Insights</p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-border">
            {aiInsights.personalization.danger_hours?.length > 0 && (
              <div className="px-5 py-4">
                <div className="flex items-center gap-1.5 mb-2">
                  <Clock className="h-3.5 w-3.5 text-red-500" />
                  <p className="text-xs font-medium uppercase tracking-widest text-muted-foreground">Danger Hours</p>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {aiInsights.personalization.danger_hours.map((h: number) => (
                    <span key={h} className="px-2 py-0.5 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 text-xs font-mono rounded">
                      {h}:00
                    </span>
                  ))}
                </div>
                <p className="text-xs text-muted-foreground mt-1.5">You tend to lose money during these hours</p>
              </div>
            )}
            {aiInsights.personalization.best_hours?.length > 0 && (
              <div className="px-5 py-4">
                <div className="flex items-center gap-1.5 mb-2">
                  <Clock className="h-3.5 w-3.5 text-green-500" />
                  <p className="text-xs font-medium uppercase tracking-widest text-muted-foreground">Best Hours</p>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {aiInsights.personalization.best_hours.map((h: number) => (
                    <span key={h} className="px-2 py-0.5 bg-green-50 dark:bg-green-900/20 text-green-600 dark:text-green-400 text-xs font-mono rounded">
                      {h}:00
                    </span>
                  ))}
                </div>
                <p className="text-xs text-muted-foreground mt-1.5">Your most profitable trading hours</p>
              </div>
            )}
            {aiInsights.personalization.problem_symbols?.length > 0 && (
              <div className="px-5 py-4">
                <div className="flex items-center gap-1.5 mb-2">
                  <AlertCircle className="h-3.5 w-3.5 text-red-500" />
                  <p className="text-xs font-medium uppercase tracking-widest text-muted-foreground">Problem Symbols</p>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {aiInsights.personalization.problem_symbols.map((s: string) => (
                    <span key={s} className="px-2 py-0.5 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 text-xs font-medium rounded">
                      {s}
                    </span>
                  ))}
                </div>
                <p className="text-xs text-muted-foreground mt-1.5">Instruments where you consistently lose</p>
              </div>
            )}
            {aiInsights.personalization.strong_symbols?.length > 0 && (
              <div className="px-5 py-4">
                <div className="flex items-center gap-1.5 mb-2">
                  <Shield className="h-3.5 w-3.5 text-green-500" />
                  <p className="text-xs font-medium uppercase tracking-widest text-muted-foreground">Strong Symbols</p>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {aiInsights.personalization.strong_symbols.map((s: string) => (
                    <span key={s} className="px-2 py-0.5 bg-green-50 dark:bg-green-900/20 text-green-600 dark:text-green-400 text-xs font-medium rounded">
                      {s}
                    </span>
                  ))}
                </div>
                <p className="text-xs text-muted-foreground mt-1.5">Instruments where you have an edge</p>
              </div>
            )}
          </div>
          {aiInsights.trading_intensity && (
            <div className="border-t border-border px-5 py-4">
              <p className="text-xs font-medium uppercase tracking-widest text-muted-foreground mb-3">Trading Intensity</p>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <p className="text-xl font-bold tabular-nums font-mono text-foreground">{aiInsights.trading_intensity.avg_daily_trades}</p>
                  <p className="text-xs text-muted-foreground">Avg trades/day</p>
                </div>
                <div>
                  <p className="text-xl font-bold tabular-nums font-mono text-foreground">{aiInsights.trading_intensity.max_daily_trades}</p>
                  <p className="text-xs text-muted-foreground">Max in one day</p>
                </div>
                <div>
                  <p className="text-xl font-bold tabular-nums font-mono text-foreground">{aiInsights.trading_intensity.active_days}</p>
                  <p className="text-xs text-muted-foreground">Active days</p>
                </div>
                <div>
                  <p className={cn(
                    'text-xl font-bold tabular-nums font-mono',
                    aiInsights.trading_intensity.overtrade_days > 3 ? 'text-red-600' : 'text-foreground'
                  )}>
                    {aiInsights.trading_intensity.overtrade_days}
                  </p>
                  <p className="text-xs text-muted-foreground">Overtrade days</p>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Journal-Emotion Correlation */}
      {journal?.has_data && journal.by_emotion.length > 0 && (
        <div className="bg-card rounded-lg border border-border overflow-hidden">
          <div className="px-5 py-4 border-b border-border">
            <div className="flex items-center gap-2">
              <BookOpen className="h-4 w-4 text-muted-foreground" />
              <p className="text-xs font-medium uppercase tracking-widest text-muted-foreground">Journal-Emotion Correlation</p>
            </div>
            <p className="text-xs text-muted-foreground mt-1">{journal.total_journaled} journaled trades — how your emotions affect outcomes</p>
          </div>
          <div className="px-5 py-4">
            <div className="h-[200px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={journal.by_emotion} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" strokeOpacity={0.5} horizontal={false} />
                  <XAxis
                    type="number"
                    axisLine={false}
                    tickLine={false}
                    tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }}
                    tickFormatter={(v) => `₹${v}`}
                  />
                  <YAxis
                    dataKey="emotion"
                    type="category"
                    axisLine={false}
                    tickLine={false}
                    tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }}
                    width={80}
                  />
                  <Tooltip content={<EmotionTooltip />} />
                  <ReferenceLine x={0} stroke="hsl(var(--border))" strokeWidth={1.5} />
                  <Bar dataKey="avg_pnl" radius={[0, 3, 3, 0]}>
                    {journal.by_emotion.map((entry, index) => (
                      <Cell
                        key={index}
                        fill={entry.avg_pnl >= 0 ? 'hsl(142, 71%, 45%)' : 'hsl(0, 84%, 60%)'}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
          <div className="border-t border-border overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="bg-muted/30">
                  <th className="px-5 py-2 text-left text-[11px] font-medium uppercase tracking-widest text-muted-foreground">Emotion</th>
                  <th className="px-3 py-2 text-right text-[11px] font-medium uppercase tracking-widest text-muted-foreground">Trades</th>
                  <th className="px-3 py-2 text-right text-[11px] font-medium uppercase tracking-widest text-muted-foreground">Avg P&L</th>
                  <th className="px-3 py-2 text-right text-[11px] font-medium uppercase tracking-widest text-muted-foreground">Total P&L</th>
                  <th className="px-3 py-2 text-right text-[11px] font-medium uppercase tracking-widest text-muted-foreground">Win Rate</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {journal.by_emotion.map((e, i) => (
                  <tr key={i} className="hover:bg-muted/40 transition-colors">
                    <td className="px-5 py-2 text-sm font-medium text-foreground capitalize">{e.emotion}</td>
                    <td className="px-3 py-2 text-right text-sm tabular-nums">{e.trade_count}</td>
                    <td className={cn('px-3 py-2 text-right text-sm tabular-nums font-mono', e.avg_pnl >= 0 ? 'text-green-600' : 'text-red-600')}>
                      {e.avg_pnl >= 0 ? '+' : ''}{formatCurrency(e.avg_pnl)}
                    </td>
                    <td className={cn('px-3 py-2 text-right text-sm tabular-nums font-mono', e.total_pnl >= 0 ? 'text-green-600' : 'text-red-600')}>
                      {e.total_pnl >= 0 ? '+' : ''}{formatCurrency(e.total_pnl)}
                    </td>
                    <td className={cn('px-3 py-2 text-right text-sm tabular-nums', e.win_rate >= 50 ? 'text-green-600' : 'text-red-600')}>
                      {e.win_rate}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Focus Area / Top Strength CTAs */}
      {(behavioral.focus_area || behavioral.top_strength) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {behavioral.top_strength && (
            <div className="rounded-lg border border-border border-l-2 border-l-emerald-500 bg-card px-4 py-3">
              <div className="flex items-center gap-1.5 mb-0.5">
                <ArrowUpRight className="h-3.5 w-3.5 text-emerald-500" />
                <p className="text-xs text-muted-foreground uppercase tracking-wide">Top Strength</p>
              </div>
              <p className="text-sm font-medium text-foreground">{behavioral.top_strength}</p>
            </div>
          )}
          {behavioral.focus_area && (
            <div className="rounded-lg border border-border border-l-2 border-l-amber-400 bg-card px-4 py-3">
              <div className="flex items-center gap-1.5 mb-0.5">
                <ArrowDownRight className="h-3.5 w-3.5 text-amber-500" />
                <p className="text-xs text-muted-foreground uppercase tracking-wide">Focus Area</p>
              </div>
              <p className="text-sm font-medium text-foreground">{behavioral.focus_area}</p>
            </div>
          )}
        </div>
      )}

      {/* Conditional Performance */}
      <ConditionalPerformanceCard days={days} />

      {/* BTST Analytics */}
      <BTSTCard days={days} />

      {/* Options Behavioral Patterns */}
      <OptionsPatternCard days={days} />
    </div>
  );
}

// ─── ConditionalPerformanceCard ───────────────────────────────────────────────

interface ConditionEntry {
  key: string;
  label: string;
  trade_count: number;
  win_rate: number;
  delta_vs_baseline: number;
  narrative: string;
}

interface ConditionalPerformanceData {
  has_data: boolean;
  baseline_win_rate: number;
  total_trades: number;
  conditions: ConditionEntry[];
}

function ConditionalPerformanceCard({ days }: { days: number }) {
  const [data, setData] = useState<ConditionalPerformanceData | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await api.get('/api/analytics/conditional-performance', { params: { days } });
        if (!cancelled) setData(res.data);
      } catch {
        if (!cancelled) setData(null);
      }
    })();
    return () => { cancelled = true; };
  }, [days]);

  if (!data?.has_data || !data.conditions?.length) return null;

  return (
    <div className="bg-card rounded-lg border border-border overflow-hidden">
      <div className="px-5 py-4 border-b border-border flex items-center gap-2">
        <BarChart3 className="h-4 w-4 text-violet-500" />
        <div>
          <p className="text-xs font-medium uppercase tracking-widest text-muted-foreground">Conditional Performance</p>
          <p className="text-xs text-muted-foreground mt-0.5">
            Baseline {data.baseline_win_rate}% WR across {data.total_trades} trades
          </p>
        </div>
      </div>
      <div className="divide-y divide-border">
        {data.conditions.map((cond) => (
          <div key={cond.key} className="px-5 py-3.5 flex items-center gap-4">
            <div className="flex-1">
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-sm font-medium text-foreground">{cond.label}</span>
                <div className="flex items-center gap-2">
                  <span className={cn(
                    'text-sm font-mono font-semibold',
                    cond.delta_vs_baseline < 0 ? 'text-red-600' : 'text-green-600'
                  )}>
                    {cond.delta_vs_baseline > 0 ? '+' : ''}{cond.delta_vs_baseline}pp
                  </span>
                  <span className="text-xs text-muted-foreground">{cond.win_rate}% WR · {cond.trade_count} trades</span>
                </div>
              </div>
              {/* Mini delta bar — 0 to ±20pp scale */}
              <div className="relative h-1.5 bg-muted rounded-full overflow-hidden">
                <div className="absolute top-0 bottom-0 w-px bg-border" style={{ left: '50%' }} />
                <div
                  className={cn(
                    'absolute top-0 bottom-0 rounded-full',
                    cond.delta_vs_baseline < 0 ? 'bg-red-500' : 'bg-green-500'
                  )}
                  style={{
                    left: cond.delta_vs_baseline < 0 ? `${50 + (cond.delta_vs_baseline / 20) * 50}%` : '50%',
                    width: `${Math.min(Math.abs(cond.delta_vs_baseline) / 20, 1) * 50}%`,
                  }}
                />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function EmotionTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="bg-popover border border-border rounded-lg p-3 shadow-lg text-sm">
      <p className="font-medium text-foreground capitalize mb-1">{d.emotion}</p>
      <p className={cn('tabular-nums font-mono', d.avg_pnl >= 0 ? 'text-green-600' : 'text-red-600')}>
        Avg: {d.avg_pnl >= 0 ? '+' : ''}{formatCurrency(d.avg_pnl)}
      </p>
      <p className="text-xs text-muted-foreground">{d.trade_count} trades &middot; {d.win_rate}% WR</p>
    </div>
  );
}

// ─── BTSTCard ─────────────────────────────────────────────────────────────────

interface BTSTTrade {
  id: string;
  tradingsymbol: string;
  instrument_type: string | null;
  entry_time: string;
  exit_time: string;
  direction: string;
  realized_pnl: number;
  avg_entry_price: number | null;
  overnight_close_price: number | null;
  was_profitable_at_eod: boolean | null;
  is_reversal: boolean;
  duration_minutes: number | null;
  hold_type: 'overnight' | 'weekend_hold';
}

interface BTSTData {
  has_data: boolean;
  period_days: number;
  total_btst_trades: number;
  btst_win_rate: number;
  btst_total_pnl: number;
  overnight_reversals: number;
  reversal_pnl_lost: number;
  trades: BTSTTrade[];
}

function BTSTCard({ days }: { days: number }) {
  const [data, setData] = useState<BTSTData | null>(null);
  const [showTrades, setShowTrades] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await api.get('/api/analytics/btst', { params: { days } });
        if (!cancelled) setData(res.data);
      } catch {
        if (!cancelled) setData(null);
      }
    })();
    return () => { cancelled = true; };
  }, [days]);

  if (!data?.has_data) return null;

  const { total_btst_trades, btst_win_rate, btst_total_pnl, overnight_reversals, reversal_pnl_lost, trades } = data;
  const visibleTrades = showTrades ? trades : trades.slice(0, 5);

  return (
    <div className="bg-card rounded-lg border border-border overflow-hidden">
      <div className="px-5 py-4 border-b border-border flex items-center gap-2">
        <Moon className="h-4 w-4 text-indigo-500" />
        <p className="text-xs font-medium uppercase tracking-widest text-muted-foreground">
          BTST — Buy Today Sell Tomorrow
        </p>
        <span className="text-xs text-muted-foreground ml-auto">Last {days} days</span>
      </div>

      {/* Summary metrics */}
      <div className="grid grid-cols-2 sm:grid-cols-4 divide-x divide-y sm:divide-y-0 divide-border border-b border-border">
        <div className="px-4 py-3">
          <p className="text-xs text-muted-foreground mb-0.5">BTST Trades</p>
          <p className="text-xl font-bold tabular-nums font-mono text-foreground">{total_btst_trades}</p>
        </div>
        <div className="px-4 py-3">
          <p className="text-xs text-muted-foreground mb-0.5">Win Rate</p>
          <p className={cn(
            'text-xl font-bold tabular-nums font-mono',
            btst_win_rate >= 50 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
          )}>
            {btst_win_rate}%
          </p>
        </div>
        <div className="px-4 py-3">
          <p className="text-xs text-muted-foreground mb-0.5">Total P&L</p>
          <p className={cn(
            'text-xl font-bold tabular-nums font-mono',
            btst_total_pnl >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
          )}>
            {btst_total_pnl >= 0 ? '+' : ''}{formatCurrency(btst_total_pnl)}
          </p>
        </div>
        <div className="px-4 py-3">
          <p className="text-xs text-muted-foreground mb-0.5">Overnight Reversals</p>
          <div className="flex items-baseline gap-1.5">
            <p className={cn(
              'text-xl font-bold tabular-nums font-mono',
              overnight_reversals > 0 ? 'text-orange-600 dark:text-orange-400' : 'text-foreground'
            )}>
              {overnight_reversals}
            </p>
            {overnight_reversals > 0 && reversal_pnl_lost > 0 && (
              <p className="text-xs text-muted-foreground">(-{formatCurrency(reversal_pnl_lost)})</p>
            )}
          </div>
        </div>
      </div>

      {/* Context blurb */}
      <div className="px-5 py-3 border-b border-border bg-indigo-50/50 dark:bg-indigo-950/20">
        <p className="text-xs text-muted-foreground leading-relaxed">
          BTST entries (after 15:00 IST in NRML) are a behavioural signal — late-day
          emotional entries held overnight hoping for a reversal. Friday entries carry 2 extra
          theta days (weekend). Overnight reversals are the most psychologically damaging:
          went to bed profitable, woke up at a loss.
        </p>
      </div>

      {/* Trade list */}
      {trades.length > 0 && (
        <div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border bg-muted/30">
                  <th className="px-4 py-2 text-left text-[11px] font-medium uppercase tracking-widest text-muted-foreground">Symbol</th>
                  <th className="px-3 py-2 text-left text-[11px] font-medium uppercase tracking-widest text-muted-foreground">Type</th>
                  <th className="px-3 py-2 text-left text-[11px] font-medium uppercase tracking-widest text-muted-foreground">Entry</th>
                  <th className="px-3 py-2 text-right text-[11px] font-medium uppercase tracking-widest text-muted-foreground">Hold</th>
                  <th className="px-3 py-2 text-right text-[11px] font-medium uppercase tracking-widest text-muted-foreground">P&L</th>
                  <th className="px-3 py-2 text-center text-[11px] font-medium uppercase tracking-widest text-muted-foreground">Reversal?</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {visibleTrades.map((t) => {
                  const entryDate = t.entry_time ? new Date(t.entry_time) : null;
                  const entryLabel = entryDate
                    ? entryDate.toLocaleDateString('en-IN', { day: '2-digit', month: 'short' })
                    : '—';
                  const holdMins = t.duration_minutes;
                  const holdLabel = holdMins == null ? '—'
                    : holdMins >= 1440 ? `${Math.floor(holdMins / 1440)}d ${Math.floor((holdMins % 1440) / 60)}h`
                    : holdMins >= 60 ? `${Math.floor(holdMins / 60)}h ${holdMins % 60}m`
                    : `${holdMins}m`;
                  return (
                    <tr key={t.id} className={cn(
                      'hover:bg-muted/40 transition-colors',
                      t.is_reversal && 'bg-orange-50/30 dark:bg-orange-950/10'
                    )}>
                      <td className="px-4 py-2.5">
                        <div className="flex items-center gap-1.5">
                          {t.hold_type === 'weekend_hold' && (
                            <span title="Weekend hold — 2 extra theta days" className="text-[10px] bg-indigo-100 dark:bg-indigo-900/40 text-indigo-600 dark:text-indigo-400 px-1 rounded">WE</span>
                          )}
                          <span className="text-sm font-medium text-foreground font-mono">{t.tradingsymbol}</span>
                        </div>
                      </td>
                      <td className="px-3 py-2.5 text-xs text-muted-foreground">{t.instrument_type || '—'}</td>
                      <td className="px-3 py-2.5 text-xs text-muted-foreground">{entryLabel}</td>
                      <td className="px-3 py-2.5 text-right text-xs tabular-nums text-muted-foreground">{holdLabel}</td>
                      <td className={cn(
                        'px-3 py-2.5 text-right text-sm tabular-nums font-mono',
                        t.realized_pnl >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
                      )}>
                        {t.realized_pnl >= 0 ? '+' : ''}{formatCurrency(t.realized_pnl)}
                      </td>
                      <td className="px-3 py-2.5 text-center">
                        {t.is_reversal ? (
                          <span className="text-[10px] font-semibold text-orange-600 dark:text-orange-400 uppercase tracking-wide">
                            ↓ Reversed
                          </span>
                        ) : t.was_profitable_at_eod === true ? (
                          <span className="text-[10px] text-green-600 dark:text-green-400">Held well</span>
                        ) : t.was_profitable_at_eod === false ? (
                          <span className="text-[10px] text-red-600 dark:text-red-400">EOD loss</span>
                        ) : (
                          <span className="text-[10px] text-muted-foreground">—</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {trades.length > 5 && (
            <div className="px-5 py-3 border-t border-border">
              <button
                onClick={() => setShowTrades(!showTrades)}
                className="text-xs text-muted-foreground hover:text-foreground transition-colors"
              >
                {showTrades ? 'Show less' : `Show all ${trades.length} BTST trades`}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── OptionsPatternCard ────────────────────────────────────────────────────────

interface OptionsPatternData {
  period_days: number;
  has_data: boolean;
  direction_confusion: {
    count: number;
    underlying_breakdown: Record<string, number>;
    avg_flip_minutes: number | null;
  };
  premium_avg_down: {
    count: number;
    total_re_entry_premium: number;
    avg_worst_loss_pct: number | null;
  };
  iv_crush: {
    count: number;
    total_loss: number;
    avg_hold_minutes: number | null;
    avg_loss_pct: number | null;
  };
}

function OptionsPatternCard({ days }: { days: number }) {
  const [data, setData] = useState<OptionsPatternData | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await api.get('/api/analytics/options-behavior', { params: { days } });
        if (!cancelled) setData(res.data);
      } catch {
        if (!cancelled) setData(null);
      }
    })();
    return () => { cancelled = true; };
  }, [days]);

  if (!data?.has_data) return null;

  const { direction_confusion: dc, premium_avg_down: pad, iv_crush: iv } = data;

  const topUnderlying = Object.entries(dc.underlying_breakdown || {})
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3);

  const rows: {
    icon: React.ReactNode;
    label: string;
    count: number;
    sub: string;
    detail: string;
    severity: 'amber' | 'red' | 'orange';
  }[] = [];

  if (dc.count > 0) {
    const underlyingStr = topUnderlying.length
      ? topUnderlying.map(([u, c]) => `${u} ×${c}`).join(', ')
      : '';
    rows.push({
      icon: <Activity className="h-4 w-4" />,
      label: 'Direction Confusion',
      count: dc.count,
      sub: dc.avg_flip_minutes != null ? `avg ${dc.avg_flip_minutes}min between flip` : '',
      detail: underlyingStr ? `On: ${underlyingStr}` : 'CE→PE flip on same underlying',
      severity: 'amber',
    });
  }

  if (pad.count > 0) {
    rows.push({
      icon: <RefreshCw className="h-4 w-4" />,
      label: 'Premium Averaging Down',
      count: pad.count,
      sub: pad.total_re_entry_premium > 0
        ? `₹${pad.total_re_entry_premium.toLocaleString('en-IN')} re-entry premium spent`
        : '',
      detail: pad.avg_worst_loss_pct != null
        ? `Prior position avg loss: ${pad.avg_worst_loss_pct}% before re-entry`
        : 'Re-entered same underlying options after a loss',
      severity: 'orange',
    });
  }

  if (iv.count > 0) {
    rows.push({
      icon: <Zap className="h-4 w-4" />,
      label: 'IV Crush',
      count: iv.count,
      sub: iv.total_loss > 0
        ? `₹${iv.total_loss.toLocaleString('en-IN')} total lost`
        : '',
      detail: [
        iv.avg_hold_minutes != null && `avg hold ${iv.avg_hold_minutes}min`,
        iv.avg_loss_pct != null && `avg ${iv.avg_loss_pct}% premium lost`,
      ].filter(Boolean).join(' · ') || 'Fast large premium collapse',
      severity: 'red',
    });
  }

  if (!rows.length) return null;

  const severityStyles = {
    amber: {
      borderL: 'border-l-amber-400',
      icon: 'text-amber-600 dark:text-amber-400',
      badge: 'text-amber-600 dark:text-amber-400',
    },
    orange: {
      borderL: 'border-l-orange-400',
      icon: 'text-orange-600 dark:text-orange-400',
      badge: 'text-orange-600 dark:text-orange-400',
    },
    red: {
      borderL: 'border-l-red-500',
      icon: 'text-red-600 dark:text-red-400',
      badge: 'text-red-600 dark:text-red-400',
    },
  };

  return (
    <div className="bg-card rounded-lg border border-border overflow-hidden">
      <div className="px-5 py-4 border-b border-border flex items-center gap-2">
        <Zap className="h-4 w-4 text-amber-500" />
        <p className="text-xs font-medium uppercase tracking-widest text-muted-foreground">
          Options Behavioral Patterns
        </p>
        <span className="text-xs text-muted-foreground ml-auto">Last {days} days</span>
      </div>
      <div className="p-5 space-y-3">
        {rows.map((row) => {
          const s = severityStyles[row.severity];
          return (
            <div
              key={row.label}
              className={cn('border-l-2 px-4 py-3 bg-card rounded-sm', s.borderL)}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2">
                  <span className={s.icon}>{row.icon}</span>
                  <span className="text-sm font-medium text-foreground">{row.label}</span>
                </div>
                <span className={cn('text-xs font-mono tabular-nums', s.badge)}>
                  {row.count}× / {days <= 7 ? 'week' : days <= 31 ? 'month' : `${days}d`}
                </span>
              </div>
              {row.detail && (
                <p className="text-xs text-muted-foreground mt-1.5 leading-relaxed">{row.detail}</p>
              )}
              {row.sub && (
                <p className="text-xs text-muted-foreground mt-0.5">{row.sub}</p>
              )}
            </div>
          );
        })}
        <p className="text-[11px] text-muted-foreground pt-1">
          These patterns are unique to options traders and invisible in standard P&L reports.
        </p>
      </div>
    </div>
  );
}
