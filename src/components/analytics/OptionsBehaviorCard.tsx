// Options-specific behavioural summary — F&O patterns brokers don't surface.
// Data: GET /api/analytics/options-behavior (aggregates stored risk_alerts rows).
// All figures are counts or realized rupees — no attribution, no estimation.
//
// HISTORICAL ONLY as of 2026-08-30. All three sections were fed by detectors
// that no longer emit: options_direction_confusion and iv_crush_behavior were
// engine-v1 names the endpoint never repointed, and options_premium_avg_down
// was retired at Pattern 20. Stored rows still render truthfully inside the
// lookback; once they age out `has_data` is false forever and this card
// renders NOTHING (see the guard below), which is why no misleading empty
// surface appears. Repointing it at premium_loss_event — the one live options
// detector — would change what these sections mean, so it is a product
// decision, recorded in docs/DEEP_REVIEW/PENDING_AND_TODO.md and deliberately
// not taken as part of a detector retirement.

import { useState, useEffect } from 'react';
import { Repeat, TrendingDown, Hourglass } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import { formatCurrencyWithSign } from '@/lib/formatters';
import { api } from '@/lib/api';

interface DirectionConfusion {
  count: number;
  underlying_breakdown: Record<string, number>;
  avg_flip_minutes: number | null;
}

interface PremiumAvgDown {
  count: number;
  total_re_entry_premium: number;
  avg_worst_loss_pct: number | null;
}

interface IvCrush {
  count: number;
  total_loss: number;
  avg_hold_minutes: number | null;
  avg_loss_pct: number | null;
}

interface OptionsBehaviorData {
  period_days: number;
  has_data: boolean;
  direction_confusion: DirectionConfusion;
  premium_avg_down: PremiumAvgDown;
  iv_crush: IvCrush;
}

function formatMinutes(mins: number | null): string | null {
  if (mins === null) return null;
  if (mins < 60) return `${Math.round(mins)}m`;
  return `${(mins / 60).toFixed(1)}h`;
}

interface OptionsBehaviorCardProps {
  days: number;
  /** Lets the parent tab know whether this card rendered, so its own empty state stays accurate. */
  onHasData?: (hasData: boolean) => void;
}

export default function OptionsBehaviorCard({ days, onHasData }: OptionsBehaviorCardProps) {
  const [data, setData] = useState<OptionsBehaviorData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api.get('/api/analytics/options-behavior', { params: { days } })
      .then(res => {
        if (cancelled) return;
        setData(res.data);
        onHasData?.(Boolean(res.data?.has_data));
      })
      .catch(() => {
        if (cancelled) return;
        setData(null);
        onHasData?.(false);
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
    // onHasData is a setState fn from the parent — stable, intentionally not a dep
  }, [days]); // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) return <Skeleton className="h-40 rounded-lg" />;

  // Nothing detected in the window — stay silent rather than render three zeroes.
  if (!data?.has_data) return null;

  const { direction_confusion: dc, premium_avg_down: ad, iv_crush: iv } = data;

  // Underlyings where direction flips concentrate — only meaningful above 1 flip.
  const topUnderlyings = Object.entries(dc.underlying_breakdown)
    .filter(([, n]) => n > 1)
    .slice(0, 3);

  const flipTime = formatMinutes(dc.avg_flip_minutes);
  const holdTime = formatMinutes(iv.avg_hold_minutes);

  return (
    <div className="tm-card overflow-hidden">
      <div className="px-5 py-3.5 border-b border-border">
        <p className="font-semibold text-sm">Options behaviour</p>
        <p className="text-[11px] text-muted-foreground mt-0.5">
          F&amp;O-specific patterns detected in the last {data.period_days} days.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 divide-y md:divide-y-0 md:divide-x divide-border">
        {/* Direction confusion — bought CE then PE (or reverse) on the same underlying */}
        <div className="px-5 py-4">
          <div className="flex items-center gap-1.5 mb-2">
            <Repeat className="h-3.5 w-3.5 text-tm-obs" />
            <span className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              Direction flips
            </span>
          </div>
          <p className="text-2xl font-mono font-black tabular-nums text-foreground">{dc.count}</p>
          {flipTime && (
            <p className="text-[12px] text-muted-foreground mt-1">
              {flipTime} average between opposite legs
            </p>
          )}
          {topUnderlyings.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-2.5">
              {topUnderlyings.map(([underlying, n]) => (
                <span
                  key={underlying}
                  className="text-[10px] text-muted-foreground border border-border rounded-full px-2 py-0.5"
                >
                  {underlying} {n}×
                </span>
              ))}
            </div>
          )}
          <p className="text-[11px] text-muted-foreground mt-2.5">
            Buying a call and a put on the same underlying minutes apart.
          </p>
        </div>

        {/* Premium averaging down — added to a losing option position */}
        <div className="px-5 py-4">
          <div className="flex items-center gap-1.5 mb-2">
            <TrendingDown className="h-3.5 w-3.5 text-tm-loss" />
            <span className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              Averaging down
            </span>
          </div>
          <p className="text-2xl font-mono font-black tabular-nums text-foreground">{ad.count}</p>
          {ad.total_re_entry_premium > 0 && (
            <p className="text-[12px] text-muted-foreground mt-1">
              <span className="font-mono tabular-nums text-foreground">
                {formatCurrencyWithSign(ad.total_re_entry_premium)}
              </span>{' '}
              added to losing positions
            </p>
          )}
          {ad.avg_worst_loss_pct !== null && (
            <p className="text-[12px] text-tm-loss mt-0.5 font-mono tabular-nums">
              {ad.avg_worst_loss_pct.toFixed(1)}% average worst drawdown
            </p>
          )}
          <p className="text-[11px] text-muted-foreground mt-2.5">
            Adding premium to an option already showing a loss.
          </p>
        </div>

        {/* IV crush — held an option through implied-volatility collapse */}
        <div className="px-5 py-4">
          <div className="flex items-center gap-1.5 mb-2">
            <Hourglass className="h-3.5 w-3.5 text-tm-obs" />
            <span className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              IV crush holds
            </span>
          </div>
          <p className="text-2xl font-mono font-black tabular-nums text-foreground">{iv.count}</p>
          {iv.total_loss > 0 && (
            <p className="text-[12px] text-muted-foreground mt-1">
              <span className="font-mono tabular-nums text-tm-loss">
                {formatCurrencyWithSign(-iv.total_loss)}
              </span>{' '}
              realized on these trades
            </p>
          )}
          {holdTime && (
            <p className="text-[12px] text-muted-foreground mt-0.5">
              {holdTime} average hold
              {iv.avg_loss_pct !== null && ` · ${iv.avg_loss_pct.toFixed(1)}% average loss`}
            </p>
          )}
          <p className="text-[11px] text-muted-foreground mt-2.5">
            Holding a long option while implied volatility collapsed.
          </p>
        </div>
      </div>
    </div>
  );
}
