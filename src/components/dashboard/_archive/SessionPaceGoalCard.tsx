import { useState, useEffect } from 'react';
import { Flame, ArrowRight } from 'lucide-react';
import { Link } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { api } from '@/lib/api';

interface WeekStats {
  total_pnl: number;
  trade_count: number;
  win_rate: number;
  winners: number;
  losers: number;
}

interface ProgressData {
  this_week: WeekStats;
  last_week: WeekStats;
  alerts: { this_week: number; last_week: number };
  streaks: { days_without_revenge: number; current_streak: number; best_streak: number };
}

interface SessionPaceGoalCardProps {
  brokerAccountId: string;
  tradesCount: number; // today's trade count
}

export default function SessionPaceGoalCard({ brokerAccountId, tradesCount }: SessionPaceGoalCardProps) {
  const [data, setData] = useState<ProgressData | null>(null);

  useEffect(() => {
    if (!brokerAccountId) return;
    api.get<ProgressData>('/api/analytics/progress')
      .then(r => setData(r.data))
      .catch(() => {});
  }, [brokerAccountId]);

  // Avg trades/day from last week (5 trading days)
  const avgPerDay = data ? Math.max(1, Math.round((data.last_week.trade_count / 5) * 10) / 10) : null;

  // Pace ratio
  const paceRatio = avgPerDay ? tradesCount / avgPerDay : null;

  // Pace status
  const getPaceStatus = () => {
    if (!paceRatio) return { label: 'Tracking', cls: 'text-muted-foreground', barCls: 'bg-tm-brand' };
    if (paceRatio >= 2) return { label: 'High volume', cls: 'text-tm-loss', barCls: 'bg-tm-loss' };
    if (paceRatio >= 1.5) return { label: 'Above pace', cls: 'text-tm-obs', barCls: 'bg-tm-obs' };
    return { label: 'On pace', cls: 'text-tm-profit', barCls: 'bg-tm-brand' };
  };

  const pace = getPaceStatus();

  // Bar fill: cap at 100%, full = 2× avg
  const barPct = paceRatio ? Math.min(100, (paceRatio / 2) * 100) : 0;

  const streak = data?.streaks?.current_streak ?? 0;
  const thisWeek = data?.this_week;

  return (
    <div className="tm-card p-5">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <span className="tm-label">Session Pace</span>
        <Link
          to="/analytics"
          className="flex items-center gap-0.5 text-[12px] font-medium text-tm-brand hover:underline"
        >
          Analytics
          <ArrowRight className="w-3 h-3" />
        </Link>
      </div>

      {/* Trade count hero */}
      <div className="flex items-end gap-2 mb-1">
        <span className="text-[40px] font-black font-mono tabular-nums leading-none text-foreground">
          {tradesCount}
        </span>
        <span className="text-[13px] text-muted-foreground pb-1.5">trades today</span>
      </div>

      {/* Context line */}
      <p className="text-[12px] text-muted-foreground mb-3">
        {avgPerDay
          ? <><span className="font-mono tabular-nums">{avgPerDay}</span> avg/day last week</>
          : 'No comparison data yet'
        }
        {paceRatio !== null && (
          <span className={cn('ml-2 font-medium', pace.cls)}>· {pace.label}</span>
        )}
      </p>

      {/* Pace bar */}
      <div className="h-1.5 rounded-full bg-slate-100 dark:bg-neutral-700/50 overflow-hidden mb-4">
        <div
          className={cn('h-full rounded-full transition-all duration-500', pace.barCls)}
          style={{
            width: `${barPct}%`,
            boxShadow: pace.barCls === 'bg-tm-loss'
              ? '0 0 6px rgba(220,38,38,0.55)'
              : pace.barCls === 'bg-tm-obs'
              ? '0 0 6px rgba(217,119,6,0.55)'
              : '0 0 6px rgba(15,142,125,0.45)',
          }}
        />
      </div>

      {/* This week snapshot */}
      {thisWeek && (
        <div className="flex items-center gap-4 mb-4 text-[12px]">
          <div>
            <span className="text-muted-foreground">This week </span>
            <span className="font-mono tabular-nums font-semibold text-foreground">{thisWeek.trade_count}</span>
            <span className="text-muted-foreground"> trades</span>
          </div>
          <div>
            <span className="font-mono tabular-nums text-tm-profit">{thisWeek.winners}W</span>
            <span className="text-muted-foreground/50 mx-1">·</span>
            <span className="font-mono tabular-nums text-tm-loss">{thisWeek.losers ?? (thisWeek.trade_count - thisWeek.winners)}L</span>
          </div>
          <div>
            <span className={cn(
              'font-mono tabular-nums font-semibold',
              thisWeek.win_rate >= 50 ? 'text-tm-profit' : 'text-tm-loss',
            )}>
              {Math.round(thisWeek.win_rate)}%
            </span>
          </div>
        </div>
      )}

      {/* Streak badge */}
      {streak > 0 && (
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-100 dark:border-amber-800/30">
          <Flame className="w-3.5 h-3.5 text-amber-500 shrink-0" />
          <span className="text-[12px] font-semibold text-amber-700 dark:text-amber-300">
            {streak}-day streak
          </span>
          <span className="text-[12px] text-amber-600/70 dark:text-amber-400/70">· no revenge trading</span>
        </div>
      )}
    </div>
  );
}
