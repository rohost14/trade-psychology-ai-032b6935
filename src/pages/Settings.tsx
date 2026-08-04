import { useState, useEffect, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Save, Loader2, User, Bell, Brain, Database, ShieldAlert } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useBroker } from '@/contexts/BrokerContext';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import { UserProfile, NotificationStatus, profileSchema } from '@/lib/settingsConstants';
import { BrokerConnectionCard } from '@/components/settings/BrokerConnectionCard';
import { ProfileTab } from '@/components/settings/ProfileTab';
import { NotificationsTab } from '@/components/settings/NotificationsTab';
import { InsightsTab } from '@/components/settings/InsightsTab';
import ErrorState from '@/components/ErrorState';
import { useQueryClient } from '@tanstack/react-query';
import { useApiQuery } from '@/hooks/useApiQuery';
import { DataTab } from '@/components/settings/DataTab';
import { DangerZoneTab } from '@/components/settings/DangerZoneTab';

// Rule fields are change-controlled by the Constitution (backend RULE_FIELDS).
// Tightening applies instantly; loosening returns 409 and must go through
// My Rules. Friendly labels so the error names what the user actually edited.
const RULE_FIELD_LABELS: Record<string, string> = {
  daily_loss_limit:       'Daily loss limit',
  daily_trade_limit:      'Max trades per day',
  max_position_size:      'Max position size',
  cooldown_after_loss:    'Cooldown after a loss',
  max_consecutive_losses: 'Max consecutive losses',
  restricted_windows:     'Restricted trading windows',
};

// Deep-linkable tabs. Anything else in ?tab= falls back to profile rather than
// rendering an empty panel — the value arrives from a URL, so it is user input.
const TABS = ['profile', 'notifications', 'insights', 'data', 'danger'] as const;

