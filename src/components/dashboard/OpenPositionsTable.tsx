import { useEffect, useRef, useState } from 'react';
import { TrendingUp, TrendingDown, Briefcase, Radio } from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatCurrency, formatPrice, formatNumber, formatCurrencyWithSign } from '@/lib/formatters';
import { useWebSocket } from '@/contexts/WebSocketContext';
import { useBroker } from '@/contexts/BrokerContext';
import type { Position } from '@/types/api';

interface OpenPositionsTableProps {
  positions: (Position & { instrument_type: string; unrealized_pnl: number; current_value: number })[];
  isLoading?: boolean;
  onPositionClick?: (position: Position & { instrument_type: string; unrealized_pnl: number; current_value: number }) => void;
}

/** Tracks which cells just got a price update for flash animation */
function usePriceFlash(key: string, price: number | undefined) {
  const prevPrice = useRef(price);
  const [flash, setFlash] = useState<'up' | 'down' | null>(null);

  useEffect(() => {
    if (price !== undefined && prevPrice.current !== undefined && price !== prevPrice.current) {
      setFlash(price > prevPrice.current ? 'up' : 'down');
      const timer = setTimeout(() => setFlash(null), 600);
      prevPrice.current = price;
      return () => clearTimeout(timer);
    }
    prevPrice.current = price;
  }, [price]);

  return flash;
}

function PriceCell({ symbol, staticPrice, livePrice }: { symbol: string; staticPrice: number; livePrice?: number }) {
  const displayPrice = livePrice ?? staticPrice;
  const flash = usePriceFlash(symbol, livePrice);

  return (
    <span
      className={cn(
        'tabular-nums transition-colors duration-300',
        flash === 'up' && 'text-green-500',
        flash === 'down' && 'text-red-500',
        !flash && 'text-foreground'
      )}
    >
      {formatPrice(displayPrice)}
    </span>
  );
}

