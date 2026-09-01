import { useEffect, useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';
import { formatCurrencyWhole } from '@/lib/formatters';
import { CardSkeleton } from '@/components/ui/skeletons';

/**
 * One list of rules: the limit in force, today's use of it, and a note only
 * when the enforced number is not the one that was typed.
 *
 * This replaces two sections that listed the same five rules — one for limits,
 * one for today's progress — which is the same duplication the Analytics hero
 * and KPI strip had. A rule is one thing; it gets one row.
 *
 * Why the enforced number can differ: a declared rule applies only when it is
 * stricter than what the trader's own baseline already produced. Declare 50
 * trades a day while averaging 6 and the engine enforces 6. Deliberate — a
 * stale value must not silently disable alerts — but the page used to show 50
 * and say nothing.
 */

type Source = 'declared' | 'learned' | 'default' | 'unset';

interface RuleRow { declared: number | null; effective: number | null; source: Source; overridden: boolean }
interface Effective { has_baseline: boolean; rules: Record<string, RuleRow>; ungoverned: Record<string, number> }
interface StatusRow { rule: string; current?: number; limit?: number | null; active?: boolean; remaining_min?: number }

const LABEL: Record<string, string> = {
  daily_loss_limit:       'Daily loss limit',
  per_trade_loss_limit:   'Per-trade loss limit',
  daily_trade_limit:      'Trades per day',
  max_position_size:      'Max risk per trade',
  max_consecutive_losses: 'Losses in a row',
  sl_percent_options:     'I exit a losing option at',
};

/** Rule key -> the status key reporting today's use of it. */
const TODAY_KEY: Record<string, string> = {
  daily_loss_limit: 'daily_loss',
  daily_trade_limit: 'daily_trades',
  max_consecutive_losses: 'max_consecutive_losses',
};

const MONEY = new Set(['daily_loss_limit', 'per_trade_loss_limit']);
/**
 * `max_position_size` IS A PERCENT OF CAPITAL, not an amount — the model says
 * so (`user_profile.py:84`) and the entry check divides a capital requirement
 * by `trading_capital` to compare against it. It sat in MONEY, so a trader who
 * had capped a trade at 10% of capital was told their limit was "₹10". A rule
 * shown in the wrong unit is a wrong rule.
 */
const PERCENT = new Set(['max_position_size', 'sl_percent_options']);
const MINUTES = new Set(['revenge_window_caution_min']);

function fmt(key: string, v: number | null | undefined): string {
  if (v == null) return 'Not set';
  if (MONEY.has(key)) return formatCurrencyWhole(v).replace('+', '');
  if (PERCENT.has(key)) return `${v}%`;
  if (MINUTES.has(key)) return `${v} min`;
  return String(v);
}

const UNGOVERNED_LABEL: Record<string, string> = {
  burst_trades_per_30min_caution: 'Trades in 30 minutes',
  consecutive_loss_caution:       'Losses in a row before a nudge',
  revenge_window_caution_min:     'Re-entry window after a loss',
  daily_trade_danger:             'Trades in a day before danger',
};

export default function EnforcedRules({ status = [] }: { status?: StatusRow[] }) {
  const [data, setData] = useState<Effective | null>(null);
  const [loading, setLoading] = useState(true);
  const [showMore, setShowMore] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api.get<Effective>('/api/constitution/effective')
      .then(r => { if (!cancelled) setData(r.data); })
      .catch(() => { if (!cancelled) setData(null); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  if (loading) return <CardSkeleton lines={5} />;
  if (!data?.rules) return null;

  const byRule = new Map(status.map(s => [s.rule, s]));
  const rows = Object.entries(data.rules).filter(([k]) => LABEL[k]);
  const ungoverned = Object.entries(data.ungoverned ?? {}).filter(([k]) => UNGOVERNED_LABEL[k]);

  return (
    <section className="tm-card overflow-hidden">
      <div className="px-5 py-3.5 border-b border-border">
        <p className="font-semibold text-[14px]">Your rules</p>
      </div>

      <div className="divide-y divide-border">
        {rows.map(([key, r]) => {
          const today = byRule.get(TODAY_KEY[key] ?? key);
          const used = today?.current;
          const limit = r.effective;
          const pct = used != null && limit ? Math.min((used / limit) * 100, 100) : null;
          const over = used != null && limit != null && used > limit;

          return (
            <div key={key} className="px-5 py-3 min-h-[44px] sm:min-h-0">
              <div className="flex items-baseline justify-between gap-3">
                <span className="text-[13.5px] text-foreground">{LABEL[key]}</span>
                <span className="text-[13.5px] font-tabular shrink-0">
                  {used != null && (
                    <span className={cn('font-medium', over ? 'text-tm-loss' : 'text-foreground')}>
                      {fmt(key, used)}
                    </span>
                  )}
                  {used != null && <span className="text-muted-foreground"> of </span>}
                  <span className={used != null ? 'text-muted-foreground' : 'font-medium text-foreground'}>
                    {fmt(key, limit)}
                  </span>
                </span>
              </div>

              {pct != null && (
                <div className="mt-1.5 h-1 rounded-full bg-muted overflow-hidden" aria-hidden>
                  {/* Never green: progress toward a limit is not a good thing. */}
                  <div
                    className={cn('h-full rounded-full transition-all',
                      over ? 'bg-tm-loss' : pct >= 75 ? 'bg-tm-obs' : 'bg-muted-foreground/40')}
                    style={{ width: `${pct}%` }}
                  />
                </div>
              )}

              {/* Only when the number in force is not the one that was typed. */}
              {r.overridden && (
                <p className="text-[11.5px] text-muted-foreground mt-1.5">
                  You set {fmt(key, r.declared)}. Your own trading runs tighter, so {fmt(key, limit)} applies.
                </p>
              )}
            </div>
          );
        })}
      </div>

      {ungoverned.length > 0 && (
        <>
          <button
            type="button"
            onClick={() => setShowMore(v => !v)}
            aria-expanded={showMore}
            className="w-full px-5 py-2.5 border-t border-border flex items-center justify-between text-[12px] text-muted-foreground hover:text-foreground hover:bg-muted/40 transition-colors"
          >
            <span>{ungoverned.length} more limits learned from your trading</span>
            <ChevronDown className={cn('h-3.5 w-3.5 transition-transform', showMore && 'rotate-180')} />
          </button>

          {showMore && (
            <div className="divide-y divide-border border-t border-border">
              {ungoverned.map(([key, v]) => (
                <div key={key} className="px-5 py-2.5 flex items-baseline justify-between gap-3">
                  <span className="text-[12.5px] text-muted-foreground">{UNGOVERNED_LABEL[key]}</span>
                  <span className="text-[12.5px] font-tabular text-foreground shrink-0">{fmt(key, v)}</span>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </section>
  );
}
