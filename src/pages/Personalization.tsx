import { useState, useEffect, useCallback } from 'react';
import { useBroker } from '@/contexts/BrokerContext';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import {
  Brain,
  Clock,
  TrendingUp,
  TrendingDown,
  BarChart3,
  Target,
  Lightbulb,
  RefreshCw,
  Sparkles,
  Calendar,
  Zap
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

      // Fetch all personalization data in parallel
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
      if (timeRes.status === 'fulfilled') {
        setTimeAnalysis(timeRes.value.data);
      }
      if (symbolRes.status === 'fulfilled') {
        setSymbolAnalysis(symbolRes.value.data);
      }
      if (interventionRes.status === 'fulfilled') {
        setInterventionTiming(interventionRes.value.data);
      }
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

  useEffect(() => {
    fetchData();
  }, [fetchData]);

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

  if (!account) {
    return (
      <div className="container mx-auto p-6">
        <Alert>
          <Brain className="h-4 w-4" />
          <AlertTitle>No Account Connected</AlertTitle>
          <AlertDescription>
            Please connect your broker account to access personalized insights.
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="container mx-auto p-6 flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <Brain className="h-12 w-12 animate-pulse mx-auto text-primary mb-4" />
          <p className="text-muted-foreground">Analyzing your trading patterns...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-6 space-y-6">

      {/* P-06: What the system has learned — shown ABOVE the settings form */}
      {behavioralStatus === 'active' && behavioralInsights.length > 0 && (
        <Card className="border-primary/30 bg-primary/5">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base">
              <Brain className="h-5 w-5 text-primary" />
              What we've learned about you
            </CardTitle>
            <CardDescription>
              Based on {sessionsAnalyzed} trading sessions — your personal thresholds, not defaults.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {behavioralInsights.map((insight: any, i: number) => (
              <div key={i} className="flex items-start gap-3 p-3 rounded-lg bg-background border border-border">
                <Sparkles className="h-4 w-4 text-primary mt-0.5 flex-shrink-0" />
                <div>
                  <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-0.5">
                    {insight.category}
                  </p>
                  <p className="text-sm text-foreground">{insight.insight}</p>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {behavioralStatus === 'insufficient_data' && (
        <Card className="border-dashed">
          <CardContent className="pt-4 pb-4 text-center">
            <Brain className="h-8 w-8 text-muted-foreground/50 mx-auto mb-2" />
            <p className="text-sm font-medium text-foreground">Behavioral learning in progress</p>
            <p className="text-xs text-muted-foreground mt-1">
              Trade for at least 5 sessions and we'll show you what we've learned about your patterns.
            </p>
          </CardContent>
        </Card>
      )}

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-2">
            <Sparkles className="h-8 w-8 text-primary" />
            Personalized Insights
          </h1>
          <p className="text-muted-foreground">
            AI-powered analysis of your unique trading patterns
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={fetchData} disabled={isLoading}>
            <RefreshCw className={`h-4 w-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          <Button onClick={handleLearnPatterns} disabled={isLearning}>
            <Brain className={`h-4 w-4 mr-2 ${isLearning ? 'animate-pulse' : ''}`} />
            {isLearning ? 'Learning...' : 'Learn Patterns'}
          </Button>
        </div>
      </div>

      {/* Last Learned Banner */}
      {lastLearned && (
        <Alert className="bg-primary/5 border-primary/20">
          <Zap className="h-4 w-4 text-primary" />
          <AlertTitle>AI Model Updated</AlertTitle>
          <AlertDescription>
            Last pattern learning: {new Date(lastLearned).toLocaleString()}
          </AlertDescription>
        </Alert>
      )}

      {/* Personalized Insights Grid */}
      {insights.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {insights.map((insight, i) => (
            <Card key={i} className={`
              ${insight.type === 'strength' ? 'border-green-200 bg-green-50/50 dark:bg-green-950/20' : ''}
              ${insight.type === 'weakness' ? 'border-red-200 bg-red-50/50 dark:bg-red-950/20' : ''}
              ${insight.type === 'pattern' ? 'border-blue-200 bg-blue-50/50 dark:bg-blue-950/20' : ''}
              ${insight.type === 'recommendation' ? 'border-yellow-200 bg-yellow-50/50 dark:bg-yellow-950/20' : ''}
            `}>
              <CardContent className="pt-4">
                <div className="flex items-start gap-3">
                  <div className={`p-2 rounded-lg
                    ${insight.type === 'strength' ? 'bg-green-100 text-green-600' : ''}
                    ${insight.type === 'weakness' ? 'bg-red-100 text-red-600' : ''}
                    ${insight.type === 'pattern' ? 'bg-blue-100 text-blue-600' : ''}
                    ${insight.type === 'recommendation' ? 'bg-yellow-100 text-yellow-600' : ''}
                  `}>
                    {insight.type === 'strength' && <TrendingUp className="h-5 w-5" />}
                    {insight.type === 'weakness' && <TrendingDown className="h-5 w-5" />}
                    {insight.type === 'pattern' && <BarChart3 className="h-5 w-5" />}
                    {insight.type === 'recommendation' && <Lightbulb className="h-5 w-5" />}
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center justify-between mb-1">
                      <h4 className="font-semibold">{insight.title}</h4>
                      <Badge variant="outline" className="text-xs">
                        {Math.round(insight.confidence * 100)}% confident
                      </Badge>
                    </div>
                    <p className="text-sm text-muted-foreground">{insight.description}</p>
                    {insight.action && (
                      <p className="text-sm font-medium mt-2 text-primary">{insight.action}</p>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Analysis Tabs */}
      <Tabs defaultValue="time">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="time">
            <Clock className="h-4 w-4 mr-2" />
            Time Analysis
          </TabsTrigger>
          <TabsTrigger value="symbols">
            <Target className="h-4 w-4 mr-2" />
            Symbol Analysis
          </TabsTrigger>
          <TabsTrigger value="intervention">
            <Zap className="h-4 w-4 mr-2" />
            Intervention Timing
          </TabsTrigger>
        </TabsList>

        {/* Time Analysis Tab */}
        <TabsContent value="time" className="space-y-4">
          {timeAnalysis ? (
            <div className="grid md:grid-cols-2 gap-4">
              {/* Best Hours */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-green-600">
                    <TrendingUp className="h-5 w-5" />
                    Your Best Trading Hours
                  </CardTitle>
                  <CardDescription>
                    Times when you perform best
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {timeAnalysis.best_hours.length > 0 ? (
                    <div className="space-y-3">
                      {timeAnalysis.best_hours.slice(0, 5).map((item, i) => (
                        <div key={i} className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <Badge variant="outline" className="bg-green-50">
                              {formatHour(item.hour)}
                            </Badge>
                            <span className="text-sm text-muted-foreground">
                              {item.trade_count} trades
                            </span>
                          </div>
                          <div className="text-right">
                            <div className="font-semibold text-green-600">
                              {item.win_rate.toFixed(0)}% win
                            </div>
                            <div className="text-xs text-muted-foreground">
                              Avg: ₹{item.avg_pnl.toFixed(0)}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-muted-foreground text-center py-4">
                      Not enough data yet
                    </p>
                  )}
                </CardContent>
              </Card>

              {/* Worst Hours */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-red-600">
                    <TrendingDown className="h-5 w-5" />
                    Hours to Avoid
                  </CardTitle>
                  <CardDescription>
                    Times when you typically underperform
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {timeAnalysis.worst_hours.length > 0 ? (
                    <div className="space-y-3">
                      {timeAnalysis.worst_hours.slice(0, 5).map((item, i) => (
                        <div key={i} className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <Badge variant="outline" className="bg-red-50">
                              {formatHour(item.hour)}
                            </Badge>
                            <span className="text-sm text-muted-foreground">
                              {item.trade_count} trades
                            </span>
                          </div>
                          <div className="text-right">
                            <div className="font-semibold text-red-600">
                              {item.win_rate.toFixed(0)}% win
                            </div>
                            <div className="text-xs text-muted-foreground">
                              Avg: ₹{item.avg_pnl.toFixed(0)}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-muted-foreground text-center py-4">
                      Not enough data yet
                    </p>
                  )}
                </CardContent>
              </Card>

              {/* Best Days */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Calendar className="h-5 w-5 text-green-600" />
                    Best Days of Week
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {timeAnalysis.best_days.length > 0 ? (
                    <div className="space-y-2">
                      {timeAnalysis.best_days.map((item, i) => (
                        <div key={i} className="flex items-center justify-between p-2 rounded-lg bg-green-50/50">
                          <span className="font-medium">{item.day}</span>
                          <div className="flex items-center gap-4">
                            <span className="text-green-600">{item.win_rate.toFixed(0)}% win</span>
                            <span className="text-muted-foreground text-sm">
                              ₹{item.avg_pnl.toFixed(0)} avg
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-muted-foreground text-center py-4">
                      Not enough data yet
                    </p>
                  )}
                </CardContent>
              </Card>

              {/* Recommendations */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Lightbulb className="h-5 w-5 text-yellow-600" />
                    Time-Based Recommendations
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {timeAnalysis.recommendations.length > 0 ? (
                    <ul className="space-y-2">
                      {timeAnalysis.recommendations.map((rec, i) => (
                        <li key={i} className="flex items-start gap-2 text-sm">
                          <span className="text-yellow-600">•</span>
                          {rec}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-muted-foreground text-center py-4">
                      Trade more to unlock personalized recommendations
                    </p>
                  )}
                </CardContent>
              </Card>
            </div>
          ) : (
            <Card>
              <CardContent className="py-12 text-center">
                <Clock className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                <h3 className="font-semibold mb-2">No Time Analysis Available</h3>
                <p className="text-muted-foreground mb-4">
                  Complete more trades to unlock time-based insights
                </p>
                <Button onClick={handleLearnPatterns} disabled={isLearning}>
                  <Brain className="h-4 w-4 mr-2" />
                  Start Learning
                </Button>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Symbol Analysis Tab */}
        <TabsContent value="symbols" className="space-y-4">
          {symbolAnalysis ? (
            <div className="grid md:grid-cols-2 gap-4">
              {/* Best Symbols */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-green-600">
                    <TrendingUp className="h-5 w-5" />
                    Your Best Symbols
                  </CardTitle>
                  <CardDescription>
                    Instruments where you excel
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {symbolAnalysis.best_symbols.length > 0 ? (
                    <div className="space-y-3">
                      {symbolAnalysis.best_symbols.slice(0, 5).map((item, i) => (
                        <div key={i} className="flex items-center justify-between">
                          <div>
                            <div className="font-medium">{item.symbol}</div>
                            <div className="text-xs text-muted-foreground">
                              {item.trade_count} trades
                            </div>
                          </div>
                          <div className="text-right">
                            <div className="font-semibold text-green-600">
                              {item.win_rate.toFixed(0)}% win
                            </div>
                            <div className="text-xs text-green-600">
                              +₹{item.avg_pnl.toFixed(0)}/trade
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-muted-foreground text-center py-4">
                      Not enough data yet
                    </p>
                  )}
                </CardContent>
              </Card>

              {/* Worst Symbols */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-red-600">
                    <TrendingDown className="h-5 w-5" />
                    Symbols to Avoid
                  </CardTitle>
                  <CardDescription>
                    Instruments where you struggle
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {symbolAnalysis.worst_symbols.length > 0 ? (
                    <div className="space-y-3">
                      {symbolAnalysis.worst_symbols.slice(0, 5).map((item, i) => (
                        <div key={i} className="flex items-center justify-between">
                          <div>
                            <div className="font-medium">{item.symbol}</div>
                            <div className="text-xs text-muted-foreground">
                              {item.trade_count} trades
                            </div>
                          </div>
                          <div className="text-right">
                            <div className="font-semibold text-red-600">
                              {item.win_rate.toFixed(0)}% win
                            </div>
                            <div className="text-xs text-red-600">
                              ₹{item.avg_pnl.toFixed(0)}/trade
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-muted-foreground text-center py-4">
                      Not enough data yet
                    </p>
                  )}
                </CardContent>
              </Card>

              {/* Overtraded Symbols */}
              {symbolAnalysis.overtraded_symbols.length > 0 && (
                <Card className="md:col-span-2">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-orange-600">
                      <BarChart3 className="h-5 w-5" />
                      Overtraded Symbols
                    </CardTitle>
                    <CardDescription>
                      Symbols you trade too frequently with poor results
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="flex flex-wrap gap-2">
                      {symbolAnalysis.overtraded_symbols.map((item, i) => (
                        <Badge key={i} variant="outline" className="bg-orange-50">
                          {item.symbol}
                          <span className="ml-2 text-orange-600">
                            {item.trade_count} trades, {(item.loss_rate * 100).toFixed(0)}% loss
                          </span>
                        </Badge>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Symbol Recommendations */}
              <Card className="md:col-span-2">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Lightbulb className="h-5 w-5 text-yellow-600" />
                    Symbol Recommendations
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {symbolAnalysis.recommendations.length > 0 ? (
                    <ul className="grid md:grid-cols-2 gap-2">
                      {symbolAnalysis.recommendations.map((rec, i) => (
                        <li key={i} className="flex items-start gap-2 text-sm p-2 bg-yellow-50/50 rounded-lg">
                          <Lightbulb className="h-4 w-4 text-yellow-600 mt-0.5" />
                          {rec}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-muted-foreground text-center py-4">
                      Trade more to unlock symbol recommendations
                    </p>
                  )}
                </CardContent>
              </Card>
            </div>
          ) : (
            <Card>
              <CardContent className="py-12 text-center">
                <Target className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                <h3 className="font-semibold mb-2">No Symbol Analysis Available</h3>
                <p className="text-muted-foreground mb-4">
                  Trade more instruments to see personalized symbol insights
                </p>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Intervention Timing Tab */}
        <TabsContent value="intervention">
          {interventionTiming ? (
            <Card>
              <CardHeader>
                <CardTitle>Intervention Effectiveness</CardTitle>
                <CardDescription>
                  How well cooldowns and interventions work for you
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="grid md:grid-cols-3 gap-4">
                  <div className="text-center p-4 bg-muted rounded-lg">
                    <div className="text-3xl font-bold">
                      {interventionTiming.optimal_cooldown_duration}m
                    </div>
                    <div className="text-sm text-muted-foreground">
                      Optimal Cooldown Duration
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">
                      Based on your recovery patterns
                    </p>
                  </div>

                  <div className="text-center p-4 bg-muted rounded-lg">
                    <div className="text-3xl font-bold text-green-600">
                      {(interventionTiming.escalation_effectiveness * 100).toFixed(0)}%
                    </div>
                    <div className="text-sm text-muted-foreground">
                      Intervention Effectiveness
                    </div>
                    <Progress
                      value={interventionTiming.escalation_effectiveness * 100}
                      className="mt-2"
                    />
                  </div>

                  <div className="text-center p-4 bg-muted rounded-lg">
                    <div className="text-3xl font-bold text-orange-600">
                      {(interventionTiming.skip_rate * 100).toFixed(0)}%
                    </div>
                    <div className="text-sm text-muted-foreground">
                      Cooldown Skip Rate
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">
                      {interventionTiming.skip_rate > 0.5 ? 'Consider harder limits' : 'Good discipline!'}
                    </p>
                  </div>
                </div>

                {interventionTiming.recommendations.length > 0 && (
                  <div>
                    <h4 className="font-semibold mb-3">Personalized Intervention Strategy</h4>
                    <div className="space-y-2">
                      {interventionTiming.recommendations.map((rec, i) => (
                        <div key={i} className="flex items-start gap-2 p-3 bg-primary/5 rounded-lg">
                          <Zap className="h-4 w-4 text-primary mt-0.5" />
                          <span className="text-sm">{rec}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="py-12 text-center">
                <Zap className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                <h3 className="font-semibold mb-2">No Intervention Data</h3>
                <p className="text-muted-foreground">
                  Use cooldowns and interventions to see effectiveness metrics
                </p>
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
