// My Patterns — Merged Goals + Risk Monitoring Page
// Shows: live danger status, emotional tax, streak, alert history
// Commitments feature removed — no user-dependent friction

import { useState, useEffect, useCallback, useMemo } from 'react';
import { Link } from 'react-router-dom';
import {
  Brain, Link2, AlertTriangle, Shield,
  Clock, RefreshCw, Phone
} from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
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
  leftBorder: string;
  dotColor: string;
  labelColor: string;
  label: string;
  Icon: typeof Shield;
}> = {
  safe:     { leftBorder: 'border-l-tm-brand',    dotColor: 'bg-tm-brand',   labelColor: 'text-tm-brand',  label: 'Safe',     Icon: Shield },
  caution:  { leftBorder: 'border-l-tm-obs',      dotColor: 'bg-tm-obs',     labelColor: 'text-tm-obs',    label: 'Caution',  Icon: AlertTriangle },
  warning:  { leftBorder: 'border-l-tm-obs',      dotColor: 'bg-tm-obs',     labelColor: 'text-tm-obs',    label: 'Warning',  Icon: AlertTriangle },
  danger:   { leftBorder: 'border-l-tm-loss',     dotColor: 'bg-tm-loss',    labelColor: 'text-tm-loss',   label: 'Danger',   Icon: AlertTriangle },
  critical: { leftBorder: 'border-l-tm-loss',     dotColor: 'bg-tm-loss',    labelColor: 'text-tm-loss',   label: 'CRITICAL', Icon: AlertTriangle },
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
  const isSafe = status.level === 'safe';
  const lossColor = status.daily_loss_used_percent >= 85
    ? 'text-tm-loss' : status.daily_loss_used_percent >= 70
      ? 'text-tm-obs' : 'text-foreground';
  const lossBarColor = status.daily_loss_used_percent >= 85
    ? 'bg-tm-loss' : status.daily_loss_used_percent >= 70
      ? 'bg-tm-obs' : 'bg-tm-brand';

  return (
    <div className={`tm-card border-l-2 ${cfg.leftBorder} px-5 py-4`}>
      <div className="flex items-center justify-between gap-4 flex-wrap mb-4">
        <div className="flex items-center gap-2.5">
          <span className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${cfg.dotColor}`} />
          <span className={`text-[15px] font-bold ${cfg.labelColor}`}>{cfg.label}</span>
          {status.cooldown_active && (
            <span className="flex items-center gap-1 text-[11px] text-muted-foreground border border-border rounded px-2 py-0.5">
              <Clock className="h-3 w-3" />
              Cooldown: {status.cooldown_remaining_minutes}m left
            </span>
          )}
          <p className="text-[12px] text-muted-foreground hidden sm:block">{status.message}</p>
        </div>
        {!isSafe && (
          <button
            onClick={onAlertGuardian}
            disabled={isAlerting}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-tm-loss text-white text-[12px] font-medium hover:bg-tm-loss/90 transition-colors disabled:opacity-50"
          >
            <Phone className="h-3.5 w-3.5" />
            Alert Guardian
          </button>
        )}
      </div>
      <p className="text-[12px] text-muted-foreground sm:hidden mb-3">{status.message}</p>

      {/* Quick stats */}
      <div className="grid grid-cols-3 gap-3">
        <div className="tm-card px-3 py-2.5 text-center">
          <div className={`text-[18px] font-bold font-mono tabular-nums ${lossColor}`}>
            {status.daily_loss_used_percent.toFixed(0)}%
          </div>
          <div className="text-[10px] text-muted-foreground">Daily Loss Used</div>
          <div className="mt-1.5 w-full bg-slate-100 dark:bg-neutral-700/40 rounded-full h-1">
            <div className={`h-1 rounded-full ${lossBarColor}`} style={{ width: `${Math.min(status.daily_loss_used_percent, 100)}%` }} />
          </div>
        </div>
        <div className="tm-card px-3 py-2.5 text-center">
          <div className="text-[18px] font-bold font-mono tabular-nums text-foreground">{status.trade_count_today}</div>
          <div className="text-[10px] text-muted-foreground">Trades Today</div>
        </div>
        <div className="tm-card px-3 py-2.5 text-center">
          <div className={`text-[18px] font-bold font-mono tabular-nums ${status.consecutive_losses >= 3 ? 'text-tm-loss' : status.consecutive_losses >= 2 ? 'text-tm-obs' : 'text-foreground'}`}>
            {status.consecutive_losses}
          </div>
          <div className="text-[10px] text-muted-foreground">Consec. Losses</div>
        </div>
      </div>

      {/* Active triggers */}
      {status.triggers.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mt-3">
          {status.triggers.map((t) => (
            <span key={t} className="text-[11px] text-muted-foreground border border-border rounded-full px-2 py-0.5 capitalize">
              {t.replace(/_/g, ' ')}
            </span>
          ))}
        </div>
      )}

      {/* Recommendations */}
      {status.recommendations.length > 0 && (
        <div className="mt-3 border-t border-border pt-3 space-y-1">
          {status.recommendations.map((rec, i) => (
            <p key={`rec-${i}`} className="text-[12px] text-muted-foreground">· {rec}</p>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Alert History Card
// ---------------------------------------------------------------------------
function AlertHistoryCard({ history }: { history: CooldownRecord[] }) {
  return (
    <div className="tm-card overflow-hidden">
      <div className="px-5 py-4 border-b border-border flex items-center gap-2">
        <Clock className="h-4 w-4 text-muted-foreground" />
        <span className="tm-label">Alert History (7 days)</span>
      </div>
      <div className="px-5 py-4">
        {history.length > 0 ? (
          <div className="space-y-2">
            {history.map((record) => (
              <div key={record.id} className="flex items-center justify-between py-2 border-b border-border/50 last:border-0">
                <div>
                  <p className="text-[12px] font-medium text-foreground capitalize">{record.reason.replace(/_/g, ' ')}</p>
                  <p className="text-[11px] text-muted-foreground mt-0.5">
                    {new Date(record.started_at).toLocaleString('en-IN', {
                      month: 'short', day: 'numeric',
                      hour: '2-digit', minute: '2-digit',
                      timeZone: 'Asia/Kolkata',
                    })}
                    {' · '}{record.duration_minutes}m cooldown
                  </p>
                </div>
                <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${record.is_active ? 'text-tm-obs border-amber-300 dark:border-amber-700/50 bg-amber-50 dark:bg-amber-900/15' : 'text-muted-foreground border-border'}`}>
                  {record.is_active ? 'Active' : 'Ended'}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <div className="flex flex-col items-center py-6 text-center">
            <Shield className="h-7 w-7 text-muted-foreground/30 mb-2" />
            <p className="text-[12px] text-muted-foreground">No alerts in the last 7 days</p>
          </div>
        )}
      </div>
    </div>
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
      <div className="max-w-4xl mx-auto space-y-4 pb-12">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-40 rounded-xl" />
        <div className="grid grid-cols-2 gap-4">
          <Skeleton className="h-56 rounded-xl" />
          <Skeleton className="h-56 rounded-xl" />
        </div>
      </div>
    );
  }

  if (!isConnected) {
    return (
      <div className="max-w-4xl mx-auto pb-12">
        <div className="mb-5">
          <h1 className="t-heading-lg text-foreground">Risk Monitor</h1>
        </div>
        <div className="tm-card flex flex-col items-center justify-center min-h-[50vh] text-center py-16">
          <div className="p-4 rounded-full bg-teal-50 dark:bg-teal-900/20 mb-5">
            <Link2 className="h-10 w-10 text-tm-brand" />
          </div>
          <h2 className="text-base font-semibold text-foreground mb-1">Connect Your Broker</h2>
          <p className="text-sm text-muted-foreground max-w-sm mb-5">
            Connect your Zerodha account to monitor live risk and behavioral patterns.
          </p>
          <Link to="/settings">
            <Button size="sm" className="gap-2 bg-tm-brand hover:bg-tm-brand/90 text-white">
              <Link2 className="h-4 w-4" />
              Connect Zerodha
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto pb-12">
      {/* Page header */}
      <div className="mb-5 flex items-center justify-between">
        <h1 className="t-heading-lg text-foreground">Risk Monitor</h1>
        <button
          onClick={fetchStatus}
          disabled={statusLoading}
          className="flex items-center gap-1.5 text-[12px] text-muted-foreground hover:text-foreground transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${statusLoading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      <div className="space-y-5">
        {/* Live danger status */}
        {status && (
          <DangerStatusBanner
            status={status}
            onAlertGuardian={handleAlertGuardian}
            isAlerting={isAlerting}
          />
        )}

        {/* Recommendations */}
        {recommendations.length > 0 && (
          <div className="tm-card border-l-2 border-l-tm-obs px-5 py-4 flex items-start gap-3">
            <AlertTriangle className="h-4 w-4 text-tm-obs flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-[12px] font-semibold text-foreground mb-1.5">Based on your patterns:</p>
              <ul className="space-y-1">
                {recommendations.map((rec, i) => (
                  <li key={`main-rec-${i}`} className="text-[12px] text-muted-foreground flex items-center gap-2">
                    <span className="w-1 h-1 rounded-full bg-tm-obs flex-shrink-0" />
                    {rec}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}

        {/* Pattern Calendar */}
        <PatternCalendar />

        {/* Grid */}
        <div className="grid gap-5 lg:grid-cols-2">
          <div className="space-y-5">
            <EmotionalTaxCard tax={emotionalTax} period="month" />
          </div>
          <div className="space-y-5">
            <StreakTrackerCard streak={streakData} goalDays={30} />
            <AlertHistoryCard history={alertHistory} />
          </div>
        </div>
      </div>
    </div>
  );
}
