import { useState, useEffect, useCallback } from 'react';
import {
  Link2,
  Link2Off,
  Shield,
  AlertTriangle,
  RefreshCw,
  Loader2,
  User,
  Phone,
  Brain,
  Save,
  Bell,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useBroker } from '@/contexts/BrokerContext';
import { toast } from 'sonner';
import NotificationSettings from '@/components/settings/NotificationSettings';
import { api } from '@/lib/api';

interface UserProfile {
  display_name?: string;
  trading_since?: number;
  experience_level?: string;
  trading_style?: string;
  risk_tolerance?: string;
  preferred_instruments?: string[];
  trading_hours_start?: string;
  trading_hours_end?: string;
  daily_loss_limit?: number;
  daily_trade_limit?: number;
  max_position_size?: number;     // % of capital per trade (e.g., 10 = 10%)
  cooldown_after_loss?: number;   // minutes
  trading_capital?: number;       // Rs capital deployed for trading
  sl_percent_futures?: number;    // typical SL % of notional for futures
  sl_percent_options?: number;    // % of premium to exit losing options
  known_weaknesses?: string[];
  push_enabled?: boolean;
  whatsapp_enabled?: boolean;
  email_enabled?: boolean;
  alert_sensitivity?: string;
  guardian_enabled?: boolean;
  guardian_phone?: string;
  guardian_alert_threshold?: string;
  guardian_daily_summary?: boolean;
  eod_report_time?: string;       // HH:MM IST, default '16:00'
  morning_brief_time?: string;    // HH:MM IST, default '08:30'
  ai_persona?: string;
  onboarding_completed?: boolean;
}

interface NotificationStatus {
  whatsapp: { twilio_configured: boolean };
  push: { vapid_configured: boolean };
}

const EXPERIENCE_LEVELS = [
  { value: 'beginner', label: 'Beginner (< 1 year)' },
  { value: 'intermediate', label: 'Intermediate (1-3 years)' },
  { value: 'experienced', label: 'Experienced (3-5 years)' },
  { value: 'professional', label: 'Professional (5+ years)' },
];


const RISK_TOLERANCE = [
  { value: 'conservative', label: 'Conservative', description: 'Preserve capital, small positions' },
  { value: 'moderate', label: 'Moderate', description: 'Balanced risk/reward' },
  { value: 'aggressive', label: 'Aggressive', description: 'Higher risk for higher returns' },
];

const AI_PERSONAS = [
  { value: 'coach', label: 'Coach', description: 'Supportive, encouraging, process-focused' },
  { value: 'mentor', label: 'Mentor', description: 'Experienced guide, shares wisdom' },
  { value: 'friend', label: 'Friend', description: 'Casual, relatable, empathetic' },
  { value: 'strict', label: 'Strict', description: 'No-nonsense, direct, disciplined' },
];

const ALERT_SENSITIVITY = [
  { value: 'low', label: 'Low', description: 'Only critical alerts' },
  { value: 'medium', label: 'Medium', description: 'Important patterns' },
  { value: 'high', label: 'High', description: 'All detected patterns' },
];

