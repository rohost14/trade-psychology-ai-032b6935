import { useEffect, useMemo, useState } from 'react';
import { NotebookPen, ChevronRight, ChevronDown, CheckCircle2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { api } from '@/lib/api';
import { formatPrice, formatCurrencyWithSign } from '@/lib/formatters';
import { parseSymbol } from '@/lib/symbolParser';
import { Skeleton } from '@/components/ui/skeleton';
import type { CompletedTrade } from '@/types/api';

// One consolidated (net) position — the backend aggregates round-trips per instrument+product.
interface ClosedSummaryRow {
  tradingsymbol: string;
  exchange: string;
  instrument_type: string | null;
  product: string | null;
  trades: number;
  net_pnl: number;
  total_qty: number;
  first_entry: string | null;
  last_exit: string | null;
  total_hold_min: number;
  avg_entry_price: number;
  avg_exit_price: number;
}

interface Props {
  /** ISO session-start; only trades closed at/after this are summarised. */
  sinceIso: string;
  /** The session's round-trips (already fetched) — used for the drill-down. */
  roundTrips: CompletedTrade[];
  journaledIds?: Set<string>;
  onTradeClick?: (trade: CompletedTrade) => void;
}

const CAP = 12;
/**
 * Symbol capped, then a flexible spacer, then the numeric columns at fixed
 * widths. Previously the symbol column was 1.5fr, so on a 1240px card it grew
 * to roughly 640px for about 150px of text -- pushing the first number nearly
 * 500px away from the name it belongs to. Slack now collects in the spacer,
 * where there is nothing to read, and the figures stay together as one block.
 */
const COLS = 'grid-cols-[minmax(150px,300px)_1fr_64px_88px_88px_72px_76px_104px_32px]';

function formatDuration(mins: number): string {
  if (mins <= 0) return '—';
  if (mins < 60) return `${mins}m`;
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  if (h < 24) return m > 0 ? `${h}h ${m}m` : `${h}h`;
  const d = Math.floor(h / 24);
  return `${d}d`;
}
function formatTime(s: string | null): string {
  if (!s) return '—';
  return new Date(s).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'Asia/Kolkata' });
}

