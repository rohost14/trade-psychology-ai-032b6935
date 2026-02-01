import { motion } from 'framer-motion';
import { cn } from '@/lib/utils';
import { formatCurrency } from '@/lib/formatters';

interface HourlyData {
  hour: string;
  pnl: number;
  trades: number;
}

interface TimeAnalysisCardProps {
  hourlyData: HourlyData[];
}

export default function TimeAnalysisCard({ hourlyData }: TimeAnalysisCardProps) {
  const maxPnl = Math.max(...hourlyData.map(h => Math.abs(h.pnl)));
  const bestHour = hourlyData.reduce((best, curr) => curr.pnl > best.pnl ? curr : best, hourlyData[0]);
  const worstHour = hourlyData.reduce((worst, curr) => curr.pnl < worst.pnl ? curr : worst, hourlyData[0]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.2 }}
      className="bg-card rounded-lg border border-border shadow-sm"
    >
      <div className="px-6 py-4 border-b border-border">
        <h3 className="text-base font-semibold text-foreground">Performance by Hour</h3>
        <p className="text-sm text-muted-foreground">Find your optimal trading windows</p>
      </div>

      <div className="p-6">
        {/* Visual Bar Chart */}
        <div className="space-y-3">
          {hourlyData.map((data, idx) => {
            const width = maxPnl > 0 ? (Math.abs(data.pnl) / maxPnl) * 100 : 0;
            const isProfit = data.pnl >= 0;
            const isBest = data.hour === bestHour.hour;
            const isWorst = data.hour === worstHour.hour;

            return (
              <div key={data.hour} className="group">
                <div className="flex items-center gap-3">
                  <span className={cn(
                    'text-sm font-mono w-14 flex-shrink-0',
                    isBest ? 'text-success font-bold' : isWorst ? 'text-destructive font-bold' : 'text-muted-foreground'
                  )}>
                    {data.hour}
                  </span>
                  
                  <div className="flex-1 h-8 bg-muted/30 rounded relative overflow-hidden">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${Math.max(width, 2)}%` }}
                      transition={{ duration: 0.5, delay: idx * 0.05 }}
                      className={cn(
                        'absolute inset-y-0 left-0 rounded',
                        isProfit ? 'bg-success/80' : 'bg-destructive/80',
                        isBest && 'ring-2 ring-success ring-offset-1',
                        isWorst && 'ring-2 ring-destructive ring-offset-1'
                      )}
                    />
                    <div className="absolute inset-0 flex items-center px-3">
                      <span className={cn(
                        'text-xs font-mono font-medium',
                        width > 30 ? 'text-white' : 'text-foreground'
                      )}>
                        {isProfit ? '+' : ''}{formatCurrency(data.pnl)}
                      </span>
                    </div>
                  </div>

                  <span className="text-xs text-muted-foreground w-16 text-right flex-shrink-0">
                    {data.trades} trades
                  </span>
                </div>
              </div>
            );
          })}
        </div>

        {/* Legend */}
        <div className="flex items-center justify-center gap-6 mt-6 pt-4 border-t border-border">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded bg-success ring-2 ring-success ring-offset-1" />
            <span className="text-xs text-muted-foreground">Best: {bestHour.hour}</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded bg-destructive ring-2 ring-destructive ring-offset-1" />
            <span className="text-xs text-muted-foreground">Worst: {worstHour.hour}</span>
          </div>
        </div>
      </div>
    </motion.div>
  );
}
