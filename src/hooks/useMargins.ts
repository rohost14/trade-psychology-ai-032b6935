/**
 * useMargins — margin data with zero polling.
 *
 * Initial load: fetches once from /api/zerodha/margins
 *   → backend serves from Redis cache (written by trade webhook pipeline)
 *   → falls back to live Kite API call on cache miss
 *
 * Real-time updates: WebSocketContext pushes margin_update events
 *   → backend fetches fresh margins from Kite after every trade webhook
 *   → pushed via Redis Streams → WebSocket → here
 *
 * No 30s polling interval. No unnecessary Kite API calls.
 */
import { useState, useEffect, useCallback } from 'react';
import { api } from '@/lib/api';
import { useWebSocket } from '@/contexts/WebSocketContext';
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

    // Subscribe to margin updates from WebSocket (replaces 30s polling)
    const { margins: wsMargins } = useWebSocket();
    useEffect(() => {
        if (wsMargins) {
            setMargins(wsMargins as unknown as MarginStatus);
        }
    }, [wsMargins]);

    const fetchMargins = useCallback(async () => {
        if (!brokerAccountId) return;
        setIsLoading(true);
        setError(null);
        try {
            const response = await api.get('/api/zerodha/margins');
            setMargins(response.data);
        } catch (err: any) {
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
        } catch {
            // Insights are optional — non-fatal
        }
    }, [brokerAccountId]);

    const refetch = useCallback(async () => {
        await Promise.all([fetchMargins(), fetchInsights()]);
    }, [fetchMargins, fetchInsights]);

    // One-time fetch on mount (serves from Redis cache on backend)
    useEffect(() => {
        if (brokerAccountId) {
            fetchMargins();
            fetchInsights();
        }
    }, [brokerAccountId, fetchMargins, fetchInsights]);

    // NO polling interval — margins updated via WebSocket margin_update events

    return { margins, insights, isLoading, error, refetch };
}
