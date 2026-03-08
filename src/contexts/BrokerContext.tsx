import { createContext, useContext, useState, useEffect, useCallback, useRef, ReactNode } from 'react';
import { api, AUTH_TOKEN_KEY } from '@/lib/api';
import { toast } from 'sonner';

export interface BrokerAccount {
  id: string;
  broker_name: string;
  broker_user_id: string | null;
  broker_email: string | null;
  status: string;
  connected_at: string | null;
  last_sync_at: string | null;
}

export type SyncStatus = 'idle' | 'syncing' | 'success' | 'error';

interface BrokerContextValue {
  // Connection state
  isConnected: boolean;
  isLoading: boolean;
  account: BrokerAccount | null;

  // Token validation state
  tokenStatus: 'valid' | 'expired' | 'checking' | 'unknown';
  isTokenExpired: boolean;

  // Sync state - exposed so Dashboard can react to it
  syncStatus: SyncStatus;
  syncError: string | null;
  lastSyncResult: SyncResult | null;

  // Actions
  connect: () => Promise<void>;
  disconnect: () => Promise<void>;
  refresh: () => Promise<void>;
  syncTrades: () => Promise<SyncResult | null>;
  validateToken: () => Promise<boolean>;
}

interface SyncResult {
  trades_synced: number;
  positions_synced: number;
  orders_synced: number;
  risk_alerts_created: number;
}

const BROKER_ACCOUNT_KEY = 'tradementor_broker_account_id';
const LAST_SYNC_KEY = 'tradementor_last_sync_ts';

const BrokerContext = createContext<BrokerContextValue | undefined>(undefined);

