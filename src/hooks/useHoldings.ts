import { useState, useEffect, useCallback } from 'react';
import { api } from '@/lib/api';
import type { Holding } from '@/types/api';

export interface HoldingsSummary {
    totalValue: number;
    totalPnl: number;
    totalPnlPercent: number;
    dayChange: number;
    dayChangePercent: number;
}

export interface EnrichedHolding extends Holding {
    current_value: number;
    pnl_pct: number;
    day_change_pct: number;
}

interface UseHoldings {
    holdings: EnrichedHolding[];
    summary: HoldingsSummary;
    isLoading: boolean;
    error: Error | null;
    refetch: () => Promise<void>;
}

export function useHoldings(brokerAccountId: string | undefined): UseHoldings {
    const [holdings, setHoldings] = useState<EnrichedHolding[]>([]);
    const [summary, setSummary] = useState<HoldingsSummary>({
        totalValue: 0,
        totalPnl: 0,
        totalPnlPercent: 0,
        dayChange: 0,
        dayChangePercent: 0
    });
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<Error | null>(null);

    const fetchHoldings = useCallback(async () => {
        if (!brokerAccountId) return;

        setIsLoading(true);
        setError(null);

        try {
            const response = await api.get('/api/zerodha/holdings');

            const holdingsData: Holding[] = response.data.holdings || [];
            // setHoldings will be called after enrichment

            // Calculate summary
            let totalValue = 0;
            let totalInvested = 0;
            let dayChange = 0;

            const enrichedHoldings: EnrichedHolding[] = [];

            for (const h of holdingsData) {
                const currentValue = (h.last_price || 0) * h.quantity;
                const investedValue = (h.average_price || 0) * h.quantity;
                const holdingDayChange = (h.day_change || 0) * h.quantity;

                const pnl = (currentValue - investedValue);
                const pnl_pct = investedValue > 0 ? (pnl / investedValue) * 100 : 0;

                // Use day_change_percentage from API if available, else calculate
                const day_change_pct = h.day_change_percentage || 0;

                enrichedHoldings.push({
                    ...h,
                    current_value: currentValue,
                    pnl_pct: pnl_pct,
                    day_change_pct: day_change_pct,
                    pnl: pnl // Ensure pnl is set
                });

                totalValue += currentValue;
                totalInvested += investedValue;
                dayChange += holdingDayChange;
            }

            setHoldings(enrichedHoldings);

            const totalPnl = totalValue - totalInvested;
            const totalPnlPercent = totalInvested > 0 ? (totalPnl / totalInvested) * 100 : 0;
            const dayChangePercent = totalValue > 0 ? (dayChange / totalValue) * 100 : 0;

            setSummary({
                totalValue,
                totalPnl,
                totalPnlPercent,
                dayChange,
                dayChangePercent
            });
        } catch (err: any) {
            console.error('Error fetching holdings:', err);
            setError(err);
        } finally {
            setIsLoading(false);
        }
    }, [brokerAccountId]);

    const refetch = useCallback(async () => {
        await fetchHoldings();
    }, [fetchHoldings]);

    useEffect(() => {
        if (brokerAccountId) {
            fetchHoldings();
        }
    }, [brokerAccountId, fetchHoldings]);

    return { holdings, summary, isLoading, error, refetch };
}
