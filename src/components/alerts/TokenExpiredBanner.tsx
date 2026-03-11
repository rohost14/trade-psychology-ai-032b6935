import { useState, useEffect, useCallback } from 'react';
import { AlertTriangle, RefreshCw, X } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { Button } from '@/components/ui/button';
import { useBroker } from '@/contexts/BrokerContext';

const DISMISS_DURATION_MS = 5 * 60 * 1000; // 5 minutes

interface TokenExpiredBannerProps {
    onReconnect?: () => void;
    isReconnecting?: boolean;
}

export default function TokenExpiredBanner({ onReconnect, isReconnecting }: TokenExpiredBannerProps) {
    const { connect } = useBroker();
    const [isDismissed, setIsDismissed] = useState(false);

    const handleDismiss = useCallback(() => {
        setIsDismissed(true);
    }, []);

    // Reappear after 5 minutes
    useEffect(() => {
        if (!isDismissed) return;
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

    return (
        <AnimatePresence>
            {!isDismissed && (
                <motion.div
                    initial={{ opacity: 0, y: -50, height: 0 }}
                    animate={{ opacity: 1, y: 0, height: 'auto' }}
                    exit={{ opacity: 0, y: -50, height: 0 }}
                    transition={{ type: 'spring', stiffness: 200, damping: 20 }}
                    className="relative overflow-hidden"
                >
                    <div className="bg-gradient-to-r from-warning/20 via-warning/15 to-warning/10 border-b border-warning/30">
                        <div className="container mx-auto px-4 py-3">
                            <div className="flex items-center justify-between gap-4">
                                <div className="flex items-center gap-3">
                                    <motion.div
                                        className="p-2 rounded-lg bg-warning/20"
                                        animate={{ scale: [1, 1.1, 1] }}
                                        transition={{ duration: 2, repeat: Infinity }}
                                    >
                                        <AlertTriangle className="h-5 w-5 text-warning" />
                                    </motion.div>
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
                                        className="p-1.5 rounded-lg hover:bg-warning/20 transition-colors"
                                        title="Dismiss for 5 minutes"
                                    >
                                        <X className="h-4 w-4 text-muted-foreground" />
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </motion.div>
            )}
        </AnimatePresence>
    );
}
