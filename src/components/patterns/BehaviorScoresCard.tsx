import { useEffect, useState } from 'react';
import { Activity } from 'lucide-react';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';

interface Contributor { detector: string; severity: string; contribution: number; age_min: number }
interface Scores {
  behavior_risk: number;
  band: string;
  drivers: { tilt: number; risk: number; discipline: number; strategy: number };
  contributors: Record<string, Contributor[]>;
}

const DRIVER_LABELS: Record<string, string> = {
  tilt: 'Tilt (emotional)',
  risk: 'Risk',
  discipline: 'Discipline',
  strategy: 'Strategy health',
};

function barColor(v: number) {
  if (v >= 80) return 'bg-tm-loss';
  if (v >= 60) return 'bg-tm-loss/70';
  if (v >= 30) return 'bg-amber-500';
  return 'bg-tm-profit';
}

/**
 * Full scores detail (master §1D.9): one headline, four drivers, contributors.
 * Scores decay through the session — quiet hours bring them down naturally.
 */
export function BehaviorScoresCard() {
  const [scores, setScores] = useState<Scores | null>(null);

  useEffect(() => {
    api.get('/api/risk/scores').then(r => setScores(r.data)).catch(() => {});
  }, []);

  if (!scores) return null;

  const headlineColor =
    scores.behavior_risk >= 80 ? 'text-tm-loss' :
    scores.behavior_risk >= 60 ? 'text-tm-loss/80' :
    scores.behavior_risk >= 30 ? 'text-amber-600 dark:text-amber-400' : 'text-tm-profit';

  return (
    <div className="tm-card overflow-hidden">
      <div className="px-5 py-3.5 border-b border-border flex items-center justify-between">
        <h2 className="text-sm font-semibold text-foreground flex items-center gap-2">
          <Activity className="h-4 w-4 text-tm-brand" />
          Behavior Risk
        </h2>
        <span className="text-[11px] text-muted-foreground">today, decays over time</span>
      </div>
      <div className="p-5">
        <div className="flex items-baseline gap-3 mb-5">
          <span className={cn('text-4xl font-bold font-mono tabular-nums', headlineColor)}>
            {Math.round(scores.behavior_risk)}
          </span>
          <span className="text-sm text-muted-foreground capitalize">{scores.band}</span>
        </div>

        <div className="space-y-3">
          {(Object.keys(DRIVER_LABELS) as Array<keyof typeof scores.drivers>).map((key) => {
            const v = scores.drivers[key] ?? 0;
            const top = (scores.contributors?.[key] || [])[0];
            return (
              <div key={key}>
                <div className="flex items-baseline justify-between mb-1">
                  <span className="text-sm text-foreground">{DRIVER_LABELS[key]}</span>
                  <span className="text-xs font-mono text-muted-foreground">{Math.round(v)}</span>
                </div>
                <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                  <div className={cn('h-full rounded-full transition-all', barColor(v))}
                       style={{ width: `${Math.min(v, 100)}%` }} />
                </div>
                {top && v >= 10 && (
                  <p className="text-[11px] text-muted-foreground mt-1">
                    Top driver: {top.detector.replace(/_/g, ' ')} ({top.severity}, {top.age_min}m ago)
                  </p>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
