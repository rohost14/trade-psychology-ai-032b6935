/**
 * DashboardV2 — Design preview page
 * Route: /dashboard-v2 — outside Layout wrapper, own TopNavbar.
 *
 * Design tokens: all via CSS variables → Tailwind (text-tm-profit, bg-tm-loss/5, etc.)
 * Dark mode: html.dark class → CSS variable overrides. Zero inline style colour hacks.
 */
import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import {
  ChevronRight, Pencil, CheckCircle2, Loader2,
  BarChart2, Shield, Clock, TrendingUp,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatCurrencyWithSign } from '@/lib/formatters';
import { api, AUTH_TOKEN_KEY } from '@/lib/api';
import { isGuestMode } from '@/lib/guestMode';
import { useAlerts } from '@/contexts/AlertContext';
import { useBroker } from '@/contexts/BrokerContext';
import { useWebSocket } from '@/contexts/WebSocketContext';
import { Position, CompletedTrade, ShieldSummary } from '@/types/api';
import { AlertNotification } from '@/contexts/AlertContext';
import { TradeJournalSheet } from '@/components/dashboard/TradeJournalSheet';
import TopNavbar from '@/components/dashboard-v2/TopNavbar';
import { severityDotClass } from '@/lib/alertSeverity';
import { format, parseISO, isToday, subMinutes } from 'date-fns';

// ── Types ──────────────────────────────────────────────────────────────────────

type PositionWithExtras = Position & {
  instrument_type: string;
  unrealized_pnl: number;
  current_value: number;
};

// ── Session state ──────────────────────────────────────────────────────────────

type SessionState = 'stable' | 'caution' | 'risk';

const STATE_CFG = {
  stable: {
    label:    'Stable',
    cardBg:   'bg-teal-50/80 dark:bg-teal-950/30',
    labelCls: 'text-teal-700 dark:text-teal-300',
    dotCls:   'bg-teal-500',
    pillBg:   'bg-teal-100/80 dark:bg-teal-900/40',
  },
  caution: {
    label:    'Caution',
    cardBg:   'bg-amber-50/80 dark:bg-amber-950/30',
    labelCls: 'text-amber-600 dark:text-amber-400',
    dotCls:   'bg-amber-500',
    pillBg:   'bg-amber-100/80 dark:bg-amber-900/40',
  },
  risk: {
    label:    'Risk',
    cardBg:   'bg-red-50/80 dark:bg-red-950/30',
    labelCls: 'text-red-600 dark:text-red-400',
    dotCls:   'bg-red-500',
    pillBg:   'bg-red-100/80 dark:bg-red-900/40',
  },
} as const;

function getSessionState(
  unreadAlerts: number,
  highSeverityCount: number,
  pacePercent: number,
  winRate: number | null,
): SessionState {
  if (highSeverityCount >= 2 || (winRate !== null && winRate < 25)) return 'risk';
  if (unreadAlerts >= 2 || pacePercent > 40 || (winRate !== null && winRate < 35)) return 'caution';
  return 'stable';
}

// ── Helpers ────────────────────────────────────────────────────────────────────

function fmtPnl(v: number): string {
  const sign = v >= 0 ? '+' : '–';
  return `${sign}₹${Math.abs(v).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;
}

function fmtPrice(v: number | undefined | null): string {
  if (v == null) return '—';
  return v.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fmtTime(iso: string | undefined): string {
  if (!iso) return '—';
  try { return format(parseISO(iso), 'HH:mm'); } catch { return '—'; }
}


function fmtSymbol(sym: string, instrType?: string): { name: string; typeChip: string; sub: string } {
  const m5 = sym.match(/^([A-Z]+)\d{5}(\d{5})(CE|PE)$/);
  if (m5) return { name: m5[1], typeChip: m5[3], sub: parseInt(m5[2], 10).toLocaleString('en-IN') };
  const m6 = sym.match(/^([A-Z]+)\d{5}(\d{6})(CE|PE)$/);
  if (m6) return { name: m6[1], typeChip: m6[3], sub: parseInt(m6[2], 10).toLocaleString('en-IN') };
  return { name: sym, typeChip: instrType && instrType !== 'EQ' ? instrType : 'EQ', sub: '' };
}

function minsAgo(n: number) { return subMinutes(new Date(), n).toISOString(); }

// ── Cumulative P&L sparkline ───────────────────────────────────────────────────
// Visible mini-chart shown in the right panel of the session hero card.

function PnlSparkline({ closed, unrealized, positive }: {
  closed: CompletedTrade[];
  unrealized: number;
  positive: boolean;
}) {
  const sorted = [...closed].sort((a, b) =>
    (a.exit_time ?? '').localeCompare(b.exit_time ?? ''));

  const pts: number[] = [0];
  sorted.forEach(t => pts.push(pts[pts.length - 1] + (t.realized_pnl ?? 0)));
  if (unrealized !== 0) pts.push(pts[pts.length - 1] + unrealized);

  if (pts.length < 2) {
    return (
      <div className="w-full h-full flex items-center justify-center">
        <span className="text-[10px] text-muted-foreground">—</span>
      </div>
    );
  }

  const W = 200; const H = 72; const PX = 4; const PY = 6;
  const min = Math.min(...pts, 0);
  const max = Math.max(...pts, 0);
  const range = max - min || 1;
  const toX = (i: number) => PX + (i / (pts.length - 1)) * (W - PX * 2);
  const toY = (v: number) => PY + ((max - v) / range) * (H - PY * 2);
  const zeroY = toY(0);

  const lineColor = positive ? 'rgb(var(--tm-profit))' : 'rgb(var(--tm-loss))';
  const fillId = `sf-${positive ? 'p' : 'l'}`;

  const polyPoints = pts.map((v, i) => `${toX(i)},${toY(v)}`).join(' ');
  const areaPoints = `${toX(0)},${zeroY} ${polyPoints} ${toX(pts.length - 1)},${zeroY}`;
  const endX = toX(pts.length - 1);
  const endY = toY(pts[pts.length - 1]);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="w-full h-full">
      <defs>
        <linearGradient id={fillId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={lineColor} stopOpacity="0.2" />
          <stop offset="100%" stopColor={lineColor} stopOpacity="0.02" />
        </linearGradient>
      </defs>
      {/* Zero reference line */}
      <line x1={PX} y1={zeroY} x2={W - PX} y2={zeroY}
        stroke="rgb(148 163 184 / 0.4)" strokeWidth="0.75" strokeDasharray="3 3" />
      {/* Area fill */}
      <polygon points={areaPoints} fill={`url(#${fillId})`} />
      {/* Line */}
      <polyline points={polyPoints} fill="none" stroke={lineColor}
        strokeWidth="1.75" strokeLinejoin="round" strokeLinecap="round" />
      {/* End dot */}
      <circle cx={endX} cy={endY} r="2.5" fill={lineColor} />
    </svg>
  );
}

