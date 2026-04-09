import { useState, useEffect } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, ReferenceLine,
} from 'recharts';
import {
  AlertTriangle, CheckCircle2, Brain, BookOpen, Shield,
  Clock, AlertCircle, Lightbulb, BarChart3, Zap, RefreshCw,
  Activity, Moon, ChevronDown, ArrowUpRight, ArrowDownRight,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatCurrencyWithSign } from '@/lib/formatters';
import { api } from '@/lib/api';

// ─── Types ────────────────────────────────────────────────────────────────────

interface DetectedPattern {
  name: string;
  category: string;
  is_positive: boolean;
  frequency: number;
  severity: string;
  pnl_impact: number;
  description: string;
  recommendation: string;
}

interface BehavioralData {
  behavior_score: number | null;
  patterns_detected: DetectedPattern[];
  emotional_tax: number;
  emotional_breakdown: Record<string, number>;
  top_strength: string;
  focus_area: string;
  total_trades_analyzed: number;
}

interface EmotionCorrelation {
  emotion: string;
  trade_count: number;
  avg_pnl: number;
  total_pnl: number;
  win_rate: number;
}

interface JournalData {
  has_data: boolean;
  total_journaled: number;
  by_emotion: EmotionCorrelation[];
}

interface AIInsightsData {
  has_data: boolean;
  personalization: any;
  trading_intensity: {
    avg_daily_trades: number;
    max_daily_trades: number;
    active_days: number;
    overtrade_days: number;
  } | null;
}

const SEV_ORDER: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3, positive: 4 };

const SEV_DOT: Record<string, string> = {
  critical: 'bg-tm-loss',
  high: 'bg-tm-loss',
  medium: 'bg-tm-obs',
  low: 'bg-slate-400',
  positive: 'bg-tm-profit',
};

const SEV_LABEL: Record<string, string> = {
  critical: 'text-tm-loss',
  high: 'text-tm-loss',
  medium: 'text-tm-obs',
  low: 'text-muted-foreground',
  positive: 'text-tm-profit',
};

const PROFIT_COLOR = '#16A34A';
const LOSS_COLOR   = '#DC2626';

// ─── Accordion wrapper ────────────────────────────────────────────────────────

function Accordion({ title, subtitle, defaultOpen = false, children }: {
  title: string; subtitle?: string; defaultOpen?: boolean; children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="tm-card overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-5 py-3.5 hover:bg-slate-50 dark:hover:bg-slate-700/30 transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="tm-label">{title}</span>
          {subtitle && <span className="text-[11px] text-muted-foreground">{subtitle}</span>}
        </div>
        <ChevronDown className={cn('w-4 h-4 text-muted-foreground/50 transition-transform duration-200', open && 'rotate-180')} />
      </button>
      {open && <div className="border-t border-slate-100 dark:border-neutral-700/60">{children}</div>}
    </div>
  );
}

// ─── Main Tab ─────────────────────────────────────────────────────────────────

