// Alerts Page — Dedicated behavioral alert center
// Replaces the small RecentAlertsCard widget on Dashboard with a full-page view.
// Three tabs: Live (unacknowledged) | History (all 48h) | Patterns (aggregate)

import { useState, useMemo } from 'react';
import { Bell, BellOff, CheckCheck, Clock, TrendingUp, AlertTriangle, Shield, Zap } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useAlerts, AlertNotification } from '@/contexts/AlertContext';
import { PatternSeverity } from '@/types/patterns';

// ---------------------------------------------------------------------------
// Severity helpers
// ---------------------------------------------------------------------------
const SEVERITY_CONFIG: Record<PatternSeverity, {
  border: string;
  bg: string;
  badge: string;
  icon: typeof AlertTriangle;
  label: string;
}> = {
  critical: {
    border: 'border-red-700',
    bg: 'bg-red-50/50 dark:bg-red-950/40',
    badge: 'bg-red-200 text-red-900 dark:bg-red-800 dark:text-red-200',
    icon: AlertTriangle,
    label: 'CRITICAL',
  },
  high: {
    border: 'border-red-500/60',
    bg: 'bg-red-50/30 dark:bg-red-950/20',
    badge: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
    icon: AlertTriangle,
    label: 'High',
  },
  medium: {
    border: 'border-yellow-500/40',
    bg: 'bg-yellow-50/20 dark:bg-yellow-950/10',
    badge: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400',
    icon: Zap,
    label: 'Caution',
  },
  low: {
    border: 'border-blue-400/30',
    bg: '',
    badge: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
    icon: Shield,
    label: 'Info',
  },
};

function timeAgo(dateStr: string | undefined): string {
  if (!dateStr) return '—';
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  const hrs = Math.floor(mins / 60);
  const days = Math.floor(hrs / 24);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  if (hrs < 24) return `${hrs}h ago`;
  return `${days}d ago`;
}

