// Streak Tracker Card - Visual display of discipline streak
// Positive reinforcement through achievement tracking

import { Flame, Trophy, Calendar } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { StreakData } from '@/types/patterns';
import { cn } from '@/lib/utils';

interface StreakTrackerCardProps {
  streak: StreakData;
  goalDays?: number;
}

export function StreakTrackerCard({ streak, goalDays = 30 }: StreakTrackerCardProps) {
  const progressPercent = Math.min((streak.current_streak_days / goalDays) * 100, 100);
  
  // Get last 30 days for visual display
  const last30Days = streak.daily_status.slice(0, 30);
  
  // Fill in missing days with empty status
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

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg flex items-center gap-2">
            <Flame className={cn(
              "h-5 w-5",
              streak.current_streak_days >= 7 ? "text-warning" : "text-muted-foreground"
            )} />
            Discipline Streak
          </CardTitle>
          {streak.current_streak_days >= 7 && (
            <Badge variant="default" className="bg-warning text-warning-foreground">
              🔥 On Fire!
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Main Streak Display */}
        <div className="text-center py-4">
          <p className="text-5xl font-bold font-mono text-primary">
            {streak.current_streak_days}
          </p>
          <p className="text-sm text-muted-foreground mt-1">days following all goals</p>
        </div>
        
        {/* Progress to Goal */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Progress to {goalDays}-day goal</span>
            <span className="font-mono">{streak.current_streak_days}/{goalDays}</span>
          </div>
          <div className="h-3 bg-muted rounded-full overflow-hidden">
            <div 
              className="h-full bg-primary transition-all duration-500"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </div>
        
        {/* Visual Day Grid */}
        <div className="space-y-2">
          <p className="text-sm font-medium text-muted-foreground flex items-center gap-2">
            <Calendar className="h-4 w-4" />
            Last 30 Days
          </p>
          <div className="flex flex-wrap gap-1">
            {displayDays.map((day, i) => (
              <div
                key={i}
                className={cn(
                  "w-4 h-4 rounded-sm transition-colors",
                  day.status === 'success' && "bg-success",
                  day.status === 'broken' && "bg-destructive",
                  day.status === 'non-trading' && "bg-muted-foreground/30",
                  day.status === 'empty' && "bg-muted"
                )}
                title={
                  day.status === 'success' ? 'All goals followed' :
                  day.status === 'broken' ? 'Goals broken' :
                  day.status === 'non-trading' ? 'Non-trading day' :
                  'No data'
                }
              />
            ))}
          </div>
          <div className="flex items-center gap-4 text-xs text-muted-foreground">
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 rounded-sm bg-success" />
              <span>Followed</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 rounded-sm bg-destructive" />
              <span>Broken</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 rounded-sm bg-muted-foreground/30" />
              <span>No trading</span>
            </div>
          </div>
        </div>
        
        {/* Stats */}
        <div className="grid grid-cols-2 gap-3 pt-3 border-t border-border">
          <div className="text-center p-3 rounded-lg bg-muted/50">
            <p className="text-2xl font-bold font-mono">{streak.longest_streak_days}</p>
            <p className="text-xs text-muted-foreground">Longest Streak</p>
          </div>
          <div className="text-center p-3 rounded-lg bg-muted/50">
            <p className="text-2xl font-bold font-mono">{streak.milestones_achieved.length}</p>
            <p className="text-xs text-muted-foreground">Milestones</p>
          </div>
        </div>
        
        {/* Recent Milestones */}
        {streak.milestones_achieved.length > 0 && (
          <div className="space-y-2">
            <p className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <Trophy className="h-4 w-4" />
              Achievements
            </p>
            <div className="flex flex-wrap gap-2">
              {streak.milestones_achieved.map((milestone) => (
                <Badge key={milestone.days} variant="secondary">
                  🏆 {milestone.label}
                </Badge>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
