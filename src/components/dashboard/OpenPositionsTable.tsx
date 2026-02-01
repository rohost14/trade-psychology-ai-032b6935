import { TrendingUp, TrendingDown, Activity, Briefcase, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatCurrency, formatPrice, formatNumber, formatCurrencyWithSign } from '@/lib/formatters';
import { motion } from 'framer-motion';
import type { Position } from '@/types/api';

interface OpenPositionsTableProps {
  positions: (Position & { instrument_type: string; unrealized_pnl: number; current_value: number })[];
  isLoading?: boolean;
  onPositionClick?: (position: Position & { instrument_type: string; unrealized_pnl: number; current_value: number }) => void;
}

export default function OpenPositionsTable({ positions, isLoading, onPositionClick }: OpenPositionsTableProps) {
  const openPositions = positions.filter((p) => p.status === 'open');
  const totalPnl = openPositions.reduce((sum, p) => sum + p.unrealized_pnl, 0);

  if (isLoading) {
    return (
      <div className="card-premium">
        <div className="px-6 py-5 border-b border-border/40">
          <div className="h-6 w-48 shimmer rounded-lg" />
        </div>
        <div className="p-6 space-y-4">
          {[1, 2].map((i) => (
            <div key={i} className="h-16 shimmer rounded-xl" />
          ))}
        </div>
      </div>
    );
  }
  
  return (
    <div className="card-premium hover-glow-success">
      {/* Header */}
      <div className="px-6 py-5 border-b border-border/40 bg-gradient-to-r from-primary/6 to-transparent relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-mesh opacity-30 pointer-events-none" />
        
        <div className="relative flex items-center justify-between">
          <div className="flex items-center gap-4">
            <motion.div 
              className="p-3 rounded-2xl bg-gradient-to-br from-primary/25 to-primary/10 border border-primary/20 shadow-lg"
              whileHover={{ scale: 1.08, rotate: 5 }}
              transition={{ type: 'spring', stiffness: 300 }}
            >
              <Briefcase className="h-5 w-5 text-primary" />
            </motion.div>
            <div>
              <h3 className="text-lg font-semibold text-foreground">Open Positions</h3>
              <p className="text-sm text-muted-foreground">{openPositions.length} active position{openPositions.length !== 1 ? 's' : ''}</p>
            </div>
          </div>
          <div className="flex items-center gap-5">
            <div className="flex items-center gap-2 px-3.5 py-2 rounded-full bg-primary/10 border border-primary/20 backdrop-blur-sm">
              <motion.div 
                className="status-dot bg-primary"
                animate={{ opacity: [1, 0.5, 1] }}
                transition={{ duration: 2, repeat: Infinity }}
              />
              <span className="text-xs font-semibold text-primary tracking-wide">LIVE</span>
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
                {formatCurrencyWithSign(totalPnl)}
              </motion.p>
            </div>
          </div>
        </div>
      </div>

      {/* Table */}
      {openPositions.length > 0 ? (
        <>
          <div className="hidden md:block overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border/40 bg-muted/30">
                  <th className="px-6 py-4 text-left table-header">Symbol</th>
                  <th className="px-6 py-4 text-right table-header">Qty</th>
                  <th className="px-6 py-4 text-right table-header">Avg Price</th>
                  <th className="px-6 py-4 text-right table-header">Value</th>
                  <th className="px-6 py-4 text-right table-header">P&L</th>
                  <th className="px-6 py-4 w-10"></th>
                </tr>
              </thead>
              <tbody>
                {openPositions.map((position, index) => {
                  const isProfit = position.unrealized_pnl >= 0;
                  return (
                    <motion.tr
                      key={position.id}
                      onClick={() => onPositionClick?.(position)}
                      className={cn(
                        'border-b border-border/30 last:border-0',
                        'hover:bg-muted/50 transition-all duration-300 cursor-pointer group',
                        index % 2 === 0 ? 'bg-card' : 'bg-muted/10'
                      )}
                      initial={{ opacity: 0, x: -15 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: index * 0.06, type: 'spring', stiffness: 120 }}
                      whileHover={{ x: 3 }}
                    >
                      <td className="px-6 py-5">
                        <div className="flex items-center gap-3">
                          <span className="table-cell-mono font-semibold">{position.tradingsymbol}</span>
                          <span className="text-xs text-muted-foreground px-2.5 py-1 rounded-lg bg-muted/60 border border-border/50 font-medium">{position.instrument_type}</span>
                        </div>
                      </td>
                      <td className="px-6 py-5 text-right table-cell-mono font-medium">
                        {formatNumber(position.total_quantity)}
                      </td>
                      <td className="px-6 py-5 text-right table-cell-mono text-muted-foreground">
                        {formatPrice(position.average_entry_price)}
                      </td>
                      <td className="px-6 py-5 text-right table-cell-mono">
                        {formatCurrency(position.current_value)}
                      </td>
                      <td className="px-6 py-5 text-right">
                        <div className="flex items-center justify-end gap-2.5">
                          <motion.div
                            initial={{ scale: 0 }}
                            animate={{ scale: 1 }}
                            transition={{ delay: 0.3 + index * 0.05, type: 'spring' }}
                          >
                            {isProfit ? (
                              <TrendingUp className="h-4 w-4 text-success" />
                            ) : (
                              <TrendingDown className="h-4 w-4 text-destructive" />
                            )}
                          </motion.div>
                          <span className={cn(
                            'table-cell-mono font-semibold',
                            isProfit ? 'text-success' : 'text-destructive'
                          )}>
                            {formatCurrencyWithSign(position.unrealized_pnl)}
                          </span>
                        </div>
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
            {openPositions.map((position, index) => {
              const isProfit = position.unrealized_pnl >= 0;
              return (
                <motion.div 
                  key={position.id} 
                  onClick={() => onPositionClick?.(position)} 
                  className="p-5 hover:bg-muted/40 transition-all duration-300 cursor-pointer active:scale-[0.99] group"
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.05, type: 'spring' }}
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <p className="font-mono text-[15px] font-semibold text-foreground">{position.tradingsymbol}</p>
                        <span className="text-xs text-muted-foreground px-2 py-0.5 rounded-md bg-muted/60 border border-border/50">{position.instrument_type}</span>
                      </div>
                      <p className="text-sm text-muted-foreground mt-1.5">
                        {formatNumber(position.total_quantity)} × {formatPrice(position.average_entry_price)}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      {isProfit ? (
                        <TrendingUp className="h-4 w-4 text-success" />
                      ) : (
                        <TrendingDown className="h-4 w-4 text-destructive" />
                      )}
                      <span className={cn(
                        'font-mono text-[15px] font-semibold',
                        isProfit ? 'text-success' : 'text-destructive'
                      )}>
                        {formatCurrencyWithSign(position.unrealized_pnl)}
                      </span>
                      <ChevronRight className="h-4 w-4 text-muted-foreground/50 group-hover:text-primary transition-colors" />
                    </div>
                  </div>
                </motion.div>
              );
            })}
          </div>
        </>
      ) : (
        <div className="py-16 text-center">
          <motion.div 
            className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-muted/50 mb-4 border border-border/50"
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ type: 'spring', stiffness: 200 }}
          >
            <Briefcase className="h-8 w-8 text-muted-foreground" />
          </motion.div>
          <motion.p 
            className="text-base font-semibold text-foreground"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
          >
            No active positions
          </motion.p>
          <motion.p 
            className="text-sm text-muted-foreground mt-1"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.3 }}
          >
            Positions will appear here when you trade
          </motion.p>
        </div>
      )}
    </div>
  );
}
