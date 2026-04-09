import React, { useState } from 'react';
import { Search, X, Pencil, CheckCircle2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatPrice, formatCurrencyWithSign } from '@/lib/formatters';
import type { CompletedTrade } from '@/types/api';

interface ClosedTradesTableProps {
  trades: CompletedTrade[];
  isLoading?: boolean;
  journaledIds?: Set<string>;
  onTradeClick?: (trade: CompletedTrade) => void;
}

// ── Symbol parser ─────────────────────────────────────────────────────────────
// Handles: weekly options, monthly options, futures, equity
function parseSymbol(sym: string): { name: string; chip: string; strike: string } {
  // Weekly options: NAME + 5-digit expiry + 5-digit strike + CE/PE  e.g. NIFTY2541524600CE
  const mw5 = sym.match(/^([A-Z]+)\d{5}(\d{5})(CE|PE)$/);
  if (mw5) return { name: mw5[1], chip: mw5[3], strike: parseInt(mw5[2], 10).toLocaleString('en-IN') };
  // Weekly options: 6-digit strike  e.g. NIFTY25415100000CE
  const mw6 = sym.match(/^([A-Z]+)\d{5}(\d{6})(CE|PE)$/);
  if (mw6) return { name: mw6[1], chip: mw6[3], strike: parseInt(mw6[2], 10).toLocaleString('en-IN') };
  // Monthly options: NAME + 2YY + 3MON + strike + CE/PE  e.g. NIFTY25MAR23000CE
  const mm = sym.match(/^([A-Z]+)\d{2}[A-Z]{3}(\d{4,6})(CE|PE)$/);
  if (mm) return { name: mm[1], chip: mm[3], strike: parseInt(mm[2], 10).toLocaleString('en-IN') };
  // Futures  e.g. NIFTY25MARFUT, BANKNIFTY25APR25FUT
  const mf = sym.match(/^([A-Z]+)(?:\d{5}|\d{2}[A-Z]{3})FUT$/);
  if (mf) return { name: mf[1], chip: 'FUT', strike: '' };
  // Equity fallback
  return { name: sym, chip: 'EQ', strike: '' };
}

function chipClass(chip: string) {
  if (chip === 'CE') return 'tm-chip tm-chip-ce';
  if (chip === 'PE') return 'tm-chip tm-chip-pe';
  if (chip === 'FUT') return 'tm-chip bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300';
  return 'tm-chip tm-chip-eq';
}

function formatDuration(minutes: number): string {
  if (minutes < 60) return `${minutes}m`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (h < 24) return m > 0 ? `${h}h ${m}m` : `${h}h`;
  const d = Math.floor(h / 24);
  const rh = h % 24;
  return rh > 0 ? `${d}d ${rh}h` : `${d}d`;
}

function formatTime(dateStr: string): string {
  if (!dateStr) return '—';
  return new Date(dateStr).toLocaleTimeString('en-IN', {
    hour: '2-digit', minute: '2-digit', hour12: false,
    timeZone: 'Asia/Kolkata',
  });
}

