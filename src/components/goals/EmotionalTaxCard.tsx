import { TrendingDown, TrendingUp, DollarSign, Info } from 'lucide-react';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { EmotionalTax } from '@/types/patterns';

interface EmotionalTaxCardProps {
  tax: EmotionalTax;
  period?: 'week' | 'month' | 'all';
}

export function EmotionalTaxCard({ tax, period = 'month' }: EmotionalTaxCardProps) {
  const displayCost = period === 'week'
    ? tax.total_cost_this_week
    : period === 'month'
    ? tax.total_cost_this_month
    : tax.total_cost_all_time;

  const totalCost = tax.total_cost_all_time || 1;
  const isImproving = tax.improvement_vs_last_month > 0;

  const getBarColor = (pct: number) => {
    if (pct > 40) return 'bg-tm-loss';
    if (pct > 20) return 'bg-tm-obs';
    return 'bg-muted-foreground/40';
  };

  return (
    <div className="tm-card overflow-hidden">
      <div className="px-5 py-4 border-b border-border flex items-center justify-between">
        <div className="flex items-center gap-2">
          <p className="text-sm font-semibold text-foreground flex items-center gap-1.5">
            <DollarSign className="h-4 w-4 text-tm-obs" />
            Emotional Tax
          </p>
          <Tooltip>
            <TooltipTrigger>
              <Info className="h-3.5 w-3.5 text-muted-foreground" />
            </TooltipTrigger>
            <TooltipContent className="max-w-xs">
              <p>The calculated cost of trading decisions influenced by emotions rather than your plan.</p>
            </TooltipContent>
          </Tooltip>
        </div>
        {tax.improvement_vs_last_month !== 0 && (
          <span className={`inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full ${
            isImproving
              ? 'bg-teal-50 dark:bg-teal-900/20 text-tm-brand'
              : 'bg-red-50 dark:bg-red-900/20 text-tm-loss'
          }`}>
            {isImproving ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
            {Math.abs(tax.improvement_vs_last_month)}% vs last month
          </span>
        )}
      </div>
      <div className="p-5 space-y-4">
        {/* Total Cost */}
        <div className="text-center py-4 rounded-lg bg-amber-50/60 dark:bg-amber-900/10 border border-amber-100 dark:border-amber-800/20">
          <p className="text-3xl font-bold font-mono tabular-nums text-tm-obs">
            ₹{displayCost.toLocaleString('en-IN')}
          </p>
          <p className="text-xs text-muted-foreground mt-1">
            {period === 'week' ? 'This Week' : period === 'month' ? 'This Month' : 'All Time'}
          </p>
        </div>

        {/* Breakdown */}
        <div className="space-y-2">
          <p className="tm-label">Breakdown by Pattern</p>
          {tax.breakdown.slice(0, 4).map((item) => {
            const pct = Math.round((item.total_cost / totalCost) * 100);
            return (
              <div key={item.pattern_type} className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-foreground">{item.pattern_name}</span>
                  <span className="font-mono tabular-nums text-muted-foreground">
                    ₹{item.total_cost.toLocaleString('en-IN')} ({pct}%)
                  </span>
                </div>
                <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${getBarColor(pct)}`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>

        {/* Insight */}
        {tax.breakdown.length > 0 && (
          <div className="p-3 rounded-lg bg-muted/40 text-xs text-muted-foreground italic">
            "{tax.breakdown[0]?.insight || 'Focus on reducing your most expensive pattern.'}"
          </div>
        )}
      </div>
    </div>
  );
}
