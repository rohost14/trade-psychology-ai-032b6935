import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  TrendingUp,
  TrendingDown,
  Minus,
  Target,
  Award,
  BarChart3,
  AlertTriangle,
  Flame,
  ChevronRight
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatCurrency, formatPercentage } from '@/lib/formatters';
import { api } from '@/lib/api';
import { Link } from 'react-router-dom';

interface WeekStats {
  total_pnl: number;
  trade_count: number;
  win_rate: number;
  winners: number;
  losers: number;
}

interface Comparison {
  change: number;
  improved: boolean;
  percent: number;
}

interface ProgressData {
  this_week: WeekStats;
  last_week: WeekStats;
  comparison: {
    pnl: Comparison;
    win_rate: Comparison;
    trade_count: Comparison;
    danger_alerts: Comparison;
  };
  alerts: {
    this_week: number;
    last_week: number;
  };
  streaks: {
    days_without_revenge: number;
    current_streak: number;
    best_streak: number;
  };
}

interface ProgressTrackingCardProps {
  brokerAccountId: string;
}

export default function ProgressTrackingCard({ brokerAccountId }: ProgressTrackingCardProps) {
  const [data, setData] = useState<ProgressData | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchProgress = async () => {
      if (!brokerAccountId) return;

      try {
        setIsLoading(true);
        const response = await api.get('/api/analytics/progress');
        setData(response.data);
      } catch (error) {
        console.error('Failed to fetch progress:', error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchProgress();
  }, [brokerAccountId]);

  if (isLoading) {
    return (
      <div className="bg-card rounded-lg border border-border p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-muted rounded w-1/3" />
          <div className="h-24 bg-muted rounded" />
        </div>
      </div>
    );
  }

  if (!data) {
    return null;
  }

  const TrendIcon = ({ improved }: { improved: boolean }) => {
    if (improved) return <TrendingUp className="h-4 w-4 text-green-500" />;
    return <TrendingDown className="h-4 w-4 text-red-500" />;
  };

  const metrics = [
    {
      label: 'P&L',
      thisWeek: formatCurrency(data.this_week.total_pnl),
      comparison: data.comparison.pnl,
      icon: BarChart3,
    },
    {
      label: 'Win Rate',
      thisWeek: `${data.this_week.win_rate.toFixed(1)}%`,
      comparison: data.comparison.win_rate,
      icon: Target,
    },
    {
      label: 'Trades',
      thisWeek: data.this_week.trade_count.toString(),
      comparison: data.comparison.trade_count,
      icon: BarChart3,
      lessIsBetter: true,
    },
    {
      label: 'Danger Alerts',
      thisWeek: data.alerts.this_week.toString(),
      comparison: data.comparison.danger_alerts,
      icon: AlertTriangle,
      lessIsBetter: true,
    },
  ];

  return (
    <div className="bg-card rounded-lg border border-border">
      {/* Header */}
      <div className="px-6 py-5 border-b border-border">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-lg bg-primary/10">
              <TrendingUp className="h-5 w-5 text-primary" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-foreground">Progress</h3>
              <p className="text-sm text-muted-foreground">This week vs last week</p>
            </div>
          </div>
          <Link
            to="/analytics"
            className="text-sm text-primary hover:underline flex items-center gap-1"
          >
            View Details
            <ChevronRight className="h-4 w-4" />
          </Link>
        </div>
      </div>

      {/* Streak Banner */}
      {data.streaks.current_streak > 0 && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="px-6 py-3 bg-gradient-to-r from-amber-500/10 to-orange-500/10 border-b border-amber-500/20"
        >
          <div className="flex items-center gap-3">
            <Flame className="h-5 w-5 text-amber-500" />
            <div>
              <span className="font-semibold text-amber-600 dark:text-amber-400">
                {data.streaks.current_streak} day streak!
              </span>
              <span className="text-sm text-muted-foreground ml-2">
                No revenge trading
              </span>
            </div>
            {data.streaks.current_streak >= data.streaks.best_streak && (
              <Award className="h-5 w-5 text-amber-500 ml-auto" />
            )}
          </div>
        </motion.div>
      )}

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 divide-x divide-y divide-border">
        {metrics.map((metric, i) => {
          const Icon = metric.icon;
          const improved = metric.lessIsBetter
            ? !metric.comparison.improved
            : metric.comparison.improved;
          const changeColor = improved ? 'text-green-500' : 'text-red-500';

          return (
            <div key={metric.label} className="px-4 py-4">
              <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
                <Icon className="h-3.5 w-3.5" />
                {metric.label}
              </div>
              <div className="flex items-end justify-between">
                <span className="text-xl font-semibold tabular-nums">
                  {metric.thisWeek}
                </span>
                {metric.comparison.percent !== 0 && (
                  <div className={cn('flex items-center gap-1 text-sm', changeColor)}>
                    {improved ? <TrendingUp className="h-3.5 w-3.5" /> : <TrendingDown className="h-3.5 w-3.5" />}
                    <span className="tabular-nums">
                      {Math.abs(metric.comparison.percent).toFixed(0)}%
                    </span>
                  </div>
                )}
              </div>
              <div className="text-xs text-muted-foreground mt-1">
                vs {metric.label === 'P&L'
                  ? formatCurrency(data.last_week.total_pnl)
                  : metric.label === 'Win Rate'
                    ? `${data.last_week.win_rate.toFixed(1)}%`
                    : metric.label === 'Trades'
                      ? data.last_week.trade_count
                      : data.alerts.last_week
                } last week
              </div>
            </div>
          );
        })}
      </div>

      {/* Insight Footer */}
      <div className="px-6 py-4 bg-muted/30 border-t border-border">
        <p className="text-sm text-muted-foreground">
          {data.comparison.win_rate.improved && data.comparison.danger_alerts.improved
            ? "Great progress! Your discipline is improving."
            : data.comparison.win_rate.improved
              ? "Win rate improving - keep focusing on quality trades."
              : data.comparison.danger_alerts.improved
                ? "Fewer danger patterns - your discipline is getting better."
                : "Focus on following your trading plan this week."}
        </p>
      </div>
    </div>
  );
}
