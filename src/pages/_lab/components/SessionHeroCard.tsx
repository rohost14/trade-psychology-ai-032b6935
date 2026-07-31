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
     * Colour as an ACCENT, not a field.
     *
     * The previous pass made this a saturated pine slab with white text, which
     * read as a promotional banner rather than an instrument -- a marketing
     * hero dropped into a data screen. Wrong intensity, right instinct.
     *
     * Personality comes from three cheap things instead: a 2px brand rule along
     * the top edge, the figure carried at 44px in its own semantic colour so
     * the number itself is the hero, and a recessed stat band. Small coloured
     * area, high impact, nothing shouting.
     */
    <section className="desk-card overflow-hidden">
      <span aria-hidden className="block h-[2px] bg-tm-brand" />

      <div className="card-head">
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

      {/* Scale does the hierarchy: 44px against 10px labels. The figure carries
          its own direction colour, so up and down are legible before reading. */}
      <div className="px-4 sm:px-6 py-5">
        <span className={cn(
          'font-display text-[44px] leading-none font-semibold tracking-tight font-tabular block',
          pnlPositive ? 'text-profit' : 'text-loss',
        )}>
          {pnlPositive ? '+' : '−'}₹{inr(animatedPnl)}
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

      {/* Recessed band rather than four more boxes. One step down from the
          card gives the depth a border cannot. */}
      <div className="grid grid-cols-2 sm:grid-cols-4 bg-muted/40 border-t border-border">
        {stats.map((s, i) => (
          <div
            key={s.label}
            className={cn(
              'px-4 sm:px-5 py-3',
              i > 0 && 'sm:border-l border-border',
              i === 1 && 'border-l border-border',
              i >= 2 && 'border-t sm:border-t-0 border-border',
              i === 3 && 'border-l border-border',
            )}
          >
            <span className="text-[10px] uppercase tracking-wider font-medium text-muted-foreground">{s.label}</span>
            <div className="mt-1 flex items-baseline gap-1.5">
              <span className={cn('text-[17px] font-semibold font-tabular tracking-tight', s.tone)}>{s.value}</span>
              {s.unit && <span className="text-[10.5px] text-muted-foreground font-tabular truncate">{s.unit}</span>}
            </div>
          </div>
        ))}
      </div>

      {open && (
        <div className="animate-accordion-down border-t border-border">
          <p className="px-4 sm:px-6 py-3 text-[12.5px] leading-snug text-muted-foreground">
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
