// Emotional Tax Card - Shows the ₹ cost of behavioral errors
// Philosophy: Facts, not pressure

import { TrendingDown, TrendingUp, DollarSign, Info } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { EmotionalTax } from '@/types/patterns';
import { cn } from '@/lib/utils';

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
    
  const totalCost = tax.total_cost_all_time || 1; // Avoid division by zero
  
  const isImproving = tax.improvement_vs_last_month > 0;

  return (
    <Card className="border-risk-caution">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CardTitle className="text-lg flex items-center gap-2">
              <DollarSign className="h-5 w-5 text-warning" />
              Emotional Tax
            </CardTitle>
            <Tooltip>
              <TooltipTrigger>
                <Info className="h-4 w-4 text-muted-foreground" />
              </TooltipTrigger>
              <TooltipContent className="max-w-xs">
                <p>The calculated cost of trading decisions influenced by emotions rather than your trading plan.</p>
              </TooltipContent>
            </Tooltip>
          </div>
          {tax.improvement_vs_last_month !== 0 && (
            <Badge 
              variant={isImproving ? "default" : "destructive"}
              className="gap-1"
            >
              {isImproving ? (
                <TrendingUp className="h-3 w-3" />
              ) : (
                <TrendingDown className="h-3 w-3" />
              )}
              {Math.abs(tax.improvement_vs_last_month)}% vs last month
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Total Cost */}
        <div className="text-center py-4 rounded-lg bg-warning/10">
          <p className="text-3xl font-bold font-mono text-warning">
            ₹{displayCost.toLocaleString('en-IN')}
          </p>
          <p className="text-sm text-muted-foreground mt-1">
            {period === 'week' ? 'This Week' : period === 'month' ? 'This Month' : 'All Time'}
          </p>
        </div>
        
        {/* Breakdown */}
        <div className="space-y-2">
          <p className="text-sm font-medium text-muted-foreground">Breakdown by Pattern</p>
          {tax.breakdown.slice(0, 4).map((item) => {
            const percentage = Math.round((item.total_cost / totalCost) * 100);
            return (
              <div key={item.pattern_type} className="space-y-1">
                <div className="flex items-center justify-between text-sm">
                  <span>{item.pattern_name}</span>
                  <span className="font-mono text-muted-foreground">
                    ₹{item.total_cost.toLocaleString('en-IN')} ({percentage}%)
                  </span>
                </div>
                <div className="h-2 bg-muted rounded-full overflow-hidden">
                  <div 
                    className={cn(
                      "h-full transition-all",
                      percentage > 40 ? "bg-destructive" : 
                      percentage > 20 ? "bg-warning" : "bg-muted-foreground/50"
                    )}
                    style={{ width: `${percentage}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
        
        {/* Insight */}
        {tax.breakdown.length > 0 && (
          <div className="p-3 rounded-lg bg-muted/50 text-sm text-muted-foreground">
            <p className="italic">
              "{tax.breakdown[0]?.insight || 'Focus on reducing your most expensive pattern.'}"
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
