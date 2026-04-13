import { useState, useEffect } from 'react';
import { Moon } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { formatCurrencyWithSign } from '@/lib/formatters';
import { api } from '@/lib/api';
import { useBroker } from '@/contexts/BrokerContext';

interface BTSTTrade {
  id: string;
  tradingsymbol: string;
  instrument_type: string | null;
  entry_time: string;
  exit_time: string;
  direction: string;
  realized_pnl: number;
  avg_entry_price: number | null;
  overnight_close_price: number | null;
  was_profitable_at_eod: boolean | null;
  is_reversal: boolean;
  duration_minutes: number | null;
  hold_type: 'overnight' | 'weekend_hold';
}

interface BTSTData {
  has_data: boolean;
  period_days: number;
  total_btst_trades: number;
  btst_win_rate: number;
  btst_total_pnl: number;
  overnight_reversals: number;
  reversal_pnl_lost: number;
  trades: BTSTTrade[];
}

function fmtHold(min: number | null): string {
  if (min == null) return '—';
  if (min >= 1440) return `${Math.floor(min / 1440)}d ${Math.floor((min % 1440) / 60)}h`;
  if (min >= 60) return `${Math.floor(min / 60)}h ${min % 60}m`;
  return `${min}m`;
}

export default function BtstTab({ days }: { days: number }) {
  const { account } = useBroker();
  const [data, setData] = useState<BTSTData | null>(null);
  const [loading, setLoading] = useState(true);
  const [showAll, setShowAll] = useState(false);

  useEffect(() => {
    if (!account?.id) return;
    setLoading(true);
    setData(null);
    let cancelled = false;
    api.get('/api/analytics/btst', { params: { days, broker_account_id: account.id } })
      .then(r => { if (!cancelled) { setData(r.data); setLoading(false); } })
      .catch(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [days, account?.id]);

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[1, 2, 3, 4].map(i => <Skeleton key={i} className="h-20 rounded-xl" />)}
        </div>
        <Skeleton className="h-64 rounded-xl" />
      </div>
    );
  }

  if (!data?.has_data) {
    return (
      <div className="tm-card overflow-hidden p-10 text-center">
        <Moon className="h-8 w-8 text-muted-foreground/40 mx-auto mb-3" />
        <p className="text-sm font-medium">No BTST trades in the last {days} days</p>
        <p className="text-xs text-muted-foreground mt-1 max-w-xs mx-auto">
          BTST trades are NRML positions entered after 15:00 IST and exited before 09:45 IST the next trading day.
        </p>
      </div>
    );
  }

  const {
    total_btst_trades, btst_win_rate, btst_total_pnl,
    overnight_reversals, reversal_pnl_lost, trades,
  } = data;

  const visible = showAll ? trades : trades.slice(0, 10);

  return (
    <div className="space-y-5">
      {/* Summary grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          {
            label: 'BTST Trades', value: String(total_btst_trades),
            sub: `Last ${days} days`, cls: 'text-foreground',
          },
          {
            label: 'Win Rate', value: `${btst_win_rate}%`,
            sub: `${trades.filter(t => t.realized_pnl > 0).length} winners`,
            cls: btst_win_rate >= 50 ? 'text-tm-profit' : 'text-tm-loss',
          },
          {
            label: 'Total P&L', value: formatCurrencyWithSign(btst_total_pnl),
            sub: 'All BTST combined',
            cls: btst_total_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss',
          },
          {
            label: 'Overnight Reversals', value: String(overnight_reversals),
            sub: overnight_reversals > 0 ? `₹${Math.abs(reversal_pnl_lost).toLocaleString('en-IN', { maximumFractionDigits: 0 })} lost` : 'None',
            cls: overnight_reversals > 0 ? 'text-tm-obs' : 'text-foreground',
          },
        ].map(({ label, value, sub, cls }) => (
          <div key={label} className="tm-card overflow-hidden p-4">
            <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide mb-1">{label}</p>
            <p className={cn('text-2xl font-semibold font-mono tabular-nums', cls)}>{value}</p>
            <p className="text-[11px] text-muted-foreground mt-0.5">{sub}</p>
          </div>
        ))}
      </div>

      {/* Context blurb */}
      <div className="rounded-lg bg-indigo-50/60 dark:bg-indigo-950/20 border border-indigo-100 dark:border-indigo-900/40 px-4 py-3">
        <div className="flex items-start gap-2">
          <Moon className="h-3.5 w-3.5 text-indigo-500 mt-0.5 flex-shrink-0" />
          <p className="text-[12px] text-muted-foreground leading-relaxed">
            BTST trades are late-day NRML entries held overnight — a behavioural signal worth tracking.
            Friday entries carry 2 extra theta days on options. <strong className="text-foreground">Overnight reversals</strong> are the most damaging pattern:
            the position was profitable at market close, but you woke up to a loss.
          </p>
        </div>
      </div>

      {/* Trade table */}
      {trades.length > 0 && (
        <div className="tm-card overflow-hidden">
          <div className="px-5 py-3 border-b border-border">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
              BTST Trade History
            </p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border">
                  {['Symbol', 'Entry Date', 'Hold', 'P&L', 'Outcome'].map((h, i) => (
                    <th
                      key={h}
                      className={cn(
                        'py-2.5 text-[11px] font-semibold text-muted-foreground uppercase tracking-wide',
                        i === 0 ? 'px-5 text-left' : 'px-4 text-right'
                      )}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {visible.map(t => (
                  <tr
                    key={t.id}
                    className={cn(
                      'border-b border-border/50 hover:bg-muted/30 transition-colors',
                      t.is_reversal && 'bg-amber-50/30 dark:bg-amber-950/10',
                    )}
                  >
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-1.5">
                        {t.hold_type === 'weekend_hold' && (
                          <span className="text-[10px] bg-indigo-100 dark:bg-indigo-900/40 text-indigo-600 dark:text-indigo-400 px-1.5 py-0.5 rounded font-semibold">
                            WE
                          </span>
                        )}
                        <span className="text-sm font-medium font-mono">{t.tradingsymbol}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right text-xs text-muted-foreground font-mono">
                      {t.entry_time
                        ? new Date(t.entry_time).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' })
                        : '—'}
                    </td>
                    <td className="px-4 py-3 text-right text-xs text-muted-foreground font-mono tabular-nums">
                      {fmtHold(t.duration_minutes)}
                    </td>
                    <td className={cn(
                      'px-4 py-3 text-right text-sm font-mono tabular-nums font-semibold',
                      t.realized_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss',
                    )}>
                      {formatCurrencyWithSign(t.realized_pnl)}
                    </td>
                    <td className="px-4 py-3 text-right text-xs">
                      {t.is_reversal ? (
                        <span className="text-tm-obs font-semibold">↓ Reversed</span>
                      ) : t.was_profitable_at_eod === true ? (
                        <span className="text-tm-profit">Held well</span>
                      ) : t.was_profitable_at_eod === false ? (
                        <span className="text-tm-loss">EOD loss</span>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {trades.length > 10 && (
            <div className="px-5 py-3 border-t border-border">
              <button
                onClick={() => setShowAll(v => !v)}
                className="text-xs font-medium text-tm-brand hover:underline"
              >
                {showAll ? 'Show less' : `Show all ${trades.length} BTST trades`}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
