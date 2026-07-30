import { useEffect, useRef, useState } from 'react';
import { Briefcase, NotebookPen, ChevronRight, CheckCircle2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatPrice, formatNumber, formatCurrencyWithSign } from '@/lib/formatters';
import { positionJournalTradeId } from '@/lib/journalKey';
import { parseSymbol } from '@/lib/symbolParser';
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
  /** Live-price freshness signals (from WebSocketContext) — drives the LTP status pill. */
  pricesConnected?: boolean;
  lastPriceAt?: number | null;
  tokenExpired?: boolean;
}

// A live tick is expected roughly every second per instrument during market hours.
const PRICE_STALE_MS = 20_000;

function PriceStatusPill({ status }: { status: 'live' | 'delayed' | 'paused' }) {
  const cfg = {
    live:    { label: 'Live',    dot: 'bg-profit',           text: 'text-profit' },
    delayed: { label: 'Delayed', dot: 'bg-warning',          text: 'text-warning' },
    paused:  { label: 'Paused',  dot: 'bg-muted-foreground', text: 'text-muted-foreground' },
  }[status];
  return (
    <span className={cn('inline-flex items-center gap-1 text-[10px] font-medium', cfg.text)} title={
      status === 'live' ? 'Live prices streaming' :
      status === 'delayed' ? 'Live prices delayed — showing last known values' :
      'Live prices paused — reconnect your broker to resume'
    }>
      <span className={cn('w-1.5 h-1.5 rounded-full', cfg.dot, status === 'live' && 'animate-pulse')} />
      {cfg.label}
    </span>
  );
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
      'font-tabular transition-colors duration-300',
      flash === 'up' && 'text-profit',
      flash === 'down' && 'text-loss',
      !flash && 'text-foreground',
    )}>
      {formatPrice(display)}
    </span>
  );
}

// Symbol capped, spacer takes the slack, figures cluster right. See
// ClosedPositionsCard for the reasoning.
const COLS = 'grid-cols-[minmax(150px,320px)_1fr_64px_92px_92px_78px_108px_40px]';

