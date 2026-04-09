import { useState, useEffect, useCallback } from 'react';
import { useBroker } from '@/contexts/BrokerContext';
import { useWebSocket } from '@/contexts/WebSocketContext';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Slider } from '@/components/ui/slider';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  AlertTriangle,
  Shield,
  Clock,
  TrendingDown,
  Bell,
  Settings,
  Phone,
  MessageSquare
} from 'lucide-react';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import type {
  DangerZoneStatus,
  DangerZoneSummary,
  DangerZoneThresholds,
  NotificationStats,
  CooldownRecord
} from '@/types/api';

const DANGER_LEVEL_CONFIG = {
  safe:     { barColor: 'bg-tm-profit',  textColor: 'text-tm-profit',  label: 'Safe',     icon: Shield,        border: 'border-tm-brand/20',  bg: '' },
  caution:  { barColor: 'bg-tm-obs',     textColor: 'text-tm-obs',     label: 'Caution',  icon: AlertTriangle, border: 'border-tm-obs/30',    bg: 'bg-amber-50/40 dark:bg-amber-900/10' },
  warning:  { barColor: 'bg-tm-obs',     textColor: 'text-tm-obs',     label: 'Warning',  icon: AlertTriangle, border: 'border-tm-obs/40',    bg: 'bg-amber-50/60 dark:bg-amber-900/15' },
  danger:   { barColor: 'bg-tm-loss',    textColor: 'text-tm-loss',    label: 'Danger',   icon: AlertTriangle, border: 'border-tm-loss/40',   bg: 'bg-red-50/40 dark:bg-red-900/10' },
  critical: { barColor: 'bg-tm-loss',    textColor: 'text-tm-loss',    label: 'CRITICAL', icon: AlertTriangle, border: 'border-tm-loss/60',   bg: 'bg-red-50/70 dark:bg-red-900/20' },
};

