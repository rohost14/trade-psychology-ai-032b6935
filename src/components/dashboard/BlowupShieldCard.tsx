import { useState, useEffect } from 'react';
import { ArrowRight, Shield, Flame, Loader2 } from 'lucide-react';
import { Link } from 'react-router-dom';
import { formatCurrency } from '@/lib/formatters';
import { cn } from '@/lib/utils';
import { useBroker } from '@/contexts/BrokerContext';
import { api } from '@/lib/api';
import type { ShieldSummary } from '@/types/api';

export default function BlowupShieldCard() {
  const { account } = useBroker();
  const [data, setData] = useState<ShieldSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchShield() {
      if (!account?.id) {
        setLoading(false);
        return;
      }
      try {
        const res = await api.get<ShieldSummary>('/api/shield/summary?days=7');
        setData(res.data);
      } catch {
        // Silently fail — card shows empty state
      } finally {
        setLoading(false);
      }
    }
    fetchShield();
  }, [account?.id]);

  if (loading) {
    return (
      <div className="bg-card rounded-lg border border-border p-6 flex items-center justify-center min-h-[180px]">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const s = data || {
    capital_defended: 0, this_week: 0, shield_score: 0,
    total_alerts: 0, heeded: 0, ignored: 0, heeded_streak: 0,
    blowups_prevented: 0, this_month: 0, methodology: 'bootstrap' as const, data_points: 0,
  };

  const hasActivity = s.this_week > 0 || s.total_alerts > 0;

  return (
    <div className="bg-card rounded-lg border border-border">
      <div className="p-6">
        {/* Header */}
        <div className="flex items-center gap-3 mb-5">
          <div className="p-2.5 rounded-lg bg-primary/10">
            <Shield className="h-5 w-5 text-primary" />
          </div>
          <div>
            <h3 className="text-base font-semibold text-foreground">Blowup Shield</h3>
            <p className="text-xs text-muted-foreground">Weekly protection</p>
          </div>
        </div>

        {/* Shield Score + Defended */}
        <div className="flex items-end justify-between mb-5">
          <div>
            <p className="text-xs text-muted-foreground mb-1">Capital Defended</p>
            <p className="text-2xl font-bold font-mono text-primary tabular-nums">
              {formatCurrency(s.this_week)}
            </p>
          </div>
          <div className="text-right">
            <p className="text-xs text-muted-foreground mb-1">Shield Score</p>
            <p className={cn(
              'text-2xl font-bold font-mono tabular-nums',
              s.shield_score >= 70 ? 'text-green-600 dark:text-green-400' :
                s.shield_score >= 40 ? 'text-amber-600 dark:text-amber-400' :
                  s.total_alerts === 0 ? 'text-muted-foreground' :
                    'text-red-600 dark:text-red-400'
            )}>
              {s.total_alerts > 0 ? `${s.shield_score}%` : '--'}
            </p>
          </div>
        </div>

        {/* Activity indicator */}
        <div className={cn(
          'p-3 rounded-lg border mb-5',
          hasActivity
            ? 'border-amber-200 bg-amber-50 dark:border-amber-800 dark:bg-amber-900/20'
            : 'border-green-200 bg-green-50 dark:border-green-800 dark:bg-green-900/20'
        )}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Flame className={cn(
                'h-4 w-4',
                hasActivity ? 'text-amber-600 dark:text-amber-400' : 'text-green-600 dark:text-green-400'
              )} />
              <span className="text-sm font-medium text-foreground">
                {hasActivity
                  ? `${s.heeded} of ${s.total_alerts} alerts heeded`
                  : 'No alerts this week'}
              </span>
            </div>
            {s.heeded_streak > 0 && (
              <span className="text-xs font-medium text-amber-600 dark:text-amber-400">
                {s.heeded_streak} streak
              </span>
            )}
          </div>
        </div>

        {/* Link to full page */}
        <Link
          to="/blowup-shield"
          className="flex items-center justify-between p-3 rounded-lg bg-muted/50 hover:bg-muted border border-border transition-colors group"
        >
          <span className="text-sm text-muted-foreground group-hover:text-foreground transition-colors font-medium">
            View protection history
          </span>
          <ArrowRight className="h-4 w-4 text-muted-foreground group-hover:text-primary transition-colors" />
        </Link>
      </div>
    </div>
  );
}
