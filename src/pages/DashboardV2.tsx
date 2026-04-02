/**
 * DashboardV2 — Design preview page
 * /dashboard-v2 — outside Layout wrapper, own TopNavbar.
 * Falls back to DEMO data when API returns empty so design is always visible.
 *
 * Color tokens (from screenshot analysis):
 *   Background : #F4F7F7
 *   Surface    : #FFFFFF  (cards, rounded-xl, shadow-sm)
 *   Primary    : #0F8E7D  (teal — brand, profit, BUY, links)
 *   Text       : #1C2D33  (deep slate — headings & body)
 *   Loss/Red   : #B13D44
 *   Amber      : #E68A00  (alerts, warnings)
 */
import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { ChevronRight, Pencil, CheckCircle2, Loader2, BarChart2, Shield, Clock } from 'lucide-react';
import { cn } from '@/lib/utils';
import { api, AUTH_TOKEN_KEY } from '@/lib/api';
import { isGuestMode } from '@/lib/guestMode';
import { useAlerts } from '@/contexts/AlertContext';
import { useBroker } from '@/contexts/BrokerContext';
import { useWebSocket } from '@/contexts/WebSocketContext';
import { Position, CompletedTrade, ShieldSummary } from '@/types/api';
import { AlertNotification } from '@/contexts/AlertContext';
import { TradeJournalSheet } from '@/components/dashboard/TradeJournalSheet';
import TopNavbar from '@/components/dashboard-v2/TopNavbar';
import { format, parseISO, isToday, subMinutes } from 'date-fns';

// ── Types ──────────────────────────────────────────────────────────────────────

type PositionWithExtras = Position & {
  instrument_type: string;
  unrealized_pnl: number;
  current_value: number;
};

// ── Color constants (single source of truth for the non-Tailwind values) ──────

const C = {
  profit:  '#0F8E7D',
  loss:    '#B13D44',
  amber:   '#E68A00',
  text:    '#1C2D33',
  muted:   '#64748B',
  teal:    '#0F8E7D',
} as const;

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

/** Severity → dot color */
function dotColor(sev: string): string {
  if (sev === 'critical' || sev === 'high') return C.loss;
  if (sev === 'medium') return C.amber;
  return '#94A3B8';
}

/** Parse F&O symbol → { name, tag }
 *  NIFTY2541523500CE  → name="NIFTY"   tag="CE · 23,500"
 *  BANKNIFTY2541647000PE → name="BANKNIFTY" tag="PE · 47,000"
 *  RELIANCE / INFY    → name="RELIANCE" tag="EQ"
 */
function fmtSymbol(sym: string, instrType?: string): { name: string; tag: string } {
  const m5 = sym.match(/^([A-Z]+)\d{5}(\d{5})(CE|PE)$/);
  if (m5) return { name: m5[1], tag: `${m5[3]} · ${parseInt(m5[2], 10).toLocaleString('en-IN')}` };
  const m6 = sym.match(/^([A-Z]+)\d{5}(\d{6})(CE|PE)$/);
  if (m6) return { name: m6[1], tag: `${m6[3]} · ${parseInt(m6[2], 10).toLocaleString('en-IN')}` };
  return { name: sym, tag: instrType && instrType !== 'EQ' ? instrType : 'EQ' };
}

function minsAgo(n: number) { return subMinutes(new Date(), n).toISOString(); }

// ── Shared card class ──────────────────────────────────────────────────────────
// Stronger shadow so cards visibly float off the #F4F7F7 background

