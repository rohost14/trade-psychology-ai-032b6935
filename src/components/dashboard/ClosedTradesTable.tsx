import React, { useState } from 'react';
import { ArrowUpRight, ArrowDownRight, Clock } from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatCurrency, formatPrice } from '@/lib/formatters';
import { formatSymbol } from '@/lib/exchangeConstants';
import type { CompletedTrade } from '@/types/api';

interface ClosedTradesTableProps {
  trades: CompletedTrade[];
  isLoading?: boolean;
  onTradeClick?: (trade: CompletedTrade) => void;
}

function formatDuration(minutes: number): string {
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  if (hours < 24) return mins > 0 ? `${hours}h ${mins}m` : `${hours}h`;
  const days = Math.floor(hours / 24);
  const remainHours = hours % 24;
  return remainHours > 0 ? `${days}d ${remainHours}h` : `${days}d`;
}

function formatTime(dateStr: string): string {
  if (!dateStr) return '—';
  return new Date(dateStr).toLocaleTimeString('en-IN', {
    hour: '2-digit', minute: '2-digit', hour12: false,
  });
}

function getDayLabel(dateStr: string): string {
  if (!dateStr) return 'Unknown';
  const d = new Date(dateStr);
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  if (d.toDateString() === today.toDateString()) return 'Today';
  if (d.toDateString() === yesterday.toDateString()) return 'Yesterday';
  return d.toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short' });
}

function getDayKey(dateStr: string): string {
  if (!dateStr) return 'unknown';
  const d = new Date(dateStr);
  return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
}

interface DayGroup {
  label: string;
  trades: CompletedTrade[];
  dayPnl: number;
}

function groupByDay(trades: CompletedTrade[]): DayGroup[] {
  const map = new Map<string, DayGroup>();
  for (const t of trades) {
    const key = getDayKey(t.exit_time);
    if (!map.has(key)) {
      map.set(key, { label: getDayLabel(t.exit_time), trades: [], dayPnl: 0 });
    }
    const group = map.get(key)!;
    group.trades.push(t);
    group.dayPnl += t.realized_pnl;
  }
  return Array.from(map.values());
}