export default function Settings() {
  const { isConnected, isLoading: brokerLoading, account, connect, disconnect, syncTrades } = useBroker();
  const [isConnecting, setIsConnecting] = useState(false);
  const [isDisconnecting, setIsDisconnecting] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isLoadingProfile, setIsLoadingProfile] = useState(false);
  const [notificationStatus, setNotificationStatus] = useState<NotificationStatus | null>(null);

  // Profile state
  const [profile, setProfile] = useState<UserProfile>({
    experience_level: 'intermediate',
    trading_style: 'intraday',
    risk_tolerance: 'moderate',
    daily_loss_limit: undefined,
    daily_trade_limit: undefined,
    max_position_size: 10,
    cooldown_after_loss: 15,
    trading_capital: undefined,
    sl_percent_futures: 1.0,
    sl_percent_options: 50.0,
    trading_hours_start: '09:15',
    trading_hours_end: '15:30',
    push_enabled: true,
    whatsapp_enabled: false,
    alert_sensitivity: 'medium',
    guardian_enabled: false,
    ai_persona: 'coach',
    eod_report_time: '16:00',
    morning_brief_time: '08:30',
  });

  // Fetch profile from backend
  const fetchProfile = useCallback(async () => {
    if (!account?.id) return;

    setIsLoadingProfile(true);
    try {
      const response = await api.get('/api/profile/');
      if (response.data?.profile) {
        setProfile(prev => ({ ...prev, ...response.data.profile }));
      }
    } catch (error) {
      console.error('Failed to fetch profile:', error);
    } finally {
      setIsLoadingProfile(false);
    }
  }, [account?.id]);

  // Fetch notification channel status
  const fetchNotificationStatus = useCallback(async () => {
    if (!account?.id) return;
    try {
      const response = await api.get('/api/profile/notification-status');
      setNotificationStatus(response.data);
    } catch {
      // Endpoint may not exist yet — silently ignore
    }
  }, [account?.id]);

  useEffect(() => {
    if (isConnected && account?.id) {
      fetchProfile();
      fetchNotificationStatus();
    }
  }, [isConnected, account?.id, fetchProfile, fetchNotificationStatus]);

  const handleSaveProfile = async () => {
    if (!account?.id) return;

    setIsSaving(true);
    try {
      const payload = {
        display_name: profile.display_name,
        trading_since: profile.trading_since,
        experience_level: profile.experience_level,
        trading_style: profile.trading_style,
        risk_tolerance: profile.risk_tolerance,
        preferred_instruments: profile.preferred_instruments,
        trading_hours_start: profile.trading_hours_start,
        trading_hours_end: profile.trading_hours_end,
        daily_loss_limit: profile.daily_loss_limit,
        daily_trade_limit: profile.daily_trade_limit,
        max_position_size: profile.max_position_size,
        cooldown_after_loss: profile.cooldown_after_loss,
        trading_capital: profile.trading_capital,
        sl_percent_futures: profile.sl_percent_futures,
        sl_percent_options: profile.sl_percent_options,
        known_weaknesses: profile.known_weaknesses,
        push_enabled: profile.push_enabled,
        whatsapp_enabled: profile.whatsapp_enabled,
        alert_sensitivity: profile.alert_sensitivity,
        guardian_enabled: profile.guardian_enabled,
        guardian_phone: profile.guardian_phone,
        guardian_alert_threshold: profile.guardian_alert_threshold,
        guardian_daily_summary: profile.guardian_daily_summary,
        eod_report_time: profile.eod_report_time || '16:00',
        morning_brief_time: profile.morning_brief_time || '08:30',
        ai_persona: profile.ai_persona,
      };

      await api.put('/api/profile/', payload);
      toast.success('Settings saved successfully');
    } catch (error) {
      console.error('Failed to save profile:', error);
      toast.error('Failed to save settings');
    } finally {
      setIsSaving(false);
    }
  };

  const handleConnect = async () => {
    setIsConnecting(true);
    try {
      await connect();
    } catch (error) {
      toast.error('Failed to connect to Zerodha');
      setIsConnecting(false);
    }
  };

  const handleDisconnect = async () => {
    setIsDisconnecting(true);
    try {
      await disconnect();
      toast.success('Disconnected from Zerodha');
    } catch (error) {
      toast.error('Failed to disconnect');
    } finally {
      setIsDisconnecting(false);
    }
  };

  const handleSync = async () => {
    setIsSyncing(true);
    try {
      const result = await syncTrades();
      if (result) {
        toast.success(`Synced ${result.trades_synced} trades, ${result.positions_synced} positions`);
      }
    } catch (error) {
      toast.error('Failed to sync trades');
    } finally {
      setIsSyncing(false);
    }
  };

  const handleTestGuardian = async () => {
    if (!profile.guardian_phone) {
      toast.error('Please enter guardian phone number first');
      return;
    }
    try {
      const response = await api.post('/api/profile/guardian/test');
      const results = response.data?.results || {};
      const guardianStatus = results.guardian_whatsapp;
      const pushStatus = results.user_push;

      if (guardianStatus === 'sent' || (pushStatus && pushStatus.startsWith('sent to'))) {
        const parts = [];
        if (guardianStatus === 'sent') parts.push('WhatsApp to guardian ✅');
        if (pushStatus && pushStatus.startsWith('sent to')) parts.push(`Push notification ${pushStatus} ✅`);
        toast.success(`Sent: ${parts.join(' | ')}\nAnalytics report included.`);
      } else {
        toast.info(`Test dispatched. Guardian: ${guardianStatus ?? 'n/a'} | Push: ${pushStatus ?? 'n/a'}`);
      }
    } catch (error: any) {
      if (error?.response?.status === 503) {
        toast.error('WhatsApp not configured — Twilio credentials missing on server');
      } else {
        toast.error('Failed to send test message');
      }
    }
  };

  const formatLastSync = (dateStr: string | null) => {
    if (!dateStr) return 'Never';
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins} min ago`;
    if (diffMins < 1440) return `${Math.floor(diffMins / 60)} hours ago`;
    return date.toLocaleDateString();
  };

  if (brokerLoading) {
    return (
      <div className="max-w-4xl mx-auto flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Settings</h1>
          <p className="text-sm text-muted-foreground">
            Manage your broker, profile, and preferences
          </p>
        </div>
        {isConnected && (
          <Button onClick={handleSaveProfile} disabled={isSaving}>
            {isSaving ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <Save className="h-4 w-4 mr-2" />
            )}
            Save All Settings
          </Button>
        )}
      </div>

      {/* Broker Connection Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Link2 className="h-5 w-5" />
            Broker Connection
          </CardTitle>
          <CardDescription>Connect your Zerodha account</CardDescription>
        </CardHeader>
        <CardContent>
          {isConnected && account ? (
            <div className="space-y-4">
              <div className="flex items-center justify-between p-4 bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800 rounded-lg">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-full bg-success/10">
                    <Shield className="h-5 w-5 text-success" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-emerald-700 dark:text-emerald-300">Connected to Zerodha</p>
                    {account.sync_status === 'syncing' ? (
                      <p className="text-xs text-amber-600 dark:text-amber-400 flex items-center gap-1">
                        <span className="inline-block h-2 w-2 rounded-full bg-amber-400 animate-pulse" />
                        Loading your trading data…
                      </p>
                    ) : (
                      <p className="text-xs text-emerald-600 dark:text-emerald-400">
                        Last synced: {formatLastSync(account.last_sync_at)}
                      </p>
                    )}
                  </div>
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={handleSync} disabled={isSyncing}>
                    <RefreshCw className={`h-4 w-4 mr-1.5 ${isSyncing ? 'animate-spin' : ''}`} />
                    {isSyncing ? 'Syncing...' : 'Sync'}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleDisconnect}
                    disabled={isDisconnecting}
                    className="text-destructive hover:text-destructive"
                  >
                    <Link2Off className="h-4 w-4 mr-1.5" />
                    Disconnect
                  </Button>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="p-4 bg-muted/50 rounded-lg">
                  <p className="text-xs text-muted-foreground mb-1">Broker</p>
                  <p className="text-sm font-medium">Zerodha (Kite)</p>
                </div>
                <div className="p-4 bg-muted/50 rounded-lg">
                  <p className="text-xs text-muted-foreground mb-1">Account ID</p>
                  <p className="text-sm font-mono">{account.broker_user_id || 'Unknown'}</p>
                </div>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="flex items-center justify-between p-4 bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 rounded-lg">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-full bg-warning/10">
                    <AlertTriangle className="h-5 w-5 text-warning" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-amber-700 dark:text-amber-300">Not Connected</p>
                    <p className="text-xs text-amber-600 dark:text-amber-400">Connect your broker to start monitoring</p>
                  </div>
                </div>
              </div>

              <Button onClick={handleConnect} disabled={isConnecting} className="w-full">
                {isConnecting ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <Link2 className="h-4 w-4 mr-2" />
                )}
                Connect Zerodha Account
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Only show other settings if connected */}
      {isConnected && (
        <Tabs defaultValue="profile" className="space-y-4">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="profile">
              <User className="h-4 w-4 mr-2" />
              Profile
            </TabsTrigger>
            <TabsTrigger value="notifications">
              <Bell className="h-4 w-4 mr-2" />
              Notifications
            </TabsTrigger>
          </TabsList>

          {/* ===== Profile Tab ===== */}
          <TabsContent value="profile">
            <div className="space-y-6">
              {/* Basic Info */}
              <Card>
                <CardHeader>
                  <CardTitle>Trading Profile</CardTitle>
                  <CardDescription>Tell us about your trading style and experience</CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  {/* Display Name */}
                  <div className="space-y-2">
                    <Label>Display Name</Label>
                    <Input
                      placeholder="Your name"
                      value={profile.display_name || ''}
                      onChange={(e) => setProfile({ ...profile, display_name: e.target.value })}
                    />
                  </div>

                  {/* Experience Level */}
                  <div className="space-y-2">
                    <Label>Experience Level</Label>
                    <Select
                      value={profile.experience_level}
                      onValueChange={(value) => setProfile({ ...profile, experience_level: value })}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select experience level" />
                      </SelectTrigger>
                      <SelectContent>
                        {EXPERIENCE_LEVELS.map((level) => (
                          <SelectItem key={level.value} value={level.value}>
                            {level.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  {/* Risk Tolerance */}
                  <div className="space-y-3">
                    <Label>Risk Tolerance</Label>
                    <div className="grid grid-cols-3 gap-3">
                      {RISK_TOLERANCE.map((risk) => (
                        <div
                          key={risk.value}
                          className={`p-4 rounded-lg border-2 cursor-pointer transition-all ${profile.risk_tolerance === risk.value
                            ? 'border-primary bg-primary/5'
                            : 'border-border hover:border-primary/50'
                            }`}
                          onClick={() => setProfile({ ...profile, risk_tolerance: risk.value })}
                        >
                          <p className="font-medium text-sm">{risk.label}</p>
                          <p className="text-xs text-muted-foreground mt-1">{risk.description}</p>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Trading Hours */}
                  <div className="space-y-2">
                    <Label>Trading Hours</Label>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <Label className="text-xs text-muted-foreground">Start Time</Label>
                        <Input
                          type="time"
                          value={profile.trading_hours_start || '09:15'}
                          onChange={(e) => setProfile({ ...profile, trading_hours_start: e.target.value })}
                        />
                      </div>
                      <div>
                        <Label className="text-xs text-muted-foreground">End Time</Label>
                        <Input
                          type="time"
                          value={profile.trading_hours_end || '15:30'}
                          onChange={(e) => setProfile({ ...profile, trading_hours_end: e.target.value })}
                        />
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Trading Limits */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Shield className="h-5 w-5" />
                    Trading Limits
                  </CardTitle>
                  <CardDescription>
                    These calibrate pattern detection to your actual trading style — alerts become more accurate.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  {/* Capital */}
                  <div className="space-y-2">
                    <Label htmlFor="trading-capital">My trading capital (₹)</Label>
                    <Input
                      id="trading-capital"
                      type="number"
                      placeholder="e.g. 500000"
                      value={profile.trading_capital ?? ''}
                      onChange={(e) => setProfile({ ...profile, trading_capital: e.target.value ? Number(e.target.value) : undefined })}
                    />
                    <p className="text-xs text-muted-foreground">
                      Used to calculate position sizing alerts as % of your actual capital.
                    </p>
                  </div>

                  {/* Max position size (% of capital) */}
                  <div className="space-y-2">
                    <Label>Max per options trade — % of capital as premium</Label>
                    <div className="flex items-center gap-3">
                      <input
                        type="range"
                        min={1}
                        max={30}
                        step={1}
                        value={profile.max_position_size ?? 10}
                        onChange={(e) => setProfile({ ...profile, max_position_size: Number(e.target.value) })}
                        className="w-full accent-primary"
                      />
                      <span className="text-sm font-medium w-12 text-right">{profile.max_position_size ?? 10}%</span>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Alert fires when a single trade exceeds this % of your capital. Default: 10%.
                    </p>
                  </div>

                  {/* SL % futures */}
                  <div className="space-y-2">
                    <Label>My typical stop-loss on futures (% of notional)</Label>
                    <div className="flex flex-wrap gap-2">
                      {[0.5, 1, 1.5, 2, 3].map((pct) => (
                        <button
                          key={pct}
                          type="button"
                          className={`px-3 py-1.5 rounded-md border text-sm font-medium transition-all ${
                            (profile.sl_percent_futures ?? 1.0) === pct
                              ? 'border-primary bg-primary text-primary-foreground'
                              : 'border-border hover:border-primary/50'
                          }`}
                          onClick={() => setProfile({ ...profile, sl_percent_futures: pct })}
                        >
                          {pct}%
                        </button>
                      ))}
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Used to detect no-stop-loss behavior on futures trades.
                    </p>
                  </div>

                  {/* SL % options */}
                  <div className="space-y-2">
                    <Label>I exit options when premium drops by</Label>
                    <div className="flex flex-wrap gap-2">
                      {[30, 50, 70, 100].map((pct) => (
                        <button
                          key={pct}
                          type="button"
                          className={`px-3 py-1.5 rounded-md border text-sm font-medium transition-all ${
                            (profile.sl_percent_options ?? 50) === pct
                              ? 'border-primary bg-primary text-primary-foreground'
                              : 'border-border hover:border-primary/50'
                          }`}
                          onClick={() => setProfile({ ...profile, sl_percent_options: pct })}
                        >
                          {pct}%
                        </button>
                      ))}
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Used to detect holding losers too long on options buys.
                    </p>
                  </div>

                  {/* Daily trade limit */}
                  <div className="space-y-2">
                    <Label htmlFor="daily-trade-limit">My max trades per day</Label>
                    <Input
                      id="daily-trade-limit"
                      type="number"
                      min={1}
                      max={50}
                      placeholder="e.g. 10"
                      value={profile.daily_trade_limit ?? ''}
                      onChange={(e) => setProfile({ ...profile, daily_trade_limit: e.target.value ? Number(e.target.value) : undefined })}
                    />
                    <p className="text-xs text-muted-foreground">
                      Overtrading alert fires when you exceed this. Scales with your style.
                    </p>
                  </div>

                  {/* Cooldown after loss */}
                  <div className="space-y-2">
                    <Label>I wait after a loss before re-entering</Label>
                    <div className="flex flex-wrap gap-2">
                      {[0, 5, 10, 15, 30, 60].map((mins) => (
                        <button
                          key={mins}
                          type="button"
                          className={`px-3 py-1.5 rounded-md border text-sm font-medium transition-all ${
                            (profile.cooldown_after_loss ?? 15) === mins
                              ? 'border-primary bg-primary text-primary-foreground'
                              : 'border-border hover:border-primary/50'
                          }`}
                          onClick={() => setProfile({ ...profile, cooldown_after_loss: mins })}
                        >
                          {mins === 0 ? 'None' : `${mins} min`}
                        </button>
                      ))}
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Revenge trading alert window. If you say 15 min, re-entries at 12 min will fire.
                    </p>
                  </div>
                </CardContent>
              </Card>

              {/* AI Persona */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Brain className="h-5 w-5" />
                    AI Coach Personality
                  </CardTitle>
                  <CardDescription>
                    Choose how your AI trading coach communicates with you
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 gap-4">
                    {AI_PERSONAS.map((persona) => (
                      <div
                        key={persona.value}
                        className={`p-4 rounded-lg border-2 cursor-pointer transition-all ${profile.ai_persona === persona.value
                          ? 'border-primary bg-primary/5'
                          : 'border-border hover:border-primary/50'
                          }`}
                        onClick={() => setProfile({ ...profile, ai_persona: persona.value })}
                      >
                        <p className="font-medium">{persona.label}</p>
                        <p className="text-sm text-muted-foreground mt-1">{persona.description}</p>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* ===== Notifications Tab ===== */}
          <TabsContent value="notifications">
            <div className="space-y-6">
              {/* WhatsApp not configured banner */}
              {notificationStatus && !notificationStatus.whatsapp.twilio_configured && (
                <div className="flex items-start gap-3 p-4 bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 rounded-lg">
                  <AlertTriangle className="h-5 w-5 text-amber-600 dark:text-amber-400 mt-0.5 shrink-0" />
                  <div>
                    <p className="text-sm font-medium text-amber-700 dark:text-amber-300">
                      WhatsApp Not Available
                    </p>
                    <p className="text-xs text-amber-600 dark:text-amber-400 mt-0.5">
                      Twilio is not configured on the server. WhatsApp reports and guardian alerts will be logged but not delivered. Contact admin to set up Twilio credentials.
                    </p>
                  </div>
                </div>
              )}

              {/* Alert Sensitivity */}
              <Card>
                <CardHeader>
                  <CardTitle>Alert Sensitivity</CardTitle>
                  <CardDescription>Control how aggressively patterns are flagged</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-3 gap-3">
                    {ALERT_SENSITIVITY.map((level) => (
                      <div
                        key={level.value}
                        className={`p-3 rounded-lg border-2 cursor-pointer transition-all text-center ${profile.alert_sensitivity === level.value
                          ? 'border-primary bg-primary/5'
                          : 'border-border hover:border-primary/50'
                          }`}
                        onClick={() => setProfile({ ...profile, alert_sensitivity: level.value })}
                      >
                        <p className="font-medium text-sm">{level.label}</p>
                        <p className="text-xs text-muted-foreground">{level.description}</p>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>

              {/* Push Notifications */}
              <NotificationSettings />

              {/* WhatsApp Reports */}
              <Card>
                <CardHeader>
                  <CardTitle>WhatsApp Reports</CardTitle>
                  <CardDescription>Daily trading summaries via WhatsApp</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center justify-between p-4 border rounded-lg">
                    <div>
                      <p className="font-medium">Daily WhatsApp Reports</p>
                      <p className="text-sm text-muted-foreground">
                        Receive end-of-day trading summary via WhatsApp
                      </p>
                    </div>
                    <Switch
                      checked={profile.whatsapp_enabled || false}
                      onCheckedChange={(checked) => setProfile({ ...profile, whatsapp_enabled: checked })}
                    />
                  </div>
                </CardContent>
              </Card>

              {/* Guardian Mode */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Phone className="h-5 w-5" />
                    Guardian Mode
                  </CardTitle>
                  <CardDescription>
                    Set up a trusted contact to receive alerts when you're in danger zone
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  {/* Enable Guardian */}
                  <div className="flex items-center justify-between p-4 border rounded-lg">
                    <div>
                      <p className="font-medium">Enable Guardian Mode</p>
                      <p className="text-sm text-muted-foreground">
                        Send critical alerts to your guardian via WhatsApp
                      </p>
                    </div>
                    <Switch
                      checked={profile.guardian_enabled || false}
                      onCheckedChange={(checked) => setProfile({ ...profile, guardian_enabled: checked })}
                    />
                  </div>

                  {profile.guardian_enabled && (
                    <>
                      {/* Guardian Phone */}
                      <div className="space-y-2">
                        <Label>Guardian's WhatsApp Number</Label>
                        <Input
                          placeholder="+91 9876543210"
                          value={profile.guardian_phone || ''}
                          onChange={(e) => setProfile({ ...profile, guardian_phone: e.target.value })}
                        />
                        <p className="text-xs text-muted-foreground">
                          Include country code (e.g., +91 for India)
                        </p>
                      </div>

                      {/* Alert Threshold */}
                      <div className="space-y-2">
                        <Label>Alert Threshold</Label>
                        <Select
                          value={profile.guardian_alert_threshold || 'critical'}
                          onValueChange={(value) => setProfile({ ...profile, guardian_alert_threshold: value })}
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="critical">Critical Only (Loss limit breached)</SelectItem>
                            <SelectItem value="danger">Danger & Critical</SelectItem>
                            <SelectItem value="warning">Warning, Danger & Critical</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>

                      {/* Daily Summary Toggle */}
                      <div className="flex items-center justify-between p-4 border rounded-lg">
                        <div>
                          <p className="font-medium">Daily Summary Reports</p>
                          <p className="text-sm text-muted-foreground">
                            Send end-of-day trading summary to your guardian
                          </p>
                        </div>
                        <Switch
                          checked={profile.guardian_daily_summary || false}
                          onCheckedChange={(checked) => setProfile({ ...profile, guardian_daily_summary: checked })}
                        />
                      </div>

                      {/* What Guardian Receives */}
                      <div className="p-4 bg-muted/50 rounded-lg space-y-2">
                        <p className="font-medium text-sm">Your guardian will receive:</p>
                        <ul className="text-sm text-muted-foreground space-y-1">
                          <li>- Daily loss limit breached alerts</li>
                          <li>- Critical patterns (tilt, revenge trading)</li>
                          <li>- Consecutive loss threshold exceeded</li>
                          {profile.guardian_alert_threshold === 'warning' && (
                            <li>- Early warning signs</li>
                          )}
                          {profile.guardian_daily_summary && (
                            <li>- Daily trading summary at 4:00 PM</li>
                          )}
                        </ul>
                      </div>

                      {/* Test Message */}
                      <Button
                        variant="outline"
                        className="w-full"
                        onClick={handleTestGuardian}
                      >
                        <Phone className="h-4 w-4 mr-2" />
                        Send Test Message
                      </Button>
                    </>
                  )}
                </CardContent>
              </Card>

              {/* Report Delivery Timing */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Bell className="h-5 w-5" />
                    Report Delivery Timing (IST)
                  </CardTitle>
                  <CardDescription>
                    Choose when you receive automated daily reports. Defaults are after market close and before open.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  {/* EOD Report Time */}
                  <div className="space-y-2">
                    <Label htmlFor="eod-time">Post-Market Report (EOD)</Label>
                    <div className="flex items-center gap-3">
                      <Input
                        id="eod-time"
                        type="time"
                        value={profile.eod_report_time || '16:00'}
                        onChange={(e) => setProfile({ ...profile, eod_report_time: e.target.value })}
                        className="w-36"
                      />
                      <span className="text-sm text-muted-foreground">
                        IST — Default 4:00 PM (after equity market close)
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Includes: trade count, P&amp;L, win rate, emotional journey, patterns detected, lessons &amp; tomorrow's focus.
                    </p>
                  </div>

                  {/* Morning Brief Time */}
                  <div className="space-y-2">
                    <Label htmlFor="morning-time">Morning Readiness Brief</Label>
                    <div className="flex items-center gap-3">
                      <Input
                        id="morning-time"
                        type="time"
                        value={profile.morning_brief_time || '08:30'}
                        onChange={(e) => setProfile({ ...profile, morning_brief_time: e.target.value })}
                        className="w-36"
                      />
                      <span className="text-sm text-muted-foreground">
                        IST — Default 8:30 AM (before market open at 9:15)
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Includes: readiness score, yesterday's recap, watch-outs, personalised checklist &amp; commitment prompt.
                    </p>
                  </div>

                  <div className="p-3 bg-muted/40 rounded-lg text-xs text-muted-foreground">
                    ℹ️ Reports are sent to your WhatsApp (guardian number) and as push notifications.
                    If no custom time is set, the default times above are used.
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}