export default function Settings() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const requestedTab = searchParams.get('tab');
  const initialTab = TABS.includes(requestedTab as typeof TABS[number]) ? requestedTab! : 'profile';
  const { isConnected, isLoading: brokerLoading, account, connect, disconnect } = useBroker();
  const [isConnecting, setIsConnecting] = useState(false);
  const [isDisconnecting, setIsDisconnecting] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isDirty, setIsDirty] = useState(false);
  // isLoadingProfile and profileError now come from the query below, not local state.
  const [notificationStatus, setNotificationStatus] = useState<NotificationStatus | null>(null);
  const queryClient = useQueryClient();

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
  });

  const updateProfile = useCallback((action: Parameters<typeof setProfile>[0]) => {
    setProfile(action);
    setIsDirty(true);
  }, []);

  const profileQuery = useApiQuery<{ profile?: Partial<UserProfile> }>(
    ['profile', account?.id],
    '/api/profile/',
    { enabled: Boolean(isConnected && account?.id) },
  );

  const notificationQuery = useApiQuery<NotificationStatus>(
    ['profile', 'notification-status', account?.id],
    '/api/profile/notification-status',
    { enabled: Boolean(isConnected && account?.id) },
  );

  const isLoadingProfile = profileQuery.isPending;
  // The form must never fall through to its hardcoded defaults after a failed
  // load — those look exactly like saved settings, and Save would write them over
  // the trader's real rules. Both the form and the Save button check this.
  const profileError = profileQuery.error;

  // Seed the editable draft from the server value. Guarded on isDirty: React Query
  // refetches in the background when the data goes stale or the tab regains focus,
  // and without this guard that refetch would silently discard whatever the user
  // was in the middle of typing.
  const serverProfile = profileQuery.data?.profile;
  useEffect(() => {
    if (!serverProfile || isDirty) return;
    setProfile(prev => ({ ...prev, ...serverProfile }));
  }, [serverProfile, isDirty]);

  useEffect(() => {
    if (notificationQuery.data) setNotificationStatus(notificationQuery.data);
  }, [notificationQuery.data]);

  const fetchProfile = useCallback(() => { profileQuery.refetch(); }, [profileQuery]);

  const handleSaveProfile = async () => {
    if (!account?.id) return;

    const validation = profileSchema.safeParse(profile);
    if (!validation.success) {
      const first = validation.error.errors[0];
      toast.error(`${first.path.join('.')}: ${first.message}`);
      return;
    }

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
        email_enabled: profile.email_enabled,
        alert_sensitivity: profile.alert_sensitivity,
        guardian_enabled: profile.guardian_enabled,
        guardian_phone: profile.guardian_phone,
        guardian_name: profile.guardian_name,
        guardian_alert_threshold: profile.guardian_alert_threshold,
        // Was missing from this payload: the Guardian tab let users edit it and
        // reported success, but the value was never sent and silently vanished.
        guardian_loss_limit: profile.guardian_loss_limit,
        // Read by retention_tasks to schedule each user's report delivery.
        eod_report_time: profile.eod_report_time,
        morning_brief_time: profile.morning_brief_time,
      };

      await api.put('/api/profile/', payload);
      toast.success('Settings saved successfully');

      // Refetch BEFORE clearing the dirty flag, and await it. The seeding effect
      // re-applies the server value the moment isDirty goes false; if the cache
      // still held the pre-save copy at that instant, the form would visibly
      // revert to the old values right after saying "saved". invalidateQueries
      // resolves once the refetch lands, so the order here is load-bearing.
      await queryClient.invalidateQueries({ queryKey: ['profile'] });
      setIsDirty(false);
    } catch (error) {
      const err = error as {
        response?: { status?: number; data?: { detail?: unknown } };
      };
      const detail = err.response?.data?.detail;

      // 409 = Constitution lock. Relaxing a trading rule needs the friction
      // flow in My Rules; the whole save is rejected server-side, so say that
      // plainly instead of a generic failure.
      if (err.response?.status === 409 && typeof detail === 'object' && detail !== null) {
        const d = detail as { code?: string; loosening_fields?: string[]; message?: string };
        if (d.code === 'override_required') {
          const names = (d.loosening_fields ?? [])
            .map(f => RULE_FIELD_LABELS[f] ?? f.replace(/_/g, ' '))
            .join(', ');
          toast.error(
            names
              ? `Relaxing ${names} needs confirmation in My Rules`
              : 'Relaxing a trading rule needs confirmation in My Rules',
            {
              description: 'Nothing was saved. Tightening a rule applies instantly; loosening one goes through My Rules.',
              duration: 10000,
              action: { label: 'Open My Rules', onClick: () => navigate('/my-rules') },
            },
          );
          return;
        }
      }

      console.error('Failed to save profile:', error);
      toast.error(typeof detail === 'string' ? detail : 'Failed to save settings');
    } finally {
      setIsSaving(false);
    }
  };

  const handleConnect = async () => {
    setIsConnecting(true);
    try {
      await connect();
    } catch {
      toast.error('Failed to connect to Zerodha');
      setIsConnecting(false);
    }
  };

  const handleDisconnect = async () => {
    setIsDisconnecting(true);
    try {
      await disconnect();
      toast.success('Disconnected from Zerodha');
    } catch {
      toast.error('Failed to disconnect');
    } finally {
      setIsDisconnecting(false);
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
    } catch (error) {
      const status = (error as { response?: { status?: number } })?.response?.status;
      if (status === 503) {
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
      <div className="max-w-3xl mx-auto space-y-4 pb-12">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-40 rounded-lg" />
        <div className="grid grid-cols-2 gap-4">
          {[1,2,3,4].map(i => <Skeleton key={i} className="h-32 rounded-lg" />)}
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="t-heading-lg text-foreground">Settings</h1>
          <p className="text-sm text-muted-foreground">
            Manage your broker, profile, and preferences
          </p>
        </div>
        {/* Hidden while the profile failed to load — the form below is hidden too,
            so Save would be writing the component's hardcoded defaults over the
            trader's real rules. Hiding the form without hiding Save leaves exactly
            that trap one click away. */}
        {isConnected && !profileError && (
          <div className="flex items-center gap-3">
            {isDirty && !isSaving && (
              <span className="text-[11px] text-muted-foreground">Unsaved changes</span>
            )}
            <Button onClick={handleSaveProfile} disabled={isSaving}>
              {isSaving ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Save className="h-4 w-4 mr-2" />
              )}
              Save All Settings
            </Button>
          </div>
        )}
      </div>

      {/* Broker Connection Card */}
      <BrokerConnectionCard
        isConnected={isConnected}
        account={account}
        isConnecting={isConnecting}
        isDisconnecting={isDisconnecting}
        onConnect={handleConnect}
        onDisconnect={handleDisconnect}
        formatLastSync={formatLastSync}
        onRedirecting={() => setIsConnecting(true)}
      />

      {/* A failed profile load must NOT fall through to the form. The form's
          initial state is a set of hardcoded defaults; rendering them after a
          failed load makes invented numbers look like saved settings, and Save
          would then overwrite the trader's real rules with them. */}
      {isConnected && profileError && (
        <ErrorState
          error={profileError}
          onRetry={fetchProfile}
          message="We couldn't load your saved settings. They haven't changed — this is only a display problem. Try again rather than re-entering them, so you don't overwrite what's already saved."
        />
      )}

      {/* Only show other settings if connected */}
      {isConnected && !profileError && (
        <Tabs defaultValue={initialTab} className="space-y-5">
          <TabsList className="inline-flex h-auto bg-transparent p-0 gap-1 border-b border-border w-full rounded-none">
            <TabsTrigger value="profile" className="rounded-none px-3 pb-3 text-sm font-medium text-muted-foreground data-[state=active]:bg-transparent data-[state=active]:text-foreground data-[state=active]:border-b-2 data-[state=active]:border-tm-brand transition-colors flex items-center gap-1.5">
              <User className="h-4 w-4" />
              Profile
            </TabsTrigger>
            <TabsTrigger value="notifications" className="rounded-none px-3 pb-3 text-sm font-medium text-muted-foreground data-[state=active]:bg-transparent data-[state=active]:text-foreground data-[state=active]:border-b-2 data-[state=active]:border-tm-brand transition-colors flex items-center gap-1.5">
              <Bell className="h-4 w-4" />
              Notifications
            </TabsTrigger>
            <TabsTrigger value="insights" className="rounded-none px-3 pb-3 text-sm font-medium text-muted-foreground data-[state=active]:bg-transparent data-[state=active]:text-foreground data-[state=active]:border-b-2 data-[state=active]:border-tm-brand transition-colors flex items-center gap-1.5">
              <Brain className="h-4 w-4" />
              Insights
            </TabsTrigger>
            <TabsTrigger value="data" className="rounded-none px-3 pb-3 text-sm font-medium text-muted-foreground data-[state=active]:bg-transparent data-[state=active]:text-foreground data-[state=active]:border-b-2 data-[state=active]:border-tm-brand transition-colors flex items-center gap-1.5">
              <Database className="h-4 w-4" />
              Data
            </TabsTrigger>
            <TabsTrigger value="danger" className="rounded-none px-3 pb-3 text-sm font-medium text-muted-foreground data-[state=active]:bg-transparent data-[state=active]:text-tm-loss data-[state=active]:border-b-2 data-[state=active]:border-tm-loss transition-colors flex items-center gap-1.5">
              <ShieldAlert className="h-4 w-4" />
              Danger Zone
            </TabsTrigger>
          </TabsList>

          <TabsContent value="profile">
            <ProfileTab profile={profile} setProfile={updateProfile} />
          </TabsContent>

          <TabsContent value="notifications">
            <NotificationsTab
              profile={profile}
              setProfile={updateProfile}
              notificationStatus={notificationStatus}
              account={account}
              onTestGuardian={handleTestGuardian}
              isDirty={isDirty}
            />
          </TabsContent>

          <TabsContent value="insights">
            <InsightsTab />
          </TabsContent>

          <TabsContent value="data">
            <DataTab />
          </TabsContent>

          <TabsContent value="danger">
            <DangerZoneTab />
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}
