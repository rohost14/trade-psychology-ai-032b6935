import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import { BarChart3, Link2, Loader2 } from 'lucide-react';
import PerformanceSummaryCard from '@/components/analytics/PerformanceSummaryCard';
import BehavioralInsightsCard from '@/components/analytics/BehavioralInsightsCard';
import TimeAnalysisCard from '@/components/analytics/TimeAnalysisCard';
import AIInsightsCard from '@/components/analytics/AIInsightsCard';
import ProfitCurveChart from '@/components/analytics/ProfitCurveChart';
import { Button } from '@/components/ui/button';
import { useBroker } from '@/contexts/BrokerContext';
import { api } from '@/lib/api';

interface PerformanceData {
  totalPnl: number;
  winRate: number;
  totalTrades: number;
  avgWin: number;
  avgLoss: number;
  profitFactor: number;
  bestDay: { date: string; pnl: number };
  worstDay: { date: string; pnl: number };
}

interface BehavioralPattern {
  id: string;
  name: string;
  type: 'danger' | 'strength';
  count: number;
  impact: string;
  description: string;
  trend: 'up' | 'down' | 'stable';
}

interface TimeData {
  hour: string;
  pnl: number;
  trades: number;
  wins?: number;
  losses?: number;
}

interface AIInsight {
  id: string;
  title: string;
  description: string;
  action: string;
  priority: 'high' | 'medium' | 'low';
}

