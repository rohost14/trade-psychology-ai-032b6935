import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';
import { formatCurrencyWithSign } from '@/lib/formatters';
import { CardSkeleton } from '@/components/ui/skeletons';

/**
 * DESIGN LAB — the P&L calendar, extracted from SessionsTab and promoted.
 *
 * It was the last block on Advanced, the least-visited tab, rendered outside
 * the card system with a Profit/Loss legend that floated above three cards and
 * belonged to none of them.
 *
 * It is moved because of what it answers. The trading-journal literature puts it
 * bluntly: a list of trades tells you which trades won; a calendar tells you
 * *when you trade well*. For a behavioural product that is the central
 * question, not an advanced one — so it sits on Behaviour, under the money.
 *
 * Changes made in the move:
 *  - Colour comes from the profit/loss tokens rather than the raw rgba(22,163,74)
 *    and rgba(220,38,38) it carried, which were a different green and red from
 *    everything around them.
 *  - The legend moves inside the card header it describes.
 *  - Day values use a true minus, matching the rest of the app.
 */

interface DailyPnl { date: string; pnl: number; trades: number }
interface OverviewResponse { daily_pnl?: DailyPnl[] }

interface Day { date: string; pnl: number; trades: number; isWeekend: boolean }
interface Month { year: number; month: number; days: Day[] }

/** Months the selected period actually touches — never a fixed three. */
function monthsForPeriod(days: number): number {
  const today = new Date();
  const start = new Date(today.getFullYear(), today.getMonth(), today.getDate() - Math.max(0, days - 1));
  return Math.max(1, (today.getFullYear() - start.getFullYear()) * 12 + (today.getMonth() - start.getMonth()) + 1);
}

function buildCalendar(dailyPnl: DailyPnl[], monthsToShow: number): Month[] {
  const byDate: Record<string, { pnl: number; trades: number }> = {};
  for (const d of dailyPnl) byDate[d.date.slice(0, 10)] = { pnl: d.pnl, trades: d.trades };

  const today = new Date();
  const months: Month[] = [];
  for (let mo = monthsToShow - 1; mo >= 0; mo--) {
    const d = new Date(today.getFullYear(), today.getMonth() - mo, 1);
    const year = d.getFullYear();
    const month = d.getMonth();
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const days: Day[] = [];
    for (let day = 1; day <= daysInMonth; day++) {
      const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
      const dow = new Date(year, month, day).getDay();
      days.push({
        date: dateStr,
        pnl: byDate[dateStr]?.pnl ?? 0,
        trades: byDate[dateStr]?.trades ?? 0,
        isWeekend: dow === 0 || dow === 6,
      });
    }
    months.push({ year, month, days });
  }
  return months;
}

/** Intensity by magnitude, hue from the tokens rather than a literal. */
function cellBg(pnl: number, maxAbs: number): string {
  if (pnl === 0) return 'rgb(var(--muted) / 0.5)';
  const weight = Math.min(1, Math.abs(pnl) / Math.max(maxAbs, 1));
  const alpha = 0.18 + weight * 0.55;
  return pnl > 0 ? `rgb(var(--tm-profit) / ${alpha})` : `rgb(var(--tm-loss) / ${alpha})`;
}

function CalendarMonth({ year, month, days, maxAbs }: Month & { maxAbs: number }) {
  const firstDow = new Date(year, month, 1).getDay();
  const blanks = firstDow === 0 ? 6 : firstDow - 1; // Monday-first grid
  const monthName = new Date(year, month, 1).toLocaleString('en-IN', { month: 'long', year: 'numeric' });
  const tradingDays = days.filter(d => d.trades > 0);
  const profitDays = tradingDays.filter(d => d.pnl > 0).length;

  return (
    <div>
      <div className="flex items-baseline justify-between px-1 pb-2">
        <span className="text-[12.5px] font-medium text-foreground">{monthName}</span>
        {tradingDays.length > 0 && (
          <span className="text-[11px] text-muted-foreground font-tabular">
            {profitDays}/{tradingDays.length} profitable
          </span>
        )}
      </div>

      <div className="grid grid-cols-7 mb-1">
        {['M', 'T', 'W', 'T', 'F', 'S', 'S'].map((d, i) => (
          <div key={i} className="text-center text-[10px] text-muted-foreground py-0.5">{d}</div>
        ))}
      </div>

      <div className="grid grid-cols-7 gap-px">
        {Array.from({ length: blanks }).map((_, i) => <div key={`b${i}`} className="min-h-[38px]" />)}
        {days.map(d => (
          <div
            key={d.date}
            className={cn(
              'min-h-[38px] rounded-sm flex flex-col items-center justify-center',
              d.isWeekend && d.trades === 0 && 'opacity-30',
            )}
            style={{ backgroundColor: d.trades > 0 ? cellBg(d.pnl, maxAbs) : undefined }}
            title={d.trades > 0
              ? `${d.date}: ${formatCurrencyWithSign(Math.round(d.pnl))} · ${d.trades} trade${d.trades !== 1 ? 's' : ''}`
              : d.date}
          >
            <span className="text-[10px] text-muted-foreground leading-none">{parseInt(d.date.slice(8), 10)}</span>
            {d.trades > 0 && (
              <span className={cn('text-[9px] font-tabular leading-none mt-0.5 font-medium',
                d.pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
                {d.pnl >= 0 ? '+' : '−'}{Math.abs(Math.round(d.pnl / 1000))}k
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

export default function PnlCalendar({ days }: { days: number }) {
  const [daily, setDaily] = useState<DailyPnl[] | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api.get<OverviewResponse>(`/api/analytics/overview?days=${days}`)
      .then(r => { if (!cancelled) setDaily(r.data?.daily_pnl ?? []); })
      .catch(() => { if (!cancelled) setDaily(null); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [days]);

  if (loading) return <CardSkeleton lines={4} />;
  if (!daily?.length) return null;

  const months = buildCalendar(daily, monthsForPeriod(days));
  const maxAbs = Math.max(...daily.map(d => Math.abs(d.pnl)), 1);

  return (
    <section className="tm-card overflow-hidden">
      <div className="px-5 py-3.5 border-b border-border flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="font-semibold text-sm">When you trade well</p>
          <p className="text-[11.5px] text-muted-foreground mt-0.5">
            Each day shaded by that day&apos;s realized P&amp;L.
          </p>
        </div>
        {/* Legend lives in the header of the card it describes, not floating
            above three cards belonging to none of them. */}
        <div className="flex items-center gap-3 text-[10px] text-muted-foreground shrink-0">
          <span className="flex items-center gap-1">
            <span className="w-3 h-3 rounded-sm" style={{ backgroundColor: 'rgb(var(--tm-profit) / 0.55)' }} /> Profit
          </span>
          <span className="flex items-center gap-1">
            <span className="w-3 h-3 rounded-sm" style={{ backgroundColor: 'rgb(var(--tm-loss) / 0.55)' }} /> Loss
          </span>
        </div>
      </div>

      <div className="p-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
        {months.map(m => (
          <CalendarMonth key={`${m.year}-${m.month}`} {...m} maxAbs={maxAbs} />
        ))}
      </div>
    </section>
  );
}
