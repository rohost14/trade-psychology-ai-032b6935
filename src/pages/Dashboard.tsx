import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Link } from 'react-router-dom';
import { Link2, Loader2, AlertTriangle, RefreshCw, X, Bot, ArrowRight } from 'lucide-react';
import BlowupShieldCard from '@/components/dashboard/BlowupShieldCard';
import RecentAlertsCard from '@/components/dashboard/RecentAlertsCard';
import AlertDetailSheet from '@/components/alerts/AlertDetailSheet';
import OpenPositionsTable from '@/components/dashboard/OpenPositionsTable';
import ClosedTradesTable from '@/components/dashboard/ClosedTradesTable';
import HoldingsCard from '@/components/dashboard/HoldingsCard';
import PredictiveWarningsCard from '@/components/dashboard/PredictiveWarningsCard';
import SessionPaceGoalCard from '@/components/dashboard/SessionPaceGoalCard';
import { useHoldings } from '@/hooks/useHoldings';
import { TradeJournalSheet } from '@/components/dashboard/TradeJournalSheet';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { formatCurrencyWithSign } from '@/lib/formatters';
import { api, apiDetailString } from '@/lib/api';
import { Position, CompletedTrade } from '@/types/api';
import { useAlerts, AlertNotification } from '@/contexts/AlertContext';
import { useBroker } from '@/contexts/BrokerContext';
import { useWebSocket } from '@/contexts/WebSocketContext';

type PositionWithExtras = Position & { instrument_type: string; unrealized_pnl: number; current_value: number };

interface RiskStateData {
  risk_state: 'safe' | 'caution' | 'danger';
  status_message: string;
  active_patterns: string[];
  unrealized_pnl: number;
  ai_recommendations: string[];
  last_synced: string;
}

// ─── Session State ────────────────────────────────────────────────────────────
const STATE_CFG = {
  stable: {
    label:  'On Track',
    pill:   'bg-teal-100 dark:bg-teal-900/40 text-teal-700 dark:text-teal-300',
    dot:    'bg-teal-500',
    accent: 'border-l-[3px] border-l-teal-400 dark:border-l-teal-500',
  },
  caution: {
    label:  'Patterns',          // behavioral patterns noted — NOT financial caution
    pill:   'bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300',
    dot:    'bg-amber-500',
    accent: 'border-l-[3px] border-l-amber-400 dark:border-l-amber-500',
  },
  risk: {
    label:  'High Alert',        // multiple/critical patterns — review immediately
    pill:   'bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300',
    dot:    'bg-red-500',
    accent: 'border-l-[3px] border-l-red-400 dark:border-l-red-500',
  },
};

type SessionState = keyof typeof STATE_CFG;

function getSessionState(unreadCount: number, highSevCount: number): SessionState {
  if (highSevCount >= 2 || unreadCount >= 5) return 'risk';
  if (highSevCount >= 1 || unreadCount >= 2) return 'caution';
  return 'stable';
}

function getSessionDesc(
  state: SessionState,
  unreadCount: number,
  tradesCount: number,
  winRate: number,
): string {
  if (state === 'risk') {
    return highSevPattern(unreadCount)
      ? `${unreadCount} high-severity pattern${unreadCount !== 1 ? 's' : ''} active — review before your next trade`
      : 'Multiple patterns detected — trade with extra caution this session';
  }
  if (state === 'caution') {
    if (unreadCount > 0)
      return `${unreadCount} behavioral pattern${unreadCount !== 1 ? 's' : ''} noted — review before continuing`;
    return 'Session elevated — stay within your plan';
  }
  if (tradesCount === 0) return 'No trades yet — session tracking is ready';
  if (winRate > 0 && winRate < 40) return `Win rate at ${winRate}% — focus on setup quality, not frequency`;
  return 'Session tracking normally — keep following your plan';
}
function highSevPattern(count: number) { return count >= 2; }

