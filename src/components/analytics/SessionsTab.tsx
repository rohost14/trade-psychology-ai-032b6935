import { useState, useEffect } from 'react';
import { RefreshCw, AlertTriangle, Clock } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { formatCurrencyWithSign } from '@/lib/formatters';
import { api } from '@/lib/api';

interface SessionsTabProps { days: number }

interface OverviewData {
  has_data: boolean;
  daily_pnl: { date: string; pnl: number; trades: number; win_rate: number }[];
}

interface ExpiryData {
  has_data: boolean;
  period_days: number;
  expiry: { trade_count: number; win_rate: number; avg_pnl: number; total_pnl: number };
  non_expiry: { trade_count: number; win_rate: number; avg_pnl: number; total_pnl: number };
  by_hour: { hour: number; label: string; expiry_count: number; expiry_avg_pnl: number; non_expiry_count: number; non_expiry_avg_pnl: number }[];
  worst_expiry_trades: { symbol: string; pnl: number; hour: number }[];
}

interface ConditionalData {
  has_data: boolean;
  first_30min: { trades: number; win_rate: number; avg_pnl: number; baseline_win_rate?: number; baseline_avg_pnl?: number };
  expiry_day: { trades: number; win_rate: number; avg_pnl: number; baseline_win_rate?: number; baseline_avg_pnl?: number };
}

function pnlColorClass(pnl: number) {
  if (pnl > 0) return 'text-tm-profit';
  if (pnl < 0) return 'text-tm-loss';
  return 'text-muted-foreground';
}

function calendarBg(pnl: number, trades: number) {
  if (trades === 0) return '';
  const intensity = Math.min(1, Math.abs(pnl) / 5000);
  if (pnl > 0) return `rgba(22,163,74,${0.1 + intensity * 0.45})`;
  return `rgba(220,38,38,${0.1 + intensity * 0.45})`;
}

const MONTHS_TO_SHOW = 3;

function buildCalendar(dailyPnl: OverviewData['daily_pnl']) {
  const byDate: Record<string, { pnl: number; trades: number }> = {};
  for (const d of dailyPnl) {
    byDate[d.date.slice(0, 10)] = { pnl: d.pnl, trades: d.trades };
  }

  const today  = new Date();
  const months: { year: number; month: number; days: { date: string; pnl: number; trades: number; isWeekend: boolean }[] }[] = [];

  for (let mo = MONTHS_TO_SHOW - 1; mo >= 0; mo--) {
    const d = new Date(today.getFullYear(), today.getMonth() - mo, 1);
    const year = d.getFullYear();
    const month = d.getMonth();
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const days = [];
    for (let day = 1; day <= daysInMonth; day++) {
      const dateStr = `${year}-${String(month + 1).padStart(2,'0')}-${String(day).padStart(2,'0')}`;
      const dow = new Date(year, month, day).getDay();
      const isWeekend = dow === 0 || dow === 6;
      days.push({
        date: dateStr,
        pnl: byDate[dateStr]?.pnl ?? 0,
        trades: byDate[dateStr]?.trades ?? 0,
        isWeekend,
      });
    }
    months.push({ year, month, days });
  }
  return months;
}