const CARD = 'bg-white rounded-xl overflow-hidden';
const CARD_STYLE = {
  boxShadow: '0 2px 12px rgba(0,0,0,0.07), 0 0 0 1px rgba(0,0,0,0.04)',
} as const;

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
  shield_score: 82, capital_defended: 18450, this_week: 3, this_month: 2,
  total_alerts: 22, heeded: 15, ignored: 7, heeded_streak: 4, blowups_prevented: 2,
  checkpoint_coverage: { complete: 14, calculating: 2, unavailable: 6 },
  data_points: 22, is_partial: false,
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
      description: 'SL moved 4 times in the current session against price movement',
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

  useEffect(() => {
    if (!localStorage.getItem(AUTH_TOKEN_KEY) && !isGuestMode()) {
      navigate('/welcome', { replace: true });
    }
  }, [navigate]);

  const [positions,     setPositions]     = useState<PositionWithExtras[]>([]);
  const [closedTrades,  setClosedTrades]  = useState<CompletedTrade[]>([]);
  const [shield,        setShield]        = useState<ShieldSummary | null>(null);
  const [posLoading,    setPosLoading]    = useState(false);
  const [tradesLoading, setTradesLoading] = useState(false);
  const [isSyncing,     setIsSyncing]     = useState(false);
  const [initialLoadDone, setInitialLoadDone] = useState(false);
  const [journaledIds,  setJournaledIds]  = useState<Set<string>>(new Set());
  const [selectedAlert, setSelectedAlert] = useState<AlertNotification | null>(null);
  const [journalOpen,   setJournalOpen]   = useState(false);
  const [journalTrade,  setJournalTrade]  = useState<PositionWithExtras | CompletedTrade | null>(null);
  const [journalType,   setJournalType]   = useState<'position' | 'closed'>('closed');
  const journalTradeIdRef = useRef<string | null>(null);
  const accountIdRef = useRef(account?.id);
  accountIdRef.current = account?.id;

  // ── Fetchers ───────────────────────────────────────────────────────────────

  const fetchPositions = useCallback(async () => {
    if (!accountIdRef.current) return;
    try {
      setPosLoading(true);
      const { data } = await api.get('/api/positions/', { params: { broker_account_id: accountIdRef.current } });
      const raw: Position[] = Array.isArray(data) ? data : (data.positions ?? []);
      setPositions(raw.filter(p => p.status === 'open').map(p => ({
        ...p,
        instrument_type: p.instrument_type ?? 'EQ',
        unrealized_pnl: p.unrealized_pnl ?? p.pnl ?? p.m2m ?? 0,
        current_value: p.current_value ?? (p.last_price ?? 0) * Math.abs(p.total_quantity ?? 0),
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
      setClosedTrades(raw.filter(t => { try { return isToday(parseISO(t.exit_time)); } catch { return false; } }));
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
    Promise.all([fetchPositions(), fetchClosedTrades(), fetchShield()]).finally(() => setInitialLoadDone(true));
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

  const isUsingDemo   = positions.length === 0 && closedTrades.length === 0;
  const displayPos    = positions.length    > 0 ? positions    : DEMO_POSITIONS;
  const displayClosed = closedTrades.length > 0 ? closedTrades : DEMO_CLOSED;
  const displayShield = shield ?? DEMO_SHIELD;
  const displayAlerts = liveAlerts.length   > 0 ? liveAlerts   : DEMO_ALERTS;
  const displayUnread = liveAlerts.length   > 0
    ? unacknowledgedCount
    : DEMO_ALERTS.filter(a => !a.acknowledged).length;

  // ── Derived stats ──────────────────────────────────────────────────────────

  const realizedPnl     = displayClosed.reduce((s, t) => s + (t.realized_pnl ?? 0), 0);
  const unrealizedPnl   = displayPos.reduce((s, p) => s + (p.unrealized_pnl ?? 0), 0);
  const sessionPnl      = realizedPnl + unrealizedPnl;
  const winCount        = displayClosed.filter(t => (t.realized_pnl ?? 0) > 0).length;
  const winRate         = displayClosed.length > 0
    ? (winCount / displayClosed.length * 100).toFixed(1)
    : null;
  const pendingJournals = displayClosed.filter(t => !journaledIds.has(t.id)).length;
  const tradeCount      = displayClosed.length + displayPos.length;
  const avgPerDay       = 5;
  const pacePercent     = Math.round((tradeCount / avgPerDay - 1) * 100);

  const recentAlerts = [...displayAlerts]
    .sort((a, b) => (b.pattern.detected_at ?? '').localeCompare(a.pattern.detected_at ?? ''))
    .slice(0, 4);

  const sortedClosed = [...displayClosed].sort((a, b) => {
    const aj = journaledIds.has(a.id) ? 1 : 0;
    const bj = journaledIds.has(b.id) ? 1 : 0;
    return aj !== bj ? aj - bj : (b.exit_time ?? '').localeCompare(a.exit_time ?? '');
  });

  // ── Journal handlers ───────────────────────────────────────────────────────

  function openJournal(trade: PositionWithExtras | CompletedTrade, type: 'position' | 'closed') {
    journalTradeIdRef.current = trade.id;
    setJournalTrade(trade);
    setJournalType(type);
    setJournalOpen(true);
  }

  // TradeJournalSheet saves to API internally; mark journaled optimistically on close
  function handleJournalClose(open: boolean) {
    if (!open && journalTradeIdRef.current) {
      setJournaledIds(prev => new Set(prev).add(journalTradeIdRef.current!));
      journalTradeIdRef.current = null;
    }
    setJournalOpen(open);
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen" style={{ background: '#F4F7F7' }}>
      <TopNavbar
        tradeCount={tradeCount}
        onSync={handleSync}
        isSyncing={isSyncing || syncStatus === 'syncing'}
        activeHref="/dashboard-v2"
      />

      {/* Demo banner */}
      {isUsingDemo && initialLoadDone && (
        <div className="fixed top-[60px] left-0 right-0 z-40 bg-amber-50 border-b border-amber-200 text-center py-1.5">
          <span className="text-xs font-medium" style={{ color: C.amber }}>
            Showing demo data — connect Zerodha to see real data
          </span>
        </div>
      )}

      <div className={cn(
        'max-w-[1200px] mx-auto px-6 pb-10',
        isUsingDemo && initialLoadDone ? 'pt-[88px]' : 'pt-[76px]'
      )}>

        {/* ── Page header ───────────────────────────────────────────────────── */}
        <div className="flex items-center gap-4 mb-6">
          <h1 className="text-[24px] font-bold" style={{ color: C.text }}>Dashboard</h1>
          <div className="flex items-center gap-3 text-sm">
            <span className="text-slate-400">{tradeCount} trades</span>
            <span className="font-mono font-semibold" style={{ color: sessionPnl >= 0 ? C.profit : C.loss }}>
              {sessionPnl >= 0 ? '+' : '–'}₹{Math.abs(sessionPnl).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
            </span>
            {displayUnread > 0 && (
              <span className="font-medium" style={{ color: C.amber }}>⚠ {displayUnread}</span>
            )}
            {pendingJournals > 0 && (
              <span className="flex items-center gap-1 text-slate-400">
                <Pencil className="w-3.5 h-3.5" />{pendingJournals}
              </span>
            )}
          </div>
        </div>

        {/* ── Session Summary ────────────────────────────────────────────────── */}
        <div className={cn(CARD, 'px-6 py-6 mb-5')} style={CARD_STYLE}>
          <div className="grid grid-cols-4 divide-x divide-slate-100 gap-0">

            <div className="pr-8">
              <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-widest mb-2">Session P&L</p>
              <p className="text-[28px] font-black font-mono tabular-nums leading-none"
                style={{ color: sessionPnl > 0 ? C.profit : sessionPnl < 0 ? C.loss : '#94A3B8' }}>
                {sessionPnl >= 0 ? '+' : '–'}₹{Math.abs(sessionPnl).toLocaleString('en-IN', { maximumFractionDigits: 0 })}.00
              </p>
              <p className="text-[12px] text-slate-400 mt-2 font-mono">
                {fmtPnl(realizedPnl)} realized · {fmtPnl(unrealizedPnl)} open
              </p>
            </div>

            <div className="px-8">
              <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-widest mb-2">Win Rate</p>
              {winRate !== null
                ? <p className="text-[28px] font-black font-mono tabular-nums leading-none" style={{ color: C.text }}>{winRate}%</p>
                : <p className="text-[28px] font-black leading-none text-slate-300">—</p>}
              <p className="text-[12px] text-slate-400 mt-2">
                {displayClosed.length > 0
                  ? `${winCount}W · ${displayClosed.length - winCount}L of ${displayClosed.length}`
                  : 'No closed trades'}
              </p>
            </div>

            <div className="px-8">
              <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-widest mb-2">Unread Alerts</p>
              <p className="text-[28px] font-black font-mono tabular-nums leading-none"
                style={{ color: displayUnread > 0 ? C.amber : C.text }}>
                {displayUnread}
              </p>
              <p className="text-[12px] text-slate-400 mt-2">{displayAlerts.length} total observations</p>
            </div>

            <div className="pl-8">
              <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-widest mb-2">Pending Journals</p>
              <p className="text-[28px] font-black font-mono tabular-nums leading-none"
                style={{ color: pendingJournals === 0 ? C.profit : C.text }}>
                {pendingJournals === 0 ? '✓' : pendingJournals}
              </p>
              <p className="text-[12px] text-slate-400 mt-2">
                {pendingJournals === 0 ? 'All trades journaled' : `${pendingJournals} of ${displayClosed.length} need notes`}
              </p>
            </div>
          </div>
        </div>

        {/* ── Behavioral Alerts ─────────────────────────────────────────────── */}
        <div className={cn(CARD, 'mb-5')} style={CARD_STYLE}>
          <div className="flex items-center justify-between px-5 py-3 border-b border-slate-100">
            <div className="flex items-center gap-3">
              <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-widest">
                Behavioral Alerts
              </span>
              {displayUnread > 0 && (
                <span className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: C.amber }}>
                  {displayUnread} unread
                </span>
              )}
            </div>
            {displayAlerts.length > 4 && (
              <Link to="/alerts" className="text-sm font-medium" style={{ color: C.teal }}>
                View all {displayAlerts.length} alerts →
              </Link>
            )}
          </div>

          {displayAlerts.length === 0 ? (
            <p className="text-sm text-slate-400 text-center py-8">No observations today</p>
          ) : (
            <div>
              {recentAlerts.map((alert, i) => {
                const isUnread = !alert.acknowledged;
                return (
                  <button
                    key={alert.id}
                    onClick={() => setSelectedAlert(alert)}
                    className={cn(
                      'w-full flex items-start gap-4 px-5 py-4 text-left hover:bg-slate-50 transition-colors',
                      i < recentAlerts.length - 1 && 'border-b border-slate-100'
                    )}
                  >
                    {/* Severity dot */}
                    <span
                      className="mt-[7px] shrink-0 w-2 h-2 rounded-full"
                      style={{ background: dotColor(alert.pattern.severity) }}
                    />

                    {/* Name + description — two lines */}
                    <div className="flex-1 min-w-0">
                      <p className="text-[15px] font-semibold leading-snug"
                        style={{ color: isUnread ? C.text : '#64748B' }}>
                        {alert.pattern.name}
                      </p>
                      <p className="text-[13px] text-slate-400 mt-0.5 leading-snug">
                        {alert.pattern.description}
                      </p>
                    </div>

                    {/* Time + chevron */}
                    <div className="shrink-0 flex items-center gap-2 pt-0.5">
                      <span className="text-[13px] text-slate-400 font-mono tabular-nums">
                        {fmtTime(alert.pattern.detected_at ?? alert.shown_at)}
                      </span>
                      <ChevronRight className="w-4 h-4 text-slate-300" />
                    </div>
                  </button>
                );
              })}

              {displayAlerts.length > 4 && (
                <div className="border-t border-slate-100 px-5 py-3">
                  <Link to="/alerts" className="text-sm font-medium" style={{ color: C.teal }}>
                    View all {displayAlerts.length} alerts →
                  </Link>
                </div>
              )}
            </div>
          )}
        </div>

        {/* ── Two-column layout ──────────────────────────────────────────────── */}
        <div className="flex gap-5 items-start">

          {/* LEFT — 62% */}
          <div className="flex-[62] min-w-0 space-y-5">

            {/* ── Open Positions ─────────────────────────────────────────────── */}
            <div className={CARD} style={CARD_STYLE}>
              <div className="flex items-center justify-between px-5 py-3 border-b border-slate-100">
                <div className="flex items-center gap-2.5">
                  <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-widest">
                    Open Positions
                  </span>
                  <span className="text-[11px] font-semibold text-slate-400">{displayPos.length}</span>
                </div>
                <span className="flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: C.amber }} />
                  <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wide">Live</span>
                </span>
              </div>

              {posLoading ? (
                <div className="flex justify-center py-10">
                  <Loader2 className="w-5 h-5 text-slate-300 animate-spin" />
                </div>
              ) : (
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-slate-100">
                      {[
                        { label: 'Symbol',  align: 'left',  cls: 'px-5' },
                        { label: 'Side',    align: 'right', cls: 'px-3' },
                        { label: 'Qty',     align: 'right', cls: 'px-3' },
                        { label: 'Avg',     align: 'right', cls: 'px-3' },
                        { label: 'LTP',     align: 'right', cls: 'px-3' },
                        { label: 'P&L',     align: 'right', cls: 'px-3' },
                        { label: 'J',       align: 'left',  cls: 'px-5 w-10' },
                      ].map(h => (
                        <th key={h.label}
                          className={`py-2.5 text-[11px] font-semibold text-slate-400 uppercase tracking-wide text-${h.align} ${h.cls}`}>
                          {h.label}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {displayPos.map((pos, i) => {
                      const pnl = pos.unrealized_pnl ?? 0;
                      const qty = pos.total_quantity ?? 0;
                      const isJournaled = journaledIds.has(pos.id);
                      const { name, tag } = fmtSymbol(pos.tradingsymbol, pos.instrument_type);
                      return (
                        <tr key={pos.id} className={cn(
                          'h-[52px] hover:bg-slate-50/80 transition-colors',
                          i < displayPos.length - 1 && 'border-b border-slate-50'
                        )}>
                          <td className="px-5">
                            <span className="text-sm font-semibold" style={{ color: C.text }}>{name}</span>
                            <span className="text-sm text-slate-400"> · {tag}</span>
                          </td>
                          <td className="px-3 text-right">
                            <span className="text-sm font-semibold"
                              style={{ color: qty > 0 ? C.profit : C.loss }}>
                              {qty > 0 ? 'BUY' : 'SELL'}
                            </span>
                          </td>
                          <td className="px-3 text-right text-sm font-mono tabular-nums" style={{ color: C.text }}>
                            {Math.abs(qty)}
                          </td>
                          <td className="px-3 text-right text-sm font-mono tabular-nums" style={{ color: C.text }}>
                            {fmtPrice(pos.average_entry_price)}
                          </td>
                          <td className="px-3 text-right text-sm font-mono tabular-nums" style={{ color: C.text }}>
                            {fmtPrice(pos.last_price)}
                          </td>
                          <td className="px-3 text-right">
                            <span className="text-sm font-mono tabular-nums font-semibold"
                              style={{ color: pnl > 0 ? C.profit : pnl < 0 ? C.loss : '#94A3B8' }}>
                              {fmtPnl(pnl)}
                            </span>
                          </td>
                          <td className="px-5">
                            <button
                              onClick={() => openJournal(pos, 'position')}
                              className="relative w-7 h-7 flex items-center justify-center rounded hover:bg-slate-100 transition-colors"
                            >
                              {isJournaled
                                ? <CheckCircle2 className="w-[18px] h-[18px]" style={{ color: C.profit }} />
                                : <>
                                    <Pencil className="w-[14px] h-[14px] text-slate-400" />
                                    <span className="absolute top-0.5 right-0.5 w-[5px] h-[5px] rounded-full"
                                      style={{ background: C.amber }} />
                                  </>
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

            {/* ── Closed Today ───────────────────────────────────────────────── */}
            <div className={CARD} style={CARD_STYLE}>
              <div className="flex items-center justify-between px-5 py-3 border-b border-slate-100">
                <div className="flex items-center gap-2.5">
                  <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-widest">
                    Closed Today
                  </span>
                  <span className="text-[11px] font-semibold text-slate-400">{displayClosed.length}</span>
                </div>
                {pendingJournals > 0 && (
                  <span className="text-[11px] font-semibold uppercase tracking-wide"
                    style={{ color: C.amber }}>
                    {pendingJournals} unjournaled
                  </span>
                )}
              </div>

              {tradesLoading ? (
                <div className="flex justify-center py-10">
                  <Loader2 className="w-5 h-5 text-slate-300 animate-spin" />
                </div>
              ) : (
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-slate-100">
                      {[
                        { label: 'Symbol',  align: 'left',  cls: 'px-5' },
                        { label: 'Side',    align: 'right', cls: 'px-3' },
                        { label: 'Qty',     align: 'right', cls: 'px-3' },
                        { label: 'Entry',   align: 'right', cls: 'px-3' },
                        { label: 'Exit',    align: 'right', cls: 'px-3' },
                        { label: 'Net P&L', align: 'right', cls: 'px-3' },
                        { label: 'J',       align: 'left',  cls: 'px-5 w-10' },
                      ].map(h => (
                        <th key={h.label}
                          className={`py-2.5 text-[11px] font-semibold text-slate-400 uppercase tracking-wide text-${h.align} ${h.cls}`}>
                          {h.label}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {sortedClosed.map((trade, i) => {
                      const pnl = trade.realized_pnl ?? 0;
                      const isJournaled = journaledIds.has(trade.id);
                      const { name, tag } = fmtSymbol(trade.tradingsymbol, trade.instrument_type);
                      return (
                        <tr key={trade.id} className={cn(
                          'h-[52px] hover:bg-slate-50/80 transition-colors',
                          i < sortedClosed.length - 1 && 'border-b border-slate-50'
                        )}>
                          <td className="px-5">
                            <span className="text-sm font-semibold" style={{ color: C.text }}>{name}</span>
                            <span className="text-sm text-slate-400"> · {tag}</span>
                          </td>
                          <td className="px-3 text-right">
                            <span className="text-sm font-semibold"
                              style={{ color: trade.direction === 'LONG' ? C.profit : C.loss }}>
                              {trade.direction === 'LONG' ? 'BUY' : 'SELL'}
                            </span>
                          </td>
                          <td className="px-3 text-right text-sm font-mono tabular-nums" style={{ color: C.text }}>
                            {trade.total_quantity}
                          </td>
                          <td className="px-3 text-right text-sm font-mono tabular-nums" style={{ color: C.text }}>
                            {fmtPrice(trade.avg_entry_price)}
                          </td>
                          <td className="px-3 text-right text-sm font-mono tabular-nums" style={{ color: C.text }}>
                            {fmtPrice(trade.avg_exit_price)}
                          </td>
                          <td className="px-3 text-right">
                            <span className="text-sm font-mono tabular-nums font-semibold"
                              style={{ color: pnl > 0 ? C.profit : pnl < 0 ? C.loss : '#94A3B8' }}>
                              {fmtPnl(pnl)}
                            </span>
                          </td>
                          <td className="px-5">
                            <button
                              onClick={() => openJournal(trade, 'closed')}
                              className="relative w-7 h-7 flex items-center justify-center rounded hover:bg-slate-100 transition-colors"
                            >
                              {isJournaled
                                ? <CheckCircle2 className="w-[18px] h-[18px]" style={{ color: C.profit }} />
                                : <>
                                    <Pencil className="w-[14px] h-[14px]" style={{ color: C.amber }} />
                                    <span className="absolute top-0.5 right-0.5 w-[5px] h-[5px] rounded-full"
                                      style={{ background: C.amber }} />
                                  </>
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
          <div className="flex-[38] min-w-0 space-y-4 sticky top-[76px]">

            {/* ── Blowup Shield ──────────────────────────────────────────────── */}
            <div className={cn(CARD, 'p-5')} style={CARD_STYLE}>
              <div className="flex items-center justify-between mb-4">
                <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-widest">
                  Blowup Shield
                </span>
                <Shield className="w-4 h-4" style={{ color: C.teal }} />
              </div>

              <div className="flex items-baseline gap-1.5 mb-1">
                <span className="text-[32px] font-black font-mono leading-none" style={{ color: C.text }}>
                  {displayShield.shield_score}
                </span>
                <span className="text-base text-slate-400 font-mono">/100</span>
              </div>
              <p className="text-[13px] mb-4" style={{ color: C.muted }}>
                {displayShield.this_month} protection{displayShield.this_month !== 1 ? 's' : ''} this month
              </p>

              {/* Heeded ratio bar */}
              <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden mb-4">
                <div
                  className="h-full rounded-full transition-all"
                  style={{
                    background: C.teal,
                    width: `${displayShield.total_alerts > 0
                      ? Math.round(displayShield.heeded / displayShield.total_alerts * 100)
                      : 0}%`,
                  }}
                />
              </div>

              {/* Last event */}
              <div className="flex items-center justify-between rounded-lg px-3 py-2.5 bg-slate-50">
                <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wide">
                  Last · Mar 28
                </span>
                <span className="text-sm font-semibold" style={{ color: C.teal }}>
                  ₹{Math.round(displayShield.capital_defended / Math.max(displayShield.blowups_prevented, 1))
                    .toLocaleString('en-IN')} saved
                </span>
              </div>
            </div>

            {/* ── Session Pace ───────────────────────────────────────────────── */}
            <div className={cn(CARD, 'p-5')} style={CARD_STYLE}>
              <div className="flex items-center justify-between mb-4">
                <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-widest">
                  Session Pace
                </span>
                <Clock className="w-4 h-4 text-slate-400" />
              </div>

              <div className="flex items-baseline gap-2.5 mb-1">
                <span className="text-[32px] font-black font-mono leading-none" style={{ color: C.text }}>
                  {tradeCount}
                </span>
                {pacePercent !== 0 && (
                  <span className="text-sm font-semibold"
                    style={{ color: pacePercent > 0 ? C.amber : C.profit }}>
                    {pacePercent > 0 ? `↑ ${pacePercent}%` : `↓ ${Math.abs(pacePercent)}%`}
                  </span>
                )}
              </div>
              <p className="text-[13px] mb-4" style={{ color: C.muted }}>trades today</p>

              <div className="flex items-center justify-between">
                <span className="text-[13px] text-slate-400">Your average</span>
                <span className="text-[13px] font-semibold" style={{ color: C.text }}>
                  {avgPerDay} per day
                </span>
              </div>
            </div>

            {/* ── AI Coach CTA ───────────────────────────────────────────────── */}
            <Link
              to="/chat"
              className="flex items-center gap-3 rounded-xl bg-white p-4 hover:bg-teal-50/40 transition-colors group"
              style={CARD_STYLE}
            >
              <div className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0"
                style={{ background: '#E8F5F3' }}>
                <BarChart2 className="w-4 h-4" style={{ color: C.teal }} />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold" style={{ color: C.text }}>Ask AI Coach</p>
                <p className="text-[12px] text-slate-400">Analyse today's session with AI</p>
              </div>
              <ChevronRight className="w-4 h-4 text-slate-300 group-hover:text-teal-600 transition-colors" />
            </Link>
          </div>
        </div>
      </div>

      {/* ── Alert Detail Bottom Sheet ─────────────────────────────────────────── */}
      {selectedAlert && (
        <div
          className="fixed inset-0 z-50 bg-black/40 flex items-end justify-center"
          onClick={() => setSelectedAlert(null)}
        >
          <div
            className="bg-white rounded-t-xl shadow-xl w-full max-w-xl pb-8"
            onClick={e => e.stopPropagation()}
          >
            <div className="w-10 h-1 bg-slate-200 rounded-full mx-auto mt-3 mb-5" />
            <div className="px-6">
              <div className="flex items-start gap-3 mb-5">
                <span
                  className="mt-2 shrink-0 w-2 h-2 rounded-full"
                  style={{ background: dotColor(selectedAlert.pattern.severity) }}
                />
                <div>
                  <h3 className="text-[17px] font-bold" style={{ color: C.text }}>
                    {selectedAlert.pattern.name}
                  </h3>
                  <p className="text-sm text-slate-500 mt-1">{selectedAlert.pattern.description}</p>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-4 bg-slate-50 rounded-xl p-4 mb-5">
                <div>
                  <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wide mb-1">Est. cost</p>
                  <p className="text-sm font-mono font-semibold" style={{ color: C.loss }}>
                    {selectedAlert.pattern.estimated_cost > 0
                      ? fmtPnl(-selectedAlert.pattern.estimated_cost)
                      : '—'}
                  </p>
                </div>
                <div>
                  <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wide mb-1">This week</p>
                  <p className="text-sm font-mono font-semibold" style={{ color: C.text }}>
                    {selectedAlert.pattern.frequency_this_week}×
                  </p>
                </div>
                <div>
                  <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wide mb-1">This month</p>
                  <p className="text-sm font-mono font-semibold" style={{ color: C.text }}>
                    {selectedAlert.pattern.frequency_this_month}×
                  </p>
                </div>
              </div>

              <div className="flex gap-3">
                {!selectedAlert.acknowledged && (
                  <button
                    onClick={() => {
                      if (!isUsingDemo) acknowledgeAlert(selectedAlert.id);
                      setSelectedAlert(null);
                    }}
                    className="flex-1 py-2.5 text-sm font-semibold rounded-lg border transition-colors"
                    style={{ color: C.teal, borderColor: C.teal }}
                  >
                    Mark as read
                  </button>
                )}
                <Link
                  to="/chat"
                  onClick={() => setSelectedAlert(null)}
                  className="flex-1 py-2.5 text-sm font-semibold text-white rounded-lg text-center transition-colors"
                  style={{ background: C.teal }}
                >
                  Discuss with Coach
                </Link>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TradeJournalSheet — saves to API internally, marks journaled on close */}
      <TradeJournalSheet
        open={journalOpen}
        onOpenChange={handleJournalClose}
        trade={journalTrade}
        type={journalType}
      />
    </div>
  );
}
