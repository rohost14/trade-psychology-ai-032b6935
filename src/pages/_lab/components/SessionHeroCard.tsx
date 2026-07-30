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
    /**
     * A COLOUR FIELD, not a card.
     *
     * The screen was grey with small green and red numerals on it, and the
     * brand colour appeared as a 6px dot. That is not restraint, it is
     * absence. One saturated region anchors the page and everything below it
     * stays quiet -- which is how calm products get personality without
     * becoming casinos.
     *
     * Depth here comes from figure/ground and scale contrast rather than from
     * a border: a deep pine field, paper-coloured text on it, the figure at
     * 44px against 10px labels, and the stat rail sitting in a darker inset
     * band rather than a row of boxes.
     */
    <section className="rounded-lg overflow-hidden bg-tm-brand text-white">
      {/* field header */}
      <div className="flex items-center justify-between gap-3 px-4 sm:px-6 h-11 border-b border-white/10">
        <span className="text-[11px] font-medium uppercase tracking-[0.12em] text-white/70 flex items-center gap-2">
          Day P&amp;L
          <span className="h-1.5 w-1.5 rounded-full bg-white/60 animate-pulse" />
        </span>
        <button
          type="button"
          onClick={() => setOpen(v => !v)}
          aria-expanded={open}
          className="shrink-0 inline-flex items-center gap-1.5 rounded-md border border-white/20 px-2.5 py-1.5 text-[11px] font-medium text-white/80 transition-colors duration-150 hover:bg-white/10 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/40"
        >
          {open ? 'Hide read' : "Today's read"}
          <ChevronDown className={cn('h-3.5 w-3.5 transition-transform duration-200', open && 'rotate-180')} />
        </button>
      </div>

      {/* the figure. Scale does the hierarchy: 44px against 10px labels. */}
      <div className="px-4 sm:px-6 py-5">
        <span className="font-display text-[44px] sm:text-[52px] leading-none font-semibold tracking-tight font-tabular text-white block">
          {pnlPositive ? '+' : '−'}₹{inr(animatedPnl)}
        </span>
        <p className="mt-2 text-[12.5px] font-tabular text-white/70">
          Booked {realizedPnlDisplay >= 0 ? '+' : '−'}₹{inr(realizedPnlDisplay)}
          <span className="text-white/30"> · </span>
          Unrealized {unrealizedTotal !== 0 ? `${unrealizedTotal >= 0 ? '+' : '−'}₹${inr(unrealizedTotal)}` : 'nothing open'}
        </p>
      </div>

      {/* inset band — darker than the field, so the rail reads as recessed
          rather than as four more boxes stacked on top */}
      <div className="grid grid-cols-2 sm:grid-cols-4 bg-black/15 border-t border-white/10">
        {stats.map((s, i) => (
          <div
            key={s.label}
            className={cn(
              'px-4 sm:px-5 py-3',
              i > 0 && 'border-l border-white/10',
              i === 2 && 'border-l-0 sm:border-l',
              i >= 2 && 'border-t border-white/10 sm:border-t-0',
            )}
          >
            <span className="text-[10px] uppercase tracking-wider font-medium text-white/55">{s.label}</span>
            <div className="mt-1 flex items-baseline gap-1.5">
              <span className="text-[17px] font-semibold font-tabular tracking-tight text-white">{s.value}</span>
              {s.unit && <span className="text-[10.5px] text-white/50 font-tabular truncate">{s.unit}</span>}
            </div>
          </div>
        ))}
      </div>

      {open && (
        <div className="animate-accordion-down border-t border-white/10 bg-black/10">
          <p className="px-4 sm:px-6 py-3 text-[12.5px] leading-snug text-white/75">
            {lossPct >= 80
              ? "Most of today's loss budget is already spent."
              : paceRatio >= 1.5
              ? 'Trading faster than your usual rhythm today.'
              : 'Running inside your normal operating range.'}
          </p>
        </div>
      )}
    </section>
  );
}
