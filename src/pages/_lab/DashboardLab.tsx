/**
 * Dashboard — "what is happening right now".
 *
 * Composition settled in the design lab and ported 2026-08-01:
 * de-carded session hero (figure left, session stats right, market status
 * inline rather than a full-width Trading Desk row), full behavioural alert
 * rows, then open positions above closed. Closed stays collapsed until asked
 * for -- open positions are live and always want to be visible, closed trades
 * are reference -- and both headers surface how many entries are still
 * unjournalled, which is the one pending action on this screen.
 */
import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Link } from 'react-router-dom';
import { Loader2, AlertTriangle, RefreshCw, X, ChevronDown } from 'lucide-react';
import BrokerGate from '@/components/BrokerGate';
import ErrorState from '@/components/ErrorState';
import { Input } from '@/components/ui/input';
import { SetupNudgeCard } from '@/components/dashboard/SetupNudgeCard';
import { TodayIntentStrip } from '@/components/dashboard/TodayIntentStrip';
import { MarketRail } from '@/components/dashboard/MarketRail';
import ImportHistoryPrompt from '@/components/onboarding/ImportHistoryPrompt';
import RecentAlertsCard from '@/components/dashboard/RecentAlertsCard';
import AlertDetailSheet from '@/components/alerts/AlertDetailSheet';
import OpenPositionsTable from '@/components/dashboard/OpenPositionsTable';
import ClosedPositionsCard from '@/components/dashboard/ClosedPositionsCard';
import { SessionHeroCard } from '@/components/dashboard/SessionHeroCard';
import { AiCoachFab } from '@/components/dashboard/AiCoachFab';
import { TradeJournalSheet } from '@/components/dashboard/TradeJournalSheet';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { formatCurrencyWithSign } from '@/lib/formatters';
import { api, apiDetailString } from '@/lib/api';
import { toast } from '@/hooks/use-toast';
import { Position, CompletedTrade } from '@/types/api';
import type { MarginStatus } from '@/types/api';
import { useAlerts, AlertNotification } from '@/contexts/AlertContext';
import { useBroker } from '@/contexts/BrokerContext';
import { useWebSocket } from '@/contexts/WebSocketContext';
import { STATE_CFG, SessionState, getSessionState, formatTimeAgo, getLastSessionStartUTC } from '@/lib/dashboardUtils';
import { normalizeSeverityStr } from '@/lib/alertSeverity';

type PositionWithExtras = Position & { instrument_type: string; unrealized_pnl: number; current_value: number };

interface RiskStateData {
  risk_state: 'safe' | 'caution' | 'danger';
  status_message: string;
  active_patterns: string[];
  unrealized_pnl: number;
  ai_recommendations: string[];
  last_synced: string;
  daily_loss_limit: number;
  daily_trade_limit: number;
}