export default function Analytics() {
  const { isConnected, isLoading: brokerLoading, account } = useBroker();
  const [isLoading, setIsLoading] = useState(true);
  const [performanceData, setPerformanceData] = useState<PerformanceData | null>(null);
  const [behavioralPatterns, setBehavioralPatterns] = useState<BehavioralPattern[]>([]);
  const [timeData, setTimeData] = useState<TimeData[]>([]);
  const [aiInsights, setAiInsights] = useState<AIInsight[]>([]);
  const [hourlyPnlData, setHourlyPnlData] = useState<TimeData[]>([]);

  useEffect(() => {
    if (!isConnected || !account) {
      setIsLoading(false);
      return;
    }

    const fetchAnalytics = async () => {
      setIsLoading(true);
      try {
        // Fetch trades for analysis
        const tradesRes = await api.get('/api/trades/', {
          params: { broker_account_id: account.id, limit: 200 }
        });
        const trades = tradesRes.data.trades || [];

        if (trades.length === 0) {
          setIsLoading(false);
          return;
        }

        // Calculate performance data from trades
        const winners = trades.filter((t: any) => (t.pnl || 0) > 0);
        const losers = trades.filter((t: any) => (t.pnl || 0) < 0);
        const totalPnl = trades.reduce((sum: number, t: any) => sum + (t.pnl || 0), 0);
        const avgWin = winners.length > 0
          ? winners.reduce((sum: number, t: any) => sum + (t.pnl || 0), 0) / winners.length
          : 0;
        const avgLoss = losers.length > 0
          ? losers.reduce((sum: number, t: any) => sum + (t.pnl || 0), 0) / losers.length
          : 0;

        setPerformanceData({
          totalPnl,
          winRate: trades.length > 0 ? (winners.length / trades.length) * 100 : 0,
          totalTrades: trades.length,
          avgWin,
          avgLoss,
          profitFactor: avgLoss !== 0 ? Math.abs(avgWin / avgLoss) : 0,
          bestDay: { date: '-', pnl: 0 },
          worstDay: { date: '-', pnl: 0 },
        });

        // Try to fetch behavioral analysis from backend
        try {
          const behavioralRes = await api.get('/api/behavioral/patterns', {
            params: { broker_account_id: account.id }
          });
          const patterns = behavioralRes.data.patterns || [];
          setBehavioralPatterns(patterns.map((p: any) => ({
            id: p.id || String(Math.random()),
            name: p.pattern_type || p.name,
            type: p.severity === 'danger' ? 'danger' : 'strength',
            count: p.count || 1,
            impact: p.impact || '₹0',
            description: p.description || '',
            trend: 'stable' as const,
          })));
        } catch (e) {
          console.log('Behavioral patterns not available');
        }

        // Calculate hourly performance
        const hourlyMap = new Map<string, { pnl: number; trades: number; wins: number; losses: number }>();
        trades.forEach((t: any) => {
          const hour = new Date(t.order_timestamp || t.created_at).getHours();
          const hourKey = `${hour}:00`;
          const existing = hourlyMap.get(hourKey) || { pnl: 0, trades: 0, wins: 0, losses: 0 };
          existing.pnl += t.pnl || 0;
          existing.trades += 1;
          if ((t.pnl || 0) > 0) existing.wins += 1;
          else if ((t.pnl || 0) < 0) existing.losses += 1;
          hourlyMap.set(hourKey, existing);
        });

        const hourlyData = Array.from(hourlyMap.entries())
          .map(([hour, data]) => ({ hour, ...data }))
          .sort((a, b) => parseInt(a.hour) - parseInt(b.hour));

        setTimeData(hourlyData);
        setHourlyPnlData(hourlyData);

      } catch (error) {
        console.error('Failed to fetch analytics:', error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchAnalytics();
  }, [isConnected, account]);

  // Loading state
  if (brokerLoading || isLoading) {
    return (
      <div className="max-w-5xl mx-auto pb-12 flex items-center justify-center min-h-[60vh]">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  // Not connected state
  if (!isConnected) {
    return (
      <div className="max-w-5xl mx-auto pb-12">
        <motion.div
          className="flex flex-col items-center justify-center min-h-[60vh]"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <div className="p-4 rounded-full bg-primary/10 mb-6">
            <Link2 className="h-12 w-12 text-primary" />
          </div>
          <h2 className="text-2xl font-semibold text-foreground mb-2">Connect Your Broker</h2>
          <p className="text-muted-foreground text-center max-w-md mb-6">
            Connect your Zerodha account to see your trading analytics and behavioral insights.
          </p>
          <Link to="/settings">
            <Button size="lg" className="gap-2">
              <Link2 className="h-5 w-5" />
              Connect Zerodha
            </Button>
          </Link>
        </motion.div>
      </div>
    );
  }

  // No data state
  if (!performanceData || performanceData.totalTrades === 0) {
    return (
      <div className="max-w-5xl mx-auto pb-12">
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-6"
        >
          <h1 className="text-2xl font-bold text-foreground">Analytics</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Weekly performance insights and behavioral patterns
          </p>
        </motion.div>

        <motion.div
          className="flex flex-col items-center justify-center min-h-[50vh] bg-card rounded-lg border border-border"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <div className="p-4 rounded-full bg-muted mb-6">
            <BarChart3 className="h-12 w-12 text-muted-foreground" />
          </div>
          <h2 className="text-xl font-semibold text-foreground mb-2">No Trading Data Yet</h2>
          <p className="text-muted-foreground text-center max-w-md">
            Start trading to see your performance analytics and behavioral patterns here.
            Your data will appear after you make some trades.
          </p>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto pb-12">
      {/* Page Header */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-6"
      >
        <h1 className="text-2xl font-bold text-foreground">Analytics</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Weekly performance insights and behavioral patterns
        </p>
      </motion.div>

      {/* Content */}
      <div className="space-y-6">
        {/* Performance Summary */}
        <PerformanceSummaryCard data={performanceData} />

        {/* Behavioral Patterns - Dangers & Strengths */}
        {behavioralPatterns.length > 0 && (
          <BehavioralInsightsCard patterns={behavioralPatterns} />
        )}

        {/* Time Analysis */}
        {timeData.length > 0 && (
          <TimeAnalysisCard hourlyData={timeData} />
        )}

        {/* P&L Curve */}
        {hourlyPnlData.length > 0 && (
          <ProfitCurveChart hourlyData={hourlyPnlData} />
        )}

        {/* AI Insights */}
        {aiInsights.length > 0 && (
          <AIInsightsCard insights={aiInsights} />
        )}
      </div>
    </div>
  );
}
