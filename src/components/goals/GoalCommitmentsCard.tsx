import { Lock, Unlock, CheckCircle2, AlertTriangle, XCircle, Calendar } from 'lucide-react';
import { TradingGoals, GoalAdherence } from '@/types/patterns';

interface GoalCommitmentsCardProps {
  goals: TradingGoals;
  adherence: GoalAdherence[];
  isReviewOpen: boolean;
  daysUntilReview: number;
  cooldown: { inCooldown: boolean; hoursRemaining?: number };
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

  const getAdherenceIcon = (pct: number) => {
    if (pct >= 80) return <CheckCircle2 className="h-4 w-4 text-tm-profit flex-shrink-0" />;
    if (pct >= 50) return <AlertTriangle className="h-4 w-4 text-tm-obs flex-shrink-0" />;
    return <XCircle className="h-4 w-4 text-tm-loss flex-shrink-0" />;
  };

  const getBarColor = (pct: number) => {
    if (pct >= 80) return 'bg-tm-profit';
    if (pct >= 50) return 'bg-tm-obs';
    return 'bg-tm-loss';
  };

  return (
    <div className="tm-card overflow-hidden">
      <div className="px-5 py-4 border-b border-border flex items-center justify-between">
        <p className="text-sm font-semibold text-foreground">My Trading Commitments</p>
        <span className={`inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full ${
          isLocked
            ? 'bg-muted text-muted-foreground'
            : 'bg-teal-50 dark:bg-teal-900/20 text-tm-brand'
        }`}>
          {isLocked ? <Lock className="h-2.5 w-2.5" /> : <Unlock className="h-2.5 w-2.5" />}
          {isLocked ? 'Locked' : 'Editable'}
        </span>
      </div>
      <div className="p-5 space-y-4">
        {/* Goal Items */}
        <div className="space-y-3">
          {adherence.map((item) => (
            <div key={item.goal_name} className="flex items-center justify-between p-3 rounded-lg bg-muted/40">
              <div className="flex items-center gap-3">
                {getAdherenceIcon(item.adherence_percent)}
                <div>
                  <p className="text-sm font-medium text-foreground">{item.goal_name}</p>
                  <p className="text-xs text-muted-foreground">{item.goal_value}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className="w-20 h-1.5 bg-muted rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${getBarColor(item.adherence_percent)}`}
                    style={{ width: `${item.adherence_percent}%` }}
                  />
                </div>
                <span className="text-sm font-mono tabular-nums w-10 text-right text-foreground">
                  {item.adherence_percent}%
                </span>
              </div>
            </div>
          ))}
        </div>

        {/* Review Info */}
        <div className="flex items-center justify-between pt-3 border-t border-border">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Calendar className="h-3.5 w-3.5" />
            {isReviewOpen ? (
              <span className="text-tm-brand font-medium">Review window open</span>
            ) : (
              <span>Next review in {daysUntilReview} days</span>
            )}
          </div>
          {isLocked && (
            <button
              onClick={onRequestChange}
              disabled={cooldown.inCooldown}
              className="text-xs font-medium px-3 py-1.5 rounded-lg border border-border hover:border-tm-brand/50 hover:text-tm-brand transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {cooldown.inCooldown ? `Wait ${cooldown.hoursRemaining}h` : 'Request Change'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