export default function OpenPositionsTable({
  positions, isLoading, journaledIds = new Set(), onPositionClick,
  pricesConnected, lastPriceAt, tokenExpired,
}: OpenPositionsTableProps) {
  const openPositions = positions.filter(p => p.status === 'open');

  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 5_000);
    return () => clearInterval(id);
  }, []);

  const priceStatus: 'live' | 'delayed' | 'paused' =
    tokenExpired ? 'paused'
    : pricesConnected && lastPriceAt != null && now - lastPriceAt < PRICE_STALE_MS ? 'live'
    : 'delayed';

  const getLivePnl = (p: PositionWithExtras) => {
    if (p.last_price) {
      const mult = (p as any).multiplier ?? 1;
      return (p.last_price - p.average_entry_price) * p.total_quantity * mult;
    }
    return p.unrealized_pnl;
  };
  const getChgPct = (p: PositionWithExtras) => {
    const ltp = p.last_price || p.average_entry_price;
    if (!p.average_entry_price) return 0;
    const diff = p.total_quantity >= 0 ? ltp - p.average_entry_price : p.average_entry_price - ltp;
    return (diff / p.average_entry_price) * 100;
  };

  const totalPnl = openPositions.reduce((s, p) => s + getLivePnl(p), 0);

  if (isLoading) {
    return (
      <section className="desk-card overflow-hidden">
        <div className="card-head"><div className="h-4 w-40 bg-muted animate-pulse rounded" /></div>
        <div className="p-5 space-y-3">{[1, 2].map(i => <div key={i} className="h-10 bg-muted animate-pulse rounded" />)}</div>
      </section>
    );
  }

  return (
    <section className="desk-card overflow-hidden">
      {/* Header */}
      <div className="px-4 sm:px-6 py-4 border-b border-border flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2.5 flex-wrap">
          <span className="text-[11px] uppercase tracking-[0.12em] font-medium text-muted-foreground">Open Positions</span>
          <span className="text-[11px] text-muted-foreground font-tabular">· {openPositions.length}</span>
          {openPositions.length > 0 && <PriceStatusPill status={priceStatus} />}
          {openPositions.length > 0 && (
            <span className="hidden sm:inline text-[10px] text-muted-foreground/70 uppercase tracking-wider">· tap a row to journal</span>
          )}
        </div>
        {openPositions.length > 0 && (
          <span className="flex items-baseline gap-1.5">
            <span className="text-[10px] uppercase tracking-wider text-muted-foreground">Unrealized</span>
            <span className={cn('text-sm font-semibold font-tabular', totalPnl >= 0 ? 'text-profit' : 'text-loss')}>
              {formatCurrencyWithSign(totalPnl)}
            </span>
          </span>
        )}
      </div>

      {openPositions.length > 0 ? (
        <>
          {/* Column header (desktop) */}
          <div className={cn('hidden sm:grid gap-3 px-4 sm:px-6 py-3 text-[10px] uppercase tracking-wider font-medium text-muted-foreground border-b border-border', COLS)}>
            <span>Symbol</span>
            <span aria-hidden />
            <span className="text-right">Qty</span>
            <span className="text-right">Entry</span>
            <span className="text-right">LTP</span>
            <span className="text-right">Chg%</span>
            <span className="text-right">P&amp;L</span>
            <span />
          </div>

          <div className="divide-y divide-border">
            {openPositions.map(pos => {
              const livePnl = getLivePnl(pos);
              const chgPct = getChgPct(pos);
              const qty = pos.total_quantity;
              const isBuy = qty >= 0;
              const isJournaled = journaledIds.has(positionJournalTradeId(pos.id));
              const { name, sub } = parseSymbol(pos.tradingsymbol, pos.instrument_type);
              return (
                <div
                  key={pos.id}
                  role="button"
                  tabIndex={0}
                  onClick={() => onPositionClick?.(pos)}
                  onKeyDown={e => (e.key === 'Enter' || e.key === ' ') && onPositionClick?.(pos)}
                  className="group cursor-pointer transition-colors hover:bg-muted/40 focus:outline-none focus:bg-muted/40"
                >
                  {/* Desktop row */}
                  <div className={cn('hidden sm:grid gap-3 px-4 sm:px-6 py-3.5 items-center', COLS)}>
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="text-sm font-medium text-foreground">{name}</span>
                      <span className={cn('text-[10px] font-semibold px-1.5 py-0.5 rounded', isBuy ? 'text-profit bg-profit/10' : 'text-loss bg-loss/10')}>
                        {isBuy ? 'BUY' : 'SELL'}
                      </span>
                      {sub && <span className="text-[11px] text-muted-foreground font-tabular truncate">{sub}</span>}
                      {isJournaled && <span title="Journalled" className="ml-1 h-1.5 w-1.5 rounded-full bg-primary" />}
                    </div>
                    <span aria-hidden />
                    <span className="text-right text-sm font-tabular text-muted-foreground">{formatNumber(Math.abs(qty))}</span>
                    <span className="text-right text-sm font-tabular text-muted-foreground">{formatPrice(pos.average_entry_price)}</span>
                    <span className="text-right text-sm font-tabular text-foreground">
                      <PriceCell symbol={pos.tradingsymbol} staticPrice={pos.last_price || pos.average_entry_price} livePrice={pos.last_price || undefined} />
                    </span>
                    <span className={cn('text-right text-sm font-tabular font-medium', chgPct >= 0 ? 'text-profit' : 'text-loss')}>
                      {chgPct >= 0 ? '+' : ''}{chgPct.toFixed(2)}%
                    </span>
                    <span className={cn('text-right text-sm font-semibold font-tabular', livePnl > 0 ? 'text-profit' : livePnl < 0 ? 'text-loss' : 'text-muted-foreground')}>
                      {formatCurrencyWithSign(livePnl)}
                    </span>
                    <span className="flex items-center justify-end gap-1 text-muted-foreground/60 group-hover:text-primary transition-colors">
                      {isJournaled ? <CheckCircle2 className="h-3.5 w-3.5 text-profit" /> : <NotebookPen className="h-3.5 w-3.5" />}
                      <ChevronRight className="h-3.5 w-3.5 opacity-0 group-hover:opacity-100 transition-opacity" />
                    </span>
                  </div>

                  {/* Mobile row */}
                  <div className="sm:hidden px-4 py-4">
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="text-sm font-medium text-foreground truncate">{name}</span>
                        <span className={cn('text-[10px] font-semibold px-1.5 py-0.5 rounded shrink-0', isBuy ? 'text-profit bg-profit/10' : 'text-loss bg-loss/10')}>
                          {isBuy ? 'BUY' : 'SELL'}
                        </span>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <span className={cn('text-sm font-semibold font-tabular', livePnl >= 0 ? 'text-profit' : 'text-loss')}>
                          {formatCurrencyWithSign(livePnl)}
                        </span>
                        <ChevronRight className="h-3.5 w-3.5 text-muted-foreground/50" />
                      </div>
                    </div>
                    <div className="flex items-center justify-between mt-2 text-[11px] text-muted-foreground font-tabular">
                      <span>{formatNumber(Math.abs(qty))} qty · Entry {formatPrice(pos.average_entry_price)} · LTP {formatPrice(pos.last_price || pos.average_entry_price)}</span>
                      <span className={cn('font-medium', chgPct >= 0 ? 'text-profit' : 'text-loss')}>{chgPct >= 0 ? '+' : ''}{chgPct.toFixed(2)}%</span>
                    </div>
                    <p className="text-[10.5px] text-primary mt-2 flex items-center gap-1">
                      <NotebookPen className="h-3 w-3" /> {isJournaled ? 'View note' : 'Add note'}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </>
      ) : (
        <div className="py-12 text-center">
          <Briefcase className="h-10 w-10 text-muted-foreground/40 mx-auto mb-3" />
          <p className="text-sm font-medium text-foreground">No active positions</p>
          <p className="text-[13px] text-muted-foreground mt-1">Positions will appear here when you trade</p>
        </div>
      )}
    </section>
  );
}

