// My Patterns — Merged Goals + Risk Monitoring Page
// Shows: live danger status, emotional tax, streak, alert history
// Commitments feature removed — no user-dependent friction

import { useState, useEffect, useCallback, useMemo } from 'react';
import { Link } from 'react-router-dom';
import {
  Brain, Link2, Loader2, AlertTriangle, Shield,
  Clock, RefreshCw, Phone
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import { useBroker } from '@/contexts/BrokerContext';
import { useAlerts } from '@/contexts/AlertContext';
import { useWebSocket } from '@/contexts/WebSocketContext';
import { EmotionalTaxCard } from '@/components/goals/EmotionalTaxCard';
import { StreakTrackerCard } from '@/components/goals/StreakTrackerCard';
import PatternCalendar from '@/components/patterns/PatternCalendar';
import { calculateEmotionalTax, getTopRecommendations } from '@/lib/emotionalTaxCalculator';
import type { DangerZoneStatus, CooldownRecord } from '@/types/api';
import type { StreakData, DailyAdherence, StreakMilestone } from '@/types/patterns';

// ---------------------------------------------------------------------------
// Danger level display config
// ---------------------------------------------------------------------------
const LEVEL_CONFIG: Record<string, {
  border: string;
  bg: string;
  badgeClass: string;
  iconColor: string;
  label: string;
  Icon: typeof Shield;
}> = {
  safe:     { border: 'border-green-500/30',  bg: '',                                      badgeClass: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',  iconColor: 'text-green-500',  label: 'Safe',     Icon: Shield },
  caution:  { border: 'border-yellow-500/40', bg: 'bg-yellow-50/30 dark:bg-yellow-950/20', badgeClass: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400', iconColor: 'text-yellow-500', label: 'Caution',  Icon: AlertTriangle },
  warning:  { border: 'border-orange-500/50', bg: 'bg-orange-50/30 dark:bg-orange-950/20', badgeClass: 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400', iconColor: 'text-orange-500', label: 'Warning',  Icon: AlertTriangle },
  danger:   { border: 'border-red-500/60',    bg: 'bg-red-50/40 dark:bg-red-950/30',       badgeClass: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',           iconColor: 'text-red-500',    label: 'Danger',   Icon: AlertTriangle },
  critical: { border: 'border-red-700',       bg: 'bg-red-100/50 dark:bg-red-950/50',      badgeClass: 'bg-red-200 text-red-900 dark:bg-red-800 dark:text-red-200',              iconColor: 'text-red-700',    label: 'CRITICAL', Icon: AlertTriangle },
};

// ---------------------------------------------------------------------------
// Status Banner
// ---------------------------------------------------------------------------
function DangerStatusBanner({
  status,
  onAlertGuardian,
  isAlerting,
}: {
  status: DangerZoneStatus;
  onAlertGuardian: () => void;
  isAlerting: boolean;
}) {
  const cfg = LEVEL_CONFIG[status.level] ?? LEVEL_CONFIG.safe;
  const LevelIcon = cfg.Icon;
  const isSafe = status.level === 'safe';

  return (
    <Card className={`border-2 ${cfg.border} ${cfg.bg}`}>
      <CardContent className="pt-5 pb-4">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div className="flex items-center gap-3">
            <LevelIcon className={`h-6 w-6 ${cfg.iconColor} flex-shrink-0`} />
            <div>
              <div className="flex items-center gap-2">
                <span className={`text-xl font-bold ${cfg.iconColor}`}>{cfg.label}</span>
                {status.cooldown_active && (
                  <Badge variant="outline" className="text-xs gap-1">
                    <Clock className="h-3 w-3" />
                    Cooldown: {status.cooldown_remaining_minutes}m left
                  </Badge>
                )}
              </div>
              <p className="text-sm text-muted-foreground">{status.message}</p>
            </div>
          </div>

          {!isSafe && (
            <Button
              variant="destructive"
              size="sm"
              onClick={onAlertGuardian}
              disabled={isAlerting}
              className="gap-2 flex-shrink-0"
            >
              <Phone className="h-3.5 w-3.5" />
              Alert Guardian
            </Button>
          )}
        </div>

        {/* Quick stats row */}
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 sm:gap-3 mt-4">
          <div className="text-center p-2.5 bg-background/60 rounded-lg">
            <div className={`text-xl font-bold ${status.daily_loss_used_percent >= 85 ? 'text-red-500' : status.daily_loss_used_percent >= 70 ? 'text-orange-500' : 'text-foreground'}`}>
              {status.daily_loss_used_percent.toFixed(0)}%
            </div>
            <div className="text-xs text-muted-foreground">Daily Loss Used</div>
            <Progress value={Math.min(status.daily_loss_used_percent, 100)} className="mt-1.5 h-1" />
          </div>
          <div className="text-center p-2.5 bg-background/60 rounded-lg">
            <div className="text-xl font-bold">{status.trade_count_today}</div>
            <div className="text-xs text-muted-foreground">Trades Today</div>
          </div>
          <div className="text-center p-2.5 bg-background/60 rounded-lg">
            <div className={`text-xl font-bold ${status.consecutive_losses >= 3 ? 'text-red-500' : status.consecutive_losses >= 2 ? 'text-orange-500' : 'text-foreground'}`}>
              {status.consecutive_losses}
            </div>
            <div className="text-xs text-muted-foreground">Consecutive Losses</div>
          </div>
        </div>

        {/* Active triggers */}
        {status.triggers.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mt-3">
            {status.triggers.map((t, i) => (
              <Badge key={i} variant="outline" className="text-xs capitalize">
                {t.replace(/_/g, ' ')}
              </Badge>
            ))}
          </div>
        )}

        {/* Recommendations */}
        {status.recommendations.length > 0 && (
          <div className="mt-3 p-3 bg-background/60 rounded-lg space-y-1">
            {status.recommendations.map((rec, i) => (
              <p key={i} className="text-sm text-muted-foreground">• {rec}</p>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Alert History Card
// ---------------------------------------------------------------------------
function AlertHistoryCard({ history }: { history: CooldownRecord[] }) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <Clock className="h-4 w-4 text-muted-foreground" />
          Alert History (7 days)
        </CardTitle>
        <CardDescription>Cooldowns and interventions triggered</CardDescription>
      </CardHeader>
      <CardContent>
        {history.length > 0 ? (
          <div className="space-y-2">
            {history.map((record, i) => (
              <div key={i} className="flex items-center justify-between p-2.5 border rounded-lg text-sm">
                <div>
                  <p className="font-medium capitalize">{record.reason.replace(/_/g, ' ')}</p>
                  <p className="text-xs text-muted-foreground">
                    {new Date(record.started_at).toLocaleString('en-IN', {
                      month: 'short', day: 'numeric',
                      hour: '2-digit', minute: '2-digit',
                      timeZone: 'Asia/Kolkata',
                    })}
                    {' · '}{record.duration_minutes}m cooldown
                  </p>
                </div>
                <Badge variant="outline" className="text-xs">
                  {record.is_active ? 'Active' : 'Ended'}
                </Badge>
              </div>
            ))}
          </div>
        ) : (
          <div className="flex flex-col items-center py-6 text-center text-muted-foreground">
            <Shield className="h-8 w-8 mb-2 opacity-30" />
            <p className="text-sm">No alerts in the last 7 days</p>
            <p className="text-xs mt-1">Keep trading disciplined!</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------
const EMPTY_STREAK: StreakData = {
  current_streak_days: 0,
  longest_streak_days: 0,
  streak_start_date: null,
  daily_status: [],
  milestones_achieved: [],
};

const MILESTONE_LABELS: Record<number, string> = {
  3: '3-day clean', 7: 'Week clean', 14: '2-week clean', 21: '3-week clean', 30: '30-day master',
};

export default function MyPatterns() {
  const { isConnected, isLoading: brokerLoading, account } = useBroker();
  const { alerts } = useAlerts();
  const { lastTradeEvent, lastAlertEvent } = useWebSocket();

  const [status, setStatus] = useState<DangerZoneStatus | null>(null);
  const [alertHistory, setAlertHistory] = useState<CooldownRecord[]>([]);
  const [streakData, setStreakData] = useState<StreakData>(EMPTY_STREAK);
  const [statusLoading, setStatusLoading] = useState(true);
  const [isAlerting, setIsAlerting] = useState(false);

  // Fetch live danger zone status + alert history + streak data
  const fetchStatus = useCallback(async () => {
    if (!account?.id) return;
    try {
      const [statusRes, summaryRes, alertsRes] = await Promise.all([
        api.get('/api/danger-zone/status'),
        api.get('/api/danger-zone/summary'),
        api.get('/api/risk/alerts', { params: { hours: 720 } }), // 30 days for streak
      ]);
      setStatus(statusRes.data);
      setAlertHistory(summaryRes.data.cooldown_history_7d || []);

      // Compute streak: consecutive days without a high/critical alert
      const rawAlerts: any[] = alertsRes.data.alerts || [];
      const alertsByDate: Record<string, { hasHighCritical: boolean }> = {};
      for (const a of rawAlerts) {
        const date = new Date(a.detected_at || a.created_at)
          .toLocaleDateString('en-CA', { timeZone: 'Asia/Kolkata' }); // YYYY-MM-DD
        if (!alertsByDate[date]) alertsByDate[date] = { hasHighCritical: false };
        if (a.severity === 'high' || a.severity === 'critical') {
          alertsByDate[date].hasHighCritical = true;
        }
      }

      const daily_status: DailyAdherence[] = [];
      for (let i = 0; i < 30; i++) {
        const d = new Date();
        d.setDate(d.getDate() - i);
        const dateStr = d.toLocaleDateString('en-CA', { timeZone: 'Asia/Kolkata' });
        const day = alertsByDate[dateStr];
        daily_status.push({
          date: dateStr,
          all_goals_followed: !day?.hasHighCritical,
          goals_broken: day?.hasHighCritical ? ['high_critical_alert'] : [],
          trading_day: !!alertsByDate[dateStr],
        });
      }

      let current_streak_days = 0;
      for (const day of daily_status) {
        if (!day.all_goals_followed) break;
        current_streak_days++;
      }

      let longest = 0, run = 0;
      for (const day of daily_status) {
        run = day.all_goals_followed ? run + 1 : 0;
        if (run > longest) longest = run;
      }

      const milestones_achieved: StreakMilestone[] = [3, 7, 14, 21, 30]
        .filter(d => longest >= d)
        .map(d => ({ days: d, achieved_at: daily_status[0]?.date ?? '', label: MILESTONE_LABELS[d] }));

      setStreakData({
        current_streak_days,
        longest_streak_days: longest,
        streak_start_date: current_streak_days > 0 ? (daily_status[current_streak_days - 1]?.date ?? null) : null,
        daily_status,
        milestones_achieved,
      });
    } catch {
      // Non-fatal — page still works without status
    } finally {
      setStatusLoading(false);
    }
  }, [account?.id]);

  // Initial load
  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  // Refetch when a trade fills or a risk alert fires — streak and danger level change at these moments
  useEffect(() => {
    if (lastTradeEvent || lastAlertEvent) fetchStatus();
  }, [lastTradeEvent, lastAlertEvent]); // eslint-disable-line react-hooks/exhaustive-deps

  // Derive patterns from backend alerts (backend is the single detection engine)
  const patterns = useMemo(() => alerts.map(a => a.pattern), [alerts]);
  const emotionalTax    = useMemo(() => calculateEmotionalTax(patterns as any, []), [patterns]);
  const recommendations = useMemo(() => getTopRecommendations(emotionalTax), [emotionalTax]);

  const handleAlertGuardian = async () => {
    setIsAlerting(true);
    try {
      const res = await api.post('/api/danger-zone/trigger-intervention');
      if (res.data.whatsapp_sent) toast.success('WhatsApp alert sent to guardian');
      else if (res.data.notification_sent) toast.success('Push notification sent');
      else toast.info('Alert logged. Configure guardian phone for WhatsApp alerts.');
      fetchStatus();
    } catch {
      toast.error('Failed to send alert');
    } finally {
      setIsAlerting(false);
    }
  };

  if (brokerLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!isConnected) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Brain className="h-6 w-6 text-primary" />
            My Patterns
          </h1>
          <p className="text-muted-foreground text-sm mt-1">
            Live risk monitoring and behavioral patterns
          </p>
        </div>
        <div className="flex flex-col items-center justify-center min-h-[50vh] bg-card rounded-lg border border-border">
          <div className="p-4 rounded-full bg-primary/10 mb-6">
            <Link2 className="h-12 w-12 text-primary" />
          </div>
          <h2 className="text-xl font-semibold text-foreground mb-2">Connect Your Broker</h2>
          <p className="text-muted-foreground text-center max-w-md mb-6">
            Connect your Zerodha account to monitor your trading patterns.
          </p>
          <Link to="/settings">
            <Button size="lg" className="gap-2">
              <Link2 className="h-5 w-5" />
              Connect Zerodha
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Brain className="h-6 w-6 text-primary" />
            My Patterns
          </h1>
          <p className="text-muted-foreground text-sm mt-1">
            Live risk monitoring and behavioral patterns
          </p>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={fetchStatus}
          disabled={statusLoading}
          className="gap-2 self-start sm:self-auto"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${statusLoading ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      {/* Live Danger Status Banner */}
      {status && (
        <DangerStatusBanner
          status={status}
          onAlertGuardian={handleAlertGuardian}
          isAlerting={isAlerting}
        />
      )}

      {/* Pattern-based Recommendations */}
      {recommendations.length > 0 && (
        <div className="flex items-start gap-3 p-4 rounded-lg border border-amber-500/30 bg-amber-500/5">
          <AlertTriangle className="h-4 w-4 text-amber-500 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium">Based on your patterns:</p>
            <ul className="mt-1.5 space-y-1">
              {recommendations.map((rec, i) => (
                <li key={i} className="text-sm text-muted-foreground flex items-center gap-2">
                  <span className="w-1 h-1 rounded-full bg-amber-500 flex-shrink-0" />
                  {rec}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* Pattern Calendar — full width */}
      <PatternCalendar />

      {/* Main Grid */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Left Column */}
        <div className="space-y-6">
          <EmotionalTaxCard tax={emotionalTax} period="month" />
        </div>

        {/* Right Column */}
        <div className="space-y-6">
          <StreakTrackerCard streak={streakData} goalDays={30} />
          <AlertHistoryCard history={alertHistory} />
        </div>
      </div>
    </div>
  );
}