export default function ClosedPositionsCard({ sinceIso, roundTrips, journaledIds = new Set(), onTradeClick }: Props) {
  const [rows, setRows] = useState<ClosedSummaryRow[] | null>(null);
  const [error, setError] = useState(false);
  const [showAll, setShowAll] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null); // `${symbol}|${product}`

  useEffect(() => {
    let cancelled = false;
    setRows(null); setError(false);
    api.get('/api/trades/closed-summary', { params: { since: sinceIso } })
      .then(res => { if (!cancelled) setRows(res.data.positions ?? []); })
      .catch(() => { if (!cancelled) setError(true); });
    return () => { cancelled = true; };
  }, [sinceIso]);

  const totalPnl = useMemo(() => (rows ?? []).reduce((s, r) => s + r.net_pnl, 0), [rows]);
  const totalTrades = useMemo(() => (rows ?? []).reduce((s, r) => s + r.trades, 0), [rows]);

  // Round-trips for a given consolidated row (drill-down), from the in-memory session set.
  const legsFor = (symbol: string, product: string | null) =>
    roundTrips
      .filter(t => t.tradingsymbol === symbol && (t.product ?? '') === (product ?? ''))
      .sort((a, b) => new Date(b.exit_time).getTime() - new Date(a.exit_time).getTime());

  if (rows === null && !error) {
    return (
      <section className="overflow-hidden">
        <div className="card-head"><div className="h-4 w-40 bg-muted animate-pulse rounded" /></div>
        <div className="p-5 space-y-3">{[1, 2, 3].map(i => <Skeleton key={i} className="h-10 rounded" />)}</div>
      </section>
    );
  }

  if (error) {
    return (
      <section className="overflow-hidden">
        <div className="card-head"><span className="text-[11px] uppercase tracking-[0.12em] font-medium text-muted-foreground">Closed Positions</span></div>
        <div className="px-5 py-8 text-center text-[13px] text-muted-foreground">Couldn't load closed positions.</div>
      </section>
    );
  }

  if (!rows || rows.length === 0) {
    const stats = [
      { stat: '94%', label: 'of traders taking >7 trades/day lose money', source: 'SEBI FY2023' },
      { stat: '73%', label: 'of trades placed within 15 min of a loss also lose', source: 'SEBI data' },
      { stat: '2.7×', label: 'faster: retail closes winners vs holding losers', source: 'SEBI FY2022' },
      { stat: '3 losses', label: 'in a row is when emotional impairment measurably starts', source: 'Behavioral research' },
    ];
    return (
      <section className="overflow-hidden">
        <div className="card-head"><span className="text-[11px] uppercase tracking-[0.12em] font-medium text-muted-foreground">Closed Positions</span></div>
        <div className="px-5 sm:px-6 py-8">
          <p className="text-sm font-medium text-foreground mb-1">Waiting for your first trade</p>
          <p className="text-[13px] text-muted-foreground mb-5">Once you trade, we'll analyze every round — entry to exit — and watch for these patterns in real time.</p>
          <div className="grid grid-cols-2 gap-3">
            {stats.map((it, i) => (
              <div key={i} className="p-3 rounded-lg bg-muted/50 border border-border">
                <p className="text-base font-bold text-primary font-tabular">{it.stat}</p>
                <p className="text-xs text-foreground mt-0.5 leading-snug">{it.label}</p>
                <p className="text-[10px] text-muted-foreground mt-1">{it.source}</p>
              </div>
            ))}
          </div>
        </div>
      </section>
    );
  }

  const visible = showAll ? rows : rows.slice(0, CAP);

  return (
    <section className="overflow-hidden">
      <div className="px-4 sm:px-6 py-4 border-b border-border flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2.5 flex-wrap">
          <span className="text-[11px] uppercase tracking-[0.12em] font-medium text-muted-foreground">Closed Positions</span>
          <span className="text-[11px] text-muted-foreground font-tabular">· {rows.length} instrument{rows.length !== 1 ? 's' : ''} · {totalTrades} trade{totalTrades !== 1 ? 's' : ''}</span>
          <span className="hidden sm:inline text-[10px] text-muted-foreground/70 uppercase tracking-wider">· tap to expand round-trips</span>
        </div>
        <span className="flex items-baseline gap-1.5">
          <span className="text-[10px] uppercase tracking-wider text-muted-foreground">Booked</span>
          <span className={cn('text-sm font-semibold font-tabular', totalPnl >= 0 ? 'text-profit' : 'text-loss')}>{formatCurrencyWithSign(totalPnl)}</span>
        </span>
      </div>

      {/* Column header */}
      <div className={cn('hidden sm:grid gap-3 px-4 sm:px-6 py-3 text-[10px] uppercase tracking-wider font-medium text-muted-foreground border-b border-border', COLS)}>
        <span>Symbol</span>
        <span aria-hidden />
        <span className="text-right">Qty</span>
        <span className="text-right">Avg Entry</span>
        <span className="text-right">Avg Exit</span>
        <span className="text-right">Hold</span>
        <span className="text-right">Chg%</span>
        <span className="text-right">Net P&amp;L</span>
        <span />
      </div>

      <div className="divide-y divide-border">
        {visible.map(r => {
          const key = `${r.tradingsymbol}|${r.product ?? ''}`;
          const isOpen = expanded === key;
          const { name } = parseSymbol(r.tradingsymbol, r.instrument_type ?? undefined);
          const chg = r.avg_entry_price ? ((r.avg_exit_price - r.avg_entry_price) / r.avg_entry_price) * 100 : 0;
          const legs = isOpen ? legsFor(r.tradingsymbol, r.product) : [];
          return (
            <div key={key}>
              <div
                role="button"
                tabIndex={0}
                onClick={() => setExpanded(isOpen ? null : key)}
                onKeyDown={e => (e.key === 'Enter' || e.key === ' ') && setExpanded(isOpen ? null : key)}
                className={cn('group cursor-pointer transition-colors hover:bg-muted/40 focus:outline-none focus:bg-muted/40', isOpen && 'bg-muted/30')}
              >
                {/* Desktop */}
                <div className={cn('hidden sm:grid gap-3 px-4 sm:px-6 py-3.5 items-center', COLS)}>
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="text-sm font-medium text-foreground">{name}</span>
                    {r.product && <span className="text-[10px] font-medium text-muted-foreground uppercase">{r.product}</span>}
                    {r.trades > 1 && <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-muted text-muted-foreground font-tabular">{r.trades}×</span>}
                  </div>
                  <span aria-hidden />
                  <span className="text-right text-sm font-tabular text-muted-foreground">{r.total_qty}</span>
                  <span className="text-right text-sm font-tabular text-muted-foreground">{formatPrice(r.avg_entry_price)}</span>
                  <span className="text-right text-sm font-tabular text-foreground">{formatPrice(r.avg_exit_price)}</span>
                  <span className="text-right text-sm font-tabular text-muted-foreground">{formatDuration(r.total_hold_min)}</span>
                  <span className={cn('text-right text-sm font-tabular font-medium', chg >= 0 ? 'text-profit' : 'text-loss')}>{chg >= 0 ? '+' : ''}{chg.toFixed(2)}%</span>
                  <span className={cn('text-right text-sm font-semibold font-tabular', r.net_pnl > 0 ? 'text-profit' : r.net_pnl < 0 ? 'text-loss' : 'text-muted-foreground')}>{formatCurrencyWithSign(r.net_pnl)}</span>
                  <span className="flex items-center justify-end text-muted-foreground/60 group-hover:text-primary transition-colors">
                    {isOpen ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
                  </span>
                </div>
                {/* Mobile */}
                <div className="sm:hidden px-4 py-4">
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="text-sm font-medium text-foreground truncate">{name}</span>
                      {r.trades > 1 && <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-muted text-muted-foreground shrink-0 font-tabular">{r.trades}×</span>}
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <span className={cn('text-sm font-semibold font-tabular', r.net_pnl >= 0 ? 'text-profit' : 'text-loss')}>{formatCurrencyWithSign(r.net_pnl)}</span>
                      {isOpen ? <ChevronDown className="h-3.5 w-3.5 text-muted-foreground/50" /> : <ChevronRight className="h-3.5 w-3.5 text-muted-foreground/50" />}
                    </div>
                  </div>
                  <div className="mt-2 text-[11px] text-muted-foreground font-tabular">{r.total_qty} qty · {r.product} · {formatDuration(r.total_hold_min)} · {chg >= 0 ? '+' : ''}{chg.toFixed(2)}%</div>
                </div>
              </div>

              {/* Drill-down: individual round-trips */}
              {isOpen && (
                <div className="bg-muted/20 border-t border-border divide-y divide-border/60">
                  {legs.length === 0 ? (
                    <p className="px-6 py-3 text-[12px] text-muted-foreground">Round-trip detail not in this window.</p>
                  ) : legs.map(leg => {
                    const isJournaled = journaledIds.has(leg.id);
                    return (
                      <button
                        key={leg.id}
                        onClick={() => onTradeClick?.(leg)}
                        className="w-full text-left px-6 sm:px-8 py-2.5 flex items-center gap-3 hover:bg-muted/40 transition-colors"
                      >
                        <span className="text-[11px] text-muted-foreground font-tabular w-12 shrink-0">{formatTime(leg.exit_time)}</span>
                        <span className={cn('text-[10px] font-semibold px-1.5 py-0.5 rounded shrink-0', leg.direction === 'LONG' ? 'text-profit bg-profit/10' : 'text-loss bg-loss/10')}>{leg.direction === 'LONG' ? 'BUY' : 'SELL'}</span>
                        <span className="text-[12px] font-tabular text-muted-foreground">{leg.total_quantity} @ {formatPrice(leg.avg_entry_price)} → {formatPrice(leg.avg_exit_price)}</span>
                        <span className={cn('ml-auto text-[12.5px] font-semibold font-tabular', leg.realized_pnl >= 0 ? 'text-profit' : 'text-loss')}>{formatCurrencyWithSign(leg.realized_pnl)}</span>
                        {isJournaled ? <CheckCircle2 className="h-3.5 w-3.5 text-profit shrink-0" /> : <NotebookPen className="h-3.5 w-3.5 text-muted-foreground/60 shrink-0" />}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {rows.length > CAP && (
        <button
          onClick={() => setShowAll(v => !v)}
          className="w-full px-6 py-2.5 border-t border-border text-[11px] font-medium text-primary hover:bg-muted/40 transition-colors uppercase tracking-wider"
        >
          {showAll ? 'Show less' : `View all ${rows.length} instruments`}
        </button>
      )}
    </section>
  );
}

