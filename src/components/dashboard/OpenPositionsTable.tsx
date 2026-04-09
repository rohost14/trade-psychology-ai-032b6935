import { useEffect, useRef, useState } from 'react';
import { Briefcase, Pencil, CheckCircle2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatPrice, formatNumber, formatCurrencyWithSign } from '@/lib/formatters';
import { useWebSocket } from '@/contexts/WebSocketContext';
import type { Position } from '@/types/api';

type PositionWithExtras = Position & {
  instrument_type: string;
  unrealized_pnl: number;
  current_value: number;
};

interface OpenPositionsTableProps {
  positions: PositionWithExtras[];
  isLoading?: boolean;
  journaledIds?: Set<string>;
  onPositionClick?: (position: PositionWithExtras) => void;
}

// Parse Zerodha symbol into display parts
// Handles: weekly options (5-digit numeric expiry), monthly options (2YY+3MON expiry), futures, equity
function parseSymbol(sym: string, instrType?: string): { name: string; chip: string; sub: string } {
  // Weekly options: NAME + 5-digit expiry + 5-digit strike + CE/PE  e.g. NIFTY2541524600CE
  const mw5 = sym.match(/^([A-Z]+)\d{5}(\d{5})(CE|PE)$/);
  if (mw5) return { name: mw5[1], chip: mw5[3], sub: parseInt(mw5[2], 10).toLocaleString('en-IN') };
  // Weekly options: 6-digit strike  e.g. NIFTY25415100000CE
  const mw6 = sym.match(/^([A-Z]+)\d{5}(\d{6})(CE|PE)$/);
  if (mw6) return { name: mw6[1], chip: mw6[3], sub: parseInt(mw6[2], 10).toLocaleString('en-IN') };
  // Monthly options: NAME + 2YY + 3MON + strike + CE/PE  e.g. NIFTY25MAR23000CE
  const mm = sym.match(/^([A-Z]+)\d{2}[A-Z]{3}(\d{3,6})(CE|PE)$/);
  if (mm) return { name: mm[1], chip: mm[3], sub: parseInt(mm[2], 10).toLocaleString('en-IN') };
  // Futures (weekly or monthly)  e.g. NIFTY25MARFUT, BANKNIFTY25APR25FUT
  const mf = sym.match(/^([A-Z]+)(?:\d{5}|\d{2}[A-Z]{3})FUT$/);
  if (mf) return { name: mf[1], chip: 'FUT', sub: '' };
  // Equity / unknown fallback
  return { name: sym, chip: instrType && instrType !== 'EQ' ? instrType : 'EQ', sub: '' };
}

function chipClass(chip: string) {
  if (chip === 'CE') return 'tm-chip tm-chip-ce';
  if (chip === 'PE') return 'tm-chip tm-chip-pe';
  return 'tm-chip tm-chip-eq';
}

function usePriceFlash(key: string, price: number | undefined) {
  const prevPrice = useRef(price);
  const [flash, setFlash] = useState<'up' | 'down' | null>(null);
  useEffect(() => {
    if (price !== undefined && prevPrice.current !== undefined && price !== prevPrice.current) {
      setFlash(price > prevPrice.current ? 'up' : 'down');
      const t = setTimeout(() => setFlash(null), 600);
      prevPrice.current = price;
      return () => clearTimeout(t);
    }
    prevPrice.current = price;
  }, [price]);
  return flash;
}

function PriceCell({ symbol, staticPrice, livePrice }: {
  symbol: string; staticPrice: number; livePrice?: number;
}) {
  const display = livePrice ?? staticPrice;
  const flash = usePriceFlash(symbol, livePrice);
  return (
    <span className={cn(
      'font-mono tabular-nums transition-colors duration-300',
      flash === 'up' && 'text-tm-profit',
      flash === 'down' && 'text-tm-loss',
      !flash && 'text-foreground',
    )}>
      {formatPrice(display)}
    </span>
  );
}

