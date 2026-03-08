import { useState, useEffect, useCallback } from 'react';
import { api } from '@/lib/api';
import type { OrderAnalytics } from '@/types/api';

interface UseOrderAnalytics {
    analytics: OrderAnalytics | null;
    isLoading: boolean;
    error: Error | null;
    refetch: (days?: number) => Promise<void>;
}

export function useOrderAnalytics(
    brokerAccountId: string | undefined,
    initialDays: number = 30
): UseOrderAnalytics {
    const [analytics, setAnalytics] = useState<OrderAnalytics | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<Error | null>(null);
    const [days, setDays] = useState(initialDays);

    const fetchAnalytics = useCallback(async (fetchDays?: number) => {
        if (!brokerAccountId) return;

        const daysToFetch = fetchDays ?? days;
        if (fetchDays) setDays(fetchDays);

        setIsLoading(true);
        setError(null);

        try {
            const response = await api.get('/api/zerodha/order-analytics', {
                params: {
                    days: daysToFetch
                }
            });

            setAnalytics(response.data);
        } catch (err: any) {
            console.error('Error fetching order analytics:', err);
            setError(err);
            // Set empty analytics on error
            setAnalytics({
                has_data: false,
                period_days: daysToFetch,
                summary: {
                    total_orders: 0,
                    completed: 0,
                    cancelled: 0,
                    rejected: 0,
                    fill_rate_pct: 0
                },
                metrics: {
                    cancel_ratio_pct: 0,
                    modification_rate_pct: 0,
                    rejection_reasons: {}
                },
                timing: {
                    hourly_distribution: {},
                    peak_trading_hour: null,
                    peak_hour_formatted: null
                },
                insights: []
            });
        } finally {
            setIsLoading(false);
        }
    }, [brokerAccountId, days]);

    const refetch = useCallback(async (newDays?: number) => {
        await fetchAnalytics(newDays);
    }, [fetchAnalytics]);

    useEffect(() => {
        if (brokerAccountId) {
            fetchAnalytics();
        }
    }, [brokerAccountId, fetchAnalytics]);

    return { analytics, isLoading, error, refetch };
}
