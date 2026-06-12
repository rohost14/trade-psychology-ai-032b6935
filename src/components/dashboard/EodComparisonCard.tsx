import { useState, useEffect } from 'react';
import { CheckCircle2, XCircle, TrendingUp } from 'lucide-react';
import { cn } from '@/lib/utils';
import { api } from '@/lib/api';
import { formatCurrencyWithSign } from '@/lib/formatters';
import { useBroker } from '@/contexts/BrokerContext';

interface IntentData {
  has_session: boolean;
  intent_acknowledged: boolean;
  planned: { max_trades: number | null; max_loss: number | null };
  actual: { trades: number; pnl: number };
  comparison: {
    trades_ok: boolean;
    loss_ok: boolean;
    respected: boolean;
    trades_over: number;
    loss_over: number;
  } | null;
}

function getIST(): { hour: number; minute: number; isWeekday: boolean } {
  const now = new Date();
  const ist = new Date(now.getTime() + now.getTimezoneOffset() * 60000 + (5 * 60 + 30) * 60000);
  return {
    hour: ist.getHours(),
    minute: ist.getMinutes(),
    isWeekday: ist.getDay() >= 1 && ist.getDay() <= 5,
  };
}

function RuleRow({
  label,
  planned,
  actual,
  ok,
  unit,
}: {
  label: string;
  planned: string;
  actual: string;
  ok: boolean;
  unit?: string;
}) {
  return (
    <div className="flex items-center gap-3 py-3 border-b border-border last:border-0">
      <div className={cn(
        'shrink-0 w-7 h-7 rounded-full flex items-center justify-center',
        ok ? 'bg-green-500/10' : 'bg-red-500/10'
      )}>
        {ok
          ? <CheckCircle2 className="h-4 w-4 text-green-600 dark:text-green-400" />
          : <XCircle className="h-4 w-4 text-red-600 dark:text-red-400" />
        }
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-xs text-muted-foreground">{label}</p>
        <div className="flex items-center gap-2 mt-0.5">
          <span className="text-xs font-mono text-muted-foreground">Planned {planned}</span>
          <span className="text-xs text-muted-foreground">→</span>
          <span className={cn(
            'text-sm font-mono font-semibold',
            ok ? 'text-tm-profit' : 'text-tm-loss'
          )}>
            {actual}{unit}
          </span>
        </div>
      </div>
    </div>
  );
}

export function EodComparisonCard() {
  const { account } = useBroker();
  const [data, setData]     = useState<IntentData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!account?.id) return;
    api.get('/api/session-intent/today')
      .then(r => setData(r.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [account?.id]);

  // Show after market close (3:30 PM IST) on weekdays
  const { hour, minute, isWeekday } = getIST();
  const show = isWeekday && (hour > 15 || (hour === 15 && minute >= 30));

  if (!show || loading || !data) return null;
  if (!data.intent_acknowledged || !data.comparison) return null;

  const { comparison, planned, actual } = data;
  const pnlLabel = formatCurrencyWithSign(actual.pnl);

  return (
    <div className={cn(
      'tm-card overflow-hidden',
      comparison.respected
        ? 'border-green-500/30 bg-green-500/[0.03]'
        : 'border-red-500/20 bg-red-500/[0.02]'
    )}>
      {/* Header */}
      <div className={cn(
        'px-5 py-3.5 border-b flex items-center justify-between',
        comparison.respected ? 'border-green-500/20' : 'border-red-500/20'
      )}>
        <div>
          <p className="text-sm font-semibold text-foreground">
            {comparison.respected ? 'Plan respected ✓' : "Today's debrief"}
          </p>
          <p className="text-xs text-muted-foreground mt-0.5">
            {comparison.respected
              ? 'You traded within your limits today.'
              : 'You exceeded your limits today.'}
          </p>
        </div>
        <div className={cn(
          'shrink-0 w-9 h-9 rounded-full flex items-center justify-center',
          comparison.respected ? 'bg-green-500/10' : 'bg-red-500/10'
        )}>
          {comparison.respected
            ? <TrendingUp className="h-5 w-5 text-green-600 dark:text-green-400" />
            : <XCircle className="h-5 w-5 text-red-600 dark:text-red-400" />
          }
        </div>
      </div>

      {/* P&L hero */}
      <div className="px-5 py-4 border-b border-border text-center">
        <p className={cn(
          'text-3xl font-bold font-mono tabular-nums',
          actual.pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss'
        )}>
          {pnlLabel}
        </p>
        <p className="text-xs text-muted-foreground mt-1">Session P&L</p>
      </div>

      {/* Rule-by-rule comparison */}
      <div className="px-5">
        {planned.max_trades != null && (
          <RuleRow
            label="Trade count"
            planned={`${planned.max_trades}`}
            actual={`${actual.trades}`}
            ok={comparison.trades_ok}
          />
        )}
        {planned.max_loss != null && (
          <RuleRow
            label="Loss limit"
            planned={`₹${planned.max_loss.toLocaleString('en-IN')}`}
            actual={formatCurrencyWithSign(actual.pnl)}
            ok={comparison.loss_ok}
          />
        )}
      </div>

      {/* Encouragement footer */}
      <div className="px-5 py-4">
        <p className="text-xs text-muted-foreground text-center">
          {comparison.respected
            ? 'Consistency builds edge. Same discipline tomorrow.'
            : 'Every debrief is data. Adjust and reset tomorrow.'}
        </p>
      </div>
    </div>
  );
}
