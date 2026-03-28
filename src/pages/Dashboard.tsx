import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Link2, Loader2, AlertTriangle, RefreshCw, X } from 'lucide-react';
import RiskGuardianCard from '@/components/dashboard/RiskGuardianCard';
import BlowupShieldCard from '@/components/dashboard/BlowupShieldCard';
import RecentAlertsCard from '@/components/dashboard/RecentAlertsCard';
import OpenPositionsTable from '@/components/dashboard/OpenPositionsTable';
import ClosedTradesTable from '@/components/dashboard/ClosedTradesTable';
import HoldingsCard from '@/components/dashboard/HoldingsCard';
import MarginStatusCard from '@/components/dashboard/MarginStatusCard';
import MarginInsightsCard from '@/components/dashboard/MarginInsightsCard';
import PredictiveWarningsCard from '@/components/dashboard/PredictiveWarningsCard';
import ProgressTrackingCard from '@/components/dashboard/ProgressTrackingCard';
import { useHoldings } from '@/hooks/useHoldings';
import { TradeJournalSheet } from '@/components/dashboard/TradeJournalSheet';
import OnboardingWizard from '@/components/onboarding/OnboardingWizard';
import GettingStartedCard from '@/components/dashboard/GettingStartedCard';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import { Position, CompletedTrade } from '@/types/api';
import { useAlerts } from '@/contexts/AlertContext';
import { useBroker } from '@/contexts/BrokerContext';
import { useWebSocket } from '@/contexts/WebSocketContext';
import { useOnboarding } from '@/hooks/useOnboarding';
import { useMargins } from '@/hooks/useMargins';

type PositionWithExtras = Position & { instrument_type: string; unrealized_pnl: number; current_value: number };

interface RiskStateData {
  risk_state: 'safe' | 'caution' | 'danger';
  status_message: string;
  active_patterns: string[];
  unrealized_pnl: number;
  ai_recommendations: string[];
  last_synced: string;
}


