import { useState } from 'react';
import { NotebookPen, ChevronRight, CheckCircle2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatPrice, formatCurrencyWithSign } from '@/lib/formatters';
import { parseSymbol } from '@/lib/symbolParser';
import type { CompletedTrade } from '@/types/api';

interface ClosedTradesTableProps {
  trades: CompletedTrade[];
  isLoading?: boolean;
  journaledIds?: Set<string>;
  onTradeClick?: (trade: CompletedTrade) => void;
}

function formatDuration(minutes: number): string {
  if (minutes <= 0) return '—';
  if (minutes < 60) return `${minutes}m`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (h < 24) return m > 0 ? `${h}h ${m}m` : `${h}h`;
  const d = Math.floor(h / 24);
  const rh = h % 24;
  return rh > 0 ? `${d}d ${rh}h` : `${d}d`;
}

function formatTime(dateStr: string): string {
  if (!dateStr) return '—';
  return new Date(dateStr).toLocaleTimeString('en-IN', {
    hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'Asia/Kolkata',
  });
}

const COLS = 'grid-cols-[1.4fr_56px_86px_86px_78px_74px_98px_36px]';

export default function ClosedTradesTable({
  trades, isLoading, journaledIds = new Set(), onTradeClick,
}: ClosedTradesTableProps) {
  const [showAll, setShowAll] = useState(false);

  const sorted = [...trades].sort((a, b) => {
    const aUnj = !journaledIds.has(a.id) ? 0 : 1;
    const bUnj = !journaledIds.has(b.id) ? 0 : 1;
    if (aUnj !== bUnj) return aUnj - bUnj;
    return new Date(b.exit_time).getTime() - new Date(a.exit_time).getTime();
  });

  const totalPnl = trades.reduce((sum, t) => sum + t.realized_pnl, 0);

  if (isLoading) {
    return (
      <section className="desk-card overflow-hidden">
        <div className="card-head"><div className="h-4 w-32 bg-muted animate-pulse rounded" /></div>
        <div className="p-5 space-y-3">{[1, 2, 3].map(i => <div key={i} className="h-10 bg-muted animate-pulse rounded" />)}</div>
      </section>
    );
  }

  if (!trades.length) {
    // The four SEBI/behavioural statistics that stood here were REMOVED
    // 2026-09-03. An external-source audit found no primary source for any of
    // them: SEBI publishes 93% for ALL individual F&O traders (FY22-FY24) and
    // 80% at >500 trades/YEAR — there is no ">7 trades/day" band, no
    // post-loss re-entry figure and no averaging-down figure in any located
    // publication, and the 2.7x is not SEBI at all (nearest real finding:
    // Odean 1998, US brokerage, ~1.5x). Removed here even though this
    // component currently has NO importer — "unreachable" is not a reason to
    // keep an invalid claim that becomes live the moment someone imports it.
    // Not replaced with other statistics.
    const capabilities = [
      { title: 'Every round, entry to exit', body: 'Each position is rebuilt from your fills — average entry, average exit, realised P&L.' },
      { title: 'Patterns in your own trades', body: 'Repeated entries, size after losses, adding to a position that has gone against you.' },
      { title: 'Your rules, your numbers', body: 'Limits you set yourself. Nothing is enforced until you write it down.' },
      { title: 'Facts, not forecasts', body: 'What happened and what it cost. TradeMentor does not predict your next trade.' },
    ];
    return (
      <section className="desk-card overflow-hidden">
        <div className="card-head">
          <span className="text-[11px] uppercase tracking-[0.12em] font-medium text-muted-foreground">Closed Positions</span>
        </div>
        <div className="px-5 sm:px-6 py-8">
          <p className="text-sm font-medium text-foreground mb-1">Waiting for your first trade</p>
          <p className="text-[13px] text-muted-foreground mb-5">
            Everything here is built from your own trades. Until you have some,
            there is nothing to show — and nothing worth claiming.
          </p>
          <div className="grid grid-cols-2 gap-3">
            {capabilities.map((it, i) => (
              <div key={i} className="p-3 rounded-lg bg-muted/50 border border-border">
                <p className="text-xs font-semibold text-foreground leading-snug">{it.title}</p>
                <p className="text-xs text-muted-foreground mt-1 leading-snug">{it.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>
    );
  }

  const visible = showAll ? sorted : sorted.slice(0, 6);

  return (
    <section className="desk-card overflow-hidden">
      {/* Header */}
      <div className="px-4 sm:px-6 py-4 border-b border-border flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2.5 flex-wrap">
          <span className="text-[11px] uppercase tracking-[0.12em] font-medium text-muted-foreground">Closed Positions</span>
          <span className="text-[11px] text-muted-foreground font-tabular">· {trades.length}</span>
          <span className="hidden sm:inline text-[10px] text-muted-foreground/70 uppercase tracking-wider">· tap a row to journal</span>
        </div>
        <span className="flex items-baseline gap-1.5">
          <span className="text-[10px] uppercase tracking-wider text-muted-foreground">Booked</span>
          <span className={cn('text-sm font-semibold font-tabular', totalPnl >= 0 ? 'text-profit' : 'text-loss')}>
            {formatCurrencyWithSign(totalPnl)}
          </span>
        </span>
      </div>

      {/* Column header (desktop) */}
      <div className={cn('hidden sm:grid gap-3 px-4 sm:px-6 py-3 text-[10px] uppercase tracking-wider font-medium text-muted-foreground border-b border-border', COLS)}>
        <span>Symbol</span>
        <span className="text-right">Qty</span>
        <span className="text-right">Entry</span>
        <span className="text-right">Exit</span>
        <span className="text-right">Hold</span>
        <span className="text-right">Chg%</span>
        <span className="text-right">P&amp;L</span>
        <span />
      </div>

      <div className="divide-y divide-border">
        {visible.map(trade => {
          const isBuy = trade.direction === 'LONG';
          const isJournaled = journaledIds.has(trade.id);
          const { name, sub: strike } = parseSymbol(trade.tradingsymbol);
          const holdMins = trade.entry_time && trade.exit_time
            ? Math.round((new Date(trade.exit_time).getTime() - new Date(trade.entry_time).getTime()) / 60000)
            : 0;
          const chgPct = trade.avg_entry_price
            ? ((isBuy ? trade.avg_exit_price - trade.avg_entry_price : trade.avg_entry_price - trade.avg_exit_price) / trade.avg_entry_price) * 100
            : 0;
          const pnl = trade.realized_pnl;

          return (
            <div
              key={trade.id}
              role="button"
              tabIndex={0}
              onClick={() => onTradeClick?.(trade)}
              onKeyDown={e => (e.key === 'Enter' || e.key === ' ') && onTradeClick?.(trade)}
              className="group cursor-pointer transition-colors hover:bg-muted/40 focus:outline-none focus:bg-muted/40"
            >
              {/* Desktop row */}
              <div className={cn('hidden sm:grid gap-3 px-4 sm:px-6 py-3.5 items-center', COLS)}>
                <div className="flex items-center gap-2 min-w-0">
                  <span className="text-sm font-medium text-foreground">{name}</span>
                  <span className={cn('text-[10px] font-semibold px-1.5 py-0.5 rounded', isBuy ? 'text-profit bg-profit/10' : 'text-loss bg-loss/10')}>
                    {isBuy ? 'BUY' : 'SELL'}
                  </span>
                  <span className="text-[11px] text-muted-foreground font-tabular truncate">{strike ? `${strike} · ` : ''}{formatTime(trade.exit_time)}</span>
                  {isJournaled && <span title="Journalled" className="ml-1 h-1.5 w-1.5 rounded-full bg-primary" />}
                </div>
                <span className="text-right text-sm font-tabular text-muted-foreground">{trade.total_quantity}</span>
                <span className="text-right text-sm font-tabular text-muted-foreground">{formatPrice(trade.avg_entry_price)}</span>
                <span className="text-right text-sm font-tabular text-foreground">{formatPrice(trade.avg_exit_price)}</span>
                <span className="text-right text-sm font-tabular text-muted-foreground">{formatDuration(holdMins)}</span>
                <span className={cn('text-right text-sm font-tabular font-medium', chgPct >= 0 ? 'text-profit' : 'text-loss')}>
                  {chgPct >= 0 ? '+' : ''}{chgPct.toFixed(2)}%
                </span>
                <span className={cn('text-right text-sm font-semibold font-tabular', pnl > 0 ? 'text-profit' : pnl < 0 ? 'text-loss' : 'text-muted-foreground')}>
                  {formatCurrencyWithSign(pnl)}
                </span>
                <span className="flex items-center justify-end text-muted-foreground/60 group-hover:text-primary transition-colors">
                  {isJournaled ? <CheckCircle2 className="h-3.5 w-3.5 text-profit" /> : <NotebookPen className="h-3.5 w-3.5" />}
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
                    <span className={cn('text-sm font-semibold font-tabular', pnl >= 0 ? 'text-profit' : 'text-loss')}>{formatCurrencyWithSign(pnl)}</span>
                    <ChevronRight className="h-3.5 w-3.5 text-muted-foreground/50" />
                  </div>
                </div>
                <div className="flex items-center justify-between mt-2 text-[11px] text-muted-foreground font-tabular">
                  <span>{trade.total_quantity} qty · Entry {formatPrice(trade.avg_entry_price)} · Exit {formatPrice(trade.avg_exit_price)} · {formatDuration(holdMins)}</span>
                  <span className={cn('font-medium', chgPct >= 0 ? 'text-profit' : 'text-loss')}>{chgPct >= 0 ? '+' : ''}{chgPct.toFixed(2)}%</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {sorted.length > 6 && (
        <button
          onClick={() => setShowAll(v => !v)}
          className="w-full px-6 py-2.5 border-t border-border text-[11px] font-medium text-primary hover:bg-muted/40 transition-colors uppercase tracking-wider"
        >
          {showAll ? 'Show less' : `View all ${sorted.length} trades`}
        </button>
      )}
    </section>
  );
}