function CalendarMonth({ year, month, days }: { year: number; month: number; days: { date: string; pnl: number; trades: number; isWeekend: boolean }[] }) {
  const firstDow = new Date(year, month, 1).getDay();
  const blanks   = firstDow === 0 ? 6 : firstDow - 1; // Mon-first grid
  const monthName = new Date(year, month, 1).toLocaleString('en-IN', { month: 'long', year: 'numeric' });
  const tradingDays = days.filter(d => d.trades > 0);
  const profitDays  = tradingDays.filter(d => d.pnl > 0).length;

  return (
    <div className="tm-card overflow-hidden">
      <div className="px-4 py-3 border-b border-border flex items-center justify-between">
        <p className="font-semibold text-sm">{monthName}</p>
        {tradingDays.length > 0 && (
          <span className="text-xs text-muted-foreground">
            {profitDays}/{tradingDays.length} days profitable
          </span>
        )}
      </div>
      <div className="p-3">
        {/* Day headers */}
        <div className="grid grid-cols-7 mb-1">
          {['M','T','W','T','F','S','S'].map((d, i) => (
            <div key={i} className="text-center text-[9px] text-muted-foreground py-1">{d}</div>
          ))}
        </div>
        {/* Day cells */}
        <div className="grid grid-cols-7 gap-px">
          {Array.from({ length: blanks }).map((_, i) => <div key={`b${i}`} />)}
          {days.map(d => (
            <div
              key={d.date}
              className={cn(
                'aspect-square rounded-sm flex flex-col items-center justify-center',
                d.isWeekend ? 'opacity-25' : '',
              )}
              style={{ backgroundColor: d.trades > 0 ? calendarBg(d.pnl, d.trades) : undefined }}
              title={d.trades > 0 ? `${d.date}: ${formatCurrencyWithSign(Math.round(d.pnl))} · ${d.trades} trades` : d.date}
            >
              <span className="text-[9px] text-muted-foreground leading-none">{parseInt(d.date.slice(8))}</span>
              {d.trades > 0 && (
                <span className={cn('text-[7px] font-mono leading-none mt-0.5', pnlColorClass(d.pnl))}>
                  {d.pnl >= 0 ? '+' : ''}{Math.round(d.pnl / 1000)}k
                </span>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function SessionsTab({ days }: SessionsTabProps) {
  const [overview, setOverview]   = useState<OverviewData | null>(null);
  const [expiry, setExpiry]       = useState<ExpiryData | null>(null);
  const [conditional, setCond]    = useState<ConditionalData | null>(null);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState<string | null>(null);
  const [retry, setRetry]         = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.allSettled([
      api.get('/api/analytics/overview',              { params: { days: 90 } }),
      api.get('/api/analytics/expiry-pattern',        { params: { days } }),
      api.get('/api/analytics/conditional-performance', { params: { days } }),
    ]).then(([ov, ex, co]) => {
      if (cancelled) return;
      if (ov.status === 'fulfilled') setOverview(ov.value.data);
      if (ex.status === 'fulfilled') setExpiry(ex.value.data);
      if (co.status === 'fulfilled') setCond(co.value.data);
      if (ov.status === 'rejected') setError('Failed to load session data.');
    }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [days, retry]);

  if (loading) return (
    <div className="space-y-4 animate-pulse">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Skeleton className="h-[220px] rounded-xl" />
        <Skeleton className="h-[220px] rounded-xl" />
        <Skeleton className="h-[220px] rounded-xl" />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <Skeleton className="h-28 rounded-xl" />
        <Skeleton className="h-28 rounded-xl" />
      </div>
      <Skeleton className="h-[180px] rounded-xl" />
    </div>
  );

  if (error) return (
    <div className="tm-card flex flex-col items-center py-16 text-center">
      <AlertTriangle className="h-8 w-8 text-tm-loss mb-3" />
      <p className="font-medium">{error}</p>
      <button onClick={() => setRetry(r => r + 1)} className="mt-4 text-sm text-tm-brand hover:underline flex items-center gap-1.5">
        <RefreshCw className="h-3.5 w-3.5" /> Try again
      </button>
    </div>
  );

  const calendarMonths = overview?.daily_pnl ? buildCalendar(overview.daily_pnl) : [];
  const first30 = conditional?.has_data ? conditional.first_30min : null;
  const expiryDay = conditional?.has_data ? conditional.expiry_day : null;

  return (
    <div className="space-y-5">

      {/* P&L Calendar */}
      {calendarMonths.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-3">
            <p className="font-semibold text-sm">3-Month P&L Calendar</p>
            <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
              <div className="flex items-center gap-1"><div className="w-3 h-3 rounded-sm" style={{ backgroundColor: 'rgba(22,163,74,0.5)' }} /> Profit</div>
              <div className="flex items-center gap-1"><div className="w-3 h-3 rounded-sm" style={{ backgroundColor: 'rgba(220,38,38,0.5)' }} /> Loss</div>
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {calendarMonths.map(m => (
              <CalendarMonth key={`${m.year}-${m.month}`} year={m.year} month={m.month} days={m.days} />
            ))}
          </div>
        </div>
      )}

      {/* Opening Trap + Expiry Day */}
      {(first30 || expiryDay) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

          {first30 && first30.trades > 0 && (
            <div className={cn(
              'tm-card overflow-hidden border-l-4',
              first30.win_rate < (first30.baseline_win_rate ?? 50) - 5 ? 'border-l-tm-loss' : 'border-l-tm-profit',
            )}>
              <div className="px-4 pt-4 pb-1 flex items-center gap-2">
                <Clock className="h-4 w-4 text-muted-foreground" />
                <p className="text-xs text-muted-foreground uppercase tracking-wide">Opening 30 Minutes (9:15–9:45)</p>
              </div>
              <div className="px-4 pb-4">
                <div className="flex items-end gap-2 my-2">
                  <span className={cn(
                    'text-4xl font-mono font-black tabular-nums',
                    first30.win_rate >= (first30.baseline_win_rate ?? 50) ? 'text-tm-profit' : 'text-tm-loss',
                  )}>
                    {Math.round(first30.win_rate)}%
                  </span>
                  <span className="text-sm text-muted-foreground pb-1">win rate</span>
                </div>
                {first30.baseline_win_rate && (
                  <p className={cn(
                    'text-[12px] font-medium',
                    first30.win_rate < first30.baseline_win_rate ? 'text-tm-loss' : 'text-tm-profit',
                  )}>
                    {(first30.win_rate - first30.baseline_win_rate).toFixed(1)}% vs your overall ({Math.round(first30.baseline_win_rate)}%)
                  </p>
                )}
                <p className="text-[11px] text-muted-foreground mt-2">
                  {first30.trades} trades · {formatCurrencyWithSign(Math.round(first30.avg_pnl))} avg P&L
                </p>
                {first30.win_rate < (first30.baseline_win_rate ?? 50) - 5 && (
                  <p className="text-[11px] text-tm-loss mt-2">
                    Opening trap: you underperform in the first 30 minutes. Consider waiting for the first candle to close.
                  </p>
                )}
              </div>
            </div>
          )}

          {expiryDay && expiryDay.trades > 0 && (
            <div className={cn(
              'tm-card overflow-hidden border-l-4',
              expiryDay.win_rate < (expiryDay.baseline_win_rate ?? 50) - 5 ? 'border-l-tm-loss' : 'border-l-tm-profit',
            )}>
              <div className="px-4 pt-4 pb-1 flex items-center gap-2">
                <Clock className="h-4 w-4 text-muted-foreground" />
                <p className="text-xs text-muted-foreground uppercase tracking-wide">Expiry Day Trades</p>
              </div>
              <div className="px-4 pb-4">
                <div className="flex items-end gap-2 my-2">
                  <span className={cn(
                    'text-4xl font-mono font-black tabular-nums',
                    expiryDay.win_rate >= (expiryDay.baseline_win_rate ?? 50) ? 'text-tm-profit' : 'text-tm-loss',
                  )}>
                    {Math.round(expiryDay.win_rate)}%
                  </span>
                  <span className="text-sm text-muted-foreground pb-1">win rate</span>
                </div>
                {expiryDay.baseline_win_rate && (
                  <p className={cn(
                    'text-[12px] font-medium',
                    expiryDay.win_rate < expiryDay.baseline_win_rate ? 'text-tm-loss' : 'text-tm-profit',
                  )}>
                    {(expiryDay.win_rate - expiryDay.baseline_win_rate).toFixed(1)}% vs your overall ({Math.round(expiryDay.baseline_win_rate)}%)
                  </p>
                )}
                <p className="text-[11px] text-muted-foreground mt-2">
                  {expiryDay.trades} trades · {formatCurrencyWithSign(Math.round(expiryDay.avg_pnl))} avg P&L
                </p>
              </div>
            </div>
          )}

        </div>
      )}

      {/* Expiry vs Non-Expiry Comparison */}
      {expiry?.has_data && (
        <div className="tm-card overflow-hidden">
          <div className="px-5 py-3.5 border-b border-border">
            <p className="font-semibold text-sm">Expiry vs Non-Expiry Performance</p>
          </div>
          <div className="grid grid-cols-2 divide-x divide-border">
            {[
              { label: 'Expiry Days', s: expiry.expiry },
              { label: 'Non-Expiry Days', s: expiry.non_expiry },
            ].map(({ label, s }) => (
              <div key={label} className="px-5 py-4">
                <p className="text-[11px] text-muted-foreground uppercase tracking-wide mb-2">{label}</p>
                <p className="text-2xl font-mono font-bold tabular-nums text-foreground">{s.trade_count}</p>
                <p className="text-[12px] text-muted-foreground mt-0.5">trades</p>
                <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1">
                  <div>
                    <p className="text-[10px] text-muted-foreground">Win rate</p>
                    <p className={cn('text-sm font-mono font-semibold', s.win_rate >= 50 ? 'text-tm-profit' : 'text-tm-loss')}>
                      {s.win_rate}%
                    </p>
                  </div>
                  <div>
                    <p className="text-[10px] text-muted-foreground">Avg P&L</p>
                    <p className={cn('text-sm font-mono font-semibold', s.avg_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
                      {formatCurrencyWithSign(Math.round(s.avg_pnl))}
                    </p>
                  </div>
                  <div>
                    <p className="text-[10px] text-muted-foreground">Total P&L</p>
                    <p className={cn('text-sm font-mono font-semibold', s.total_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
                      {formatCurrencyWithSign(Math.round(s.total_pnl))}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Hourly breakdown on expiry days */}
          {expiry.by_hour && expiry.by_hour.length > 0 && (
            <div className="border-t border-border px-5 py-3">
              <p className="text-[11px] text-muted-foreground mb-2">Expiry vs non-expiry by hour</p>
              <div className="space-y-1.5">
                {expiry.by_hour.map(h => (
                  <div key={h.hour} className="flex items-center gap-2 text-[11px]">
                    <span className="w-10 text-muted-foreground font-mono shrink-0">
                      {String(h.hour).padStart(2,'0')}:00
                    </span>
                    <div className="flex-1 grid grid-cols-2 gap-2">
                      <div className="flex items-center gap-1">
                        <div className="w-1.5 h-1.5 rounded-full bg-tm-brand shrink-0" />
                        <span className={cn('font-mono', h.expiry_avg_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
                          {formatCurrencyWithSign(Math.round(h.expiry_avg_pnl))}
                        </span>
                        <span className="text-muted-foreground">({h.expiry_count})</span>
                      </div>
                      <div className="flex items-center gap-1">
                        <div className="w-1.5 h-1.5 rounded-full bg-muted-foreground/40 shrink-0" />
                        <span className={cn('font-mono', h.non_expiry_avg_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
                          {formatCurrencyWithSign(Math.round(h.non_expiry_avg_pnl))}
                        </span>
                        <span className="text-muted-foreground">({h.non_expiry_count})</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
              <div className="flex items-center gap-4 mt-2 text-[10px] text-muted-foreground">
                <div className="flex items-center gap-1"><div className="w-1.5 h-1.5 rounded-full bg-tm-brand" /> Expiry</div>
                <div className="flex items-center gap-1"><div className="w-1.5 h-1.5 rounded-full bg-muted-foreground/40" /> Non-expiry</div>
              </div>
            </div>
          )}

          <p className="px-5 pb-3.5 text-[11px] text-muted-foreground">
            {expiry.expiry.avg_pnl < expiry.non_expiry.avg_pnl
              ? `You underperform on expiry days by ${formatCurrencyWithSign(Math.round(expiry.non_expiry.avg_pnl - expiry.expiry.avg_pnl))} per trade. Consider reducing size on expiry.`
              : `You perform better on expiry days than non-expiry days. Your edge is stronger near settlement.`
            }
          </p>
        </div>
      )}

    </div>
  );
}
