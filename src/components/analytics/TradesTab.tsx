import { useState, useEffect, useMemo } from 'react';
import { Skeleton } from '@/components/ui/skeleton';
import {
  TrendingDown, Search, X, AlertTriangle,
  ChevronDown, ChevronUp, ArrowUpDown,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatCurrencyWithSign, formatCurrency } from '@/lib/formatters';
import { api } from '@/lib/api';
import type { CompletedTrade } from '@/types/api';

// ─── Helpers ──────────────────────────────────────────────────────────────────

function parseSymbol(sym: string): { name: string; chip: string; sub: string } {
  const m5 = sym.match(/^([A-Z]+)\d{5}(\d{5})(CE|PE)$/);
  if (m5) return { name: m5[1], chip: m5[3], sub: parseInt(m5[2], 10).toLocaleString('en-IN') };
  const m6 = sym.match(/^([A-Z]+)\d{5}(\d{6})(CE|PE)$/);
  if (m6) return { name: m6[1], chip: m6[3], sub: parseInt(m6[2], 10).toLocaleString('en-IN') };
  return { name: sym, chip: 'EQ', sub: '' };
}

function chipClass(chip: string) {
  if (chip === 'CE') return 'tm-chip tm-chip-ce';
  if (chip === 'PE') return 'tm-chip tm-chip-pe';
  return 'tm-chip tm-chip-eq';
}

function formatDuration(minutes: number | null): string {
  if (!minutes) return '—';
  if (minutes < 60) return `${minutes}m`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (h < 24) return m > 0 ? `${h}h ${m}m` : `${h}h`;
  return `${Math.floor(h / 24)}d`;
}

function formatExitTime(isoStr: string): { date: string; time: string } {
  const d = new Date(isoStr);
  return {
    date: d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' }),
    time: d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false }),
  };
}

// ─── Types ────────────────────────────────────────────────────────────────────

interface FlagReason {
  type: string;
  label: string;
}

const FLAG_COLORS: Record<string, string> = {
  large_loss:       'text-tm-loss bg-red-50 dark:bg-red-900/15 border-red-200 dark:border-red-800/30',
  behavioral_alert: 'text-tm-obs bg-amber-50 dark:bg-amber-900/15 border-amber-200 dark:border-amber-800/30',
  oversized:        'text-purple-600 bg-purple-50 dark:bg-purple-900/15 border-purple-200 dark:border-purple-800/30',
  quick_reentry:    'text-tm-obs bg-amber-50 dark:bg-amber-900/15 border-amber-200 dark:border-amber-800/30',
};

type DirFilter = 'all' | 'LONG' | 'SHORT';
type SortKey = 'date' | 'pnl' | 'duration';
type SortDir = 'asc' | 'desc';

const PAGE_SIZE = 50;

// ─── Expanded Detail Row ──────────────────────────────────────────────────────

