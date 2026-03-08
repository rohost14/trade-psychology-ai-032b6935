import { useState, useEffect } from 'react';
import { Bell, BellOff, Smartphone, Monitor, Check, AlertTriangle, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { pushNotifications } from '@/lib/pushNotifications';
import { useBroker } from '@/contexts/BrokerContext';
import { cn } from '@/lib/utils';

interface NotificationSettingsProps {
  className?: string;
}

export default function NotificationSettings({ className }: NotificationSettingsProps) {
  const { account } = useBroker();
  const [isSupported, setIsSupported] = useState(false);
  const [permission, setPermission] = useState<NotificationPermission>('default');
  const [isSubscribed, setIsSubscribed] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [testSent, setTestSent] = useState(false);

  // Check support and current state on mount
  useEffect(() => {
    const checkState = async () => {
      const supported = pushNotifications.isSupported();
      setIsSupported(supported);

      if (supported) {
        setPermission(pushNotifications.getPermissionStatus());
        const subscribed = await pushNotifications.isSubscribed();
        setIsSubscribed(subscribed);
      }
    };

    checkState();
  }, []);

  const handleEnableNotifications = async () => {
    if (!account?.id) {
      setError('Please connect your broker first');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const result = await pushNotifications.setup(account.id);

      setPermission(result.permission);
      setIsSubscribed(result.subscribed);

      if (!result.success) {
        if (result.permission === 'denied') {
          setError('Notification permission was denied. Please enable in browser settings.');
        } else {
          setError('Failed to enable notifications. Please try again.');
        }
      }
    } catch (err) {
      console.error('Enable notifications error:', err);
      setError('An error occurred while enabling notifications');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDisableNotifications = async () => {
    if (!account?.id) return;

    setIsLoading(true);
    setError(null);

    try {
      await pushNotifications.unsubscribe();
      await pushNotifications.removeSubscription(account.id);
      setIsSubscribed(false);
    } catch (err) {
      console.error('Disable notifications error:', err);
      setError('Failed to disable notifications');
    } finally {
      setIsLoading(false);
    }
  };

  const handleTestNotification = async () => {
    if (!account?.id || !isSubscribed) return;

    try {
      await pushNotifications.showLocalNotification({
        title: '🔔 Test Alert',
        body: 'Push notifications are working! You will receive alerts when risky patterns are detected.',
        severity: 'info'
      });
      setTestSent(true);
      setTimeout(() => setTestSent(false), 3000);
    } catch (err) {
      console.error('Test notification error:', err);
      setError('Failed to send test notification');
    }
  };

  if (!isSupported) {
    return (
      <div className={cn('bg-card rounded-lg border border-border p-5', className)}>
        <div className="flex items-start gap-3">
          <div className="p-2 rounded-lg bg-muted">
            <BellOff className="h-5 w-5 text-muted-foreground" />
          </div>
          <div>
            <h3 className="font-medium text-foreground">Push Notifications</h3>
            <p className="text-sm text-muted-foreground mt-1">
              Push notifications are not supported in this browser.
              Try using Chrome, Firefox, or Edge for the best experience.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={cn('bg-card rounded-lg border border-border', className)}>
      <div className="p-5 border-b border-border">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={cn(
              'p-2 rounded-lg',
              isSubscribed ? 'bg-success/10' : 'bg-muted'
            )}>
              {isSubscribed ? (
                <Bell className="h-5 w-5 text-success" />
              ) : (
                <BellOff className="h-5 w-5 text-muted-foreground" />
              )}
            </div>
            <div>
              <h3 className="font-medium text-foreground">Push Notifications</h3>
              <p className="text-sm text-muted-foreground">
                Get instant alerts when risky patterns are detected
              </p>
            </div>
          </div>
          <Switch
            checked={isSubscribed}
            onCheckedChange={(checked) => {
              if (checked) {
                handleEnableNotifications();
              } else {
                handleDisableNotifications();
              }
            }}
            disabled={isLoading || permission === 'denied'}
          />
        </div>
      </div>

      <div className="p-5 space-y-4">
        {/* Status */}
        {permission === 'denied' && (
          <div className="flex items-start gap-2 p-3 bg-destructive/10 rounded-lg">
            <AlertTriangle className="h-4 w-4 text-destructive mt-0.5" />
            <div>
              <p className="text-sm font-medium text-destructive">Permission Denied</p>
              <p className="text-xs text-muted-foreground mt-0.5">
                You've blocked notifications. To enable them, click the lock icon in your browser's
                address bar and allow notifications for this site.
              </p>
            </div>
          </div>
        )}

        {error && (
          <div className="flex items-start gap-2 p-3 bg-destructive/10 rounded-lg">
            <AlertTriangle className="h-4 w-4 text-destructive mt-0.5" />
            <p className="text-sm text-destructive">{error}</p>
          </div>
        )}

        {isSubscribed && (
          <>
            {/* What you'll receive */}
            <div>
              <p className="text-sm font-medium text-foreground mb-2">You'll be notified about:</p>
              <ul className="space-y-2">
                {[
                  { icon: '🚨', text: 'Danger alerts (consecutive losses, revenge trading)' },
                  { icon: '⚠️', text: 'Caution alerts (overtrading, unusual sizing)' },
                  { icon: '📊', text: 'Pattern detection results' }
                ].map((item, idx) => (
                  <li key={idx} className="flex items-center gap-2 text-sm text-muted-foreground">
                    <span>{item.icon}</span>
                    <span>{item.text}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Device info */}
            <div className="flex items-center gap-4 pt-2">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Monitor className="h-4 w-4" />
                <span>This device is subscribed</span>
              </div>
            </div>

            {/* Test button */}
            <div className="pt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleTestNotification}
                disabled={testSent}
                className="gap-2"
              >
                {testSent ? (
                  <>
                    <Check className="h-4 w-4 text-success" />
                    Sent!
                  </>
                ) : (
                  <>
                    <Bell className="h-4 w-4" />
                    Send Test Notification
                  </>
                )}
              </Button>
            </div>
          </>
        )}

        {!isSubscribed && permission !== 'denied' && (
          <div className="pt-2">
            <Button
              onClick={handleEnableNotifications}
              disabled={isLoading || !account}
              className="gap-2"
            >
              {isLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Bell className="h-4 w-4" />
              )}
              Enable Notifications
            </Button>
            <p className="text-xs text-muted-foreground mt-2">
              We'll ask for permission to send you notifications
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