export function BrokerProvider({ children }: { children: ReactNode }) {
  const [account, setAccount] = useState<BrokerAccount | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [tokenStatus, setTokenStatus] = useState<'valid' | 'expired' | 'checking' | 'unknown'>('unknown');

  // Sync state
  const [syncStatus, setSyncStatus] = useState<SyncStatus>('idle');
  const [syncError, setSyncError] = useState<string | null>(null);
  const [lastSyncResult, setLastSyncResult] = useState<SyncResult | null>(null);

  // Refs to prevent duplicate operations
  const syncInProgressRef = useRef(false);
  const initialSyncDoneRef = useRef(false);

  // Check for OAuth callback params (token + broker_account_id in URL)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get('token');
    const brokerAccountId = params.get('broker_account_id');
    const connected = params.get('connected');
    const error = params.get('error');

    if (error) {
      console.error('OAuth error:', error);
      toast.error(`Connection failed: ${decodeURIComponent(error)}`, { duration: 8000 });
      window.history.replaceState({}, '', window.location.pathname);
    }

    if (connected === 'true' && token) {
      // Store JWT for all future API calls
      localStorage.setItem(AUTH_TOKEN_KEY, token);
      if (brokerAccountId) {
        localStorage.setItem(BROKER_ACCOUNT_KEY, brokerAccountId);
      }
      // Mark that we need initial sync after account loads
      initialSyncDoneRef.current = false;
      window.history.replaceState({}, '', window.location.pathname);
    }
  }, []);

  // Load broker account on mount
  const loadAccount = useCallback(async () => {
    setIsLoading(true);
    try {
      const authToken = localStorage.getItem(AUTH_TOKEN_KEY);
      if (!authToken) {
        // No auth token - user hasn't connected yet
        setAccount(null);
        setIsLoading(false);
        return;
      }

      const response = await api.get('/api/zerodha/accounts');
      const accounts: BrokerAccount[] = response.data.accounts || [];

      if (accounts.length > 0) {
        setAccount(accounts[0]);
        localStorage.setItem(BROKER_ACCOUNT_KEY, accounts[0].id);
      } else {
        setAccount(null);
        localStorage.removeItem(BROKER_ACCOUNT_KEY);
      }
    } catch (error: any) {
      if (error.response?.status === 401) {
        // JWT expired or invalid - clear stored credentials
        localStorage.removeItem(AUTH_TOKEN_KEY);
        localStorage.removeItem(BROKER_ACCOUNT_KEY);
      }
      console.error('Failed to load broker account:', error);
      setAccount(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAccount();
  }, [loadAccount]);

  // Core sync function - all sync calls go through here
  const doSync = useCallback(async (accountToSync: BrokerAccount): Promise<SyncResult | null> => {
    // Prevent concurrent syncs
    if (syncInProgressRef.current) {
      return null;
    }

    syncInProgressRef.current = true;
    setSyncStatus('syncing');
    setSyncError(null);

    try {
      const response = await api.post('/api/zerodha/sync/all');

      const result = response.data;

      // If server says sync already in progress, treat as success
      if (result.message === 'Sync already in progress') {
        setSyncStatus('success');
        return null;
      }

      const syncResult: SyncResult = {
        trades_synced: result.results?.trades?.trades_synced || 0,
        positions_synced: result.results?.trades?.positions_synced || 0,
        orders_synced: result.results?.orders?.orders_synced || 0,
        risk_alerts_created: result.results?.risk_alerts || 0,
      };

      setLastSyncResult(syncResult);
      setSyncStatus('success');
      localStorage.setItem(LAST_SYNC_KEY, Date.now().toString());

      // Refresh account to update last_sync_at without re-triggering sync
      const accResponse = await api.get('/api/zerodha/accounts');
      const accounts: BrokerAccount[] = accResponse.data.accounts || [];
      const updated = accounts.find(a => a.id === accountToSync.id);
      if (updated) {
        setAccount(updated);
      }

      return syncResult;
    } catch (error: any) {
      const errMsg = error.response?.data?.detail || error.message || 'Sync failed';
      console.error('Sync failed:', errMsg);
      setSyncError(errMsg);
      setSyncStatus('error');
      return null;
    } finally {
      syncInProgressRef.current = false;
    }
  }, []);

  // Single unified auto-sync effect - runs ONCE after account loads
  useEffect(() => {
    if (!account || account.status !== 'connected' || initialSyncDoneRef.current) return;

    const shouldSync = () => {
      // Check localStorage timestamp for cross-tab deduplication
      const lastSyncTs = localStorage.getItem(LAST_SYNC_KEY);
      if (lastSyncTs) {
        const elapsed = Date.now() - parseInt(lastSyncTs, 10);
        if (elapsed < 5 * 60 * 1000) return false; // Synced less than 5 min ago
      }
      // Also check server-side last_sync_at
      if (account.last_sync_at) {
        const elapsed = Date.now() - new Date(account.last_sync_at).getTime();
        if (elapsed < 5 * 60 * 1000) return false;
      }
      return true;
    };

    initialSyncDoneRef.current = true;

    if (shouldSync()) {
      doSync(account);
    } else {
      // Data is fresh enough, mark as success so Dashboard knows to fetch
      setSyncStatus('success');
    }
  }, [account, doSync]);

  const connect = useCallback(async () => {
    try {
      const response = await api.get('/api/zerodha/connect');
      const { login_url } = response.data;
      if (login_url) {
        window.location.href = login_url;
      }
    } catch (error) {
      console.error('Failed to initiate OAuth:', error);
      throw error;
    }
  }, []);

  const disconnect = useCallback(async () => {
    if (!account) return;

    try {
      await api.post('/api/zerodha/disconnect');
      setAccount(null);
      setSyncStatus('idle');
      setLastSyncResult(null);
      localStorage.removeItem(AUTH_TOKEN_KEY);
      localStorage.removeItem(BROKER_ACCOUNT_KEY);
      localStorage.removeItem(LAST_SYNC_KEY);
    } catch (error) {
      console.error('Failed to disconnect:', error);
      throw error;
    }
  }, [account]);

  const syncTrades = useCallback(async (): Promise<SyncResult | null> => {
    if (!account) return null;
    return doSync(account);
  }, [account, doSync]);

  const validateToken = useCallback(async (): Promise<boolean> => {
    if (!account) return false;

    setTokenStatus('checking');
    try {
      const response = await api.get('/api/zerodha/token/validate');

      const { valid, needs_login } = response.data;

      if (valid) {
        setTokenStatus('valid');
        return true;
      } else if (needs_login) {
        setTokenStatus('expired');
        return false;
      } else {
        setTokenStatus('unknown');
        return false;
      }
    } catch (error) {
      console.error('Failed to validate token:', error);
      setTokenStatus('unknown');
      return false;
    }
  }, [account]);

  // Validate token when account loads
  useEffect(() => {
    if (account && account.status === 'connected') {
      validateToken();
    }
  }, [account, validateToken]);

  // Listen for token expiry events from API interceptor (D12)
  useEffect(() => {
    const handler = () => {
      setTokenStatus('expired');
    };
    window.addEventListener('tradementor:token-expired', handler);
    return () => window.removeEventListener('tradementor:token-expired', handler);
  }, []);

  const refresh = useCallback(async () => {
    await loadAccount();
  }, [loadAccount]);

  return (
    <BrokerContext.Provider
      value={{
        isConnected: account?.status === 'connected',
        isLoading,
        account,
        tokenStatus,
        isTokenExpired: tokenStatus === 'expired',
        syncStatus,
        syncError,
        lastSyncResult,
        connect,
        disconnect,
        refresh,
        syncTrades,
        validateToken,
      }}
    >
      {children}
    </BrokerContext.Provider>
  );
}

export function useBroker() {
  const context = useContext(BrokerContext);
  if (!context) {
    throw new Error('useBroker must be used within BrokerProvider');
  }
  return context;
}
