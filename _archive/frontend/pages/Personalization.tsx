import { useState, useEffect, useCallback } from 'react';
import { useBroker } from '@/contexts/BrokerContext';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { cn } from '@/lib/utils';
import {
  Brain, Clock, TrendingUp, TrendingDown, BarChart3,
  Target, Lightbulb, RefreshCw, Sparkles, Calendar, Zap,
} from 'lucide-react';
import { toast } from 'sonner';
import { api } from '@/lib/api';

interface TimeAnalysis {
  best_hours: Array<{ hour: number; win_rate: number; avg_pnl: number; trade_count: number }>;
  worst_hours: Array<{ hour: number; win_rate: number; avg_pnl: number; trade_count: number }>;
  best_days: Array<{ day: string; win_rate: number; avg_pnl: number; trade_count: number }>;
  worst_days: Array<{ day: string; win_rate: number; avg_pnl: number; trade_count: number }>;
  recommendations: string[];
}

interface SymbolAnalysis {
  best_symbols: Array<{ symbol: string; win_rate: number; avg_pnl: number; trade_count: number }>;
  worst_symbols: Array<{ symbol: string; win_rate: number; avg_pnl: number; trade_count: number }>;
  overtraded_symbols: Array<{ symbol: string; trade_count: number; loss_rate: number }>;
  recommendations: string[];
}

interface PersonalizedInsight {
  type: 'strength' | 'weakness' | 'pattern' | 'recommendation';
  title: string;
  description: string;
  confidence: number;
  action?: string;
}

interface InterventionTiming {
  optimal_cooldown_duration: number;
  escalation_effectiveness: number;
  skip_rate: number;
  recommendations: string[];
}

