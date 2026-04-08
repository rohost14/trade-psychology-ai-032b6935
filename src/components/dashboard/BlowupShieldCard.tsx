import { useState, useEffect } from 'react';
import { ArrowRight, Shield } from 'lucide-react';
import { Link } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { formatCurrencyWithSign } from '@/lib/formatters';
import { useBroker } from '@/contexts/BrokerContext';
import { api } from '@/lib/api';
import type { ShieldSummary } from '@/types/api';

export default function BlowupShieldCard() {
  const { account } = useBroker();
  const [data, setData] = useState<ShieldSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchShield() {
      if (!account?.id) { setLoading(false); return; }
      try {
        const res = await api.get<ShieldSummary>('/api/shield/summary?days=30');
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
      <div className="tm-card p-5 bg-gradient-to-br from-teal-50 to-white dark:from-teal-950/30 dark:to-[#1C1C1C]">
        <div className="flex items-center justify-between mb-4">
          <span className="tm-label">Blowup Shield</span>
          <Shield className="w-4 h-4 text-teal-400 dark:text-teal-500" />
        </div>
        <div className="space-y-3">
          <div className="h-10 bg-muted/60 rounded animate-pulse w-20" />
          <div className="h-3 bg-muted/60 rounded animate-pulse w-32" />
          <div className="h-1.5 bg-muted/60 rounded animate-pulse" />
        </div>
      </div>
    );
  }

  const s = data ?? {
    total_alerts: 0, danger_count: 0, caution_count: 0,
    heeded_count: 0, continued_count: 0, post_alert_pnl_continued: 0,
    heeded_streak: 0, spiral_sessions: 0,
  };

  const heedRate = (s.total_alerts > 0 && Number.isFinite(s.heeded_count))
    ? Math.round((s.heeded_count ?? 0) / s.total_alerts * 100)
    : null;

  const additionalLoss = Number.isFinite(s.post_alert_pnl_continued) && s.post_alert_pnl_continued < 0
    ? s.post_alert_pnl_continued
    : null;

  return (
    <div className="tm-card p-5 bg-gradient-to-br from-teal-50 to-white dark:from-teal-950/30 dark:to-[#1C1C1C]">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <span className="tm-label">Blowup Shield</span>
        <Shield className="w-4 h-4 text-teal-400 dark:text-teal-500" />
      </div>

      {s.total_alerts === 0 ? (
        <p className="text-sm text-muted-foreground mb-4">No alerts yet this period.</p>
      ) : (
        <>
          {/* Heeded rate — hero number */}
          <div className="flex items-end gap-2 mb-1">
            <span className={cn(
              'text-[44px] font-black font-mono tabular-nums leading-none',
              heedRate === null ? 'text-foreground' :
                heedRate >= 70 ? 'text-tm-profit' :
                heedRate >= 40 ? 'text-tm-obs' : 'text-tm-loss',
            )}>
              {heedRate !== null ? `${heedRate}%` : '—'}
            </span>
          </div>
          <p className="text-[13px] text-muted-foreground mb-4">
            alerts heeded · {s.heeded_count}/{s.total_alerts} total
          </p>

          {/* Heeded progress bar */}
          <div className="h-1.5 rounded-full overflow-hidden bg-muted">
            <div
              className={cn(
                'h-full rounded-full transition-all duration-500',
                (heedRate ?? 0) >= 70 ? 'bg-tm-profit' :
                  (heedRate ?? 0) >= 40 ? 'bg-tm-obs' : 'bg-tm-loss',
              )}
              style={{ width: `${heedRate ?? 0}%` }}
            />
          </div>
          <div className="flex items-center justify-between mb-4 mt-1">
            <span className="text-[10px] text-muted-foreground">0%</span>
            <span className="text-[10px] text-muted-foreground">100% heeded</span>
          </div>

          {/* Additional loss callout when alerts were ignored */}
          {additionalLoss !== null && (
            <div className="flex items-center justify-between rounded-lg px-3 py-2.5 mb-4 bg-red-50/80 dark:bg-red-900/10 border border-red-100 dark:border-red-800/30">
              <span className="tm-label">After ignored alerts</span>
              <span className="text-sm font-semibold text-tm-loss font-mono tabular-nums">
                {formatCurrencyWithSign(additionalLoss)}
              </span>
            </div>
          )}

          {/* Streak */}
          {s.heeded_streak > 0 && (
            <p className="text-xs text-muted-foreground mb-4">
              Current streak: <span className="font-semibold text-tm-profit">{s.heeded_streak}</span> consecutive heeded
            </p>
          )}
        </>
      )}

      <Link
        to="/blowup-shield"
        className="flex items-center justify-between text-[13px] font-medium text-tm-brand hover:underline"
      >
        <span>View alert history</span>
        <ArrowRight className="w-3.5 h-3.5" />
      </Link>
    </div>
  );
}
