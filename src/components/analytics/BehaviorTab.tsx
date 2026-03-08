import { useState, useEffect } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, ReferenceLine, PieChart, Pie,
} from 'recharts';
import {
  Loader2, AlertTriangle, CheckCircle2, Brain, BookOpen,
  ArrowUpRight, ArrowDownRight, Shield, Clock, AlertCircle,
  TrendingDown, Lightbulb,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatCurrency } from '@/lib/formatters';
import { api } from '@/lib/api';
import AINarrativeCard from './AINarrativeCard';

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
  behavior_score: number;
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
  critical: 'text-red-700 bg-red-50 dark:text-red-400 dark:bg-red-900/20',
  high: 'text-red-600 bg-red-50 dark:text-red-400 dark:bg-red-900/20',
  medium: 'text-amber-600 bg-amber-50 dark:text-amber-400 dark:bg-amber-900/20',
  low: 'text-blue-600 bg-blue-50 dark:text-blue-400 dark:bg-blue-900/20',
  positive: 'text-green-600 bg-green-50 dark:text-green-400 dark:bg-green-900/20',
};

const severityOrder: Record<string, number> = {
  critical: 0, high: 1, medium: 2, low: 3, positive: 4,
};

export default function BehaviorTab({ days }: BehaviorTabProps) {
  const [behavioral, setBehavioral] = useState<BehavioralData | null>(null);
  const [journal, setJournal] = useState<JournalData | null>(null);
  const [aiInsights, setAiInsights] = useState<AIInsightsData | null>(null);
  const [isLoading, setIsLoading] = useState(true);

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
      <div className="flex items-center justify-center min-h-[40vh]">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  // Fixed: handle null AND empty array
  if (!behavioral || !behavioral.patterns_detected || (behavioral.total_trades_analyzed < 5 && behavioral.patterns_detected.length === 0)) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[40vh] bg-card rounded-lg border border-border">
        <Brain className="h-10 w-10 text-muted-foreground/40 mb-3" />
        <p className="font-medium text-foreground">Not enough data for behavioral analysis</p>
        <p className="text-sm text-muted-foreground mt-1">Need at least 5 completed trades</p>
      </div>
    );
  }

  const dangers = behavioral.patterns_detected
    .filter(p => !p.is_positive)
    .sort((a, b) => (severityOrder[a.severity] ?? 3) - (severityOrder[b.severity] ?? 3));
  const strengths = behavioral.patterns_detected.filter(p => p.is_positive);

  // Emotional tax breakdown for pie chart
  const emotionalBreakdown = Object.entries(behavioral.emotional_breakdown || {})
    .map(([name, amount]) => ({ name: name.replace(/_/g, ' '), value: Math.abs(amount) }))
    .filter(d => d.value > 0)
    .sort((a, b) => b.value - a.value);

  const COLORS = ['#ef4444', '#f97316', '#eab308', '#06b6d4', '#8b5cf6', '#ec4899', '#6b7280'];

  // Predictive warnings from pattern prediction service
  const predictions = aiInsights?.predictions || {};
  const sortedPredictions = Object.entries(predictions)
    .map(([key, val]) => ({ pattern: key.replace(/_/g, ' '), ...val }))
    .sort((a, b) => b.probability - a.probability)
    .filter(p => p.probability > 0);

  return (
    <div className="space-y-4">
      {/* AI Narrative */}
      <AINarrativeCard tab="behavior" days={days} />

      {/* Predictive Warnings */}
      {sortedPredictions.length > 0 && (
        <div className="bg-card border border-border rounded-lg p-4">
          <div className="flex items-center gap-2 mb-3">
            <Shield className="h-4 w-4 text-amber-500" />
            <h3 className="text-sm font-semibold">Real-Time Pattern Predictions</h3>
            {aiInsights?.risk_assessment?.overall_risk && (
              <span className={cn(
                'text-[10px] font-medium px-1.5 py-0.5 rounded uppercase',
                aiInsights.risk_assessment.overall_risk === 'critical' ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' :
                  aiInsights.risk_assessment.overall_risk === 'high' ? 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400' :
                    aiInsights.risk_assessment.overall_risk === 'medium' ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400' :
                      'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
              )}>
                {aiInsights.risk_assessment.overall_risk} risk
              </span>
            )}
          </div>
          <div className="space-y-2">
            {sortedPredictions.map((pred) => (
              <div key={pred.pattern} className="flex items-center gap-3">
                <span className="text-xs text-muted-foreground w-28 truncate capitalize">{pred.pattern}</span>
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
            <p className="text-xs text-muted-foreground mt-2 italic">
              {aiInsights.risk_assessment.message}
            </p>
          )}
        </div>
      )}

      {/* Score + Emotional Tax + Trades Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-px bg-border rounded-lg overflow-hidden">
        <div className="bg-card px-5 py-4">
          <p className="text-xs text-muted-foreground mb-1">Behavior Score</p>
          <div className="flex items-end gap-2">
            <p className={cn(
              'text-3xl font-bold tabular-nums font-mono',
              behavioral.behavior_score >= 70 ? 'text-green-600 dark:text-green-400' :
                behavioral.behavior_score >= 40 ? 'text-amber-600 dark:text-amber-400' :
                  'text-red-600 dark:text-red-400'
            )}>
              {behavioral.behavior_score}
              <span className="text-base text-muted-foreground font-normal">/100</span>
            </p>
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            {behavioral.behavior_score >= 70 ? 'Disciplined trader' :
              behavioral.behavior_score >= 40 ? 'Room for improvement' :
                'High emotional interference'}
          </p>
        </div>
        <div className="bg-card px-5 py-4">
          <p className="text-xs text-muted-foreground mb-1">Emotional Tax</p>
          <p className="text-3xl font-bold tabular-nums font-mono text-red-600 dark:text-red-400">
            {formatCurrency(behavioral.emotional_tax)}
          </p>
          <p className="text-xs text-muted-foreground mt-1">
            Lost to behavioral patterns in {days} days
          </p>
        </div>
        <div className="bg-card px-5 py-4">
          <p className="text-xs text-muted-foreground mb-1">Analysis Summary</p>
          <p className="text-3xl font-bold tabular-nums font-mono text-foreground">
            {behavioral.total_trades_analyzed}
            <span className="text-base text-muted-foreground font-normal ml-1">trades</span>
          </p>
          <p className="text-xs text-muted-foreground mt-1">
            {dangers.length} risk pattern{dangers.length !== 1 ? 's' : ''} &middot; {strengths.length} strength{strengths.length !== 1 ? 's' : ''}
          </p>
        </div>
      </div>

      {/* Emotional Tax Breakdown */}
      {emotionalBreakdown.length > 0 && (
        <div className="bg-card rounded-lg border border-border overflow-hidden">
          <div className="px-4 py-3 border-b border-border">
            <div className="flex items-center gap-2">
              <TrendingDown className="h-4 w-4 text-red-600" />
              <div>
                <h3 className="text-sm font-semibold text-foreground">Where You're Losing Money</h3>
                <p className="text-xs text-muted-foreground">Cost breakdown by behavioral pattern</p>
              </div>
            </div>
          </div>
          <div className="px-4 py-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Breakdown table */}
              <div className="space-y-2">
                {emotionalBreakdown.slice(0, 6).map((item, i) => (
                  <div key={item.name} className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: COLORS[i % COLORS.length] }} />
                      <span className="text-sm text-foreground capitalize">{item.name}</span>
                    </div>
                    <span className="text-sm tabular-nums font-mono text-red-600 dark:text-red-400 font-medium">
                      -{formatCurrency(item.value)}
                    </span>
                  </div>
                ))}
              </div>
              {/* Pie chart */}
              <div className="h-[160px]">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={emotionalBreakdown.slice(0, 6)}
                      cx="50%"
                      cy="50%"
                      innerRadius={40}
                      outerRadius={70}
                      paddingAngle={2}
                      dataKey="value"
                    >
                      {emotionalBreakdown.slice(0, 6).map((_, i) => (
                        <Cell key={i} fill={COLORS[i % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip
                      formatter={(value: number) => formatCurrency(value)}
                      contentStyle={{
                        backgroundColor: 'hsl(var(--popover))',
                        border: '1px solid hsl(var(--border))',
                        borderRadius: '8px',
                        fontSize: '12px',
                      }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Detected Patterns Table */}
      {behavioral.patterns_detected.length > 0 && (
        <div className="bg-card rounded-lg border border-border overflow-hidden">
          <div className="px-4 py-3 border-b border-border">
            <h3 className="text-sm font-semibold text-foreground">Detected Patterns</h3>
            <p className="text-xs text-muted-foreground">{behavioral.patterns_detected.length} patterns found in last {days} days</p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border bg-muted/30">
                  <th className="px-4 py-2 text-left text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Pattern</th>
                  <th className="px-3 py-2 text-left text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Category</th>
                  <th className="px-3 py-2 text-center text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Severity</th>
                  <th className="px-3 py-2 text-right text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Freq</th>
                  <th className="px-3 py-2 text-right text-[11px] font-medium uppercase tracking-wide text-muted-foreground">P&L Impact</th>
                  <th className="px-4 py-2 text-left text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Recommendation</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {[...behavioral.patterns_detected]
                  .sort((a, b) => (severityOrder[a.severity] ?? 3) - (severityOrder[b.severity] ?? 3))
                  .map((pattern, i) => (
                    <tr key={i} className="hover:bg-muted/30">
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
                          'px-2 py-0.5 rounded text-[10px] font-medium uppercase',
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
          {/* Weaknesses */}
          <div className="bg-card rounded-lg border border-border overflow-hidden">
            <div className="px-4 py-3 border-b border-border bg-red-50/50 dark:bg-red-900/10">
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-red-600" />
                <h3 className="text-sm font-semibold text-foreground">Areas to Improve ({dangers.length})</h3>
              </div>
            </div>
            <div className="divide-y divide-border">
              {dangers.length > 0 ? dangers.map((p, i) => (
                <div key={i} className="px-4 py-3">
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
                <div className="px-4 py-6 text-center">
                  <CheckCircle2 className="h-6 w-6 text-green-600 mx-auto mb-1" />
                  <p className="text-sm text-muted-foreground">No concerning patterns</p>
                </div>
              )}
            </div>
          </div>

          {/* Strengths */}
          <div className="bg-card rounded-lg border border-border overflow-hidden">
            <div className="px-4 py-3 border-b border-border bg-green-50/50 dark:bg-green-900/10">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-green-600" />
                <h3 className="text-sm font-semibold text-foreground">Your Strengths ({strengths.length})</h3>
              </div>
            </div>
            <div className="divide-y divide-border">
              {strengths.length > 0 ? strengths.map((p, i) => (
                <div key={i} className="px-4 py-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-medium text-foreground">{p.name}</span>
                    <span className="text-xs tabular-nums font-mono text-green-600">{p.frequency}x</span>
                  </div>
                  <p className="text-xs text-muted-foreground">{p.description}</p>
                </div>
              )) : (
                <div className="px-4 py-6 text-center">
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
          <div className="px-4 py-3 border-b border-border bg-primary/5">
            <div className="flex items-center gap-2">
              <Lightbulb className="h-4 w-4 text-primary" />
              <div>
                <h3 className="text-sm font-semibold text-foreground">Personalized Insights</h3>
                <p className="text-xs text-muted-foreground">AI-learned patterns from your trading history</p>
              </div>
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-px bg-border">
            {/* Danger Hours */}
            {aiInsights.personalization.danger_hours?.length > 0 && (
              <div className="bg-card px-4 py-3">
                <div className="flex items-center gap-1.5 mb-2">
                  <Clock className="h-3.5 w-3.5 text-red-500" />
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Danger Hours</p>
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

            {/* Best Hours */}
            {aiInsights.personalization.best_hours?.length > 0 && (
              <div className="bg-card px-4 py-3">
                <div className="flex items-center gap-1.5 mb-2">
                  <Clock className="h-3.5 w-3.5 text-green-500" />
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Best Hours</p>
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

            {/* Problem Symbols */}
            {aiInsights.personalization.problem_symbols?.length > 0 && (
              <div className="bg-card px-4 py-3">
                <div className="flex items-center gap-1.5 mb-2">
                  <AlertCircle className="h-3.5 w-3.5 text-red-500" />
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Problem Symbols</p>
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

            {/* Strong Symbols */}
            {aiInsights.personalization.strong_symbols?.length > 0 && (
              <div className="bg-card px-4 py-3">
                <div className="flex items-center gap-1.5 mb-2">
                  <Shield className="h-3.5 w-3.5 text-green-500" />
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Strong Symbols</p>
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

          {/* Trading Intensity */}
          {aiInsights.trading_intensity && (
            <div className="border-t border-border px-4 py-3">
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">Trading Intensity</p>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <p className="text-lg font-bold tabular-nums font-mono text-foreground">{aiInsights.trading_intensity.avg_daily_trades}</p>
                  <p className="text-xs text-muted-foreground">Avg trades/day</p>
                </div>
                <div>
                  <p className="text-lg font-bold tabular-nums font-mono text-foreground">{aiInsights.trading_intensity.max_daily_trades}</p>
                  <p className="text-xs text-muted-foreground">Max in one day</p>
                </div>
                <div>
                  <p className="text-lg font-bold tabular-nums font-mono text-foreground">{aiInsights.trading_intensity.active_days}</p>
                  <p className="text-xs text-muted-foreground">Active days</p>
                </div>
                <div>
                  <p className={cn(
                    'text-lg font-bold tabular-nums font-mono',
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
          <div className="px-4 py-3 border-b border-border">
            <div className="flex items-center gap-2">
              <BookOpen className="h-4 w-4 text-muted-foreground" />
              <div>
                <h3 className="text-sm font-semibold text-foreground">Journal-Emotion Correlation</h3>
                <p className="text-xs text-muted-foreground">{journal.total_journaled} journaled trades — how your emotions affect outcomes</p>
              </div>
            </div>
          </div>

          {/* Chart */}
          <div className="px-4 py-4">
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
                    className="capitalize"
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

          {/* Table */}
          <div className="border-t border-border overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="bg-muted/30">
                  <th className="px-4 py-2 text-left text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Emotion</th>
                  <th className="px-3 py-2 text-right text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Trades</th>
                  <th className="px-3 py-2 text-right text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Avg P&L</th>
                  <th className="px-3 py-2 text-right text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Total P&L</th>
                  <th className="px-3 py-2 text-right text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Win Rate</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {journal.by_emotion.map((e, i) => (
                  <tr key={i} className="hover:bg-muted/30">
                    <td className="px-4 py-2 text-sm font-medium text-foreground capitalize">{e.emotion}</td>
                    <td className="px-3 py-2 text-right text-sm tabular-nums">{e.trade_count}</td>
                    <td className={cn(
                      'px-3 py-2 text-right text-sm tabular-nums font-mono',
                      e.avg_pnl >= 0 ? 'text-green-600' : 'text-red-600'
                    )}>
                      {e.avg_pnl >= 0 ? '+' : ''}{formatCurrency(e.avg_pnl)}
                    </td>
                    <td className={cn(
                      'px-3 py-2 text-right text-sm tabular-nums font-mono',
                      e.total_pnl >= 0 ? 'text-green-600' : 'text-red-600'
                    )}>
                      {e.total_pnl >= 0 ? '+' : ''}{formatCurrency(e.total_pnl)}
                    </td>
                    <td className={cn(
                      'px-3 py-2 text-right text-sm tabular-nums',
                      e.win_rate >= 50 ? 'text-green-600' : 'text-red-600'
                    )}>
                      {e.win_rate}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* AI Trading Persona */}
      {behavioral.trading_persona && (
        <div className="bg-card rounded-lg border border-border overflow-hidden">
          <div className="px-4 py-3 border-b border-border">
            <div className="flex items-center gap-2">
              <Brain className="h-4 w-4 text-primary" />
              <h3 className="text-sm font-semibold text-foreground">AI Trading Persona</h3>
            </div>
            <p className="text-xs text-muted-foreground mt-0.5">AI-generated profile based on your trading behavior</p>
          </div>
          <div className="px-4 py-4">
            {typeof behavioral.trading_persona === 'string' ? (
              <p className="text-sm text-muted-foreground leading-relaxed whitespace-pre-line">
                {behavioral.trading_persona}
              </p>
            ) : (
              <div className="space-y-3">
                {behavioral.trading_persona.persona && (
                  <p className="text-sm font-semibold text-foreground">
                    {typeof behavioral.trading_persona.persona === 'object'
                      ? (behavioral.trading_persona.persona as any).persona || 'Unknown Persona'
                      : behavioral.trading_persona.persona}
                  </p>
                )}
                {behavioral.trading_persona.description && (
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    {typeof behavioral.trading_persona.description === 'object'
                      ? (behavioral.trading_persona.description as any).description || ''
                      : behavioral.trading_persona.description}
                  </p>
                )}
                {behavioral.trading_persona.strengths?.length > 0 && (
                  <div>
                    <p className="text-xs font-medium text-green-600 dark:text-green-400 uppercase tracking-wide mb-1">Strengths</p>
                    <ul className="space-y-0.5">
                      {(Array.isArray(behavioral.trading_persona.strengths) ? behavioral.trading_persona.strengths : [behavioral.trading_persona.strengths]).map((s, i) => (
                        <li key={i} className="text-sm text-muted-foreground flex gap-2"><span className="text-green-500 flex-shrink-0">+</span>{typeof s === 'string' ? s : JSON.stringify(s)}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {behavioral.trading_persona.weaknesses?.length > 0 && (
                  <div>
                    <p className="text-xs font-medium text-red-600 dark:text-red-400 uppercase tracking-wide mb-1">Watch Out For</p>
                    <ul className="space-y-0.5">
                      {(Array.isArray(behavioral.trading_persona.weaknesses) ? behavioral.trading_persona.weaknesses : [behavioral.trading_persona.weaknesses]).map((w, i) => (
                        <li key={i} className="text-sm text-muted-foreground flex gap-2"><span className="text-red-500 flex-shrink-0">−</span>{typeof w === 'string' ? w : JSON.stringify(w)}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {behavioral.trading_persona.next_steps && (
                  <div>
                    <p className="text-xs font-medium text-primary uppercase tracking-wide mb-1">Next Steps</p>
                    <ul className="space-y-0.5">
                      {(Array.isArray(behavioral.trading_persona.next_steps) ? behavioral.trading_persona.next_steps : [behavioral.trading_persona.next_steps]).map((n, i) => (
                        <li key={i} className="text-sm text-muted-foreground flex gap-2"><span className="text-primary flex-shrink-0">→</span>{typeof n === 'string' ? n : JSON.stringify(n)}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Focus Area CTA */}
      {(behavioral.focus_area || behavioral.top_strength) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {behavioral.top_strength && (
            <div className="bg-green-50/50 dark:bg-green-900/10 rounded-lg border border-green-200 dark:border-green-800 px-4 py-3">
              <div className="flex items-center gap-2 mb-1">
                <ArrowUpRight className="h-4 w-4 text-green-600" />
                <p className="text-xs font-medium text-green-700 dark:text-green-400 uppercase tracking-wide">Top Strength</p>
              </div>
              <p className="text-sm font-medium text-foreground">{behavioral.top_strength}</p>
            </div>
          )}
          {behavioral.focus_area && (
            <div className="bg-amber-50/50 dark:bg-amber-900/10 rounded-lg border border-amber-200 dark:border-amber-800 px-4 py-3">
              <div className="flex items-center gap-2 mb-1">
                <ArrowDownRight className="h-4 w-4 text-amber-600" />
                <p className="text-xs font-medium text-amber-700 dark:text-amber-400 uppercase tracking-wide">Focus Area</p>
              </div>
              <p className="text-sm font-medium text-foreground">{behavioral.focus_area}</p>
            </div>
          )}
        </div>
      )}
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
