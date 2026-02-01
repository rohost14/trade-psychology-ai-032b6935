import { motion } from 'framer-motion';
import { ArrowUpRight, ArrowDownRight, Clock, Target, AlertTriangle, TrendingUp, TrendingDown } from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatCurrency } from '@/lib/formatters';

interface PerformanceSummary {
  totalPnl: number;
  winRate: number;
  totalTrades: number;
  avgWin: number;
  avgLoss: number;
  profitFactor: number;
  bestDay: { date: string; pnl: number };
  worstDay: { date: string; pnl: number };
}

interface PerformanceSummaryCardProps {
  data: PerformanceSummary;
}

export default function PerformanceSummaryCard({ data }: PerformanceSummaryCardProps) {
  const isProfit = data.totalPnl >= 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-card rounded-lg border border-border shadow-sm overflow-hidden"
    >
      {/* Header with Total P&L */}
      <div className={cn(
        'px-6 py-5 border-l-4',
        isProfit ? 'border-l-success bg-success/5' : 'border-l-destructive bg-destructive/5'
      )}>
        <p className="text-sm text-muted-foreground mb-1">This Week's P&L</p>
        <div className="flex items-center gap-2">
          {isProfit ? (
            <ArrowUpRight className="h-6 w-6 text-success" />
          ) : (
            <ArrowDownRight className="h-6 w-6 text-destructive" />
          )}
          <span className={cn(
            'text-3xl font-bold font-mono',
            isProfit ? 'text-success' : 'text-destructive'
          )}>
            {isProfit ? '+' : ''}{formatCurrency(data.totalPnl)}
          </span>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-border">
        <div className="bg-card p-4">
          <div className="flex items-center gap-2 text-muted-foreground mb-1">
            <Target className="h-4 w-4" />
            <span className="text-xs">Win Rate</span>
          </div>
          <span className={cn(
            'text-xl font-bold font-mono',
            data.winRate >= 50 ? 'text-success' : 'text-destructive'
          )}>
            {data.winRate.toFixed(1)}%
          </span>
        </div>

        <div className="bg-card p-4">
          <div className="flex items-center gap-2 text-muted-foreground mb-1">
            <Clock className="h-4 w-4" />
            <span className="text-xs">Total Trades</span>
          </div>
          <span className="text-xl font-bold font-mono text-foreground">
            {data.totalTrades}
          </span>
        </div>

        <div className="bg-card p-4">
          <div className="flex items-center gap-2 text-muted-foreground mb-1">
            <TrendingUp className="h-4 w-4 text-success" />
            <span className="text-xs">Avg Win</span>
          </div>
          <span className="text-xl font-bold font-mono text-success">
            +{formatCurrency(data.avgWin)}
          </span>
        </div>

        <div className="bg-card p-4">
          <div className="flex items-center gap-2 text-muted-foreground mb-1">
            <TrendingDown className="h-4 w-4 text-destructive" />
            <span className="text-xs">Avg Loss</span>
          </div>
          <span className="text-xl font-bold font-mono text-destructive">
            {formatCurrency(data.avgLoss)}
          </span>
        </div>
      </div>

      {/* Best/Worst Days */}
      <div className="grid grid-cols-2 gap-px bg-border border-t border-border">
        <div className="bg-card p-4">
          <p className="text-xs text-muted-foreground mb-1">Best Day</p>
          <p className="text-sm font-medium text-foreground">{data.bestDay.date}</p>
          <p className="text-lg font-bold font-mono text-success">+{formatCurrency(data.bestDay.pnl)}</p>
        </div>
        <div className="bg-card p-4">
          <p className="text-xs text-muted-foreground mb-1">Worst Day</p>
          <p className="text-sm font-medium text-foreground">{data.worstDay.date}</p>
          <p className="text-lg font-bold font-mono text-destructive">{formatCurrency(data.worstDay.pnl)}</p>
        </div>
      </div>
    </motion.div>
  );
}
