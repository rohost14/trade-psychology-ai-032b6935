import { useState, useEffect, useCallback } from 'react';
import { useBroker } from '@/contexts/BrokerContext';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Slider } from '@/components/ui/slider';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import {
  AlertTriangle,
  Shield,
  Clock,
  TrendingDown,
  Bell,
  Settings,
  RefreshCw,
  Phone,
  MessageSquare
} from 'lucide-react';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import type {
  DangerZoneStatus,
  DangerZoneSummary,
  DangerZoneThresholds,
  EscalationStatus,
  NotificationStats,
  CooldownRecord
} from '@/types/api';

const DANGER_LEVEL_CONFIG = {
  safe: { color: 'bg-green-500', textColor: 'text-green-600', label: 'Safe', icon: Shield },
  caution: { color: 'bg-yellow-500', textColor: 'text-yellow-600', label: 'Caution', icon: AlertTriangle },
  warning: { color: 'bg-orange-500', textColor: 'text-orange-600', label: 'Warning', icon: AlertTriangle },
  danger: { color: 'bg-red-500', textColor: 'text-red-600', label: 'Danger', icon: AlertTriangle },
  critical: { color: 'bg-red-700', textColor: 'text-red-700', label: 'CRITICAL', icon: AlertTriangle },
};

export default function DangerZone() {
  const { account } = useBroker();
  const [status, setStatus] = useState<DangerZoneStatus | null>(null);
  const [summary, setSummary] = useState<DangerZoneSummary | null>(null);
  const [thresholds, setThresholds] = useState<DangerZoneThresholds | null>(null);
  const [notificationStats, setNotificationStats] = useState<NotificationStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isUpdating, setIsUpdating] = useState(false);

  // Editable thresholds
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

      // Fetch all data in parallel
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

      // Initialize editable thresholds
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

  useEffect(() => {
    fetchData();
    // Refresh every 30 seconds
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const handleTriggerIntervention = async () => {
    if (!account?.id) return;

    try {
      setIsUpdating(true);
      const response = await api.post(`/api/danger-zone/trigger-intervention`);

      if (response.data.notification_sent) {
        toast.success('Push notification sent');
      }
      if (response.data.whatsapp_sent) {
        toast.success('WhatsApp alert sent to guardian');
      }
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
      <div className="container mx-auto p-6">
        <Alert>
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>No Account Connected</AlertTitle>
          <AlertDescription>
            Please connect your broker account to access the Danger Zone.
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="container mx-auto p-6 flex items-center justify-center min-h-[400px]">
        <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const levelConfig = status ? DANGER_LEVEL_CONFIG[status.level] : DANGER_LEVEL_CONFIG.safe;
  const LevelIcon = levelConfig.icon;

  return (
    <div className="container mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Danger Zone</h1>
          <p className="text-muted-foreground">
            Real-time risk monitoring and intervention system
          </p>
        </div>
        <Button variant="outline" onClick={fetchData} disabled={isLoading}>
          <RefreshCw className={`h-4 w-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      {/* Current Status Banner */}
      {status && (
        <Card className={`border-2 ${status.level === 'critical' ? 'border-red-500 bg-red-50 dark:bg-red-950' :
          status.level === 'danger' ? 'border-red-400 bg-red-50/50 dark:bg-red-950/50' :
            status.level === 'warning' ? 'border-orange-400 bg-orange-50/50 dark:bg-orange-950/50' :
              ''}`}>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className={`p-3 rounded-full ${levelConfig.color}`}>
                  <LevelIcon className="h-8 w-8 text-white" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className={`text-2xl font-bold ${levelConfig.textColor}`}>
                      {levelConfig.label}
                    </h2>
                  </div>
                  <p className="text-muted-foreground">{status.message}</p>
                </div>
              </div>

              {status.level !== 'safe' && (
                <Button
                  variant="destructive"
                  onClick={handleTriggerIntervention}
                  disabled={isUpdating}
                >
                  <Phone className="h-4 w-4 mr-2" />
                  Alert Guardian
                </Button>
              )}
            </div>

            {/* Quick Stats */}
            <div className="grid grid-cols-4 gap-4 mt-6">
              <div className="text-center p-3 bg-background rounded-lg">
                <div className="text-2xl font-bold">{status.daily_loss_used_percent.toFixed(0)}%</div>
                <div className="text-sm text-muted-foreground">Daily Loss Used</div>
                <Progress value={status.daily_loss_used_percent} className="mt-2" />
              </div>
              <div className="text-center p-3 bg-background rounded-lg">
                <div className="text-2xl font-bold">{status.trade_count_today}</div>
                <div className="text-sm text-muted-foreground">Trades Today</div>
              </div>
              <div className="text-center p-3 bg-background rounded-lg">
                <div className="text-2xl font-bold text-red-500">{status.consecutive_losses}</div>
                <div className="text-sm text-muted-foreground">Consecutive Losses</div>
              </div>
              <div className="text-center p-3 bg-background rounded-lg">
                <div className="text-2xl font-bold">{status.patterns_active.length}</div>
                <div className="text-sm text-muted-foreground">Active Patterns</div>
              </div>
            </div>

            {/* Active Triggers */}
            {status.triggers.length > 0 && (
              <div className="mt-4 flex flex-wrap gap-2">
                {status.triggers.map((trigger, i) => (
                  <Badge key={i} variant="outline" className="bg-background">
                    {trigger.replace(/_/g, ' ')}
                  </Badge>
                ))}
              </div>
            )}

            {/* Recommendations */}
            {status.recommendations.length > 0 && (
              <div className="mt-4 p-3 bg-background rounded-lg">
                <h4 className="font-semibold mb-2">Recommendations</h4>
                <ul className="space-y-1">
                  {status.recommendations.map((rec, i) => (
                    <li key={i} className="text-sm text-muted-foreground">• {rec}</li>
                  ))}
                </ul>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Tabs for different sections */}
      <Tabs defaultValue="settings">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="settings">
            <Settings className="h-4 w-4 mr-2" />
            Thresholds
          </TabsTrigger>
          <TabsTrigger value="history">
            <Clock className="h-4 w-4 mr-2" />
            Alert History
          </TabsTrigger>
          <TabsTrigger value="notifications">
            <Bell className="h-4 w-4 mr-2" />
            Notifications
          </TabsTrigger>
          <TabsTrigger value="whatsapp">
            <MessageSquare className="h-4 w-4 mr-2" />
            WhatsApp
          </TabsTrigger>
        </TabsList>

        {/* Thresholds Tab */}
        <TabsContent value="settings" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Danger Zone Thresholds</CardTitle>
              <CardDescription>
                Configure when different danger levels are triggered
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Loss Limit Thresholds */}
              <div className="space-y-4">
                <h4 className="font-semibold flex items-center gap-2">
                  <TrendingDown className="h-4 w-4" />
                  Daily Loss Limit Thresholds
                </h4>

                <div className="grid gap-4">
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <Label>Warning Level: {editedThresholds.loss_limit_warning}%</Label>
                      <Badge variant="outline" className="bg-yellow-100">Yellow Alert</Badge>
                    </div>
                    <Slider
                      value={[editedThresholds.loss_limit_warning]}
                      onValueChange={([v]) => setEditedThresholds(prev => ({ ...prev, loss_limit_warning: v }))}
                      min={50}
                      max={90}
                      step={5}
                    />
                  </div>

                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <Label>Danger Level: {editedThresholds.loss_limit_danger}%</Label>
                      <Badge variant="outline" className="bg-red-100">Red Alert</Badge>
                    </div>
                    <Slider
                      value={[editedThresholds.loss_limit_danger]}
                      onValueChange={([v]) => setEditedThresholds(prev => ({ ...prev, loss_limit_danger: v }))}
                      min={70}
                      max={100}
                      step={5}
                    />
                  </div>
                </div>
              </div>

              {/* Consecutive Loss Thresholds */}
              <div className="space-y-4">
                <h4 className="font-semibold flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4" />
                  Consecutive Loss Thresholds
                </h4>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Warning after losses: {editedThresholds.consecutive_loss_warning}</Label>
                    <Slider
                      value={[editedThresholds.consecutive_loss_warning]}
                      onValueChange={([v]) => setEditedThresholds(prev => ({ ...prev, consecutive_loss_warning: v }))}
                      min={1}
                      max={5}
                      step={1}
                    />
                  </div>

                  <div className="space-y-2">
                    <Label>Danger after losses: {editedThresholds.consecutive_loss_danger}</Label>
                    <Slider
                      value={[editedThresholds.consecutive_loss_danger]}
                      onValueChange={([v]) => setEditedThresholds(prev => ({ ...prev, consecutive_loss_danger: v }))}
                      min={2}
                      max={7}
                      step={1}
                    />
                  </div>
                </div>
              </div>

              <div className="flex gap-2">
                <Button onClick={handleUpdateThresholds} disabled={isUpdating}>
                  Save Thresholds
                </Button>
                <Button variant="outline" onClick={handleResetEscalation} disabled={isUpdating}>
                  Reset Escalation Levels
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Alert History Tab */}
        <TabsContent value="history">
          <Card>
            <CardHeader>
              <CardTitle>Alert History</CardTitle>
              <CardDescription>
                Recent risk alerts and interventions triggered
              </CardDescription>
            </CardHeader>
            <CardContent>
              {summary?.cooldown_history_7d && summary.cooldown_history_7d.length > 0 ? (
                <div className="space-y-3">
                  {summary.cooldown_history_7d.map((alert: CooldownRecord, i: number) => (
                    <div key={i} className="flex items-center justify-between p-3 border rounded-lg">
                      <div>
                        <div className="font-medium capitalize">
                          {alert.reason.replace(/_/g, ' ')}
                        </div>
                        <div className="text-sm text-muted-foreground">
                          {new Date(alert.started_at).toLocaleString()}
                        </div>
                      </div>
                      <Badge variant="outline">Alert Sent</Badge>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  No alerts in the last 7 days - keep trading disciplined!
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Notifications Tab */}
        <TabsContent value="notifications">
          <Card>
            <CardHeader>
              <CardTitle>Notification Statistics</CardTitle>
              <CardDescription>
                Notification usage in the last 24 hours
              </CardDescription>
            </CardHeader>
            <CardContent>
              {notificationStats ? (
                <div className="space-y-6">
                  <div className="text-center p-4 bg-muted rounded-lg">
                    <div className="text-4xl font-bold">{notificationStats.total_24h}</div>
                    <div className="text-muted-foreground">Total Notifications (24h)</div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    {Object.entries(notificationStats.by_tier).map(([tier, stats]) => (
                      <div key={tier} className="p-4 border rounded-lg">
                        <div className="font-semibold capitalize mb-2">{tier}</div>
                        <div className="grid grid-cols-2 gap-2 text-sm">
                          <div>
                            <span className="text-muted-foreground">Hourly: </span>
                            {stats.hourly}/{stats.hourly_limit}
                          </div>
                          <div>
                            <span className="text-muted-foreground">Daily: </span>
                            {stats.daily}/{stats.daily_limit}
                          </div>
                        </div>
                        <Progress
                          value={(stats.daily / stats.daily_limit) * 100}
                          className="mt-2"
                        />
                      </div>
                    ))}
                  </div>

                  {Object.keys(notificationStats.by_type).length > 0 && (
                    <div>
                      <h4 className="font-semibold mb-2">By Type</h4>
                      <div className="flex flex-wrap gap-2">
                        {Object.entries(notificationStats.by_type).map(([type, count]) => (
                          <Badge key={type} variant="secondary">
                            {type.replace(/_/g, ' ')}: {count}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  No notification data available
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* WhatsApp Tab */}
        <TabsContent value="whatsapp">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Phone className="h-5 w-5" />
                WhatsApp Alerts
              </CardTitle>
              <CardDescription>
                Configure WhatsApp notifications for critical alerts
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Alert>
                <MessageSquare className="h-4 w-4" />
                <AlertTitle>WhatsApp Integration Active</AlertTitle>
                <AlertDescription>
                  Critical alerts will be sent to your registered guardian phone number.
                  Configure your guardian in the Profile settings.
                </AlertDescription>
              </Alert>

              <div className="space-y-4">
                <div className="flex items-center justify-between p-4 border rounded-lg">
                  <div>
                    <div className="font-medium">Loss Limit Breach</div>
                    <div className="text-sm text-muted-foreground">
                      Immediate WhatsApp when daily loss limit is hit
                    </div>
                  </div>
                  <Switch defaultChecked />
                </div>

                <div className="flex items-center justify-between p-4 border rounded-lg">
                  <div>
                    <div className="font-medium">Critical Pattern Detection</div>
                    <div className="text-sm text-muted-foreground">
                      Alert when revenge trading or tilt is detected
                    </div>
                  </div>
                  <Switch defaultChecked />
                </div>

                <div className="flex items-center justify-between p-4 border rounded-lg">
                  <div>
                    <div className="font-medium">Consecutive Loss Alert</div>
                    <div className="text-sm text-muted-foreground">
                      Notify when consecutive losses exceed threshold
                    </div>
                  </div>
                  <Switch defaultChecked />
                </div>

                <div className="flex items-center justify-between p-4 border rounded-lg">
                  <div>
                    <div className="font-medium">Daily Summary</div>
                    <div className="text-sm text-muted-foreground">
                      End-of-day trading summary via WhatsApp
                    </div>
                  </div>
                  <Switch />
                </div>
              </div>

              <Button variant="outline" className="w-full">
                <Phone className="h-4 w-4 mr-2" />
                Send Test WhatsApp Message
              </Button>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