// ── Demo data ──────────────────────────────────────────────────────────────────

const DEMO_POSITIONS: PositionWithExtras[] = [
  {
    id: 'dp1', tradingsymbol: 'NIFTY2541523500CE', exchange: 'NFO',
    instrument_type: 'CE', product: 'MIS', total_quantity: 75,
    average_entry_price: 112.40, average_exit_price: null,
    realized_pnl: 0, unrealized_pnl: 435, current_value: 8865,
    last_price: 118.20, status: 'open',
  },
  {
    id: 'dp2', tradingsymbol: 'BANKNIFTY2541652000PE', exchange: 'NFO',
    instrument_type: 'PE', product: 'MIS', total_quantity: -30,
    average_entry_price: 445.10, average_exit_price: null,
    realized_pnl: 0, unrealized_pnl: -531, current_value: 13893,
    last_price: 462.80, status: 'open',
  },
];

const DEMO_CLOSED: CompletedTrade[] = [
  {
    id: 'dc1', broker_account_id: 'demo', tradingsymbol: 'RELIANCE',
    exchange: 'NSE', instrument_type: 'EQ', product: 'MIS', direction: 'LONG',
    total_quantity: 100, num_entries: 1, num_exits: 1,
    avg_entry_price: 2910.00, avg_exit_price: 2895.00, realized_pnl: -1500,
    entry_time: minsAgo(200), exit_time: minsAgo(150), duration_minutes: 50,
    closed_by_flip: false, entry_trade_ids: [], exit_trade_ids: [], status: 'closed', created_at: minsAgo(200),
  },
  {
    id: 'dc2', broker_account_id: 'demo', tradingsymbol: 'NIFTY2541524600CE',
    exchange: 'NFO', instrument_type: 'CE', product: 'MIS', direction: 'SHORT',
    total_quantity: 150, num_entries: 1, num_exits: 1,
    avg_entry_price: 88.50, avg_exit_price: 94.20, realized_pnl: -855,
    entry_time: minsAgo(170), exit_time: minsAgo(130), duration_minutes: 40,
    closed_by_flip: false, entry_trade_ids: [], exit_trade_ids: [], status: 'closed', created_at: minsAgo(170),
  },
  {
    id: 'dc3', broker_account_id: 'demo', tradingsymbol: 'INFY',
    exchange: 'NSE', instrument_type: 'EQ', product: 'MIS', direction: 'LONG',
    total_quantity: 80, num_entries: 1, num_exits: 1,
    avg_entry_price: 1842.00, avg_exit_price: 1871.00, realized_pnl: 2320,
    entry_time: minsAgo(300), exit_time: minsAgo(240), duration_minutes: 60,
    closed_by_flip: false, entry_trade_ids: [], exit_trade_ids: [], status: 'closed', created_at: minsAgo(300),
  },
  {
    id: 'dc4', broker_account_id: 'demo', tradingsymbol: 'BANKNIFTY2541647500PE',
    exchange: 'NFO', instrument_type: 'PE', product: 'MIS', direction: 'LONG',
    total_quantity: 25, num_entries: 1, num_exits: 1,
    avg_entry_price: 310.00, avg_exit_price: 241.00, realized_pnl: -1725,
    entry_time: minsAgo(130), exit_time: minsAgo(100), duration_minutes: 30,
    closed_by_flip: false, entry_trade_ids: [], exit_trade_ids: [], status: 'closed', created_at: minsAgo(130),
  },
  {
    id: 'dc5', broker_account_id: 'demo', tradingsymbol: 'NIFTY2541522500PE',
    exchange: 'NFO', instrument_type: 'PE', product: 'MIS', direction: 'LONG',
    total_quantity: 50, num_entries: 1, num_exits: 1,
    avg_entry_price: 95.00, avg_exit_price: 103.50, realized_pnl: 425,
    entry_time: minsAgo(360), exit_time: minsAgo(320), duration_minutes: 40,
    closed_by_flip: false, entry_trade_ids: [], exit_trade_ids: [], status: 'closed', created_at: minsAgo(360),
  },
];

const DEMO_SHIELD: ShieldSummary = {
  total_alerts: 22, danger_count: 8, caution_count: 14,
  heeded_count: 15, continued_count: 7, post_alert_pnl_continued: -4120,
  heeded_streak: 4, spiral_sessions: 1,
};

