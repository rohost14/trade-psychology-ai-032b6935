import { useState, useEffect, useCallback } from 'react';
import { api } from '@/lib/api';
import type { MarginStatus, MarginInsightsResponse } from '@/types/api';

interface UseMargins {
    margins: MarginStatus | null;
    insights: MarginInsightsResponse | null;
    isLoading: boolean;
    error: Error | null;
    refetch: () => Promise<void>;
}

export function useMargins(brokerAccountId: string | undefined): UseMargins {
    const [margins, setMargins] = useState<MarginStatus | null>(null);
    const [insights, setInsights] = useState<MarginInsightsResponse | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<Error | null>(null);

    const fetchMargins = useCallback(async () => {
        if (!brokerAccountId) return;

        setIsLoading(true);
        setError(null);

        try {
            const response = await api.get('/api/zerodha/margins');
            // Backend now returns the fully calculated MarginStatus structure
            setMargins(response.data);
        } catch (err: any) {
            console.error('Error fetching margins:', err);
            setError(err);
        } finally {
            setIsLoading(false);
        }
    }, [brokerAccountId]);

    const fetchInsights = useCallback(async () => {
        if (!brokerAccountId) return;

        try {
            const response = await api.get('/api/zerodha/margins/insights');
            setInsights(response.data);
        } catch (err: any) {
            console.error('Error fetching margin insights:', err);
            // Don't set error for insights - it's optional
        }
    }, [brokerAccountId]);

    const refetch = useCallback(async () => {
        await Promise.all([fetchMargins(), fetchInsights()]);
    }, [fetchMargins, fetchInsights]);

    useEffect(() => {
        if (brokerAccountId) {
            fetchMargins();
            fetchInsights();
        }
    }, [brokerAccountId, fetchMargins, fetchInsights]);

    // Auto-refresh every 30 seconds when tab is visible
    useEffect(() => {
        if (!brokerAccountId) return;

        const intervalId = setInterval(() => {
            if (document.visibilityState === 'visible') {
                fetchMargins();
            }
        }, 30000);

        return () => clearInterval(intervalId);
    }, [brokerAccountId, fetchMargins]);

    return { margins, insights, isLoading, error, refetch };
}
