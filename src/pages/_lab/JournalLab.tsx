/**
 * DESIGN LAB — working copy of Journal. Route: /journal-lab
 */
import { useState, useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { Link2, BookOpen, ChevronDown, ChevronUp } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import ErrorState from '@/components/ErrorState';
import { cn } from '@/lib/utils';
import { api } from '@/lib/api';
import { useBroker } from '@/contexts/BrokerContext';
import { MorningIntentCard } from '@/components/dashboard/MorningIntentCard';

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
  /** Day-entry lesson. Present in the backend schema, missing from this type. */
  lessons?: string | null;
  trade_symbol: string | null;
  trade_type: string | null;
  trade_pnl: string | null;
  entry_type: string;
  created_at: string;
  updated_at: string;
}

// ── Display maps ──────────────────────────────────────────────────────────────
import { formatCurrencyWhole } from '@/lib/formatters';
import DayEntrySheet from '@/components/journal/DayEntrySheet';
import LessonLibrary from '@/components/journal/LessonLibrary';

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

interface DayGroup {
  date: string;
  day: JournalEntry | null;
  trades: JournalEntry[];
  pnl: number;
}

/** Fold entries into days: the day entry heads the group, trades sit under it. */
function groupByDay(entries: JournalEntry[]): DayGroup[] {
  const byDate = new Map<string, DayGroup>();

  for (const e of entries) {
    const date = (e.created_at ?? '').slice(0, 10);
    if (!date) continue;
    if (!byDate.has(date)) byDate.set(date, { date, day: null, trades: [], pnl: 0 });
    const g = byDate.get(date)!;

    if (e.entry_type !== 'trade') {
      g.day = e;
    } else {
      g.trades.push(e);
      const v = e.trade_pnl != null ? Number(e.trade_pnl) : 0;
      if (Number.isFinite(v)) g.pnl += v;
    }
  }

  return [...byDate.values()].sort((a, b) => (a.date < b.date ? 1 : -1));
}

function dayLabel(date: string) {
  const [y, m, d] = date.split('-').map(Number);
  return new Date(y, m - 1, d).toLocaleDateString('en-IN', {
    weekday: 'short', day: 'numeric', month: 'short',
  });
}

/**
 * Did the day match its intent?
 *
 * Computed, never asked. The trader wrote what they meant to do; the engine
 * already knows what they did. Comparing the two is the whole mirror premise
 * applied to intent, and it is what makes writing one worth the ten seconds.
 *
 * Deliberately narrow: only plan-adherence recorded on the day's own trades.
 * No language parsing of the intent text -- guessing at whether "only A+
 * setups" was honoured would be exactly the counterfactual the charter bans.
 */
function intentOutcome(g: DayGroup): { kept: number; broke: number } | null {
  if (!g.day || g.trades.length === 0) return null;
  let kept = 0, broke = 0;
  for (const t of g.trades) {
    if (t.followed_plan === 'yes') kept++;
    else if (t.followed_plan === 'no' || t.followed_plan === 'partial') broke++;
  }
  if (kept + broke === 0) return null;
  return { kept, broke };
}

