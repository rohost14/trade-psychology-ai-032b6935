import { useState } from 'react';
import { Briefcase, TrendingUp, TrendingDown } from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatCurrency, formatPercentage } from '@/lib/formatters';

import { EnrichedHolding, HoldingsSummary } from '@/hooks/useHoldings';

interface HoldingsCardProps {
    holdings: EnrichedHolding[];
    summary: HoldingsSummary;
    isLoading?: boolean;
    onHoldingClick?: (holding: EnrichedHolding) => void;
}

export default function HoldingsCard({ holdings, summary, isLoading, onHoldingClick }: HoldingsCardProps) {
    const [showAll, setShowAll] = useState(false);
    if (isLoading) {
        return (
            <div className="bg-card rounded-lg border border-border p-6">
                <div className="animate-pulse space-y-4">
                    <div className="h-6 bg-muted rounded w-1/3" />
                    <div className="h-20 bg-muted rounded" />
                    <div className="space-y-2">
                        {[1, 2, 3].map((i) => (
                            <div key={i} className="h-12 bg-muted rounded" />
                        ))}
                    </div>
                </div>
            </div>
        );
    }

    const pnlColor = summary.totalPnl >= 0
        ? 'text-green-600 dark:text-green-400'
        : 'text-red-600 dark:text-red-400';
    const dayColor = summary.dayChange >= 0
        ? 'text-green-600 dark:text-green-400'
        : 'text-red-600 dark:text-red-400';

    return (
        <div className="bg-card rounded-lg border border-border">
            {/* Header */}
            <div className="px-6 py-5 border-b border-border">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="p-2.5 rounded-lg bg-primary/10">
                            <Briefcase className="h-5 w-5 text-primary" />
                        </div>
                        <div>
                            <h3 className="text-lg font-semibold text-foreground">Holdings</h3>
                            <p className="text-sm text-muted-foreground">{holdings.length} stocks</p>
                        </div>
                    </div>
                    <div className="text-right">
                        <p className="text-xl font-semibold text-foreground tabular-nums">
                            {formatCurrency(summary.totalValue)}
                        </p>
                        <p className={cn('text-sm font-medium tabular-nums', pnlColor)}>
                            {summary.totalPnl >= 0 ? '+' : ''}{formatCurrency(summary.totalPnl)} ({formatPercentage(summary.totalPnlPercent)})
                        </p>
                    </div>
                </div>
            </div>

            {/* Summary Stats */}
            <div className="grid grid-cols-2 divide-x divide-border border-b border-border">
                <div className="px-6 py-4">
                    <p className="text-sm text-muted-foreground mb-1">Total P&L</p>
                    <p className={cn('text-lg font-semibold tabular-nums', pnlColor)}>
                        {summary.totalPnl >= 0 ? '+' : ''}{formatCurrency(summary.totalPnl)}
                    </p>
                </div>
                <div className="px-6 py-4">
                    <p className="text-sm text-muted-foreground mb-1">Day Change</p>
                    <p className={cn('text-lg font-semibold tabular-nums', dayColor)}>
                        {summary.dayChange >= 0 ? '+' : ''}{formatCurrency(summary.dayChange)}
                    </p>
                </div>
            </div>

            {/* Holdings List */}
            {holdings.length > 0 ? (
                <div className="divide-y divide-border">
                    {(showAll ? holdings : holdings.slice(0, 5)).map((holding) => {
                        const holdingPnl = holding.pnl || 0;
                        const holdingPnlColor = holdingPnl >= 0
                            ? 'text-green-600 dark:text-green-400'
                            : 'text-red-600 dark:text-red-400';
                        const TrendIcon = holdingPnl >= 0 ? TrendingUp : TrendingDown;

                        return (
                            <div
                                key={`${holding.exchange}:${holding.tradingsymbol}`}
                                className={cn(
                                    'px-6 py-4 hover:bg-muted/50 transition-colors',
                                    onHoldingClick && 'cursor-pointer'
                                )}
                                onClick={() => onHoldingClick?.(holding)}
                            >
                                <div className="flex items-center justify-between">
                                    <div>
                                        <p className="font-medium text-foreground">{holding.tradingsymbol}</p>
                                        <p className="text-sm text-muted-foreground">
                                            {holding.quantity} qty @ {formatCurrency(holding.average_price)}
                                        </p>
                                    </div>
                                    <div className="text-right">
                                        <p className="font-medium text-foreground tabular-nums">
                                            {formatCurrency(holding.current_value)}
                                        </p>
                                        <div className={cn('flex items-center justify-end gap-1 text-sm', holdingPnlColor)}>
                                            <TrendIcon className="h-3.5 w-3.5" />
                                            <span className="tabular-nums">
                                                {holdingPnl >= 0 ? '+' : ''}{formatCurrency(holdingPnl)} ({formatPercentage(holding.pnl_pct)})
                                            </span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        );
                    })}
                    {holdings.length > 5 && (
                        <div className="px-6 py-3 text-center">
                            <button
                              className="text-sm text-primary hover:underline"
                              onClick={() => setShowAll(!showAll)}
                            >
                                {showAll ? 'Show less' : `View all ${holdings.length} holdings`}
                            </button>
                        </div>
                    )}
                </div>
            ) : (
                <div className="px-6 py-8 text-center">
                    <Briefcase className="h-10 w-10 text-muted-foreground/40 mx-auto mb-3" />
                    <p className="text-muted-foreground">No holdings found</p>
                </div>
            )}
        </div>
    );
}