function TradeDetail({ trade }: { trade: CompletedTrade }) {
  return (
    <div className="px-4 pb-3 pt-1 flex flex-wrap gap-x-6 gap-y-1 bg-slate-50/80 dark:bg-neutral-800/20 border-t border-border/50 text-[11px] text-muted-foreground font-mono">
      <span>Entry <span className="text-foreground tabular-nums">₹{trade.avg_entry_price.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span></span>
      <span>Exit <span className="text-foreground tabular-nums">₹{trade.avg_exit_price.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span></span>
      <span>Qty <span className="text-foreground tabular-nums">{trade.total_quantity}</span></span>
      {trade.product && <span>Product <span className="text-foreground uppercase">{trade.product}</span></span>}
      {trade.num_entries > 1 && <span>Entries <span className="text-foreground">{trade.num_entries}</span></span>}
      {trade.num_exits > 1 && <span>Exits <span className="text-foreground">{trade.num_exits}</span></span>}
      <span>Hold <span className="text-foreground">{formatDuration(trade.duration_minutes)}</span></span>
    </div>
  );
}

// ─── Sort Header Button ───────────────────────────────────────────────────────

function SortBtn({
  label, sortKey, current, dir, onSort,
}: {
  label: string; sortKey: SortKey; current: SortKey; dir: SortDir;
  onSort: (k: SortKey) => void;
}) {
  const active = current === sortKey;
  return (
    <button
      onClick={() => onSort(sortKey)}
      className={cn(
        'flex items-center gap-1 text-[11px] font-medium transition-colors',
        active ? 'text-foreground' : 'text-muted-foreground hover:text-foreground'
      )}
    >
      {label}
      {active
        ? (dir === 'desc' ? <ChevronDown className="h-3 w-3" /> : <ChevronUp className="h-3 w-3" />)
        : <ArrowUpDown className="h-3 w-3 opacity-40" />
      }
    </button>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function TradesTab({ days }: { days: number }) {
  const [trades, setTrades]         = useState<CompletedTrade[]>([]);
  const [total, setTotal]           = useState(0);
  const [offset, setOffset]         = useState(0);
  const [loadingMore, setLoadingMore] = useState(false);
  const [flagMap, setFlagMap]       = useState<Map<string, FlagReason[]>>(new Map());
  const [qualityMap, setQualityMap] = useState<Map<string, { score: number; tier: string }>>(new Map());
  const [isLoading, setIsLoading]   = useState(true);
  const [expanded, setExpanded]     = useState<Set<string>>(new Set());
  const [dirFilter, setDirFilter]   = useState<DirFilter>('all');
  const [tradeFilter, setTradeFilter] = useState<'all' | 'clean' | 'flagged'>('all');
  const [search, setSearch]         = useState('');
  const [sortKey, setSortKey]       = useState<SortKey>('date');
  const [sortDir, setSortDir]       = useState<SortDir>('desc');

  const cutoff = useMemo(
    () => new Date(Date.now() - days * 86_400_000),
    [days]
  );

  // Initial load
  useEffect(() => {
    let cancelled = false;
    setOffset(0);
    setTrades([]);
    setExpanded(new Set());

    const load = async () => {
      setIsLoading(true);
      const [tradesRes, criticalRes, qualityRes] = await Promise.allSettled([
        api.get('/api/trades/completed', { params: { limit: PAGE_SIZE, offset: 0 } }),
        api.get('/api/analytics/critical-trades', { params: { days } }),
        api.get('/api/analytics/quality-breakdown', { params: { days } }),
      ]);
      if (cancelled) return;

      const map = new Map<string, FlagReason[]>();
      if (criticalRes.status === 'fulfilled') {
        for (const ct of (criticalRes.value.data.trades ?? [])) {
          map.set(ct.id, ct.reasons ?? []);
        }
      }

      const qmap = new Map<string, { score: number; tier: string }>();
      if (qualityRes.status === 'fulfilled') {
        for (const qt of (qualityRes.value.data.per_trade ?? [])) {
          qmap.set(qt.trade_id, { score: qt.score, tier: qt.tier });
        }
      }

      if (tradesRes.status === 'fulfilled') {
        const all: CompletedTrade[] = tradesRes.value.data.trades ?? [];
        const inPeriod = all.filter((t) => t.exit_time && new Date(t.exit_time) >= cutoff);
        setTrades(inPeriod);
        setTotal(tradesRes.value.data.total ?? 0);
        setOffset(PAGE_SIZE);
      }
      setFlagMap(map);
      setQualityMap(qmap);
      setIsLoading(false);
    };
    load();
    return () => { cancelled = true; };
  }, [days]);

  const loadMore = async () => {
    setLoadingMore(true);
    try {
      const res = await api.get('/api/trades/completed', {
        params: { limit: PAGE_SIZE, offset },
      });
      const more: CompletedTrade[] = (res.data.trades ?? []).filter(
        (t: CompletedTrade) => t.exit_time && new Date(t.exit_time) >= cutoff
      );
      setTrades((prev) => [...prev, ...more]);
      setOffset((o) => o + PAGE_SIZE);
    } finally {
      setLoadingMore(false);
    }
  };

  const handleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir((d) => (d === 'desc' ? 'asc' : 'desc'));
    else { setSortKey(key); setSortDir('desc'); }
  };

  const toggleExpand = (id: string) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  const filtered = useMemo(() => {
    let list = trades;
    if (dirFilter !== 'all') list = list.filter((t) => t.direction === dirFilter);
    if (tradeFilter === 'flagged') list = list.filter((t) => (flagMap.get(t.id) ?? []).length > 0);
    if (tradeFilter === 'clean')   list = list.filter((t) => (flagMap.get(t.id) ?? []).length === 0);
    if (search.trim()) {
      const q = search.trim().toUpperCase();
      list = list.filter((t) => t.tradingsymbol.includes(q));
    }
    // Sort
    list = [...list].sort((a, b) => {
      let diff = 0;
      if (sortKey === 'date')     diff = new Date(a.exit_time).getTime() - new Date(b.exit_time).getTime();
      if (sortKey === 'pnl')      diff = a.realized_pnl - b.realized_pnl;
      if (sortKey === 'duration') diff = (a.duration_minutes ?? 0) - (b.duration_minutes ?? 0);
      return sortDir === 'desc' ? -diff : diff;
    });
    return list;
  }, [trades, dirFilter, tradeFilter, flagMap, search, sortKey, sortDir]);

  // Stats (always from full `trades` list, not filtered)
  const winners  = trades.filter((t) => t.realized_pnl > 0).length;
  const losers   = trades.filter((t) => t.realized_pnl < 0).length;
  const winRate  = trades.length > 0 ? Math.round((winners / trades.length) * 100) : 0;
  const totalPnl = trades.reduce((s, t) => s + t.realized_pnl, 0);
  const flagCount = trades.filter((t) => flagMap.has(t.id)).length;
  const hasMore = offset < total;

  if (isLoading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-14 rounded-xl" />
        <Skeleton className="h-10 rounded-xl" />
        {[1,2,3,4,5,6].map(i => <Skeleton key={i} className="h-14 rounded-xl" />)}
      </div>
    );
  }

  if (trades.length === 0) {
    return (
      <div className="tm-card flex flex-col items-center justify-center py-16 text-center">
        <TrendingDown className="h-10 w-10 text-muted-foreground/30 mb-3" />
        <p className="font-medium text-foreground">No completed trades in this period</p>
        <p className="text-sm text-muted-foreground mt-1">Trade and close positions to see your log here</p>
      </div>
    );
  }

  return (
    <div className="space-y-4 animate-fade-in">

      {/* Summary strip */}
      <div className="tm-card px-5 py-3 flex items-center gap-4 flex-wrap text-[13px]">
        <span className="font-mono tabular-nums font-medium text-foreground">{trades.length} trades</span>
        <span className="text-muted-foreground/40">·</span>
        <span className="text-tm-profit font-mono tabular-nums">{winners}W</span>
        <span className="text-muted-foreground/40">/</span>
        <span className="text-tm-loss font-mono tabular-nums">{losers}L</span>
        <span className="text-muted-foreground/40">·</span>
        <span className="text-muted-foreground">{winRate}% WR</span>
        <span className="text-muted-foreground/40">·</span>
        <span className={cn('font-mono tabular-nums font-medium', totalPnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
          {formatCurrencyWithSign(totalPnl)}
        </span>
        {flagCount > 0 && (
          <>
            <span className="text-muted-foreground/40">·</span>
            <span className="text-tm-obs text-[12px]">{flagCount} flagged</span>
          </>
        )}
      </div>

      {/* Filter + sort bar */}
      <div className="flex items-center gap-2 flex-wrap">
        {/* Symbol search */}
        <div className="relative flex-1 min-w-[140px] max-w-[200px]">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground pointer-events-none" />
          <input
            type="text"
            placeholder="Symbol…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-8 pr-7 py-1.5 text-[12px] bg-slate-100 dark:bg-neutral-700/50 rounded-lg border-0 outline-none focus:ring-1 focus:ring-tm-brand/40 text-foreground placeholder:text-muted-foreground"
          />
          {search && (
            <button onClick={() => setSearch('')} className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
              <X className="h-3 w-3" />
            </button>
          )}
        </div>

        {/* Direction filter */}
        <div className="flex items-center gap-1 p-1 bg-slate-100 dark:bg-neutral-700/50 rounded-lg">
          {(['all', 'LONG', 'SHORT'] as const).map((d) => (
            <button
              key={d}
              onClick={() => setDirFilter(d)}
              className={cn(
                'px-2.5 py-1 text-[11px] font-medium rounded-md transition-all',
                dirFilter === d
                  ? 'bg-white dark:bg-neutral-800 text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              )}
            >
              {d === 'all' ? 'All' : d === 'LONG' ? 'Long' : 'Short'}
            </button>
          ))}
        </div>

        {/* All / Clean / Flagged toggle */}
        <div className="flex items-center gap-1 p-1 bg-slate-100 dark:bg-neutral-700/50 rounded-lg">
          {(['all', 'clean', 'flagged'] as const).map((f) => (
            <button
              key={f}
              onClick={() => setTradeFilter(f)}
              className={cn(
                'px-2.5 py-1 text-[11px] font-medium rounded-md transition-all capitalize',
                tradeFilter === f
                  ? f === 'flagged'
                    ? 'bg-amber-50 dark:bg-amber-900/30 text-tm-obs shadow-sm'
                    : 'bg-white dark:bg-neutral-800 text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              )}
            >
              {f === 'flagged' ? `Flagged${flagCount > 0 ? ` (${flagCount})` : ''}` : f === 'clean' ? 'Clean' : 'All'}
            </button>
          ))}
        </div>

        {/* Sort — pushed to right */}
        <div className="ml-auto flex items-center gap-3 px-3 py-1.5 bg-slate-100 dark:bg-neutral-700/50 rounded-lg">
          <SortBtn label="Date"     sortKey="date"     current={sortKey} dir={sortDir} onSort={handleSort} />
          <SortBtn label="P&L"      sortKey="pnl"      current={sortKey} dir={sortDir} onSort={handleSort} />
          <SortBtn label="Hold"     sortKey="duration" current={sortKey} dir={sortDir} onSort={handleSort} />
        </div>
      </div>

      {/* Trade list */}
      <div className="tm-card overflow-hidden divide-y divide-border">
        {/* Column header */}
        <div className="px-4 py-2 bg-slate-50 dark:bg-neutral-800/30 flex items-center gap-3 text-[11px] text-muted-foreground">
          <span className="flex-1">Symbol</span>
          <span className="hidden sm:block w-28 text-right">Date · Hold</span>
          <span className="w-24 text-right">P&L</span>
          <span className="w-4" />
        </div>

        {filtered.length === 0 ? (
          <div className="py-10 text-center text-sm text-muted-foreground">No trades match this filter</div>
        ) : (
          filtered.map((trade) => {
            const flags = flagMap.get(trade.id) ?? [];
            const isFlagged = flags.length > 0;
            const quality = qualityMap.get(trade.id);
            const isOpen = expanded.has(trade.id);
            const { name, chip, sub } = parseSymbol(trade.tradingsymbol);
            const { date, time } = formatExitTime(trade.exit_time);

            return (
              <div key={trade.id} className={cn(isFlagged && 'border-l-2 border-l-tm-obs')}>
                {/* Main row */}
                <button
                  onClick={() => toggleExpand(trade.id)}
                  className="w-full px-4 py-3 flex items-center gap-3 hover:bg-slate-50 dark:hover:bg-slate-800/30 transition-colors text-left"
                >
                  {/* Symbol */}
                  <div className="flex items-center gap-1.5 min-w-0 flex-1">
                    <span className={chipClass(chip)}>{chip}</span>
                    <span className="text-[13px] font-medium text-foreground truncate">{name}</span>
                    {sub && <span className="text-[11px] text-muted-foreground hidden sm:inline shrink-0">{sub}</span>}
                    <span className={cn(
                      'text-[10px] font-bold px-1.5 py-0.5 rounded shrink-0',
                      trade.direction === 'LONG'
                        ? 'bg-green-50 dark:bg-green-900/20 text-tm-profit'
                        : 'bg-red-50 dark:bg-red-900/20 text-tm-loss'
                    )}>
                      {trade.direction === 'LONG' ? 'L' : 'S'}
                    </span>
                    {isFlagged && (
                      <AlertTriangle className="h-3 w-3 text-tm-obs shrink-0 hidden sm:block" />
                    )}
                    {quality && (
                      <span className={cn(
                        'text-[10px] font-bold font-mono px-1.5 py-0.5 rounded shrink-0 hidden sm:inline',
                        quality.tier === 'high' && 'bg-green-50 dark:bg-green-900/20 text-tm-profit',
                        quality.tier === 'mid'  && 'bg-amber-50 dark:bg-amber-900/20 text-tm-obs',
                        quality.tier === 'low'  && 'bg-red-50 dark:bg-red-900/20 text-tm-loss',
                      )}>
                        Q{quality.score}
                      </span>
                    )}
                  </div>

                  {/* Date + duration */}
                  <div className="text-right hidden sm:block w-28 shrink-0">
                    <p className="text-[11px] text-foreground">{date}</p>
                    <p className="text-[10px] text-muted-foreground">{time} · {formatDuration(trade.duration_minutes)}</p>
                  </div>

                  {/* P&L */}
                  <span className={cn(
                    'text-[14px] font-mono tabular-nums font-semibold w-24 text-right shrink-0',
                    trade.realized_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss'
                  )}>
                    {formatCurrencyWithSign(trade.realized_pnl)}
                  </span>

                  {/* Expand chevron */}
                  <ChevronDown className={cn(
                    'h-3.5 w-3.5 text-muted-foreground/40 shrink-0 transition-transform duration-150',
                    isOpen && 'rotate-180'
                  )} />
                </button>

                {/* Expanded detail */}
                {isOpen && (
                  <>
                    <TradeDetail trade={trade} />
                    {/* Flag chips in expanded area */}
                    {isFlagged && (
                      <div className="flex flex-wrap gap-1 px-4 pb-3 bg-slate-50/80 dark:bg-neutral-800/20">
                        {flags.map((f, i) => (
                          <span
                            key={i}
                            className={cn(
                              'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium border',
                              FLAG_COLORS[f.type] ?? 'text-muted-foreground bg-muted border-border'
                            )}
                          >
                            <AlertTriangle className="h-2.5 w-2.5" />
                            {f.label}
                          </span>
                        ))}
                      </div>
                    )}
                  </>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Load more */}
      {hasMore && (
        <div className="text-center">
          <button
            onClick={loadMore}
            disabled={loadingMore}
            className="px-5 py-2 text-[12px] font-medium text-muted-foreground hover:text-foreground border border-border hover:border-foreground rounded-lg transition-colors disabled:opacity-50"
          >
            {loadingMore ? 'Loading…' : `Load more (${total - trades.length} remaining)`}
          </button>
        </div>
      )}
    </div>
  );
}
