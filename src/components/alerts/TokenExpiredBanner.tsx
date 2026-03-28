import { useState, useEffect, useCallback } from 'react';
import { AlertTriangle, RefreshCw, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useBroker } from '@/contexts/BrokerContext';
import { cn } from '@/lib/utils';

const DISMISS_DURATION_MS = 5 * 60 * 1000; // 5 minutes

interface TokenExpiredBannerProps {
    onReconnect?: () => void;
    isReconnecting?: boolean;
}

export default function TokenExpiredBanner({ onReconnect, isReconnecting }: TokenExpiredBannerProps) {
    const { connect } = useBroker();
    const [isDismissed, setIsDismissed] = useState(false);
    const [isExiting, setIsExiting] = useState(false);

    const handleDismiss = useCallback(() => {
        setIsExiting(true);
        // Wait for exit animation, then fully unmount
        setTimeout(() => setIsDismissed(true), 240);
    }, []);

    // Reappear after 5 minutes
    useEffect(() => {
        if (!isDismissed) return;
        setIsExiting(false);
        const timer = setTimeout(() => setIsDismissed(false), DISMISS_DURATION_MS);
        return () => clearTimeout(timer);
    }, [isDismissed]);

    const handleReconnect = async () => {
        if (onReconnect) {
            onReconnect();
        } else {
            await connect();
        }
    };

    if (isDismissed) return null;

    return (
        <div
            role="alert"
            aria-live="assertive"
            className={cn(
                'relative overflow-hidden',
                isExiting ? 'animate-slide-out-up' : 'animate-slide-in-down'
            )}
        >
            <div className="bg-gradient-to-r from-warning/20 via-warning/15 to-warning/10 border-b border-warning/30">
                <div className="container mx-auto px-4 py-3">
                    <div className="flex items-center justify-between gap-4">
                        <div className="flex items-center gap-3">
                            <div className="p-2 rounded-lg bg-warning/20 animate-pulse-scale">
                                <AlertTriangle className="h-5 w-5 text-warning" />
                            </div>
                            <div>
                                <p className="text-sm font-medium text-foreground">
                                    Zerodha session expired — live sync paused
                                </p>
                                <p className="text-xs text-muted-foreground">
                                    Analytics, journal, chat and trade history still work.
                                    Reconnect to resume live prices and alerts.
                                </p>
                            </div>
                        </div>
                        <div className="flex items-center gap-2">
                            <Button
                                variant="default"
                                size="sm"
                                onClick={handleReconnect}
                                disabled={isReconnecting}
                                className="gap-2 bg-warning text-warning-foreground hover:bg-warning/90"
                            >
                                {isReconnecting ? (
                                    <>
                                        <RefreshCw className="h-4 w-4 animate-spin" />
                                        Reconnecting...
                                    </>
                                ) : (
                                    <>
                                        <RefreshCw className="h-4 w-4" />
                                        Reconnect
                                    </>
                                )}
                            </Button>
                            <button
                                onClick={handleDismiss}
                                aria-label="Dismiss for 5 minutes"
                                className="p-1.5 rounded-lg hover:bg-warning/20 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                            >
                                <X className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
