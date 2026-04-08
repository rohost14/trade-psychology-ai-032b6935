import { Flame, Trophy, Calendar } from 'lucide-react';
import { StreakData } from '@/types/patterns';
import { cn } from '@/lib/utils';

interface StreakTrackerCardProps {
  streak: StreakData;
  goalDays?: number;
}

export function StreakTrackerCard({ streak, goalDays = 30 }: StreakTrackerCardProps) {
  const progressPercent = Math.min((streak.current_streak_days / goalDays) * 100, 100);
  const last30Days = streak.daily_status.slice(0, 30);
  const displayDays = Array.from({ length: 30 }, (_, i) => {
    const day = last30Days[i];
    if (day) {
      return {
        ...day,
        status: day.all_goals_followed ? 'success' : day.trading_day ? 'broken' : 'non-trading',
      };
    }
    return { status: 'empty' };
  });

  const isOnFire = streak.current_streak_days >= 7;

  return (
    <div className="tm-card overflow-hidden">
      <div className="px-5 py-4 border-b border-border flex items-center justify-between">
        <p className="text-sm font-semibold text-foreground flex items-center gap-1.5">
          <Flame className={cn('h-4 w-4', isOnFire ? 'text-tm-obs' : 'text-muted-foreground')} />
          Discipline Streak
        </p>
        {isOnFire && (
          <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-amber-50 dark:bg-amber-900/20 text-tm-obs">
            On Fire!
          </span>
        )}
      </div>
      <div className="p-5 space-y-4">
        {/* Main streak number */}
        <div className="text-center py-3">
          <p className="text-5xl font-bold font-mono tabular-nums text-tm-brand">
            {streak.current_streak_days}
          </p>
          <p className="text-xs text-muted-foreground mt-1">days without a high/critical alert</p>
        </div>

        {/* Progress to goal */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground">Progress to {goalDays}-day goal</span>
            <span className="font-mono tabular-nums text-foreground">{streak.current_streak_days}/{goalDays}</span>
          </div>
          <div className="h-2 bg-muted rounded-full overflow-hidden">
            <div
              className="h-full bg-tm-brand rounded-full transition-all duration-500"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </div>

        {/* Day grid */}
        <div className="space-y-2">
          <p className="tm-label flex items-center gap-1.5">
            <Calendar className="h-3 w-3" />
            Last 30 Days
          </p>
          <div className="flex flex-wrap gap-1">
            {displayDays.map((day, i) => (
              <div
                key={i}
                className={cn(
                  'w-4 h-4 rounded-sm transition-colors',
                  day.status === 'success' && 'bg-tm-profit',
                  day.status === 'broken' && 'bg-tm-loss',
                  day.status === 'non-trading' && 'bg-muted-foreground/25',
                  day.status === 'empty' && 'bg-muted'
                )}
                title={
                  day.status === 'success' ? 'Clean — no high/critical alert' :
                  day.status === 'broken' ? 'High or critical alert triggered' :
                  day.status === 'non-trading' ? 'No alerts recorded' : 'No data'
                }
              />
            ))}
          </div>
          <div className="flex items-center gap-4 text-[10px] text-muted-foreground">
            <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-sm bg-tm-profit inline-block" />Clean</span>
            <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-sm bg-tm-loss inline-block" />Alert</span>
            <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-sm bg-muted inline-block" />No data</span>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 gap-3 pt-3 border-t border-border">
          <div className="text-center p-3 rounded-lg bg-muted/40">
            <p className="text-xl font-bold font-mono tabular-nums text-foreground">{streak.longest_streak_days}</p>
            <p className="text-[10px] text-muted-foreground mt-0.5">Longest Streak</p>
          </div>
          <div className="text-center p-3 rounded-lg bg-muted/40">
            <p className="text-xl font-bold font-mono tabular-nums text-foreground">{streak.milestones_achieved.length}</p>
            <p className="text-[10px] text-muted-foreground mt-0.5">Milestones</p>
          </div>
        </div>

        {/* Milestones */}
        {streak.milestones_achieved.length > 0 && (
          <div className="space-y-2">
            <p className="tm-label flex items-center gap-1.5">
              <Trophy className="h-3 w-3" />
              Achievements
            </p>
            <div className="flex flex-wrap gap-1.5">
              {streak.milestones_achieved.map((milestone) => (
                <span key={milestone.days} className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-teal-50 dark:bg-teal-900/20 text-tm-brand">
                  🏆 {milestone.label}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