export default function Dashboard() {
  const navigate = useNavigate();
  const { isConnected, isLoading: brokerLoading, account, connect, syncTrades, syncStatus, syncError, isTokenExpired } = useBroker();
  const { lastTradeEvent } = useWebSocket();
  const { alerts, acknowledgeAlert } = useAlerts();
  const { showOnboarding, completeOnboarding, skipOnboarding, reopenOnboarding, status: onboardingStatus } = useOnboarding();

  // Stabilize account id to prevent callback churn
  const accountId = account?.id;
  const lastSyncAt = account?.last_sync_at;

  // Fetch real margin data from Kite API
  const { margins, insights: marginInsights, isLoading: marginsLoading, refetch: refetchMargins } = useMargins(accountId);

  // Fetch holdings
  const { holdings, summary: holdingsSummary, isLoading: holdingsLoading } = useHoldings(accountId);

  const [isSyncing, setIsSyncing] = useState(false);
  const [positions, setPositions] = useState<PositionWithExtras[]>([]);
  const [positionsLoading, setPositionsLoading] = useState(false);
  const [positionsError, setPositionsError] = useState<string | null>(null);
  const [closedTrades, setClosedTrades] = useState<CompletedTrade[]>([]);
  const [tradesLoading, setTradesLoading] = useState(false);
  const [tradesError, setTradesError] = useState<string | null>(null);
  const [riskState, setRiskState] = useState<RiskStateData | null>(null);
  const [dataLoaded, setDataLoaded] = useState(false);
  // Session P&L in its own state — never wiped during riskState refetches
  const [sessionPnlDisplay, setSessionPnlDisplay] = useState<number>(0);

  const [tradeStats, setTradeStats] = useState<{
    trades_today: number;
    win_rate: number;
    max_drawdown: number;
    risk_used: number;
    margin_utilization?: number;
    margin_available?: number;
  } | null>(null);

  const [journalOpen, setJournalOpen] = useState(false);
  const [selectedTrade, setSelectedTrade] = useState<PositionWithExtras | CompletedTrade | null>(null);
  const [selectedType, setSelectedType] = useState<'position' | 'closed'>('position');

  // Capital prompt — shown when trading_capital is not set
  const [showCapitalPrompt, setShowCapitalPrompt] = useState(false);
  const [capitalInput, setCapitalInput] = useState('');
  const [capitalSaving, setCapitalSaving] = useState(false);

  // Use ref for account id in fetch callbacks to avoid recreating them
  const accountIdRef = useRef(accountId);
  accountIdRef.current = accountId;

  // Track whether we've already fetched for this sync cycle
  const fetchedForSyncRef = useRef<string | null>(null);

  // Fetch positions - stable callback (no account in deps)
  const fetchPositions = useCallback(async () => {
    const id = accountIdRef.current;
    if (!id) return;

    try {
      setPositionsLoading(true);
      setPositionsError(null);
      const response = await api.get('/api/positions/');

      const transformedPositions = (response.data.positions || []).map((pos: any) => ({
        ...pos,
        instrument_type: pos.instrument_type || 'OPTION',
        unrealized_pnl: parseFloat(pos.unrealized_pnl) || parseFloat(pos.pnl) || 0,
        current_value: pos.last_price
          ? parseFloat(pos.last_price) * Math.abs(pos.total_quantity || 0)
          : (parseFloat(pos.average_entry_price) || 0) * Math.abs(pos.total_quantity || 0),
        last_price: parseFloat(pos.last_price) || 0,
        day_pnl: parseFloat(pos.day_pnl) || 0
      }));

      setPositions(transformedPositions);
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || 'Failed to fetch positions';
      console.error('Error fetching positions:', msg);
      setPositionsError(msg);
    } finally {
      setPositionsLoading(false);
    }
  }, []);

  // Fetch completed trades (flat-to-flat rounds) - stable callback
  const fetchTrades = useCallback(async () => {
    const id = accountIdRef.current;
    if (!id) return;

    try {
      setTradesLoading(true);
      setTradesError(null);
      const response = await api.get('/api/trades/completed', {
        params: { limit: 50 }
      });

      const trades: CompletedTrade[] = (response.data.trades || []).map((t: any) => ({
        id: t.id,
        broker_account_id: t.broker_account_id,
        tradingsymbol: t.tradingsymbol,
        exchange: t.exchange,
        instrument_type: t.instrument_type || '',
        product: t.product || '',
        direction: t.direction,
        total_quantity: t.total_quantity || 0,
        num_entries: t.num_entries || 1,
        num_exits: t.num_exits || 1,
        avg_entry_price: parseFloat(t.avg_entry_price) || 0,
        avg_exit_price: parseFloat(t.avg_exit_price) || 0,
        realized_pnl: parseFloat(t.realized_pnl) || 0,
        entry_time: t.entry_time,
        exit_time: t.exit_time,
        duration_minutes: t.duration_minutes || 0,
        closed_by_flip: t.closed_by_flip || false,
        entry_trade_ids: t.entry_trade_ids || [],
        exit_trade_ids: t.exit_trade_ids || [],
        status: t.status || 'closed',
        created_at: t.created_at,
      }));

      setClosedTrades(trades);
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || 'Failed to fetch trades';
      console.error('Error fetching trades:', msg);
      setTradesError(msg);
    } finally {
      setTradesLoading(false);
    }
  }, []);

  // Fetch risk state - stable callback
  const fetchRiskState = useCallback(async () => {
    const id = accountIdRef.current;
    if (!id) return;

    try {
      const response = await api.get('/api/risk/state');

      const data = response.data;
      setRiskState({
        risk_state: data.risk_state || 'safe',
        status_message: data.risk_state === 'danger' ? 'High Risk Zone' :
          data.risk_state === 'caution' ? 'Caution Advised' : 'Trading Safely',
        active_patterns: data.active_patterns || [],
        unrealized_pnl: 0,
        ai_recommendations: data.recommendations || [],
        last_synced: lastSyncAt ? `Synced ${formatTimeAgo(lastSyncAt)}` : 'Not synced yet'
      });
    } catch (err: any) {
      console.error('Error fetching risk state:', err);
      setRiskState({
        risk_state: 'safe',
        status_message: 'Unable to fetch risk state',
        active_patterns: [],
        unrealized_pnl: 0,
        ai_recommendations: [],
        last_synced: 'Unknown'
      });
    }
  }, [lastSyncAt]);

  // Fetch all dashboard data - stable callback (no account dependency)
  const fetchAllData = useCallback(async () => {
    if (!accountIdRef.current) return;
    await Promise.all([
      fetchPositions(),
      fetchTrades(),
      fetchRiskState(),
    ]);
    setDataLoaded(true);
  }, [fetchPositions, fetchTrades, fetchRiskState]);

  // Load data immediately on connect — don't wait for sync
  useEffect(() => {
    if (!isConnected || !accountId) return;
    const fetchKey = `connect-${accountId}`;
    if (fetchedForSyncRef.current === fetchKey) return;
    fetchedForSyncRef.current = fetchKey;
    fetchAllData();

    // Check if trading_capital is set — needed for position sizing alerts
    const dismissed = localStorage.getItem(`capital_prompt_dismissed_${accountId}`);
    if (!dismissed) {
      api.get('/api/profile/').then((res) => {
        const capital = res.data?.profile?.trading_capital;
        if (!capital) setShowCapitalPrompt(true);
      }).catch(() => {/* non-critical */});
    }
  }, [isConnected, accountId, fetchAllData]);

  // Re-fetch silently when sync completes (gets latest fills)
  useEffect(() => {
    if (syncStatus === 'success' && isConnected && accountId) {
      fetchAllData();
    }
  }, [syncStatus]); // eslint-disable-line react-hooks/exhaustive-deps

  // React to WebSocket trade events — no polling needed.
  // When Celery processes a trade (webhook → FIFO → BehaviorEngine),
  // it publishes to Redis → FastAPI forwards via WebSocket → lastTradeEvent changes.
  // This replaces ALL time-based polling for trade and position data.
  useEffect(() => {
    if (!lastTradeEvent || !isConnected || isTokenExpired) return;
    // Silent background refresh — no loading spinner
    fetchTrades();
    fetchPositions();
  }, [lastTradeEvent]); // eslint-disable-line react-hooks/exhaustive-deps

  // Calculate trade stats + session P&L (D1: realized+unrealized, D2: IST date, D4: real margin)
  useEffect(() => {
    // Today boundary in browser local time (IST for Indian users)
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    // Today's completed trades
    const todayTrades = closedTrades.filter(t => new Date(t.exit_time) >= today);
    const winners = todayTrades.filter(t => t.realized_pnl > 0);

    // Realized P&L from today's closed trades
    const realizedPnl = todayTrades.reduce((sum, t) => sum + t.realized_pnl, 0);

    // Unrealized P&L from open positions
    const unrealizedPnl = positions.reduce((sum, p) => sum + (p.unrealized_pnl || 0), 0);

    // Session P&L = realized + unrealized (broker standard: Zerodha, Sensibull)
    const sessionPnl = realizedPnl + unrealizedPnl;

    // Max drawdown from completed trades sequence
    let cumPnl = 0;
    let peak = 0;
    let maxDrawdown = 0;
    for (const trade of todayTrades) {
      cumPnl += trade.realized_pnl;
      if (cumPnl > peak) peak = cumPnl;
      const drawdown = peak - cumPnl;
      if (drawdown > maxDrawdown) maxDrawdown = drawdown;
    }

    // Real margin utilization from Kite API (replaces hardcoded trades/10 formula)
    const marginUtilization = margins?.overall?.max_utilization_pct ?? 0;

    setTradeStats({
      trades_today: todayTrades.length,
      win_rate: todayTrades.length > 0 ? (winners.length / todayTrades.length) * 100 : 0,
      max_drawdown: -maxDrawdown,
      risk_used: marginUtilization,
      margin_utilization: marginUtilization || undefined,
      margin_available: margins?.equity?.available ?? undefined,
    });

    // Store session P&L in dedicated state (never wiped during riskState refetches)
    setSessionPnlDisplay(sessionPnl);
    // Also keep riskState in sync when it exists
    setRiskState(prev => prev ? { ...prev, unrealized_pnl: sessionPnl } : prev);
  }, [closedTrades, positions, margins]);

  const handleSaveCapital = async () => {
    const val = parseFloat(capitalInput.replace(/,/g, ''));
    if (!val || val <= 0) return;
    setCapitalSaving(true);
    try {
      await api.put('/api/profile/', { trading_capital: val });
      setShowCapitalPrompt(false);
      localStorage.setItem(`capital_prompt_dismissed_${accountId}`, '1');
    } catch {
      // Non-critical — just dismiss
      setShowCapitalPrompt(false);
    } finally {
      setCapitalSaving(false);
    }
  };

  const handleDismissCapital = () => {
    setShowCapitalPrompt(false);
    if (accountId) localStorage.setItem(`capital_prompt_dismissed_${accountId}`, '1');
  };

  const handleSync = async () => {
    setIsSyncing(true);
    try {
      // Reset dedup key BEFORE sync so the effect can trigger a fresh fetch
      fetchedForSyncRef.current = null;
      await syncTrades();
      // syncTrades sets syncStatus='success', which triggers fetchAllData via the useEffect above.
      // No manual fetchAllData call needed — the effect handles it.
    } catch (err) {
      console.error('Sync failed:', err);
    } finally {
      setIsSyncing(false);
    }
  };


  const handlePositionClick = (position: PositionWithExtras) => {
    setSelectedTrade(position);
    setSelectedType('position');
    setJournalOpen(true);
  };

  const handleTradeClick = (trade: CompletedTrade) => {
    setSelectedTrade(trade);
    setSelectedType('closed');
    setJournalOpen(true);
  };

  // Alert list for RecentAlertsCard — backend risk_alerts is the single source of truth
  const mergedAlerts = useMemo(() => {
    const twoDaysAgo = Date.now() - 48 * 60 * 60 * 1000;
    return alerts
      .filter(a => new Date(a.shown_at).getTime() > twoDaysAgo)
      .map(a => ({
        id: a.id,
        pattern_name: a.pattern.name,
        pattern: a.pattern.name,
        pattern_type: a.pattern.type,
        severity: (a.pattern.severity === 'low' ? 'medium' : a.pattern.severity) as 'critical' | 'high' | 'medium' | 'positive',
        description: a.pattern.description,
        message: a.pattern.description,
        why_it_matters: a.pattern.insight,
        timestamp: a.shown_at,
        acknowledged: a.acknowledged,
      }))
      .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
      .slice(0, 8);
  }, [alerts]);

  const recentTrades = useMemo(() => {
    const threeDaysAgo = Date.now() - 3 * 24 * 60 * 60 * 1000;
    return closedTrades.filter(t => new Date(t.exit_time).getTime() > threeDaysAgo);
  }, [closedTrades]);

  // Show loading state
  if (brokerLoading) {
    return (
      <div className="w-full min-h-[60vh] flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  // Show connect prompt if not connected
  if (!isConnected) {
    return (
      <div className="w-full min-h-[60vh] flex flex-col items-center justify-center animate-fade-in-up">
        <div className="p-4 rounded-full bg-primary/10 mb-6">
          <Link2 className="h-12 w-12 text-primary" />
        </div>
        <h2 className="text-2xl font-semibold text-foreground mb-2">Connect Your Broker</h2>
        <p className="text-muted-foreground text-center max-w-md mb-6">
          Connect your Zerodha account to start monitoring your trading behavior and get personalized insights.
        </p>
        <Button size="lg" className="gap-2" onClick={() => connect()}>
          <Link2 className="h-5 w-5" />
          Connect Zerodha
        </Button>
      </div>
    );
  }

  // Show sync error with retry (only if we have no data at all and not currently loading)
  if (syncStatus === 'error' && !dataLoaded && !positionsLoading && !tradesLoading) {
    return (
      <div className="w-full min-h-[60vh] flex flex-col items-center justify-center gap-4">
        <div className="p-4 rounded-full bg-destructive/10">
          <AlertTriangle className="h-10 w-10 text-destructive" />
        </div>
        <div className="text-center">
          <h2 className="text-lg font-semibold text-foreground">Sync Failed</h2>
          <p className="text-sm text-muted-foreground mt-1 max-w-md">
            {syncError || 'Could not sync data from Zerodha. This may be a temporary issue.'}
          </p>
        </div>
        <Button onClick={handleSync} variant="outline" className="gap-2">
          <RefreshCw className="h-4 w-4" />
          Retry Sync
        </Button>
      </div>
    );
  }

  // Default risk state while loading
  const displayRiskState = {
    ...(riskState || {
      risk_state: 'safe' as const,
      status_message: 'Loading...',
      active_patterns: [],
      ai_recommendations: [],
      last_synced: 'Loading...'
    }),
    // Use stable sessionPnlDisplay — never flickers to 0 during riskState refetches
    unrealized_pnl: sessionPnlDisplay,
  };

  return (
    <div className="w-full min-h-screen">
      {/* Degraded mode banner — token expired but historical data still works */}
      {isTokenExpired && dataLoaded && (
        <div className="mb-4 p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-between animate-fade-in-up">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-amber-600 dark:text-amber-400" />
            <span className="text-sm text-amber-700 dark:text-amber-300">
              Live sync paused — showing last known data. Analytics, chat and history still work.
            </span>
          </div>
        </div>
      )}

      {/* Capital prompt — one-time, dismissible, enables position sizing alerts */}
      {showCapitalPrompt && dataLoaded && (
        <div className="mb-4 p-3 rounded-lg bg-primary/5 border border-primary/20 flex flex-wrap items-center gap-3 animate-fade-in-up">
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-foreground">
              Enable position sizing alerts
            </p>
            <p className="text-xs text-muted-foreground mt-0.5">
              Without your trading capital, we can't detect when a single trade is oversized. Takes 5 seconds.
            </p>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <span className="text-sm text-muted-foreground">₹</span>
            <input
              type="number"
              placeholder="e.g. 500000"
              value={capitalInput}
              onChange={(e) => setCapitalInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSaveCapital()}
              className="w-32 px-2 py-1.5 text-sm bg-background border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-ring"
            />
            <button
              onClick={handleSaveCapital}
              disabled={!capitalInput || capitalSaving}
              className="px-3 py-1.5 text-sm bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 disabled:opacity-50"
            >
              {capitalSaving ? <Loader2 className="h-3 w-3 animate-spin" /> : 'Save'}
            </button>
            <button onClick={handleDismissCapital} className="text-muted-foreground hover:text-foreground">
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}

      {/* Sync error banner (when data is loaded but sync had errors) */}
      {syncStatus === 'error' && dataLoaded && !isTokenExpired && (
        <div className="mb-4 p-3 rounded-lg bg-destructive/10 border border-destructive/20 flex items-center justify-between animate-fade-in-up">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-destructive" />
            <span className="text-sm text-destructive">
              Sync failed: {syncError || 'Could not refresh data'}. Showing cached data.
            </span>
          </div>
          <Button onClick={handleSync} variant="ghost" size="sm" className="gap-1 text-destructive">
            <RefreshCw className="h-3 w-3" />
            Retry
          </Button>
        </div>
      )}

      {/* Getting Started — shown to new users until they have data */}
      <GettingStartedCard
        tradeCount={closedTrades.length}
        onboardingCompleted={onboardingStatus?.completed ?? false}
        onOpenWizard={reopenOnboarding}
      />

      {/* Page Header */}
      <div className="mb-6 animate-fade-in-up flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-foreground tracking-tight">Dashboard</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Real-time trading behavior monitoring</p>
        </div>
        <div className="shrink-0 text-right">
          {(() => {
            const now = new Date();
            // Convert to IST: UTC + 5h30m. Use UTC getters on the shifted timestamp.
            // Do NOT subtract browser timezone offset — getTime() is always UTC.
            const ist = new Date(now.getTime() + 5.5 * 60 * 60 * 1000);
            const h = ist.getUTCHours(), m = ist.getUTCMinutes(), day = ist.getUTCDay();
            const isOpen = day >= 1 && day <= 5 &&
              (h > 9 || (h === 9 && m >= 15)) && (h < 15 || (h === 15 && m <= 30));
            const dateStr = now.toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short' });
            return (
              <>
                <p className="text-sm text-muted-foreground">{dateStr}</p>
                <div className="flex items-center justify-end gap-1.5 mt-0.5">
                  <span className={`w-1.5 h-1.5 rounded-full ${isOpen ? 'bg-emerald-500' : 'bg-muted-foreground/40'}`} />
                  <span className="text-xs text-muted-foreground">
                    {isOpen ? 'Market Open · 09:15–15:30' : 'Market Closed'}
                  </span>
                </div>
              </>
            );
          })()}
        </div>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-12 gap-6 lg:gap-8">
        {/* Hero Card - Full width */}
        <div className="col-span-12 animate-fade-in-up" style={{ animationDelay: '40ms' }}>
          <RiskGuardianCard
            data={displayRiskState}
            stats={tradeStats || undefined}
            onSync={handleSync}
            isLoading={isSyncing}
          />
        </div>

        {/* Left Column - Positions & Trades (priority content) */}
        <div className="col-span-12 lg:col-span-8 space-y-6 lg:space-y-8">
          <div className="animate-fade-in-up" style={{ animationDelay: '80ms' }}>
            {positionsError && !positionsLoading && positions.length === 0 ? (
              <div className="rounded-xl border border-destructive/20 bg-card p-6 text-center">
                <AlertTriangle className="h-6 w-6 text-destructive mx-auto mb-2" />
                <p className="text-sm text-muted-foreground">{positionsError}</p>
                <Button onClick={fetchPositions} variant="ghost" size="sm" className="mt-2">
                  Retry
                </Button>
              </div>
            ) : (
              <OpenPositionsTable
                positions={positions}
                isLoading={positionsLoading}
                onPositionClick={handlePositionClick}
              />
            )}
          </div>
          <div className="animate-fade-in-up" style={{ animationDelay: '120ms' }}>
            {tradesError && !tradesLoading && closedTrades.length === 0 ? (
              <div className="rounded-xl border border-destructive/20 bg-card p-6 text-center">
                <AlertTriangle className="h-6 w-6 text-destructive mx-auto mb-2" />
                <p className="text-sm text-muted-foreground">{tradesError}</p>
                <Button onClick={fetchTrades} variant="ghost" size="sm" className="mt-2">
                  Retry
                </Button>
              </div>
            ) : (
              <ClosedTradesTable
                trades={recentTrades}
                isLoading={tradesLoading}
                onTradeClick={handleTradeClick}
              />
            )}
          </div>
        </div>

        {/* Right Sidebar - Alerts & Monitoring */}
        <div className="col-span-12 lg:col-span-4 space-y-6 lg:space-y-8">
          <div className="animate-fade-in-up" style={{ animationDelay: '80ms' }}>
            <RecentAlertsCard
              alerts={mergedAlerts}
              onAcknowledge={acknowledgeAlert}
            />
          </div>
          {accountId && (
            <div className="animate-fade-in-up" style={{ animationDelay: '120ms' }}>
              <PredictiveWarningsCard brokerAccountId={accountId} />
            </div>
          )}
          <div className="animate-fade-in-up" style={{ animationDelay: '160ms' }}>
            <BlowupShieldCard />
          </div>
          {accountId && (
            <div className="animate-fade-in-up" style={{ animationDelay: '200ms' }}>
              <ProgressTrackingCard brokerAccountId={accountId} />
            </div>
          )}
          {holdings.length > 0 && holdingsSummary && (
            <div className="animate-fade-in-up" style={{ animationDelay: '240ms' }}>
              <HoldingsCard
                holdings={holdings}
                summary={holdingsSummary}
                isLoading={holdingsLoading}
              />
            </div>
          )}
        </div>

        {/* Margin Cards - Lower priority, full width at bottom */}
        {margins && (
          <>
            <div className="col-span-12 lg:col-span-6 animate-fade-in-up" style={{ animationDelay: '160ms' }}>
              <MarginStatusCard
                margins={margins}
                isLoading={marginsLoading}
                onRefresh={refetchMargins}
              />
            </div>
            <div className="col-span-12 lg:col-span-6 animate-fade-in-up" style={{ animationDelay: '200ms' }}>
              <MarginInsightsCard
                insights={marginInsights}
                isLoading={marginsLoading}
              />
            </div>
          </>
        )}
      </div>

      {/* Trade Journal Sheet */}
      <TradeJournalSheet
        open={journalOpen}
        onOpenChange={setJournalOpen}
        trade={selectedTrade}
        type={selectedType}
      />

      {/* Onboarding Wizard */}
      {showOnboarding && account?.id && (
        <OnboardingWizard
          brokerAccountId={account.id}
          onComplete={completeOnboarding}
          onSkip={skipOnboarding}
        />
      )}
    </div>
  );
}

function formatTimeAgo(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSecs = Math.floor(diffMs / 1000);
  const diffMins = Math.floor(diffSecs / 60);
  const diffHours = Math.floor(diffMins / 60);

  if (diffSecs < 60) return 'just now';
  if (diffMins < 60) return `${diffMins} min ago`;
  if (diffHours < 24) return `${diffHours} hours ago`;
  return date.toLocaleDateString();
}
