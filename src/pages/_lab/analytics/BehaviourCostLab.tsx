/**
 * DESIGN LAB — the ranked cost leak, given Kite's table treatment.
 *
 * From docs/DESIGN_REFERENCES.md §1, mined from Kite's production CSS:
 *  - cell padding 10px 12px, the real production value
 *  - tabular-nums on every cell
 *  - a permanent tint band on the P&L *column*, and NO zebra striping anywhere.
 *    Kite separates the region that matters instead of decorating every row,
 *    which is the calmer borrow and the one we had not taken.
 *  - rows reach 44px on mobile (WCAG 2.5.8 target size), 40px above sm
 *
 * The header also loses its icon: the reference set treats an icon as carrying
 * meaning or being deleted, and a warning triangle beside the words "Behaviour
 * → your money" adds a tone we explicitly do not want.
 *
 * Original behaviour → your money. The raw realized P&L of the exact completed trades that each
 * behavioural alert / broken personal rule fired on (via the trigger_completed_trade_id the
 * engine already stores). FACTUAL — deliberately framed as "realized P&L on flagged trades",
 * never "cost", so it can't be read as a causal claim that the behaviour caused the loss.
 */
import { useEffect, useState } from 'react';
import { Scale } from 'lucide-react';
import { api } from '@/lib/api';

interface Row { pattern_type?: string; rule?: string; alert_count?: number; breach_count?: number; trade_count: number; realized_pnl: number; }
interface Totals { trade_count: number; realized_pnl: number; }
interface Data {
  has_data: boolean;
  patterns: Row[]; pattern_totals: Totals;
  rules: Row[]; rule_totals: Totals;
}

const PATTERN_LABEL: Record<string, string> = {
  revenge_trade: 'Revenge trading', rapid_reentry: 'Rapid re-entry', overtrading: 'Overtrading',
  size_escalation: 'Size escalation', martingale_behaviour: 'Martingale (doubling down)',
  consecutive_loss_streak: 'Trading through a loss streak', panic_exit: 'Panic exit',
  post_loss_recovery_bet: 'Recovery bet after a loss', no_stoploss: 'No stop-loss',
  fomo_entry: 'FOMO entry', chasing_entry: 'Chasing entries', direction_instability: 'Flip-flopping direction',
  cooldown_violation: 'Cooldown ignored', winning_streak_overconfidence: 'Overconfidence on a streak',
  early_exit: 'Cutting winners early', profit_giveaway: 'Giving profit back',
  session_meltdown: 'Session meltdown', daily_overtrading: 'Overtrading (daily)',
  overtrading_burst: 'Overtrading burst', expiry_day_overtrading: 'Expiry-day overtrading',
  constitution_violation: 'Own rule broken',
};
const RULE_LABEL: Record<string, string> = {
  cooldown_after_loss: 'Cooldown after a loss', daily_trade_limit: 'Daily trade limit',
  max_consecutive_losses: 'Consecutive-loss stop', restricted_windows: 'Restricted time windows',
  daily_loss_limit: 'Daily loss limit', max_position_size: 'Max position size',
};
// Sentence-case the fallback so a detector missing from the map above still
// reads as a label rather than a database key.
const humanise = (k: string) => {
  const words = k.replace(/_/g, ' ');
  return words.charAt(0).toUpperCase() + words.slice(1);
};
const labelPattern = (k?: string) => (k && PATTERN_LABEL[k]) || (k ? humanise(k) : '—');
const labelRule = (k?: string) => (k && RULE_LABEL[k]) || (k ? humanise(k) : '—');

// U+2212 minus, not an ASCII hyphen — matches every other money figure in the
// app. Visible here because these rows are now the first thing on Analytics.
const inr = (n: number) => (n < 0 ? '−' : '') + '₹' + Math.abs(Math.round(n)).toLocaleString('en-IN');
const pnlClass = (n: number) => (n >= 0 ? 'text-tm-profit' : 'text-tm-loss');

function Section({ title, totals, unitLabel, rows, label }: {
  title: string; totals: Totals; unitLabel: string; rows: Row[]; label: (k?: string) => string;
}) {
  if (!rows.length) return null;
  return (
    <div>
      <div className="flex items-baseline justify-between mb-3">
        <span className="text-[13px] font-semibold text-foreground">{title}</span>
        <span className="text-xs text-muted-foreground">
          {totals.trade_count} trades · net <span className={pnlClass(totals.realized_pnl)}>{inr(totals.realized_pnl)}</span>
        </span>
      </div>
      <div className="space-y-2">
        {rows.map((r, i) => {
          const count = r.alert_count ?? r.breach_count ?? 0;
          return (
            <div key={i} className="flex items-stretch justify-between border-b border-border last:border-0 min-h-[44px] sm:min-h-[40px]">
              <div className="min-w-0 flex flex-col justify-center py-2.5 pr-3">
                <span className="text-[13px] font-medium text-foreground">{label(r.pattern_type ?? r.rule)}</span>
                <span className="text-[11px] text-muted-foreground ml-2">
                  {count} {count === 1 ? unitLabel.replace(/e?s$/, '') : unitLabel} · {r.trade_count} trade{r.trade_count !== 1 ? 's' : ''}
                </span>
              </div>
              {/* Permanent tint on the money column, Kite-style — the region
                  that matters is separated, rather than every row striped. */}
              <span className={`flex items-center justify-end text-[13px] font-semibold tabular-nums shrink-0 w-[116px] px-3 -my-px bg-muted/40 ${pnlClass(r.realized_pnl)}`}>
                {inr(r.realized_pnl)}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function BehaviourCostCard({ days = 90 }: { days?: number }) {
  const [data, setData] = useState<Data | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api.get<Data>(`/api/analytics/behaviour-cost?days=${days}`)
      .then(res => { if (!cancelled) setData(res.data); })
      .catch(() => { if (!cancelled) setData(null); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [days]);

  if (loading) return null;
  if (!data || !data.has_data) return null;

  return (
    <div className="tm-card overflow-hidden">
      <div className="px-5 py-3.5 border-b border-border">
        <p className="text-sm font-semibold text-foreground flex items-center gap-2">
Behaviour → your money
        </p>
        <p className="text-xs text-muted-foreground mt-0.5">
          Realized P&amp;L on the exact trades we flagged. A fact — not a claim the behaviour caused it.
        </p>
      </div>

      <div className="p-5 space-y-6">
        <Section
          title="Flagged patterns"
          totals={data.pattern_totals}
          unitLabel="alerts"
          rows={data.patterns}
          label={labelPattern}
        />

        {data.rules.length > 0 && (
          <div className="pt-1 border-t border-border">
            <div className="flex items-center gap-2 mb-3 pt-4">
              <Scale className="h-4 w-4 text-tm-brand" />
              <span className="text-[13px] font-semibold text-foreground">Against your own rules</span>
            </div>
            <Section
              title="Rules you broke"
              totals={data.rule_totals}
              unitLabel="breaches"
              rows={data.rules}
              label={labelRule}
            />
          </div>
        )}


      </div>
    </div>
  );
}
