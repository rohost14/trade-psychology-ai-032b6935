import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Activity } from 'lucide-react';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';

interface Scores {
  behavior_risk: number;
  band: 'normal' | 'elevated' | 'high' | 'critical';
}

const BAND_STYLES: Record<string, string> = {
  normal:   'bg-tm-profit/10 text-tm-profit border-tm-profit/20',
  elevated: 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20',
  high:     'bg-tm-loss/10 text-tm-loss border-tm-loss/20',
  critical: 'bg-tm-loss/20 text-tm-loss border-tm-loss/40 animate-pulse',
};

const BAND_LABELS: Record<string, string> = {
  normal: 'Normal', elevated: 'Elevated', high: 'High', critical: 'Critical',
};

/**
 * Dashboard coarse band (master Q10): users shouldn't need to visit Analytics
 * to know they're tilted. Band only here; the number and drivers live in
 * My Patterns. Ambient state, not an alert.
 */
export function BehaviorRiskBadge() {
  const [scores, setScores] = useState<Scores | null>(null);

  useEffect(() => {
    let alive = true;
    const load = () =>
      api.get('/api/risk/scores')
        .then(r => { if (alive) setScores(r.data); })
        .catch(() => {});
    load();
    const t = setInterval(load, 120_000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  if (!scores) return null;

  return (
    <Link
      to="/my-patterns"
      title="Behavior Risk. Tap for drivers and details."
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-colors',
        BAND_STYLES[scores.band] || BAND_STYLES.normal,
      )}
    >
      <Activity className="h-3 w-3" />
      Behavior Risk: {BAND_LABELS[scores.band] || scores.band}
    </Link>
  );
}
