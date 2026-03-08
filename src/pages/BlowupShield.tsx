import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  ArrowLeft, Shield, AlertTriangle, Loader2,
  Flame, CheckCircle2, XCircle, MinusCircle, TrendingUp,
  Clock, Sparkles, Info,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { formatCurrency, formatRelativeTime } from '@/lib/formatters';
import { useBroker } from '@/contexts/BrokerContext';
import { api } from '@/lib/api';
import type { ShieldSummary, ShieldTimelineItem, PatternBreakdown } from '@/types/api';

const outcomeConfig = {
  heeded: { label: 'Heeded', icon: CheckCircle2, color: 'text-green-600 dark:text-green-400', bg: 'bg-green-100 dark:bg-green-900/30' },
  partially_heeded: { label: 'Partial', icon: MinusCircle, color: 'text-amber-600 dark:text-amber-400', bg: 'bg-amber-100 dark:bg-amber-900/30' },
  ignored: { label: 'Ignored', icon: XCircle, color: 'text-red-600 dark:text-red-400', bg: 'bg-red-100 dark:bg-red-900/30' },
} as const;

export default function BlowupShieldPage() {
  const { account } = useBroker();
  const [summary, setSummary] = useState<ShieldSummary | null>(null);
  const [timeline, setTimeline] = useState<ShieldTimelineItem[]>([]);
  const [patterns, setPatterns] = useState<PatternBreakdown[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchShieldData() {
      if (!account?.id) { setLoading(false); return; }
      try {
        setLoading(true);
        const [summaryRes, timelineRes, patternsRes] = await Promise.all([
          api.get<ShieldSummary>('/api/shield/summary'),
          api.get<{ timeline: ShieldTimelineItem[] }>('/api/shield/timeline?limit=50'),
          api.get<{ patterns: PatternBreakdown[] }>('/api/shield/patterns'),
        ]);
        setSummary(summaryRes.data);
        setTimeline(timelineRes.data.timeline);
        setPatterns(patternsRes.data.patterns);
        setError(null);
      } catch (err) {
        console.error('Failed to fetch shield data:', err);
        setError('Failed to load protection data');
      } finally {
        setLoading(false);
      }
    }
    fetchShieldData();
  }, [account?.id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  const s = summary || {
    capital_defended: 0, this_week: 0, this_month: 0, shield_score: 0,
    total_alerts: 0, heeded: 0, ignored: 0, heeded_streak: 0,
    blowups_prevented: 0, data_points: 0,
    checkpoint_coverage: { complete: 0, calculating: 0, unavailable: 0 },
  };

  const coverage = s.checkpoint_coverage;
  const coveragePct = s.total_alerts > 0
    ? Math.round(coverage.complete / s.total_alerts * 100)
    : 0;

  return (
    <div className="max-w-4xl mx-auto pb-12">
      {/* Back */}
      <Link
        to="/dashboard"
        className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground mb-6"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Dashboard
      </Link>

      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <div className="p-2 rounded-lg bg-gradient-to-br from-primary/20 to-green-500/20 border border-primary/20">
            <Shield className="h-6 w-6 text-primary" />
          </div>
          <h1 className="text-2xl font-bold text-foreground">Blowup Shield</h1>
        </div>
        <p className="text-muted-foreground">
          Real counterfactual P&L — what would have happened if you held.
        </p>
      </motion.div>

      {/* Hero Stats */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4"
      >
        {/* Capital Defended */}
        <div className="md:col-span-1 bg-gradient-to-br from-primary/10 via-card to-green-500/5 rounded-lg border border-primary/20 p-6 relative overflow-hidden">
          <div className="absolute top-0 right-0 w-24 h-24 bg-gradient-to-bl from-primary/10 to-transparent rounded-bl-full" />
          <div className="relative">
            <div className="flex items-center gap-2 mb-2">
              <Shield className="h-4 w-4 text-primary" />
              <p className="text-xs font-medium text-primary uppercase tracking-wide">Capital Defended</p>
            </div>
            <p className="text-3xl font-bold font-mono text-foreground">
              {s.data_points > 0 ? formatCurrency(s.capital_defended) : '—'}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              {s.data_points > 0 ? `from ${s.data_points} verified alerts` : 'no verified data yet'}
            </p>
          </div>
        </div>

        {/* Shield Score */}
        <div className="bg-card rounded-lg border border-border p-6">
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp className="h-4 w-4 text-primary" />
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Shield Score</p>
          </div>
          <p className={cn(
            'text-3xl font-bold font-mono',
            s.shield_score >= 70 ? 'text-green-600 dark:text-green-400' :
              s.shield_score >= 40 ? 'text-amber-600 dark:text-amber-400' :
                'text-red-600 dark:text-red-400'
          )}>
            {s.shield_score}%
          </p>
          <p className="text-xs text-muted-foreground mt-1">
            {s.heeded} heeded / {s.total_alerts} total alerts
          </p>
        </div>

        {/* Heeded Streak */}
        <div className="bg-card rounded-lg border border-border p-6">
          <div className="flex items-center gap-2 mb-2">
            <Flame className="h-4 w-4 text-amber-500" />
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Heeded Streak</p>
          </div>
          <p className="text-3xl font-bold font-mono text-foreground">
            {s.heeded_streak}
          </p>
          <p className="text-xs text-muted-foreground mt-1">consecutive alerts heeded</p>
        </div>
      </motion.div>

      {/* Data coverage bar */}
      {s.total_alerts > 0 && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.15 }}
          className="mb-8 bg-card rounded-lg border border-border p-4"
        >
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              Real data coverage
            </span>
            <span className="text-xs font-mono text-foreground">
              {coverage.complete}/{s.total_alerts} alerts verified
            </span>
          </div>
          <div className="h-2 rounded-full bg-muted overflow-hidden flex">
            {coverage.complete > 0 && (
              <div
                className="bg-green-500 h-full"
                style={{ width: `${coverage.complete / s.total_alerts * 100}%` }}
              />
            )}
            {coverage.calculating > 0 && (
              <div
                className="bg-amber-400 h-full"
                style={{ width: `${coverage.calculating / s.total_alerts * 100}%` }}
              />
            )}
          </div>
          <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-green-500 inline-block" />
              {coverage.complete} verified
            </span>
            {coverage.calculating > 0 && (
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-amber-400 inline-block" />
                {coverage.calculating} calculating
              </span>
            )}
            {coverage.unavailable > 0 && (
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-muted-foreground/30 inline-block" />
                {coverage.unavailable} no position
              </span>
            )}
          </div>
        </motion.div>
      )}

      {/* Secondary metrics */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="grid grid-cols-3 gap-4 mb-8"
      >
        <div className="bg-card rounded-lg border border-border p-4 text-center">
          <p className="text-xs text-muted-foreground mb-1">This Week</p>
          <p className="text-lg font-bold font-mono text-foreground">
            {s.this_week > 0 ? formatCurrency(s.this_week) : '—'}
          </p>
        </div>
        <div className="bg-card rounded-lg border border-border p-4 text-center">
          <p className="text-xs text-muted-foreground mb-1">This Month</p>
          <p className="text-lg font-bold font-mono text-foreground">
            {s.this_month > 0 ? formatCurrency(s.this_month) : '—'}
          </p>
        </div>
        <div className="bg-card rounded-lg border border-border p-4 text-center">
          <p className="text-xs text-muted-foreground mb-1">Blowups Prevented</p>
          <p className="text-lg font-bold font-mono text-foreground">{s.blowups_prevented}</p>
        </div>
      </motion.div>

      {/* Pattern Breakdown */}
      {patterns.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.25 }}
          className="bg-card rounded-lg border border-border mb-8"
        >
          <div className="px-5 py-4 border-b border-border">
            <h2 className="text-base font-semibold text-foreground">Pattern Breakdown</h2>
            <p className="text-sm text-muted-foreground">Real savings grouped by pattern</p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-muted-foreground">
                  <th className="text-left px-5 py-3 font-medium">Pattern</th>
                  <th className="text-center px-3 py-3 font-medium">Alerts</th>
                  <th className="text-center px-3 py-3 font-medium">Heeded %</th>
                  <th className="text-right px-3 py-3 font-medium">Avg Saved</th>
                  <th className="text-right px-5 py-3 font-medium">Total Saved</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {patterns.map((p) => (
                  <tr key={p.pattern_type} className="hover:bg-muted/30 transition-colors">
                    <td className="px-5 py-3 font-medium text-foreground">{p.display_name}</td>
                    <td className="text-center px-3 py-3 text-muted-foreground">{p.alerts}</td>
                    <td className="text-center px-3 py-3">
                      <span className={cn(
                        'font-mono font-medium',
                        p.heeded_pct >= 70 ? 'text-green-600 dark:text-green-400' :
                          p.heeded_pct >= 40 ? 'text-amber-600 dark:text-amber-400' :
                            'text-red-600 dark:text-red-400'
                      )}>
                        {p.heeded_pct}%
                      </span>
                    </td>
                    <td className="text-right px-3 py-3 font-mono text-muted-foreground">
                      {p.avg_defended > 0 ? formatCurrency(p.avg_defended) : '—'}
                    </td>
                    <td className="text-right px-5 py-3 font-mono font-medium text-primary">
                      {p.total_defended > 0 ? formatCurrency(p.total_defended) : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </motion.div>
      )}

      {/* Intervention Timeline */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
        className="bg-card rounded-lg border border-border"
      >
        <div className="px-5 py-4 border-b border-border">
          <h2 className="text-base font-semibold text-foreground">Intervention Timeline</h2>
          <p className="text-sm text-muted-foreground">Each alert — what happened, what would have happened</p>
        </div>

        {error ? (
          <div className="p-8 text-center">
            <AlertTriangle className="h-8 w-8 text-destructive mx-auto mb-2" />
            <p className="text-sm text-muted-foreground">{error}</p>
          </div>
        ) : timeline.length === 0 ? (
          <div className="p-8 text-center">
            <Shield className="h-12 w-12 text-muted-foreground/50 mx-auto mb-3" />
            <p className="text-base font-medium text-foreground mb-1">Shield Standing By</p>
            <p className="text-sm text-muted-foreground">
              When a danger pattern is detected, the shield snapshots your position and tracks
              what would have happened if you held. Those results appear here.
            </p>
          </div>
        ) : (
          <div className="divide-y divide-border">
            {timeline.map((event, idx) => {
              const oc = outcomeConfig[event.outcome] || outcomeConfig.ignored;
              const OutcomeIcon = oc.icon;
              const isComplete = event.calculation_status === 'complete';
              const isCalculating = event.calculation_status === 'pending' || event.calculation_status === 'calculating';
              const hasPosition = event.calculation_status !== 'no_positions' && event.calculation_status !== null;

              return (
                <motion.div
                  key={event.id}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.35 + idx * 0.03 }}
                  className="p-5"
                >
                  {/* Top row */}
                  <div className="flex items-start justify-between gap-4 mb-3">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1 flex-wrap">
                        {/* Pattern badge */}
                        <span className={cn(
                          'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium',
                          event.severity === 'danger' || event.severity === 'critical'
                            ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                            : 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400'
                        )}>
                          {(event.pattern_type || '').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                        </span>

                        {/* Outcome badge */}
                        <span className={cn('inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium', oc.bg, oc.color)}>
                          <OutcomeIcon className="h-3 w-3" />
                          {oc.label}
                        </span>

                        {/* Data quality badge */}
                        {isComplete && (
                          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">
                            <Sparkles className="h-3 w-3" />
                            Verified
                          </span>
                        )}
                        {isCalculating && (
                          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">
                            <Clock className="h-3 w-3" />
                            Calculating…
                          </span>
                        )}

                        <span className="text-xs text-muted-foreground">
                          {event.detected_at ? formatRelativeTime(event.detected_at) : ''}
                        </span>
                      </div>

                      <p className="text-sm font-medium text-foreground">{event.trigger_symbol}</p>
                      {event.trigger_trade && (
                        <p className="text-xs text-muted-foreground mt-0.5">
                          {event.trigger_trade.transaction_type} {event.trigger_trade.quantity} @ {formatCurrency(event.trigger_trade.average_price)}
                        </p>
                      )}
                    </div>

                    {/* Right side: money result */}
                    {isCalculating ? (
                      <div className="text-right flex-shrink-0">
                        <Clock className="h-4 w-4 text-amber-500 animate-pulse mx-auto mb-1" />
                        <p className="text-xs text-muted-foreground">pending T+30</p>
                      </div>
                    ) : isComplete && event.money_saved !== null ? (
                      <div className="text-right flex-shrink-0">
                        <p className={cn(
                          'text-lg font-bold font-mono',
                          (event.money_saved ?? 0) >= 0 ? 'text-primary' : 'text-destructive'
                        )}>
                          {(event.money_saved ?? 0) >= 0 ? '+' : ''}{formatCurrency(event.money_saved ?? 0)}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {(event.money_saved ?? 0) >= 0 ? 'saved' : 'missed gain'}
                        </p>
                      </div>
                    ) : null}
                  </div>

                  {/* Breakdown box */}
                  <div className="bg-muted/30 rounded-lg p-3 text-xs">
                    {isComplete && event.money_saved !== null ? (
                      <>
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-muted-foreground">Your P&L (30 min after alert):</span>
                          <span className={cn(
                            'font-mono',
                            (event.user_actual_pnl ?? 0) >= 0
                              ? 'text-green-600 dark:text-green-400'
                              : 'text-destructive'
                          )}>
                            {event.user_actual_pnl !== null
                              ? `${(event.user_actual_pnl ?? 0) >= 0 ? '+' : ''}${formatCurrency(event.user_actual_pnl ?? 0)}`
                              : 'no trades'}
                          </span>
                        </div>
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-muted-foreground">If position held to T+30:</span>
                          <span className={cn(
                            'font-mono',
                            (event.counterfactual_pnl_t30 ?? 0) >= 0
                              ? 'text-green-600 dark:text-green-400'
                              : 'text-destructive'
                          )}>
                            {event.counterfactual_pnl_t30 !== null
                              ? `${(event.counterfactual_pnl_t30 ?? 0) >= 0 ? '+' : ''}${formatCurrency(event.counterfactual_pnl_t30 ?? 0)}`
                              : '—'}
                          </span>
                        </div>
                        <div className="flex items-center justify-between pt-1 border-t border-border">
                          <span className="text-foreground font-medium">Difference (real saving):</span>
                          <span className={cn(
                            'font-mono font-bold',
                            (event.money_saved ?? 0) >= 0 ? 'text-primary' : 'text-destructive'
                          )}>
                            {(event.money_saved ?? 0) >= 0 ? '+' : ''}{formatCurrency(event.money_saved ?? 0)}
                          </span>
                        </div>
                        <div className="flex items-center gap-1 mt-2">
                          <Sparkles className="h-3 w-3 text-green-500" />
                          <span className="text-muted-foreground">
                            Real market prices at T+30 — not estimated
                          </span>
                        </div>
                      </>
                    ) : isCalculating ? (
                      <div className="flex items-center gap-2 text-amber-600 dark:text-amber-400">
                        <Clock className="h-3 w-3 animate-pulse flex-shrink-0" />
                        <span>
                          Position snapshot taken. Fetching T+30 market price to compute real saving. Check back in a few minutes.
                        </span>
                      </div>
                    ) : event.calculation_status === 'no_positions' ? (
                      <div className="flex items-center gap-2 text-muted-foreground">
                        <Info className="h-3 w-3 flex-shrink-0" />
                        <span>
                          No open position in {event.trigger_symbol} at alert time — nothing to track.
                        </span>
                      </div>
                    ) : (
                      <div className="flex items-center gap-2 text-muted-foreground">
                        <Info className="h-3 w-3 flex-shrink-0" />
                        <span>
                          This alert predates the checkpoint system — no counterfactual data available.
                        </span>
                      </div>
                    )}
                  </div>
                </motion.div>
              );
            })}
          </div>
        )}
      </motion.div>

      {/* How it works */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.6 }}
        className="mt-6 p-4 bg-muted/30 rounded-lg border border-border"
      >
        <div className="flex items-start gap-3">
          <Info className="h-5 w-5 text-muted-foreground flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-foreground mb-1">How savings are calculated</p>
            <p className="text-xs text-muted-foreground leading-relaxed">
              When a danger alert fires, we snapshot your open position and the live market price.
              At T+30 minutes we fetch the actual market price again and compute what your P&L
              would have been if you held. <strong>Saving = your actual P&L − counterfactual P&L at T+30.</strong>
              {' '}This can be negative — if the market recovered after you exited, we show that honestly.
              No estimates, no hardcoded defaults.
            </p>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