const DEMO_ALERTS: AlertNotification[] = [
  {
    id: 'da1',
    pattern: {
      id: 'p1', type: 'revenge_trading' as any, name: 'Revenge Trading Pattern',
      severity: 'high' as any,
      description: 'Immediate re-entry detected after a ₹1,200 loss within 120 seconds',
      detected_at: minsAgo(58), insight: null, historical_insight: null,
      estimated_cost: 1200, trades_involved: ['dc2', 'dc3'],
      frequency_this_week: 3, frequency_this_month: 7,
    },
    shown_at: minsAgo(58), acknowledged: false,
  },
  {
    id: 'da2',
    pattern: {
      id: 'p2', type: 'overtrading' as any, name: 'Over-Leveraged Entry',
      severity: 'medium' as any,
      description: 'Position size exceeds daily risk limit by 40% in NIFTY 24500 CE',
      detected_at: minsAgo(115), insight: null, historical_insight: null,
      estimated_cost: 0, trades_involved: [],
      frequency_this_week: 1, frequency_this_month: 4,
    },
    shown_at: minsAgo(115), acknowledged: false,
  },
  {
    id: 'da3',
    pattern: {
      id: 'p3', type: 'loss_aversion' as any, name: 'Stop-Loss Widening',
      severity: 'low' as any,
      description: 'Stop-loss moved 4 times against price movement this session',
      detected_at: minsAgo(175), insight: null, historical_insight: null,
      estimated_cost: 0, trades_involved: ['dc5'],
      frequency_this_week: 2, frequency_this_month: 5,
    },
    shown_at: minsAgo(175), acknowledged: true,
  },
];

// ── Component ──────────────────────────────────────────────────────────────────

