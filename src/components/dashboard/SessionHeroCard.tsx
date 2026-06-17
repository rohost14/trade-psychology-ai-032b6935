import { cn } from '@/lib/utils';
import { formatCurrencyWithSign, formatCurrency } from '@/lib/formatters';
import { STATE_CFG, SessionState } from '@/lib/dashboardUtils';
import { useCountUp } from '@/hooks/useCountUp';
import type { MarginStatus } from '@/types/api';

interface SessionHeroCardProps {
  stateCfg: typeof STATE_CFG[SessionState];
  sessionPnlDisplay: number;
  realizedPnlDisplay: number;
  tradeStats: { trades_today: number; win_rate: number; max_drawdown: number; risk_used: number } | null;
  pnlPositive: boolean;
  unreadCount: number;
  acknowledgedTodayCount: number;
  unrealizedTotal: number;
  dailyLossLimit: number;
  dailyTradeLimit: number;
  margins: MarginStatus | null;
}

function Zone({ label, children, className }: { label: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={cn('flex flex-col justify-center px-4 py-3', className)}>
      <p className="text-[9.5px] font-semibold text-muted-foreground/70 uppercase tracking-[0.09em] mb-1.5 whitespace-nowrap">
        {label}
      </p>
      {children}
    </div>
  );
}

