/**
 * "What's my record here?" — pre-trade lookup of the trader's own history.
 *
 * Responsibility (DESIGN_SYSTEM.md §26): what happened the last time I traded
 * this setup. Nothing here predicts, scores, or advises — every figure is the
 * trader's own realised history. When a bucket is too thin the API widens the
 * scope and says so, and this UI must always surface that rather than imply an
 * exact-contract read it does not have.
 *
 * Containers: the lookup earns a card (§9 justification 1 — a distinct
 * interactive object). Everything below it is a labelled section, so the
 * situations table runs edge to edge.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { Clock, Search, TrendingDown, TrendingUp, Info } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import { formatCurrencyWithSign } from '@/lib/formatters';
import { api } from '@/lib/api';
import { useBroker } from '@/contexts/BrokerContext';
import BrokerGate from '@/components/BrokerGate';

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

function pnlTone(b: Pick<Bucket, 'pnl' | 'enough'>) {
  if (!b.enough) return 'text-muted-foreground';
  if (b.pnl > 0) return 'text-profit';
  if (b.pnl < 0) return 'text-loss';
  return 'text-muted-foreground';
}

/** A block header inside a surface: label left, optional summary right. */
function SectionHead({ label, icon: Icon, right }: {
  label: string;
  icon?: React.ElementType;
  right?: React.ReactNode;
}) {
  return (
    <div className="card-head">
      <span className="t-label flex items-center gap-1.5">
        {Icon && <Icon className="h-3.5 w-3.5" />}
        {label}
      </span>
      {right}
    </div>
  );
}


/** One situation row. Dense, value right-aligned and tabular (§18). */
function SituationRow({ label, b }: { label: string; b: Bucket }) {
  return (
    <div className="flex items-center justify-between gap-3 py-3.5">
      <div className="min-w-0">
        <p className="text-[14px] font-medium text-foreground truncate">{label}</p>
        <p className="text-[11px] text-muted-foreground font-tabular">
          {b.trades} trade{b.trades !== 1 ? 's' : ''}
          {b.win_rate !== null && ` · ${Math.round(b.win_rate)}% win rate`}
          {!b.enough && ' · too few to read'}
        </p>
      </div>
      <span className={cn('text-[14px] font-semibold font-tabular shrink-0', pnlTone(b))}>
        {formatCurrencyWithSign(Math.round(b.pnl))}
      </span>
    </div>
  );
}

/** Best / weakest window. Same shape both sides. */
function WindowStat({ bucket, kind }: { bucket: HourBucket; kind: 'best' | 'worst' }) {
  const isBest = kind === 'best';
  const Icon = isBest ? TrendingUp : TrendingDown;

  return (
    <div className="px-4 sm:px-6 py-4">
      <span className="t-label">{isBest ? 'Strongest window' : 'Weakest window'}</span>
      <div className="flex items-baseline gap-2 mt-1.5">
        <Icon className={cn('h-4 w-4 shrink-0', isBest ? 'text-profit' : 'text-loss')} />
        <p className="text-[17px] font-semibold tracking-tight text-foreground">{bucket.label}</p>
      </div>
      <p className="text-[12.5px] text-muted-foreground mt-1 font-tabular">
        {bucket.trades} trades · {Math.round(bucket.win_rate ?? 0)}% win ·{' '}
        <span className={isBest ? 'text-profit' : 'text-loss'}>
          {formatCurrencyWithSign(Math.round(bucket.pnl))}
        </span>
      </p>
    </div>
  );
}

