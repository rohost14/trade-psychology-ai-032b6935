import { useState, useEffect, useMemo, useCallback } from 'react';
import { motion, type Variants } from 'framer-motion';
import { Link } from 'react-router-dom';
import { Link2, Loader2 } from 'lucide-react';
import RiskGuardianCard from '@/components/dashboard/RiskGuardianCard';
import MoneySavedCard from '@/components/dashboard/MoneySavedCard';
import RecentAlertsCard from '@/components/dashboard/RecentAlertsCard';
import OpenPositionsTable from '@/components/dashboard/OpenPositionsTable';
import ClosedTradesTable from '@/components/dashboard/ClosedTradesTable';
import { TradeJournalSheet } from '@/components/dashboard/TradeJournalSheet';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import { Position, Trade, Alert, MoneySaved } from '@/types/api';
import { useAlerts } from '@/contexts/AlertContext';
import { useBroker } from '@/contexts/BrokerContext';

type PositionWithExtras = Position & { instrument_type: string; unrealized_pnl: number; current_value: number };

interface RiskStateData {
  risk_state: 'safe' | 'caution' | 'danger';
  status_message: string;
  active_patterns: string[];
  unrealized_pnl: number;
  ai_recommendations: string[];
  last_synced: string;
}

// Refined spring animations - Cred-inspired
const containerVariants: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1,
      delayChildren: 0.05,
    },
  },
};

const itemVariants: Variants = {
  hidden: { opacity: 0, y: 24, scale: 0.98 },
  visible: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: {
      type: 'spring',
      stiffness: 120,
      damping: 20,
      mass: 0.8,
    },
  },
};

const heroVariants: Variants = {
  hidden: { opacity: 0, y: 32, scale: 0.96 },
  visible: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: {
      type: 'spring',
      stiffness: 100,
      damping: 22,
      mass: 1,
      delay: 0.1,
    },
  },
};

const sidebarVariants: Variants = {
  hidden: { opacity: 0, x: 20 },
  visible: {
    opacity: 1,
    x: 0,
    transition: {
      type: 'spring',
      stiffness: 120,
      damping: 20,
      staggerChildren: 0.1,
      delayChildren: 0.2,
    },
  },
};