function formatIST(dateStr: string | undefined): string {
  if (!dateStr) return '—';
  return new Date(dateStr).toLocaleString('en-IN', {
    timeZone: 'Asia/Kolkata',
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

// ---------------------------------------------------------------------------
// Alert Card
// ---------------------------------------------------------------------------
function AlertCard({
  alert,
  onAcknowledge,
  showAck = true,
}: {
  alert: AlertNotification;
  onAcknowledge: (id: string) => void;
  showAck?: boolean;
}) {
  const cfg = SEVERITY_CONFIG[alert.pattern.severity] ?? SEVERITY_CONFIG.medium;
  const Icon = cfg.icon;

  return (
    <div className={`rounded-lg border-2 ${cfg.border} ${cfg.bg} p-4 transition-opacity ${alert.acknowledged ? 'opacity-60' : ''}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3 min-w-0">
          <Icon className={`h-4 w-4 mt-0.5 flex-shrink-0 ${alert.pattern.severity === 'low' ? 'text-blue-500' : alert.pattern.severity === 'medium' ? 'text-yellow-500' : 'text-red-500'}`} />
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-semibold text-sm text-foreground">{alert.pattern.name}</span>
              <Badge className={`text-xs ${cfg.badge}`}>{cfg.label}</Badge>
              {alert.acknowledged && (
                <Badge variant="outline" className="text-xs text-muted-foreground">Acknowledged</Badge>
              )}
            </div>
            <p className="text-sm text-muted-foreground mt-1 leading-relaxed">
              {alert.pattern.description}
            </p>
            {alert.pattern.insight && typeof alert.pattern.insight === 'string' && alert.pattern.insight.length > 0 && (
              <p className="text-xs text-muted-foreground/80 mt-1.5 italic">
                {alert.pattern.insight}
              </p>
            )}
            <div className="flex items-center gap-2 mt-2 text-xs text-muted-foreground">
              <Clock className="h-3 w-3" />
              <span title={formatIST(alert.shown_at)}>{timeAgo(alert.shown_at)}</span>
              {(alert.pattern.estimated_cost ?? 0) > 0 && (
                <>
                  <span>·</span>
                  <span className="text-red-500">
                    ₹{(alert.pattern.estimated_cost as number).toLocaleString('en-IN')} estimated cost
                  </span>
                </>
              )}
            </div>
          </div>
        </div>

        {showAck && !alert.acknowledged && (
          <Button
            variant="ghost"
            size="sm"
            className="flex-shrink-0 h-7 px-2 text-xs text-muted-foreground hover:text-foreground"
            onClick={() => onAcknowledge(alert.id)}
            title="Mark as acknowledged"
          >
            <CheckCheck className="h-3.5 w-3.5" />
          </Button>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Live Tab — unacknowledged alerts only
// ---------------------------------------------------------------------------
function LiveTab() {
  const { alerts, acknowledgeAlert, acknowledgeAll } = useAlerts();
  const live = useMemo(
    () => alerts
      .filter(a => !a.acknowledged)
      .sort((a, b) => new Date(b.shown_at ?? 0).getTime() - new Date(a.shown_at ?? 0).getTime()),
    [alerts]
  );

  if (live.length === 0) {
    return (
      <div className="rounded-lg border border-emerald-200 dark:border-emerald-800/50 bg-emerald-50/50 dark:bg-emerald-950/20 px-6 py-8">
        <div className="flex items-start gap-4">
          <div className="mt-0.5 flex-shrink-0 w-9 h-9 rounded-full bg-emerald-100 dark:bg-emerald-900/40 flex items-center justify-center">
            <Shield className="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
          </div>
          <div>
            <p className="text-sm font-semibold text-emerald-800 dark:text-emerald-300">Clean session</p>
            <p className="text-sm text-emerald-700/80 dark:text-emerald-400/80 mt-0.5 leading-relaxed">
              No active behavioral alerts. You're trading with discipline — keep it up.
            </p>
            <p className="text-xs text-emerald-600/60 dark:text-emerald-500/60 mt-3">
              Alerts are saved here as they fire. Check the History tab to review past patterns.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {live.length} unacknowledged alert{live.length !== 1 ? 's' : ''}
        </p>
        <Button variant="ghost" size="sm" className="text-xs gap-1.5" onClick={acknowledgeAll}>
          <CheckCheck className="h-3.5 w-3.5" />
          Acknowledge all
        </Button>
      </div>
      {live.map(alert => (
        <AlertCard key={alert.id} alert={alert} onAcknowledge={acknowledgeAlert} />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// History Tab — all 48h alerts with severity filter
// ---------------------------------------------------------------------------
const SEVERITY_OPTIONS: Array<{ value: string; label: string }> = [
  { value: 'all',      label: 'All Severities' },
  { value: 'critical', label: 'Critical' },
  { value: 'high',     label: 'High' },
  { value: 'medium',   label: 'Caution' },
  { value: 'low',      label: 'Info' },
];

function HistoryTab() {
  const { alerts, acknowledgeAlert } = useAlerts();
  const [severityFilter, setSeverityFilter] = useState('all');

  const filtered = useMemo(() => {
    const sorted = [...alerts].sort(
      (a, b) => new Date(b.shown_at ?? 0).getTime() - new Date(a.shown_at ?? 0).getTime()
    );
    if (severityFilter === 'all') return sorted;
    return sorted.filter(a => a.pattern.severity === severityFilter);
  }, [alerts, severityFilter]);

  return (
    <div className="space-y-4">
      {/* Severity filter */}
      <div className="flex items-center gap-2 flex-wrap">
        {SEVERITY_OPTIONS.map(opt => (
          <button
            key={opt.value}
            onClick={() => setSeverityFilter(opt.value)}
            className={`text-xs px-3 py-1 rounded-full border transition-colors ${
              severityFilter === opt.value
                ? 'bg-primary text-primary-foreground border-primary'
                : 'border-border text-muted-foreground hover:border-foreground hover:text-foreground'
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <BellOff className="h-8 w-8 text-muted-foreground/40 mb-3" />
          <p className="text-sm text-muted-foreground">No alerts match this filter.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map(alert => (
            <AlertCard key={alert.id} alert={alert} onAcknowledge={acknowledgeAlert} />
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Patterns Tab — aggregate by pattern type
// ---------------------------------------------------------------------------
interface PatternSummary {
  type: string;
  name: string;
  count: number;
  totalCost: number;
  latestAt: string | undefined;
  severities: Record<PatternSeverity, number>;
  worstSeverity: PatternSeverity;
}

const SEVERITY_ORDER: PatternSeverity[] = ['critical', 'high', 'medium', 'low'];

function PatternsTab() {
  const { alerts } = useAlerts();

  const summaries = useMemo<PatternSummary[]>(() => {
    const map = new Map<string, PatternSummary>();

    for (const alert of alerts) {
      const key = alert.pattern.type;
      const existing = map.get(key) ?? {
        type: key,
        name: alert.pattern.name,
        count: 0,
        totalCost: 0,
        latestAt: undefined,
        severities: { critical: 0, high: 0, medium: 0, low: 0 },
        worstSeverity: 'low' as PatternSeverity,
      };

      existing.count++;
      existing.totalCost += alert.pattern.estimated_cost ?? 0;
      existing.severities[alert.pattern.severity]++;

      const dt = alert.shown_at;
      if (!existing.latestAt || (dt && dt > existing.latestAt)) {
        existing.latestAt = dt;
      }

      // Track worst severity
      const idx = SEVERITY_ORDER.indexOf(alert.pattern.severity);
      if (idx < SEVERITY_ORDER.indexOf(existing.worstSeverity)) {
        existing.worstSeverity = alert.pattern.severity;
      }

      map.set(key, existing);
    }

    return Array.from(map.values()).sort((a, b) => b.count - a.count);
  }, [alerts]);

  if (summaries.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <div className="p-4 rounded-full bg-muted mb-4">
          <TrendingUp className="h-8 w-8 text-muted-foreground" />
        </div>
        <p className="text-base font-medium text-foreground">No pattern data yet</p>
        <p className="text-sm text-muted-foreground mt-1">
          Patterns will appear here as your backend engine detects behaviors.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">
        {summaries.length} distinct pattern{summaries.length !== 1 ? 's' : ''} detected in the last 48 hours
      </p>
      {summaries.map(s => {
        const cfg = SEVERITY_CONFIG[s.worstSeverity] ?? SEVERITY_CONFIG.medium;
        const Icon = cfg.icon;
        const maxCount = Math.max(...summaries.map(x => x.count));

        return (
          <Card key={s.type} className={`border ${cfg.border}`}>
            <CardContent className="pt-4 pb-4">
              <div className="flex items-start justify-between gap-3 mb-3">
                <div className="flex items-center gap-2">
                  <Icon className={`h-4 w-4 ${s.worstSeverity === 'low' ? 'text-blue-500' : s.worstSeverity === 'medium' ? 'text-yellow-500' : 'text-red-500'}`} />
                  <span className="font-semibold text-sm">{s.name}</span>
                  <Badge className={`text-xs ${cfg.badge}`}>{cfg.label}</Badge>
                </div>
                <div className="text-right flex-shrink-0">
                  <div className="text-lg font-bold text-foreground">{s.count}×</div>
                  <div className="text-xs text-muted-foreground">occurrences</div>
                </div>
              </div>

              {/* Frequency bar */}
              <div className="w-full bg-muted rounded-full h-1.5 mb-3">
                <div
                  className={`h-1.5 rounded-full transition-all ${
                    s.worstSeverity === 'critical' || s.worstSeverity === 'high'
                      ? 'bg-red-500'
                      : s.worstSeverity === 'medium'
                        ? 'bg-yellow-500'
                        : 'bg-blue-400'
                  }`}
                  style={{ width: `${Math.min((s.count / maxCount) * 100, 100)}%` }}
                />
              </div>

              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <div className="flex items-center gap-3">
                  {/* Severity breakdown dots */}
                  {(SEVERITY_ORDER as PatternSeverity[]).map(sev => s.severities[sev] > 0 && (
                    <span key={sev} className="flex items-center gap-1">
                      <span className={`w-2 h-2 rounded-full ${sev === 'critical' || sev === 'high' ? 'bg-red-500' : sev === 'medium' ? 'bg-yellow-500' : 'bg-blue-400'}`} />
                      {s.severities[sev]} {sev}
                    </span>
                  ))}
                </div>
                <div className="flex items-center gap-3">
                  {s.totalCost > 0 && (
                    <span className="text-red-500">₹{s.totalCost.toLocaleString('en-IN')}</span>
                  )}
                  {s.latestAt && (
                    <span title={formatIST(s.latestAt)}>Last: {timeAgo(s.latestAt)}</span>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------
export default function AlertsPage() {
  const { alerts, unacknowledgedCount } = useAlerts();

  const stats = useMemo(() => ({
    total: alerts.length,
    critical: alerts.filter(a => a.pattern.severity === 'critical').length,
    high: alerts.filter(a => a.pattern.severity === 'high').length,
    medium: alerts.filter(a => a.pattern.severity === 'medium').length,
    unacked: unacknowledgedCount,
  }), [alerts, unacknowledgedCount]);

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-foreground flex items-center gap-2">
            <Bell className="h-5 w-5 text-primary" />
            Behavioral Alerts
            {unacknowledgedCount > 0 && (
              <Badge className="bg-red-500 text-white text-xs px-2 py-0.5 rounded-full">
                {unacknowledgedCount}
              </Badge>
            )}
          </h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Real-time behavioral pattern detection by the backend engine
          </p>
        </div>
      </div>

      {/* Stats row */}
      {stats.total > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <StatPill label="Total (48h)" value={stats.total} color="text-foreground" />
          <StatPill label="Critical" value={stats.critical} color="text-red-700 dark:text-red-400" />
          <StatPill label="High" value={stats.high} color="text-red-500" />
          <StatPill label="Unread" value={stats.unacked} color="text-yellow-600 dark:text-yellow-400" />
        </div>
      )}

      {/* Tabs */}
      <Tabs defaultValue="live" className="w-full">
        <TabsList className="w-full sm:w-auto grid grid-cols-3 sm:inline-flex">
          <TabsTrigger value="live" className="gap-1.5">
            Live
            {unacknowledgedCount > 0 && (
              <span className="bg-red-500 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full leading-none">
                {unacknowledgedCount}
              </span>
            )}
          </TabsTrigger>
          <TabsTrigger value="history">History</TabsTrigger>
          <TabsTrigger value="patterns">Patterns</TabsTrigger>
        </TabsList>

        <TabsContent value="live" className="mt-4">
          <LiveTab />
        </TabsContent>
        <TabsContent value="history" className="mt-4">
          <HistoryTab />
        </TabsContent>
        <TabsContent value="patterns" className="mt-4">
          <PatternsTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function StatPill({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="bg-card border rounded-lg p-3 text-center">
      <div className={`text-xl font-bold ${color}`}>{value}</div>
      <div className="text-xs text-muted-foreground mt-0.5">{label}</div>
    </div>
  );
}
