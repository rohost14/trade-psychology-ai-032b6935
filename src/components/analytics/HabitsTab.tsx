/**
 * Habits tab — zero-input behavioural tendencies from the user's own completed trades:
 * after-loss size drift, time-of-day, day-of-week, and instrument. Plain-language, factual,
 * raw P&L. Cross-links to Edge (instruments) / Advanced (session timing) for the deep charts
 * rather than re-plotting them.
 */
import { TrendingUp, TrendingDown, Clock, CalendarDays, Layers, AlertTriangle } from 'lucide-react';
import { api } from '@/lib/api';
import { useFetch } from '@/hooks/useFetch';
import ErrorState from '@/components/ErrorState';
import { CardSkeleton } from '@/components/ui/skeletons';
import SessionLog from './SessionLog';

interface Bucket { key: number | string; label: string; trades: number; net_pnl: number; win_rate: number; }
interface HabitsData {
  has_data: boolean;
  sample: number;
  min_sample?: number;
  by_hour: Bucket[];
  by_day_of_week: Bucket[];
  by_instrument: Bucket[];
  after_loss_size: {
    overall_avg_notional: number; after_loss_avg_notional: number;
    ratio: number | null; after_loss_count: number; min_bucket: number;
  };
  summary: {
    total_trades: number; gross_pnl: number; win_rate: number;
    worst_hour: string | null; best_hour: string | null;
    worst_instrument: string | null; best_instrument: string | null;
  };
}

const inr = (n: number) => (n < 0 ? '-' : '') + '₹' + Math.abs(Math.round(n)).toLocaleString('en-IN');
const pnlClass = (n: number) => (n >= 0 ? 'text-tm-profit' : 'text-tm-loss');

function BucketBars({ rows, minBucket = 1 }: { rows: Bucket[]; minBucket?: number }) {
  const shown = rows.filter(r => r.trades >= minBucket);
  const maxAbs = Math.max(1, ...shown.map(r => Math.abs(r.net_pnl)));
  if (shown.length === 0) return <p className="text-xs text-muted-foreground">Not enough data yet.</p>;
  return (
    <div className="space-y-2">
      {shown.map(r => (
        <div key={String(r.key)} className="grid items-center gap-3 [grid-template-columns:64px_1fr_92px]">
          <span className="text-xs text-muted-foreground">{r.label}</span>
          <div className="h-2 rounded bg-muted overflow-hidden relative">
            <div
              className={r.net_pnl >= 0 ? 'bg-tm-profit' : 'bg-tm-loss'}
              style={{ position: 'absolute', inset: 0, width: `${(Math.abs(r.net_pnl) / maxAbs) * 100}%` }}
            />
          </div>
          <div className="text-right">
            <span className={`text-[13px] font-semibold tabular-nums ${pnlClass(r.net_pnl)}`}>{inr(r.net_pnl)}</span>
            <span className="text-[11px] text-muted-foreground ml-2">{r.win_rate}%</span>
          </div>
        </div>
      ))}
    </div>
  );
}

function Card({ icon: Icon, title, sub, children }: { icon: React.ElementType; title: string; sub?: string; children: React.ReactNode }) {
  return (
    <div className="tm-card overflow-hidden">
      <div className="px-5 py-3.5 border-b border-border">
        <p className="text-sm font-semibold text-foreground flex items-center gap-2"><Icon className="h-4 w-4 text-tm-brand" /> {title}</p>
        {sub && <p className="text-xs text-muted-foreground mt-0.5">{sub}</p>}
      </div>
      <div className="p-5">{children}</div>
    </div>
  );
}

