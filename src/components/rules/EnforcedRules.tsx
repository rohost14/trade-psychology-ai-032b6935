import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';
import { formatCurrencyWhole } from '@/lib/formatters';
import { CardSkeleton } from '@/components/ui/skeletons';

/**
 * What the engine actually enforces, and why it differs from what you typed.
 *
 * A declared rule is applied only when it is more restrictive than the
 * threshold already resolved from the trader's own behaviour. Declare 50 trades
 * a day while averaging 6 and the engine enforces 6. That is deliberate — a
 * stale value must not silently disable alerts — but the page used to display
 * 50 and say nothing, so it reported a rule that was not the one in force.
 *
 * It also lists the thresholds no rule can set. The old page rendered "no rule
 * set" beside them, which reads as "no limit exists" while one is being
 * enforced — the contradiction where "Cooldown after a loss: no rule set" sat
 * directly above a violation reading "cooldown is 15".
 */

type Source = 'declared' | 'learned' | 'default' | 'unset';

interface RuleRow {
  declared: number | null;
  effective: number | null;
  source: Source;
  overridden: boolean;
}

interface Effective {
  has_baseline: boolean;
  rules: Record<string, RuleRow>;
  ungoverned: Record<string, number>;
}

const RULE_LABEL: Record<string, string> = {
  daily_loss_limit:       'Daily loss limit',
  daily_trade_limit:      'Max trades per day',
  max_position_size:      'Max position size',
  cooldown_after_loss:    'Cooldown after a loss',
  max_consecutive_losses: 'Stop after consecutive losses',
};

const UNGOVERNED_LABEL: Record<string, string> = {
  burst_trades_per_30min_caution: 'Trades in 30 min before caution',
  burst_trades_per_30min_danger:  'Trades in 30 min before danger',
  consecutive_loss_caution:       'Losses in a row before caution',
  consecutive_loss_danger:        'Losses in a row before danger',
  revenge_window_caution_min:     'Re-entry window after a loss',
  daily_trade_danger:             'Trades in a day before danger',
};

const MONEY = new Set(['daily_loss_limit', 'max_position_size']);
const MINUTES = new Set(['cooldown_after_loss', 'revenge_window_caution_min']);

function fmt(key: string, v: number | null): string {
  if (v == null) return '—';
  if (MONEY.has(key)) return formatCurrencyWhole(v).replace('+', '');
  if (MINUTES.has(key)) return `${v} min`;
  return String(v);
}

const SOURCE_NOTE: Record<Source, string> = {
  declared: 'your rule',
  learned:  'from your own trading',
  default:  'default — you have not set one',
  unset:    'not set',
};

export default function EnforcedRules() {
  const [data, setData] = useState<Effective | null>(null);
  const [loading, setLoading] = useState(true);

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

  const entries = Object.entries(data.rules).filter(([k]) => RULE_LABEL[k]);
  const overridden = entries.filter(([, r]) => r.overridden);
  const ungoverned = Object.entries(data.ungoverned ?? {});

  return (
    <section className="tm-card overflow-hidden">
      <div className="px-5 py-3.5 border-b border-border">
        <p className="font-semibold text-[14px]">What is being enforced</p>
        <p className="text-[12px] text-muted-foreground mt-0.5">
          Your rule applies when it is stricter than what your own trading already shows.
        </p>
      </div>

      <div className="divide-y divide-border">
        {entries.map(([key, r]) => (
          <div key={key} className="px-5 py-3 min-h-[44px] sm:min-h-0">
            <div className="flex items-baseline justify-between gap-3">
              <span className="text-[13.5px] text-foreground">{RULE_LABEL[key]}</span>
              <span className="text-[13.5px] font-medium font-tabular text-foreground shrink-0">
                {fmt(key, r.effective)}
              </span>
            </div>
            <p className="text-[11.5px] text-muted-foreground mt-0.5">
              {r.overridden
                ? `You set ${fmt(key, r.declared)} — your trading averages tighter, so ${fmt(key, r.effective)} is enforced.`
                : SOURCE_NOTE[r.source]}
            </p>
          </div>
        ))}
      </div>

      {overridden.length > 0 && (
        <p className="px-5 py-3 border-t border-border text-[12px] text-muted-foreground bg-muted/40">
          {overridden.length === 1 ? 'One rule is' : `${overridden.length} rules are`}{' '}
          looser than your actual trading, so the tighter figure is used. Nothing is
          disabled by leaving a rule loose.
        </p>
      )}

      {ungoverned.length > 0 && (
        <div className="border-t border-border">
          <div className="px-5 py-3">
            <p className="text-[12.5px] font-medium text-foreground">Limits you cannot set</p>
            <p className="text-[11.5px] text-muted-foreground mt-0.5">
              Enforced from your own history. They move as your trading does.
            </p>
          </div>
          <div className="divide-y divide-border">
            {ungoverned.map(([key, v]) => (
              <div key={key} className="px-5 py-2.5 flex items-baseline justify-between gap-3">
                <span className="text-[12.5px] text-muted-foreground">
                  {UNGOVERNED_LABEL[key] ?? key.replace(/_/g, ' ')}
                </span>
                <span className={cn('text-[12.5px] font-tabular text-foreground shrink-0')}>
                  {fmt(key, v)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
