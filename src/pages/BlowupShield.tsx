import { useState, useEffect } from 'react';
import {
  ArrowLeft, Shield, AlertTriangle,
  CheckCircle2, XCircle, ChevronDown, ChevronUp,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { formatCurrencyWithSign, formatRelativeTime, formatCurrency } from '@/lib/formatters';
import { Skeleton } from '@/components/ui/skeleton';
import { useBroker } from '@/contexts/BrokerContext';
import { api } from '@/lib/api';
import type { ShieldSummary, ShieldTimelineItem, PatternBreakdown } from '@/types/api';

// Cache for 5 minutes
const CACHE_TTL_MS = 5 * 60 * 1000;
const shieldCache: {
  data: { summary: ShieldSummary; timeline: ShieldTimelineItem[]; patterns: PatternBreakdown[] } | null;
  ts: number;
  accountId: string | null;
} = { data: null, ts: 0, accountId: null };

function PatternLabel({ type }: { type: string }) {
  return (
    <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
      {type.replace(/_/g, ' ')}
    </span>
  );
}

function SeverityDot({ severity }: { severity: string }) {
  return (
    <span className={cn(
      'inline-block w-1.5 h-1.5 rounded-full flex-shrink-0',
      severity === 'danger' || severity === 'critical' ? 'bg-tm-loss' : 'bg-tm-obs',
    )} />
  );
}

function TimelineRow({ item }: { item: ShieldTimelineItem }) {
  const [expanded, setExpanded] = useState(false);
  const heeded = item.outcome === 'heeded';
  const hasTrades = item.post_alert_trades.length > 0;

  return (
    <div className="px-5 py-4 border-b border-border last:border-0">
      <div className="flex items-start gap-3">
        {/* Outcome icon */}
        <div className="mt-0.5 flex-shrink-0">
          {heeded
            ? <CheckCircle2 className="h-4 w-4 text-tm-profit" />
            : <XCircle className="h-4 w-4 text-tm-loss" />
          }
        </div>

        <div className="flex-1 min-w-0">
          {/* Header row */}
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <SeverityDot severity={item.severity} />
            <PatternLabel type={item.pattern_type} />
            {item.trigger_symbol && (
              <span className="text-xs font-medium text-foreground">{item.trigger_symbol}</span>
            )}
            <span className="text-xs text-muted-foreground ml-auto">
              {item.detected_at ? formatRelativeTime(item.detected_at) : ''}
            </span>
          </div>

          {/* Alert message */}
          <p className="text-sm text-foreground mb-2">{item.message}</p>

          {/* Narrative */}
          <p className={cn(
            'text-xs font-medium',
            heeded ? 'text-tm-profit' : item.post_alert_pnl < 0 ? 'text-tm-loss' : 'text-tm-obs',
          )}>
            {item.narrative}
          </p>

          {/* Expand trades when continued */}
          {!heeded && hasTrades && (
            <button
              onClick={() => setExpanded(v => !v)}
              className="mt-2 flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              {expanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
              {expanded ? 'Hide trades' : `Show ${item.post_alert_trades.length} trade${item.post_alert_trades.length !== 1 ? 's' : ''}`}
            </button>
          )}

          {expanded && (
            <div className="mt-2 rounded-md bg-muted/30 divide-y divide-border text-xs">
              {item.post_alert_trades.map((t, i) => (
                <div key={i} className="flex items-center justify-between px-3 py-2">
                  <span className="font-medium text-foreground">{t.tradingsymbol}</span>
                  <span className={cn(
                    'font-mono tabular-nums',
                    t.realized_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss',
                  )}>
                    {formatCurrencyWithSign(t.realized_pnl)}
                  </span>
                </div>
              ))}
              <div className="flex items-center justify-between px-3 py-2 font-medium">
                <span className="text-muted-foreground">Net</span>
                <span className={cn(
                  'font-mono tabular-nums',
                  item.post_alert_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss',
                )}>
                  {formatCurrencyWithSign(item.post_alert_pnl)}
                </span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function BlowupShieldPage() {
  const { account } = useBroker();
  const [summary, setSummary] = useState<ShieldSummary | null>(null);
  const [timeline, setTimeline] = useState<ShieldTimelineItem[]>([]);
  const [patterns, setPatterns] = useState<PatternBreakdown[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!account?.id) { setLoading(false); return; }

    async function fetchShieldData(force = false) {
      const now = Date.now();
      if (
        !force &&
        shieldCache.data &&
        shieldCache.accountId === account.id &&
        now - shieldCache.ts < CACHE_TTL_MS
      ) {
        setSummary(shieldCache.data.summary);
        setTimeline(shieldCache.data.timeline);
        setPatterns(shieldCache.data.patterns);
        setLoading(false);
        return;
      }
      try {
        setLoading(true);
        const [summaryRes, timelineRes, patternsRes] = await Promise.all([
          api.get<ShieldSummary>('/api/shield/summary'),
          api.get<{ timeline: ShieldTimelineItem[] }>('/api/shield/timeline?limit=50'),
          api.get<{ patterns: PatternBreakdown[] }>('/api/shield/patterns'),
        ]);
        const fresh = {
          summary: summaryRes.data,
          timeline: timelineRes.data.timeline,
          patterns: patternsRes.data.patterns,
        };
        shieldCache.data = fresh;
        shieldCache.ts = Date.now();
        shieldCache.accountId = account.id;
        setSummary(fresh.summary);
        setTimeline(fresh.timeline);
        setPatterns(fresh.patterns);
        setError(null);
      } catch (err) {
        console.error('Failed to fetch shield data:', err);
        setError('Failed to load protection data');
      } finally {
        setLoading(false);
      }
    }

    fetchShieldData();

    const onVisible = () => {
      if (document.visibilityState === 'visible') fetchShieldData();
    };
    document.addEventListener('visibilitychange', onVisible);
    return () => document.removeEventListener('visibilitychange', onVisible);
  }, [account?.id]);

  if (loading) {
    return (
      <div className="max-w-3xl mx-auto pb-12 space-y-4">
        <Skeleton className="h-5 w-32" />
        <Skeleton className="h-8 w-48" />
        <div className="grid grid-cols-4 gap-3">
          {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-20 rounded-xl" />)}
        </div>
        <Skeleton className="h-64 rounded-xl" />
      </div>
    );
  }

  const s = summary ?? {
    total_alerts: 0, danger_count: 0, caution_count: 0,
    heeded_count: 0, continued_count: 0, post_alert_pnl_continued: 0,
    heeded_streak: 0, spiral_sessions: 0,
  };

  const heedRate = s.total_alerts > 0
    ? Math.round(s.heeded_count / s.total_alerts * 100)
    : null;

  // Additional losses = continued P&L when negative
  const additionalLoss = s.post_alert_pnl_continued < 0 ? s.post_alert_pnl_continued : null;

  return (
    <div className="max-w-3xl mx-auto pb-12">
      <Link
        to="/dashboard"
        className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground mb-6"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Dashboard
      </Link>

      {/* Header */}
      <div className="mb-6 animate-fade-in-up">
        <h1 className="text-xl font-semibold text-foreground tracking-tight">Blowup Shield</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          What you did after each alert — facts only.
        </p>
      </div>

      {/* Summary metrics */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6 animate-fade-in-up">
        <div className="tm-card px-4 py-3">
          <p className="text-xs text-muted-foreground mb-1">Total Alerts</p>
          <p className="text-2xl font-semibold font-mono text-foreground">{s.total_alerts}</p>
          <p className="text-xs text-muted-foreground mt-0.5">
            {s.danger_count} danger · {s.caution_count} caution
          </p>
        </div>

        <div className="tm-card px-4 py-3">
          <p className="text-xs text-muted-foreground mb-1">Heeded Rate</p>
          <p className={cn(
            'text-2xl font-semibold font-mono',
            heedRate === null ? 'text-foreground' :
              heedRate >= 70 ? 'text-tm-profit' :
              heedRate >= 40 ? 'text-tm-obs' : 'text-tm-loss',
          )}>
            {heedRate !== null ? `${heedRate}%` : '—'}
          </p>
          <p className="text-xs text-muted-foreground mt-0.5">
            {s.heeded_count} stopped · {s.continued_count} kept going
          </p>
        </div>

        <div className="tm-card px-4 py-3">
          <p className="text-xs text-muted-foreground mb-1">Current Streak</p>
          <p className="text-2xl font-semibold font-mono text-foreground">{s.heeded_streak}</p>
          <p className="text-xs text-muted-foreground mt-0.5">consecutive heeded</p>
        </div>

        <div className="tm-card px-4 py-3">
          <p className="text-xs text-muted-foreground mb-1">
            {additionalLoss !== null ? 'Added Loss (ignored)' : 'Spiral Sessions'}
          </p>
          {additionalLoss !== null ? (
            <p className="text-2xl font-semibold font-mono text-tm-loss">
              {formatCurrencyWithSign(additionalLoss)}
            </p>
          ) : (
            <p className="text-2xl font-semibold font-mono text-foreground">{s.spiral_sessions}</p>
          )}
          <p className="text-xs text-muted-foreground mt-0.5">
            {additionalLoss !== null
              ? 'P&L after alerts were ignored'
              : 'days with 3+ danger alerts'}
          </p>
        </div>
      </div>

      {/* Pattern breakdown */}
      {patterns.length > 0 && (
        <div className="tm-card overflow-hidden mb-6 animate-fade-in-up">
          <div className="px-5 py-4 border-b border-border">
            <p className="text-sm font-medium text-foreground">By Pattern</p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-muted-foreground text-xs">
                  <th className="text-left px-5 py-3 font-medium">Pattern</th>
                  <th className="text-center px-3 py-3 font-medium">Alerts</th>
                  <th className="text-center px-3 py-3 font-medium">Heeded</th>
                  <th className="text-right px-5 py-3 font-medium">Post-alert P&L</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {patterns.map((p) => (
                  <tr key={p.pattern_type} className="hover:bg-muted/20 transition-colors">
                    <td className="px-5 py-3 font-medium text-foreground">{p.display_name}</td>
                    <td className="text-center px-3 py-3 text-muted-foreground font-mono">{p.alerts}</td>
                    <td className="text-center px-3 py-3">
                      <span className={cn(
                        'font-mono font-medium text-xs',
                        p.heeded_pct >= 70 ? 'text-tm-profit' :
                          p.heeded_pct >= 40 ? 'text-tm-obs' : 'text-tm-loss',
                      )}>
                        {p.heeded_pct}%
                      </span>
                    </td>
                    <td className="text-right px-5 py-3 font-mono">
                      {p.post_alert_pnl !== 0 ? (
                        <span className={p.post_alert_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss'}>
                          {formatCurrencyWithSign(p.post_alert_pnl)}
                        </span>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Timeline */}
      <div className="tm-card overflow-hidden animate-fade-in-up">
        <div className="px-5 py-4 border-b border-border">
          <p className="text-sm font-medium text-foreground">Alert History</p>
          <p className="text-xs text-muted-foreground mt-0.5">What happened after each alert</p>
        </div>

        {error ? (
          <div className="p-8 text-center">
            <AlertTriangle className="h-8 w-8 text-tm-loss mx-auto mb-2" />
            <p className="text-sm text-muted-foreground">{error}</p>
          </div>
        ) : timeline.length === 0 ? (
          <div className="p-8 text-center">
            <Shield className="h-12 w-12 text-muted-foreground/40 mx-auto mb-3" />
            <p className="text-base font-medium text-foreground mb-1">No alerts yet</p>
            <p className="text-sm text-muted-foreground">
              Behavioural alerts appear here as you trade. Each one shows whether you stopped or kept going.
            </p>
          </div>
        ) : (
          <div>
            {timeline.map((item) => (
              <TimelineRow key={item.id} item={item} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
