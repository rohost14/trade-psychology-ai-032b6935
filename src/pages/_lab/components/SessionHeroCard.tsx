import { useState } from 'react';
import { cn } from '@/lib/utils';
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
  // No count-up on the live figure. Every price tick changes sessionPnlDisplay,
  // which restarts the animation, and in a live session ticks arrive faster
  // than the 500ms it needs to land -- so the headline number was permanently
  // in flight and never equalled Booked plus Unrealized underneath it. It read
  // as a reconciliation bug because on screen it was one.

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
    /**
     * No card. This is the page's opening statement, not one tile among
     * several -- and the box was what created the dead space: a 44px figure
     * in a full-width container leaves roughly 900px of nothing to its right,
     * and putting the stats in a band underneath spent vertical space to
     * avoid using horizontal space that was already there.
     *
     * So: figure left, session figures beside it, one rule underneath to
     * separate it from what follows. The brand accent stays as a short rule
     * above the label rather than a border around everything.
     */
    <section className="pb-4 border-b border-border">
      <div className="flex items-center justify-between gap-3 h-9">
        <span className="t-label flex items-center gap-2">
          Day P&amp;L
          <span className={cn('h-1.5 w-1.5 rounded-full animate-pulse', pnlPositive ? 'bg-profit' : 'bg-loss')} />
        </span>
        <button
          type="button"
          onClick={() => setOpen(v => !v)}
          aria-expanded={open}
          className="shrink-0 inline-flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-[11px] font-medium text-muted-foreground transition-colors duration-150 hover:text-foreground hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {open ? 'Hide read' : "Today's read"}
          <ChevronDown className={cn('h-3.5 w-3.5 transition-transform duration-200', open && 'rotate-180')} />
        </button>
      </div>

      <div className="mt-2 flex flex-wrap items-end justify-between gap-x-10 gap-y-5">
        {/* the figure — scale carries the hierarchy, colour carries direction */}
        <div className="min-w-0">
          <span className={cn(
            'font-display text-[38px] leading-none font-semibold tracking-tight font-tabular block',
            pnlPositive ? 'text-profit' : 'text-loss',
          )}>
            {pnlPositive ? '+' : '−'}₹{inr(sessionPnlDisplay)}
          </span>
          <p className="mt-2 text-[12.5px] font-tabular text-muted-foreground">
            Booked{' '}
            <span className={realizedPnlDisplay >= 0 ? 'text-profit' : 'text-loss'}>
              {realizedPnlDisplay >= 0 ? '+' : '−'}₹{inr(realizedPnlDisplay)}
            </span>
            <span className="text-muted-foreground/40"> · </span>
            Unrealized{' '}
            <span className={unrealizedTotal > 0 ? 'text-profit' : unrealizedTotal < 0 ? 'text-loss' : ''}>
              {unrealizedTotal !== 0 ? `${unrealizedTotal >= 0 ? '+' : '−'}₹${inr(unrealizedTotal)}` : 'nothing open'}
            </span>
          </p>
        </div>

        {/* session figures, in the space the number leaves rather than beneath it */}
        <div className="flex items-end gap-8 sm:gap-12">
          {stats.map(s => (
            <div key={s.label}>
              <span className="text-[10px] uppercase tracking-wider font-medium text-muted-foreground whitespace-nowrap">{s.label}</span>
              <div className="mt-1.5 flex items-baseline gap-1.5">
                <span className={cn('text-[19px] font-semibold font-tabular tracking-tight', s.tone)}>{s.value}</span>
                {s.unit && <span className="text-[10.5px] text-muted-foreground font-tabular whitespace-nowrap">{s.unit}</span>}
              </div>
            </div>
          ))}
        </div>
      </div>

      {open && (
        <p className="mt-4 text-[12.5px] leading-snug text-muted-foreground animate-accordion-down">
          {lossPct >= 80
            ? "Most of today's loss budget is already spent."
            : paceRatio >= 1.5
            ? 'Trading faster than your usual rhythm today.'
            : 'Running inside your normal operating range.'}
        </p>
      )}
    </section>
  );
}
