import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { motion, type Variants } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { Link2, Loader2, AlertTriangle, RefreshCw } from 'lucide-react';
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
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import { Position, Trade, CompletedTrade } from '@/types/api';
import { useAlerts } from '@/contexts/AlertContext';
import { useBroker } from '@/contexts/BrokerContext';
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

// Subtle, fast animations — data-first design (D9)
const containerVariants: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.04, delayChildren: 0.02 },
  },
};

const itemVariants: Variants = {
  hidden: { opacity: 0, y: 8 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.2, ease: 'easeOut' },
  },
};

const heroVariants: Variants = {
  hidden: { opacity: 0, y: 8 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.25, ease: 'easeOut' },
  },
};

const sidebarVariants: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.04, delayChildren: 0.1 },
  },
};

export default function Dashboard() {
  const navigate = useNavigate();
  const { isConnected, isLoading: brokerLoading, account, connect, syncTrades, syncStatus, syncError, isTokenExpired } = useBroker();
  const { alerts, runAnalysis, acknowledgeAlert } = useAlerts();
  const { showOnboarding, completeOnboarding, skipOnboarding } = useOnboarding();

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

  // Load data when sync completes or on initial mount
  // Uses a ref to prevent double-fetching for the same sync cycle
  useEffect(() => {
    if (!isConnected || !accountId) return;

    // Create a key for this fetch trigger to deduplicate
    const fetchKey = `${syncStatus}-${accountId}`;

    if (syncStatus === 'success' || syncStatus === 'error') {
      if (fetchedForSyncRef.current !== fetchKey) {
        fetchedForSyncRef.current = fetchKey;
        fetchAllData();
      }
    } else if (syncStatus === 'idle' && !dataLoaded) {
      if (fetchedForSyncRef.current !== fetchKey) {
        fetchedForSyncRef.current = fetchKey;
        fetchAllData();
      }
    }
  }, [isConnected, accountId, syncStatus, dataLoaded, fetchAllData]);

  // Run pattern analysis on TODAY's trades only (D14: use both entry + exit data)
  // Only analyzes today's trading session to avoid generating alerts for historical trades.
  // Creates entry AND exit events from each CompletedTrade so pattern detector
  // can analyze: rapid entries (overtrading), loss-exit→quick-entry (revenge),
  // entry price × qty (position sizing), win/loss ratio (loss aversion)
  useEffect(() => {
    if (closedTrades.length === 0) return;

    // Only analyze today's trades — not all 50 historical ones
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const todaysClosedTrades = closedTrades.filter(ct => new Date(ct.exit_time) >= today);

    // No trades today = no patterns to detect (market may be closed)
    if (todaysClosedTrades.length === 0) return;

    const mapped: Trade[] = [];
    for (const ct of todaysClosedTrades) {
      // Entry event — for overtrading detection, position sizing, FOMO
      mapped.push({
        id: `${ct.id}_entry`,
        tradingsymbol: ct.tradingsymbol,
        exchange: ct.exchange,
        trade_type: ct.direction === 'LONG' ? 'BUY' : 'SELL',
        quantity: ct.total_quantity,
        price: ct.avg_entry_price,
        pnl: 0,
        traded_at: ct.entry_time,
        instrument_type: ct.instrument_type,
        product: ct.product,
      });
      // Exit event — carries P&L for revenge trading, loss aversion
      mapped.push({
        id: `${ct.id}_exit`,
        tradingsymbol: ct.tradingsymbol,
        exchange: ct.exchange,
        trade_type: ct.direction === 'LONG' ? 'SELL' : 'BUY',
        quantity: ct.total_quantity,
        price: ct.avg_exit_price,
        pnl: ct.realized_pnl,
        traded_at: ct.exit_time,
        instrument_type: ct.instrument_type,
        product: ct.product,
      });
    }
    runAnalysis(mapped);
  }, [closedTrades, runAnalysis]);

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
      <motion.div
        className="w-full min-h-[60vh] flex flex-col items-center justify-center"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
      >
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
      </motion.div>
    );
  }

  // Show syncing state (only on initial load, not on manual re-sync)
  if (syncStatus === 'syncing' && !dataLoaded) {
    return (
      <div className="w-full min-h-[60vh] flex flex-col items-center justify-center gap-4">
        <Loader2 className="h-10 w-10 animate-spin text-primary" />
        <div className="text-center">
          <h2 className="text-lg font-semibold text-foreground">Syncing your trades...</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Fetching positions, orders, and holdings from Zerodha
          </p>
        </div>
      </div>
    );
  }

  // Show sync error with retry (only if we have no data at all)
  if (syncStatus === 'error' && !dataLoaded) {
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
    <motion.div
      className="w-full min-h-screen"
      initial="hidden"
      animate="visible"
      variants={containerVariants}
    >
      {/* Degraded mode banner — token expired but historical data still works */}
      {isTokenExpired && dataLoaded && (
        <motion.div
          className="mb-4 p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-between"
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-amber-600 dark:text-amber-400" />
            <span className="text-sm text-amber-700 dark:text-amber-300">
              Live sync paused — showing last known data. Analytics, chat and history still work.
            </span>
          </div>
        </motion.div>
      )}

      {/* Sync error banner (when data is loaded but sync had errors) */}
      {syncStatus === 'error' && dataLoaded && !isTokenExpired && (
        <motion.div
          className="mb-4 p-3 rounded-lg bg-destructive/10 border border-destructive/20 flex items-center justify-between"
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
        >
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
        </motion.div>
      )}

      {/* Page Header */}
      <motion.div className="mb-6" variants={itemVariants}>
        <h1 className="text-xl font-semibold text-foreground tracking-tight">Dashboard</h1>
        <p className="text-sm text-muted-foreground mt-0.5">Real-time trading behavior monitoring</p>
      </motion.div>

      {/* Main Grid */}
      <div className="grid grid-cols-12 gap-6 lg:gap-8">
        {/* Hero Card - Full width */}
        <motion.div className="col-span-12" variants={heroVariants}>
          <RiskGuardianCard
            data={displayRiskState}
            stats={tradeStats || undefined}
            onSync={handleSync}
            isLoading={isSyncing}
          />
        </motion.div>

        {/* Left Column - Positions & Trades (priority content) */}
        <motion.div
          className="col-span-12 lg:col-span-8 space-y-6 lg:space-y-8"
          variants={containerVariants}
        >
          <motion.div variants={itemVariants}>
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
          </motion.div>
          <motion.div variants={itemVariants}>
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
          </motion.div>
        </motion.div>

        {/* Right Sidebar - Alerts & Monitoring */}
        <motion.div
          className="col-span-12 lg:col-span-4 space-y-6 lg:space-y-8"
          variants={sidebarVariants}
        >
          <motion.div variants={itemVariants}>
            <RecentAlertsCard
              alerts={mergedAlerts}
              onAcknowledge={acknowledgeAlert}
            />
          </motion.div>
          {accountId && (
            <motion.div variants={itemVariants}>
              <PredictiveWarningsCard brokerAccountId={accountId} />
            </motion.div>
          )}
          <motion.div variants={itemVariants}>
            <BlowupShieldCard />
          </motion.div>
          {accountId && (
            <motion.div variants={itemVariants}>
              <ProgressTrackingCard brokerAccountId={accountId} />
            </motion.div>
          )}
          {holdings.length > 0 && holdingsSummary && (
            <motion.div variants={itemVariants}>
              <HoldingsCard
                holdings={holdings}
                summary={holdingsSummary}
                isLoading={holdingsLoading}
              />
            </motion.div>
          )}
        </motion.div>

        {/* Margin Cards - Lower priority, full width at bottom */}
        {margins && (
          <>
            <motion.div className="col-span-12 lg:col-span-6" variants={itemVariants}>
              <MarginStatusCard
                margins={margins}
                isLoading={marginsLoading}
                onRefresh={refetchMargins}
              />
            </motion.div>
            <motion.div className="col-span-12 lg:col-span-6" variants={itemVariants}>
              <MarginInsightsCard
                insights={marginInsights}
                isLoading={marginsLoading}
              />
            </motion.div>
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
    </motion.div>
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