export default function OpenPositionsTable({
  positions, isLoading, journaledIds = new Set(), onPositionClick,
}: OpenPositionsTableProps) {
  const openPositions = positions.filter(p => p.status === 'open');
  const { prices, isConnected, subscribe } = useWebSocket();

  useEffect(() => {
    if (openPositions.length > 0 && isConnected) {
      subscribe(openPositions.map(p => p.tradingsymbol));
    }
  }, [openPositions.length, isConnected, subscribe]);

  const getLivePnl = (p: PositionWithExtras) => {
    const live = prices[p.tradingsymbol];
    if (live?.last_price) {
      // p.multiplier is Zerodha's contract multiplier:
      //   NSE/BSE F&O (NFO/BFO): multiplier=1 — Kite sends qty in units already
      //   MCX commodities: multiplier=lot_size (e.g. GOLDM=10, SILVERM=30, CRUDEOIL=100)
      const mult = (p as any).multiplier ?? 1;
      return (live.last_price - p.average_entry_price) * p.total_quantity * mult;
    }
    return p.unrealized_pnl;
  };

  const totalPnl = openPositions.reduce((s, p) => s + getLivePnl(p), 0);

  if (isLoading) {
    return (
      <div className="tm-card">
        <div className="px-5 py-3 border-b border-slate-100 dark:border-neutral-700/60">
          <div className="h-4 w-40 bg-muted animate-pulse rounded" />
        </div>
        <div className="p-5 space-y-3">
          {[1, 2].map(i => <div key={i} className="h-10 bg-muted animate-pulse rounded" />)}
        </div>
      </div>
    );
  }

  return (
    <div className="tm-card">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-slate-100 dark:border-neutral-700/60">
        <div className="flex items-center gap-2">
          <span className="tm-label">Open Positions</span>
          <span className="text-[11px] text-muted-foreground font-mono tabular-nums">
            {openPositions.length}
          </span>
        </div>
        <div className="flex items-center gap-3">
          {/* Live dot */}
          {isConnected && openPositions.length > 0 && (
            <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-teal-50 dark:bg-teal-900/30">
              <span className="w-1.5 h-1.5 rounded-full animate-pulse bg-teal-500 dark:bg-teal-400" />
              <span className="text-[11px] font-semibold text-teal-600 dark:text-teal-400 uppercase tracking-wide">Live</span>
            </div>
          )}
          {/* Total P&L */}
          {openPositions.length > 0 && (
            <span className={cn(
              'text-sm font-semibold font-mono tabular-nums',
              totalPnl >= 0 ? 'text-tm-profit' : 'text-tm-loss',
            )}>
              {formatCurrencyWithSign(totalPnl)}
            </span>
          )}
        </div>
      </div>

      {openPositions.length > 0 ? (
        <table className="w-full">
          <thead>
            <tr className="border-b-2 border-b-slate-200 dark:border-b-neutral-700/80">
              {['Symbol', 'Qty', 'Avg', 'LTP', 'P&L', ''].map((h, idx) => (
                <th key={idx} className={cn(
                  'py-3 table-header',
                  idx === 0 ? 'px-5 text-left' :
                  idx === 5 ? 'px-5 w-10 text-left' :
                  'px-3 text-right',
                )}>
                  {h === '' ? <Pencil className="w-3 h-3 text-muted-foreground/50" /> : h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {openPositions.map((pos, i) => {
              const livePnl = getLivePnl(pos);
              const liveData = prices[pos.tradingsymbol];
              const qty = pos.total_quantity;
              const isJournaled = journaledIds.has(pos.id);
              const { name, chip, sub } = parseSymbol(pos.tradingsymbol, pos.instrument_type);
              return (
                <tr key={pos.id} className={cn(
                  'transition-colors hover:bg-slate-50 dark:hover:bg-slate-700/30',
                  i < openPositions.length - 1 && 'border-b border-slate-50 dark:border-neutral-700/30',
                  livePnl > 0 && 'bg-tm-profit/[0.03]',
                  livePnl < 0 && 'bg-tm-loss/[0.03]',
                )}>
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-1.5">
                      <span className="text-sm font-semibold text-foreground leading-none">{name}</span>
                      <span className={chipClass(chip)}>{chip}</span>
                    </div>
                    {sub && (
                      <span className="text-[12px] text-muted-foreground font-mono tabular-nums mt-1 block">
                        {sub} · {pos.product}
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-3 text-right">
                    <span className={cn('text-sm font-semibold', qty > 0 ? 'text-tm-profit' : 'text-tm-loss')}>
                      {qty > 0 ? 'BUY' : 'SELL'}
                    </span>
                    <span className="ml-1.5 text-sm font-mono tabular-nums text-foreground">
                      {formatNumber(Math.abs(qty))}
                    </span>
                  </td>
                  <td className="px-3 py-3 text-right text-sm font-mono tabular-nums font-medium text-muted-foreground">
                    {formatPrice(pos.average_entry_price)}
                  </td>
                  <td className="px-3 py-3 text-right text-sm font-medium">
                    <PriceCell
                      symbol={pos.tradingsymbol}
                      staticPrice={pos.last_price || pos.average_entry_price}
                      livePrice={liveData?.last_price}
                    />
                  </td>
                  <td className="px-3 py-3 text-right">
                    <span className={cn(
                      'text-sm font-mono tabular-nums font-semibold',
                      livePnl > 0 ? 'text-tm-profit' : livePnl < 0 ? 'text-tm-loss' : 'text-muted-foreground',
                    )}>
                      {formatCurrencyWithSign(livePnl)}
                    </span>
                  </td>
                  <td className="px-5 py-3">
                    <button
                      onClick={() => onPositionClick?.(pos)}
                      className="w-7 h-7 flex items-center justify-center rounded hover:bg-muted/60 transition-colors relative"
                    >
                      {isJournaled
                        ? <CheckCircle2 className="w-[18px] h-[18px] text-tm-profit" />
                        : <>
                            <Pencil className="w-[14px] h-[14px] text-muted-foreground" />
                            <span className="absolute top-0.5 right-0.5 w-[5px] h-[5px] rounded-full bg-tm-obs" />
                          </>
                      }
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      ) : (
        <div className="py-12 text-center">
          <Briefcase className="h-10 w-10 text-muted-foreground/40 mx-auto mb-3" />
          <p className="text-sm font-medium text-foreground">No active positions</p>
          <p className="text-[13px] text-muted-foreground mt-1">Positions will appear here when you trade</p>
        </div>
      )}
    </div>
  );
}