export default function Dashboard() {
  const { isConnected, isLoading: brokerLoading, account, syncTrades } = useBroker();
  const { patterns, runAnalysis, acknowledgeAlert: acknowledgePatternAlert } = useAlerts();

  const [isLoading, setIsLoading] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [positions, setPositions] = useState<PositionWithExtras[]>([]);
  const [positionsLoading, setPositionsLoading] = useState(false);
  const [closedTrades, setClosedTrades] = useState<Trade[]>([]);
  const [tradesLoading, setTradesLoading] = useState(false);
  const [riskState, setRiskState] = useState<RiskStateData | null>(null);
  const [moneySaved, setMoneySaved] = useState<MoneySaved | null>(null);

  const [tradeStats, setTradeStats] = useState<{
    trades_today: number;
    win_rate: number;
    max_drawdown: number;
    risk_used: number;
  } | null>(null);

  const [journalOpen, setJournalOpen] = useState(false);
  const [selectedTrade, setSelectedTrade] = useState<PositionWithExtras | Trade | null>(null);
  const [selectedType, setSelectedType] = useState<'position' | 'closed'>('position');

  // Fetch positions
  const fetchPositions = useCallback(async () => {
    if (!account) return;

    try {
      setPositionsLoading(true);
      const response = await api.get('/api/positions/', {
        params: { broker_account_id: account.id }
      });

      const transformedPositions = (response.data.positions || []).map((pos: any) => ({
        ...pos,
        instrument_type: pos.instrument_type || 'OPTION',
        unrealized_pnl: parseFloat(pos.realized_pnl) || 0,
        current_value: (parseFloat(pos.average_entry_price) || 0) * (pos.total_quantity || 0)
      }));

      setPositions(transformedPositions);
    } catch (err: any) {
      console.error('Error fetching positions:', err);
    } finally {
      setPositionsLoading(false);
    }
  }, [account]);

  // Fetch trades
  const fetchTrades = useCallback(async () => {
    if (!account) return;

    try {
      setTradesLoading(true);
      const response = await api.get('/api/trades/', {
        params: {
          broker_account_id: account.id,
          limit: 50,
          status: 'COMPLETE'
        }
      });

      // Transform backend trade format to frontend format
      const trades: Trade[] = (response.data.trades || []).map((t: any) => ({
        id: t.id,
        tradingsymbol: t.tradingsymbol,
        exchange: t.exchange,
        trade_type: t.transaction_type === 'BUY' ? 'BUY' : 'SELL',
        quantity: t.filled_quantity || t.quantity,
        price: t.average_price || t.price,
        pnl: t.pnl || 0,
        traded_at: t.order_timestamp || t.created_at,
        order_id: t.order_id
      }));

      setClosedTrades(trades);
    } catch (err: any) {
      console.error('Error fetching trades:', err);
    } finally {
      setTradesLoading(false);
    }
  }, [account]);

  // Fetch risk state
  const fetchRiskState = useCallback(async () => {
    if (!account) return;

    try {
      const response = await api.get('/api/risk/state', {
        params: { broker_account_id: account.id }
      });

      const data = response.data;
      setRiskState({
        risk_state: data.risk_state || 'safe',
        status_message: data.risk_state === 'danger' ? 'High Risk Zone' :
                       data.risk_state === 'caution' ? 'Caution Advised' : 'Trading Safely',
        active_patterns: data.active_patterns || [],
        unrealized_pnl: 0, // Will calculate from positions
        ai_recommendations: data.recommendations || [],
        last_synced: account.last_sync_at ? `Synced ${formatTimeAgo(account.last_sync_at)}` : 'Not synced yet'
      });
    } catch (err: any) {
      console.error('Error fetching risk state:', err);
      // Set default safe state on error
      setRiskState({
        risk_state: 'safe',
        status_message: 'Unable to fetch risk state',
        active_patterns: [],
        unrealized_pnl: 0,
        ai_recommendations: [],
        last_synced: 'Unknown'
      });
    }
  }, [account]);

  // Fetch money saved
  const fetchMoneySaved = useCallback(async () => {
    if (!account) return;

    try {
      const response = await api.get('/api/analytics/money-saved', {
        params: { broker_account_id: account.id }
      });

      setMoneySaved({
        all_time: response.data.all_time || 0,
        this_week: response.data.this_week || 0,
        this_month: response.data.this_month || 0,
        blowups_prevented: response.data.prevented_blowups || response.data.blowups_prevented || 0
      });
    } catch (err: any) {
      console.error('Error fetching money saved:', err);
      setMoneySaved({
        all_time: 0,
        this_week: 0,
        this_month: 0,
        blowups_prevented: 0
      });
    }
  }, [account]);

  // Load all data when account is available
  useEffect(() => {
    if (isConnected && account) {
      fetchPositions();
      fetchTrades();
      fetchRiskState();
      fetchMoneySaved();
    }
  }, [isConnected, account, fetchPositions, fetchTrades, fetchRiskState, fetchMoneySaved]);

  // Run pattern analysis when trades are loaded
  useEffect(() => {
    if (closedTrades.length > 0) {
      runAnalysis(closedTrades);
    }
  }, [closedTrades, runAnalysis]);

  // Calculate trade stats from trades
  useEffect(() => {
    if (closedTrades.length > 0) {
      const today = new Date();
      today.setHours(0, 0, 0, 0);

      const todayTrades = closedTrades.filter(t => new Date(t.traded_at) >= today);
      const winners = todayTrades.filter(t => t.pnl > 0);
      const losers = todayTrades.filter(t => t.pnl < 0);

      // Calculate max drawdown (cumulative low point)
      let cumPnl = 0;
      let peak = 0;
      let maxDrawdown = 0;
      for (const trade of todayTrades) {
        cumPnl += trade.pnl;
        if (cumPnl > peak) peak = cumPnl;
        const drawdown = peak - cumPnl;
        if (drawdown > maxDrawdown) maxDrawdown = drawdown;
      }

      setTradeStats({
        trades_today: todayTrades.length,
        win_rate: todayTrades.length > 0 ? (winners.length / todayTrades.length) * 100 : 0,
        max_drawdown: -maxDrawdown,
        risk_used: Math.min(100, Math.max(0, (todayTrades.length / 10) * 100)) // Rough estimate based on trade count
      });
    }
  }, [closedTrades]);

  // Calculate unrealized PnL from positions
  useEffect(() => {
    if (positions.length > 0 && riskState) {
      const totalUnrealizedPnl = positions.reduce((sum, p) => sum + (p.unrealized_pnl || 0), 0);
      setRiskState(prev => prev ? { ...prev, unrealized_pnl: totalUnrealizedPnl } : null);
    }
  }, [positions]);

  const handleSync = async () => {
    setIsSyncing(true);
    try {
      await syncTrades();
      // Refresh all data after sync
      await Promise.all([
        fetchPositions(),
        fetchTrades(),
        fetchRiskState(),
        fetchMoneySaved()
      ]);
    } catch (err) {
      console.error('Sync failed:', err);
    } finally {
      setIsSyncing(false);
    }
  };

  const handleAcknowledgeAlert = async (alertId: string) => {
    try {
      await api.post(`/api/risk/alerts/${alertId}/acknowledge`);
    } catch (err) {
      console.error('Error acknowledging alert:', err);
    }
    acknowledgePatternAlert(alertId);
  };

  const handlePositionClick = (position: PositionWithExtras) => {
    setSelectedTrade(position);
    setSelectedType('position');
    setJournalOpen(true);
  };

  const handleTradeClick = (trade: Trade) => {
    setSelectedTrade(trade);
    setSelectedType('closed');
    setJournalOpen(true);
  };

  const alertsFromPatterns: (Alert & { pattern: string; description: string; why_it_matters?: string })[] = useMemo(() => {
    return patterns.slice(0, 5).map((p) => ({
      id: p.id,
      pattern_name: p.name,
      pattern: p.name,
      severity: p.severity === 'critical' ? 'critical' :
               p.severity === 'high' ? 'high' :
               p.severity === 'medium' ? 'medium' : 'positive',
      description: p.description,
      message: p.description,
      why_it_matters: p.insight,
      timestamp: p.detected_at,
    }));
  }, [patterns]);

  const todaysTrades = useMemo(() => {
    const oneDayAgo = Date.now() - 24 * 60 * 60 * 1000;
    return closedTrades.filter(t => new Date(t.traded_at).getTime() > oneDayAgo);
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
        <Link to="/settings">
          <Button size="lg" className="gap-2">
            <Link2 className="h-5 w-5" />
            Connect Zerodha
          </Button>
        </Link>
      </motion.div>
    );
  }

  // Default risk state while loading
  const displayRiskState = riskState || {
    risk_state: 'safe' as const,
    status_message: 'Loading...',
    active_patterns: [],
    unrealized_pnl: 0,
    ai_recommendations: [],
    last_synced: 'Loading...'
  };

  const displayMoneySaved = moneySaved || {
    all_time: 0,
    this_week: 0,
    this_month: 0,
    blowups_prevented: 0
  };

  return (
    <motion.div
      className="w-full min-h-screen"
      initial="hidden"
      animate="visible"
      variants={containerVariants}
    >
      {/* Page Header with subtle entrance */}
      <motion.div className="mb-8" variants={itemVariants}>
        <motion.h1
          className="text-[28px] font-semibold text-foreground tracking-tight"
          initial={{ opacity: 0, x: -10 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.1, duration: 0.4 }}
        >
          Dashboard
        </motion.h1>
        <motion.p
          className="text-[15px] text-muted-foreground mt-1"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.2, duration: 0.4 }}
        >
          Real-time trading behavior monitoring
        </motion.p>
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

        {/* Left Column - Positions & Trades */}
        <motion.div
          className="col-span-12 lg:col-span-8 space-y-6 lg:space-y-8"
          variants={containerVariants}
        >
          <motion.div variants={itemVariants}>
            <OpenPositionsTable
              positions={positions}
              isLoading={positionsLoading}
              onPositionClick={handlePositionClick}
            />
          </motion.div>
          <motion.div variants={itemVariants}>
            <ClosedTradesTable
              trades={todaysTrades}
              isLoading={tradesLoading}
              onTradeClick={handleTradeClick}
            />
          </motion.div>
        </motion.div>

        {/* Right Sidebar */}
        <motion.div
          className="col-span-12 lg:col-span-4 space-y-6 lg:space-y-8"
          variants={sidebarVariants}
        >
          <motion.div variants={itemVariants}>
            <RecentAlertsCard
              alerts={alertsFromPatterns}
              onAcknowledge={handleAcknowledgeAlert}
            />
          </motion.div>
          <motion.div variants={itemVariants}>
            <MoneySavedCard data={displayMoneySaved} />
          </motion.div>
        </motion.div>
      </div>

      {/* Trade Journal Sheet */}
      <TradeJournalSheet
        open={journalOpen}
        onOpenChange={setJournalOpen}
        trade={selectedTrade}
        type={selectedType}
      />
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