export default function OpenPositionsTable({ positions, isLoading, onPositionClick }: OpenPositionsTableProps) {
  const openPositions = positions.filter((p) => p.status === 'open');
  const { account } = useBroker();
  const { prices, isConnected, subscribe } = useWebSocket();

  // Subscribe to position symbols when positions change
  useEffect(() => {
    if (openPositions.length > 0 && isConnected) {
      const symbols = openPositions.map((p) => p.tradingsymbol);
      subscribe(symbols);
    }
  }, [openPositions.length, isConnected, subscribe]);

  // Calculate live P&L for a position
  // Uses signed quantity: positive = long, negative = short
  // (current - entry) * qty naturally gives correct P&L for both directions
  const getLivePnl = (position: typeof openPositions[0]) => {
    const liveData = prices[position.tradingsymbol];
    if (liveData?.last_price) {
      return (liveData.last_price - position.average_entry_price) * position.total_quantity;
    }
    return position.unrealized_pnl;
  };

  const getLiveValue = (position: typeof openPositions[0]) => {
    const liveData = prices[position.tradingsymbol];
    if (liveData?.last_price) {
      return liveData.last_price * Math.abs(position.total_quantity);
    }
    return position.current_value;
  };

  const totalPnl = openPositions.reduce((sum, p) => sum + getLivePnl(p), 0);

  if (isLoading) {
    return (
      <div className="bg-card rounded-lg border border-border">
        <div className="px-6 py-5 border-b border-border">
          <div className="h-6 w-48 bg-muted animate-pulse rounded" />
        </div>
        <div className="p-6 space-y-3">
          {[1, 2].map((i) => (
            <div key={i} className="h-14 bg-muted animate-pulse rounded" />
          ))}
        </div>
      </div>
    );
  }

  const pnlColor = totalPnl >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400';

  return (
    <div className="bg-card rounded-lg border border-border">
      {/* Header */}
      <div className="px-4 py-3 border-b border-border">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Briefcase className="h-4 w-4 text-muted-foreground" />
            <h3 className="text-sm font-semibold text-foreground">Open Positions</h3>
            <span className="text-xs text-muted-foreground">({openPositions.length})</span>
            {isConnected && openPositions.length > 0 && (
              <span className="flex items-center gap-1 text-[10px] text-success bg-success/10 px-1.5 py-0.5 rounded-full">
                <Radio className="h-2.5 w-2.5 animate-pulse" />
                LIVE
              </span>
            )}
          </div>
          <div className={cn('text-sm font-semibold tabular-nums', pnlColor)}>
            {formatCurrencyWithSign(totalPnl)}
          </div>
        </div>
      </div>

      {/* Table */}
      {openPositions.length > 0 ? (
        <>
          {/* Desktop Table */}
          <div className="hidden md:block overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border bg-muted/30">
                  <th className="px-4 py-2 text-left text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Symbol</th>
                  <th className="px-3 py-2 text-right text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Qty</th>
                  <th className="px-3 py-2 text-right text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Avg Price</th>
                  <th className="px-3 py-2 text-right text-[11px] font-medium uppercase tracking-wide text-muted-foreground">LTP</th>
                  <th className="px-3 py-2 text-right text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Value</th>
                  <th className="px-3 py-2 text-right text-[11px] font-medium uppercase tracking-wide text-muted-foreground">P&L</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {openPositions.map((position) => {
                  const livePnl = getLivePnl(position);
                  const liveValue = getLiveValue(position);
                  const liveData = prices[position.tradingsymbol];
                  const isProfit = livePnl >= 0;
                  const rowPnlColor = isProfit ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400';
                  return (
                    <tr
                      key={position.id}
                      onClick={() => onPositionClick?.(position)}
                      className="hover:bg-muted/50 transition-colors cursor-pointer"
                    >
                      <td className="px-4 py-2.5">
                        <div className="flex items-center gap-1.5">
                          <span className="text-sm font-medium text-foreground">{position.tradingsymbol}</span>
                          <span className={cn(
                            'text-[10px] px-1 py-0.5 rounded font-medium',
                            position.total_quantity > 0
                              ? 'text-green-700 dark:text-green-400'
                              : 'text-red-700 dark:text-red-400'
                          )}>
                            {position.total_quantity > 0 ? 'B' : 'S'}
                          </span>
                        </div>
                      </td>
                      <td className="px-3 py-2.5 text-right text-sm tabular-nums text-foreground">
                        {formatNumber(Math.abs(position.total_quantity))}
                      </td>
                      <td className="px-3 py-2.5 text-right text-sm tabular-nums text-muted-foreground">
                        {formatPrice(position.average_entry_price)}
                      </td>
                      <td className="px-3 py-2.5 text-right text-sm">
                        <PriceCell
                          symbol={position.tradingsymbol}
                          staticPrice={position.last_price || position.average_entry_price}
                          livePrice={liveData?.last_price}
                        />
                      </td>
                      <td className="px-3 py-2.5 text-right text-sm tabular-nums text-foreground">
                        {formatCurrency(liveValue)}
                      </td>
                      <td className="px-3 py-2.5 text-right">
                        <span className={cn('text-sm tabular-nums font-medium', rowPnlColor)}>
                          {formatCurrencyWithSign(livePnl)}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Mobile Cards */}
          <div className="md:hidden divide-y divide-border">
            {openPositions.map((position) => {
              const livePnl = getLivePnl(position);
              const liveData = prices[position.tradingsymbol];
              const isProfit = livePnl >= 0;
              const cardPnlColor = isProfit ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400';
              return (
                <div
                  key={position.id}
                  onClick={() => onPositionClick?.(position)}
                  className="px-6 py-4 hover:bg-muted/50 transition-colors cursor-pointer"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <p className="font-medium text-foreground">{position.tradingsymbol}</p>
                        <span className={cn(
                          'text-xs px-1.5 py-0.5 rounded font-medium',
                          position.total_quantity > 0
                            ? 'bg-green-50 text-green-700 dark:bg-green-900/20 dark:text-green-400'
                            : 'bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-400'
                        )}>
                          {position.total_quantity > 0 ? 'LONG' : 'SHORT'}
                        </span>
                      </div>
                      <p className="text-sm text-muted-foreground mt-1">
                        {formatNumber(Math.abs(position.total_quantity))} × <PriceCell
                          symbol={position.tradingsymbol + '_mobile'}
                          staticPrice={position.last_price || position.average_entry_price}
                          livePrice={liveData?.last_price}
                        />
                      </p>
                    </div>
                    <div className="flex items-center gap-1.5">
                      {isProfit ? (
                        <TrendingUp className="h-4 w-4 text-green-600" />
                      ) : (
                        <TrendingDown className="h-4 w-4 text-red-600" />
                      )}
                      <span className={cn('tabular-nums font-medium', cardPnlColor)}>
                        {formatCurrencyWithSign(livePnl)}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </>
      ) : (
        <div className="py-12 text-center">
          <Briefcase className="h-10 w-10 text-muted-foreground/40 mx-auto mb-3" />
          <p className="font-medium text-foreground">No active positions</p>
          <p className="text-sm text-muted-foreground mt-1">Positions will appear here when you trade</p>
        </div>
      )}
    </div>
  );
}