export default function Personalization() {
  const { account } = useBroker();
  const [insights, setInsights] = useState<PersonalizedInsight[]>([]);
  const [timeAnalysis, setTimeAnalysis] = useState<TimeAnalysis | null>(null);
  const [symbolAnalysis, setSymbolAnalysis] = useState<SymbolAnalysis | null>(null);
  const [interventionTiming, setInterventionTiming] = useState<InterventionTiming | null>(null);
  const [behavioralInsights, setBehavioralInsights] = useState<any[]>([]);
  const [behavioralStatus, setBehavioralStatus] = useState<string>('loading');
  const [sessionsAnalyzed, setSessionsAnalyzed] = useState<number>(0);
  const [isLoading, setIsLoading] = useState(true);
  const [isLearning, setIsLearning] = useState(false);
  const [lastLearned, setLastLearned] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    if (!account?.id) return;
    try {
      setIsLoading(true);
      const [insightsRes, timeRes, symbolRes, interventionRes, behavioralRes] = await Promise.allSettled([
        api.get(`/api/personalization/insights`),
        api.get(`/api/personalization/time-analysis`),
        api.get(`/api/personalization/symbol-analysis`),
        api.get(`/api/personalization/intervention-timing`),
        api.get(`/api/profile/behavioral-insights`),
      ]);
      if (insightsRes.status === 'fulfilled') {
        setInsights(insightsRes.value.data.insights || []);
        setLastLearned(insightsRes.value.data.last_learned_at);
      }
      if (timeRes.status === 'fulfilled') setTimeAnalysis(timeRes.value.data);
      if (symbolRes.status === 'fulfilled') setSymbolAnalysis(symbolRes.value.data);
      if (interventionRes.status === 'fulfilled') setInterventionTiming(interventionRes.value.data);
      if (behavioralRes.status === 'fulfilled') {
        setBehavioralInsights(behavioralRes.value.data.insights || []);
        setBehavioralStatus(behavioralRes.value.data.status || 'insufficient_data');
        setSessionsAnalyzed(behavioralRes.value.data.sessions_analyzed || 0);
      }
    } catch (error) {
      console.error('Failed to fetch personalization data:', error);
    } finally {
      setIsLoading(false);
    }
  }, [account?.id]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleLearnPatterns = async () => {
    if (!account?.id) return;
    try {
      setIsLearning(true);
      await api.post(`/api/personalization/learn`);
      toast.success('Pattern learning completed!');
      fetchData();
    } catch (error) {
      console.error('Failed to learn patterns:', error);
      toast.error('Failed to learn patterns');
    } finally {
      setIsLearning(false);
    }
  };

  const formatHour = (hour: number) => {
    const ampm = hour >= 12 ? 'PM' : 'AM';
    const h = hour % 12 || 12;
    return `${h}:00 ${ampm}`;
  };

  // ── Guard states ─────────────────────────────────────────────────────────────

  if (!account) {
    return (
      <div className="flex items-center gap-3 px-4 py-3 rounded-lg bg-tm-brand/5 border border-tm-brand/20">
        <Brain className="h-4 w-4 text-tm-brand shrink-0" />
        <div>
          <p className="text-sm font-medium text-foreground">No account connected</p>
          <p className="text-[13px] text-muted-foreground">Connect your broker to access personalized insights.</p>
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px]">
        <Brain className="h-10 w-10 animate-pulse text-tm-brand mb-3" />
        <p className="text-sm text-muted-foreground">Analyzing your trading patterns…</p>
      </div>
    );
  }

  // ── Helpers ──────────────────────────────────────────────────────────────────

  const insightStyle = (type: PersonalizedInsight['type']) => ({
    card: type === 'strength'       ? 'border-l-4 border-l-tm-profit'
        : type === 'weakness'       ? 'border-l-4 border-l-tm-loss'
        : type === 'pattern'        ? 'border-l-4 border-l-tm-brand'
        :                             'border-l-4 border-l-tm-obs',
    icon: type === 'strength'       ? 'bg-tm-profit/10 text-tm-profit'
        : type === 'weakness'       ? 'bg-tm-loss/10 text-tm-loss'
        : type === 'pattern'        ? 'bg-tm-brand/10 text-tm-brand'
        :                             'bg-tm-obs/10 text-tm-obs',
  });

  // ── Render ───────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-5">

      {/* What we've learned */}
      {behavioralStatus === 'active' && behavioralInsights.length > 0 && (
        <div className="tm-card border-l-4 border-l-tm-brand bg-tm-brand/[0.03]">
          <div className="px-5 py-3.5 border-b border-slate-100 dark:border-neutral-700/60">
            <div className="flex items-center gap-2">
              <Brain className="h-4 w-4 text-tm-brand" />
              <span className="text-[13px] font-semibold text-foreground">What we've learned about you</span>
            </div>
            <p className="text-[12px] text-muted-foreground mt-0.5">
              Based on {sessionsAnalyzed} trading sessions — your personal thresholds, not defaults.
            </p>
          </div>
          <div className="p-5 space-y-3">
            {behavioralInsights.map((insight: any, i: number) => (
              <div key={i} className="flex items-start gap-3 p-3 rounded-lg bg-background border border-border">
                <Sparkles className="h-4 w-4 text-tm-brand mt-0.5 shrink-0" />
                <div>
                  <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide mb-0.5">
                    {insight.category}
                  </p>
                  <p className="text-[13px] text-foreground">{insight.insight}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {behavioralStatus === 'insufficient_data' && (
        <div className="tm-card border border-dashed">
          <div className="py-8 text-center">
            <Brain className="h-8 w-8 text-muted-foreground/40 mx-auto mb-2.5" />
            <p className="text-sm font-medium text-foreground">Behavioral learning in progress</p>
            <p className="text-[12px] text-muted-foreground mt-1">
              Trade for at least 5 sessions and we'll show you what we've learned about your patterns.
            </p>
          </div>
        </div>
      )}

      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-foreground tracking-tight flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-tm-brand" />
            Personalized Insights
          </h1>
          <p className="text-[13px] text-muted-foreground mt-0.5">
            AI-powered analysis of your unique trading patterns
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={fetchData}
            disabled={isLoading}
            className="flex items-center gap-1.5 px-3 py-1.5 text-[13px] font-medium rounded-lg border border-border hover:bg-muted transition-colors disabled:opacity-50"
          >
            <RefreshCw className={cn('h-3.5 w-3.5', isLoading && 'animate-spin')} />
            Refresh
          </button>
          <button
            onClick={handleLearnPatterns}
            disabled={isLearning}
            className="flex items-center gap-1.5 px-3 py-1.5 text-[13px] font-semibold rounded-lg bg-tm-brand text-white hover:bg-tm-brand/90 transition-colors disabled:opacity-50"
          >
            <Brain className={cn('h-3.5 w-3.5', isLearning && 'animate-pulse')} />
            {isLearning ? 'Learning…' : 'Learn Patterns'}
          </button>
        </div>
      </div>

      {/* Last learned banner */}
      {lastLearned && (
        <div className="flex items-center gap-2.5 px-4 py-2.5 rounded-lg bg-tm-brand/5 border border-tm-brand/20">
          <Zap className="h-3.5 w-3.5 text-tm-brand shrink-0" />
          <div>
            <span className="text-[13px] font-medium text-foreground">AI model updated · </span>
            <span className="text-[13px] text-muted-foreground">
              Last learned: {new Date(lastLearned).toLocaleString()}
            </span>
          </div>
        </div>
      )}

      {/* Insights grid */}
      {insights.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {insights.map((insight, i) => {
            const s = insightStyle(insight.type);
            return (
              <div key={i} className={cn('tm-card overflow-hidden', s.card)}>
                <div className="p-4">
                  <div className="flex items-start gap-3">
                    <div className={cn('p-2 rounded-lg shrink-0', s.icon)}>
                      {insight.type === 'strength'       && <TrendingUp className="h-4 w-4" />}
                      {insight.type === 'weakness'       && <TrendingDown className="h-4 w-4" />}
                      {insight.type === 'pattern'        && <BarChart3 className="h-4 w-4" />}
                      {insight.type === 'recommendation' && <Lightbulb className="h-4 w-4" />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-2 mb-1">
                        <p className="text-[13px] font-semibold text-foreground leading-snug">{insight.title}</p>
                        <span className="text-[11px] font-mono tabular-nums text-muted-foreground shrink-0">
                          {Math.round(insight.confidence * 100)}%
                        </span>
                      </div>
                      <p className="text-[12px] text-muted-foreground leading-snug">{insight.description}</p>
                      {insight.action && (
                        <p className="text-[12px] font-medium mt-2 text-tm-brand">{insight.action}</p>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Analysis Tabs */}
      <Tabs defaultValue="time">
        <TabsList className="flex gap-1 h-9 bg-muted/50 p-1 rounded-lg w-full md:w-auto">
          <TabsTrigger value="time" className="flex items-center gap-1.5 text-[12px]">
            <Clock className="h-3.5 w-3.5" />
            Time Analysis
          </TabsTrigger>
          <TabsTrigger value="symbols" className="flex items-center gap-1.5 text-[12px]">
            <Target className="h-3.5 w-3.5" />
            Symbols
          </TabsTrigger>
          <TabsTrigger value="intervention" className="flex items-center gap-1.5 text-[12px]">
            <Zap className="h-3.5 w-3.5" />
            Intervention
          </TabsTrigger>
        </TabsList>

        {/* ── Time Analysis ──────────────────────────────────────────────────── */}
        <TabsContent value="time" className="mt-4 space-y-4">
          {timeAnalysis ? (
            <div className="grid md:grid-cols-2 gap-4">

              {/* Best Hours */}
              <div className="tm-card">
                <div className="px-5 py-3 border-b border-slate-100 dark:border-neutral-700/60">
                  <div className="flex items-center gap-2 text-tm-profit">
                    <TrendingUp className="h-4 w-4" />
                    <span className="text-[13px] font-semibold">Your Best Trading Hours</span>
                  </div>
                  <p className="text-[12px] text-muted-foreground mt-0.5">Times when you perform best</p>
                </div>
                <div className="p-5">
                  {timeAnalysis.best_hours.length > 0 ? (
                    <div className="space-y-3">
                      {timeAnalysis.best_hours.slice(0, 5).map((item, i) => (
                        <div key={i} className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <span className="px-2 py-0.5 rounded text-[11px] font-mono tabular-nums bg-tm-profit/10 text-tm-profit">
                              {formatHour(item.hour)}
                            </span>
                            <span className="text-[12px] text-muted-foreground">{item.trade_count} trades</span>
                          </div>
                          <div className="text-right">
                            <p className="text-[13px] font-semibold text-tm-profit">{item.win_rate.toFixed(0)}% win</p>
                            <p className="text-[11px] text-muted-foreground font-mono">₹{item.avg_pnl.toFixed(0)} avg</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-[13px] text-muted-foreground text-center py-6">Not enough data yet</p>
                  )}
                </div>
              </div>

              {/* Worst Hours */}
              <div className="tm-card">
                <div className="px-5 py-3 border-b border-slate-100 dark:border-neutral-700/60">
                  <div className="flex items-center gap-2 text-tm-loss">
                    <TrendingDown className="h-4 w-4" />
                    <span className="text-[13px] font-semibold">Hours to Avoid</span>
                  </div>
                  <p className="text-[12px] text-muted-foreground mt-0.5">Times when you typically underperform</p>
                </div>
                <div className="p-5">
                  {timeAnalysis.worst_hours.length > 0 ? (
                    <div className="space-y-3">
                      {timeAnalysis.worst_hours.slice(0, 5).map((item, i) => (
                        <div key={i} className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <span className="px-2 py-0.5 rounded text-[11px] font-mono tabular-nums bg-tm-loss/10 text-tm-loss">
                              {formatHour(item.hour)}
                            </span>
                            <span className="text-[12px] text-muted-foreground">{item.trade_count} trades</span>
                          </div>
                          <div className="text-right">
                            <p className="text-[13px] font-semibold text-tm-loss">{item.win_rate.toFixed(0)}% win</p>
                            <p className="text-[11px] text-muted-foreground font-mono">₹{item.avg_pnl.toFixed(0)} avg</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-[13px] text-muted-foreground text-center py-6">Not enough data yet</p>
                  )}
                </div>
              </div>

              {/* Best Days */}
              <div className="tm-card">
                <div className="px-5 py-3 border-b border-slate-100 dark:border-neutral-700/60">
                  <div className="flex items-center gap-2">
                    <Calendar className="h-4 w-4 text-tm-profit" />
                    <span className="text-[13px] font-semibold text-foreground">Best Days of Week</span>
                  </div>
                </div>
                <div className="p-5">
                  {timeAnalysis.best_days.length > 0 ? (
                    <div className="space-y-2">
                      {timeAnalysis.best_days.map((item, i) => (
                        <div key={i} className="flex items-center justify-between p-2.5 rounded-lg bg-tm-profit/[0.04]">
                          <span className="text-[13px] font-medium text-foreground">{item.day}</span>
                          <div className="flex items-center gap-4">
                            <span className="text-[13px] font-mono tabular-nums text-tm-profit">{item.win_rate.toFixed(0)}% win</span>
                            <span className="text-[12px] text-muted-foreground font-mono">₹{item.avg_pnl.toFixed(0)} avg</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-[13px] text-muted-foreground text-center py-6">Not enough data yet</p>
                  )}
                </div>
              </div>

              {/* Time Recommendations */}
              <div className="tm-card">
                <div className="px-5 py-3 border-b border-slate-100 dark:border-neutral-700/60">
                  <div className="flex items-center gap-2">
                    <Lightbulb className="h-4 w-4 text-tm-obs" />
                    <span className="text-[13px] font-semibold text-foreground">Time-Based Recommendations</span>
                  </div>
                </div>
                <div className="p-5">
                  {timeAnalysis.recommendations.length > 0 ? (
                    <ul className="space-y-2">
                      {timeAnalysis.recommendations.map((rec, i) => (
                        <li key={i} className="flex items-start gap-2 text-[13px]">
                          <span className="text-tm-obs mt-px">•</span>
                          <span className="text-foreground">{rec}</span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-[13px] text-muted-foreground text-center py-6">
                      Trade more to unlock personalized recommendations
                    </p>
                  )}
                </div>
              </div>

            </div>
          ) : (
            <div className="tm-card">
              <div className="py-12 text-center">
                <Clock className="h-10 w-10 mx-auto text-muted-foreground/40 mb-3" />
                <p className="text-sm font-medium text-foreground mb-1">No time analysis available</p>
                <p className="text-[13px] text-muted-foreground mb-4">Complete more trades to unlock time-based insights</p>
                <button
                  onClick={handleLearnPatterns}
                  disabled={isLearning}
                  className="flex items-center gap-1.5 px-4 py-2 text-[13px] font-semibold rounded-lg bg-tm-brand text-white hover:bg-tm-brand/90 transition-colors mx-auto disabled:opacity-50"
                >
                  <Brain className={cn('h-3.5 w-3.5', isLearning && 'animate-pulse')} />
                  Start Learning
                </button>
              </div>
            </div>
          )}
        </TabsContent>

        {/* ── Symbol Analysis ────────────────────────────────────────────────── */}
        <TabsContent value="symbols" className="mt-4 space-y-4">
          {symbolAnalysis ? (
            <div className="grid md:grid-cols-2 gap-4">

              {/* Best Symbols */}
              <div className="tm-card">
                <div className="px-5 py-3 border-b border-slate-100 dark:border-neutral-700/60">
                  <div className="flex items-center gap-2 text-tm-profit">
                    <TrendingUp className="h-4 w-4" />
                    <span className="text-[13px] font-semibold">Your Best Symbols</span>
                  </div>
                  <p className="text-[12px] text-muted-foreground mt-0.5">Instruments where you excel</p>
                </div>
                <div className="p-5">
                  {symbolAnalysis.best_symbols.length > 0 ? (
                    <div className="space-y-3">
                      {symbolAnalysis.best_symbols.slice(0, 5).map((item, i) => (
                        <div key={i} className="flex items-center justify-between">
                          <div>
                            <p className="text-[13px] font-medium text-foreground">{item.symbol}</p>
                            <p className="text-[11px] text-muted-foreground">{item.trade_count} trades</p>
                          </div>
                          <div className="text-right">
                            <p className="text-[13px] font-semibold text-tm-profit">{item.win_rate.toFixed(0)}% win</p>
                            <p className="text-[11px] text-tm-profit font-mono">+₹{item.avg_pnl.toFixed(0)}/trade</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-[13px] text-muted-foreground text-center py-6">Not enough data yet</p>
                  )}
                </div>
              </div>

              {/* Worst Symbols */}
              <div className="tm-card">
                <div className="px-5 py-3 border-b border-slate-100 dark:border-neutral-700/60">
                  <div className="flex items-center gap-2 text-tm-loss">
                    <TrendingDown className="h-4 w-4" />
                    <span className="text-[13px] font-semibold">Symbols to Avoid</span>
                  </div>
                  <p className="text-[12px] text-muted-foreground mt-0.5">Instruments where you struggle</p>
                </div>
                <div className="p-5">
                  {symbolAnalysis.worst_symbols.length > 0 ? (
                    <div className="space-y-3">
                      {symbolAnalysis.worst_symbols.slice(0, 5).map((item, i) => (
                        <div key={i} className="flex items-center justify-between">
                          <div>
                            <p className="text-[13px] font-medium text-foreground">{item.symbol}</p>
                            <p className="text-[11px] text-muted-foreground">{item.trade_count} trades</p>
                          </div>
                          <div className="text-right">
                            <p className="text-[13px] font-semibold text-tm-loss">{item.win_rate.toFixed(0)}% win</p>
                            <p className="text-[11px] text-tm-loss font-mono">₹{item.avg_pnl.toFixed(0)}/trade</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-[13px] text-muted-foreground text-center py-6">Not enough data yet</p>
                  )}
                </div>
              </div>

              {/* Overtraded Symbols */}
              {symbolAnalysis.overtraded_symbols.length > 0 && (
                <div className="tm-card md:col-span-2">
                  <div className="px-5 py-3 border-b border-slate-100 dark:border-neutral-700/60">
                    <div className="flex items-center gap-2 text-tm-obs">
                      <BarChart3 className="h-4 w-4" />
                      <span className="text-[13px] font-semibold">Overtraded Symbols</span>
                    </div>
                    <p className="text-[12px] text-muted-foreground mt-0.5">Symbols you trade too frequently with poor results</p>
                  </div>
                  <div className="p-5">
                    <div className="flex flex-wrap gap-2">
                      {symbolAnalysis.overtraded_symbols.map((item, i) => (
                        <span key={i} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-tm-obs/10 border border-tm-obs/20 text-[12px]">
                          <span className="font-medium text-foreground">{item.symbol}</span>
                          <span className="text-tm-obs">{item.trade_count} trades · {(item.loss_rate * 100).toFixed(0)}% loss</span>
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {/* Symbol Recommendations */}
              <div className="tm-card md:col-span-2">
                <div className="px-5 py-3 border-b border-slate-100 dark:border-neutral-700/60">
                  <div className="flex items-center gap-2">
                    <Lightbulb className="h-4 w-4 text-tm-obs" />
                    <span className="text-[13px] font-semibold text-foreground">Symbol Recommendations</span>
                  </div>
                </div>
                <div className="p-5">
                  {symbolAnalysis.recommendations.length > 0 ? (
                    <ul className="grid md:grid-cols-2 gap-2">
                      {symbolAnalysis.recommendations.map((rec, i) => (
                        <li key={i} className="flex items-start gap-2 text-[13px] p-3 rounded-lg bg-tm-obs/[0.04] border border-tm-obs/10">
                          <Lightbulb className="h-3.5 w-3.5 text-tm-obs mt-0.5 shrink-0" />
                          <span className="text-foreground">{rec}</span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-[13px] text-muted-foreground text-center py-6">
                      Trade more to unlock symbol recommendations
                    </p>
                  )}
                </div>
              </div>

            </div>
          ) : (
            <div className="tm-card">
              <div className="py-12 text-center">
                <Target className="h-10 w-10 mx-auto text-muted-foreground/40 mb-3" />
                <p className="text-sm font-medium text-foreground mb-1">No symbol analysis available</p>
                <p className="text-[13px] text-muted-foreground">Trade more instruments to see personalized symbol insights</p>
              </div>
            </div>
          )}
        </TabsContent>

        {/* ── Intervention Timing ────────────────────────────────────────────── */}
        <TabsContent value="intervention" className="mt-4">
          {interventionTiming ? (
            <div className="tm-card">
              <div className="px-5 py-3 border-b border-slate-100 dark:border-neutral-700/60">
                <span className="text-[13px] font-semibold text-foreground">Intervention Effectiveness</span>
                <p className="text-[12px] text-muted-foreground mt-0.5">How well cooldowns and interventions work for you</p>
              </div>
              <div className="p-5 space-y-6">

                {/* 3 stat boxes */}
                <div className="grid md:grid-cols-3 gap-4">
                  <div className="text-center p-4 rounded-lg bg-muted/40">
                    <p className="text-[32px] font-black font-mono tabular-nums text-foreground leading-none">
                      {interventionTiming.optimal_cooldown_duration}m
                    </p>
                    <p className="text-[12px] text-muted-foreground mt-1">Optimal cooldown duration</p>
                    <p className="text-[11px] text-muted-foreground/70 mt-0.5">Based on your recovery patterns</p>
                  </div>

                  <div className="text-center p-4 rounded-lg bg-muted/40">
                    <p className="text-[32px] font-black font-mono tabular-nums text-tm-profit leading-none">
                      {(interventionTiming.escalation_effectiveness * 100).toFixed(0)}%
                    </p>
                    <p className="text-[12px] text-muted-foreground mt-1">Intervention effectiveness</p>
                    <div className="h-1.5 rounded-full bg-muted mt-2 overflow-hidden">
                      <div
                        className="h-full rounded-full bg-tm-profit transition-all"
                        style={{ width: `${interventionTiming.escalation_effectiveness * 100}%` }}
                      />
                    </div>
                  </div>

                  <div className="text-center p-4 rounded-lg bg-muted/40">
                    <p className="text-[32px] font-black font-mono tabular-nums text-tm-obs leading-none">
                      {(interventionTiming.skip_rate * 100).toFixed(0)}%
                    </p>
                    <p className="text-[12px] text-muted-foreground mt-1">Cooldown skip rate</p>
                    <p className="text-[11px] text-muted-foreground/70 mt-0.5">
                      {interventionTiming.skip_rate > 0.5 ? 'Consider harder limits' : 'Good discipline!'}
                    </p>
                  </div>
                </div>

                {/* Recommendations */}
                {interventionTiming.recommendations.length > 0 && (
                  <div>
                    <p className="text-[13px] font-semibold text-foreground mb-3">Personalized intervention strategy</p>
                    <div className="space-y-2">
                      {interventionTiming.recommendations.map((rec, i) => (
                        <div key={i} className="flex items-start gap-2.5 p-3 rounded-lg bg-tm-brand/[0.04] border border-tm-brand/10">
                          <Zap className="h-3.5 w-3.5 text-tm-brand mt-0.5 shrink-0" />
                          <span className="text-[13px] text-foreground">{rec}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

              </div>
            </div>
          ) : (
            <div className="tm-card">
              <div className="py-12 text-center">
                <Zap className="h-10 w-10 mx-auto text-muted-foreground/40 mb-3" />
                <p className="text-sm font-medium text-foreground mb-1">No intervention data</p>
                <p className="text-[13px] text-muted-foreground">Use cooldowns and interventions to see effectiveness metrics</p>
              </div>
            </div>
          )}
        </TabsContent>

      </Tabs>
    </div>
  );
}
