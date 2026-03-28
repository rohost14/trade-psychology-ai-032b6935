import { BarChart3, CheckCircle2, XCircle, AlertTriangle, Clock, TrendingUp, Info } from 'lucide-react';
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
    positive: 'text-success bg-success/10 border-success/20',
    warning: 'text-warning bg-warning/10 border-warning/20',
    danger: 'text-destructive bg-destructive/10 border-destructive/20',
    info: 'text-primary bg-primary/10 border-primary/20',
};

export default function OrderAnalyticsCard({
    analytics,
    isLoading,
    onPeriodChange,
    selectedPeriod = 30
}: OrderAnalyticsCardProps) {
    if (isLoading) {
        return (
            <div className="card-premium">
                <div className="px-6 py-5 border-b border-border/40">
                    <div className="h-6 w-48 shimmer rounded-lg" />
                </div>
                <div className="p-6 space-y-4">
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                        {[1, 2, 3, 4].map((i) => (
                            <div key={i} className="h-20 shimmer rounded-xl" />
                        ))}
                    </div>
                    <div className="h-32 shimmer rounded-xl" />
                </div>
            </div>
        );
    }

    if (!analytics?.has_data) {
        return (
            <div className="card-premium">
                <div className="px-6 py-5 border-b border-border/40 bg-gradient-to-r from-primary/6 to-transparent">
                    <div className="flex items-center gap-4">
                        <div className="p-3 rounded-2xl bg-gradient-to-br from-primary/25 to-primary/10 border border-primary/20 shadow-lg">
                            <BarChart3 className="h-5 w-5 text-primary" />
                        </div>
                        <div>
                            <h3 className="text-lg font-semibold text-foreground">Order Analytics</h3>
                            <p className="text-sm text-muted-foreground">Last {selectedPeriod} days</p>
                        </div>
                    </div>
                </div>
                <div className="py-16 text-center">
                    <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-muted/50 mb-4 border border-border/50">
                        <BarChart3 className="h-8 w-8 text-muted-foreground" />
                    </div>
                    <p className="text-base font-semibold text-foreground">No order data yet</p>
                    <p className="text-sm text-muted-foreground mt-1">
                        Place some trades to see your order analytics
                    </p>
                </div>
            </div>
        );
    }

    const { summary, metrics, timing, insights } = analytics;

    // Calculate fill rate color
    const fillRateColor = summary.fill_rate_pct >= 90
        ? 'text-success'
        : summary.fill_rate_pct >= 70
            ? 'text-warning'
            : 'text-destructive';

    // Calculate cancel ratio color (lower is better)
    const cancelColor = metrics.cancel_ratio_pct <= 5
        ? 'text-success'
        : metrics.cancel_ratio_pct <= 15
            ? 'text-warning'
            : 'text-destructive';

    // Create hourly distribution bars
    const hourlyData = Object.entries(timing.hourly_distribution || {})
        .map(([hour, count]) => ({ hour: parseInt(hour), count: count as number }))
        .sort((a, b) => a.hour - b.hour);

    const maxHourlyCount = Math.max(...hourlyData.map(d => d.count), 1);

    return (
        <div className="card-premium">
            {/* Header */}
            <div className="px-6 py-5 border-b border-border/40 bg-gradient-to-r from-primary/6 to-transparent relative overflow-hidden">
                <div className="absolute inset-0 bg-gradient-mesh opacity-30 pointer-events-none" />

                <div className="relative flex items-center justify-between">
                    <div className="flex items-center gap-4">
                        <div className="p-3 rounded-2xl bg-gradient-to-br from-primary/25 to-primary/10 border border-primary/20 shadow-lg hover:scale-[1.008] transition-transform duration-200">
                            <BarChart3 className="h-5 w-5 text-primary" />
                        </div>
                        <div>
                            <h3 className="text-lg font-semibold text-foreground">Order Analytics</h3>
                            <p className="text-sm text-muted-foreground">Last {analytics.period_days} days</p>
                        </div>
                    </div>

                    {/* Period Selector */}
                    <div className="flex items-center gap-2">
                        {[7, 14, 30].map((days) => (
                            <button
                                key={days}
                                onClick={() => onPeriodChange?.(days)}
                                className={cn(
                                    'px-3 py-1.5 text-xs font-medium rounded-lg transition-all',
                                    selectedPeriod === days
                                        ? 'bg-primary text-primary-foreground'
                                        : 'bg-muted/50 text-muted-foreground hover:bg-muted'
                                )}
                            >
                                {days}D
                            </button>
                        ))}
                    </div>
                </div>
            </div>

            {/* Summary Stats */}
            <div className="grid grid-cols-2 lg:grid-cols-4 divide-x divide-y lg:divide-y-0 divide-border/40">
                <div className="px-6 py-5 animate-fade-in-up" style={{ animationDelay: '60ms' }}>
                    <p className="text-xs text-muted-foreground font-medium mb-1 uppercase tracking-wider">Total Orders</p>
                    <p className="text-2xl font-mono font-medium text-foreground">{summary.total_orders}</p>
                </div>
                <div className="px-6 py-5 animate-fade-in-up" style={{ animationDelay: '120ms' }}>
                    <p className="text-xs text-muted-foreground font-medium mb-1 uppercase tracking-wider">Fill Rate</p>
                    <p className={cn('text-2xl font-mono font-medium', fillRateColor)}>
                        {summary.fill_rate_pct.toFixed(1)}%
                    </p>
                </div>
                <div className="px-6 py-5 animate-fade-in-up" style={{ animationDelay: '180ms' }}>
                    <p className="text-xs text-muted-foreground font-medium mb-1 uppercase tracking-wider">Cancelled</p>
                    <p className={cn('text-2xl font-mono font-medium', cancelColor)}>
                        {metrics.cancel_ratio_pct.toFixed(1)}%
                    </p>
                </div>
                <div className="px-6 py-5 animate-fade-in-up" style={{ animationDelay: '240ms' }}>
                    <p className="text-xs text-muted-foreground font-medium mb-1 uppercase tracking-wider">Rejected</p>
                    <p className={cn(
                        'text-2xl font-mono font-medium',
                        summary.rejected === 0 ? 'text-success' : 'text-destructive'
                    )}>
                        {summary.rejected}
                    </p>
                </div>
            </div>

            {/* Hourly Distribution */}
            {hourlyData.length > 0 && (
                <div className="px-6 py-5 border-t border-border/40">
                    <div className="flex items-center gap-2 mb-4">
                        <Clock className="h-4 w-4 text-muted-foreground" />
                        <p className="text-sm font-medium text-foreground">Trading Activity by Hour</p>
                        {timing.peak_hour_formatted && (
                            <span className="text-xs text-muted-foreground ml-auto">
                                Peak: {timing.peak_hour_formatted}
                            </span>
                        )}
                    </div>
                    <div className="flex items-end gap-1 h-16">
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
                                        isPeak ? 'bg-primary' : count > 0 ? 'bg-primary/40' : 'bg-muted/40'
                                    )}
                                    style={{ height: `${Math.max(height, 4)}%` }}
                                    title={`${hour}:00 - ${count} orders`}
                                />
                            );
                        })}
                    </div>
                    <div className="flex justify-between mt-2 text-xs text-muted-foreground">
                        <span>9AM</span>
                        <span>12PM</span>
                        <span>3PM</span>
                    </div>
                </div>
            )}

            {/* Insights */}
            {insights && insights.length > 0 && (
                <div className="px-6 py-5 border-t border-border/40 space-y-3">
                    <div className="flex items-center gap-2 mb-3">
                        <TrendingUp className="h-4 w-4 text-muted-foreground" />
                        <p className="text-sm font-medium text-foreground">Behavioral Insights</p>
                    </div>
                    {insights.slice(0, 3).map((insight, index) => {
                        const IconComponent = insightIcons[insight.type] || Info;
                        const colorClass = insightColors[insight.type] || insightColors.info;

                        return (
                            <div
                                key={index}
                                className={cn(
                                    'flex items-start gap-3 p-4 rounded-xl border animate-fade-in-up',
                                    colorClass
                                )}
                                style={{ animationDelay: `${index * 60}ms` }}
                            >
                                <IconComponent className="h-5 w-5 mt-0.5 flex-shrink-0" />
                                <div className="flex-1 min-w-0">
                                    <p className="text-sm font-medium">{insight.title}</p>
                                    <p className="text-xs opacity-80 mt-1">{insight.message}</p>
                                    {insight.suggestion && (
                                        <p className="text-xs opacity-60 mt-2 italic">{insight.suggestion}</p>
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