export default function HabitsTab({ days }: { days: number }) {
  // Reference migration to the Phase 2 primitives — the template for the Phase 3 rollout.
  const { data, loading, error, retry } = useFetch<HabitsData>(
    () => api.get<HabitsData>(`/api/analytics/habits?days=${days}`).then(r => r.data),
    [days],
  );

  if (loading) return <div className="space-y-5"><CardSkeleton lines={2} /><CardSkeleton lines={4} /><CardSkeleton lines={4} /></div>;
  if (error) return <ErrorState error={error} onRetry={retry} />;
  if (!data) return null;

  if (!data.has_data) {
    return (
      <div className="tm-card p-8 text-center">
        <div className="w-12 h-12 rounded-full bg-tm-brand/10 flex items-center justify-center mx-auto mb-3">
          <Clock className="h-6 w-6 text-tm-brand" />
        </div>
        <p className="text-sm font-semibold text-foreground">Habits unlock after {data.min_sample ?? 5} completed trades</p>
        <p className="text-xs text-muted-foreground mt-1">
          You have {data.sample}. Import your Console tradebook (Settings → or the banner on Dashboard) to see them straight away.
        </p>
      </div>
    );
  }

  const als = data.after_loss_size;
  const driftUp = als.ratio != null && als.ratio > 1.15;
  const driftDown = als.ratio != null && als.ratio < 0.85;

  return (
    <div className="space-y-5">
      {/* Session tagging — your days at a glance */}
      <SessionLog days={days} />

      {/* After-loss size drift — the lead, net-new insight */}
      <Card icon={AlertTriangle} title="After a loss, do you size up?" sub="Average position value on the trade right after a losing one, vs your normal.">
        {als.ratio == null ? (
          <p className="text-sm text-muted-foreground">Not enough back-to-back trades yet ({als.after_loss_count} after-loss trades so far).</p>
        ) : (
          <div className="flex items-baseline gap-3">
            <span className={`text-[34px] font-bold tabular-nums leading-none ${driftUp ? 'text-tm-loss' : driftDown ? 'text-tm-profit' : 'text-foreground'}`}>
              {als.ratio}×
            </span>
            <p className="text-[13px] text-muted-foreground">
              {driftUp
                ? <>your normal size, right after a loss — a classic tilt / revenge-size tell. Based on {als.after_loss_count} after-loss trades.</>
                : driftDown
                ? <>your normal size after a loss — you shrink, not chase. Based on {als.after_loss_count} after-loss trades.</>
                : <>about your normal size after a loss — no size tilt. Based on {als.after_loss_count} after-loss trades.</>}
            </p>
          </div>
        )}
      </Card>

      {/* Time of day */}
      <Card icon={Clock} title="Time of day" sub={data.summary.worst_hour ? `Your weakest hour is around ${data.summary.worst_hour}. Bars = net P&L, right = win-rate.` : 'Net P&L by entry hour (IST).'}>
        <BucketBars rows={data.by_hour} minBucket={2} />
      </Card>

      {/* Day of week */}
      <Card icon={CalendarDays} title="Day of week" sub="Captures the Thursday weekly-expiry effect. Bars = net P&L, right = win-rate.">
        <BucketBars rows={data.by_day_of_week} minBucket={2} />
      </Card>

      {/* Instrument */}
      <Card icon={Layers} title="By instrument" sub="Where your edge lives and leaks. See the full breakdown in the Edge tab.">
        <div className="space-y-2">
          {data.by_instrument.filter(r => r.trades >= 2).map(r => (
            <div key={String(r.key)} className="flex items-center justify-between py-1.5 border-b border-border last:border-0">
              <div className="flex items-center gap-2">
                {r.net_pnl >= 0 ? <TrendingUp className="h-3.5 w-3.5 text-tm-profit" /> : <TrendingDown className="h-3.5 w-3.5 text-tm-loss" />}
                <span className="text-[13px] font-medium text-foreground">{r.label}</span>
                <span className="text-[11px] text-muted-foreground">{r.trades} trades · {r.win_rate}%</span>
              </div>
              <span className={`text-[13px] font-semibold tabular-nums ${pnlClass(r.net_pnl)}`}>{inr(r.net_pnl)}</span>
            </div>
          ))}
        </div>
      </Card>

      <p className="text-[11px] text-muted-foreground text-center">
        All figures are raw realized P&L over the selected period, computed from your own trades. No estimates.
      </p>
    </div>
  );
}