export default function BehaviorTab({ days }: { days: number }) {
  const [behavioral, setBehavioral] = useState<BehavioralData | null>(null);
  const [journal, setJournal]       = useState<JournalData | null>(null);
  const [aiInsights, setAiInsights] = useState<AIInsightsData | null>(null);
  const [loading, setLoading]       = useState(true);
  const [showAllPatterns, setShowAllPatterns] = useState(false);

  useEffect(() => {
    let c = false;
    setLoading(true);
    Promise.allSettled([
      api.get('/api/behavioral/analysis', { params: { time_window_days: days } }),
      api.get('/api/analytics/journal-correlation', { params: { days } }),
      api.get('/api/analytics/ai-insights', { params: { days } }),
    ]).then(([r1, r2, r3]) => {
      if (c) return;
      if (r1.status === 'fulfilled') setBehavioral(r1.value.data);
      if (r2.status === 'fulfilled') setJournal(r2.value.data);
      if (r3.status === 'fulfilled') setAiInsights(r3.value.data);
      setLoading(false);
    });
    return () => { c = true; };
  }, [days]);

  if (loading) {
    return (
      <div className="space-y-4 animate-pulse">
        <div className="grid grid-cols-3 gap-4">{[1,2,3].map(i => <div key={i} className="h-28 tm-card" />)}</div>
        <div className="h-48 tm-card" />
        <div className="grid grid-cols-2 gap-4">{[1,2].map(i => <div key={i} className="h-40 tm-card" />)}</div>
      </div>
    );
  }

  if (!behavioral || behavioral.total_trades_analyzed < 5) {
    return (
      <div className="tm-card px-6 py-10 text-center">
        <Brain className="h-8 w-8 text-muted-foreground/40 mx-auto mb-3" />
        <p className="font-semibold text-foreground">Not enough data for behavioral analysis</p>
        <p className="text-[13px] text-muted-foreground mt-1 mb-6">Need at least 5 completed trades</p>
        <div className="grid grid-cols-2 gap-3 max-w-sm mx-auto">
          {[
            { stat: '89%', label: 'of F&O traders lose money', source: 'SEBI FY2023' },
            { stat: '73%', label: 'trades within 15 min of a loss are also losers', source: 'SEBI data' },
          ].map((item, i) => (
            <div key={i} className="p-3 rounded-lg bg-slate-50 dark:bg-neutral-700/30 border border-slate-100 dark:border-neutral-700/60 text-left">
              <p className="text-base font-bold text-tm-brand">{item.stat}</p>
              <p className="text-xs text-foreground mt-0.5 leading-snug">{item.label}</p>
              <p className="text-[10px] text-muted-foreground mt-1">{item.source}</p>
            </div>
          ))}
        </div>
      </div>
    );
  }

  const score    = behavioral.behavior_score;
  const dangers  = behavioral.patterns_detected.filter(p => !p.is_positive)
    .sort((a, b) => (SEV_ORDER[a.severity] ?? 3) - (SEV_ORDER[b.severity] ?? 3));
  const strengths = behavioral.patterns_detected.filter(p => p.is_positive);
  const allPatterns = [...behavioral.patterns_detected]
    .sort((a, b) => (SEV_ORDER[a.severity] ?? 3) - (SEV_ORDER[b.severity] ?? 3));
  const visiblePatterns = showAllPatterns ? allPatterns : allPatterns.slice(0, 3);

  const emotionalBreakdown = Object.entries(behavioral.emotional_breakdown || {})
    .map(([name, amount]) => ({ name: name.replace(/_/g, ' '), value: Math.abs(amount) }))
    .filter(d => d.value > 0)
    .sort((a, b) => b.value - a.value);
  const maxTax = Math.max(...emotionalBreakdown.map(e => e.value), 1);

  const scoreCls = score == null ? 'text-muted-foreground'
    : score >= 70 ? 'text-tm-profit'
    : score >= 40 ? 'text-tm-obs'
    : 'text-tm-loss';

  const scoreLabel = score == null ? 'Need 5+ trades'
    : score >= 70 ? 'Disciplined'
    : score >= 40 ? 'Improving'
    : 'High interference';

  return (
    <div className="space-y-4">

      {/* ── Hero KPIs ─────────────────────────────────────────────────── */}
      <div className="grid grid-cols-3 gap-4">
        {/* Behavior Score */}
        <div className="tm-card px-5 py-4">
          <span className="tm-label">Behavior Score</span>
          <div className="flex items-baseline gap-1.5 mt-2">
            <p className={cn('text-[40px] font-black font-mono tabular-nums leading-none', scoreCls)}>
              {score ?? '—'}
            </p>
            {score != null && <span className="text-sm text-muted-foreground">/100</span>}
          </div>
          <p className="text-[12px] text-muted-foreground mt-1.5">{scoreLabel}</p>
          {score != null && (
            <div className="mt-2 h-1.5 rounded-full bg-slate-100 dark:bg-neutral-700/50 overflow-hidden">
              <div
                className={cn('h-full rounded-full transition-all duration-500',
                  score >= 70 ? 'bg-tm-profit' : score >= 40 ? 'bg-tm-obs' : 'bg-tm-loss')}
                style={{ width: `${score}%` }}
              />
            </div>
          )}
        </div>

        {/* Emotional Tax */}
        <div className="tm-card px-5 py-4">
          <span className="tm-label">Emotional Tax</span>
          <p className="text-[32px] font-black font-mono tabular-nums leading-none text-tm-loss mt-2">
            {formatCurrencyWithSign(-behavioral.emotional_tax)}
          </p>
          <p className="text-[12px] text-muted-foreground mt-1.5">Lost to patterns in {days}d</p>

          {/* Top breakdown bar */}
          {emotionalBreakdown.length > 0 && (
            <div className="mt-3 space-y-1.5">
              {emotionalBreakdown.slice(0, 2).map(item => (
                <div key={item.name} className="flex items-center gap-2">
                  <span className="text-[11px] text-muted-foreground capitalize w-24 truncate">{item.name}</span>
                  <div className="flex-1 h-1 bg-slate-100 dark:bg-neutral-700/50 rounded-full overflow-hidden">
                    <div className="h-full bg-tm-loss rounded-full" style={{ width: `${(item.value / maxTax) * 100}%` }} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Analyzed */}
        <div className="tm-card px-5 py-4">
          <span className="tm-label">Analyzed</span>
          <p className="text-[40px] font-black font-mono tabular-nums leading-none text-foreground mt-2">
            {behavioral.total_trades_analyzed}
          </p>
          <p className="text-[12px] text-muted-foreground mt-1.5">
            <span className="text-tm-loss font-medium">{dangers.length} risk{dangers.length !== 1 ? 's' : ''}</span>
            <span className="text-muted-foreground/40 mx-1.5">·</span>
            <span className="text-tm-profit font-medium">{strengths.length} strength{strengths.length !== 1 ? 's' : ''}</span>
          </p>
        </div>
      </div>

      {/* ── Detected Patterns ─────────────────────────────────────────── */}
      {allPatterns.length > 0 && (
        <div className="tm-card overflow-hidden">
          <div className="flex items-center justify-between px-5 py-3 border-b border-slate-100 dark:border-neutral-700/60">
            <span className="tm-label">Detected Patterns</span>
            {allPatterns.length > 3 && (
              <button
                onClick={() => setShowAllPatterns(v => !v)}
                className="text-[12px] font-medium text-tm-brand hover:underline"
              >
                {showAllPatterns ? 'Show less' : `Show all ${allPatterns.length}`}
              </button>
            )}
          </div>
          <div className="divide-y divide-slate-50 dark:divide-slate-700/30">
            {visiblePatterns.map((p, i) => (
              <div key={i} className="flex items-start gap-4 px-5 py-3.5 hover:bg-slate-50 dark:hover:bg-slate-700/20 transition-colors">
                {/* Severity dot */}
                <span className={cn('mt-1.5 w-2 h-2 rounded-full shrink-0', SEV_DOT[p.severity] ?? 'bg-slate-400')} />
                {/* Content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-0.5">
                    <span className="text-sm font-semibold text-foreground">{p.name}</span>
                    <span className="tm-chip tm-chip-eq">{p.category}</span>
                    <span className={cn('text-[10px] font-bold uppercase tracking-wide', SEV_LABEL[p.severity] ?? 'text-muted-foreground')}>
                      {p.severity}
                    </span>
                  </div>
                  <p className="text-[12px] text-muted-foreground leading-snug">{p.description}</p>
                  {p.recommendation && (
                    <p className="text-[12px] text-tm-brand mt-1 leading-snug">→ {p.recommendation}</p>
                  )}
                </div>
                {/* Stats */}
                <div className="shrink-0 text-right">
                  <p className="text-sm font-mono tabular-nums text-muted-foreground">{p.frequency}×</p>
                  {p.pnl_impact > 0 && (
                    <p className="text-[12px] font-mono tabular-nums text-tm-loss font-semibold mt-0.5">
                      {formatCurrencyWithSign(-p.pnl_impact)}
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Conditional Performance ───────────────────────────────────── */}
      <ConditionalPerformanceCard days={days} />

      {/* ── Strengths vs Areas to Improve ────────────────────────────── */}
      {(dangers.length > 0 || strengths.length > 0) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Areas to Improve */}
          <div className="tm-card overflow-hidden">
            <div className="flex items-center gap-2 px-5 py-3 border-b border-slate-100 dark:border-neutral-700/60">
              <AlertTriangle className="h-3.5 w-3.5 text-tm-loss" />
              <span className="tm-label">Areas to Improve</span>
              <span className="text-[11px] text-muted-foreground ml-1">({dangers.length})</span>
            </div>
            {dangers.length > 0 ? (
              <div className="divide-y divide-slate-50 dark:divide-slate-700/30">
                {dangers.map((p, i) => (
                  <div key={i} className="px-5 py-3">
                    <div className="flex items-center justify-between mb-0.5">
                      <span className="text-sm font-semibold text-foreground">{p.name}</span>
                      <div className="flex items-center gap-2">
                        {p.pnl_impact > 0 && (
                          <span className="text-[12px] font-mono tabular-nums text-tm-loss">{formatCurrencyWithSign(-p.pnl_impact)}</span>
                        )}
                        <span className="text-[12px] font-mono tabular-nums text-muted-foreground">{p.frequency}×</span>
                      </div>
                    </div>
                    <p className="text-[12px] text-muted-foreground leading-snug">{p.description}</p>
                  </div>
                ))}
              </div>
            ) : (
              <div className="px-5 py-8 text-center">
                <CheckCircle2 className="h-6 w-6 text-tm-profit mx-auto mb-1.5" />
                <p className="text-[13px] text-muted-foreground">No concerning patterns</p>
              </div>
            )}
          </div>

          {/* Strengths */}
          <div className="tm-card overflow-hidden">
            <div className="flex items-center gap-2 px-5 py-3 border-b border-slate-100 dark:border-neutral-700/60">
              <CheckCircle2 className="h-3.5 w-3.5 text-tm-profit" />
              <span className="tm-label">Your Strengths</span>
              <span className="text-[11px] text-muted-foreground ml-1">({strengths.length})</span>
            </div>
            {strengths.length > 0 ? (
              <div className="divide-y divide-slate-50 dark:divide-slate-700/30">
                {strengths.map((p, i) => (
                  <div key={i} className="px-5 py-3">
                    <div className="flex items-center justify-between mb-0.5">
                      <span className="text-sm font-semibold text-foreground">{p.name}</span>
                      <span className="text-[12px] font-mono tabular-nums text-tm-profit">{p.frequency}×</span>
                    </div>
                    <p className="text-[12px] text-muted-foreground leading-snug">{p.description}</p>
                  </div>
                ))}
              </div>
            ) : (
              <div className="px-5 py-8 text-center">
                <p className="text-[13px] text-muted-foreground">Keep trading to build strengths</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Focus / Strength callouts ─────────────────────────────────── */}
      {(behavioral.top_strength || behavioral.focus_area) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {behavioral.top_strength && (
            <div className="tm-card flex items-start gap-3 px-4 py-3.5 border-l-2 border-l-tm-profit">
              <ArrowUpRight className="h-4 w-4 text-tm-profit shrink-0 mt-0.5" />
              <div>
                <span className="tm-label block mb-0.5">Top Strength</span>
                <p className="text-sm font-medium text-foreground">{behavioral.top_strength}</p>
              </div>
            </div>
          )}
          {behavioral.focus_area && (
            <div className="tm-card flex items-start gap-3 px-4 py-3.5 border-l-2 border-l-tm-obs">
              <ArrowDownRight className="h-4 w-4 text-tm-obs shrink-0 mt-0.5" />
              <div>
                <span className="tm-label block mb-0.5">Focus Area</span>
                <p className="text-sm font-medium text-foreground">{behavioral.focus_area}</p>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Personalized Insights ─────────────────────────────────────── */}
      {aiInsights?.has_data && aiInsights.personalization && (
        <div className="tm-card overflow-hidden">
          <div className="flex items-center gap-2 px-5 py-3 border-b border-slate-100 dark:border-neutral-700/60">
            <Lightbulb className="h-3.5 w-3.5 text-tm-brand" />
            <span className="tm-label">Personalized Insights</span>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 divide-x divide-y md:divide-y-0 divide-slate-100 dark:divide-slate-700/60">
            {/* Danger Hours */}
            {aiInsights.personalization.danger_hours?.length > 0 && (
              <div className="px-4 py-3.5">
                <div className="flex items-center gap-1.5 mb-2">
                  <Clock className="h-3 w-3 text-tm-loss" />
                  <span className="tm-label">Avoid</span>
                </div>
                <div className="flex flex-wrap gap-1">
                  {aiInsights.personalization.danger_hours.map((h: number) => (
                    <span key={h} className="px-2 py-0.5 bg-red-50 dark:bg-red-900/20 text-tm-loss text-[11px] font-mono rounded">
                      {h}:00
                    </span>
                  ))}
                </div>
                <p className="text-[11px] text-muted-foreground mt-1.5">Danger hours IST</p>
              </div>
            )}
            {/* Best Hours */}
            {aiInsights.personalization.best_hours?.length > 0 && (
              <div className="px-4 py-3.5">
                <div className="flex items-center gap-1.5 mb-2">
                  <Clock className="h-3 w-3 text-tm-profit" />
                  <span className="tm-label">Best Window</span>
                </div>
                <div className="flex flex-wrap gap-1">
                  {aiInsights.personalization.best_hours.map((h: number) => (
                    <span key={h} className="px-2 py-0.5 bg-teal-50 dark:bg-teal-900/20 text-tm-profit text-[11px] font-mono rounded">
                      {h}:00
                    </span>
                  ))}
                </div>
                <p className="text-[11px] text-muted-foreground mt-1.5">Profitable hours IST</p>
              </div>
            )}
            {/* Problem Symbols */}
            {aiInsights.personalization.problem_symbols?.length > 0 && (
              <div className="px-4 py-3.5">
                <div className="flex items-center gap-1.5 mb-2">
                  <AlertCircle className="h-3 w-3 text-tm-obs" />
                  <span className="tm-label">Problem</span>
                </div>
                <div className="flex flex-wrap gap-1">
                  {aiInsights.personalization.problem_symbols.map((s: string) => (
                    <span key={s} className="tm-chip tm-chip-pe">{s}</span>
                  ))}
                </div>
                <p className="text-[11px] text-muted-foreground mt-1.5">Consistent losses</p>
              </div>
            )}
            {/* Strong Symbols */}
            {aiInsights.personalization.strong_symbols?.length > 0 && (
              <div className="px-4 py-3.5">
                <div className="flex items-center gap-1.5 mb-2">
                  <Shield className="h-3 w-3 text-tm-profit" />
                  <span className="tm-label">Edge</span>
                </div>
                <div className="flex flex-wrap gap-1">
                  {aiInsights.personalization.strong_symbols.map((s: string) => (
                    <span key={s} className="tm-chip tm-chip-ce">{s}</span>
                  ))}
                </div>
                <p className="text-[11px] text-muted-foreground mt-1.5">Where you have edge</p>
              </div>
            )}
          </div>

          {/* Trading Intensity */}
          {aiInsights.trading_intensity && (
            <div className="border-t border-slate-100 dark:border-neutral-700/60 grid grid-cols-2 md:grid-cols-4 divide-x divide-slate-100 dark:divide-slate-700/60">
              {[
                { label: 'Avg trades/day', value: String(aiInsights.trading_intensity.avg_daily_trades), cls: 'text-foreground' },
                { label: 'Max in one day',  value: String(aiInsights.trading_intensity.max_daily_trades), cls: 'text-foreground' },
                { label: 'Active days',     value: String(aiInsights.trading_intensity.active_days), cls: 'text-foreground' },
                { label: 'Overtrade days',  value: String(aiInsights.trading_intensity.overtrade_days),
                  cls: aiInsights.trading_intensity.overtrade_days > 3 ? 'text-tm-loss' : 'text-foreground' },
              ].map(({ label, value, cls }) => (
                <div key={label} className="px-4 py-3">
                  <p className={cn('text-xl font-semibold font-mono tabular-nums', cls)}>{value}</p>
                  <p className="text-[11px] text-muted-foreground mt-0.5">{label}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Journal Correlation (accordion) ──────────────────────────── */}
      {journal?.has_data && journal.by_emotion.length > 0 && (
        <Accordion title="Journal × Emotion Correlation" subtitle={`${journal.total_journaled} journaled trades`}>
          <div className="px-5 py-4">
            <div className="h-[180px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={journal.by_emotion} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" strokeOpacity={0.4} horizontal={false} />
                  <XAxis type="number" axisLine={false} tickLine={false}
                    tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }}
                    tickFormatter={v => `₹${(v / 1000).toFixed(0)}k`} />
                  <YAxis dataKey="emotion" type="category" axisLine={false} tickLine={false}
                    tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }} width={72} />
                  <Tooltip content={({ active, payload }) => {
                    if (!active || !payload?.length) return null;
                    const d = payload[0].payload as EmotionCorrelation;
                    return (
                      <div className="tm-card px-3 py-2 shadow-lg text-sm">
                        <p className="font-medium text-foreground capitalize mb-1">{d.emotion}</p>
                        <p className={cn('font-mono tabular-nums', d.avg_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
                          Avg: {formatCurrencyWithSign(d.avg_pnl)}
                        </p>
                        <p className="text-[11px] text-muted-foreground">{d.trade_count} trades · {d.win_rate}% WR</p>
                      </div>
                    );
                  }} />
                  <ReferenceLine x={0} stroke="hsl(var(--border))" strokeWidth={1.5} />
                  <Bar dataKey="avg_pnl" radius={[0, 3, 3, 0]}>
                    {journal.by_emotion.map((e, i) => (
                      <Cell key={i} fill={e.avg_pnl >= 0 ? PROFIT_COLOR : LOSS_COLOR} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
          <table className="w-full border-t border-slate-100 dark:border-neutral-700/60">
            <thead>
              <tr className="border-b border-slate-100 dark:border-neutral-700/60">
                {['Emotion', 'Trades', 'Avg P&L', 'Total P&L', 'Win Rate'].map((h, i) => (
                  <th key={i} className={cn('py-2.5 table-header', i === 0 ? 'px-5 text-left' : 'px-4 text-right')}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {journal.by_emotion.map((e, i) => (
                <tr key={i} className="border-b border-slate-50 dark:border-neutral-700/30 hover:bg-slate-50 dark:hover:bg-slate-700/20 transition-colors">
                  <td className="px-5 py-2.5 text-sm font-medium text-foreground capitalize">{e.emotion}</td>
                  <td className="px-4 py-2.5 text-right text-sm font-mono tabular-nums text-muted-foreground">{e.trade_count}</td>
                  <td className={cn('px-4 py-2.5 text-right text-sm font-mono tabular-nums font-semibold', e.avg_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
                    {formatCurrencyWithSign(e.avg_pnl)}
                  </td>
                  <td className={cn('px-4 py-2.5 text-right text-sm font-mono tabular-nums font-semibold', e.total_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
                    {formatCurrencyWithSign(e.total_pnl)}
                  </td>
                  <td className={cn('px-4 py-2.5 text-right text-sm font-mono tabular-nums', e.win_rate >= 50 ? 'text-tm-profit' : 'text-tm-loss')}>
                    {e.win_rate}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Accordion>
      )}

      {/* ── Advanced (BTST + Options) — collapsed by default ─────────── */}
      <Accordion title="Advanced Patterns" subtitle="BTST · Options behavior">
        <div className="p-4 space-y-4">
          <BTSTCard days={days} />
          <OptionsPatternCard days={days} />
        </div>
      </Accordion>

    </div>
  );
}

// ─── ConditionalPerformanceCard ───────────────────────────────────────────────

interface ConditionEntry {
  key: string; label: string; trade_count: number;
  win_rate: number; delta_vs_baseline: number; narrative: string;
}

function ConditionalPerformanceCard({ days }: { days: number }) {
  const [data, setData] = useState<{ has_data: boolean; baseline_win_rate: number; total_trades: number; conditions: ConditionEntry[] } | null>(null);

  useEffect(() => {
    let c = false;
    api.get('/api/analytics/conditional-performance', { params: { days } })
      .then(r => { if (!c) setData(r.data); })
      .catch(() => {});
    return () => { c = true; };
  }, [days]);

  if (!data?.has_data || !data.conditions?.length) return null;

  return (
    <div className="tm-card overflow-hidden">
      <div className="flex items-center gap-2 px-5 py-3 border-b border-slate-100 dark:border-neutral-700/60">
        <BarChart3 className="h-3.5 w-3.5 text-tm-brand" />
        <span className="tm-label">Conditional Performance</span>
        <span className="text-[11px] text-muted-foreground ml-1">
          Baseline {data.baseline_win_rate}% WR · {data.total_trades} trades
        </span>
      </div>
      <div className="divide-y divide-slate-50 dark:divide-slate-700/30">
        {data.conditions.map(cond => (
          <div key={cond.key} className="px-5 py-3.5">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-foreground">{cond.label}</span>
              <div className="flex items-center gap-3">
                <span className={cn('text-sm font-mono font-semibold tabular-nums',
                  cond.delta_vs_baseline < 0 ? 'text-tm-loss' : 'text-tm-profit')}>
                  {cond.delta_vs_baseline > 0 ? '+' : ''}{cond.delta_vs_baseline}pp
                </span>
                <span className="text-[11px] text-muted-foreground font-mono">{cond.win_rate}% WR · {cond.trade_count} trades</span>
              </div>
            </div>
            <div className="relative h-1.5 bg-slate-100 dark:bg-neutral-700/50 rounded-full overflow-hidden">
              <div className="absolute top-0 bottom-0 w-px bg-slate-300 dark:bg-neutral-600" style={{ left: '50%' }} />
              <div
                className={cn('absolute top-0 bottom-0 rounded-full',
                  cond.delta_vs_baseline < 0 ? 'bg-tm-loss' : 'bg-tm-profit')}
                style={{
                  left: cond.delta_vs_baseline < 0 ? `${50 + (cond.delta_vs_baseline / 20) * 50}%` : '50%',
                  width: `${Math.min(Math.abs(cond.delta_vs_baseline) / 20, 1) * 50}%`,
                }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── BTSTCard ─────────────────────────────────────────────────────────────────

interface BTSTTrade {
  id: string; tradingsymbol: string; instrument_type: string | null;
  entry_time: string; exit_time: string; direction: string;
  realized_pnl: number; avg_entry_price: number | null;
  overnight_close_price: number | null; was_profitable_at_eod: boolean | null;
  is_reversal: boolean; duration_minutes: number | null;
  hold_type: 'overnight' | 'weekend_hold';
}

interface BTSTData {
  has_data: boolean; period_days: number; total_btst_trades: number;
  btst_win_rate: number; btst_total_pnl: number; overnight_reversals: number;
  reversal_pnl_lost: number; trades: BTSTTrade[];
}

function BTSTCard({ days }: { days: number }) {
  const [data, setData] = useState<BTSTData | null>(null);
  const [showTrades, setShowTrades] = useState(false);

  useEffect(() => {
    let c = false;
    api.get('/api/analytics/btst', { params: { days } })
      .then(r => { if (!c) setData(r.data); })
      .catch(() => {});
    return () => { c = true; };
  }, [days]);

  if (!data?.has_data) return null;

  const { total_btst_trades, btst_win_rate, btst_total_pnl, overnight_reversals, reversal_pnl_lost, trades } = data;
  const visible = showTrades ? trades : trades.slice(0, 5);

  const fmtHold = (min: number | null) => {
    if (min == null) return '—';
    if (min >= 1440) return `${Math.floor(min / 1440)}d ${Math.floor((min % 1440) / 60)}h`;
    if (min >= 60) return `${Math.floor(min / 60)}h ${min % 60}m`;
    return `${min}m`;
  };

  return (
    <div className="tm-card overflow-hidden">
      <div className="flex items-center gap-2 px-5 py-3 border-b border-slate-100 dark:border-neutral-700/60">
        <Moon className="h-3.5 w-3.5 text-indigo-500" />
        <span className="tm-label">BTST — Buy Today Sell Tomorrow</span>
        <span className="text-[11px] text-muted-foreground ml-auto">Last {days} days</span>
      </div>

      <div className="grid grid-cols-4 divide-x divide-slate-100 dark:divide-slate-700/60">
        {[
          { label: 'Trades',     value: String(total_btst_trades), cls: 'text-foreground' },
          { label: 'Win Rate',   value: `${btst_win_rate}%`,       cls: btst_win_rate >= 50 ? 'text-tm-profit' : 'text-tm-loss' },
          { label: 'Total P&L',  value: formatCurrencyWithSign(btst_total_pnl), cls: btst_total_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss' },
          { label: 'Reversals',  value: String(overnight_reversals), cls: overnight_reversals > 0 ? 'text-tm-obs' : 'text-foreground' },
        ].map(({ label, value, cls }) => (
          <div key={label} className="px-4 py-3">
            <span className="tm-label">{label}</span>
            <p className={cn('text-xl font-semibold font-mono tabular-nums mt-1', cls)}>{value}</p>
            {label === 'Reversals' && overnight_reversals > 0 && reversal_pnl_lost > 0 && (
              <p className="text-[11px] text-tm-loss font-mono">{formatCurrencyWithSign(-reversal_pnl_lost)}</p>
            )}
          </div>
        ))}
      </div>

      <div className="px-5 py-2.5 bg-indigo-50/50 dark:bg-indigo-950/20 border-t border-slate-100 dark:border-neutral-700/60">
        <p className="text-[11px] text-muted-foreground leading-relaxed">
          BTST entries (after 15:00 IST in NRML) are a behavioural signal — late-day entries held overnight. Friday entries carry 2 extra theta days. Overnight reversals are the most psychologically damaging: profitable at close, loss at open.
        </p>
      </div>

      {trades.length > 0 && (
        <>
          <table className="w-full border-t border-slate-100 dark:border-neutral-700/60">
            <thead>
              <tr className="border-b border-slate-100 dark:border-neutral-700/60">
                {['Symbol', 'Entry', 'Hold', 'P&L', 'Reversal?'].map((h, i) => (
                  <th key={i} className={cn('py-2.5 table-header', i === 0 ? 'px-5 text-left' : 'px-4 text-right')}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {visible.map(t => (
                <tr key={t.id} className={cn(
                  'border-b border-slate-50 dark:border-neutral-700/30 hover:bg-slate-50 dark:hover:bg-slate-700/20 transition-colors',
                  t.is_reversal && 'bg-orange-50/30 dark:bg-orange-950/10',
                )}>
                  <td className="px-5 py-2.5">
                    <div className="flex items-center gap-1.5">
                      {t.hold_type === 'weekend_hold' && (
                        <span className="text-[10px] bg-indigo-100 dark:bg-indigo-900/40 text-indigo-600 dark:text-indigo-400 px-1 rounded">WE</span>
                      )}
                      <span className="text-sm font-medium text-foreground font-mono">{t.tradingsymbol}</span>
                    </div>
                  </td>
                  <td className="px-4 py-2.5 text-right text-[12px] text-muted-foreground font-mono">
                    {t.entry_time ? new Date(t.entry_time).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' }) : '—'}
                  </td>
                  <td className="px-4 py-2.5 text-right text-[12px] text-muted-foreground font-mono tabular-nums">{fmtHold(t.duration_minutes)}</td>
                  <td className={cn('px-4 py-2.5 text-right text-sm font-mono tabular-nums font-semibold',
                    t.realized_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
                    {formatCurrencyWithSign(t.realized_pnl)}
                  </td>
                  <td className="px-4 py-2.5 text-right text-[11px]">
                    {t.is_reversal
                      ? <span className="text-tm-obs font-semibold">↓ Reversed</span>
                      : t.was_profitable_at_eod === true ? <span className="text-tm-profit">Held well</span>
                      : t.was_profitable_at_eod === false ? <span className="text-tm-loss">EOD loss</span>
                      : <span className="text-muted-foreground">—</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {trades.length > 5 && (
            <div className="px-5 py-2.5 border-t border-slate-100 dark:border-neutral-700/60">
              <button onClick={() => setShowTrades(v => !v)}
                className="text-[12px] font-medium text-tm-brand hover:underline">
                {showTrades ? 'Show less' : `Show all ${trades.length} BTST trades`}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ─── OptionsPatternCard ────────────────────────────────────────────────────────

interface OptionsPatternData {
  period_days: number; has_data: boolean;
  direction_confusion: { count: number; underlying_breakdown: Record<string, number>; avg_flip_minutes: number | null };
  premium_avg_down: { count: number; total_re_entry_premium: number; avg_worst_loss_pct: number | null };
  iv_crush: { count: number; total_loss: number; avg_hold_minutes: number | null; avg_loss_pct: number | null };
}

function OptionsPatternCard({ days }: { days: number }) {
  const [data, setData] = useState<OptionsPatternData | null>(null);

  useEffect(() => {
    let c = false;
    api.get('/api/analytics/options-behavior', { params: { days } })
      .then(r => { if (!c) setData(r.data); })
      .catch(() => {});
    return () => { c = true; };
  }, [days]);

  if (!data?.has_data) return null;

  const { direction_confusion: dc, premium_avg_down: pad, iv_crush: iv } = data;

  const rows: { icon: React.ReactNode; label: string; count: number; sub: string; detail: string; cls: string }[] = [];

  if (dc.count > 0) {
    const top = Object.entries(dc.underlying_breakdown || {}).sort((a, b) => b[1] - a[1]).slice(0, 3);
    rows.push({
      icon: <Activity className="h-3.5 w-3.5" />,
      label: 'Direction Confusion', count: dc.count,
      sub: dc.avg_flip_minutes != null ? `avg ${dc.avg_flip_minutes}min between flip` : '',
      detail: top.length ? `On: ${top.map(([u, c]) => `${u} ×${c}`).join(', ')}` : 'CE→PE flip on same underlying',
      cls: 'text-tm-obs',
    });
  }
  if (pad.count > 0) {
    rows.push({
      icon: <RefreshCw className="h-3.5 w-3.5" />,
      label: 'Premium Averaging Down', count: pad.count,
      sub: pad.total_re_entry_premium > 0 ? `₹${pad.total_re_entry_premium.toLocaleString('en-IN')} re-entry premium` : '',
      detail: pad.avg_worst_loss_pct != null ? `Prior position avg ${pad.avg_worst_loss_pct}% loss before re-entry` : 'Re-entered after a loss on same underlying',
      cls: 'text-tm-obs',
    });
  }
  if (iv.count > 0) {
    rows.push({
      icon: <Zap className="h-3.5 w-3.5" />,
      label: 'IV Crush', count: iv.count,
      sub: iv.total_loss > 0 ? `₹${iv.total_loss.toLocaleString('en-IN')} total lost` : '',
      detail: [iv.avg_hold_minutes != null && `avg hold ${iv.avg_hold_minutes}min`, iv.avg_loss_pct != null && `avg ${iv.avg_loss_pct}% premium lost`].filter(Boolean).join(' · ') || '',
      cls: 'text-tm-loss',
    });
  }

  if (!rows.length) return null;

  return (
    <div className="tm-card overflow-hidden">
      <div className="flex items-center gap-2 px-5 py-3 border-b border-slate-100 dark:border-neutral-700/60">
        <Zap className="h-3.5 w-3.5 text-tm-obs" />
        <span className="tm-label">Options Behavioral Patterns</span>
        <span className="text-[11px] text-muted-foreground ml-auto">Last {days} days</span>
      </div>
      <div className="divide-y divide-slate-50 dark:divide-slate-700/30">
        {rows.map(row => (
          <div key={row.label} className="flex items-start gap-3 px-5 py-3.5">
            <span className={cn('mt-0.5 shrink-0', row.cls)}>{row.icon}</span>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-0.5">
                <span className="text-sm font-semibold text-foreground">{row.label}</span>
                <span className={cn('text-[11px] font-mono tabular-nums', row.cls)}>{row.count}× / {days <= 7 ? 'week' : days <= 31 ? 'month' : `${days}d`}</span>
              </div>
              {row.detail && <p className="text-[12px] text-muted-foreground leading-snug">{row.detail}</p>}
              {row.sub && <p className="text-[11px] text-muted-foreground mt-0.5">{row.sub}</p>}
            </div>
          </div>
        ))}
        <p className="px-5 py-2.5 text-[11px] text-muted-foreground">These patterns are unique to options traders and invisible in standard P&L reports.</p>
      </div>
    </div>
  );
}
