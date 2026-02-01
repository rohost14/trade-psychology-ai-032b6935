import { ArrowUpRight, ArrowDownRight, History, Clock, ChevronRight, Target } from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatCurrency, formatRelativeTime } from '@/lib/formatters';
import { motion } from 'framer-motion';
import type { Trade } from '@/types/api';

interface ClosedTradesTableProps {
  trades: Trade[];
  isLoading?: boolean;
  onTradeClick?: (trade: Trade) => void;
}

export default function ClosedTradesTable({ trades, isLoading, onTradeClick }: ClosedTradesTableProps) {
  const totalPnl = trades.reduce((sum, t) => sum + t.pnl, 0);
  const winners = trades.filter(t => t.pnl > 0).length;
  const losers = trades.length - winners;
  const winRate = trades.length > 0 ? Math.round((winners / trades.length) * 100) : 0;

  if (isLoading) {
    return (
      <div className="card-premium">
        <div className="px-6 py-5 border-b border-border/40">
          <div className="h-6 w-48 shimmer rounded-lg" />
        </div>
        <div className="p-6 space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-16 shimmer rounded-xl" />
          ))}
        </div>
      </div>
    );
  }

  if (!trades.length) {
    return (
      <div className="card-premium">
        <div className="px-6 py-5 border-b border-border/40">
          <div className="flex items-center gap-4">
            <div className="p-3 rounded-2xl bg-muted/50 border border-border/50">
              <Clock className="h-5 w-5 text-muted-foreground" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-foreground">Today's Trades</h3>
              <p className="text-sm text-muted-foreground">Completed trades</p>
            </div>
          </div>
        </div>
        <div className="py-16 text-center">
          <motion.div 
            className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-muted/50 mb-4 border border-border/50"
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ type: 'spring', stiffness: 200 }}
          >
            <History className="h-8 w-8 text-muted-foreground" />
          </motion.div>
          <motion.p 
            className="text-base font-semibold text-foreground"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
          >
            No closed trades today
          </motion.p>
          <motion.p 
            className="text-sm text-muted-foreground mt-1"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.3 }}
          >
            Completed trades will appear here
          </motion.p>
        </div>
      </div>
    );
  }

  return (
    <div className="card-premium">
      {/* Header */}
      <div className="px-6 py-5 border-b border-border/40 bg-gradient-to-r from-muted/40 to-transparent relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-mesh opacity-20 pointer-events-none" />
        
        <div className="relative flex items-center justify-between">
          <div className="flex items-center gap-4">
            <motion.div 
              className="p-3 rounded-2xl bg-gradient-to-br from-muted to-muted/50 border border-border/50 shadow-lg"
              whileHover={{ scale: 1.08, rotate: 5 }}
              transition={{ type: 'spring', stiffness: 300 }}
            >
              <Clock className="h-5 w-5 text-muted-foreground" />
            </motion.div>
            <div>
              <h3 className="text-lg font-semibold text-foreground">Today's Trades</h3>
              <div className="flex items-center gap-3 mt-1">
                <span className="text-sm text-muted-foreground font-medium">{trades.length} trade{trades.length !== 1 ? 's' : ''}</span>
                <span className="text-xs text-muted-foreground/40">•</span>
                <div className="flex items-center gap-2">
                  <span className="text-sm text-success font-semibold">{winners}W</span>
                  <span className="text-sm text-destructive font-semibold">{losers}L</span>
                </div>
                <span className="text-xs text-muted-foreground/40">•</span>
                <motion.span 
                  className={cn(
                    'badge-premium',
                    winRate >= 50 ? 'bg-success/15 text-success border-success/25' : 'bg-destructive/15 text-destructive border-destructive/25'
                  )}
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ delay: 0.2, type: 'spring' }}
                >
                  <Target className="h-3 w-3" />
                  {winRate}%
                </motion.span>
              </div>
            </div>
          </div>
          <div className="text-right">
            <p className="text-xs text-muted-foreground font-medium mb-1">Total P&L</p>
            <motion.p 
              className={cn(
                'text-xl font-mono font-medium tracking-tight',
                totalPnl >= 0 ? 'text-success' : 'text-destructive'
              )}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
            >
              {totalPnl >= 0 ? '+' : ''}{formatCurrency(totalPnl)}
            </motion.p>
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="hidden md:block overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border/40 bg-muted/30">
              <th className="px-6 py-4 text-left table-header">Symbol</th>
              <th className="px-6 py-4 text-center table-header">Side</th>
              <th className="px-6 py-4 text-right table-header">Qty</th>
              <th className="px-6 py-4 text-right table-header">Price</th>
              <th className="px-6 py-4 text-right table-header">P&L</th>
              <th className="px-6 py-4 text-right table-header">Time</th>
              <th className="px-6 py-4 w-10"></th>
            </tr>
          </thead>
          <tbody>
            {trades.slice(0, 8).map((trade, idx) => {
              const isProfit = trade.pnl >= 0;
              return (
                <motion.tr
                  key={trade.id}
                  onClick={() => onTradeClick?.(trade)}
                  className={cn(
                    'border-b border-border/30 last:border-0',
                    'hover:bg-muted/50 transition-all duration-300 cursor-pointer group',
                    idx % 2 === 0 ? 'bg-card' : 'bg-muted/10'
                  )}
                  initial={{ opacity: 0, x: -15 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: idx * 0.04, type: 'spring', stiffness: 120 }}
                  whileHover={{ x: 3 }}
                >
                  <td className="px-6 py-5">
                    <span className="table-cell-mono font-semibold">{trade.tradingsymbol}</span>
                  </td>
                  <td className="px-6 py-5 text-center">
                    <span className={cn(
                      'badge-premium',
                      trade.trade_type === 'BUY' 
                        ? 'bg-success/15 text-success border-success/25' 
                        : 'bg-destructive/15 text-destructive border-destructive/25'
                    )}>
                      {trade.trade_type}
                    </span>
                  </td>
                  <td className="px-6 py-5 text-right table-cell-mono font-medium">{trade.quantity}</td>
                  <td className="px-6 py-5 text-right table-cell-mono text-muted-foreground">{formatCurrency(trade.price)}</td>
                  <td className="px-6 py-5 text-right">
                    <div className="flex items-center justify-end gap-2.5">
                      <motion.div
                        initial={{ scale: 0 }}
                        animate={{ scale: 1 }}
                        transition={{ delay: 0.2 + idx * 0.03, type: 'spring' }}
                      >
                        {isProfit ? (
                          <ArrowUpRight className="h-4 w-4 text-success" />
                        ) : (
                          <ArrowDownRight className="h-4 w-4 text-destructive" />
                        )}
                      </motion.div>
                      <span className={cn(
                        'table-cell-mono font-semibold',
                        isProfit ? 'text-success' : 'text-destructive'
                      )}>
                        {isProfit ? '+' : ''}{formatCurrency(trade.pnl)}
                      </span>
                    </div>
                  </td>
                  <td className="px-6 py-5 text-right text-sm text-muted-foreground font-medium">
                    {formatRelativeTime(trade.traded_at)}
                  </td>
                  <td className="px-4 py-5">
                    <ChevronRight className="h-4 w-4 text-muted-foreground/50 group-hover:text-primary group-hover:translate-x-0.5 transition-all" />
                  </td>
                </motion.tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Mobile Cards */}
      <div className="md:hidden divide-y divide-border/40">
        {trades.slice(0, 8).map((trade, index) => {
          const isProfit = trade.pnl >= 0;
          return (
            <motion.div 
              key={trade.id} 
              onClick={() => onTradeClick?.(trade)} 
              className="p-5 hover:bg-muted/40 transition-all duration-300 cursor-pointer active:scale-[0.99] group"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.04, type: 'spring' }}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="font-mono text-[15px] font-semibold text-foreground">{trade.tradingsymbol}</span>
                  <span className={cn(
                    'px-2.5 py-1 rounded-lg text-xs font-semibold border',
                    trade.trade_type === 'BUY' 
                      ? 'bg-success/15 text-success border-success/25' 
                      : 'bg-destructive/15 text-destructive border-destructive/25'
                  )}>
                    {trade.trade_type}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  {isProfit ? (
                    <ArrowUpRight className="h-4 w-4 text-success" />
                  ) : (
                    <ArrowDownRight className="h-4 w-4 text-destructive" />
                  )}
                  <span className={cn(
                    'font-mono text-[15px] font-semibold',
                    isProfit ? 'text-success' : 'text-destructive'
                  )}>
                    {isProfit ? '+' : ''}{formatCurrency(trade.pnl)}
                  </span>
                  <ChevronRight className="h-4 w-4 text-muted-foreground/50 group-hover:text-primary transition-colors" />
                </div>
              </div>
              <div className="flex items-center justify-between mt-2 text-sm text-muted-foreground">
                <span className="font-medium">{trade.quantity} × {formatCurrency(trade.price)}</span>
                <span>{formatRelativeTime(trade.traded_at)}</span>
              </div>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
