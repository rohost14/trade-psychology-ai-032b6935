import { useState } from 'react';
import { cn } from '@/lib/utils';
import { useCountUp } from '@/hooks/useCountUp';
import { ChevronDown } from 'lucide-react';
import { STATE_CFG, SessionState } from '@/lib/dashboardUtils';
import type { MarginStatus } from '@/types/api';

interface SessionHeroCardProps {
  stateCfg: typeof STATE_CFG[SessionState];
  sessionPnlDisplay: number;
  realizedPnlDisplay: number;
  tradeStats: { trades_today: number; win_rate: number; max_drawdown: number } | null;
  pnlPositive: boolean;
  unreadCount: number;
  acknowledgedTodayCount: number;
  unrealizedTotal: number;
  dailyLossLimit: number;
  dailyTradeLimit: number;
  margins: MarginStatus | null;
}

// Higher value = worse → warn/crit tones. Mirrors the Lovable HeroPanel toneOf.
const toneOf = (v: number, warn: number, crit: number) =>
  v >= crit ? 'text-loss' : v >= warn ? 'text-warning' : 'text-profit';

const inr = (n: number) => Math.abs(Math.round(n)).toLocaleString('en-IN');

/**
 * Compact "Intraday P&L" hero, styled to match the Lovable Dashboard HeroPanel:
 * one money-truth line + a collapsible 4-stat session rail. Wired to real data.
 */
export function SessionHeroCard({
  sessionPnlDisplay,
  realizedPnlDisplay,
  tradeStats,
  pnlPositive,
  unrealizedTotal,
  dailyLossLimit,
  dailyTradeLimit,
}: SessionHeroCardProps) {
  const [open, setOpen] = useState(false);
  const animatedPnl = useCountUp(sessionPnlDisplay, 500);

  const tradesToday = tradeStats?.trades_today ?? 0;
  const winRate = tradeStats?.win_rate ?? 0;
  const lossAmt = Math.max(0, -realizedPnlDisplay);
  const lossPct = dailyLossLimit > 0 ? (lossAmt / dailyLossLimit) * 100 : 0;
  const lossRemaining = Math.max(0, dailyLossLimit - lossAmt);
  const paceRatio = dailyTradeLimit > 0 ? tradesToday / dailyTradeLimit : 0;

  const stats = [
    { label: 'Trades', value: String(tradesToday), unit: `${paceRatio.toFixed(1)}x pace`, tone: toneOf(paceRatio, 1, 1.5) },
    { label: 'Loss budget', value: `₹${(lossRemaining / 1000).toFixed(1)}k`, unit: `of ₹${(dailyLossLimit / 1000).toFixed(0)}k`, tone: toneOf(lossPct, 50, 80) },
    { label: 'Win rate', value: `${Math.round(winRate)}%`, unit: `${tradesToday} trade${tradesToday !== 1 ? 's' : ''}`, tone: 'text-foreground' },
    {
      label: unrealizedTotal !== 0 ? 'Unrealized' : 'Realized',
      value: (() => { const v = unrealizedTotal !== 0 ? unrealizedTotal : realizedPnlDisplay; return `${v >= 0 ? '+' : '−'}₹${inr(v)}`; })(),
      unit: '',
      tone: (unrealizedTotal !== 0 ? unrealizedTotal : realizedPnlDisplay) >= 0 ? 'text-profit' : 'text-loss',
    },
  ];

  return (
    <section className="desk-card overflow-hidden">
      <div className="px-4 sm:px-6 py-4 flex items-center justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="t-label">Intraday P&amp;L</span>
            <span className={cn('h-1.5 w-1.5 rounded-full animate-pulse', pnlPositive ? 'bg-profit' : 'bg-loss')} />
          </div>
          <div className="mt-1 flex items-baseline gap-2 flex-wrap">
            <span className={cn(
              'font-display text-[28px] sm:text-[32px] leading-none font-semibold tracking-tight font-tabular',
              pnlPositive ? 'text-profit' : 'text-loss',
            )}>
              {pnlPositive ? '+' : '−'}₹{inr(animatedPnl)}
            </span>
            {tradesToday > 0 && (
              <span className="text-[12px] font-tabular font-medium text-muted-foreground">
                {Math.round(winRate)}% win · {tradesToday} trade{tradesToday !== 1 ? 's' : ''}
              </span>
            )}
          </div>
        </div>

        <button
          type="button"
          onClick={() => setOpen(v => !v)}
          aria-expanded={open}
          className="shrink-0 inline-flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-[11.5px] font-medium text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-colors"
        >
          {open ? 'Hide session stats' : 'Session stats'}
          <ChevronDown className={cn('h-3.5 w-3.5 transition-transform duration-200', open && 'rotate-180')} />
        </button>
      </div>

      {open && (
        <div className="animate-accordion-down">
          <p className="px-4 sm:px-6 pb-3 text-[12.5px] leading-snug text-muted-foreground">
            {lossPct >= 80
              ? "Most of today's loss budget is already spent."
              : paceRatio >= 1.5
              ? 'Trading faster than your usual rhythm today.'
              : 'Running inside your normal operating range.'}
          </p>
          <div className="grid grid-cols-2 sm:grid-cols-4 border-t border-border divide-x divide-y sm:divide-y-0 divide-border">
            {stats.map(s => (
              <div key={s.label} className="px-4 sm:px-5 py-2.5">
                <span className="text-[10px] uppercase tracking-[0.12em] font-medium text-muted-foreground">{s.label}</span>
                <div className="mt-0.5 flex items-baseline gap-1.5">
                  <span className={cn('text-[16px] font-semibold font-tabular tracking-tight', s.tone)}>{s.value}</span>
                  {s.unit && <span className="text-[10.5px] text-muted-foreground font-tabular truncate">{s.unit}</span>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
