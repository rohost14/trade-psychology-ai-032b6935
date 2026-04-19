import { useState, useEffect, useCallback } from 'react';
import { Save, Loader2, User, Bell } from 'lucide-react';
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

export default function Settings() {
  const { isConnected, isLoading: brokerLoading, account, connect, disconnect } = useBroker();
  const [isConnecting, setIsConnecting] = useState(false);
  const [isDisconnecting, setIsDisconnecting] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isLoadingProfile, setIsLoadingProfile] = useState(false);
  const [notificationStatus, setNotificationStatus] = useState<NotificationStatus | null>(null);

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
        guardian_daily_summary: profile.guardian_daily_summary,
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
      <div className="max-w-4xl mx-auto space-y-4 pb-12">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-40 rounded-xl" />
        <div className="grid grid-cols-2 gap-4">
          {[1,2,3,4].map(i => <Skeleton key={i} className="h-32 rounded-xl" />)}
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-foreground tracking-tight">Settings</h1>
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

      {/* Only show other settings if connected */}
      {isConnected && (
        <Tabs defaultValue="profile" className="space-y-5">
          <TabsList className="inline-flex h-auto bg-transparent p-0 gap-1 border-b border-border w-full rounded-none">
            <TabsTrigger value="profile" className="rounded-none px-3 pb-3 text-sm font-medium text-muted-foreground data-[state=active]:bg-transparent data-[state=active]:text-foreground data-[state=active]:border-b-2 data-[state=active]:border-tm-brand transition-colors flex items-center gap-1.5">
              <User className="h-4 w-4" />
              Profile
            </TabsTrigger>
            <TabsTrigger value="notifications" className="rounded-none px-3 pb-3 text-sm font-medium text-muted-foreground data-[state=active]:bg-transparent data-[state=active]:text-foreground data-[state=active]:border-b-2 data-[state=active]:border-tm-brand transition-colors flex items-center gap-1.5">
              <Bell className="h-4 w-4" />
              Notifications
            </TabsTrigger>
          </TabsList>

          <TabsContent value="profile">
            <ProfileTab profile={profile} setProfile={setProfile} />
          </TabsContent>

          <TabsContent value="notifications">
            <NotificationsTab
              profile={profile}
              setProfile={setProfile}
              notificationStatus={notificationStatus}
              account={account}
              onTestGuardian={handleTestGuardian}
            />
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}
