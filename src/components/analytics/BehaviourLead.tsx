import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';

/**
 * DESIGN LAB — the one hero insight for Analytics.
 *
 * Built from docs/DESIGN_REFERENCES.md §3, the reflection-product research,
 * which is the section we had never applied:
 *
 *  - "One hero insight per screen, sized large. Everything else supports it."
 *    Analytics had a hero *number* and no hero insight.
 *  - "A detected pattern ships as plain-language sentence + the number + one
 *    concrete action. A correlation alone is the documented failure state."
 *    The ranked cost table underneath is exactly a correlation list — it says
 *    what happened and never what to do about it.
 *  - Oura's rationale: "more data without context or guidance often produces
 *    anxiety, not action." A page that opens with −₹24,080 and no next step is
 *    the anxiety version.
 *  - "State the rupee number, state the behaviour, do not editorialise."
 *    So: no adjectives, no encouragement, no grade. One fact, one action.
 *
 * Composition follows §4: "four equal cards stacked is the sparse-feeling
 * failure; four unequal regions with one dominant is not." This is the
 * dominant region — full-bleed band, everything below supports it.
 */

interface Row { pattern_type?: string; alert_count?: number; trade_count: number; realized_pnl: number }
interface Data { has_data: boolean; patterns: Row[]; pattern_totals: { trade_count: number; realized_pnl: number } }

const LABEL: Record<string, string> = {
  revenge_trade: 'revenge trades', rapid_reentry: 'rapid re-entries', overtrading: 'overtrading',
  size_escalation: 'oversized entries', martingale_behaviour: 'doubling down',
  consecutive_loss_streak: 'trading through loss streaks', panic_exit: 'panic exits',
  post_loss_recovery_bet: 'recovery bets after a loss', no_stoploss: 'trades without a stop-loss',
  fomo_entry: 'FOMO entries', chasing_entry: 'chased entries',
  direction_instability: 'flip-flopping direction', cooldown_violation: 'ignored cooldowns',
  winning_streak_overconfidence: 'overconfident sizing', early_exit: 'cutting winners early',
  profit_giveaway: 'giving profit back', session_meltdown: 'session meltdowns',
  daily_overtrading: 'overtrading', overtrading_burst: 'bursts of overtrading',
  expiry_day_overtrading: 'expiry-day overtrading',
};

/** The action is the rule that directly constrains the behaviour. */
const ACTION: Record<string, { text: string; to: string }> = {
  revenge_trade:                 { text: 'Set a cooldown after a loss', to: '/my-rules' },
  rapid_reentry:                 { text: 'Set a cooldown after a loss', to: '/my-rules' },
  cooldown_violation:            { text: 'Review your cooldown rule', to: '/my-rules' },
  post_loss_recovery_bet:        { text: 'Set a cooldown after a loss', to: '/my-rules' },
  overtrading:                   { text: 'Set a daily trade limit', to: '/my-rules' },
  daily_overtrading:             { text: 'Set a daily trade limit', to: '/my-rules' },
  overtrading_burst:             { text: 'Set a daily trade limit', to: '/my-rules' },
  expiry_day_overtrading:        { text: 'Set a daily trade limit', to: '/my-rules' },
  size_escalation:               { text: 'Set a max position size', to: '/my-rules' },
  martingale_behaviour:          { text: 'Set a max position size', to: '/my-rules' },
  winning_streak_overconfidence: { text: 'Set a max position size', to: '/my-rules' },
  consecutive_loss_streak:       { text: 'Set a consecutive-loss stop', to: '/my-rules' },
  session_meltdown:              { text: 'Set a daily loss limit', to: '/my-rules' },
  no_stoploss:                   { text: 'Check this against your record', to: '/my-record' },
};

const inr = (n: number) => (n < 0 ? '−' : '') + '₹' + Math.abs(Math.round(n)).toLocaleString('en-IN');

export default function BehaviourLead({ days }: { days: number }) {
  const [data, setData] = useState<Data | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api.get<Data>(`/api/analytics/behaviour-cost?days=${days}`)
      .then(r => { if (!cancelled) setData(r.data); })
      .catch(() => { if (!cancelled) setData(null); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [days]);

  if (loading || !data?.has_data) return null;

  // The single worst leak by realized money. Only losses qualify as the lead —
  // a profitable flagged pattern is not the thing to act on.
  const worst = [...(data.patterns ?? [])]
    .filter(p => p.realized_pnl < 0)
    .sort((a, b) => a.realized_pnl - b.realized_pnl)[0];
  if (!worst) return null;

  const key = worst.pattern_type ?? '';
  const name = LABEL[key] ?? key.replace(/_/g, ' ');
  const action = ACTION[key];
  const count = worst.alert_count ?? 0;

  return (
    <section className="rounded-lg border border-border bg-card overflow-hidden">

      <div className="px-5 sm:px-6 py-5">
        <span className="text-[11px] font-medium uppercase tracking-[0.12em] text-muted-foreground">
          Your biggest leak · last {days} days
        </span>

        {/* Sentence first, number inside it. Weight 400 at this size: the
            references put headings at 300–400, never bold. Leading tightens as
            size rises (Stripe 1.25 at 18px, Linear 1.6 at 15px). */}
        <p className="mt-2 text-[21px] sm:text-[23px] leading-[1.3] tracking-[-0.015em] text-foreground font-normal max-w-[46ch]">
          {count} {name} closed at{' '}
          <span className="text-tm-loss font-medium font-tabular">{inr(worst.realized_pnl)}</span>{' '}
          across {worst.trade_count} trade{worst.trade_count !== 1 ? 's' : ''}.
        </p>

        <p className="mt-2 text-[13px] leading-relaxed text-muted-foreground max-w-[60ch]">
          That is the realized P&amp;L of those exact trades — not an estimate of what they cost you.
        </p>

        {action && (
          <Link
            to={action.to}
            className={cn(
              'mt-4 inline-flex items-center gap-1.5 h-9 px-3.5 rounded-md',
              'text-[13px] font-medium text-primary-foreground bg-primary',
              'transition-colors duration-150 hover:bg-primary/90',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
            )}
          >
            {action.text}
            <span aria-hidden>→</span>
          </Link>
        )}
      </div>
    </section>
  );
}