// ─── P&L Sparkline ────────────────────────────────────────────────────────────
function PnlSparkline({ closed, unrealized, positive }: {
  closed: CompletedTrade[]; unrealized: number; positive: boolean;
}) {
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const todayTrades = closed.filter(t => new Date(t.exit_time) >= today);

  const points: number[] = [0];
  let cum = 0;
  for (const t of todayTrades) { cum += t.realized_pnl; points.push(cum); }
  points.push(cum + unrealized);

  if (points.length < 2) {
    return <div className="flex-1 flex items-center justify-center text-[11px] text-muted-foreground/50">No data yet</div>;
  }

  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min || 1;
  const W = 200; const H = 72;
  const toX = (i: number) => (i / (points.length - 1)) * W;
  const toY = (v: number) => H - ((v - min) / range) * (H * 0.85) - H * 0.075;
  const zeroY = toY(0);

  const linePath = points.map((v, i) => `${i === 0 ? 'M' : 'L'}${toX(i).toFixed(1)},${toY(v).toFixed(1)}`).join(' ');
  const areaPath = `${linePath} L${W},${zeroY.toFixed(1)} L0,${zeroY.toFixed(1)} Z`;

  const lineColor = positive ? 'var(--tm-profit, #16A34A)' : 'var(--tm-loss, #DC2626)';
  const gradId = `spk-${positive ? 'p' : 'l'}`;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="flex-1 w-full">
      <defs>
        <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={lineColor} stopOpacity="0.18" />
          <stop offset="100%" stopColor={lineColor} stopOpacity="0.02" />
        </linearGradient>
      </defs>
      <line x1="0" y1={zeroY} x2={W} y2={zeroY} stroke="currentColor" strokeOpacity="0.12" strokeWidth="1" strokeDasharray="3 3" className="text-muted-foreground" />
      <path d={areaPath} fill={`url(#${gradId})`} />
      <path d={linePath} fill="none" stroke={lineColor} strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={toX(points.length - 1)} cy={toY(points[points.length - 1])} r="3" fill={lineColor} />
    </svg>
  );
}