export default function ClosedTradesTable({ trades, isLoading, onTradeClick }: ClosedTradesTableProps) {
  const [showAll, setShowAll] = useState(false);

  const totalPnl = trades.reduce((sum, t) => sum + t.realized_pnl, 0);
  const winners = trades.filter(t => t.realized_pnl > 0).length;
  const losers = trades.filter(t => t.realized_pnl < 0).length;
  const winRate = trades.length > 0 ? Math.round((winners / trades.length) * 100) : 0;

  if (isLoading) {
    return (
      <div className="bg-card rounded-lg border border-border">
        <div className="px-6 py-5 border-b border-border">
          <div className="h-6 w-48 bg-muted animate-pulse rounded" />
        </div>
        <div className="p-6 space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-14 bg-muted animate-pulse rounded" />
          ))}
        </div>
      </div>
    );
  }

  if (!trades.length) {
    const watchList = [
      { stat: '94%', label: 'of traders who take >7 trades/day lose money', source: 'SEBI FY2023' },
      { stat: '73%', label: 'of trades placed within 15 min of a loss are also losing trades', source: 'SEBI data' },
      { stat: '2.7×', label: 'faster: retail closes winners vs holding losers (disposition effect)', source: 'SEBI FY2022' },
      { stat: '3 losses', label: 'in a row is when emotional impairment measurably starts', source: 'Behavioral research' },
    ];

    return (
      <div className="bg-card rounded-lg border border-border">
        <div className="px-6 py-5 border-b border-border">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-lg bg-muted">
              <Clock className="h-5 w-5 text-muted-foreground" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-foreground">Completed Trades</h3>
              <p className="text-sm text-muted-foreground">Flat-to-flat trade rounds</p>
            </div>
          </div>
        </div>
        <div className="px-6 py-8">
          <p className="text-sm font-medium text-foreground mb-1">Waiting for your first trade</p>
          <p className="text-sm text-muted-foreground mb-6">
            Once you trade, we'll analyze every round — entry to exit — and watch for these patterns in real time.
          </p>
          <div className="grid grid-cols-2 gap-3">
            {watchList.map((item, i) => (
              <div key={i} className="p-3 rounded-lg bg-muted/50 border border-border/60">
                <p className="text-lg font-bold text-primary">{item.stat}</p>
                <p className="text-xs text-foreground mt-0.5 leading-snug">{item.label}</p>
                <p className="text-[10px] text-muted-foreground mt-1">{item.source}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  const pnlColor = totalPnl >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400';
  const winRateColor = winRate >= 50 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400';

  const displayTrades = showAll ? trades : trades.slice(0, 10);
  const groups = groupByDay(displayTrades);

  return (
    <div className="bg-card rounded-lg border border-border">
      {/* Header */}
      <div className="px-4 py-3 border-b border-border">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Clock className="h-4 w-4 text-muted-foreground" />
            <h3 className="text-sm font-semibold text-foreground">Completed Trades</h3>
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <span>{trades.length}</span>
              <span className="text-muted-foreground/40">&bull;</span>
              <span className="text-green-600 font-medium">{winners}W</span>
              <span className="text-red-600 font-medium">{losers}L</span>
              <span className="text-muted-foreground/40">&bull;</span>
              <span className={cn('font-medium', winRateColor)}>{winRate}%</span>
            </div>
          </div>
          <div className={cn('text-sm font-semibold tabular-nums', pnlColor)}>
            {totalPnl >= 0 ? '+' : ''}{formatCurrency(totalPnl)}
          </div>
        </div>
      </div>

      {/* Desktop Table */}
      <div className="hidden md:block overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border bg-muted/30">
              <th className="px-4 py-2 text-left text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Symbol</th>
              <th className="px-3 py-2 text-right text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Qty</th>
              <th className="px-3 py-2 text-right text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Entry</th>
              <th className="px-3 py-2 text-right text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Exit</th>
              <th className="px-3 py-2 text-right text-[11px] font-medium uppercase tracking-wide text-muted-foreground">P&L</th>
              <th className="px-3 py-2 text-right text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Dur</th>
            </tr>
          </thead>
          <tbody>
            {groups.map((group) => (
              <React.Fragment key={group.label}>
                {/* Date separator row */}
                <tr className="bg-muted/20">
                  <td colSpan={4} className="px-4 py-1.5">
                    <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">
                      {group.label}
                    </span>
                    <span className="text-[11px] text-muted-foreground ml-2">
                      {group.trades.length} trade{group.trades.length !== 1 ? 's' : ''}
                    </span>
                  </td>
                  <td className="px-3 py-1.5 text-right" colSpan={2}>
                    <span className={cn(
                      'text-[11px] font-semibold tabular-nums',
                      group.dayPnl >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
                    )}>
                      {group.dayPnl >= 0 ? '+' : ''}{formatCurrency(group.dayPnl)}
                    </span>
                  </td>
                </tr>
                {/* Trade rows for this day */}
                {group.trades.map((trade) => {
                  const isProfit = trade.realized_pnl > 0;
                  const rowPnlColor = isProfit
                    ? 'text-green-600 dark:text-green-400'
                    : 'text-red-600 dark:text-red-400';
                  return (
                    <tr
                      key={trade.id}
                      onClick={() => onTradeClick?.(trade)}
                      className="border-t border-border/50 hover:bg-muted/50 transition-colors cursor-pointer"
                    >
                      <td className="px-4 py-2.5">
                        {(() => {
                          const { primary, secondary } = formatSymbol(trade.tradingsymbol);
                          return (
                            <>
                              <div className="text-sm font-medium text-foreground">{primary}</div>
                              <div className="text-[10px] text-muted-foreground tabular-nums">
                                {secondary ? <span className="mr-1.5">{secondary}</span> : null}
                                {formatTime(trade.exit_time)}
                              </div>
                            </>
                          );
                        })()}
                      </td>
                      <td className="px-3 py-2.5 text-right text-sm tabular-nums text-foreground">{trade.total_quantity}</td>
                      <td className="px-3 py-2.5 text-right text-sm tabular-nums text-muted-foreground">{formatPrice(trade.avg_entry_price)}</td>
                      <td className="px-3 py-2.5 text-right text-sm tabular-nums text-muted-foreground">{formatPrice(trade.avg_exit_price)}</td>
                      <td className="px-3 py-2.5 text-right">
                        <span className={cn('text-sm tabular-nums font-medium', rowPnlColor)}>
                          {isProfit ? '+' : ''}{formatCurrency(trade.realized_pnl)}
                        </span>
                      </td>
                      <td className="px-3 py-2.5 text-right text-xs text-muted-foreground tabular-nums">
                        {formatDuration(trade.duration_minutes)}
                      </td>
                    </tr>
                  );
                })}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>

      {/* Mobile Cards */}
      <div className="md:hidden">
        {groups.map((group) => (
          <div key={`mob-${group.label}`}>
            {/* Date separator */}
            <div className="px-4 py-1.5 bg-muted/20 flex items-center justify-between">
              <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">
                {group.label} · {group.trades.length} trade{group.trades.length !== 1 ? 's' : ''}
              </span>
              <span className={cn(
                'text-[11px] font-semibold tabular-nums',
                group.dayPnl >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
              )}>
                {group.dayPnl >= 0 ? '+' : ''}{formatCurrency(group.dayPnl)}
              </span>
            </div>
            {/* Trade cards */}
            <div className="divide-y divide-border">
              {group.trades.map((trade) => {
                const isProfit = trade.realized_pnl > 0;
                const cardPnlColor = isProfit
                  ? 'text-green-600 dark:text-green-400'
                  : 'text-red-600 dark:text-red-400';
                return (
                  <div
                    key={trade.id}
                    onClick={() => onTradeClick?.(trade)}
                    className="px-4 py-3 hover:bg-muted/50 transition-colors cursor-pointer"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div>
                          <span className="font-medium text-foreground text-sm">
                            {formatSymbol(trade.tradingsymbol).primary}
                          </span>
                          {formatSymbol(trade.tradingsymbol).secondary && (
                            <span className="ml-1 text-[10px] text-muted-foreground">
                              {formatSymbol(trade.tradingsymbol).secondary}
                            </span>
                          )}
                        </div>
                        <span className={cn(
                          'px-1.5 py-0.5 rounded text-[10px] font-medium',
                          trade.direction === 'LONG'
                            ? 'bg-green-50 text-green-700 dark:bg-green-900/20 dark:text-green-400'
                            : 'bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-400'
                        )}>
                          {trade.direction}
                        </span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        {isProfit ? (
                          <ArrowUpRight className="h-4 w-4 text-green-600" />
                        ) : (
                          <ArrowDownRight className="h-4 w-4 text-red-600" />
                        )}
                        <span className={cn('tabular-nums font-medium', cardPnlColor)}>
                          {isProfit ? '+' : ''}{formatCurrency(trade.realized_pnl)}
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center justify-between mt-1.5 text-xs text-muted-foreground">
                      <span>{trade.total_quantity} qty · {formatPrice(trade.avg_entry_price)} → {formatPrice(trade.avg_exit_price)}</span>
                      <span className="tabular-nums">{formatTime(trade.exit_time)} · {formatDuration(trade.duration_minutes)}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      {/* View all toggle */}
      {trades.length > 10 && (
        <div className="px-6 py-3 border-t border-border text-center">
          <button
            className="text-sm text-primary hover:underline"
            onClick={() => setShowAll(!showAll)}
          >
            {showAll ? 'Show less' : `View all ${trades.length} trades`}
          </button>
        </div>
      )}
    </div>
  );
}
