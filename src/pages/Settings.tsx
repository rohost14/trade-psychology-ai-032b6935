import { useState } from 'react';
import { Link2, Link2Off, Settings as SettingsIcon, Shield, AlertTriangle, RefreshCw, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useBroker } from '@/contexts/BrokerContext';
import { toast } from 'sonner';

export default function Settings() {
  const { isConnected, isLoading, account, connect, disconnect, syncTrades } = useBroker();
  const [isConnecting, setIsConnecting] = useState(false);
  const [isDisconnecting, setIsDisconnecting] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);

  const handleConnect = async () => {
    setIsConnecting(true);
    try {
      await connect();
      // The page will redirect to Zerodha, so we don't need to handle success here
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

  if (isLoading) {
    return (
      <div className="max-w-2xl mx-auto flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto">
      {/* Page Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-foreground">Settings</h1>
        <p className="text-sm text-muted-foreground">
          Manage your broker connection and preferences
        </p>
      </div>

      {/* Broker Connection Card */}
      <div className="bg-card rounded-lg shadow-sm border border-border p-6 mb-6">
        <div className="flex items-center gap-3 mb-6">
          <div className="p-2 rounded-lg bg-primary/10">
            <Link2 className="h-5 w-5 text-primary" />
          </div>
          <div>
            <h3 className="text-base font-semibold text-foreground">Broker Connection</h3>
            <p className="text-sm text-muted-foreground">Connect your Zerodha account</p>
          </div>
        </div>

        {isConnected && account ? (
          <div className="space-y-4">
            {/* Connected State */}
            <div className="flex items-center justify-between p-4 bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800 rounded-lg">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-full bg-success/10">
                  <Shield className="h-5 w-5 text-success" />
                </div>
                <div>
                  <p className="text-sm font-medium text-emerald-700 dark:text-emerald-300">Connected to Zerodha</p>
                  <p className="text-xs text-emerald-600 dark:text-emerald-400">
                    Last synced: {formatLastSync(account.last_sync_at)}
                  </p>
                </div>
              </div>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleSync}
                  disabled={isSyncing}
                  className="gap-1.5"
                >
                  <RefreshCw className={`h-4 w-4 ${isSyncing ? 'animate-spin' : ''}`} />
                  {isSyncing ? 'Syncing...' : 'Sync'}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleDisconnect}
                  disabled={isDisconnecting}
                  className="text-destructive hover:text-destructive hover:bg-destructive/10"
                >
                  <Link2Off className="h-4 w-4 mr-1.5" />
                  {isDisconnecting ? 'Disconnecting...' : 'Disconnect'}
                </Button>
              </div>
            </div>

            {/* Account Info */}
            <div className="grid grid-cols-2 gap-4">
              <div className="p-4 bg-muted/50 rounded-lg">
                <p className="text-xs text-muted-foreground mb-1">Broker</p>
                <p className="text-sm font-medium text-foreground">Zerodha (Kite)</p>
              </div>
              <div className="p-4 bg-muted/50 rounded-lg">
                <p className="text-xs text-muted-foreground mb-1">Account ID</p>
                <p className="text-sm font-mono text-foreground">
                  {account.broker_user_id || 'Unknown'}
                </p>
              </div>
              {account.broker_email && (
                <div className="p-4 bg-muted/50 rounded-lg col-span-2">
                  <p className="text-xs text-muted-foreground mb-1">Email</p>
                  <p className="text-sm text-foreground">{account.broker_email}</p>
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Disconnected State */}
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

            <Button
              onClick={handleConnect}
              disabled={isConnecting}
              className="w-full gap-2"
            >
              {isConnecting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Connecting...
                </>
              ) : (
                <>
                  <Link2 className="h-4 w-4" />
                  Connect Zerodha Account
                </>
              )}
            </Button>

            <p className="text-xs text-muted-foreground text-center">
              You will be redirected to Zerodha to authorize access. We only request read-only
              permissions for your positions and orders.
            </p>
          </div>
        )}
      </div>

      {/* Preferences Card */}
      <div className="bg-card rounded-lg shadow-sm border border-border p-6">
        <div className="flex items-center gap-3 mb-6">
          <div className="p-2 rounded-lg bg-muted">
            <SettingsIcon className="h-5 w-5 text-muted-foreground" />
          </div>
          <div>
            <h3 className="text-base font-semibold text-foreground">Preferences</h3>
            <p className="text-sm text-muted-foreground">Customize your experience</p>
          </div>
        </div>

        <div className="space-y-4">
          <div className="flex items-center justify-between p-4 bg-muted/50 rounded-lg">
            <div>
              <p className="text-sm font-medium text-foreground">Analysis Window</p>
              <p className="text-xs text-muted-foreground">
                Time period for behavioral analysis
              </p>
            </div>
            <select className="px-3 py-1.5 bg-card border border-border rounded-md text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring">
              <option value="7">Last 7 days</option>
              <option value="30">Last 30 days</option>
              <option value="90">Last 90 days</option>
            </select>
          </div>

          <div className="flex items-center justify-between p-4 bg-muted/50 rounded-lg">
            <div>
              <p className="text-sm font-medium text-foreground">Alert Notifications</p>
              <p className="text-xs text-muted-foreground">
                Receive alerts for behavioral patterns
              </p>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input type="checkbox" defaultChecked className="sr-only peer" />
              <div className="w-11 h-6 bg-muted rounded-full peer peer-checked:bg-primary peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-card after:rounded-full after:h-5 after:w-5 after:transition-all" />
            </label>
          </div>
        </div>
      </div>
    </div>
  );
}