// ─── Dashboard ────────────────────────────────────────────────────────────────
export default function DashboardLab() {
  const navigate = useNavigate();
  const { isConnected, isLoading: brokerLoading, account, connect, syncTrades, syncStatus, syncError, isTokenExpired } = useBroker();
  const { lastTradeEvent, lastLtpEvent, lastLtpAt, isConnected: wsConnected } = useWebSocket();
  const { alerts, isLoading: alertsLoading, acknowledgeAlert } = useAlerts();

  const accountId = account?.id;
  const lastSyncAt = account?.last_sync_at;

  const [isSyncing, setIsSyncing] = useState(false);
  const [positions, setPositions] = useState<PositionWithExtras[]>([]);
  const [positionsLoading, setPositionsLoading] = useState(false);
  const [positionsError, setPositionsError] = useState<string | null>(null);
  const [closedTrades, setClosedTrades] = useState<CompletedTrade[]>([]);
  const [tradesLoading, setTradesLoading] = useState(false);
  const [tradesError, setTradesError] = useState<string | null>(null);
  const [riskState, setRiskState] = useState<RiskStateData | null>(null);
  const [margins, setMargins] = useState<MarginStatus | null>(null);
  const [dataLoaded, setDataLoaded] = useState(false);
  const [realizedPnlDisplay, setRealizedPnlDisplay] = useState<number>(0);

  const [tradeStats, setTradeStats] = useState<{
    trades_today: number;
    win_rate: number;
    max_drawdown: number;
  } | null>(null);

  const [selectedAlert, setSelectedAlert] = useState<AlertNotification | null>(null);

  const [journaledIds, setJournaledIds] = useState<Set<string>>(new Set());
  const [journalOpen, setJournalOpen] = useState(false);
  const [selectedTrade, setSelectedTrade] = useState<PositionWithExtras | CompletedTrade | null>(null);
  const [selectedType, setSelectedType] = useState<'position' | 'closed'>('position');

  const [closedOpen, setClosedOpen] = useState(false);
  const [showCapitalPrompt, setShowCapitalPrompt] = useState(false);
  const [capitalInput, setCapitalInput] = useState('');
  const [capitalSaving, setCapitalSaving] = useState(false);

  const accountIdRef = useRef(accountId);
  accountIdRef.current = accountId;
  // Live mirrors of open-state so the 45s auto-prompt timer can read CURRENT values
  // (its effect closure is stale) and never interrupt an open sheet/prompt.
  const journalOpenRef = useRef(journalOpen);
  journalOpenRef.current = journalOpen;
  const alertOpenRef = useRef<AlertNotification | null>(selectedAlert);
  alertOpenRef.current = selectedAlert;
  const capitalPromptRef = useRef(showCapitalPrompt);
  capitalPromptRef.current = showCapitalPrompt;
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
      const msg = apiDetailString(err.response?.data?.detail, err.message || 'Failed to fetch positions');
      setPositionsError(msg);
      if (err?.response?.status !== 401) {
        toast({ variant: 'destructive', title: 'Could not load positions', description: msg });
      }
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
      const msg = apiDetailString(err.response?.data?.detail, err.message || 'Failed to fetch trades');
      setTradesError(msg);
      if (err?.response?.status !== 401) {
        toast({ variant: 'destructive', title: 'Could not load trades', description: msg });
      }
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
        risk_state: data.risk_state || data.state || 'safe',
        status_message: (data.risk_state || data.state) === 'danger' ? 'High Risk Zone' :
          (data.risk_state || data.state) === 'caution' ? 'Caution Advised' : 'Trading Safely',
        active_patterns: data.active_patterns || [],
        unrealized_pnl: 0,
        ai_recommendations: data.recommendations || [],
        last_synced: lastSyncAt ? `Synced ${formatTimeAgo(lastSyncAt)}` : 'Not synced yet',
        daily_loss_limit: data.daily_loss_limit || 25000,
        daily_trade_limit: data.daily_trade_limit || 10,
      });
    } catch {
      setRiskState({
        risk_state: 'safe', status_message: 'Unable to fetch risk state',
        active_patterns: [], unrealized_pnl: 0, ai_recommendations: [], last_synced: 'Unknown',
        daily_loss_limit: 25000, daily_trade_limit: 10,
      });
    }
  }, [lastSyncAt]);

  const fetchMargins = useCallback(async () => {
    const id = accountIdRef.current;
    if (!id) return;
    try {
      const res = await api.get('/api/zerodha/margins');
      setMargins(res.data);
    } catch {
      // non-critical — show nothing
    }
  }, []);

  const fetchAllData = useCallback(async () => {
    if (!accountIdRef.current) return;
    await Promise.all([fetchPositions(), fetchTrades(), fetchRiskState(), fetchMargins()]);
    setDataLoaded(true);
  }, [fetchPositions, fetchTrades, fetchRiskState, fetchMargins]);

  // Fetch journal entries
  useEffect(() => {
    if (!accountId) return;
    api.get('/api/journal/').then(res => {
      const entries = res.data?.entries || [];
      const ids = new Set<string>(entries.map((e: any) => e.trade_id).filter(Boolean));
      setJournaledIds(ids);
    }).catch((err) => { console.warn('[Dashboard] journal fetch failed:', err); });
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
      }).catch((err) => { console.warn('[Dashboard] profile fetch failed:', err); });
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
    fetchMargins();
  }, [lastTradeEvent]); // eslint-disable-line react-hooks/exhaustive-deps

  // Patch positions' last_price on every KiteTicker tick — no API call needed
  useEffect(() => {
    if (!lastLtpEvent) return;
    setPositions(prev => prev.map(pos =>
      pos.tradingsymbol === lastLtpEvent.symbol
        ? { ...pos, last_price: lastLtpEvent.last_price }
        : pos
    ));
  }, [lastLtpEvent]); // eslint-disable-line react-hooks/exhaustive-deps

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
      // Read CURRENT open-state via refs (the effect closure is 45s stale). Don't
      // interrupt the user if any sheet/prompt is already open — auto-prompt only
      // fires into a clean screen.
      if (!journalOpenRef.current && !alertOpenRef.current && !capitalPromptRef.current) {
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
    const todayTrades = closedTrades.filter(t => new Date(t.exit_time) >= getLastSessionStartUTC());
    const winners = todayTrades.filter(t => t.realized_pnl > 0);
    const losers = todayTrades.filter(t => t.realized_pnl < 0);
    const realizedPnl = todayTrades.reduce((sum, t) => sum + t.realized_pnl, 0);
    const unrealizedPnl = positions.reduce((sum, p) => sum + (p.unrealized_pnl || 0), 0);
    const sessionPnl = realizedPnl + unrealizedPnl;

    // Drawdown must accumulate in the order trades actually closed — the API list
    // is not guaranteed to be exit-time ordered, so sort before folding.
    const drawdownOrdered = [...todayTrades].sort(
      (a, b) => new Date(a.exit_time).getTime() - new Date(b.exit_time).getTime()
    );
    let cumPnl = 0, peak = 0, maxDrawdown = 0;
    for (const trade of drawdownOrdered) {
      cumPnl += trade.realized_pnl;
      if (cumPnl > peak) peak = cumPnl;
      const drawdown = peak - cumPnl;
      if (drawdown > maxDrawdown) maxDrawdown = drawdown;
    }

    setTradeStats({
      trades_today: todayTrades.length,
      // Win rate = wins / decided trades. Breakeven trades (pnl == 0) are neither
      // a win nor a loss, so they're excluded from the denominator rather than
      // silently counted against the trader.
      win_rate: (winners.length + losers.length) > 0
        ? (winners.length / (winners.length + losers.length)) * 100
        : 0,
      max_drawdown: -maxDrawdown,
    });
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
      toast({
        variant: 'destructive',
        title: 'Could not save capital',
        description: 'Please try again from Settings → Profile.',
      });
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
    // Do NOT mark journaled on close — only a successful save marks it (onSaved below).
    setJournalOpen(open);
  };

  const handleJournalSaved = (tradeId: string) => {
    setJournaledIds(prev => new Set([...prev, tradeId]));
  };

  const handleJournalDeleted = (tradeId: string) => {
    setJournaledIds(prev => {
      const next = new Set(prev);
      next.delete(tradeId);
      return next;
    });
  };

  // ── Computed values ───────────────────────────────────────────────────────
  const mergedAlerts = useMemo(() => {
    // Same session window as closed trades — so the alert feed doesn't blank out at
    // calendar midnight; it holds the last session's alerts until the next 09:15.
    const cutoff = getLastSessionStartUTC().getTime();
    return alerts
      .filter(a => a.shown_at && new Date(a.shown_at).getTime() >= cutoff)
      .map(a => ({
        id: a.id,
        pattern_name: a.pattern.name,
        pattern: a.pattern.name,
        pattern_type: a.pattern.type,
        severity: normalizeSeverityStr(a.pattern.severity),
        description: a.pattern.description,
        message: a.pattern.description,
        // pattern.insight is `unknown` (free-form detail from behavior_engine);
        // RecentAlertsCard expects a string.
        why_it_matters: typeof a.pattern.insight === 'string' ? a.pattern.insight : undefined,
        details: a.pattern.details,
        timestamp: a.shown_at,
        acknowledged: a.acknowledged,
      }))
      .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
      .slice(0, 8);
  }, [alerts]);

  // Today's closed trades only
  const recentTrades = useMemo(() => {
    return closedTrades.filter(t => new Date(t.exit_time) >= getLastSessionStartUTC());
  }, [closedTrades]);

  const unreadCount = mergedAlerts.filter(a => !a.acknowledged).length;
  const acknowledgedTodayCount = mergedAlerts.filter(a => a.acknowledged).length;
  const highSevCount = mergedAlerts.filter(a => !a.acknowledged && a.severity === 'danger').length;
  const sessionStateKey: SessionState = getSessionState(unreadCount, highSevCount);
  const stateCfg = STATE_CFG[sessionStateKey];

  const unjournaled = recentTrades.filter(t =>
    new Date(t.exit_time) >= getLastSessionStartUTC() && !journaledIds.has(t.id)
  ).length;

  // How many closed round-trips still have no journal entry. This is the only
  // pending action on the screen and it was invisible until a row was opened.
  const closedUnjournalled = useMemo(
    () => recentTrades.filter(t => !journaledIds.has(t.id)).length,
    [recentTrades, journaledIds],
  );

  const unrealizedTotal = useMemo(() =>
    positions.reduce((s, p) => {
      if (p.last_price) {
        const mult = p.multiplier ?? 1;
        return s + (p.last_price - p.average_entry_price) * p.total_quantity * mult;
      }
      return s + (p.unrealized_pnl || 0);
    }, 0),
    [positions]
  );
  const sessionPnlDisplay = realizedPnlDisplay + unrealizedTotal;
  const pnlPositive = sessionPnlDisplay >= 0;

  const dailyLossLimit = riskState?.daily_loss_limit ?? 25000;
  const dailyTradeLimit = riskState?.daily_trade_limit ?? 10;

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
      <BrokerGate
        title="Dashboard"
        unlocks="Connect your Zerodha account to see your live session — open positions, day P&L and behavioural alerts as they fire."
      />
    );
  }

  // Sync failed with nothing cached to fall back on. Uses the shared error
  // surface with the specific reason, rather than a bespoke block.
  if (syncStatus === 'error' && !dataLoaded && !positionsLoading && !tradesLoading) {
    return (
      <ErrorState
        error={{ response: { status: 500 } }}
        message={syncError || 'Could not sync data from Zerodha. This may be a temporary issue.'}
        onRetry={handleSync}
      />
    );
  }

  return (
    <div className="w-full">

      <ImportHistoryPrompt />

      {/* ── System banners (token / sync / capital) ─────────────────────────
             Semantic tokens, which already carry both themes — the previous
             raw amber and red pairs needed a dark: variant for every value. */}
      {isTokenExpired && dataLoaded && (
        <div className="mb-4 px-3 py-2.5 rounded-lg bg-warning/10 border border-warning/20 flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 text-warning shrink-0" />
          <span className="text-[12.5px] text-warning">
            Live sync paused — showing last known data. Analytics and history still work.
          </span>
        </div>
      )}


      {syncStatus === 'error' && dataLoaded && !isTokenExpired && (
        <div className="mb-4 px-3 py-2.5 rounded-lg bg-loss/10 border border-loss/20 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 min-w-0">
            <AlertTriangle className="h-4 w-4 text-loss shrink-0" />
            <span className="text-[12.5px] text-loss">
              Sync failed: {syncError || 'Could not refresh data'}. Showing cached data.
            </span>
          </div>
          <Button onClick={handleSync} variant="ghost" size="sm" className="gap-1 text-loss h-8 text-[12.5px] shrink-0">
            <RefreshCw className="h-3.5 w-3.5" />
            Retry
          </Button>
        </div>
      )}

      {/* ── Single-column dashboard: hero · alerts · open · closed ─────────
             20px between top-level sections (§8). */}
      <div className="flex flex-col gap-5">
        <SessionHeroCard
          marketStatus={<MarketRail />}
          stateCfg={stateCfg}
          sessionPnlDisplay={sessionPnlDisplay}
          realizedPnlDisplay={realizedPnlDisplay}
          tradeStats={tradeStats}
          pnlPositive={pnlPositive}
          unreadCount={unreadCount}
          acknowledgedTodayCount={acknowledgedTodayCount}
          unrealizedTotal={unrealizedTotal}
          dailyLossLimit={dailyLossLimit}
          dailyTradeLimit={dailyTradeLimit}
          margins={margins}
        />

        {/* Setup nudges sit BELOW the session, not above it. A form asking for
            trading capital was the first thing on the page, pushing the number
            the screen exists to show under the fold. */}
        {showCapitalPrompt && dataLoaded && (
        <div className="mb-4 px-3 py-2.5 rounded-lg bg-primary/5 border border-primary/20 flex flex-wrap items-center gap-3">
          <div className="flex-1 min-w-0">
            <p className="text-[14px] font-medium text-foreground">Enable position sizing alerts</p>
            <p className="text-[12.5px] text-muted-foreground mt-0.5">
              Add your trading capital to detect oversized positions.
            </p>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <span className="text-[14px] text-muted-foreground">₹</span>
            <Input
              type="number"
              placeholder="e.g. 500000"
              value={capitalInput}
              onChange={e => setCapitalInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSaveCapital()}
              className="w-32 h-9 text-[14px] font-tabular"
            />
            <Button onClick={handleSaveCapital} disabled={!capitalInput || capitalSaving}>
              {capitalSaving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : 'Save'}
            </Button>
            <button
              onClick={handleDismissCapital}
              aria-label="Dismiss"
              className="text-muted-foreground transition-colors duration-150 hover:text-foreground"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}

        {/* New-user setup prompt — self-gates to null once onboarded/dismissed */}
        <SetupNudgeCard />

        {/* One line, opening the same sheet Journal uses. The Dashboard was
            where entries got written and the only place that never showed one
            back, which is why the two read as separate apps. */}
        <TodayIntentStrip />

        {/* Behavioral alerts */}
        <div aria-live="polite" aria-label="Behavioral alerts">
          <RecentAlertsCard
            alerts={mergedAlerts}
            loading={alertsLoading}
            onAcknowledge={acknowledgeAlert}
            onOpen={id => setSelectedAlert(alerts.find(a => a.id === id) ?? null)}
          />
        </div>

        {/* Open above, closed below and collapsed until asked for. Open
            positions are live and always want to be visible; closed trades are
            reference, so they cost a click rather than a screenful. Both
            headers surface how many entries are still unjournalled, because
            that is the one pending action on this screen and it was invisible
            until you opened a row. */}
        <section className="desk-card overflow-hidden">
          {positionsError && !positionsLoading && positions.length === 0 ? (
            <ErrorState error={{ response: { status: 500 } }} message={positionsError} onRetry={fetchPositions} compact />
          ) : (
            <OpenPositionsTable
              positions={positions}
              isLoading={positionsLoading}
              journaledIds={journaledIds}
              onPositionClick={handlePositionClick}
              pricesConnected={wsConnected}
              lastPriceAt={lastLtpAt}
              tokenExpired={isTokenExpired}
            />
          )}
        </section>

        <section className="desk-card overflow-hidden">
          <button
            type="button"
            onClick={() => setClosedOpen(v => !v)}
            aria-expanded={closedOpen}
            className="w-full card-head hover:bg-muted/40 transition-colors duration-150 focus-visible:outline-none focus-visible:bg-muted/40"
          >
            <span className="flex items-center gap-2.5 min-w-0">
              <span className="t-label">Closed positions</span>
              <span className="text-[11px] text-muted-foreground font-tabular">
                · {recentTrades.length} trade{recentTrades.length !== 1 ? 's' : ''}
              </span>
              {closedUnjournalled > 0 && (
                <span className="inline-flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wider text-primary bg-primary/10 px-1.5 py-0.5 rounded">
                  {closedUnjournalled} to journal
                </span>
              )}
            </span>
            <span className="flex items-center gap-2.5 shrink-0">
              <span className={cn('text-[13px] font-semibold font-tabular', realizedPnlDisplay >= 0 ? 'text-profit' : 'text-loss')}>
                {formatCurrencyWithSign(realizedPnlDisplay)}
              </span>
              <ChevronDown className={cn('h-4 w-4 text-muted-foreground transition-transform duration-200', closedOpen && 'rotate-180')} />
            </span>
          </button>

          {closedOpen && (
            <div className="border-t border-border animate-accordion-down">
              {tradesError && !tradesLoading && closedTrades.length === 0 ? (
                <ErrorState error={{ response: { status: 500 } }} message={tradesError} onRetry={fetchTrades} compact />
              ) : (
                <ClosedPositionsCard
                  sinceIso={getLastSessionStartUTC().toISOString()}
                  roundTrips={recentTrades}
                  journaledIds={journaledIds}
                  onTradeClick={handleTradeClick}
                />
              )}
            </div>
          )}
        </section>
      </div>

      {/* ── AI Coach floating action button ──────────────────────────────── */}
      <AiCoachFab />

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
        onSaved={handleJournalSaved}
        onDeleted={handleJournalDeleted}
      />
    </div>
  );
}

