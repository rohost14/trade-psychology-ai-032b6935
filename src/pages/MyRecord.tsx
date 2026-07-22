/**
 * "What's my record here?" — pre-trade lookup of the trader's own history.
 *
 * Replaces the old Blowup Shield page, which mixed analytics with alerts and
 * duplicated the Alerts page's "did you listen?" story using a weaker inferred
 * signal.
 *
 * Everything here is the trader's own realised history. No prediction, no
 * counterfactual, no estimated cost. When a bucket is too thin the API widens
 * the scope and says so — this UI must always surface that, never imply an
 * exact-contract read it does not have.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { Clock, Search, TrendingDown, TrendingUp, Loader2, Info } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import { formatCurrencyWithSign } from '@/lib/formatters';
import { api } from '@/lib/api';
import { useBroker } from '@/contexts/BrokerContext';

interface Bucket {
  trades: number;
  win_rate: number | null;
  wins?: number;
  losses?: number;
  pnl: number;
  avg_pnl: number;
  best?: number;
  worst?: number;
  enough: boolean;
}
interface HourBucket extends Bucket { hour: number; label: string }

interface RecordData {
  has_data: boolean;
  query: string;
  message?: string;
  scope?: string;
  scope_label?: string;
  widened?: boolean;
  min_sample?: number;
  underlying?: string;
  overall?: Bucket;
  current_hour?: number;
  this_hour?: HourBucket | null;
  by_hour?: HourBucket[];
  best_hour?: HourBucket | null;
  worst_hour?: HourBucket | null;
  situations?: Record<string, Bucket>;
  holding?: { longest_minutes: number | null; avg_minutes: number | null };
  verdict?: string | null;
}

interface SearchHit { underlying: string; trades: number; last_traded: string | null }

const SITUATION_LABELS: Record<string, string> = {
  after_loss: 'After a loss',
  after_2plus_losses: 'After 2+ losses',
  expiry_day: 'On expiry day',
  quick_reentry: 'Re-entered within 20 min',
};

function fmtHold(mins: number | null | undefined) {
  if (!mins) return '—';
  if (mins < 60) return `${Math.round(mins)}m`;
  const h = Math.floor(mins / 60);
  const m = Math.round(mins % 60);
  return m ? `${h}h ${m}m` : `${h}h`;
}

function StatRow({ label, b, highlight }: { label: string; b: Bucket; highlight?: boolean }) {
  return (
    <div className={cn(
      'flex items-center justify-between gap-3 px-4 py-3',
      highlight && 'bg-tm-brand/5',
    )}>
      <div className="min-w-0">
        <p className="text-[13px] font-medium text-foreground truncate">{label}</p>
        <p className="text-[11px] text-muted-foreground">
          {b.trades} trade{b.trades !== 1 ? 's' : ''}
          {b.win_rate !== null && ` · ${Math.round(b.win_rate)}% win rate`}
          {!b.enough && ' · too few to read'}
        </p>
      </div>
      <span className={cn(
        'font-mono font-semibold tabular-nums text-sm shrink-0',
        !b.enough ? 'text-muted-foreground' : b.pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss',
      )}>
        {formatCurrencyWithSign(Math.round(b.pnl))}
      </span>
    </div>
  );
}

export default function MyRecordPage() {
  const { account } = useBroker();
  const [query, setQuery] = useState('');
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [data, setData] = useState<RecordData | null>(null);
  const [loading, setLoading] = useState(false);
  const [searching, setSearching] = useState(false);
  const debounce = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Seed with the instruments they actually trade, so the page is useful before
  // they type anything.
  useEffect(() => {
    if (!account?.id) return;
    setSearching(true);
    api.get('/api/my-record/search', { params: { q: '' } })
      .then(r => setHits(r.data?.underlyings ?? []))
      .catch(() => setHits([]))
      .finally(() => setSearching(false));
  }, [account?.id]);

  useEffect(() => {
    if (!account?.id) return;
    if (debounce.current) clearTimeout(debounce.current);
    debounce.current = setTimeout(() => {
      api.get('/api/my-record/search', { params: { q: query } })
        .then(r => setHits(r.data?.underlyings ?? []))
        .catch(() => {});
    }, 250);
    return () => { if (debounce.current) clearTimeout(debounce.current); };
  }, [query, account?.id]);

  const lookup = useCallback(async (symbol: string) => {
    setLoading(true);
    try {
      const res = await api.get('/api/my-record', { params: { symbol } });
      setData(res.data);
    } catch {
      setData({ has_data: false, query: symbol, message: 'Could not load your record.' });
    } finally {
      setLoading(false);
    }
  }, []);

  const situations = data?.situations
    ? Object.entries(data.situations).filter(([, b]) => b.trades > 0)
    : [];

  return (
    <div className="pb-12">
      <div className="mb-5">
        <h1 className="t-heading-lg text-foreground">My Record</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Before you trade it — what actually happened last time you did.
        </p>
      </div>

      {/* Search */}
      <div className="tm-card overflow-hidden mb-5">
        <div className="p-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
            <Input
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && query.trim()) lookup(query.trim()); }}
              placeholder="Search an instrument you've traded — NIFTY, BANKNIFTY, RELIANCE…"
              className="pl-9"
            />
          </div>

          {searching ? (
            <div className="flex gap-2 mt-3">
              {[1, 2, 3].map(i => <Skeleton key={i} className="h-7 w-24 rounded-full" />)}
            </div>
          ) : hits.length > 0 ? (
            <div className="flex flex-wrap gap-2 mt-3">
              {hits.map(h => (
                <button
                  key={h.underlying}
                  onClick={() => { setQuery(h.underlying); lookup(h.underlying); }}
                  className="px-3 py-1.5 rounded-full border border-border text-[12px] hover:border-tm-brand hover:text-tm-brand transition-colors"
                >
                  {h.underlying}
                  <span className="text-muted-foreground ml-1.5">{h.trades}</span>
                </button>
              ))}
            </div>
          ) : (
            <p className="text-[12px] text-muted-foreground mt-3">
              No completed trades yet. Import your Console tradebook from Settings → Danger Zone
              to bring in your history.
            </p>
          )}
        </div>
      </div>

      {loading && (
        <div className="space-y-4">
          <Skeleton className="h-28 rounded-xl" />
          <Skeleton className="h-48 rounded-xl" />
        </div>
      )}

      {!loading && data && !data.has_data && (
        <div className="tm-card px-5 py-10 text-center">
          <p className="text-sm font-medium text-foreground">{data.message ?? 'No record found.'}</p>
        </div>
      )}

      {!loading && data?.has_data && data.overall && (
        <div className="space-y-5">
          {/* Headline */}
          <div className="tm-card px-5 py-5">
            <div className="flex flex-wrap items-baseline justify-between gap-3">
              <div className="min-w-0">
                <p className="text-[11px] uppercase tracking-wide text-muted-foreground">
                  Your record — {data.scope_label}
                </p>
                <p className="text-[15px] font-semibold text-foreground mt-0.5">
                  {data.overall.trades} completed trade{data.overall.trades !== 1 ? 's' : ''}
                  {data.overall.win_rate !== null && ` · ${Math.round(data.overall.win_rate)}% win rate`}
                </p>
              </div>
              <span className={cn(
                'font-mono font-black tabular-nums text-2xl',
                data.overall.pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss',
              )}>
                {formatCurrencyWithSign(Math.round(data.overall.pnl))}
              </span>
            </div>

            {/* Scope honesty — never let a widened bucket look exact */}
            {data.widened && (
              <p className="text-[12px] text-muted-foreground mt-3 flex items-start gap-1.5">
                <Info className="h-3.5 w-3.5 shrink-0 mt-px" />
                Too few trades on that exact contract, so this covers{' '}
                <span className="text-foreground">all your {data.scope_label} trades</span>.
              </p>
            )}

            {data.verdict && (
              <p className={cn(
                'text-[13px] mt-3 pt-3 border-t border-border',
                data.this_hour?.enough && data.this_hour.avg_pnl < 0
                  ? 'text-tm-loss' : 'text-foreground',
              )}>
                {data.verdict}
              </p>
            )}
          </div>

          {/* Right now */}
          {data.this_hour && (
            <div className={cn(
              'tm-card px-5 py-4 border-l-4',
              !data.this_hour.enough ? 'border-l-border'
                : data.this_hour.avg_pnl >= 0 ? 'border-l-tm-profit' : 'border-l-tm-loss',
            )}>
              <p className="text-[11px] uppercase tracking-wide text-muted-foreground flex items-center gap-1.5">
                <Clock className="h-3.5 w-3.5" />
                Right now · {data.this_hour.label} IST
              </p>
              <p className="text-[15px] font-semibold text-foreground mt-1">
                {data.this_hour.trades} trade{data.this_hour.trades !== 1 ? 's' : ''}
                {data.this_hour.win_rate !== null && ` · ${Math.round(data.this_hour.win_rate)}% win rate`}
                {' · '}
                <span className={data.this_hour.pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss'}>
                  {formatCurrencyWithSign(Math.round(data.this_hour.pnl))}
                </span>
              </p>
              {!data.this_hour.enough && (
                <p className="text-[12px] text-muted-foreground mt-1">
                  Fewer than {data.min_sample} trades in this window — not enough to mean much.
                </p>
              )}
            </div>
          )}

          {/* Best / worst hour */}
          {(data.best_hour || data.worst_hour) && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {data.best_hour && (
                <div className="tm-card px-5 py-4">
                  <p className="text-[11px] uppercase tracking-wide text-muted-foreground flex items-center gap-1.5">
                    <TrendingUp className="h-3.5 w-3.5 text-tm-profit" /> Your strongest window
                  </p>
                  <p className="text-[15px] font-semibold text-foreground mt-1">{data.best_hour.label}</p>
                  <p className="text-[12px] text-muted-foreground">
                    {data.best_hour.trades} trades · {Math.round(data.best_hour.win_rate ?? 0)}% win ·{' '}
                    <span className="text-tm-profit">{formatCurrencyWithSign(Math.round(data.best_hour.pnl))}</span>
                  </p>
                </div>
              )}
              {data.worst_hour && (
                <div className="tm-card px-5 py-4">
                  <p className="text-[11px] uppercase tracking-wide text-muted-foreground flex items-center gap-1.5">
                    <TrendingDown className="h-3.5 w-3.5 text-tm-loss" /> Your weakest window
                  </p>
                  <p className="text-[15px] font-semibold text-foreground mt-1">{data.worst_hour.label}</p>
                  <p className="text-[12px] text-muted-foreground">
                    {data.worst_hour.trades} trades · {Math.round(data.worst_hour.win_rate ?? 0)}% win ·{' '}
                    <span className="text-tm-loss">{formatCurrencyWithSign(Math.round(data.worst_hour.pnl))}</span>
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Situations */}
          {situations.length > 0 && (
            <div className="tm-card overflow-hidden">
              <div className="px-5 py-3.5 border-b border-border">
                <p className="font-semibold text-sm">In these situations</p>
                <p className="text-[11px] text-muted-foreground mt-0.5">
                  Your own results on {data.scope_label}, grouped by the state you were in
                </p>
              </div>
              <div className="divide-y divide-border">
                {situations.map(([key, b]) => (
                  <StatRow key={key} label={SITUATION_LABELS[key] ?? key} b={b} />
                ))}
              </div>
            </div>
          )}

          {/* Holding */}
          {data.holding?.avg_minutes != null && (
            <div className="tm-card px-5 py-4 flex flex-wrap gap-x-8 gap-y-2">
              <div>
                <p className="text-[11px] uppercase tracking-wide text-muted-foreground">Average hold</p>
                <p className="text-[15px] font-semibold text-foreground font-mono">
                  {fmtHold(data.holding.avg_minutes)}
                </p>
              </div>
              <div>
                <p className="text-[11px] uppercase tracking-wide text-muted-foreground">Longest you've held</p>
                <p className="text-[15px] font-semibold text-foreground font-mono">
                  {fmtHold(data.holding.longest_minutes)}
                </p>
              </div>
            </div>
          )}

          <p className="text-[11px] text-muted-foreground">
            Every figure is your own realised history over the last year — raw P&amp;L, no charges,
            no projections. Buckets under {data.min_sample} trades are marked as too thin to read.
          </p>
        </div>
      )}

      {!loading && !data && hits.length > 0 && (
        <div className="tm-card px-5 py-10 text-center">
          <Search className="h-7 w-7 text-muted-foreground/40 mx-auto mb-3" />
          <p className="text-sm font-medium text-foreground">Pick an instrument above</p>
          <p className="text-[13px] text-muted-foreground mt-1 max-w-sm mx-auto">
            You'll see how you've actually performed on it — including at this hour of the day,
            and after a loss.
          </p>
        </div>
      )}
    </div>
  );
}
