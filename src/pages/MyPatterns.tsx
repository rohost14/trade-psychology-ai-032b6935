// My Patterns — Merged Goals + Risk Monitoring Page
// Shows: live danger status, emotional tax, streak, alert history
// Commitments feature removed — no user-dependent friction

import { useState, useEffect, useCallback, useMemo } from 'react';
import { Link } from 'react-router-dom';
import {
  Link2, AlertTriangle, Shield,
  Clock, RefreshCw, Phone,
} from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import { useBroker } from '@/contexts/BrokerContext';
import { useAlerts } from '@/contexts/AlertContext';
import { useWebSocket } from '@/contexts/WebSocketContext';
import { BehaviorScoresCard } from '@/components/patterns/BehaviorScoresCard';
import { StreakTrackerCard } from '@/components/goals/StreakTrackerCard';
import PatternCalendar from '@/components/patterns/PatternCalendar';
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
          <div className="mt-1.5 w-full bg-muted rounded-full h-1">
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
        <span className="tm-label">Cooldown History (7 days)</span>
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
            <p className="text-[12px] text-muted-foreground">No cooldowns in the last 7 days</p>
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
      const rawAlerts: { detected_at?: string; created_at?: string; severity?: string }[] = alertsRes.data.alerts || [];
      const alertsByDate: Record<string, { hasHighCritical: boolean }> = {};
      for (const a of rawAlerts) {
        const date = new Date(a.detected_at || a.created_at)
          .toLocaleDateString('en-CA', { timeZone: 'Asia/Kolkata' }); // YYYY-MM-DD
        if (!alertsByDate[date]) alertsByDate[date] = { hasHighCritical: false };
        // Backend severities are danger/caution/critical/info. A "clean" day = no
        // danger/critical alert. (Was checking 'high', which never occurs, so danger
        // days were silently counted as clean — inflating the streak.)
        if (a.severity === 'danger' || a.severity === 'critical') {
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
          trading_day: true, // all non-weekend days are trading days; alert presence is not a reliable proxy
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
    } catch (err: unknown) {
      if ((err as { code?: string })?.code === 'ERR_CANCELED') return; // aborted on unmount — not an error
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

  // Most frequent pattern, last 30 days. Keyed by backend_type so the tailored
  // recommendation lookup (patternRecs, backend-keyed) matches.
  const worstPattern = useMemo(() => {
    const cutoff = Date.now() - 30 * 24 * 60 * 60 * 1000;
    const map = new Map<string, { name: string; count: number }>();
    for (const a of alerts) {
      if (new Date(a.shown_at ?? 0).getTime() < cutoff) continue;
      const key = a.pattern.backend_type ?? a.pattern.type;
      const existing = map.get(key) ?? { name: a.pattern.name, count: 0 };
      existing.count += 1;
      map.set(key, existing);
    }
    if (map.size === 0) return null;
    return Array.from(map.entries())
      .map(([type, d]) => ({ type, ...d }))
      .sort((a, b) => b.count - a.count)[0];
  }, [alerts]);

  // Specific actionable recommendations derived from real data (not generic strings)
  const specificRecs = useMemo((): string[] => {
    const recs: string[] = [];

    // 1. Worst pattern with real numbers
    if (worstPattern && worstPattern.count >= 2) {
      // Cost modelling intentionally not shown (raw-P&L / no-estimation policy).
      const costStr = '';
      const patternRecs: Record<string, string> = {
        revenge_trade:            `Revenge trading fired ${worstPattern.count}×${costStr}. Set a rule: no new trade within 10 minutes of a loss.`,
        rapid_reentry:            `Rapid re-entry fired ${worstPattern.count}×${costStr}. After exiting a losing position, wait at least 5 minutes before the same instrument.`,
        overtrading:              `Overtrading fired ${worstPattern.count}×${costStr}. Your best sessions have fewer trades — cap at your own session average.`,
        size_escalation:          `Size escalation fired ${worstPattern.count}×${costStr}. When you're losing, shrink size — not the opposite.`,
        martingale_behaviour:     `Martingale pattern fired ${worstPattern.count}×${costStr}. Doubling down after losses amplifies risk at the worst moment.`,
        consecutive_loss_streak:  `${worstPattern.count} consecutive-loss alerts this month${costStr}. After 3 losses in a row, stop for the session.`,
        panic_exit:               `Panic exits fired ${worstPattern.count}×${costStr}. Set your stop-loss at entry — not when the position is already down.`,
        post_loss_recovery_bet:   `Recovery bets fired ${worstPattern.count}×${costStr}. Larger size after a loss is the highest-risk trade you can take.`,
        profit_giveaway:          `You gave back gains ${worstPattern.count}×${costStr}. After a strong session P&L, treat the next trade with extra scrutiny.`,
        fomo_entry:               `FOMO entries fired ${worstPattern.count}×${costStr}. Wait for your own setup — not one driven by watching a move you missed.`,
        no_stoploss:              `No stop-loss exits fired ${worstPattern.count}×${costStr}. Define your exit before you enter — every time.`,
        opening_5min_trap:        `Opening-5min entries fired ${worstPattern.count}×${costStr}. The first 8 minutes have the widest spreads. Wait.`,
        end_of_session_mis_panic: `Late MIS entries fired ${worstPattern.count}×${costStr}. After 15:10 IST, MIS auto-squares in minutes — not a normal trade window.`,
      };
      const rec = patternRecs[worstPattern.type];
      if (rec) recs.push(rec);
      else recs.push(`${worstPattern.name} fired ${worstPattern.count}× this month${costStr}.`);
    }

    // 2. Danger zone state — from live status
    if (status) {
      if (status.consecutive_losses >= 3) {
        recs.push(`${status.consecutive_losses} consecutive losses right now. History says the next trade is statistically weaker — consider stopping here.`);
      } else if (status.consecutive_losses === 2) {
        recs.push('2 consecutive losses. One more and consecutive-loss rules apply — trade with reduced size next.');
      }
      if (status.daily_loss_used_percent >= 80 && status.level !== 'safe') {
        recs.push(`${status.daily_loss_used_percent.toFixed(0)}% of daily loss limit used. Remaining trades risk crossing the limit — size down or stop.`);
      }
    }

    // 3. Week frequency context
    const cutoffWeek = Date.now() - 7 * 24 * 60 * 60 * 1000;
    const weekAlerts = alerts.filter(a => new Date(a.shown_at ?? 0).getTime() >= cutoffWeek);
    if (weekAlerts.length >= 5 && recs.length < 3) {
      recs.push(`${weekAlerts.length} behavioral alerts this week. More alerts in a week typically means session quality is declining — review the pattern calendar.`);
    }

    return recs.slice(0, 3);
  }, [worstPattern, status, alerts]);

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
          <h1 className="t-heading-lg text-foreground">My Patterns</h1>
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
        <h1 className="t-heading-lg text-foreground">My Patterns</h1>
        <button
          onClick={() => fetchStatus()}
          disabled={statusLoading}
          className="flex items-center gap-1.5 text-[12px] text-muted-foreground hover:text-foreground transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${statusLoading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      <div className="space-y-5">
        {/* Streak — the hero. This is the number a user comes back for, so it leads. */}
        <StreakTrackerCard streak={streakData} goalDays={30} />

        {/* Behavior Risk headline + drivers (Phase 5, master 1D.9) */}
        <BehaviorScoresCard />

        {/* Worst pattern callout */}
        {worstPattern && (
          <div className="tm-card border-l-2 border-l-tm-loss px-5 py-4">
            <p className="text-[11px] font-semibold text-tm-loss uppercase tracking-wide mb-2">
              Your most frequent pattern this month
            </p>
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-[15px] font-bold text-foreground">{worstPattern.name}</p>
                <p className="text-[12px] text-muted-foreground mt-0.5">
                  Detected {worstPattern.count}× in the last 30 days
                </p>
              </div>
              <div className="text-right flex-shrink-0">
                <p className="text-[17px] font-bold font-mono tabular-nums text-tm-loss">{worstPattern.count}×</p>
              </div>
            </div>
          </div>
        )}

        {/* Live danger status */}
        {status && (
          <DangerStatusBanner
            status={status}
            onAlertGuardian={handleAlertGuardian}
            isAlerting={isAlerting}
          />
        )}

        {/* Specific data-driven recommendations */}
        {specificRecs.length > 0 && (
          <div className="tm-card border-l-2 border-l-tm-obs px-5 py-4 flex items-start gap-3">
            <AlertTriangle className="h-4 w-4 text-tm-obs flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-[12px] font-semibold text-foreground mb-1.5">Based on your data:</p>
              <ul className="space-y-1.5">
                {specificRecs.map((rec, i) => (
                  <li key={`srec-${i}`} className="text-[12px] text-muted-foreground flex items-start gap-2">
                    <span className="w-1 h-1 rounded-full bg-tm-obs flex-shrink-0 mt-1.5" />
                    {rec}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}

        {/* Pattern Calendar */}
        <PatternCalendar />

        <AlertHistoryCard history={alertHistory} />

        {/* Pattern frequency lives on the Alerts "Patterns" tab (with the response
            stats and per-pattern cost) — cross-link instead of recomputing it here. */}
        <div className="tm-card px-5 py-4 flex items-center justify-between gap-4 flex-wrap">
          <div>
            <p className="text-[13px] font-medium text-foreground">Want the full pattern breakdown?</p>
            <p className="text-[12px] text-muted-foreground mt-0.5">
              Per-pattern frequency, how often you acted on each alert, and the P&amp;L behind them.
            </p>
          </div>
          <Link
            to="/alerts"
            className="text-[12px] font-medium text-tm-brand hover:underline flex-shrink-0"
          >
            Open Alerts →
          </Link>
        </div>
      </div>
    </div>
  );
}
