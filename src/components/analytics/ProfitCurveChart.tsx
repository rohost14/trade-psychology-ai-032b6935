import { useState } from 'react';
import { motion } from 'framer-motion';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Area,
  ComposedChart,
} from 'recharts';
import { HourlyPnl } from '@/data/analyticsData';
import { formatCurrency } from '@/lib/formatters';

interface ProfitCurveChartProps {
  hourlyData: HourlyPnl[];
}

type FilterType = 'all' | 'wins' | 'losses';

const ProfitCurveChart = ({ hourlyData }: ProfitCurveChartProps) => {
  const [filter, setFilter] = useState<FilterType>('all');

  const getFilteredData = () => {
    switch (filter) {
      case 'wins':
        return hourlyData.map((d) => ({ ...d, pnl: d.pnl > 0 ? d.pnl : 0, trades: d.wins }));
      case 'losses':
        return hourlyData.map((d) => ({ ...d, pnl: d.pnl < 0 ? d.pnl : 0, trades: d.losses }));
      default:
        return hourlyData;
    }
  };

  const data = getFilteredData();

  // Calculate cumulative P&L
  let cumulative = 0;
  const cumulativeData = data.map((d) => {
    cumulative += d.pnl;
    return { ...d, cumulative };
  });

  // Find best and worst hours
  const bestHour = hourlyData.reduce((best, current) =>
    current.pnl > best.pnl ? current : best
  );
  const worstHour = hourlyData.reduce((worst, current) =>
    current.pnl < worst.pnl ? current : worst
  );

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="bg-popover/95 backdrop-blur-lg border border-border rounded-xl p-3 shadow-xl">
          <p className="text-sm font-semibold text-foreground mb-2">{label}</p>
          <div className="space-y-1.5 text-xs">
            <div className="flex justify-between gap-4">
              <span className="text-muted-foreground">P&L</span>
              <span className={`font-mono font-semibold ${data.pnl >= 0 ? 'text-success' : 'text-destructive'}`}>
                {data.pnl >= 0 ? '+' : ''}{formatCurrency(data.pnl)}
              </span>
            </div>
            <div className="flex justify-between gap-4">
              <span className="text-muted-foreground">Cumulative</span>
              <span className={`font-mono font-semibold ${data.cumulative >= 0 ? 'text-success' : 'text-destructive'}`}>
                {data.cumulative >= 0 ? '+' : ''}{formatCurrency(data.cumulative)}
              </span>
            </div>
            <div className="flex justify-between gap-4">
              <span className="text-muted-foreground">Trades</span>
              <span className="font-medium text-foreground">{data.trades}</span>
            </div>
          </div>
        </div>
      );
    }
    return null;
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.3 }}
      className="relative overflow-hidden rounded-2xl border border-border/50 bg-card/80 backdrop-blur-xl p-6"
    >
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
        <div>
          <h3 className="text-lg font-semibold text-foreground">Time-of-Day Performance</h3>
          <p className="text-sm text-muted-foreground">P&L curve by trading hour</p>
        </div>

        {/* Toggle buttons */}
        <div className="flex items-center gap-1 p-1 bg-muted/50 rounded-lg">
          {(['all', 'wins', 'losses'] as FilterType[]).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`
                px-3 py-1.5 text-xs font-medium rounded-md transition-all
                ${filter === f
                  ? f === 'wins'
                    ? 'bg-success text-success-foreground'
                    : f === 'losses'
                    ? 'bg-destructive text-destructive-foreground'
                    : 'bg-background text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
                }
              `}
            >
              {f === 'all' ? 'All' : f === 'wins' ? 'Wins Only' : 'Losses Only'}
            </button>
          ))}
        </div>
      </div>

      {/* Best/Worst hour badges */}
      <div className="flex flex-wrap gap-3 mb-4">
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-success/10 border border-success/20">
          <div className="w-2 h-2 rounded-full bg-success" />
          <span className="text-xs text-success font-medium">
            Best: {bestHour.hour} ({formatCurrency(bestHour.pnl)})
          </span>
        </div>
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-destructive/10 border border-destructive/20">
          <div className="w-2 h-2 rounded-full bg-destructive" />
          <span className="text-xs text-destructive font-medium">
            Worst: {worstHour.hour} ({formatCurrency(worstHour.pnl)})
          </span>
        </div>
      </div>

      {/* Chart */}
      <div className="h-[280px]">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={cumulativeData}>
            <defs>
              <linearGradient id="profitGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="hsl(var(--success))" stopOpacity={0.3} />
                <stop offset="100%" stopColor="hsl(var(--success))" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="lossGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="hsl(var(--destructive))" stopOpacity={0} />
                <stop offset="100%" stopColor="hsl(var(--destructive))" stopOpacity={0.3} />
              </linearGradient>
            </defs>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="hsl(var(--border))"
              strokeOpacity={0.5}
              vertical={false}
            />
            <XAxis
              dataKey="hour"
              axisLine={false}
              tickLine={false}
              tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }}
            />
            <YAxis
              axisLine={false}
              tickLine={false}
              tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }}
              tickFormatter={(value) => `₹${value > 0 ? '+' : ''}${value}`}
            />
            <Tooltip content={<CustomTooltip />} />
            <ReferenceLine
              y={0}
              stroke="hsl(var(--border))"
              strokeWidth={2}
            />
            <Area
              type="monotone"
              dataKey="cumulative"
              stroke="none"
              fill="url(#profitGradient)"
              animationDuration={800}
            />
            <Line
              type="monotone"
              dataKey="cumulative"
              stroke="hsl(var(--success))"
              strokeWidth={2.5}
              dot={{
                fill: 'hsl(var(--background))',
                stroke: 'hsl(var(--success))',
                strokeWidth: 2,
                r: 4,
              }}
              activeDot={{
                fill: 'hsl(var(--success))',
                stroke: 'hsl(var(--background))',
                strokeWidth: 2,
                r: 6,
              }}
              animationDuration={800}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </motion.div>
  );
};

export default ProfitCurveChart;