function EntryCard({ entry }: { entry: JournalEntry }) {
  const [expanded, setExpanded] = useState(false);
  const pnl = parsePnl(entry.trade_pnl);
  const isDay = entry.entry_type !== 'trade';
  const pnlStr = fmtPnl(entry.trade_pnl);
  const hasNotes = !!entry.notes?.trim();
  const hasExtra = !!(entry.market_condition || entry.setup_quality || entry.would_repeat || entry.deviation_reason);

  return (
    <div className="border-b border-border last:border-b-0">
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
            {/* Day-level and trade-level entries were indistinguishable in this
                list, which was exactly the question it could not answer. */}
            <span className="text-[10px] uppercase tracking-wider text-muted-foreground border border-border rounded px-1.5 py-0.5 shrink-0">
              {isDay ? 'Day' : 'Trade'}
            </span>
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

export default function JournalLab() {
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
  const [search, setSearch]         = useState('');
  const [dayEntryOpen, setDayEntryOpen] = useState(false);

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
  // A day-level entry carries no trade. Everything written from the Dashboard
  // sheet is attached to one, so entry_type distinguishes the two.
  const todayEntry = useMemo(() => {
    const today = new Date().toISOString().slice(0, 10);
    return entries.find(e => e.entry_type !== 'trade' && (e.created_at ?? '').slice(0, 10) === today) ?? null;
  }, [entries]);

  const filtered = useMemo(() => {
    const cutoff = period > 0
      ? Date.now() - period * 24 * 60 * 60 * 1000
      : 0;

    return entries.filter(e => {
      if (period > 0 && new Date(e.created_at).getTime() < cutoff) return false;
      if (emotionFilter.length > 0 && !emotionFilter.some(f => e.emotion_tags.includes(f))) return false;
      if (planFilter && e.followed_plan !== planFilter) return false;
      if (search.trim()) {
        // Notes and symbol are what a trader actually remembers an entry by.
        const hay = `${e.notes ?? ''} ${e.trade_symbol ?? ''} ${e.deviation_reason ?? ''}`.toLowerCase();
        if (!hay.includes(search.trim().toLowerCase())) return false;
      }
      return true;
    });
  }, [entries, period, emotionFilter, planFilter, search]);

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

      {/* Today's intent — moved here from the Dashboard (Journal owns intent) */}
      <div className="mb-5">
        <MorningIntentCard />
      </div>

      {/* Session summary. A hairline strip, not three equal cards -- the gaps
          are the separators. */}
      {!loading && stats && (
        <div className="grid grid-cols-3 divide-x divide-border border-y border-border mb-6">
          <div className="px-4 py-3">
            <span className="t-label">P&amp;L journalled</span>
            <div className={cn(
              'text-[17px] font-medium font-tabular mt-0.5',
              stats.total >= 0 ? 'text-tm-profit' : 'text-tm-loss',
            )}>
              {formatCurrencyWhole(stats.total)}
            </div>
          </div>
          <div className="px-4 py-3">
            <span className="t-label">Followed plan</span>
            <div className="text-[17px] font-medium font-tabular mt-0.5 text-foreground">
              {stats.count > 0 ? Math.round((stats.followed / stats.count) * 100) : 0}%
            </div>
          </div>
          <div className="px-4 py-3">
            <span className="t-label">Entries</span>
            <div className="text-[17px] font-medium font-tabular mt-0.5 text-foreground">
              {stats.count}
            </div>
          </div>
        </div>
      )}

      <DayEntrySheet
        open={dayEntryOpen}
        onOpenChange={setDayEntryOpen}
        existing={todayEntry}
        onSaved={() => fetchEntries(true)}
      />

      {/* Write one. There was no way to create a journal entry from this page
          at all -- every entry here came from the Dashboard trade sheet, so the
          page could only ever be read. Day-level entries have no other home. */}
      <div className="flex items-center justify-between gap-3 mb-4 pb-3 border-b border-border">
        <div className="min-w-0">
          <h2 className="text-[15px] font-medium text-foreground">Today</h2>
          {todayEntry ? (
            /* Read it without opening it. An intent you have to click to see is
               an intent you will not re-read mid-session, which is the only
               moment it is worth anything. */
            <div className="mt-1.5 space-y-1">
              {todayEntry.notes && (
                <p className="text-[13px] text-foreground leading-snug">
                  <span className="text-muted-foreground">Intent: </span>{todayEntry.notes}
                </p>
              )}
              {todayEntry.lessons && (
                <p className="text-[13px] text-foreground leading-snug">
                  <span className="text-tm-obs">Lesson: </span>{todayEntry.lessons}
                </p>
              )}
              {!todayEntry.notes && !todayEntry.lessons && (
                <p className="text-[12.5px] text-muted-foreground">
                  Mood recorded. Add an intent when you have one.
                </p>
              )}
            </div>
          ) : (
            <p className="text-[12.5px] text-muted-foreground mt-0.5">
              Nothing written yet — how you are trading today, and what you plan to do about it.
            </p>
          )}
        </div>
        <button
          type="button"
          onClick={() => setDayEntryOpen(true)}
          className="h-9 px-3.5 rounded-md bg-primary text-primary-foreground text-[13px] font-medium shrink-0 transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        >
          {todayEntry ? 'Edit today' : 'Write today'}
        </button>
      </div>

      {/* Collected lessons. A lesson written into one day's entry scrolls away
          with it, so writing one has no payoff; this is the payoff. */}
      {!loading && <LessonLibrary entries={entries} />}

      {/* One filter row and a search box. There were three rows and thirteen
          controls here, above a list of four; search answers more of them than
          any of the chips did. */}
      <div className="flex items-center gap-2 flex-wrap mb-4">
        <input
          type="search"
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search entries"
          className="h-8 px-3 rounded-md border border-border bg-card text-[13px] text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring w-full sm:w-56"
        />
        <div className="flex items-center gap-1.5 flex-wrap">
          <button
            onClick={() => setEmotionFilter([])}
            className={cn(
              'h-8 px-3 rounded-md text-[12.5px] font-medium border transition-colors',
              emotionFilter.length === 0 ? 'bg-muted text-foreground border-border' : 'text-muted-foreground border-border hover:text-foreground',
            )}
          >
            All
          </button>
          {EMOTION_FILTERS.map(v => ({ value: v, label: EMOTION_LABELS[v] ?? v })).map(em => (
            <button
              key={em.value}
              onClick={() => setEmotionFilter(prev => prev.includes(em.value) ? prev.filter(v => v !== em.value) : [...prev, em.value])}
              className={cn(
                'h-8 px-3 rounded-md text-[12.5px] font-medium border transition-colors',
                emotionFilter.includes(em.value) ? 'bg-muted text-foreground border-border' : 'text-muted-foreground border-border hover:text-foreground',
              )}
            >
              {em.label}
            </button>
          ))}
        </div>
      </div>

      {loading && entries.length === 0 ? (
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
        <div className="space-y-6">
          {groupByDay(filtered).map(g => {
            const outcome = intentOutcome(g);
            return (
              <section key={g.date} className="grid grid-cols-1 sm:grid-cols-[104px_minmax(0,1fr)] gap-x-5">
                {/* Date lives in a left gutter rather than a full-width header
                    row. The header was spending a whole row on a date and a
                    number while the right two-thirds sat empty; this uses the
                    horizontal space that was already there and gives every day
                    back that vertical space. Collapses to an inline header
                    below sm, where a 104px gutter would eat the content. */}
                <div className="sm:text-right sm:pt-3 sm:sticky sm:top-2 sm:self-start">
                  <div className="flex sm:block items-baseline gap-2 pb-1 sm:pb-0 border-b sm:border-b-0 border-border">
                    <span className="text-[13px] font-medium text-foreground whitespace-nowrap">
                      {dayLabel(g.date)}
                    </span>
                    {g.trades.length > 0 && (
                      <>
                        <span className={cn(
                          'text-[12.5px] font-medium font-tabular sm:block sm:mt-0.5',
                          g.pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss',
                        )}>
                          {formatCurrencyWhole(g.pnl)}
                        </span>
                        <span className="text-[11px] text-muted-foreground font-tabular sm:block sm:mt-0.5">
                          {g.trades.length} trade{g.trades.length !== 1 ? 's' : ''}
                        </span>
                      </>
                    )}
                  </div>
                </div>

                <div className="min-w-0 sm:border-l sm:border-border sm:pl-5">
                  {g.day && (
                    <div className="py-3 border-b border-border">
                      {g.day.notes && (
                        <p className="text-[13px] text-foreground leading-snug">
                          <span className="text-muted-foreground">Intent: </span>{g.day.notes}
                        </p>
                      )}
                      {g.day.lessons && (
                        <p className="text-[13px] text-foreground leading-snug mt-1">
                          <span className="text-tm-obs">Lesson: </span>{g.day.lessons}
                        </p>
                      )}
                      {outcome && (
                        <p className="text-[12px] text-muted-foreground mt-1.5">
                          {outcome.broke === 0
                            ? 'Every trade that day matched your plan.'
                            : `${outcome.kept} of ${outcome.kept + outcome.broke} trades matched it.`}
                        </p>
                      )}
                    </div>
                  )}

                  {g.trades.map(entry => (
                    <EntryCard key={entry.id} entry={entry} />
                  ))}
                </div>
              </section>
            );
          })}

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
