import { Link } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { formatCurrencyWithSign } from '@/lib/formatters';
import { CompletedTrade } from '@/types/api';
import { PnlSparkline } from './PnlSparkline';
import { STATE_CFG, SessionState, getSessionDesc } from '@/lib/dashboardUtils';

interface SessionHeroCardProps {
  stateCfg: typeof STATE_CFG[SessionState];
  sessionStateKey: SessionState;
  sessionPnlDisplay: number;
  realizedPnlDisplay: number;
  tradeStats: { trades_today: number; win_rate: number; max_drawdown: number; risk_used: number; } | null;
  pnlPositive: boolean;
  unreadCount: number;
  unjournaled: number;
  closedTrades: CompletedTrade[];
  unrealizedTotal: number;
}

export function SessionHeroCard({
  stateCfg,
  sessionStateKey,
  sessionPnlDisplay,
  realizedPnlDisplay,
  tradeStats,
  pnlPositive,
  unreadCount,
  unjournaled,
  closedTrades,
  unrealizedTotal,
}: SessionHeroCardProps) {
  return (
    <div className={cn('tm-card mb-5', stateCfg.accent)}>
      <div className="flex items-stretch">
        {/* Left: state + P&L */}
        <div className="flex-1 min-w-0 px-5 pt-4 pb-3">
          <div className="flex items-center gap-2 mb-2">
            <span className={cn('flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold uppercase tracking-wide', stateCfg.pill)}>
              <span className={cn('w-1.5 h-1.5 rounded-full', stateCfg.dot)} />
              {stateCfg.label}
            </span>
          </div>
          <div className="flex items-baseline gap-2 mb-1">
            <span className={cn('text-[44px] font-black font-mono tabular-nums leading-none', pnlPositive ? 'text-tm-profit' : 'text-tm-loss')}>
              {formatCurrencyWithSign(sessionPnlDisplay)}
            </span>
          </div>
          <p className="text-[13px] text-muted-foreground leading-snug">
            {getSessionDesc(sessionStateKey, unreadCount, tradeStats?.trades_today ?? 0, Math.round(tradeStats?.win_rate ?? 0))}
          </p>
        </div>

        {/* Right: sparkline */}
        <div className="w-[176px] shrink-0 border-l border-slate-100 dark:border-neutral-700/60 px-4 pt-4 pb-3 flex flex-col">
          <span className="tm-label mb-2">Cumulative P&L</span>
          <PnlSparkline closed={closedTrades} unrealized={unrealizedTotal} positive={pnlPositive} />
          <div className="flex items-center justify-between mt-1.5">
            <span className="text-[10px] text-muted-foreground">open → now</span>
            <span className={cn('text-[11px] font-mono tabular-nums font-semibold', pnlPositive ? 'text-tm-profit' : 'text-tm-loss')}>
              {formatCurrencyWithSign(sessionPnlDisplay)}
            </span>
          </div>
        </div>
      </div>

      {/* Stat footer — pipe-separated */}
      <div className="flex items-center flex-wrap gap-y-1 border-t border-slate-100 dark:border-neutral-700/60 px-5 py-3">
        <span className="text-[12px] text-muted-foreground pr-4">
          <span className="font-mono tabular-nums font-semibold text-foreground">{tradeStats?.trades_today ?? 0}</span>
          {' '}trades
        </span>
        {tradeStats && tradeStats.trades_today > 0 && (
          <>
            <span className="w-px h-3.5 shrink-0 bg-slate-200 dark:bg-neutral-600" />
            <span className="text-[12px] text-muted-foreground px-4">
              <span className={cn('font-mono tabular-nums font-semibold', tradeStats.win_rate >= 50 ? 'text-tm-profit' : 'text-tm-loss')}>
                {Math.round(tradeStats.win_rate)}%
              </span>
              {' '}win rate
            </span>
          </>
        )}
        <span className="w-px h-3.5 shrink-0 bg-slate-200 dark:bg-neutral-600" />
        <span className="text-[12px] text-muted-foreground px-4">
          <span className={cn('font-mono tabular-nums font-semibold', realizedPnlDisplay >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
            {formatCurrencyWithSign(realizedPnlDisplay)}
          </span>
          {' '}realized
        </span>
        {unjournaled > 0 && (
          <>
            <span className="w-px h-3.5 shrink-0 bg-slate-200 dark:bg-neutral-600" />
            <span className="text-[12px] text-tm-obs font-medium px-4">{unjournaled} to journal</span>
          </>
        )}
        {unreadCount > 0 && (
          <>
            <span className="w-px h-3.5 shrink-0 bg-slate-200 dark:bg-neutral-600" />
            <Link to="/alerts" className="text-[12px] text-tm-obs font-medium hover:underline px-4">
              {unreadCount} alert{unreadCount !== 1 ? 's' : ''} →
            </Link>
          </>
        )}
      </div>
    </div>
  );
}
