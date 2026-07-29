import { useState, useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { Link2, BookOpen, ChevronDown, ChevronUp } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import ErrorState from '@/components/ErrorState';
import { cn } from '@/lib/utils';
import { api } from '@/lib/api';
import { useBroker } from '@/contexts/BrokerContext';

// ── Types ─────────────────────────────────────────────────────────────────────
interface JournalEntry {
  id: string;
  trade_id: string | null;
  emotion_tags: string[];
  followed_plan: string | null;
  deviation_reason: string | null;
  exit_reason: string | null;
  setup_quality: number | null;
  would_repeat: string | null;
  market_condition: string | null;
  notes: string | null;
  trade_symbol: string | null;
  trade_type: string | null;
  trade_pnl: string | null;
  entry_type: string;
  created_at: string;
  updated_at: string;
}

// ── Display maps ──────────────────────────────────────────────────────────────
const EMOTION_LABELS: Record<string, string> = {
  calm: 'Calm', fomo: 'FOMO', revenge: 'Revenge',
  anxious: 'Anxious', overconfident: 'Overconfident',
};
const EMOTION_COLORS: Record<string, string> = {
  calm: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-900/20 dark:text-emerald-400',
  fomo: 'bg-amber-50 text-amber-700 dark:bg-amber-900/20 dark:text-amber-400',
  revenge: 'bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-400',
  anxious: 'bg-orange-50 text-orange-700 dark:bg-orange-900/20 dark:text-orange-400',
  overconfident: 'bg-purple-50 text-purple-700 dark:bg-purple-900/20 dark:text-purple-400',
};
const PLAN_LABELS: Record<string, string> = {
  yes: 'Followed plan', partially: 'Partial', no: 'Deviated',
};
const PLAN_COLORS: Record<string, string> = {
  yes: 'text-tm-profit', partially: 'text-tm-obs', no: 'text-tm-loss',
};
const EXIT_LABELS: Record<string, string> = {
  sl_hit: 'SL hit', target_hit: 'Target hit', trailed_stop: 'Trailed stop',
  manual: 'Manual', panic: 'Panic exit', news: 'News event',
};
const REPEAT_LABELS: Record<string, string> = { yes: 'Would repeat', maybe: 'Maybe', no: "Won't repeat" };
const REPEAT_COLORS: Record<string, string> = { yes: 'text-tm-profit', maybe: 'text-tm-obs', no: 'text-tm-loss' };
const CONDITION_LABELS: Record<string, string> = {
  trending: 'Trending', ranging: 'Ranging', volatile: 'Volatile',
  choppy: 'Choppy', news_driven: 'News-driven',
};
const PERIOD_OPTIONS = [
  { label: '7d',  days: 7 },
  { label: '30d', days: 30 },
  { label: '90d', days: 90 },
  { label: 'All', days: 0 },
];
const EMOTION_FILTERS = ['calm', 'fomo', 'revenge', 'anxious', 'overconfident'];
const PLAN_FILTERS = [
  { value: 'yes', label: 'Followed plan' },
  { value: 'partially', label: 'Partial' },
  { value: 'no', label: 'Deviated' },
];

// ── Helpers ───────────────────────────────────────────────────────────────────
function parsePnl(raw: string | null): number | null {
  if (!raw) return null;
  const n = parseFloat(raw.replace(/[₹,]/g, ''));
  return isNaN(n) ? null : n;
}

function fmtPnl(raw: string | null): string {
  const n = parsePnl(raw);
  if (n === null) return '—';
  const abs = Math.abs(n).toLocaleString('en-IN', { maximumFractionDigits: 0 });
  return `${n >= 0 ? '+' : '−'}₹${abs}`;
}

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  const hrs = Math.floor(mins / 60);
  const days = Math.floor(hrs / 24);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  if (hrs < 24) return `${hrs}h ago`;
  if (days < 7) return `${days}d ago`;
  return new Date(dateStr).toLocaleDateString('en-IN', {
    month: 'short', day: 'numeric', timeZone: 'Asia/Kolkata',
  });
}

