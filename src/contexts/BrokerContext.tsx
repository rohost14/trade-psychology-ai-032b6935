import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { api } from '@/lib/api';

export interface BrokerAccount {
  id: string;
  broker_name: string;
  broker_user_id: string | null;
  broker_email: string | null;
  status: string;
  connected_at: string | null;
  last_sync_at: string | null;
}

interface BrokerContextValue {
  // Connection state
  isConnected: boolean;
  isLoading: boolean;
  account: BrokerAccount | null;

  // Actions
  connect: () => Promise<void>;
  disconnect: () => Promise<void>;
  refresh: () => Promise<void>;
  syncTrades: () => Promise<SyncResult | null>;
}

interface SyncResult {
  trades_synced: number;
  positions_synced: number;
  orders_synced: number;
  risk_alerts_created: number;
}

const BROKER_ACCOUNT_KEY = 'tradementor_broker_account_id';

const BrokerContext = createContext<BrokerContextValue | undefined>(undefined);

export function BrokerProvider({ children }: { children: ReactNode }) {
  const [account, setAccount] = useState<BrokerAccount | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Check for broker_account_id in URL params (after OAuth callback)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const brokerAccountId = params.get('broker_account_id');
    const connected = params.get('connected');
    const error = params.get('error');

    if (error) {
      console.error('OAuth error:', error);
      // Clean URL
      window.history.replaceState({}, '', window.location.pathname);
    }

    if (connected === 'true' && brokerAccountId) {
      // Save the broker account ID
      localStorage.setItem(BROKER_ACCOUNT_KEY, brokerAccountId);
      // Clean URL
      window.history.replaceState({}, '', window.location.pathname);
    }
  }, []);

  // Load broker account on mount
  const loadAccount = useCallback(async () => {
    setIsLoading(true);
    try {
      // First check localStorage for saved account ID
      const savedAccountId = localStorage.getItem(BROKER_ACCOUNT_KEY);

      // Fetch all connected accounts from backend
      const response = await api.get('/api/zerodha/accounts');
      const accounts: BrokerAccount[] = response.data.accounts || [];

      if (accounts.length > 0) {
        // If we have a saved account ID, try to find it
        if (savedAccountId) {
          const savedAccount = accounts.find(a => a.id === savedAccountId);
          if (savedAccount) {
            setAccount(savedAccount);
            return;
          }
        }
        // Otherwise use the first connected account
        setAccount(accounts[0]);
        localStorage.setItem(BROKER_ACCOUNT_KEY, accounts[0].id);
      } else {
        setAccount(null);
        localStorage.removeItem(BROKER_ACCOUNT_KEY);
      }
    } catch (error) {
      console.error('Failed to load broker account:', error);
      setAccount(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAccount();
  }, [loadAccount]);

  const connect = useCallback(async () => {
    try {
      // Get the OAuth URL from backend
      // The redirect_uri must point to the backend callback endpoint
      const backendUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const redirectUri = `${backendUrl}/api/zerodha/callback`;
      const response = await api.get('/api/zerodha/connect', {
        params: { redirect_uri: redirectUri }
      });

      const { login_url } = response.data;
      if (login_url) {
        // Redirect to Zerodha login
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
      await api.post('/api/zerodha/disconnect', {
        broker_account_id: account.id
      });
      setAccount(null);
      localStorage.removeItem(BROKER_ACCOUNT_KEY);
    } catch (error) {
      console.error('Failed to disconnect:', error);
      throw error;
    }
  }, [account]);

  const syncTrades = useCallback(async (): Promise<SyncResult | null> => {
    if (!account) return null;

    try {
      const response = await api.post('/api/trades/sync', {
        broker_account_id: account.id
      });

      // Refresh account to update last_sync_at
      await loadAccount();

      return response.data;
    } catch (error) {
      console.error('Failed to sync trades:', error);
      throw error;
    }
  }, [account, loadAccount]);

  const refresh = useCallback(async () => {
    await loadAccount();
  }, [loadAccount]);

  return (
    <BrokerContext.Provider
      value={{
        isConnected: account?.status === 'connected',
        isLoading,
        account,
        connect,
        disconnect,
        refresh,
        syncTrades,
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
