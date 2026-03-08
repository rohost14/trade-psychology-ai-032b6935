import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  AlertTriangle,
  Clock,
  TrendingDown,
  Zap,
  X,
  ChevronRight
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { api } from '@/lib/api';

interface PredictiveAlert {
  id: string;
  type: 'danger_hour' | 'danger_day' | 'problem_symbol' | 'revenge_window';
  severity: 'warning' | 'danger';
  title: string;
  message: string;
  stat?: string;
}

interface PredictiveWarningsCardProps {
  brokerAccountId: string;
}

const ALERT_CONFIG = {
  danger_hour: {
    icon: Clock,
    color: 'text-orange-500',
    bgColor: 'bg-orange-500/10',
    borderColor: 'border-orange-500/30',
  },
  danger_day: {
    icon: AlertTriangle,
    color: 'text-red-500',
    bgColor: 'bg-red-500/10',
    borderColor: 'border-red-500/30',
  },
  problem_symbol: {
    icon: TrendingDown,
    color: 'text-red-500',
    bgColor: 'bg-red-500/10',
    borderColor: 'border-red-500/30',
  },
  revenge_window: {
    icon: Zap,
    color: 'text-amber-500',
    bgColor: 'bg-amber-500/10',
    borderColor: 'border-amber-500/30',
  },
};

export default function PredictiveWarningsCard({ brokerAccountId }: PredictiveWarningsCardProps) {
  const [alerts, setAlerts] = useState<PredictiveAlert[]>([]);
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchPredictiveData = async () => {
      if (!brokerAccountId) return;

      try {
        setIsLoading(true);
        const [insightsRes, checkRes] = await Promise.all([
          api.get('/api/personalization/insights'),
          api.post('/api/personalization/predictive-check', {})
        ]);

        const insights = insightsRes.data;
        const check = checkRes.data;
        const newAlerts: PredictiveAlert[] = [];

        // Check if current hour is a danger hour
        const currentHour = new Date().getHours();
        const currentHourStr = `${currentHour}:00`;
        if (insights.danger_hours?.includes(currentHourStr)) {
          newAlerts.push({
            id: 'current-danger-hour',
            type: 'danger_hour',
            severity: 'danger',
            title: 'High-Risk Trading Hour',
            message: `You historically lose money trading at ${currentHourStr}. Consider waiting.`,
            stat: `${insights.danger_hours.length} danger hours identified`,
          });
        }

        // Check if today is a danger day
        const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
        const today = days[new Date().getDay()];
        if (insights.danger_days?.includes(today)) {
          newAlerts.push({
            id: 'current-danger-day',
            type: 'danger_day',
            severity: 'danger',
            title: `${today} is a Danger Day`,
            message: `Your historical win rate on ${today}s is below 35%. Trade with extra caution.`,
          });
        }

        // Check revenge window warning
        if (insights.revenge_window_minutes && check.has_warning) {
          newAlerts.push({
            id: 'revenge-window',
            type: 'revenge_window',
            severity: 'warning',
            title: 'Inside Revenge Window',
            message: `You typically revenge trade within ${insights.revenge_window_minutes} minutes after a loss. Take a break first.`,
            stat: `${insights.revenge_window_minutes} min window`,
          });
        }

        // Add predictive alert from check endpoint
        if (check.alert) {
          newAlerts.push({
            id: 'predictive-' + Date.now(),
            type: check.alert.type || 'danger_hour',
            severity: check.alert.severity || 'warning',
            title: check.alert.title,
            message: check.alert.message,
          });
        }

        // Show best hours as positive reinforcement if no danger
        if (newAlerts.length === 0 && insights.best_hours?.includes(currentHourStr)) {
          newAlerts.push({
            id: 'best-hour',
            type: 'danger_hour', // reuse styling
            severity: 'warning',
            title: 'Good Trading Hour',
            message: `${currentHourStr} is one of your best performing hours. Good time to trade!`,
          });
        }

        setAlerts(newAlerts);
      } catch (error) {
        console.error('Failed to fetch predictive data:', error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchPredictiveData();
    // Refresh every 5 minutes
    const interval = setInterval(fetchPredictiveData, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, [brokerAccountId]);

  const handleDismiss = (alertId: string) => {
    setDismissed(prev => new Set([...prev, alertId]));
  };

  const visibleAlerts = alerts.filter(a => !dismissed.has(a.id));

  if (isLoading || visibleAlerts.length === 0) {
    return null;
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
        <Zap className="h-4 w-4" />
        <span>AI Predictive Warnings</span>
      </div>

      <AnimatePresence mode="popLayout">
        {visibleAlerts.map((alert) => {
          const config = ALERT_CONFIG[alert.type];
          const Icon = config.icon;

          return (
            <motion.div
              key={alert.id}
              initial={{ opacity: 0, y: -10, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95, y: -10 }}
              transition={{ type: 'spring', stiffness: 200, damping: 20 }}
              className={cn(
                'relative p-4 rounded-lg border',
                config.bgColor,
                config.borderColor
              )}
            >
              <button
                onClick={() => handleDismiss(alert.id)}
                className="absolute top-2 right-2 p-1 rounded-full hover:bg-background/50 transition-colors"
              >
                <X className="h-4 w-4 text-muted-foreground" />
              </button>

              <div className="flex gap-3">
                <div className={cn('p-2 rounded-lg', config.bgColor)}>
                  <Icon className={cn('h-5 w-5', config.color)} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-2">
                    <h4 className={cn('font-semibold text-sm', config.color)}>
                      {alert.title}
                    </h4>
                    {alert.stat && (
                      <span className="text-xs text-muted-foreground whitespace-nowrap">
                        {alert.stat}
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-muted-foreground mt-1">
                    {alert.message}
                  </p>
                </div>
              </div>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