function fmtDate(dateStr: string): string {
  return new Date(dateStr).toLocaleString('en-IN', {
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
    timeZone: 'Asia/Kolkata',
  });
}

// ── Entry card ────────────────────────────────────────────────────────────────
function EntryCard({ entry }: { entry: JournalEntry }) {
  const [expanded, setExpanded] = useState(false);
  const pnl = parsePnl(entry.trade_pnl);
  const pnlStr = fmtPnl(entry.trade_pnl);
  const hasNotes = !!entry.notes?.trim();
  const hasExtra = !!(entry.market_condition || entry.setup_quality || entry.would_repeat || entry.deviation_reason);

  return (
    <div className="tm-card overflow-hidden">
      {/* Main row */}
      <button
        type="button"
        onClick={() => (hasNotes || hasExtra) && setExpanded(e => !e)}
        className={cn(
          'w-full text-left px-5 py-3.5 flex items-start gap-3',
          (hasNotes || hasExtra) && 'hover:bg-muted/40 transition-colors',
        )}
        aria-expanded={expanded}
      >
        {/* Symbol + P&L */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1.5">
            {entry.trade_symbol && (
              <span className="text-[13px] font-semibold font-mono text-foreground">
                {entry.trade_symbol}
              </span>
            )}
            {pnl !== null && (
              <span className={cn(
                'text-[12px] font-mono tabular-nums font-semibold',
                pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss',
              )}>
                {pnlStr}
              </span>
            )}
          </div>

          {/* Tags row */}
          <div className="flex flex-wrap items-center gap-1.5">
            {entry.emotion_tags.map(tag => (
              <span key={tag} className={cn(
                'text-[11px] font-medium px-1.5 py-0.5 rounded',
                EMOTION_COLORS[tag] ?? 'bg-muted text-muted-foreground',
              )}>
                {EMOTION_LABELS[tag] ?? tag}
              </span>
            ))}
            {entry.followed_plan && (
              <span className={cn('text-[11px] font-medium', PLAN_COLORS[entry.followed_plan])}>
                · {PLAN_LABELS[entry.followed_plan]}
              </span>
            )}
            {entry.exit_reason && (
              <span className="text-[11px] text-muted-foreground">
                · {EXIT_LABELS[entry.exit_reason] ?? entry.exit_reason}
              </span>
            )}
          </div>

          {/* Notes preview — only when collapsed */}
          {hasNotes && !expanded && (
            <p className="text-[11px] text-muted-foreground mt-1 truncate max-w-xs">
              {entry.notes}
            </p>
          )}
        </div>

        {/* Date + expand indicator */}
        <div className="flex-shrink-0 flex flex-col items-end gap-1">
          <span className="text-[11px] text-muted-foreground">{timeAgo(entry.created_at)}</span>
          {(hasNotes || hasExtra) && (
            expanded
              ? <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" />
              : <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
          )}
        </div>
      </button>

      {/* Expanded details */}
      {expanded && (
        <div className="px-5 pb-4 border-t border-border pt-3 space-y-3">
          {/* Notes */}
          {hasNotes && (
            <p className="text-[13px] text-foreground leading-relaxed">{entry.notes}</p>
          )}

          {/* Extra fields grid */}
          {hasExtra && (
            <div className="grid grid-cols-2 gap-x-6 gap-y-1.5">
              {entry.would_repeat && (
                <div>
                  <span className="text-[10px] text-muted-foreground uppercase tracking-wide">Would repeat</span>
                  <p className={cn('text-[12px] font-medium', REPEAT_COLORS[entry.would_repeat])}>
                    {REPEAT_LABELS[entry.would_repeat]}
                  </p>
                </div>
              )}
              {entry.market_condition && (
                <div>
                  <span className="text-[10px] text-muted-foreground uppercase tracking-wide">Market</span>
                  <p className="text-[12px] font-medium text-foreground">
                    {CONDITION_LABELS[entry.market_condition] ?? entry.market_condition}
                  </p>
                </div>
              )}
              {entry.setup_quality && (
                <div>
                  <span className="text-[10px] text-muted-foreground uppercase tracking-wide">Setup quality</span>
                  <p className="text-[12px] font-medium text-foreground">
                    {'★'.repeat(entry.setup_quality)}{'☆'.repeat(5 - entry.setup_quality)}
                  </p>
                </div>
              )}
              {entry.deviation_reason && (
                <div>
                  <span className="text-[10px] text-muted-foreground uppercase tracking-wide">Deviated because</span>
                  <p className="text-[12px] font-medium text-foreground capitalize">
                    {entry.deviation_reason.replace(/_/g, ' ')}
                  </p>
                </div>
              )}
            </div>
          )}

          <p className="text-[10px] text-muted-foreground">{fmtDate(entry.created_at)}</p>
        </div>
      )}
    </div>
  );
}

// ── Skeleton loader ───────────────────────────────────────────────────────────
function EntrySkeleton() {
  return (
    <div className="tm-card px-5 py-3.5 space-y-2">
      <div className="flex items-center gap-2">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-4 w-16" />
      </div>
      <div className="flex gap-1.5">
        <Skeleton className="h-5 w-14 rounded" />
        <Skeleton className="h-5 w-20 rounded" />
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
const PAGE_SIZE = 50;

export default function Journal() {
  const { isConnected, isLoading: brokerLoading, account } = useBroker();

  const [entries, setEntries]       = useState<JournalEntry[]>([]);
  const [loading, setLoading]       = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError]           = useState<unknown>(null);
  const [hasMore, setHasMore]       = useState(false);
  const [offset, setOffset]         = useState(0);

  // Filters
  const [period, setPeriod]         = useState(30);
  const [emotionFilter, setEmotionFilter] = useState<string[]>([]);
  const [planFilter, setPlanFilter] = useState('');

  const fetchEntries = async (reset = false) => {
    if (!account?.id) return;
    const currentOffset = reset ? 0 : offset;
    if (reset) { setLoading(true); setError(null); }
    else setLoadingMore(true);

    try {
      const res = await api.get('/api/journal/', {
        params: { limit: PAGE_SIZE, offset: currentOffset },
      });
      const fetched: JournalEntry[] = res.data.entries ?? [];
      setEntries(prev => reset ? fetched : [...prev, ...fetched]);
      setHasMore(fetched.length === PAGE_SIZE);
      setOffset(currentOffset + fetched.length);
    } catch (e) {
      if (reset) setError(e);   // don't fake "no entries" on a failed load
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  };

  useEffect(() => {
    if (account?.id) fetchEntries(true);
  }, [account?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  // Client-side filter
  const filtered = useMemo(() => {
    const cutoff = period > 0
      ? Date.now() - period * 24 * 60 * 60 * 1000
      : 0;

    return entries.filter(e => {
      if (period > 0 && new Date(e.created_at).getTime() < cutoff) return false;
      if (emotionFilter.length > 0 && !emotionFilter.some(f => e.emotion_tags.includes(f))) return false;
      if (planFilter && e.followed_plan !== planFilter) return false;
      return true;
    });
  }, [entries, period, emotionFilter, planFilter]);

  // Emotion filter toggle
  const toggleEmotion = (e: string) =>
    setEmotionFilter(prev => prev.includes(e) ? prev.filter(x => x !== e) : [...prev, e]);

  // Stats bar
  const stats = useMemo(() => {
    if (filtered.length === 0) return null;
    const withPnl = filtered.filter(e => parsePnl(e.trade_pnl) !== null);
    const total = withPnl.reduce((s, e) => s + (parsePnl(e.trade_pnl) ?? 0), 0);
    const followed = filtered.filter(e => e.followed_plan === 'yes').length;
    const topEmotion = (() => {
      const counts: Record<string, number> = {};
      for (const e of filtered) {
        for (const tag of e.emotion_tags) counts[tag] = (counts[tag] ?? 0) + 1;
      }
      return Object.entries(counts).sort((a, b) => b[1] - a[1])[0]?.[0] ?? null;
    })();
    return { total, followed, topEmotion, count: filtered.length };
  }, [filtered]);

  if (brokerLoading) {
    return (
      <div className="w-full space-y-4 pb-12">
        <Skeleton className="h-8 w-36" />
        <Skeleton className="h-12 w-full" />
        {[1, 2, 3].map(i => <EntrySkeleton key={i} />)}
      </div>
    );
  }

  if (!isConnected) {
    return (
      <div className="w-full pb-12">
        <div className="mb-5">
          <h1 className="t-heading-lg text-foreground">Journal</h1>
        </div>
        <div className="tm-card flex flex-col items-center justify-center min-h-[50vh] text-center py-16">
          <div className="p-4 rounded-full bg-teal-50 dark:bg-teal-900/20 mb-5">
            <Link2 className="h-10 w-10 text-tm-brand" />
          </div>
          <h2 className="text-base font-semibold text-foreground mb-1">Connect Your Broker</h2>
          <p className="text-sm text-muted-foreground max-w-sm mb-5">
            Connect your Zerodha account to see your trade journal.
          </p>
          <Link to="/settings">
            <Button size="sm" className="gap-2 bg-tm-brand hover:bg-tm-brand/90 text-white">
              <Link2 className="h-4 w-4" />
              Connect Zerodha
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full pb-12">
      {/* Header */}
      <div className="mb-5 flex items-center justify-between">
        <div>
          <h1 className="t-heading-lg text-foreground">Journal</h1>
          {!loading && (
            <p className="text-[13px] text-muted-foreground mt-0.5">
              {entries.length} {entries.length === 1 ? 'entry' : 'entries'} total
            </p>
          )}
        </div>
      </div>

      {/* Stats bar */}
      {!loading && stats && (
        <div className="grid grid-cols-3 gap-3 mb-5">
          <div className="tm-card px-4 py-3 text-center">
            <div className={cn(
              'text-[17px] font-bold font-mono tabular-nums',
              stats.total >= 0 ? 'text-tm-profit' : 'text-tm-loss',
            )}>
              {stats.total >= 0 ? '+' : '−'}₹{Math.abs(stats.total).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
            </div>
            <div className="text-[10px] text-muted-foreground mt-0.5">P&L (journaled)</div>
          </div>
          <div className="tm-card px-4 py-3 text-center">
            <div className="text-[17px] font-bold font-mono tabular-nums text-foreground">
              {stats.count > 0 ? Math.round((stats.followed / stats.count) * 100) : 0}%
            </div>
            <div className="text-[10px] text-muted-foreground mt-0.5">Followed plan</div>
          </div>
          <div className="tm-card px-4 py-3 text-center">
            <div className="text-[17px] font-bold font-mono tabular-nums text-foreground capitalize">
              {stats.topEmotion ? (EMOTION_LABELS[stats.topEmotion] ?? stats.topEmotion) : '—'}
            </div>
            <div className="text-[10px] text-muted-foreground mt-0.5">Top emotion</div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="space-y-2.5 mb-5">
        {/* Period */}
        <div className="flex items-center gap-1.5">
          {PERIOD_OPTIONS.map(opt => (
            <button
              key={opt.label}
              onClick={() => setPeriod(opt.days)}
              className={cn(
                'px-3 py-1.5 rounded-lg text-[12px] font-medium transition-colors border',
                period === opt.days
                  ? 'bg-tm-brand text-white border-tm-brand'
                  : 'border-border text-muted-foreground hover:text-foreground hover:border-foreground/30',
              )}
            >
              {opt.label}
            </button>
          ))}
        </div>

        {/* Emotion filter */}
        <div className="flex flex-wrap items-center gap-1.5">
          {EMOTION_FILTERS.map(e => (
            <button
              key={e}
              onClick={() => toggleEmotion(e)}
              className={cn(
                'px-2.5 py-1 rounded text-[11px] font-medium transition-all border',
                emotionFilter.includes(e)
                  ? (EMOTION_COLORS[e] ?? '') + ' border-current'
                  : 'border-border text-muted-foreground hover:border-foreground/30',
              )}
            >
              {EMOTION_LABELS[e]}
            </button>
          ))}
        </div>

        {/* Plan filter */}
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => setPlanFilter('')}
            className={cn(
              'px-2.5 py-1 rounded text-[11px] font-medium transition-colors border',
              planFilter === ''
                ? 'bg-foreground/10 text-foreground border-foreground/20'
                : 'border-border text-muted-foreground hover:border-foreground/30',
            )}
          >
            All
          </button>
          {PLAN_FILTERS.map(opt => (
            <button
              key={opt.value}
              onClick={() => setPlanFilter(prev => prev === opt.value ? '' : opt.value)}
              className={cn(
                'px-2.5 py-1 rounded text-[11px] font-medium transition-colors border',
                planFilter === opt.value
                  ? 'bg-foreground/10 text-foreground border-foreground/20'
                  : 'border-border text-muted-foreground hover:border-foreground/30',
              )}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Entry list */}
      {loading ? (
        <div className="space-y-2">
          {[1, 2, 3, 4, 5].map(i => <EntrySkeleton key={i} />)}
        </div>
      ) : error ? (
        <ErrorState error={error} onRetry={() => fetchEntries(true)} />
      ) : filtered.length === 0 ? (
        (() => {
          const hasTagFilters = emotionFilter.length > 0 || !!planFilter;
          // Distinguish the three empty reasons so the page never looks broken:
          //   (a) genuinely no entries, (b) entries exist but all fall outside the
          //   selected time window (was misleading: "19 total" + "no match"),
          //   (c) an emotion/plan filter is hiding them.
          const noneAtAll = entries.length === 0;
          const outsideWindow = !noneAtAll && !hasTagFilters && period > 0;
          return (
            <div className="tm-card flex flex-col items-center justify-center py-16 text-center">
              <BookOpen className="h-10 w-10 text-muted-foreground/30 mb-3" />
              <p className="text-sm font-medium text-foreground">
                {noneAtAll
                  ? 'No journal entries yet'
                  : outsideWindow
                    ? `No entries in the last ${period} days`
                    : 'No entries match these filters'}
              </p>
              <p className="text-[13px] text-muted-foreground mt-1 max-w-xs">
                {noneAtAll
                  ? 'Journal entries are created when you tap the pencil icon on a trade'
                  : outsideWindow
                    ? `Your ${entries.length} entr${entries.length === 1 ? 'y is' : 'ies are'} older than this window.`
                    : 'Try removing a filter to see more entries'}
              </p>
              {outsideWindow && (
                <button
                  onClick={() => setPeriod(0)}
                  className="mt-3 text-[12px] font-medium text-tm-brand hover:underline"
                >
                  Show all entries
                </button>
              )}
            </div>
          );
        })()
      ) : (
        <div className="space-y-2">
          {filtered.map(entry => (
            <EntryCard key={entry.id} entry={entry} />
          ))}

          {/* Load more — only when no active filters (filtered view may not show new data) */}
          {hasMore && emotionFilter.length === 0 && !planFilter && (
            <button
              onClick={() => fetchEntries(false)}
              disabled={loadingMore}
              className="w-full py-3 text-[13px] text-muted-foreground hover:text-foreground transition-colors disabled:opacity-50"
            >
              {loadingMore ? 'Loading…' : 'Load more'}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
