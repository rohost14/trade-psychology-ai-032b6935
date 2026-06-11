// My Patterns — Merged Goals + Risk Monitoring Page
// Shows: live danger status, emotional tax, streak, alert history
// Commitments feature removed — no user-dependent friction

import { useState, useEffect, useCallback, useMemo } from 'react';
import { Link } from 'react-router-dom';
import {
  Brain, Link2, AlertTriangle, Shield,
  Clock, RefreshCw, Phone, TrendingUp, Zap, Flame,
} from 'lucide-react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer,
} from 'recharts';
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
// Discipline types + components
// ---------------------------------------------------------------------------

interface DisciplineData {
  has_data: boolean;
  score: number;
  max_score: number;
  week_start: string;
  danger_alerts: number;
  caution_alerts: number;
  trades_this_week: number;
  revenge_free_days: number;
  weekly_trend: number[];
  breakdown: {
    alerts_score: number;
    quality_score: number;
  };
}

function ScoreGauge({ score, max }: { score: number; max: number }) {
  const pct = Math.min(100, (score / max) * 100);
  const color = pct >= 70 ? '#16A34A' : pct >= 45 ? '#D97706' : '#DC2626';
  const circumference = 2 * Math.PI * 45;
  const dashOffset = circumference * (1 - pct / 100);

  return (
    <div className="flex flex-col items-center">
      <div className="relative w-28 h-28">
        <svg viewBox="0 0 100 100" className="transform -rotate-90 w-full h-full">
          <circle cx="50" cy="50" r="45" stroke="var(--border)" strokeWidth="8" fill="none" />
          <circle
            cx="50" cy="50" r="45"
            stroke={color}
            strokeWidth="8"
            fill="none"
            strokeDasharray={circumference}
            strokeDashoffset={dashOffset}
            strokeLinecap="round"
            className="transition-all duration-700"
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <p className="text-2xl font-bold font-mono tabular-nums text-foreground">{score}</p>
          <p className="text-[10px] text-muted-foreground">/ {max}</p>
        </div>
      </div>
      <p className={cn(
        'text-xs font-semibold mt-1.5',
        pct >= 70 ? 'text-tm-profit' : pct >= 45 ? 'text-tm-obs' : 'text-tm-loss'
      )}>
        {pct >= 80 ? 'Excellent' : pct >= 60 ? 'Good' : pct >= 40 ? 'Needs work' : 'Struggling'}
      </p>
    </div>
  );
}

function DisciplineTrendTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-card border border-border rounded-md px-2 py-1.5 text-xs">
      <p className="font-mono tabular-nums">{payload[0].value} / 100</p>
    </div>
  );
}

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
      <div className="px-5 py-3.5 border-b border-border flex items-center gap-2">
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
  const [disciplineData, setDisciplineData] = useState<DisciplineData | null>(null);

  // Fetch live danger zone status + alert history + streak data
  const fetchStatus = useCallback(async (signal?: AbortSignal) => {
    if (!account?.id) return;
    try {
      const [statusRes, summaryRes, alertsRes] = await Promise.all([
        api.get('/api/danger-zone/status', { signal }),
        api.get('/api/danger-zone/summary', { signal }),
        api.get('/api/risk/alerts', { params: { hours: 720 }, signal }), // 30 days for streak
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
        // Parse IST date to get IST day-of-week (avoids UTC-vs-IST offset issues)
        const [y, mo, dy] = dateStr.split('-').map(Number);
        const dow = new Date(y, mo - 1, dy).getDay(); // 0 = Sun, 6 = Sat
        if (dow === 0 || dow === 6) continue; // NSE doesn't trade on weekends
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
        // achieved_at = the date the streak first hit d days (d-1 index back in the
        // sorted-newest-first array). Falls back to the streak-start date if index
        // is out of range (milestone is from a longer past streak).
        .map(d => ({
          days: d,
          achieved_at: daily_status[d - 1]?.date ?? daily_status[daily_status.length - 1]?.date ?? '',
          label: MILESTONE_LABELS[d],
        }));

      setStreakData({
        current_streak_days,
        longest_streak_days: longest,
        streak_start_date: current_streak_days > 0 ? (daily_status[current_streak_days - 1]?.date ?? null) : null,
        daily_status,
        milestones_achieved,
      });
    } catch (err: any) {
      if (err?.code === 'ERR_CANCELED') return; // aborted on unmount — not an error
      // Non-fatal — page still works without status
    } finally {
      if (!signal?.aborted) setStatusLoading(false);
    }
  }, [account?.id]);

  // Initial load — cancel in-flight requests if the component unmounts
  useEffect(() => {
    const controller = new AbortController();
    fetchStatus(controller.signal);
    return () => controller.abort();
  }, [fetchStatus]);

  // Refetch when a trade fills or a risk alert fires — streak and danger level change at these moments
  useEffect(() => {
    if (lastTradeEvent || lastAlertEvent) fetchStatus();
  }, [lastTradeEvent, lastAlertEvent]); // eslint-disable-line react-hooks/exhaustive-deps

  // Discipline score — fetched once on mount, independent of status polling
  useEffect(() => {
    if (!account?.id) return;
    api.get('/api/analytics/discipline-summary')
      .then(r => setDisciplineData(r.data))
      .catch(() => setDisciplineData(null));
  }, [account?.id]);

  // Derive BehaviorPattern objects from backend alerts for EmotionalTax.
  // Alert has no .pattern sub-object; map the fields we do have.
  // estimated_cost is not returned by the backend yet — defaults to 0.
  const patterns = useMemo(() => alerts.map(a => ({
    id: a.id,
    type: (a.pattern_type ?? a.pattern_name ?? 'overtrading') as import('@/types/patterns').PatternType,
    name: a.pattern_name,
    severity: a.severity as import('@/types/patterns').PatternSeverity,
    detected_at: a.timestamp || a.detected_at || new Date().toISOString(),
    description: a.message,
    evidence: { trades_involved: a.related_trade_ids ?? [], time_range: '', market_context: '' },
    historical_insight: '',
    frequency_this_week: 0,
    frequency_this_month: 0,
    estimated_cost: 0,
    insight: '',
  })), [alerts]);
  const emotionalTax    = useMemo(() => calculateEmotionalTax(patterns, []), [patterns]);
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
      <div className="w-full space-y-4 pb-12">
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
      <div className="w-full pb-12">
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
    <div className="w-full pb-12">
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

        {/* Weekly Discipline Score */}
        {disciplineData?.has_data && (
          <div className="tm-card overflow-hidden">
            <div className="px-5 py-3.5 border-b border-border flex items-center gap-2">
              <Zap className="h-4 w-4 text-tm-brand" />
              <p className="text-sm font-medium text-foreground">Weekly Score</p>
              <span className="text-[11px] text-muted-foreground ml-auto">
                Week of {disciplineData.week_start}
              </span>
            </div>
            <div className="p-5">
              <div className="flex flex-col sm:flex-row items-center gap-6">
                <ScoreGauge score={disciplineData.score} max={disciplineData.max_score} />

                <div className="flex-1 w-full space-y-3">
                  {/* Breakdown bars */}
                  <div className="space-y-2">
                    <div>
                      <div className="flex justify-between text-[11px] text-muted-foreground mb-1">
                        <span>Alert control</span>
                        <span className="font-mono">{disciplineData.breakdown.alerts_score} / 60</span>
                      </div>
                      <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                        <div
                          className="h-full bg-tm-brand transition-all"
                          style={{ width: `${(disciplineData.breakdown.alerts_score / 60) * 100}%` }}
                        />
                      </div>
                    </div>
                    <div>
                      <div className="flex justify-between text-[11px] text-muted-foreground mb-1">
                        <span>Trade quality</span>
                        <span className="font-mono">{disciplineData.breakdown.quality_score} / 40</span>
                      </div>
                      <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                        <div
                          className="h-full bg-tm-brand transition-all"
                          style={{ width: `${(disciplineData.breakdown.quality_score / 40) * 100}%` }}
                        />
                      </div>
                    </div>
                  </div>

                  {/* Quick stats */}
                  <div className="flex gap-4 pt-1">
                    <div>
                      <p className="text-[10px] text-muted-foreground uppercase">Trades</p>
                      <p className="text-sm font-mono font-semibold text-foreground">
                        {disciplineData.trades_this_week}
                      </p>
                    </div>
                    <div>
                      <p className="text-[10px] text-muted-foreground uppercase">Danger alerts</p>
                      <p className={cn(
                        'text-sm font-mono font-semibold',
                        disciplineData.danger_alerts > 0 ? 'text-tm-loss' : 'text-tm-profit',
                      )}>
                        {disciplineData.danger_alerts}
                      </p>
                    </div>
                    <div>
                      <p className="text-[10px] text-muted-foreground uppercase">Caution alerts</p>
                      <p className={cn(
                        'text-sm font-mono font-semibold',
                        disciplineData.caution_alerts > 2 ? 'text-tm-obs' : 'text-foreground',
                      )}>
                        {disciplineData.caution_alerts}
                      </p>
                    </div>
                    <div>
                      <p className="text-[10px] text-muted-foreground uppercase flex items-center gap-1">
                        <Flame className="h-2.5 w-2.5 text-tm-obs" /> Revenge-free
                      </p>
                      <p className={cn(
                        'text-sm font-mono font-semibold',
                        disciplineData.revenge_free_days >= 5 ? 'text-tm-profit'
                          : disciplineData.revenge_free_days >= 2 ? 'text-tm-obs'
                            : 'text-tm-loss',
                      )}>
                        {disciplineData.revenge_free_days}d
                      </p>
                    </div>
                  </div>
                </div>

                {/* 4-week trend (only when enough data) */}
                {disciplineData.weekly_trend.length > 1 && (
                  <div className="w-full sm:w-48 shrink-0">
                    <div className="flex items-center gap-1.5 mb-2">
                      <TrendingUp className="h-3.5 w-3.5 text-muted-foreground" />
                      <p className="text-[11px] text-muted-foreground font-medium">4-Week Trend</p>
                    </div>
                    <ResponsiveContainer width="100%" height={80}>
                      <LineChart
                        data={disciplineData.weekly_trend.map((s, i) => ({
                          week: `W-${disciplineData.weekly_trend.length - i}`,
                          score: s,
                        }))}
                      >
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                        <XAxis
                          dataKey="week"
                          tick={{ fontSize: 10, fill: 'var(--muted-foreground)' }}
                          axisLine={false} tickLine={false}
                        />
                        <YAxis domain={[0, 100]} hide />
                        <Tooltip content={<DisciplineTrendTooltip />} />
                        <Line
                          type="monotone" dataKey="score"
                          stroke="#0D9488" strokeWidth={2}
                          dot={{ fill: '#0D9488', r: 2 }}
                          activeDot={{ r: 4 }}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