export function SessionHeroCard({
  stateCfg,
  sessionPnlDisplay,
  realizedPnlDisplay,
  tradeStats,
  pnlPositive,
  unrealizedTotal,
  dailyLossLimit,
  dailyTradeLimit,
  margins,
}: SessionHeroCardProps) {
  const animatedPnl = useCountUp(sessionPnlDisplay, 500);

  const tradesToday = tradeStats?.trades_today ?? 0;
  const winRate = tradeStats?.win_rate ?? 0;
  const lossAmt = Math.max(0, -realizedPnlDisplay);
  const limitPct = dailyLossLimit > 0 ? Math.min(100, Math.round((lossAmt / dailyLossLimit) * 100)) : 0;
  const tradeRatio = dailyTradeLimit > 0 ? tradesToday / dailyTradeLimit : 0;
  const marginPct = margins?.equity?.utilization_pct ?? 0;

  const tradeColor =
    tradeRatio >= 0.8 ? 'text-tm-loss' : tradeRatio >= 0.6 ? 'text-tm-obs' : 'text-foreground';
  const lossColor =
    limitPct >= 80 ? 'text-tm-loss' : limitPct >= 60 ? 'text-tm-obs' : 'text-muted-foreground';
  const marginColor =
    marginPct >= 80 ? 'text-tm-loss' : marginPct >= 60 ? 'text-tm-obs' : 'text-muted-foreground';

  return (
    <div className="border-b border-border bg-card/60 backdrop-blur-sm mb-0">

      {/* ── Desktop: single horizontal row ─────────────────────────────────── */}
      <div className="hidden md:flex divide-x divide-border">
        {/* Session P&L — wider zone */}
        <Zone label="SESSION P&L" className="min-w-[160px] px-5">
          <span className={cn(
            'font-black font-mono tabular-nums leading-none',
            'text-[24px]',
            pnlPositive ? 'text-tm-profit' : 'text-tm-loss',
          )}>
            {formatCurrencyWithSign(Math.round(animatedPnl))}
          </span>
          {tradeStats && tradeStats.trades_today > 0 && (
            <span className="text-[10.5px] text-muted-foreground font-mono mt-1 tabular-nums">
              {Math.round(winRate)}% win rate · {tradesToday} trade{tradesToday !== 1 ? 's' : ''}
            </span>
          )}
        </Zone>

        {/* Realized */}
        <Zone label="REALIZED">
          <span className={cn(
            'text-[15px] font-semibold font-mono tabular-nums leading-none',
            realizedPnlDisplay >= 0 ? 'text-tm-profit' : 'text-tm-loss',
          )}>
            {formatCurrencyWithSign(Math.round(realizedPnlDisplay))}
          </span>
        </Zone>

        {/* Unrealized */}
        <Zone label="UNREALIZED">
          <span className={cn(
            'text-[15px] font-semibold font-mono tabular-nums leading-none',
            unrealizedTotal > 0 ? 'text-tm-profit' : unrealizedTotal < 0 ? 'text-tm-loss' : 'text-muted-foreground',
          )}>
            {unrealizedTotal !== 0 ? formatCurrencyWithSign(Math.round(unrealizedTotal)) : '—'}
          </span>
        </Zone>

        {/* Trades */}
        <Zone label="TRADES">
          <span className={cn('text-[15px] font-semibold font-mono tabular-nums leading-none', tradeColor)}>
            {tradesToday}
            <span className="text-muted-foreground text-[12px] font-normal"> / {dailyTradeLimit}</span>
          </span>
        </Zone>

        {/* Risk State */}
        <Zone label="RISK">
          <span className={cn(
            'inline-flex items-center gap-1.5 text-[11px] font-semibold px-2.5 py-1 rounded-full self-start',
            stateCfg.pill,
          )}>
            <span className={cn('w-1.5 h-1.5 rounded-full flex-shrink-0', stateCfg.dot)} />
            {stateCfg.label}
          </span>
        </Zone>

        {/* Daily limit */}
        <Zone label="LOSS LIMIT">
          <span className={cn('text-[15px] font-semibold font-mono tabular-nums leading-none', lossColor)}>
            {limitPct}%
          </span>
          <span className="text-[10px] text-muted-foreground mt-1">
            {formatCurrency(lossAmt)} / {formatCurrency(dailyLossLimit)}
          </span>
        </Zone>

        {/* Margin (conditional) */}
        {margins && (
          <Zone label="MARGIN">
            <span className={cn('text-[15px] font-semibold font-mono tabular-nums leading-none', marginColor)}>
              {marginPct}%
            </span>
            <span className="text-[10px] text-muted-foreground mt-1">
              {formatCurrency(margins.equity?.available ?? 0)} free
            </span>
          </Zone>
        )}
      </div>

      {/* ── Mobile: 2-row 3-col grid ────────────────────────────────────────── */}
      <div className="md:hidden">
        {/* Row 1: P&L | Risk | Trades */}
        <div className="grid grid-cols-3 divide-x divide-border border-b border-border">
          <div className="px-4 py-3">
            <p className="text-[9px] font-semibold text-muted-foreground/70 uppercase tracking-[0.09em] mb-1">P&L</p>
            <span className={cn(
              'text-[22px] font-black font-mono tabular-nums leading-none block',
              pnlPositive ? 'text-tm-profit' : 'text-tm-loss',
            )}>
              {formatCurrencyWithSign(Math.round(animatedPnl))}
            </span>
          </div>
          <div className="px-3 py-3 flex flex-col justify-center">
            <p className="text-[9px] font-semibold text-muted-foreground/70 uppercase tracking-[0.09em] mb-1.5">RISK</p>
            <span className={cn(
              'inline-flex items-center gap-1 text-[10.5px] font-semibold px-2 py-0.5 rounded-full self-start',
              stateCfg.pill,
            )}>
              <span className={cn('w-1.5 h-1.5 rounded-full flex-shrink-0', stateCfg.dot)} />
              {stateCfg.label}
            </span>
          </div>
          <div className="px-3 py-3 flex flex-col justify-center">
            <p className="text-[9px] font-semibold text-muted-foreground/70 uppercase tracking-[0.09em] mb-1">TRADES</p>
            <span className={cn('text-[16px] font-semibold font-mono tabular-nums', tradeColor)}>
              {tradesToday}
              <span className="text-muted-foreground text-[12px] font-normal"> / {dailyTradeLimit}</span>
            </span>
          </div>
        </div>

        {/* Row 2: Realized | Unrealized | Limit */}
        <div className="grid grid-cols-3 divide-x divide-border">
          <div className="px-4 py-2.5">
            <p className="text-[9px] font-semibold text-muted-foreground/70 uppercase tracking-[0.07em] mb-1">Realized</p>
            <span className={cn(
              'text-[12.5px] font-semibold font-mono tabular-nums',
              realizedPnlDisplay >= 0 ? 'text-tm-profit' : 'text-tm-loss',
            )}>
              {formatCurrencyWithSign(Math.round(realizedPnlDisplay))}
            </span>
          </div>
          <div className="px-3 py-2.5">
            <p className="text-[9px] font-semibold text-muted-foreground/70 uppercase tracking-[0.07em] mb-1">Unrealized</p>
            <span className={cn(
              'text-[12.5px] font-semibold font-mono tabular-nums',
              unrealizedTotal > 0 ? 'text-tm-profit' : unrealizedTotal < 0 ? 'text-tm-loss' : 'text-muted-foreground',
            )}>
              {unrealizedTotal !== 0 ? formatCurrencyWithSign(Math.round(unrealizedTotal)) : '—'}
            </span>
          </div>
          <div className="px-3 py-2.5">
            <p className="text-[9px] font-semibold text-muted-foreground/70 uppercase tracking-[0.07em] mb-1">Loss limit</p>
            <span className={cn('text-[12.5px] font-semibold font-mono tabular-nums', lossColor)}>
              {limitPct}%
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