export default function DashboardV2() {
  const navigate = useNavigate();
  const { account, syncTrades, syncStatus } = useBroker();
  const { lastTradeEvent } = useWebSocket();
  const { alerts: liveAlerts, unacknowledgedCount, acknowledgeAlert } = useAlerts();

  const [positions,       setPositions]       = useState<PositionWithExtras[]>([]);
  const [closedTrades,    setClosedTrades]    = useState<CompletedTrade[]>([]);
  const [shield,          setShield]          = useState<ShieldSummary | null>(null);
  const [posLoading,      setPosLoading]      = useState(false);
  const [tradesLoading,   setTradesLoading]   = useState(false);
  const [isSyncing,       setIsSyncing]       = useState(false);
  const [initialLoadDone, setInitialLoadDone] = useState(false);
  const [journaledIds,    setJournaledIds]    = useState<Set<string>>(new Set());
  const [selectedAlert,   setSelectedAlert]   = useState<AlertNotification | null>(null);
  const [journalOpen,     setJournalOpen]     = useState(false);
  const [journalTrade,    setJournalTrade]    = useState<PositionWithExtras | CompletedTrade | null>(null);
  const [journalType,     setJournalType]     = useState<'position' | 'closed'>('closed');
  const journalTradeIdRef = useRef<string | null>(null);
  const accountIdRef      = useRef(account?.id);
  accountIdRef.current    = account?.id;

  useEffect(() => {
    if (!localStorage.getItem(AUTH_TOKEN_KEY) && !isGuestMode()) {
      navigate('/welcome', { replace: true });
    }
  }, [navigate]);

  // ── Fetchers ───────────────────────────────────────────────────────────────

  const fetchPositions = useCallback(async () => {
    if (!accountIdRef.current) return;
    try {
      setPosLoading(true);
      const { data } = await api.get('/api/positions/', {
        params: { broker_account_id: accountIdRef.current },
      });
      const raw: Position[] = Array.isArray(data) ? data : (data.positions ?? []);
      setPositions(raw.filter(p => p.status === 'open').map(p => ({
        ...p,
        instrument_type: p.instrument_type ?? 'EQ',
        unrealized_pnl:  p.unrealized_pnl ?? p.pnl ?? p.m2m ?? 0,
        current_value:   p.current_value  ?? (p.last_price ?? 0) * Math.abs(p.total_quantity ?? 0),
      })));
    } catch { setPositions([]); } finally { setPosLoading(false); }
  }, []);

  const fetchClosedTrades = useCallback(async () => {
    if (!accountIdRef.current) return;
    try {
      setTradesLoading(true);
      const { data } = await api.get('/api/trades/completed', {
        params: { broker_account_id: accountIdRef.current, limit: 50 },
      });
      const raw: CompletedTrade[] = Array.isArray(data) ? data : (data.trades ?? []);
      setClosedTrades(raw.filter(t => {
        try { return isToday(parseISO(t.exit_time)); } catch { return false; }
      }));
    } catch { setClosedTrades([]); } finally { setTradesLoading(false); }
  }, []);

  const fetchShield = useCallback(async () => {
    if (!accountIdRef.current) return;
    try {
      const { data } = await api.get('/api/shield/summary', {
        params: { days: 30, broker_account_id: accountIdRef.current },
      });
      setShield(data);
    } catch { setShield(null); }
  }, []);

  useEffect(() => {
    if (!account?.id) { setInitialLoadDone(true); return; }
    Promise.all([fetchPositions(), fetchClosedTrades(), fetchShield()])
      .finally(() => setInitialLoadDone(true));
  }, [account?.id, fetchPositions, fetchClosedTrades, fetchShield]);

  useEffect(() => {
    if (lastTradeEvent) { fetchPositions(); fetchClosedTrades(); }
  }, [lastTradeEvent, fetchPositions, fetchClosedTrades]);

  const handleSync = useCallback(async () => {
    if (!account?.id || isSyncing) return;
    try {
      setIsSyncing(true);
      await syncTrades(account.id);
      await Promise.all([fetchPositions(), fetchClosedTrades()]);
    } finally { setIsSyncing(false); }
  }, [account?.id, isSyncing, syncTrades, fetchPositions, fetchClosedTrades]);

  // ── Demo fallback ──────────────────────────────────────────────────────────

  const isUsingDemo    = positions.length === 0 && closedTrades.length === 0;
  const displayPos     = positions.length    > 0 ? positions    : DEMO_POSITIONS;
  const displayClosed  = closedTrades.length > 0 ? closedTrades : DEMO_CLOSED;
  const displayShield  = shield ?? DEMO_SHIELD;
  const displayAlerts  = liveAlerts.length   > 0 ? liveAlerts   : DEMO_ALERTS;
  const displayUnread  = liveAlerts.length   > 0
    ? unacknowledgedCount
    : DEMO_ALERTS.filter(a => !a.acknowledged).length;

  // ── Derived stats ──────────────────────────────────────────────────────────

  const realizedPnl    = displayClosed.reduce((s, t) => s + (t.realized_pnl ?? 0), 0);
  const unrealizedPnl  = displayPos.reduce((s, p) => s + (p.unrealized_pnl ?? 0), 0);
  const sessionPnl     = realizedPnl + unrealizedPnl;
  const winCount       = displayClosed.filter(t => (t.realized_pnl ?? 0) > 0).length;
  const winRate        = displayClosed.length > 0
    ? (winCount / displayClosed.length * 100).toFixed(1)
    : null;
  const pendingJournals = displayClosed.filter(t => !journaledIds.has(t.id)).length;
  const tradeCount      = displayClosed.length + displayPos.length;
  const avgPerDay       = 5;
  const pacePercent     = Math.round((tradeCount / avgPerDay - 1) * 100);

  // Session state
  const highSevCount  = displayAlerts.filter(
    a => a.pattern.severity === 'high' || a.pattern.severity === 'critical',
  ).length;
  const sessionState  = getSessionState(
    displayUnread, highSevCount, pacePercent, winRate ? parseFloat(winRate) : null,
  );
  const stateCfg      = STATE_CFG[sessionState];
  const stateDesc     = sessionState === 'risk'
    ? 'Multiple patterns active — review before your next trade'
    : sessionState === 'caution'
      ? pacePercent > 30
        ? `Trade pace ${pacePercent}% above your average — watch for overtrading`
        : `${displayUnread} behavioral pattern${displayUnread !== 1 ? 's' : ''} noted this session`
      : tradeCount === 0 ? 'No trades yet — market is open'
      : 'Session tracking normally';

  const recentAlerts = [...displayAlerts]
    .sort((a, b) => (b.pattern.detected_at ?? '').localeCompare(a.pattern.detected_at ?? ''))
    .slice(0, 4);

  const sortedClosed = [...displayClosed].sort((a, b) => {
    const aj = journaledIds.has(a.id) ? 1 : 0;
    const bj = journaledIds.has(b.id) ? 1 : 0;
    return aj !== bj ? aj - bj : (b.exit_time ?? '').localeCompare(a.exit_time ?? '');
  });

  // Session pace bar — fill % capped at 100, turns amber when over avg
  const paceBarPct = Math.min(100, Math.round((tradeCount / (avgPerDay * 1.5)) * 100));

  // ── Journal handlers ───────────────────────────────────────────────────────

  function openJournal(trade: PositionWithExtras | CompletedTrade, type: 'position' | 'closed') {
    journalTradeIdRef.current = trade.id;
    setJournalTrade(trade);
    setJournalType(type);
    setJournalOpen(true);
  }

  function handleJournalClose(open: boolean) {
    if (!open && journalTradeIdRef.current) {
      setJournaledIds(prev => new Set(prev).add(journalTradeIdRef.current!));
      journalTradeIdRef.current = null;
    }
    setJournalOpen(open);
  }

  // ── Shared table column defs ───────────────────────────────────────────────

  const positionCols = ['Symbol', 'Side', 'Qty', 'Avg', 'LTP', 'P&L', ''];
  const closedCols   = ['Symbol', 'Side', 'Qty', 'Entry', 'Exit', 'Net P&L', ''];

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="tm-page-bg min-h-screen flex flex-col">
      <TopNavbar
        tradeCount={tradeCount}
        onSync={handleSync}
        isSyncing={isSyncing || syncStatus === 'syncing'}
        activeHref="/dashboard-v2"
      />

      {/* Demo banner */}
      {isUsingDemo && initialLoadDone && (
        <div className="fixed top-[60px] left-0 right-0 z-40 bg-amber-50 dark:bg-amber-950/60 border-b border-amber-200 dark:border-amber-800/50 text-center py-1.5">
          <span className="text-xs font-medium text-tm-obs">
            Showing demo data — connect Zerodha to see real trades
          </span>
        </div>
      )}

      <div className="flex-1">
        <div className={cn(
          'max-w-[1200px] mx-auto px-6 pb-12',
          isUsingDemo && initialLoadDone ? 'pt-[92px]' : 'pt-[80px]',
        )}>

          {/* ── Page header ───────────────────────────────────────────────────── */}
          <div className="flex items-center justify-between mb-5">
            <h1 className="text-xl font-semibold text-foreground tracking-tight">Dashboard</h1>
            <span className="text-[13px] text-muted-foreground font-mono tabular-nums">
              {tradeCount} trades today
            </span>
          </div>

          {/* ── Session Hero — Behavioral State + P&L + Sparkline ─────────────── */}
          <div className="tm-card mb-5">
            <div className="flex items-stretch">

              {/* LEFT: state pill + P&L number + description */}
              <div className="flex-1 min-w-0 px-5 pt-4 pb-3">
                <div className="flex items-center justify-between mb-3">
                  <div className={cn(
                    'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-bold uppercase tracking-widest',
                    stateCfg.pillBg, stateCfg.labelCls,
                  )}>
                    <span className={cn('w-1.5 h-1.5 rounded-full', stateCfg.dotCls)} />
                    {stateCfg.label}
                  </div>
                  <span className="tm-label">Today's Session</span>
                </div>

                <div className="mb-1">
                  <span className={cn(
                    'text-[32px] font-black font-mono tabular-nums leading-none',
                    sessionPnl > 0 ? 'text-tm-profit'
                      : sessionPnl < 0 ? 'text-tm-loss'
                      : 'text-muted-foreground',
                  )}>
                    {sessionPnl >= 0 ? '+' : '–'}₹{Math.abs(sessionPnl).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                  </span>
                </div>

                <p className="text-[13px] text-muted-foreground leading-relaxed">
                  {stateDesc}
                </p>
              </div>

              {/* RIGHT: cumulative P&L sparkline */}
              <div className="w-[176px] shrink-0 border-l border-slate-100 dark:border-neutral-700/60 px-4 pt-4 pb-3 flex flex-col">
                <span className="tm-label mb-2">Cumulative P&L</span>
                <div className="flex-1">
                  <PnlSparkline
                    closed={displayClosed}
                    unrealized={unrealizedPnl}
                    positive={sessionPnl >= 0}
                  />
                </div>
                <div className="flex items-center justify-between mt-1.5">
                  <span className="text-[10px] text-muted-foreground">open → now</span>
                  <span className={cn(
                    'text-[11px] font-mono tabular-nums font-semibold',
                    sessionPnl > 0 ? 'text-tm-profit' : sessionPnl < 0 ? 'text-tm-loss' : 'text-muted-foreground',
                  )}>
                    {fmtPnl(sessionPnl)}
                  </span>
                </div>
              </div>
            </div>

            {/* Stat row — full-width footer */}
            <div className="flex items-center flex-wrap gap-y-1 border-t border-slate-100 dark:border-neutral-700/60 px-5 py-2.5">
              <span className="text-[13px] font-mono tabular-nums text-muted-foreground pr-4">
                {tradeCount} trade{tradeCount !== 1 ? 's' : ''}
              </span>
              {winRate !== null && (
                <>
                  <span className="w-px h-3.5 shrink-0 bg-slate-200 dark:bg-neutral-700" />
                  <span className="text-[13px] font-mono tabular-nums text-muted-foreground px-4">
                    {winRate}% win rate
                  </span>
                </>
              )}
              <span className="w-px h-3.5 shrink-0 bg-slate-200 dark:bg-neutral-700" />
              <span className={cn(
                'text-[13px] font-mono tabular-nums font-medium px-4',
                realizedPnl > 0 ? 'text-tm-profit' : realizedPnl < 0 ? 'text-tm-loss' : 'text-muted-foreground',
              )}>
                {fmtPnl(realizedPnl)} realized
              </span>
              {pendingJournals > 0 && (
                <>
                  <span className="w-px h-3.5 shrink-0 bg-slate-200 dark:bg-neutral-700" />
                  <span className="text-[13px] text-muted-foreground pl-4">
                    {pendingJournals} to journal
                  </span>
                </>
              )}
              {displayUnread > 0 && (
                <>
                  <span className="w-px h-3.5 shrink-0 bg-slate-200 dark:bg-neutral-700" />
                  <Link
                    to="/alerts"
                    className={cn('text-[13px] font-medium pl-4', stateCfg.labelCls)}
                  >
                    {displayUnread} alert{displayUnread !== 1 ? 's' : ''} →
                  </Link>
                </>
              )}
            </div>
          </div>

          {/* ── Behavioral Alerts ─────────────────────────────────────────────── */}
          <div className="tm-card mb-5">
            <div className="flex items-center justify-between px-5 py-3 border-b border-slate-100 dark:border-neutral-700/60">
              <div className="flex items-center gap-3">
                <span className="tm-label">Behavioral Alerts</span>
                {displayUnread > 0 && (
                  <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-amber-100 text-amber-700 dark:bg-amber-800/40 dark:text-amber-300">
                    {displayUnread} unread
                  </span>
                )}
              </div>
              {displayAlerts.length > 4 && (
                <Link to="/alerts" className="text-[13px] font-medium text-tm-brand hover:underline">
                  View all {displayAlerts.length} →
                </Link>
              )}
            </div>

            {displayAlerts.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-8">No observations today</p>
            ) : (
              <div>
                {recentAlerts.map((alert, i) => (
                  <button
                    key={alert.id}
                    onClick={() => setSelectedAlert(alert)}
                    className={cn(
                      'w-full flex items-start gap-4 px-5 py-4 text-left transition-colors',
                      'hover:bg-slate-50 dark:hover:bg-slate-700/40',
                      i < recentAlerts.length - 1 && 'border-b border-slate-50 dark:border-neutral-700/40',
                    )}
                  >
                    <span
                      className={cn('mt-[5px] shrink-0 rounded-full', severityDotClass(alert.pattern.severity))}
                      style={{ width: 7, height: 7, minWidth: 7 }}
                    />
                    <div className="flex-1 min-w-0">
                      <p className={cn(
                        'text-sm leading-snug',
                        alert.pattern.severity === 'critical' || alert.pattern.severity === 'high'
                          ? 'font-semibold text-foreground'
                          : alert.pattern.severity === 'medium'
                            ? 'font-medium text-foreground/90 dark:text-foreground/80'
                            : 'font-normal text-muted-foreground',
                      )}>
                        {alert.pattern.name}
                      </p>
                      <p className="text-[13px] text-muted-foreground mt-0.5 leading-snug">
                        {alert.pattern.description}
                      </p>
                    </div>
                    <div className="shrink-0 flex items-center gap-1.5 pt-0.5">
                      <span className="text-[12px] text-muted-foreground font-mono tabular-nums">
                        {fmtTime(alert.pattern.detected_at ?? alert.shown_at)}
                      </span>
                      <ChevronRight className="w-3.5 h-3.5 text-muted-foreground/50" />
                    </div>
                  </button>
                ))}
                {displayAlerts.length > 4 && (
                  <div className="border-t border-slate-100 dark:border-neutral-700/60 px-5 py-3">
                    <Link to="/alerts" className="text-[13px] font-medium text-tm-brand hover:underline">
                      View all {displayAlerts.length} alerts →
                    </Link>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* ── Two-column layout ─────────────────────────────────────────────── */}
          <div className="flex gap-5 items-start">

            {/* LEFT — 62% */}
            <div className="flex-[62] min-w-0 space-y-5">

              {/* ── Open Positions ──────────────────────────────────────────── */}
              <div className="tm-card">
                <div className="flex items-center justify-between px-5 py-3 border-b border-slate-100 dark:border-neutral-700/60">
                  <div className="flex items-center gap-2">
                    <span className="tm-label">Open Positions</span>
                    <span className="text-[11px] text-muted-foreground font-mono tabular-nums">
                      {displayPos.length}
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-teal-50 dark:bg-teal-900/30">
                    <span className="w-1.5 h-1.5 rounded-full animate-pulse bg-teal-500 dark:bg-teal-400" />
                    <span className="text-[11px] font-semibold text-teal-600 dark:text-teal-400 uppercase tracking-wide">Live</span>
                  </div>
                </div>

                {posLoading ? (
                  <div className="flex justify-center py-10">
                    <Loader2 className="w-5 h-5 text-muted-foreground/40 animate-spin" />
                  </div>
                ) : (
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-slate-100 dark:border-neutral-700/60">
                        {positionCols.map((h, idx) => (
                          <th key={idx} className={cn(
                            'py-2.5 table-header',
                            idx === 0 ? 'px-5 text-left' :
                            idx === positionCols.length - 1 ? 'px-5 w-10 text-left' :
                            'px-3 text-right',
                          )}>
                            {h === '' ? <Pencil className="w-3 h-3 text-muted-foreground/50" /> : h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {displayPos.map((pos, i) => {
                        const pnl = pos.unrealized_pnl ?? 0;
                        const qty = pos.total_quantity ?? 0;
                        const isJournaled = journaledIds.has(pos.id);
                        const { name, typeChip, sub } = fmtSymbol(pos.tradingsymbol, pos.instrument_type);
                        return (
                          <tr key={pos.id} className={cn(
                            'transition-colors hover:bg-slate-50 dark:hover:bg-slate-700/30',
                            i < displayPos.length - 1 && 'border-b border-slate-50 dark:border-neutral-700/30',
                            pnl > 0 && 'bg-tm-profit/[0.03]',
                            pnl < 0 && 'bg-tm-loss/[0.03]',
                          )}>
                            <td className="px-5 py-2.5">
                              <div className="flex items-center gap-1.5">
                                <span className="text-sm font-semibold text-foreground leading-none">{name}</span>
                                <span className={cn('tm-chip', typeChip === 'CE' ? 'tm-chip-ce' : typeChip === 'PE' ? 'tm-chip-pe' : 'tm-chip-eq')}>
                                  {typeChip}
                                </span>
                              </div>
                              {sub && (
                                <span className="text-[11px] text-muted-foreground font-mono tabular-nums mt-0.5 block">
                                  {sub} · {pos.product}
                                </span>
                              )}
                            </td>
                            <td className="px-3 text-right">
                              <span className={cn('text-sm font-semibold', qty > 0 ? 'text-tm-profit' : 'text-tm-loss')}>
                                {qty > 0 ? 'BUY' : 'SELL'}
                              </span>
                            </td>
                            <td className="px-3 text-right text-sm font-mono tabular-nums text-foreground">
                              {Math.abs(qty)}
                            </td>
                            <td className="px-3 text-right text-sm font-mono tabular-nums text-foreground">
                              {fmtPrice(pos.average_entry_price)}
                            </td>
                            <td className="px-3 text-right text-sm font-mono tabular-nums text-foreground">
                              {fmtPrice(pos.last_price)}
                            </td>
                            <td className="px-3 text-right">
                              <span className={cn(
                                'text-sm font-mono tabular-nums font-semibold',
                                pnl > 0 ? 'text-tm-profit' : pnl < 0 ? 'text-tm-loss' : 'text-muted-foreground',
                              )}>
                                {fmtPnl(pnl)}
                              </span>
                            </td>
                            <td className="px-5">
                              <button onClick={() => openJournal(pos, 'position')}
                                className="w-7 h-7 flex items-center justify-center rounded hover:bg-muted/60 transition-colors relative">
                                {isJournaled
                                  ? <CheckCircle2 className="w-[18px] h-[18px] text-tm-profit" />
                                  : <><Pencil className="w-[14px] h-[14px] text-muted-foreground" />
                                     <span className="absolute top-0.5 right-0.5 w-[5px] h-[5px] rounded-full bg-tm-obs" /></>
                                }
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                )}
              </div>

              {/* ── Closed Today ────────────────────────────────────────────── */}
              <div className="tm-card">
                <div className="flex items-center justify-between px-5 py-3 border-b border-slate-100 dark:border-neutral-700/60">
                  <div className="flex items-center gap-2">
                    <span className="tm-label">Closed Today</span>
                    <span className="text-[11px] text-muted-foreground font-mono tabular-nums">
                      {displayClosed.length}
                    </span>
                  </div>
                  {pendingJournals > 0 && (
                    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-amber-100 text-amber-700 dark:bg-amber-800/40 dark:text-amber-300">
                      {pendingJournals} to journal
                    </span>
                  )}
                </div>

                {tradesLoading ? (
                  <div className="flex justify-center py-10">
                    <Loader2 className="w-5 h-5 text-muted-foreground/40 animate-spin" />
                  </div>
                ) : (
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-slate-100 dark:border-neutral-700/60">
                        {closedCols.map((h, idx) => (
                          <th key={idx} className={cn(
                            'py-2.5 table-header',
                            idx === 0 ? 'px-5 text-left' :
                            idx === closedCols.length - 1 ? 'px-5 w-10 text-left' :
                            'px-3 text-right',
                          )}>
                            {h === '' ? <Pencil className="w-3 h-3 text-muted-foreground/50" /> : h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {sortedClosed.map((trade, i) => {
                        const pnl = trade.realized_pnl ?? 0;
                        const isJournaled = journaledIds.has(trade.id);
                        const { name, typeChip, sub } = fmtSymbol(trade.tradingsymbol, trade.instrument_type);
                        return (
                          <tr key={trade.id} className={cn(
                            'transition-colors hover:bg-slate-50 dark:hover:bg-slate-700/30',
                            i < sortedClosed.length - 1 && 'border-b border-slate-50 dark:border-neutral-700/30',
                            pnl > 0 && 'bg-tm-profit/[0.03]',
                            pnl < 0 && 'bg-tm-loss/[0.03]',
                          )}>
                            <td className="px-5 py-2.5">
                              <div className="flex items-center gap-1.5">
                                <span className="text-sm font-semibold text-foreground leading-none">{name}</span>
                                <span className={cn('tm-chip', typeChip === 'CE' ? 'tm-chip-ce' : typeChip === 'PE' ? 'tm-chip-pe' : 'tm-chip-eq')}>
                                  {typeChip}
                                </span>
                              </div>
                              {sub && (
                                <span className="text-[11px] text-muted-foreground font-mono tabular-nums mt-0.5 block">
                                  {sub} · {trade.product}
                                </span>
                              )}
                            </td>
                            <td className="px-3 text-right">
                              <span className={cn('text-sm font-semibold', trade.direction === 'LONG' ? 'text-tm-profit' : 'text-tm-loss')}>
                                {trade.direction === 'LONG' ? 'BUY' : 'SELL'}
                              </span>
                            </td>
                            <td className="px-3 text-right text-sm font-mono tabular-nums text-foreground">
                              {trade.total_quantity}
                            </td>
                            <td className="px-3 text-right text-sm font-mono tabular-nums text-foreground">
                              {fmtPrice(trade.avg_entry_price)}
                            </td>
                            <td className="px-3 text-right text-sm font-mono tabular-nums text-foreground">
                              {fmtPrice(trade.avg_exit_price)}
                            </td>
                            <td className="px-3 text-right">
                              <span className={cn(
                                'text-sm font-mono tabular-nums font-semibold',
                                pnl > 0 ? 'text-tm-profit' : pnl < 0 ? 'text-tm-loss' : 'text-muted-foreground',
                              )}>
                                {fmtPnl(pnl)}
                              </span>
                            </td>
                            <td className="px-5">
                              <button onClick={() => openJournal(trade, 'closed')}
                                className="w-7 h-7 flex items-center justify-center rounded hover:bg-muted/60 transition-colors relative">
                                {isJournaled
                                  ? <CheckCircle2 className="w-[18px] h-[18px] text-tm-profit" />
                                  : <><Pencil className="w-[14px] h-[14px] text-muted-foreground" />
                                     <span className="absolute top-0.5 right-0.5 w-[5px] h-[5px] rounded-full bg-tm-obs" /></>
                                }
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                )}
              </div>
            </div>

            {/* RIGHT — 38%, sticky */}
            <div className="flex-[38] min-w-0 space-y-4 sticky top-[80px]">

              {/* ── Blowup Shield ──────────────────────────────────────────── */}
              {/* Subtle teal gradient to give this card a "protected" feel     */}
              <div className="tm-card p-5 bg-gradient-to-br from-teal-50 via-white to-white dark:from-teal-950/40 dark:via-slate-800 dark:to-slate-800">
                <div className="flex items-center justify-between mb-4">
                  <span className="tm-label">Blowup Shield</span>
                  <Shield className="w-4 h-4 text-teal-400 dark:text-teal-500" />
                </div>

                {/* Heeded rate — hero number */}
                {(() => {
                  const heedRate = (displayShield.total_alerts > 0 && Number.isFinite(displayShield.heeded_count))
                    ? Math.round((displayShield.heeded_count ?? 0) / displayShield.total_alerts * 100)
                    : null;
                  const additionalLoss = Number.isFinite(displayShield.post_alert_pnl_continued) && displayShield.post_alert_pnl_continued < 0
                    ? displayShield.post_alert_pnl_continued : null;
                  return (
                    <>
                      <div className="flex items-end gap-2 mb-1">
                        <span className={cn(
                          'text-[44px] font-black font-mono tabular-nums leading-none',
                          heedRate === null ? 'text-foreground' :
                            heedRate >= 70 ? 'text-tm-profit' :
                            heedRate >= 40 ? 'text-tm-obs' : 'text-tm-loss',
                        )}>
                          {heedRate !== null ? `${heedRate}%` : '—'}
                        </span>
                      </div>
                      <p className="text-[13px] text-muted-foreground mb-4">
                        alerts heeded · {displayShield.heeded_count}/{displayShield.total_alerts}
                      </p>
                      <div className="h-1.5 rounded-full overflow-hidden mb-4 bg-muted">
                        <div
                          className={cn(
                            'h-full rounded-full transition-all',
                            (heedRate ?? 0) >= 70 ? 'bg-tm-profit' :
                              (heedRate ?? 0) >= 40 ? 'bg-tm-obs' : 'bg-tm-loss',
                          )}
                          style={{ width: `${heedRate ?? 0}%` }}
                        />
                      </div>
                      {additionalLoss !== null && (
                        <div className="flex items-center justify-between rounded-lg px-3 py-2.5 bg-red-50/80 dark:bg-red-900/10 border border-red-100 dark:border-red-800/30">
                          <span className="tm-label">After ignored alerts</span>
                          <span className="text-sm font-semibold text-tm-loss font-mono tabular-nums">
                            {formatCurrencyWithSign(additionalLoss)}
                          </span>
                        </div>
                      )}
                    </>
                  );
                })()}
              </div>

              {/* ── Session Pace ────────────────────────────────────────────── */}
              <div className="tm-card p-5">
                <div className="flex items-center justify-between mb-3">
                  <span className="tm-label">Session Pace</span>
                  <TrendingUp className="w-4 h-4 text-muted-foreground/50" />
                </div>

                <div className="flex items-baseline gap-2.5 mb-0.5">
                  <span className={cn(
                    'text-[36px] font-black font-mono tabular-nums leading-none',
                    pacePercent > 40 ? 'text-tm-obs' : 'text-foreground',
                  )}>
                    {tradeCount}
                  </span>
                  {pacePercent !== 0 && (
                    <span className={cn(
                      'text-sm font-semibold',
                      pacePercent > 0 ? 'text-tm-obs' : 'text-tm-profit',
                    )}>
                      {pacePercent > 0 ? `↑ ${pacePercent}%` : `↓ ${Math.abs(pacePercent)}%`}
                    </span>
                  )}
                </div>
                <p className="text-[13px] text-muted-foreground mb-4">
                  trades today · avg {avgPerDay}/day
                </p>

                {/* Pace bar — fills toward 1.5× avg, turns amber at high pace */}
                <div className="h-1.5 rounded-full overflow-hidden bg-slate-100 dark:bg-neutral-700/60 mb-1.5">
                  <div
                    className={cn(
                      'h-full rounded-full transition-all',
                      pacePercent > 40 ? 'bg-tm-obs' : 'bg-tm-brand',
                    )}
                    style={{
                      width: `${paceBarPct}%`,
                      boxShadow: pacePercent > 40
                        ? '0 0 6px rgba(230,138,0,0.5)'
                        : '0 0 6px rgba(15,142,125,0.4)',
                    }}
                  />
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[10px] text-muted-foreground">0</span>
                  <span className="text-[10px] text-muted-foreground">{Math.round(avgPerDay * 1.5)} (1.5× avg)</span>
                </div>
              </div>

              {/* ── AI Coach CTA ─────────────────────────────────────────────── */}
              <Link
                to="/chat"
                className="flex items-center gap-3 rounded-xl p-4 hover:opacity-95 transition-opacity group"
                style={{
                  background: 'linear-gradient(135deg, #0F8E7D 0%, #0A7A6B 100%)',
                  boxShadow: '0 4px 20px rgba(15,142,125,0.3), 0 0 0 1px rgba(15,142,125,0.2)',
                }}
              >
                <div className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0 bg-white/15">
                  <BarChart2 className="w-4 h-4 text-white" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-white">Ask AI Coach</p>
                  <p className="text-[12px] text-white/70">Analyse today's session</p>
                </div>
                <ChevronRight className="w-4 h-4 text-white/40 group-hover:text-white transition-colors" />
              </Link>
            </div>
          </div>
        </div>
      </div>

      {/* ── Footer ───────────────────────────────────────────────────────────── */}
      <footer className="bg-slate-800 border-t border-white/[0.06]">
        <div className="max-w-[1200px] mx-auto px-6 py-5 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-5 h-5 rounded bg-tm-brand flex items-center justify-center shrink-0">
              <span className="text-white font-bold" style={{ fontSize: 9 }}>TM</span>
            </div>
            <span className="text-slate-400 text-sm font-medium">TradeMentor AI</span>
          </div>
          <div className="flex items-center gap-5 text-slate-500 text-[13px]">
            <Link to="/terms"   className="hover:text-slate-300 transition-colors">Terms</Link>
            <Link to="/privacy" className="hover:text-slate-300 transition-colors">Privacy</Link>
            <span>© {new Date().getFullYear()}</span>
          </div>
        </div>
      </footer>

      {/* ── Alert detail bottom sheet ─────────────────────────────────────────── */}
      {selectedAlert && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-end justify-center"
          onClick={() => setSelectedAlert(null)}>
          <div className="rounded-t-xl shadow-xl w-full max-w-xl pb-8 bg-white dark:bg-neutral-800"
            onClick={e => e.stopPropagation()}>
            <div className="w-10 h-1 bg-muted rounded-full mx-auto mt-3 mb-5" />
            <div className="px-6">
              <div className="flex items-start gap-3 mb-4">
                <span
                  className={cn('mt-1 rounded-full shrink-0', severityDotClass(selectedAlert.pattern.severity))}
                  style={{ width: 8, height: 8, minWidth: 8 }}
                />
                <div>
                  <h2 className="text-base font-semibold text-foreground leading-snug">
                    {selectedAlert.pattern.name}
                  </h2>
                  <p className="text-[13px] text-muted-foreground mt-1 leading-relaxed">
                    {selectedAlert.pattern.description}
                  </p>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3 mb-5">
                {selectedAlert.pattern.estimated_cost > 0 && (
                  <div className="rounded-lg px-4 py-3 bg-slate-50 dark:bg-neutral-700/40">
                    <p className="tm-label mb-1">Estimated Cost</p>
                    <p className="text-sm font-semibold font-mono tabular-nums text-tm-loss">
                      –₹{selectedAlert.pattern.estimated_cost.toLocaleString('en-IN')}
                    </p>
                  </div>
                )}
                <div className="rounded-lg px-4 py-3 bg-slate-50 dark:bg-neutral-700/40">
                  <p className="tm-label mb-1">This Month</p>
                  <p className="text-sm font-semibold font-mono tabular-nums text-foreground">
                    {selectedAlert.pattern.frequency_this_month}× detected
                  </p>
                </div>
                <div className="rounded-lg px-4 py-3 bg-slate-50 dark:bg-neutral-700/40">
                  <p className="tm-label mb-1">Detected at</p>
                  <p className="text-sm font-semibold font-mono tabular-nums text-foreground">
                    {fmtTime(selectedAlert.pattern.detected_at ?? selectedAlert.shown_at)}
                  </p>
                </div>
              </div>
              <Link
                to="/alerts"
                className="flex items-center justify-center gap-2 w-full py-2.5 rounded-lg text-sm font-medium text-tm-brand border border-tm-brand/30 hover:bg-tm-brand/5 transition-colors"
                onClick={() => setSelectedAlert(null)}
              >
                View full alert history
                <ChevronRight className="w-4 h-4" />
              </Link>
            </div>
          </div>
        </div>
      )}

      {/* Journal sheet */}
      {journalTrade && (
        <TradeJournalSheet
          open={journalOpen}
          onOpenChange={handleJournalClose}
          trade={journalTrade}
          tradeType={journalType}
        />
      )}
    </div>
  );
}
