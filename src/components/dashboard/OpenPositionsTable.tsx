import { useEffect, useRef, useState } from 'react';
import { Briefcase, Pencil, CheckCircle2 } from 'lucide-react';
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
// Treat prices as stale if none has arrived in this window.
const PRICE_STALE_MS = 20_000;

function PriceStatusPill({ status }: { status: 'live' | 'delayed' | 'paused' }) {
  const cfg = {
    live:    { label: 'Live',    dot: 'bg-tm-profit',        text: 'text-tm-profit' },
    delayed: { label: 'Delayed', dot: 'bg-tm-obs',           text: 'text-tm-obs' },
    paused:  { label: 'Paused',  dot: 'bg-muted-foreground',  text: 'text-muted-foreground' },
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

// Symbol parsing lives in @/lib/symbolParser (shared with ClosedTradesTable).

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
  pricesConnected, lastPriceAt, tokenExpired,
}: OpenPositionsTableProps) {
  const openPositions = positions.filter(p => p.status === 'open');

  // Re-evaluate freshness on a slow tick so 'live' flips to 'delayed' when ticks stop.
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
      // p.multiplier is Zerodha's contract multiplier:
      //   NSE/BSE F&O (NFO/BFO): multiplier=1 — Kite sends qty in units already
      //   MCX commodities: multiplier=lot_size (e.g. GOLDM=10, SILVERM=30, CRUDEOIL=100)
      const mult = (p as any).multiplier ?? 1;
      return (p.last_price - p.average_entry_price) * p.total_quantity * mult;
    }
    return p.unrealized_pnl;
  };

  const totalPnl = openPositions.reduce((s, p) => s + getLivePnl(p), 0);

  if (isLoading) {
    return (
      <div className="tm-card">
        <div className="px-5 py-3 border-b border-border">
          <div className="h-4 w-40 bg-muted animate-pulse rounded" />
        </div>
        {/* Mobile skeleton cards */}
        <div className="md:hidden flex gap-3 px-4 py-3 overflow-hidden">
          {[1, 2].map(i => <div key={i} className="h-24 w-40 flex-shrink-0 bg-muted animate-pulse rounded-xl" />)}
        </div>
        {/* Desktop skeleton rows */}
        <div className="hidden md:block p-5 space-y-3">
          {[1, 2].map(i => <div key={i} className="h-10 bg-muted animate-pulse rounded" />)}
        </div>
      </div>
    );
  }

  return (
    <div className="tm-card">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-border">
        <div className="flex items-center gap-2">
          <span className="tm-label">Open Positions</span>
          <span className="text-[11px] text-muted-foreground font-mono tabular-nums">
            {openPositions.length}
          </span>
          {openPositions.length > 0 && <PriceStatusPill status={priceStatus} />}
        </div>
        {openPositions.length > 0 && (
          <span className={cn(
            'text-sm font-semibold font-mono tabular-nums',
            totalPnl >= 0 ? 'text-tm-profit' : 'text-tm-loss',
          )}>
            {formatCurrencyWithSign(totalPnl)}
          </span>
        )}
      </div>

      {openPositions.length > 0 ? (
        <>
          {/* ── Mobile: horizontal scroll snap cards ─────────────────────── */}
          <div className="md:hidden overflow-x-auto [-webkit-overflow-scrolling:touch] scroll-smooth">
            <div className="flex gap-3 px-4 py-3 snap-x snap-mandatory">
              {openPositions.map((pos) => {
                const livePnl = getLivePnl(pos);
                const qty = pos.total_quantity;
                const isJournaled = journaledIds.has(positionJournalTradeId(pos.id));
                const { name, chip, sub } = parseSymbol(pos.tradingsymbol, pos.instrument_type);
                return (
                  <button
                    key={pos.id}
                    onClick={() => onPositionClick?.(pos)}
                    className={cn(
                      'flex-shrink-0 snap-start w-44 rounded-xl border text-left p-3.5',
                      'bg-card hover:bg-muted/60 transition-colors',
                      livePnl > 0 ? 'border-tm-profit/20' : livePnl < 0 ? 'border-tm-loss/20' : 'border-border',
                    )}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-1.5">
                        <span className="text-[13px] font-semibold text-foreground leading-none">{name}</span>
                        <span className={chipClass(chip)}>{chip}</span>
                      </div>
                      {isJournaled
                        ? <CheckCircle2 className="w-3.5 h-3.5 text-tm-profit" />
                        : <Pencil className="w-3.5 h-3.5 text-muted-foreground/50" />
                      }
                    </div>
                    {sub && (
                      <p className="text-[11px] text-muted-foreground font-mono tabular-nums mb-2">{sub}</p>
                    )}
                    <div className="space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="text-[10.5px] text-muted-foreground">
                          {qty > 0 ? 'BUY' : 'SELL'} {formatNumber(Math.abs(qty))}
                        </span>
                        <span className="text-[11px] font-mono tabular-nums text-muted-foreground">
                          avg {formatPrice(pos.average_entry_price)}
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-[10.5px] text-muted-foreground">LTP</span>
                        <PriceCell
                          symbol={pos.tradingsymbol}
                          staticPrice={pos.last_price || pos.average_entry_price}
                          livePrice={pos.last_price || undefined}
                        />
                      </div>
                      <div className={cn(
                        'text-[16px] font-black font-mono tabular-nums mt-1.5 leading-none',
                        livePnl > 0 ? 'text-tm-profit' : livePnl < 0 ? 'text-tm-loss' : 'text-muted-foreground',
                      )}>
                        {formatCurrencyWithSign(livePnl)}
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* ── Desktop: standard table ───────────────────────────────────── */}
          <table className="hidden md:table w-full">
            <thead>
              <tr className="border-b border-border">
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
                const qty = pos.total_quantity;
                const isJournaled = journaledIds.has(positionJournalTradeId(pos.id));
                const { name, chip, sub } = parseSymbol(pos.tradingsymbol, pos.instrument_type);
                return (
                  <tr key={pos.id} className={cn(
                    'transition-colors hover:bg-muted/60',
                    i < openPositions.length - 1 && 'border-b border-border/50',
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
                        livePrice={pos.last_price || undefined}
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
                        aria-label={isJournaled ? `View journal for ${pos.tradingsymbol}` : `Add journal entry for ${pos.tradingsymbol}`}
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
        </>
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