export default function MyRecordPage() {
  const { account, isConnected, isLoading: brokerLoading } = useBroker();
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
      // Error-as-data: the API's own contract carries the message, so a failure
      // still reads as a failure rather than as "no record".
      setData({ has_data: false, query: symbol, message: 'Could not load your record.' });
    } finally {
      setLoading(false);
    }
  }, []);

  const situations = data?.situations
    ? Object.entries(data.situations).filter(([, b]) => b.trades > 0)
    : [];

  // Not connected — the same gate every other screen shows. This screen used to
  // render an inert search box instead.
  if (!brokerLoading && !isConnected) {
    return (
      <BrokerGate
        title="My Record"
        unlocks="Connect your Zerodha account to look up how you've actually traded an instrument before."
      />
    );
  }

  return (
    <div className="pb-12">
      <div className="mb-5">
        <h1 className="text-[22px] font-semibold tracking-tight text-foreground">My Record</h1>
        <p className="text-[12.5px] text-muted-foreground mt-0.5">
          Before you trade it — what actually happened last time you did.
        </p>
      </div>

      {/* Lookup — a distinct interactive object, so it earns a card (§9). */}
      <div className="desk-card p-4 mb-5">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
          <Input
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && query.trim()) lookup(query.trim()); }}
            placeholder="Search an instrument you've traded — NIFTY, BANKNIFTY, RELIANCE…"
            className="pl-9 text-[14px]"
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
                className="px-3 py-1.5 rounded-full border border-border text-[12.5px] text-foreground transition-colors duration-150 hover:border-primary hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
              >
                {h.underlying}
                <span className="text-muted-foreground ml-1.5 font-tabular">{h.trades}</span>
              </button>
            ))}
          </div>
        ) : (
          // Cold start states the actual cause, not "no data" (§15).
          <p className="text-[12.5px] text-muted-foreground mt-3">
            No completed trades yet. Kite doesn't provide historical trades — import your Console
            tradebook from Settings → Danger Zone to bring in your history.
          </p>
        )}
      </div>

      {loading && (
        <div className="space-y-5">
          <div>
            <div className="section-head"><Skeleton className="h-3 w-40" /><Skeleton className="h-6 w-28" /></div>
            <div className="py-4 space-y-2"><Skeleton className="h-4 w-56" /><Skeleton className="h-4 w-40" /></div>
          </div>
          <div>
            <div className="section-head"><Skeleton className="h-3 w-32" /></div>
            <div className="divide-y divide-border">
              {[1, 2, 3].map(i => (
                <div key={i} className="flex items-center justify-between py-3.5">
                  <div className="space-y-1.5"><Skeleton className="h-3.5 w-32" /><Skeleton className="h-3 w-24" /></div>
                  <Skeleton className="h-4 w-16" />
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {!loading && data && !data.has_data && (
        <div className="py-10 text-center">
          <p className="text-[14px] font-medium text-foreground">{data.message ?? 'No record found.'}</p>
          <p className="text-[12.5px] text-muted-foreground mt-1">
            Try another instrument, or import more history from Settings → Danger Zone.
          </p>
        </div>
      )}

      {!loading && data?.has_data && data.overall && (
        <div className="space-y-5">
          {/* Surface 1 — the record itself: headline, this hour, the two
              windows. One block, with sub-blocks inside it. */}
          <section className="desk-card overflow-hidden">
            <SectionHead
              label={`Your record · ${data.scope_label}`}
              right={
                <span className="text-[11px] text-muted-foreground font-tabular">
                  {data.overall.trades} trade{data.overall.trades !== 1 ? 's' : ''}
                  {data.overall.win_rate !== null && ` · ${Math.round(data.overall.win_rate)}% win`}
                </span>
              }
            />
            <div className="px-4 sm:px-6 py-4">
              <p className={cn(
                'font-display text-[30px] font-semibold tracking-tight font-tabular',
                pnlTone(data.overall),
              )}>
                {formatCurrencyWithSign(Math.round(data.overall.pnl))}
              </p>

              {/* Scope honesty — never let a widened bucket look exact. */}
              {data.widened && (
                <p className="text-[12.5px] text-muted-foreground mt-2 flex items-start gap-1.5">
                  <Info className="h-3.5 w-3.5 shrink-0 mt-0.5" />
                  <span>
                    Too few trades on that exact contract, so this covers{' '}
                    <span className="text-foreground">all your {data.scope_label} trades</span>.
                  </span>
                </p>
              )}

              {data.verdict && (
                <p className="text-[14px] text-foreground mt-3">{data.verdict}</p>
              )}
            </div>

            {/* Right now — sub-block, keyed to this hour's own record. */}
            {data.this_hour && (
              <div className={cn(
                'border-t border-border border-l-2',
                !data.this_hour.enough ? 'border-l-border'
                  : data.this_hour.avg_pnl >= 0 ? 'border-l-profit' : 'border-l-loss',
              )}>
                <div className="px-4 sm:px-6 py-4">
                  <span className="t-label flex items-center gap-1.5">
                    <Clock className="h-3.5 w-3.5" />
                    Right now · {data.this_hour.label} IST
                  </span>
                  <p className="text-[17px] font-semibold tracking-tight text-foreground font-tabular mt-1.5">
                    {data.this_hour.trades} trade{data.this_hour.trades !== 1 ? 's' : ''}
                    {data.this_hour.win_rate !== null && ` · ${Math.round(data.this_hour.win_rate)}% win rate`}
                    {' · '}
                    <span className={pnlTone(data.this_hour)}>
                      {formatCurrencyWithSign(Math.round(data.this_hour.pnl))}
                    </span>
                  </p>
                  {!data.this_hour.enough && (
                    <p className="text-[12.5px] text-muted-foreground mt-1 font-tabular">
                      Fewer than {data.min_sample} trades in this window — not enough to mean much.
                    </p>
                  )}
                </div>
              </div>
            )}

            {/* Strongest / weakest window — hairline pair inside the surface. */}
            {(data.best_hour || data.worst_hour) && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-px bg-border border-t border-border">
                {data.best_hour && <div className="bg-card"><WindowStat bucket={data.best_hour} kind="best" /></div>}
                {data.worst_hour && <div className="bg-card"><WindowStat bucket={data.worst_hour} kind="worst" /></div>}
              </div>
            )}
          </section>

          {/* Surface 2 — situations. The table runs edge to edge inside it. */}
          {situations.length > 0 && (
            <section className="desk-card overflow-hidden">
              <SectionHead
                label="In these situations"
                right={
                  <span className="text-[11px] text-muted-foreground">
                    grouped by the state you were in
                  </span>
                }
              />
              <div className="px-4 sm:px-6 divide-y divide-border">
                {situations.map(([key, b]) => (
                  <SituationRow key={key} label={SITUATION_LABELS[key] ?? key} b={b} />
                ))}
              </div>
            </section>
          )}

          {/* Surface 3 — holding */}
          {data.holding?.avg_minutes != null && (
            <section className="desk-card overflow-hidden">
              <SectionHead label="Holding" />
              <div className="grid grid-cols-2 gap-px bg-border">
                <div className="bg-card px-4 sm:px-6 py-3">
                  <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">Average hold</p>
                  <p className="text-[14px] font-semibold text-foreground font-tabular mt-0.5">
                    {fmtHold(data.holding.avg_minutes)}
                  </p>
                </div>
                <div className="bg-card px-4 sm:px-6 py-3">
                  <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">Longest held</p>
                  <p className="text-[14px] font-semibold text-foreground font-tabular mt-0.5">
                    {fmtHold(data.holding.longest_minutes)}
                  </p>
                </div>
              </div>
            </section>
          )}

          <p className="text-[11px] text-muted-foreground pt-1">
            Every figure is your own realised history over the last year — raw P&amp;L, no charges,
            no projections. Buckets under {data.min_sample} trades are marked as too thin to read.
          </p>
        </div>
      )}

      {!loading && !data && hits.length > 0 && (
        <div className="py-10 text-center">
          <Search className="h-5 w-5 text-muted-foreground mx-auto mb-3" />
          <p className="text-[14px] font-medium text-foreground">Pick an instrument above</p>
          <p className="text-[12.5px] text-muted-foreground mt-1 max-w-sm mx-auto">
            You'll see how you've actually performed on it — including at this hour of the day,
            and after a loss.
          </p>
        </div>
      )}
    </div>
  );
}
