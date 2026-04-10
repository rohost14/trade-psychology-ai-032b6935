import { Link2, Link2Off, Shield, AlertTriangle, Loader2, Key } from 'lucide-react';
import { Button } from '@/components/ui/button';
import ApiKeySetup from '@/components/ApiKeySetup';

interface BrokerAccount {
  id: string;
  broker_user_id?: string;
  broker_email?: string;
  sync_status?: string;
  last_sync_at?: string | null;
}

interface BrokerConnectionCardProps {
  isConnected: boolean;
  account: BrokerAccount | null;
  isConnecting: boolean;
  isDisconnecting: boolean;
  onConnect: () => void;
  onDisconnect: () => void;
  formatLastSync: (dateStr: string | null) => string;
  onRedirecting: () => void;
}

export function BrokerConnectionCard({
  isConnected,
  account,
  isConnecting,
  isDisconnecting,
  onConnect,
  onDisconnect,
  formatLastSync,
  onRedirecting,
}: BrokerConnectionCardProps) {
  return (
    <div className="tm-card overflow-hidden">
      <div className="px-5 py-4 border-b border-border">
        <p className="text-sm font-semibold text-foreground flex items-center gap-2">
          <Link2 className="h-4 w-4" />
          Broker Connection
        </p>
        <p className="text-xs text-muted-foreground mt-0.5">Connect your Zerodha account</p>
      </div>
      <div className="p-5">
        {isConnected && account ? (
          <div className="space-y-4">
            <div className="flex items-center justify-between p-4 bg-teal-50 dark:bg-teal-900/10 border border-tm-brand/20 rounded-lg">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-full bg-teal-50 dark:bg-teal-900/20">
                  <Shield className="h-5 w-5 text-tm-brand" />
                </div>
                <div>
                  <p className="text-sm font-medium text-tm-brand">Connected to Zerodha</p>
                  {account.sync_status === 'syncing' ? (
                    <p className="text-xs text-tm-obs flex items-center gap-1">
                      <span className="inline-block h-2 w-2 rounded-full bg-amber-400 animate-pulse" />
                      Loading your trading data…
                    </p>
                  ) : (
                    <p className="text-xs text-tm-brand/70">
                      Last synced: {formatLastSync(account.last_sync_at ?? null)}
                    </p>
                  )}
                </div>
              </div>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={onDisconnect}
                  disabled={isDisconnecting}
                  className="text-tm-loss hover:text-tm-loss"
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
                <div className="p-2 rounded-full bg-amber-500/10">
                  <AlertTriangle className="h-5 w-5 text-amber-500" />
                </div>
                <div>
                  <p className="text-sm font-medium text-amber-700 dark:text-amber-300">Not Connected</p>
                  <p className="text-xs text-amber-600 dark:text-amber-400">Connect your broker to start monitoring</p>
                </div>
              </div>
            </div>

            <Button onClick={onConnect} disabled={isConnecting} className="w-full">
              {isConnecting ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Link2 className="h-4 w-4 mr-2" />
              )}
              Connect Zerodha Account
            </Button>

            <div className="relative flex items-center gap-3">
              <div className="flex-1 border-t border-border" />
              <span className="text-xs text-muted-foreground shrink-0">or</span>
              <div className="flex-1 border-t border-border" />
            </div>

            <ApiKeySetup
              onRedirecting={onRedirecting}
              trigger={
                <Button variant="outline" className="w-full gap-2">
                  <Key className="h-4 w-4" />
                  Use your own KiteConnect app
                </Button>
              }
            />
          </div>
        )}
      </div>
    </div>
  );
}