// ─── Dashboard ────────────────────────────────────────────────────────────────
export default function Dashboard() {
  const navigate = useNavigate();
  const { isConnected, isLoading: brokerLoading, account, connect, syncTrades, syncStatus, syncError, isTokenExpired } = useBroker();
  const { lastTradeEvent } = useWebSocket();
  const { alerts, acknowledgeAlert } = useAlerts();

  const accountId = account?.id;
  const lastSyncAt = account?.last_sync_at;

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
  const [sessionPnlDisplay, setSessionPnlDisplay] = useState<number>(0);
  const [realizedPnlDisplay, setRealizedPnlDisplay] = useState<number>(0);

  const [tradeStats, setTradeStats] = useState<{
    trades_today: number;
    win_rate: number;
    max_drawdown: number;
    risk_used: number;
  } | null>(null);

  const [selectedAlert, setSelectedAlert] = useState<AlertNotification | null>(null);

  const [journaledIds, setJournaledIds] = useState<Set<string>>(new Set());
  const [journalOpen, setJournalOpen] = useState(false);
  const [selectedTrade, setSelectedTrade] = useState<PositionWithExtras | CompletedTrade | null>(null);
  const [selectedType, setSelectedType] = useState<'position' | 'closed'>('position');

  const [showCapitalPrompt, setShowCapitalPrompt] = useState(false);
  const [capitalInput, setCapitalInput] = useState('');
  const [capitalSaving, setCapitalSaving] = useState(false);

  const accountIdRef = useRef(accountId);
  accountIdRef.current = accountId;
  const fetchedForSyncRef = useRef<string | null>(null);
  const seenTradeIdsRef = useRef<Set<string>>(new Set());
  const journalPromptTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── Fetch callbacks ──────────────────────────────────────────────────────
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
          ? parseFloat(pos.last_price) * Math.abs(pos.total_quantity || 0) * (parseFloat(pos.multiplier) || 1)
          : (parseFloat(pos.average_entry_price) || 0) * Math.abs(pos.total_quantity || 0) * (parseFloat(pos.multiplier) || 1),
        last_price: parseFloat(pos.last_price) || 0,
        day_pnl: parseFloat(pos.day_pnl) || 0,
      }));
      setPositions(transformedPositions);
    } catch (err: any) {
      setPositionsError(apiDetailString(err.response?.data?.detail, err.message || 'Failed to fetch positions'));
    } finally {
      setPositionsLoading(false);
    }
  }, []);

  const fetchTrades = useCallback(async () => {
    const id = accountIdRef.current;
    if (!id) return;
    try {
      setTradesLoading(true);
      setTradesError(null);
      const response = await api.get('/api/trades/completed', { params: { limit: 50 } });
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
      setTradesError(apiDetailString(err.response?.data?.detail, err.message || 'Failed to fetch trades'));
    } finally {
      setTradesLoading(false);
    }
  }, []);

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
        last_synced: lastSyncAt ? `Synced ${formatTimeAgo(lastSyncAt)}` : 'Not synced yet',
      });
    } catch {
      setRiskState({
        risk_state: 'safe', status_message: 'Unable to fetch risk state',
        active_patterns: [], unrealized_pnl: 0, ai_recommendations: [], last_synced: 'Unknown',
      });
    }
  }, [lastSyncAt]);

  const fetchAllData = useCallback(async () => {
    if (!accountIdRef.current) return;
    await Promise.all([fetchPositions(), fetchTrades(), fetchRiskState()]);
    setDataLoaded(true);
  }, [fetchPositions, fetchTrades, fetchRiskState]);

  // Fetch journal entries
  useEffect(() => {
    if (!accountId) return;
    api.get('/api/journal').then(res => {
      const entries = res.data?.entries || [];
      const ids = new Set<string>(entries.map((e: any) => e.trade_id).filter(Boolean));
      setJournaledIds(ids);
    }).catch(() => {});
  }, [accountId]);

  // Load on connect
  useEffect(() => {
    if (!isConnected || !accountId) return;
    const fetchKey = `connect-${accountId}`;
    if (fetchedForSyncRef.current === fetchKey) return;
    fetchedForSyncRef.current = fetchKey;
    fetchAllData();

    const dismissed = localStorage.getItem(`capital_prompt_dismissed_${accountId}`);
    if (!dismissed) {
      api.get('/api/profile/').then((res) => {
        if (!res.data?.profile?.trading_capital) setShowCapitalPrompt(true);
      }).catch(() => {});
    }
  }, [isConnected, accountId, fetchAllData]);

  // Re-fetch when sync transitions to success
  const prevSyncStatusRef = useRef<string>('idle');
  useEffect(() => {
    const prev = prevSyncStatusRef.current;
    prevSyncStatusRef.current = syncStatus;
    if (syncStatus === 'success' && prev === 'syncing' && isConnected && accountId) {
      fetchAllData();
    }
  }, [syncStatus, isConnected, accountId, fetchAllData]);

  // Re-fetch on WebSocket trade event
  useEffect(() => {
    if (!lastTradeEvent || !isConnected || isTokenExpired) return;
    fetchTrades();
    fetchPositions();
  }, [lastTradeEvent]); // eslint-disable-line react-hooks/exhaustive-deps

  // Journal auto-prompt: open journal 45s after new trade closes
  useEffect(() => {
    if (!dataLoaded || closedTrades.length === 0) return;
    if (seenTradeIdsRef.current.size === 0) {
      closedTrades.forEach(t => seenTradeIdsRef.current.add(t.id));
      return;
    }
    const newTrade = closedTrades.find(t => !seenTradeIdsRef.current.has(t.id) && !journaledIds.has(t.id));
    closedTrades.forEach(t => seenTradeIdsRef.current.add(t.id));
    if (!newTrade) return;
    if (journalPromptTimerRef.current) clearTimeout(journalPromptTimerRef.current);
    journalPromptTimerRef.current = setTimeout(() => {
      if (!journalOpen) {
        setSelectedTrade(newTrade);
        setSelectedType('closed');
        setJournalOpen(true);
      }
    }, 45_000);
    return () => {
      if (journalPromptTimerRef.current) clearTimeout(journalPromptTimerRef.current);
    };
  }, [closedTrades]); // eslint-disable-line react-hooks/exhaustive-deps

  // Compute session stats
  useEffect(() => {
    const today = new Date(); today.setHours(0, 0, 0, 0);
    const todayTrades = closedTrades.filter(t => new Date(t.exit_time) >= today);
    const winners = todayTrades.filter(t => t.realized_pnl > 0);
    const realizedPnl = todayTrades.reduce((sum, t) => sum + t.realized_pnl, 0);
    const unrealizedPnl = positions.reduce((sum, p) => sum + (p.unrealized_pnl || 0), 0);
    const sessionPnl = realizedPnl + unrealizedPnl;

    let cumPnl = 0, peak = 0, maxDrawdown = 0;
    for (const trade of todayTrades) {
      cumPnl += trade.realized_pnl;
      if (cumPnl > peak) peak = cumPnl;
      const drawdown = peak - cumPnl;
      if (drawdown > maxDrawdown) maxDrawdown = drawdown;
    }

    setTradeStats({
      trades_today: todayTrades.length,
      win_rate: todayTrades.length > 0 ? (winners.length / todayTrades.length) * 100 : 0,
      max_drawdown: -maxDrawdown,
      risk_used: 0,
    });
    setSessionPnlDisplay(sessionPnl);
    setRealizedPnlDisplay(realizedPnl);
    setRiskState(prev => prev ? { ...prev, unrealized_pnl: sessionPnl } : prev);
  }, [closedTrades, positions]);

  // ── Handlers ─────────────────────────────────────────────────────────────
  const handleSaveCapital = async () => {
    const val = parseFloat(capitalInput.replace(/,/g, ''));
    if (!val || val <= 0) return;
    setCapitalSaving(true);
    try {
      await api.put('/api/profile/', { trading_capital: val });
      setShowCapitalPrompt(false);
      if (accountId) localStorage.setItem(`capital_prompt_dismissed_${accountId}`, '1');
    } catch {
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
      fetchedForSyncRef.current = null;
      await syncTrades();
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

  const handleJournalClose = (open: boolean) => {
    if (!open && selectedTrade) {
      setJournaledIds(prev => new Set([...prev, selectedTrade.id]));
    }
    setJournalOpen(open);
  };

  // ── Computed values ───────────────────────────────────────────────────────
  const mergedAlerts = useMemo(() => {
    const startOfToday = new Date(); startOfToday.setHours(0, 0, 0, 0);
    return alerts
      .filter(a => new Date(a.shown_at).getTime() >= startOfToday.getTime())
      .map(a => ({
        id: a.id,
        pattern_name: a.pattern.name,
        pattern: a.pattern.name,
        pattern_type: a.pattern.type,
        severity: (a.pattern.severity === 'low' ? 'medium' : a.pattern.severity) as 'critical' | 'high' | 'medium' | 'positive',
        description: a.pattern.description,
        message: a.pattern.description,
        why_it_matters: a.pattern.insight,
        details: a.pattern.details,
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

  const unreadCount = mergedAlerts.filter(a => !a.acknowledged).length;
  const highSevCount = mergedAlerts.filter(a => !a.acknowledged && (a.severity === 'critical' || a.severity === 'high')).length;
  const sessionStateKey = getSessionState(unreadCount, highSevCount);
  const stateCfg = STATE_CFG[sessionStateKey];

  const unjournaled = recentTrades.filter(t => {
    const today = new Date(); today.setHours(0, 0, 0, 0);
    return new Date(t.exit_time) >= today && !journaledIds.has(t.id);
  }).length;

  const pnlPositive = sessionPnlDisplay >= 0;

  // ── Render guards ─────────────────────────────────────────────────────────
  if (brokerLoading) {
    return (
      <div className="w-full min-h-[60vh] flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

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

  return (
    <div className="w-full min-h-screen tm-page-bg">

      {/* ── Banners ───────────────────────────────────────────────────────── */}
      {isTokenExpired && dataLoaded && (
        <div className="mb-4 px-3 py-2.5 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800/30 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-3.5 w-3.5 text-amber-600 dark:text-amber-400 shrink-0" />
            <span className="text-[13px] text-amber-700 dark:text-amber-300">
              Live sync paused — showing last known data. Analytics, chat and history still work.
            </span>
          </div>
        </div>
      )}

      {showCapitalPrompt && dataLoaded && (
        <div className="mb-4 px-3 py-2.5 rounded-lg bg-tm-brand/5 border border-tm-brand/20 flex flex-wrap items-center gap-3">
          <div className="flex-1 min-w-0">
            <p className="text-[13px] font-medium text-foreground">Enable position sizing alerts</p>
            <p className="text-[12px] text-muted-foreground mt-0.5">
              Without your trading capital, we can't detect oversized positions.
            </p>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <span className="text-sm text-muted-foreground">₹</span>
            <input
              type="number"
              placeholder="e.g. 500000"
              value={capitalInput}
              onChange={e => setCapitalInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSaveCapital()}
              className="w-32 px-2 py-1.5 text-sm bg-background border border-border rounded-lg focus:outline-none focus:ring-1 focus:ring-ring"
            />
            <button
              onClick={handleSaveCapital}
              disabled={!capitalInput || capitalSaving}
              className="px-3 py-1.5 text-sm bg-tm-brand text-white rounded-lg hover:bg-tm-brand/90 disabled:opacity-50"
            >
              {capitalSaving ? <Loader2 className="h-3 w-3 animate-spin" /> : 'Save'}
            </button>
            <button onClick={handleDismissCapital} className="text-muted-foreground hover:text-foreground">
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}

      {syncStatus === 'error' && dataLoaded && !isTokenExpired && (
        <div className="mb-4 px-3 py-2.5 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800/30 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-3.5 w-3.5 text-tm-loss shrink-0" />
            <span className="text-[13px] text-tm-loss">
              Sync failed: {syncError || 'Could not refresh data'}. Showing cached data.
            </span>
          </div>
          <Button onClick={handleSync} variant="ghost" size="sm" className="gap-1 text-tm-loss h-7 text-[13px]">
            <RefreshCw className="h-3 w-3" />
            Retry
          </Button>
        </div>
      )}

      {/* ── Page Header ───────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-lg font-semibold text-foreground tracking-tight">Dashboard</h1>
        <div className="flex items-center gap-3 text-[13px] text-muted-foreground font-mono tabular-nums">
          <span>{tradeStats?.trades_today ?? 0} trades</span>
          <span className="text-muted-foreground/30">·</span>
          <span className={cn('font-semibold', pnlPositive ? 'text-tm-profit' : 'text-tm-loss')}>
            {formatCurrencyWithSign(sessionPnlDisplay)}
          </span>
          {unreadCount > 0 && (
            <>
              <span className="text-muted-foreground/30">·</span>
              <Link to="/alerts" className="text-tm-obs hover:underline font-medium">
                {unreadCount} alert{unreadCount !== 1 ? 's' : ''}
              </Link>
            </>
          )}
          {unjournaled > 0 && (
            <>
              <span className="text-muted-foreground/30">·</span>
              <span className="text-tm-obs">{unjournaled} to journal</span>
            </>
          )}
        </div>
      </div>

      {/* ── Session Hero ──────────────────────────────────────────────────── */}
      <div className={cn('tm-card mb-5', stateCfg.accent)}>
        <div className="flex items-stretch">
          {/* Left: state + P&L */}
          <div className="flex-1 min-w-0 px-5 pt-4 pb-3">
            <div className="flex items-center gap-2 mb-2">
              <span className={cn('flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold uppercase tracking-wide', stateCfg.pill)}>
                <span className={cn('w-1.5 h-1.5 rounded-full', stateCfg.dot)} />
                {stateCfg.label}
              </span>
            </div>
            <div className="flex items-baseline gap-2 mb-1">
              <span className={cn('text-[44px] font-black font-mono tabular-nums leading-none', pnlPositive ? 'text-tm-profit' : 'text-tm-loss')}>
                {formatCurrencyWithSign(sessionPnlDisplay)}
              </span>
            </div>
            <p className="text-[13px] text-muted-foreground leading-snug">
              {getSessionDesc(sessionStateKey, unreadCount, tradeStats?.trades_today ?? 0, Math.round(tradeStats?.win_rate ?? 0))}
            </p>
          </div>

          {/* Right: sparkline */}
          <div className="w-[176px] shrink-0 border-l border-slate-100 dark:border-neutral-700/60 px-4 pt-4 pb-3 flex flex-col">
            <span className="tm-label mb-2">Cumulative P&L</span>
            <PnlSparkline closed={closedTrades} unrealized={positions.reduce((s, p) => s + (p.unrealized_pnl || 0), 0)} positive={pnlPositive} />
            <div className="flex items-center justify-between mt-1.5">
              <span className="text-[10px] text-muted-foreground">open → now</span>
              <span className={cn('text-[11px] font-mono tabular-nums font-semibold', pnlPositive ? 'text-tm-profit' : 'text-tm-loss')}>
                {formatCurrencyWithSign(sessionPnlDisplay)}
              </span>
            </div>
          </div>
        </div>

        {/* Stat footer — pipe-separated */}
        <div className="flex items-center flex-wrap gap-y-1 border-t border-slate-100 dark:border-neutral-700/60 px-5 py-3">
          <span className="text-[12px] text-muted-foreground pr-4">
            <span className="font-mono tabular-nums font-semibold text-foreground">{tradeStats?.trades_today ?? 0}</span>
            {' '}trades
          </span>
          {tradeStats && tradeStats.trades_today > 0 && (
            <>
              <span className="w-px h-3.5 shrink-0 bg-slate-200 dark:bg-neutral-600" />
              <span className="text-[12px] text-muted-foreground px-4">
                <span className={cn('font-mono tabular-nums font-semibold', tradeStats.win_rate >= 50 ? 'text-tm-profit' : 'text-tm-loss')}>
                  {Math.round(tradeStats.win_rate)}%
                </span>
                {' '}win rate
              </span>
            </>
          )}
          <span className="w-px h-3.5 shrink-0 bg-slate-200 dark:bg-neutral-600" />
          <span className="text-[12px] text-muted-foreground px-4">
            <span className={cn('font-mono tabular-nums font-semibold', realizedPnlDisplay >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
              {formatCurrencyWithSign(realizedPnlDisplay)}
            </span>
            {' '}realized
          </span>
          {unjournaled > 0 && (
            <>
              <span className="w-px h-3.5 shrink-0 bg-slate-200 dark:bg-neutral-600" />
              <span className="text-[12px] text-tm-obs font-medium px-4">{unjournaled} to journal</span>
            </>
          )}
          {unreadCount > 0 && (
            <>
              <span className="w-px h-3.5 shrink-0 bg-slate-200 dark:bg-neutral-600" />
              <Link to="/alerts" className="text-[12px] text-tm-obs font-medium hover:underline px-4">
                {unreadCount} alert{unreadCount !== 1 ? 's' : ''} →
              </Link>
            </>
          )}
        </div>
      </div>

      {/* ── Alerts (full-width) ───────────────────────────────────────────── */}
      <div className="mb-5">
        <RecentAlertsCard
          alerts={mergedAlerts}
          onAcknowledge={acknowledgeAlert}
          onOpen={id => setSelectedAlert(alerts.find(a => a.id === id) ?? null)}
        />
      </div>

      {/* ── Two-column layout ─────────────────────────────────────────────── */}
      <div className="flex gap-5 items-start">

        {/* Left 62% */}
        <div className="flex-[62] min-w-0 space-y-5">
          {positionsError && !positionsLoading && positions.length === 0 ? (
            <div className="tm-card p-5 text-center">
              <AlertTriangle className="h-5 w-5 text-tm-loss mx-auto mb-2" />
              <p className="text-[13px] text-muted-foreground">{positionsError}</p>
              <Button onClick={fetchPositions} variant="ghost" size="sm" className="mt-2">Retry</Button>
            </div>
          ) : (
            <OpenPositionsTable
              positions={positions}
              isLoading={positionsLoading}
              journaledIds={journaledIds}
              onPositionClick={handlePositionClick}
            />
          )}

          {tradesError && !tradesLoading && closedTrades.length === 0 ? (
            <div className="tm-card p-5 text-center">
              <AlertTriangle className="h-5 w-5 text-tm-loss mx-auto mb-2" />
              <p className="text-[13px] text-muted-foreground">{tradesError}</p>
              <Button onClick={fetchTrades} variant="ghost" size="sm" className="mt-2">Retry</Button>
            </div>
          ) : (
            <ClosedTradesTable
              trades={recentTrades}
              isLoading={tradesLoading}
              journaledIds={journaledIds}
              onTradeClick={handleTradeClick}
            />
          )}
        </div>

        {/* Right 38% sticky */}
        <div className="flex-[38] min-w-0 space-y-5 sticky top-4">
          <BlowupShieldCard />
          {accountId && (
            <SessionPaceGoalCard
              brokerAccountId={accountId}
              tradesCount={tradeStats?.trades_today ?? 0}
            />
          )}

          {/* AI Coach CTA */}
          <Link
            to="/chat"
            className="tm-coach-cta flex items-center gap-3 rounded-xl p-4 hover:opacity-90 transition-opacity group"
          >
            <div className="w-9 h-9 rounded-lg bg-white/15 flex items-center justify-center shrink-0">
              <Bot className="w-4 h-4 text-white" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-white">AI Trading Coach</p>
              <p className="text-[12px] text-white/70">Ask about your patterns or get a debrief</p>
            </div>
            <ArrowRight className="w-4 h-4 text-white/40 group-hover:text-white transition-colors shrink-0" />
          </Link>

          {holdings.length > 0 && holdingsSummary && (
            <HoldingsCard
              holdings={holdings}
              summary={holdingsSummary}
              isLoading={holdingsLoading}
            />
          )}
        </div>
      </div>

      {/* ── Predictive Warnings (full-width below) ─────────────────────────── */}
      {accountId && (
        <div className="mt-5">
          <PredictiveWarningsCard brokerAccountId={accountId} />
        </div>
      )}

      {/* ── Alert Detail Sheet ───────────────────────────────────────────── */}
      <AlertDetailSheet
        alert={selectedAlert}
        open={selectedAlert !== null}
        onClose={() => setSelectedAlert(null)}
        onAcknowledge={id => { acknowledgeAlert(id); setSelectedAlert(null); }}
      />

      {/* ── Trade Journal Sheet ───────────────────────────────────────────── */}
      <TradeJournalSheet
        open={journalOpen}
        onOpenChange={handleJournalClose}
        trade={selectedTrade}
        type={selectedType}
      />
    </div>
  );
}

function formatTimeAgo(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins} min ago`;
  if (diffHours < 24) return `${diffHours} hours ago`;
  return date.toLocaleDateString();
}
