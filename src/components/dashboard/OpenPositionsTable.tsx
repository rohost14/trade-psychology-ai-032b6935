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

// Parse Zerodha tradingsymbol into display parts.
//
// Zerodha uses two different expiry formats depending on instrument type:
//
//   YYMMM  (2-digit year + 3-char month BEFORE strike)
//     → Index monthly options:  NIFTY25MAR23000CE, ICICIGI24JUN1640PE
//     → Weekly index:           NIFTY25415XXXXXCE (5-digit numeric expiry)
//
//   DDMMMYY (day + month + 2-digit year AFTER month, BEFORE strike)
//     → Stock options with specific-date or weekly expiry: ADANIPOWER26JUN242.5CE
//     → Strike can be decimal for low-priced stocks (2.5, 7.5, etc.)
//
// Disambiguation is needed because both share the \d{2}[A-Z]{3} prefix.
// Strategy: for non-index symbols, try DDMMMYY first with year-range validation (≥24).
// Index symbols (NIFTY/BANKNIFTY/etc.) never use DDMMMYY — skip straight to YYMMM.

const INDEX_PREFIXES = ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY', 'SENSEX', 'BANKEX'];

function fmtStrike(raw: string): string {
  const n = parseFloat(raw);
  return Number.isInteger(n)
    ? n.toLocaleString('en-IN')
    : n.toLocaleString('en-IN', { minimumFractionDigits: 1, maximumFractionDigits: 2 });
}

function parseSymbol(sym: string, instrType?: string): { name: string; chip: string; sub: string } {
  // ── Weekly index options: 5-digit numeric expiry ──────────────────────────
  // e.g. NIFTY2541524600CE, NIFTY25415100000CE
  const mw = sym.match(/^([A-Z]+)\d{5}(\d{5,6})(CE|PE)$/);
  if (mw) return { name: mw[1], chip: mw[3], sub: parseInt(mw[2], 10).toLocaleString('en-IN') };

  // ── Stock options with DDMMMYY expiry (specific date, decimal strikes OK) ─
  // e.g. ADANIPOWER26JUN242.5CE  →  DD=26, MON=JUN, YY=24, strike=2.5, type=CE
  // Skip for known index underlyings — they never use this format.
  const isIndex = INDEX_PREFIXES.some(p => sym.startsWith(p));
  if (!isIndex) {
    const mDD = sym.match(/^([A-Z]+)(\d{2})([A-Z]{3})(\d{2})(\d+(?:\.\d+)?)(CE|PE)$/);
    if (mDD) {
      const expYear = parseInt(mDD[4], 10);
      const strike  = parseFloat(mDD[5]);
      // expYear must be a plausible options year (2024–2040); strike must be positive.
      // This rejects cases where \d{2}[A-Z]{3}\d{2} accidentally captures two year-digits
      // from a YYMMM symbol (e.g. ICICIGI24JUN → year parsed as "16" < 24 → falls through).
      if (expYear >= 24 && expYear <= 40 && strike > 0) {
        return { name: mDD[1], chip: mDD[6], sub: fmtStrike(mDD[5]) };
      }
    }
  }

  // ── Monthly options: YYMMM expiry ─────────────────────────────────────────
  // e.g. NIFTY25MAR23000CE, ICICIGI24JUN1640PE, KALYANKJIL24JUN370CE
  const mm = sym.match(/^([A-Z]+)\d{2}[A-Z]{3}(\d{3,6})(CE|PE)$/);
  if (mm) return { name: mm[1], chip: mm[3], sub: parseInt(mm[2], 10).toLocaleString('en-IN') };

  // ── Futures ───────────────────────────────────────────────────────────────
  // e.g. NIFTY25MARFUT, BANKNIFTY25APR25FUT, CRUDEOIL25MARFUT
  const mf = sym.match(/^([A-Z0-9]+)(?:\d{5}|\d{2}[A-Z]{3}(?:\d{2})?)FUT$/);
  if (mf) return { name: mf[1], chip: 'FUT', sub: '' };

  // ── Equity / unknown fallback ─────────────────────────────────────────────
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
  }, [openPositions, isConnected, subscribe]);

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