export default function DangerZone() {
  const { account } = useBroker();
  const { lastTradeEvent, lastAlertEvent } = useWebSocket();
  const [status, setStatus] = useState<DangerZoneStatus | null>(null);
  const [summary, setSummary] = useState<DangerZoneSummary | null>(null);
  const [thresholds, setThresholds] = useState<DangerZoneThresholds | null>(null);
  const [notificationStats, setNotificationStats] = useState<NotificationStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isUpdating, setIsUpdating] = useState(false);

  const [editedThresholds, setEditedThresholds] = useState({
    loss_limit_warning: 70,
    loss_limit_danger: 85,
    consecutive_loss_warning: 2,
    consecutive_loss_danger: 3,
  });

  const fetchData = useCallback(async () => {
    if (!account?.id) return;
    try {
      setIsLoading(true);
      const [statusRes, summaryRes, thresholdsRes, statsRes] = await Promise.all([
        api.get(`/api/danger-zone/status`),
        api.get(`/api/danger-zone/summary`),
        api.get(`/api/danger-zone/thresholds`),
        api.get(`/api/danger-zone/notification-stats`),
      ]);
      setStatus(statusRes.data);
      setSummary(summaryRes.data);
      setThresholds(thresholdsRes.data);
      setNotificationStats(statsRes.data);
      if (thresholdsRes.data) {
        setEditedThresholds({
          loss_limit_warning: thresholdsRes.data.loss_limits.warning_percent,
          loss_limit_danger: thresholdsRes.data.loss_limits.danger_percent,
          consecutive_loss_warning: thresholdsRes.data.consecutive_losses.warning,
          consecutive_loss_danger: thresholdsRes.data.consecutive_losses.danger,
        });
      }
    } catch (error) {
      console.error('Failed to fetch danger zone data:', error);
      toast.error('Failed to load danger zone data');
    } finally {
      setIsLoading(false);
    }
  }, [account?.id]);

  useEffect(() => { fetchData(); }, [fetchData]);

  useEffect(() => {
    if (lastTradeEvent || lastAlertEvent) fetchData();
  }, [lastTradeEvent, lastAlertEvent]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleTriggerIntervention = async () => {
    if (!account?.id) return;
    try {
      setIsUpdating(true);
      const response = await api.post(`/api/danger-zone/trigger-intervention`);
      if (response.data.notification_sent) toast.success('Push notification sent');
      if (response.data.whatsapp_sent) toast.success('WhatsApp alert sent to guardian');
      if (!response.data.notification_sent && !response.data.whatsapp_sent) {
        toast.info('Alert logged - configure guardian phone to receive WhatsApp');
      }
      fetchData();
    } catch (error) {
      console.error('Failed to trigger intervention:', error);
      toast.error('Failed to trigger intervention');
    } finally {
      setIsUpdating(false);
    }
  };

  const handleUpdateThresholds = async () => {
    try {
      setIsUpdating(true);
      await api.post(`/api/danger-zone/thresholds`, {
        loss_limit_warning_percent: editedThresholds.loss_limit_warning,
        loss_limit_danger_percent: editedThresholds.loss_limit_danger,
        consecutive_loss_warning: editedThresholds.consecutive_loss_warning,
        consecutive_loss_danger: editedThresholds.consecutive_loss_danger,
      });
      toast.success('Thresholds updated');
      fetchData();
    } catch (error) {
      console.error('Failed to update thresholds:', error);
      toast.error('Failed to update thresholds');
    } finally {
      setIsUpdating(false);
    }
  };

  const handleResetEscalation = async () => {
    try {
      setIsUpdating(true);
      await api.post(`/api/danger-zone/reset-escalation`);
      toast.success('Escalation levels reset');
      fetchData();
    } catch (error) {
      console.error('Failed to reset escalation:', error);
      toast.error('Failed to reset escalation');
    } finally {
      setIsUpdating(false);
    }
  };

  if (!account) {
    return (
      <div className="px-4 sm:px-6 py-6 max-w-4xl mx-auto">
        <div className="tm-card overflow-hidden">
          <div className="p-5 flex items-start gap-3">
            <AlertTriangle className="h-5 w-5 text-tm-obs flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-semibold text-foreground">No Account Connected</p>
              <p className="text-sm text-muted-foreground mt-0.5">
                Please connect your broker account to access the Danger Zone.
              </p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="px-4 sm:px-6 py-6 max-w-4xl mx-auto space-y-4">
        <div className="flex items-center justify-between">
          <Skeleton className="h-6 w-32" />
          <Skeleton className="h-9 w-24" />
        </div>
        <Skeleton className="h-32 w-full rounded-xl" />
        <Skeleton className="h-64 w-full rounded-xl" />
      </div>
    );
  }

  const levelConfig = status ? DANGER_LEVEL_CONFIG[status.level] : DANGER_LEVEL_CONFIG.safe;
  const LevelIcon = levelConfig.icon;

  return (
    <div className="px-4 sm:px-6 py-6 max-w-4xl mx-auto space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">Danger Zone</h1>
          <p className="text-sm text-muted-foreground">Real-time risk monitoring and intervention</p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchData} disabled={isLoading}>
          Refresh
        </Button>
      </div>

      {/* Current Status Banner */}
      {status && (
        <div className={`tm-card overflow-hidden border-2 ${levelConfig.border} ${levelConfig.bg}`}>
          <div className="p-5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className={`p-3 rounded-full ${levelConfig.barColor}`}>
                  <LevelIcon className="h-7 w-7 text-white" />
                </div>
                <div>
                  <p className={`text-xl font-bold font-mono ${levelConfig.textColor}`}>
                    {levelConfig.label}
                  </p>
                  <p className="text-sm text-muted-foreground">{status.message}</p>
                </div>
              </div>
              {status.level !== 'safe' && (
                <Button
                  size="sm"
                  className="bg-tm-loss hover:bg-tm-loss/90 text-white"
                  onClick={handleTriggerIntervention}
                  disabled={isUpdating}
                >
                  <Phone className="h-4 w-4 mr-2" />
                  Alert Guardian
                </Button>
              )}
            </div>

            {/* Quick Stats */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-5">
              <div className="text-center p-3 bg-background/60 rounded-lg">
                <div className="text-xl font-bold font-mono tabular-nums">
                  {status.daily_loss_used_percent.toFixed(0)}%
                </div>
                <div className="text-xs text-muted-foreground mt-1">Daily Loss Used</div>
                <div className="h-1.5 bg-muted rounded-full overflow-hidden mt-2">
                  <div
                    className={`h-full rounded-full transition-all ${levelConfig.barColor}`}
                    style={{ width: `${Math.min(status.daily_loss_used_percent, 100)}%` }}
                  />
                </div>
              </div>
              <div className="text-center p-3 bg-background/60 rounded-lg">
                <div className="text-xl font-bold font-mono tabular-nums">{status.trade_count_today}</div>
                <div className="text-xs text-muted-foreground mt-1">Trades Today</div>
              </div>
              <div className="text-center p-3 bg-background/60 rounded-lg">
                <div className="text-xl font-bold font-mono tabular-nums text-tm-loss">
                  {status.consecutive_losses}
                </div>
                <div className="text-xs text-muted-foreground mt-1">Consecutive Losses</div>
              </div>
              <div className="text-center p-3 bg-background/60 rounded-lg">
                <div className="text-xl font-bold font-mono tabular-nums">{status.patterns_active.length}</div>
                <div className="text-xs text-muted-foreground mt-1">Active Patterns</div>
              </div>
            </div>

            {/* Active Triggers */}
            {status.triggers.length > 0 && (
              <div className="mt-4 flex flex-wrap gap-2">
                {status.triggers.map((trigger, i) => (
                  <span
                    key={i}
                    className="text-[11px] font-medium px-2 py-0.5 rounded-full border border-border bg-background/60 text-muted-foreground"
                  >
                    {trigger.replace(/_/g, ' ')}
                  </span>
                ))}
              </div>
            )}

            {/* Recommendations */}
            {status.recommendations.length > 0 && (
              <div className="mt-4 p-3 bg-background/60 rounded-lg">
                <p className="text-xs font-semibold mb-2 text-foreground">Recommendations</p>
                <ul className="space-y-1">
                  {status.recommendations.map((rec, i) => (
                    <li key={i} className="text-sm text-muted-foreground">• {rec}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tabs */}
      <Tabs defaultValue="settings">
        <TabsList className="w-full justify-start rounded-none border-b border-border bg-transparent p-0 h-auto gap-0">
          {[
            { value: 'settings',      label: 'Thresholds',     Icon: Settings    },
            { value: 'history',       label: 'Alert History',  Icon: Clock       },
            { value: 'notifications', label: 'Notifications',  Icon: Bell        },
            { value: 'whatsapp',      label: 'WhatsApp',       Icon: MessageSquare },
          ].map(({ value, label, Icon }) => (
            <TabsTrigger
              key={value}
              value={value}
              className="rounded-none border-b-2 border-transparent data-[state=active]:border-tm-brand data-[state=active]:text-tm-brand bg-transparent px-4 pb-2 pt-0 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
            >
              <Icon className="h-3.5 w-3.5 mr-1.5" />
              {label}
            </TabsTrigger>
          ))}
        </TabsList>

        {/* Thresholds Tab */}
        <TabsContent value="settings" className="mt-4">
          <div className="tm-card overflow-hidden">
            <div className="px-5 py-4 border-b border-border">
              <p className="text-sm font-semibold text-foreground">Danger Zone Thresholds</p>
              <p className="text-xs text-muted-foreground mt-0.5">Configure when different danger levels are triggered</p>
            </div>
            <div className="p-5 space-y-6">
              {/* Loss Limit Thresholds */}
              <div className="space-y-4">
                <p className="text-sm font-semibold flex items-center gap-2">
                  <TrendingDown className="h-4 w-4 text-muted-foreground" />
                  Daily Loss Limit Thresholds
                </p>
                <div className="grid gap-4">
                  <div className="space-y-2">
                    <div className="flex justify-between items-center">
                      <Label className="text-sm">Warning Level: {editedThresholds.loss_limit_warning}%</Label>
                      <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-amber-50 dark:bg-amber-900/20 text-tm-obs border border-tm-obs/20">
                        Yellow Alert
                      </span>
                    </div>
                    <Slider
                      value={[editedThresholds.loss_limit_warning]}
                      onValueChange={([v]) => setEditedThresholds(prev => ({ ...prev, loss_limit_warning: v }))}
                      min={50} max={90} step={5}
                    />
                  </div>
                  <div className="space-y-2">
                    <div className="flex justify-between items-center">
                      <Label className="text-sm">Danger Level: {editedThresholds.loss_limit_danger}%</Label>
                      <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-red-50 dark:bg-red-900/20 text-tm-loss border border-tm-loss/20">
                        Red Alert
                      </span>
                    </div>
                    <Slider
                      value={[editedThresholds.loss_limit_danger]}
                      onValueChange={([v]) => setEditedThresholds(prev => ({ ...prev, loss_limit_danger: v }))}
                      min={70} max={100} step={5}
                    />
                  </div>
                </div>
              </div>

              {/* Consecutive Loss Thresholds */}
              <div className="space-y-4">
                <p className="text-sm font-semibold flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4 text-muted-foreground" />
                  Consecutive Loss Thresholds
                </p>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label className="text-sm">Warning after losses: {editedThresholds.consecutive_loss_warning}</Label>
                    <Slider
                      value={[editedThresholds.consecutive_loss_warning]}
                      onValueChange={([v]) => setEditedThresholds(prev => ({ ...prev, consecutive_loss_warning: v }))}
                      min={1} max={5} step={1}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-sm">Danger after losses: {editedThresholds.consecutive_loss_danger}</Label>
                    <Slider
                      value={[editedThresholds.consecutive_loss_danger]}
                      onValueChange={([v]) => setEditedThresholds(prev => ({ ...prev, consecutive_loss_danger: v }))}
                      min={2} max={7} step={1}
                    />
                  </div>
                </div>
              </div>

              <div className="flex gap-2 pt-2">
                <Button
                  size="sm"
                  className="bg-tm-brand hover:bg-tm-brand/90 text-white"
                  onClick={handleUpdateThresholds}
                  disabled={isUpdating}
                >
                  Save Thresholds
                </Button>
                <Button variant="outline" size="sm" onClick={handleResetEscalation} disabled={isUpdating}>
                  Reset Escalation Levels
                </Button>
              </div>
            </div>
          </div>
        </TabsContent>

        {/* Alert History Tab */}
        <TabsContent value="history" className="mt-4">
          <div className="tm-card overflow-hidden">
            <div className="px-5 py-4 border-b border-border">
              <p className="text-sm font-semibold text-foreground">Alert History</p>
              <p className="text-xs text-muted-foreground mt-0.5">Recent risk alerts and interventions</p>
            </div>
            <div className="p-5">
              {summary?.cooldown_history_7d && summary.cooldown_history_7d.length > 0 ? (
                <div className="space-y-3">
                  {summary.cooldown_history_7d.map((alert: CooldownRecord, i: number) => (
                    <div key={i} className="flex items-center justify-between p-3 border border-border rounded-lg">
                      <div>
                        <p className="text-sm font-medium capitalize">
                          {alert.reason.replace(/_/g, ' ')}
                        </p>
                        <p className="text-xs text-muted-foreground mt-0.5">
                          {new Date(alert.started_at).toLocaleString()}
                        </p>
                      </div>
                      <span className="text-[11px] font-medium px-2 py-0.5 rounded-full border border-border text-muted-foreground">
                        Alert Sent
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-10 text-muted-foreground">
                  <Shield className="h-8 w-8 mx-auto mb-2 text-muted-foreground/40" />
                  <p className="text-sm">No alerts in the last 7 days</p>
                  <p className="text-xs text-muted-foreground/70 mt-0.5">Keep trading disciplined!</p>
                </div>
              )}
            </div>
          </div>
        </TabsContent>

        {/* Notifications Tab */}
        <TabsContent value="notifications" className="mt-4">
          <div className="tm-card overflow-hidden">
            <div className="px-5 py-4 border-b border-border">
              <p className="text-sm font-semibold text-foreground">Notification Statistics</p>
              <p className="text-xs text-muted-foreground mt-0.5">Usage in the last 24 hours</p>
            </div>
            <div className="p-5">
              {notificationStats ? (
                <div className="space-y-5">
                  <div className="text-center p-4 bg-muted/50 rounded-lg">
                    <div className="text-4xl font-bold font-mono tabular-nums">
                      {notificationStats.total_24h}
                    </div>
                    <div className="text-sm text-muted-foreground mt-1">Total Notifications (24h)</div>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    {Object.entries(notificationStats.by_tier).map(([tier, stats]) => (
                      <div key={tier} className="p-4 border border-border rounded-lg">
                        <p className="text-sm font-semibold capitalize mb-2">{tier}</p>
                        <div className="grid grid-cols-2 gap-2 text-xs mb-2">
                          <div>
                            <span className="text-muted-foreground">Hourly: </span>
                            <span className="font-mono">{stats.hourly}/{stats.hourly_limit}</span>
                          </div>
                          <div>
                            <span className="text-muted-foreground">Daily: </span>
                            <span className="font-mono">{stats.daily}/{stats.daily_limit}</span>
                          </div>
                        </div>
                        <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                          <div
                            className="h-full bg-tm-brand rounded-full transition-all"
                            style={{ width: `${Math.min((stats.daily / stats.daily_limit) * 100, 100)}%` }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                  {Object.keys(notificationStats.by_type).length > 0 && (
                    <div>
                      <p className="text-sm font-semibold mb-2">By Type</p>
                      <div className="flex flex-wrap gap-2">
                        {Object.entries(notificationStats.by_type).map(([type, count]) => (
                          <span
                            key={type}
                            className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-muted text-muted-foreground"
                          >
                            {type.replace(/_/g, ' ')}: {count as number}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-center py-10 text-muted-foreground">
                  <Bell className="h-8 w-8 mx-auto mb-2 text-muted-foreground/40" />
                  <p className="text-sm">No notification data available</p>
                </div>
              )}
            </div>
          </div>
        </TabsContent>

        {/* WhatsApp Tab */}
        <TabsContent value="whatsapp" className="mt-4">
          <div className="tm-card overflow-hidden">
            <div className="px-5 py-4 border-b border-border">
              <p className="text-sm font-semibold text-foreground flex items-center gap-1.5">
                <Phone className="h-4 w-4 text-muted-foreground" />
                WhatsApp Alerts
              </p>
              <p className="text-xs text-muted-foreground mt-0.5">
                Configure WhatsApp notifications for critical alerts
              </p>
            </div>
            <div className="p-5 space-y-4">
              {/* Info banner */}
              <div className="flex items-start gap-3 p-3 rounded-lg bg-teal-50/60 dark:bg-teal-900/15 border border-tm-brand/20">
                <MessageSquare className="h-4 w-4 text-tm-brand flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-xs font-semibold text-tm-brand">WhatsApp Integration Active</p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Critical alerts will be sent to your registered guardian phone number.
                    Configure your guardian in Profile settings.
                  </p>
                </div>
              </div>

              <div className="space-y-3">
                {[
                  { label: 'Loss Limit Breach', desc: 'Immediate WhatsApp when daily loss limit is hit', default: true },
                  { label: 'Critical Pattern Detection', desc: 'Alert when revenge trading or tilt is detected', default: true },
                  { label: 'Consecutive Loss Alert', desc: 'Notify when consecutive losses exceed threshold', default: true },
                  { label: 'Daily Summary', desc: 'End-of-day trading summary via WhatsApp', default: false },
                ].map((item) => (
                  <div key={item.label} className="flex items-center justify-between p-3 border border-border rounded-lg">
                    <div>
                      <p className="text-sm font-medium">{item.label}</p>
                      <p className="text-xs text-muted-foreground mt-0.5">{item.desc}</p>
                    </div>
                    <Switch defaultChecked={item.default} />
                  </div>
                ))}
              </div>

              <Button variant="outline" size="sm" className="w-full">
                <Phone className="h-4 w-4 mr-2" />
                Send Test WhatsApp Message
              </Button>
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
