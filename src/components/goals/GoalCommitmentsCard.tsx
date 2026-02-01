// Goal Commitments Card - Shows current goals with adherence stats
// Locked by default with friction-based changes

import { Lock, Unlock, CheckCircle2, AlertTriangle, XCircle, Calendar } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { TradingGoals, GoalAdherence } from '@/types/patterns';
import { cn } from '@/lib/utils';

interface GoalCommitmentsCardProps {
  goals: TradingGoals;
  adherence: GoalAdherence[];
  isReviewOpen: boolean;
  daysUntilReview: number;
  cooldown: {
    inCooldown: boolean;
    hoursRemaining?: number;
  };
  onRequestChange: () => void;
}

export function GoalCommitmentsCard({
  goals,
  adherence,
  isReviewOpen,
  daysUntilReview,
  cooldown,
  onRequestChange,
}: GoalCommitmentsCardProps) {
  const isLocked = !isReviewOpen && !cooldown.inCooldown;
  
  const getAdherenceIcon = (percent: number) => {
    if (percent >= 80) return <CheckCircle2 className="h-4 w-4 text-success" />;
    if (percent >= 50) return <AlertTriangle className="h-4 w-4 text-warning" />;
    return <XCircle className="h-4 w-4 text-destructive" />;
  };
  
  const getAdherenceColor = (percent: number) => {
    if (percent >= 80) return 'bg-success';
    if (percent >= 50) return 'bg-warning';
    return 'bg-destructive';
  };

  return (
    <Card className="border-risk-safe">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CardTitle className="text-lg">My Trading Commitments</CardTitle>
            <Badge variant={isLocked ? "secondary" : "default"} className="gap-1">
              {isLocked ? (
                <>
                  <Lock className="h-3 w-3" />
                  Locked
                </>
              ) : (
                <>
                  <Unlock className="h-3 w-3" />
                  Editable
                </>
              )}
            </Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Goal Items */}
        <div className="space-y-3">
          {adherence.map((item) => (
            <div
              key={item.goal_name}
              className="flex items-center justify-between p-3 rounded-lg bg-muted/50"
            >
              <div className="flex items-center gap-3">
                {getAdherenceIcon(item.adherence_percent)}
                <div>
                  <p className="font-medium text-sm">{item.goal_name}</p>
                  <p className="text-xs text-muted-foreground">{item.goal_value}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className="w-24">
                  <Progress 
                    value={item.adherence_percent} 
                    className={cn("h-2", getAdherenceColor(item.adherence_percent))}
                  />
                </div>
                <span className="text-sm font-mono w-12 text-right">
                  {item.adherence_percent}%
                </span>
              </div>
            </div>
          ))}
        </div>
        
        {/* Review Info */}
        <div className="flex items-center justify-between pt-3 border-t border-border">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Calendar className="h-4 w-4" />
            {isReviewOpen ? (
              <span className="text-success font-medium">Review window open (until 3rd)</span>
            ) : (
              <span>Next review: {daysUntilReview} days</span>
            )}
          </div>
          
          {isLocked && (
            <Button 
              variant="outline" 
              size="sm"
              onClick={onRequestChange}
              disabled={cooldown.inCooldown}
            >
              {cooldown.inCooldown 
                ? `Wait ${cooldown.hoursRemaining}h`
                : 'Request Early Change'
              }
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