// ── Component ─────────────────────────────────────────────────────────────────
export default function ClosedTradesTable({
  trades, isLoading, journaledIds = new Set(), onTradeClick,
}: ClosedTradesTableProps) {
  const [showAll, setShowAll] = useState(false);
  const [filter, setFilter] = useState('');

  // Sort unjournaled today-trades first, then by exit time descending
  const sorted = [...trades].sort((a, b) => {
    const aUnj = !journaledIds.has(a.id) ? 0 : 1;
    const bUnj = !journaledIds.has(b.id) ? 0 : 1;
    if (aUnj !== bUnj) return aUnj - bUnj;
    return new Date(b.exit_time).getTime() - new Date(a.exit_time).getTime();
  });

  const totalPnl = trades.reduce((sum, t) => sum + t.realized_pnl, 0);
  const winners  = trades.filter(t => t.realized_pnl > 0).length;
  const losers   = trades.filter(t => t.realized_pnl < 0).length;
  const winRate  = trades.length > 0 ? Math.round((winners / trades.length) * 100) : 0;

  if (isLoading) {
    return (
      <div className="tm-card">
        <div className="px-5 py-3 border-b border-slate-100 dark:border-neutral-700/60">
          <div className="h-4 w-32 bg-muted animate-pulse rounded" />
        </div>
        <div className="p-5 space-y-3">
          {[1, 2, 3].map(i => <div key={i} className="h-10 bg-muted animate-pulse rounded" />)}
        </div>
      </div>
    );
  }

  if (!trades.length) {
    const stats = [
      { stat: '94%',    label: 'of traders taking >7 trades/day lose money',          source: 'SEBI FY2023' },
      { stat: '73%',    label: 'of trades placed within 15 min of a loss also lose',  source: 'SEBI data' },
      { stat: '2.7×',   label: 'faster: retail closes winners vs holding losers',      source: 'SEBI FY2022' },
      { stat: '3 losses', label: 'in a row is when emotional impairment measurably starts', source: 'Behavioral research' },
    ];
    return (
      <div className="tm-card">
        <div className="px-5 py-3 border-b border-slate-100 dark:border-neutral-700/60">
          <span className="tm-label">Closed Trades</span>
        </div>
        <div className="px-5 py-8">
          <p className="text-sm font-medium text-foreground mb-1">Waiting for your first trade</p>
          <p className="text-[13px] text-muted-foreground mb-5">
            Once you trade, we'll analyze every round — entry to exit — and watch for these patterns in real time.
          </p>
          <div className="grid grid-cols-2 gap-3">
            {stats.map((item, i) => (
              <div key={i} className="p-3 rounded-lg bg-slate-50 dark:bg-neutral-700/30 border border-slate-100 dark:border-neutral-700/60">
                <p className="text-base font-bold text-tm-brand">{item.stat}</p>
                <p className="text-xs text-foreground mt-0.5 leading-snug">{item.label}</p>
                <p className="text-[10px] text-muted-foreground mt-1">{item.source}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  const filtered     = filter.trim()
    ? sorted.filter(t => t.tradingsymbol.toLowerCase().includes(filter.toLowerCase()))
    : sorted;
  const displayLimit = showAll ? filtered.length : 6;
  const visible      = filtered.slice(0, displayLimit);

  return (
    <div className="tm-card">
      {/* ── Header ── */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-slate-100 dark:border-neutral-700/60">
        <div className="flex items-center gap-2 min-w-0">
          <span className="tm-label">Closed Trades</span>
          <span className="text-[11px] text-muted-foreground font-mono tabular-nums">{trades.length}</span>
          <span className="text-[11px] text-muted-foreground/40">·</span>
          <span className="text-[11px] font-mono tabular-nums text-tm-profit">{winners}W</span>
          <span className="text-[11px] font-mono tabular-nums text-tm-loss ml-0.5">{losers}L</span>
          <span className="text-[11px] text-muted-foreground/40">·</span>
          <span className={cn('text-[11px] font-mono tabular-nums', winRate >= 50 ? 'text-tm-profit' : 'text-tm-loss')}>
            {winRate}%
          </span>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          {/* Filter */}
          <div className="relative flex items-center">
            <Search className="absolute left-2 w-3 h-3 text-muted-foreground/50 pointer-events-none" />
            <input
              value={filter}
              onChange={e => setFilter(e.target.value)}
              placeholder="Filter"
              className="h-6 pl-6 pr-5 text-[12px] bg-slate-50 dark:bg-neutral-700/40 border border-slate-200 dark:border-neutral-600/50 rounded text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:ring-1 focus:ring-tm-brand/40 w-[80px]"
            />
            {filter && (
              <button onClick={() => setFilter('')} className="absolute right-1.5 text-muted-foreground/50 hover:text-muted-foreground">
                <X className="w-3 h-3" />
              </button>
            )}
          </div>
          {/* Session P&L */}
          <span className={cn('text-sm font-semibold font-mono tabular-nums', totalPnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
            {formatCurrencyWithSign(totalPnl)}
          </span>
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="py-8 text-center">
          <p className="text-sm text-muted-foreground">No trades matching "{filter}"</p>
        </div>
      ) : (
        <table className="w-full">
          <thead>
            <tr className="border-b-2 border-b-slate-200 dark:border-b-neutral-700/80">
              <th className="px-5 py-3 text-left table-header">Symbol</th>
              <th className="px-3 py-3 text-right table-header">Qty</th>
              <th className="px-3 py-3 text-right table-header">Entry</th>
              <th className="px-3 py-3 text-right table-header">Exit</th>
              <th className="px-3 py-3 text-right table-header">P&L</th>
              <th className="px-5 py-3 w-8 text-center table-header">
                <Pencil className="w-3 h-3 text-muted-foreground/50 mx-auto" />
              </th>
            </tr>
          </thead>
          <tbody>
            {visible.map((trade, i) => {
              const isProfit   = trade.realized_pnl > 0;
              const isJournaled = journaledIds.has(trade.id);
              const { name, chip, strike } = parseSymbol(trade.tradingsymbol);
              const isLast     = i === visible.length - 1;

              return (
                <tr
                  key={trade.id}
                  onClick={() => onTradeClick?.(trade)}
                  className={cn(
                    'transition-colors hover:bg-slate-50 dark:hover:bg-slate-700/30 cursor-pointer',
                    !isLast && 'border-b border-slate-50 dark:border-neutral-700/30',
                  )}
                >
                  {/* Symbol — always two lines for consistent row height */}
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-1.5">
                      <span className="text-sm font-semibold text-foreground leading-none">{name}</span>
                      <span className={chipClass(chip)}>{chip}</span>
                    </div>
                    {/* Sub line: strike (if options) + exit time */}
                    <span className="text-[12px] text-muted-foreground font-mono tabular-nums mt-1 block">
                      {strike ? `${strike} · ` : ''}{formatTime(trade.exit_time)}
                    </span>
                  </td>

                  {/* Qty — direction color, quantity value */}
                  <td className="px-3 py-3 text-right">
                    <span className={cn(
                      'text-[12px] font-semibold uppercase',
                      trade.direction === 'LONG' ? 'text-tm-profit' : 'text-tm-loss',
                    )}>
                      {trade.direction === 'LONG' ? 'B' : 'S'}
                    </span>
                    <span className="ml-1 text-sm font-mono tabular-nums text-foreground">
                      {trade.total_quantity}
                    </span>
                  </td>

                  {/* Entry */}
                  <td className="px-3 py-3 text-right text-sm font-mono tabular-nums font-medium text-muted-foreground">
                    {formatPrice(trade.avg_entry_price)}
                  </td>

                  {/* Exit */}
                  <td className="px-3 py-3 text-right text-sm font-mono tabular-nums font-medium text-muted-foreground">
                    {formatPrice(trade.avg_exit_price)}
                  </td>

                  {/* P&L */}
                  <td className="px-3 py-3 text-right">
                    <span className={cn(
                      'text-sm font-mono tabular-nums font-semibold',
                      isProfit ? 'text-tm-profit' : trade.realized_pnl < 0 ? 'text-tm-loss' : 'text-muted-foreground',
                    )}>
                      {formatCurrencyWithSign(trade.realized_pnl)}
                    </span>
                  </td>

                  {/* Journal icon */}
                  <td className="px-5 py-3 text-center">
                    <button
                      onClick={e => { e.stopPropagation(); onTradeClick?.(trade); }}
                      className="w-7 h-7 inline-flex items-center justify-center rounded hover:bg-muted/60 transition-colors relative"
                    >
                      {isJournaled
                        ? <CheckCircle2 className="w-[16px] h-[16px] text-tm-profit" />
                        : <>
                            <Pencil className="w-[13px] h-[13px] text-muted-foreground" />
                            <span className="absolute top-0.5 right-0.5 w-[5px] h-[5px] rounded-full bg-tm-obs" />
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

      {/* Show more / less */}
      {!filter && filtered.length > displayLimit && (
        <div className="px-5 py-2.5 border-t border-slate-100 dark:border-neutral-700/60 text-center">
          <button
            onClick={() => setShowAll(true)}
            className="text-[13px] font-medium text-tm-brand hover:underline"
          >
            View all {filtered.length} trades
          </button>
        </div>
      )}
      {!filter && showAll && filtered.length > 6 && (
        <div className="px-5 py-2.5 border-t border-slate-100 dark:border-neutral-700/60 text-center">
          <button
            onClick={() => setShowAll(false)}
            className="text-[13px] font-medium text-tm-brand hover:underline"
          >
            Show less
          </button>
        </div>
      )}
    </div>
  );
}
