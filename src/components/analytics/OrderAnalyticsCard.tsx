import { BarChart3, CheckCircle2, XCircle, AlertTriangle, Clock, TrendingUp, Info } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import type { OrderAnalytics } from '@/types/api';

interface OrderAnalyticsCardProps {
    analytics: OrderAnalytics | null;
    isLoading?: boolean;
    onPeriodChange?: (days: number) => void;
    selectedPeriod?: number;
}

const insightIcons = {
    positive: CheckCircle2,
    warning: AlertTriangle,
    danger: XCircle,
    info: Info,
};

const insightColors = {
    positive: 'text-tm-profit bg-green-50 dark:bg-green-900/10 border-green-200 dark:border-green-800/30',
    warning: 'text-tm-obs bg-amber-50 dark:bg-amber-900/10 border-amber-200 dark:border-amber-800/30',
    danger: 'text-tm-loss bg-red-50 dark:bg-red-900/10 border-red-200 dark:border-red-800/30',
    info: 'text-tm-brand bg-teal-50 dark:bg-teal-900/10 border-teal-200 dark:border-teal-800/30',
};

export default function OrderAnalyticsCard({
    analytics,
    isLoading,
    onPeriodChange,
    selectedPeriod = 30
}: OrderAnalyticsCardProps) {
    if (isLoading) {
        return (
            <div className="tm-card overflow-hidden">
                <div className="px-5 py-4 border-b border-border">
                    <Skeleton className="h-5 w-40" />
                </div>
                <div className="p-5 space-y-4">
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                        {[1, 2, 3, 4].map((i) => (
                            <Skeleton key={i} className="h-16 rounded-xl" />
                        ))}
                    </div>
                    <Skeleton className="h-24 rounded-xl" />
                </div>
            </div>
        );
    }

    if (!analytics?.has_data) {
        return (
            <div className="tm-card overflow-hidden">
                <div className="px-5 py-4 border-b border-border flex items-center gap-2">
                    <BarChart3 className="h-4 w-4 text-muted-foreground" />
                    <span className="tm-label">Order Analytics</span>
                </div>
                <div className="py-12 flex flex-col items-center justify-center text-center">
                    <BarChart3 className="h-8 w-8 text-muted-foreground/30 mb-3" />
                    <p className="text-sm font-medium text-foreground">No order data yet</p>
                    <p className="text-xs text-muted-foreground mt-1">Place some trades to see order analytics</p>
                </div>
            </div>
        );
    }

    const { summary, metrics, timing, insights } = analytics;

    const fillRateColor = summary.fill_rate_pct >= 90
        ? 'text-tm-profit'
        : summary.fill_rate_pct >= 70
            ? 'text-tm-obs'
            : 'text-tm-loss';

    const cancelColor = metrics.cancel_ratio_pct <= 5
        ? 'text-tm-profit'
        : metrics.cancel_ratio_pct <= 15
            ? 'text-tm-obs'
            : 'text-tm-loss';

    const hourlyData = Object.entries(timing.hourly_distribution || {})
        .map(([hour, count]) => ({ hour: parseInt(hour), count: count as number }))
        .sort((a, b) => a.hour - b.hour);

    const maxHourlyCount = Math.max(...hourlyData.map(d => d.count), 1);

    return (
        <div className="tm-card overflow-hidden">
            {/* Header */}
            <div className="px-5 py-4 border-b border-border flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <BarChart3 className="h-4 w-4 text-muted-foreground" />
                    <span className="tm-label">Order Analytics</span>
                    <span className="text-[11px] text-muted-foreground">· last {analytics.period_days}d</span>
                </div>
                <div className="flex items-center gap-1 p-1 bg-slate-100 dark:bg-neutral-700/50 rounded-lg">
                    {[7, 14, 30].map((days) => (
                        <button
                            key={days}
                            onClick={() => onPeriodChange?.(days)}
                            className={cn(
                                'px-2.5 py-1 text-[11px] font-medium rounded-md transition-all',
                                selectedPeriod === days
                                    ? 'bg-white dark:bg-neutral-800 text-foreground shadow-sm'
                                    : 'text-muted-foreground hover:text-foreground'
                            )}
                        >
                            {days}D
                        </button>
                    ))}
                </div>
            </div>

            {/* Summary Stats */}
            <div className="grid grid-cols-2 lg:grid-cols-4 divide-x divide-y lg:divide-y-0 divide-border">
                <div className="px-5 py-4">
                    <p className="tm-label mb-1">Total Orders</p>
                    <p className="text-2xl font-mono font-semibold tabular-nums text-foreground">{summary.total_orders}</p>
                </div>
                <div className="px-5 py-4">
                    <p className="tm-label mb-1">Fill Rate</p>
                    <p className={cn('text-2xl font-mono font-semibold tabular-nums', fillRateColor)}>
                        {summary.fill_rate_pct.toFixed(1)}%
                    </p>
                </div>
                <div className="px-5 py-4">
                    <p className="tm-label mb-1">Cancelled</p>
                    <p className={cn('text-2xl font-mono font-semibold tabular-nums', cancelColor)}>
                        {metrics.cancel_ratio_pct.toFixed(1)}%
                    </p>
                </div>
                <div className="px-5 py-4">
                    <p className="tm-label mb-1">Rejected</p>
                    <p className={cn(
                        'text-2xl font-mono font-semibold tabular-nums',
                        summary.rejected === 0 ? 'text-tm-profit' : 'text-tm-loss'
                    )}>
                        {summary.rejected}
                    </p>
                </div>
            </div>

            {/* Hourly Distribution */}
            {hourlyData.length > 0 && (
                <div className="px-5 py-4 border-t border-border">
                    <div className="flex items-center gap-2 mb-3">
                        <Clock className="h-3.5 w-3.5 text-muted-foreground" />
                        <p className="text-[12px] font-medium text-foreground">Activity by Hour</p>
                        {timing.peak_hour_formatted && (
                            <span className="text-[11px] text-muted-foreground ml-auto">
                                Peak: {timing.peak_hour_formatted}
                            </span>
                        )}
                    </div>
                    <div className="flex items-end gap-0.5 h-12">
                        {Array.from({ length: 24 }, (_, hour) => {
                            const data = hourlyData.find(d => d.hour === hour);
                            const count = data?.count || 0;
                            const height = maxHourlyCount > 0 ? (count / maxHourlyCount) * 100 : 0;
                            const isPeak = hour === timing.peak_trading_hour;
                            return (
                                <div
                                    key={hour}
                                    className={cn(
                                        'flex-1 rounded-t-sm transition-colors',
                                        isPeak ? 'bg-tm-brand' : count > 0 ? 'bg-tm-brand/35' : 'bg-slate-100 dark:bg-neutral-700/40'
                                    )}
                                    style={{ height: `${Math.max(height, 4)}%` }}
                                    title={`${hour}:00 — ${count} orders`}
                                />
                            );
                        })}
                    </div>
                    <div className="flex justify-between mt-1.5 text-[10px] text-muted-foreground">
                        <span>9AM</span>
                        <span>12PM</span>
                        <span>3PM</span>
                    </div>
                </div>
            )}

            {/* Insights */}
            {insights && insights.length > 0 && (
                <div className="px-5 py-4 border-t border-border space-y-2">
                    <div className="flex items-center gap-2 mb-2">
                        <TrendingUp className="h-3.5 w-3.5 text-muted-foreground" />
                        <p className="text-[12px] font-medium text-foreground">Behavioral Insights</p>
                    </div>
                    {insights.slice(0, 3).map((insight, index) => {
                        const IconComponent = insightIcons[insight.type] || Info;
                        const colorClass = insightColors[insight.type] || insightColors.info;
                        return (
                            <div
                                key={index}
                                className={cn('flex items-start gap-2.5 p-3 rounded-lg border text-sm', colorClass)}
                            >
                                <IconComponent className="h-4 w-4 mt-0.5 flex-shrink-0" />
                                <div className="flex-1 min-w-0">
                                    <p className="font-medium text-[12px]">{insight.title}</p>
                                    <p className="text-[11px] opacity-80 mt-0.5">{insight.message}</p>
                                    {insight.suggestion && (
                                        <p className="text-[11px] opacity-60 mt-1 italic">{insight.suggestion}</p>
                                    )}
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}
