import { useState, useEffect } from 'react';
import { ChevronDown, ChevronUp, AlertTriangle, CheckCircle2, TrendingDown } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { formatCurrencyWithSign, formatCurrency } from '@/lib/formatters';
import { api } from '@/lib/api';
import RecoveryCard from '@/components/analytics/RecoveryCard';

interface PatternsTabProps { days: number; }

// ─── Types ────────────────────────────────────────────────────────────────────

interface FlaggedTrade {
  id: string;
  tradingsymbol: string;
  realized_pnl: number;
  exit_time: string;
  duration_minutes: number | null;
  flag_reasons: { type: string; label: string }[];
}

interface CriticalData {
  has_data: boolean;
  trades: FlaggedTrade[];
}

interface Condition {
  key: string;
  label: string;
  win_rate: number;
  avg_pnl: number;
  trade_count: number;
  delta_vs_baseline: number;
  narrative: string;
}

interface ConditionalData {
  has_data: boolean;
  baseline_win_rate: number;
  baseline_avg_pnl: number;
  total_trades: number;
  conditions: Condition[];
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

const FLAG_LABEL: Record<string, string> = {
  large_loss:       'Large Loss',
  behavioral_alert: 'Behavioral Alert',
  oversized:        'Oversized Position',
  quick_reentry:    'Quick Re-entry',
};

const FLAG_COLOR: Record<string, string> = {
  large_loss:       'bg-red-50 text-tm-loss border-red-200 dark:bg-red-900/10 dark:border-red-800/30',
  behavioral_alert: 'bg-amber-50 text-tm-obs border-amber-200 dark:bg-amber-900/10 dark:border-amber-800/30',
  oversized:        'bg-purple-50 text-purple-600 border-purple-200 dark:bg-purple-900/10 dark:border-purple-800/30',
  quick_reentry:    'bg-amber-50 text-tm-obs border-amber-200 dark:bg-amber-900/10 dark:border-amber-800/30',
};

function fmtDate(s: string) {
  return new Date(s).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
}
function fmtTime(s: string) {
  return new Date(s).toLocaleTimeString('en-IN', {
    hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'Asia/Kolkata',
  });
}
function fmtDur(m: number | null) {
  if (!m) return '—';
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60), rem = m % 60;
  return rem ? `${h}h ${rem}m` : `${h}h`;
}

// ─── Pattern group row (expandable) ──────────────────────────────────────────

function PatternGroup({
  type, label, trades,
}: { type: string; label: string; trades: FlaggedTrade[] }) {
  const [open, setOpen] = useState(false);
  const total_pnl = trades.reduce((s, t) => s + t.realized_pnl, 0);
  const wins = trades.filter(t => t.realized_pnl > 0).length;

  return (
    <div className="border-b border-border last:border-0">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-5 py-3.5 hover:bg-slate-50 dark:hover:bg-neutral-700/20 transition-colors text-left"
      >
        <div className="flex items-center gap-3">
          <span className={cn(
            'text-[11px] font-medium px-2 py-0.5 rounded border',
            FLAG_COLOR[type] ?? 'bg-muted text-muted-foreground border-border'
          )}>
            {label}
          </span>
          <span className="text-sm text-muted-foreground">{trades.length} trade{trades.length !== 1 ? 's' : ''}</span>
        </div>
        <div className="flex items-center gap-4">
          <span className={cn('text-sm font-bold font-mono tabular-nums',
            total_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
            {formatCurrencyWithSign(total_pnl)}
          </span>
          <span className="text-xs text-muted-foreground">
            {wins}/{trades.length} winners
          </span>
          {open
            ? <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" />
            : <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
          }
        </div>
      </button>

      {open && (
        <div className="bg-slate-50/60 dark:bg-neutral-800/20 border-t border-border">
          <table className="w-full">
            <thead>
              <tr className="border-b border-border/60">
                <th className="px-5 py-2 text-left table-header">Symbol</th>
                <th className="px-3 py-2 text-right table-header">P&L</th>
                <th className="px-3 py-2 text-right table-header">Hold</th>
                <th className="px-5 py-2 text-right table-header">Date / Time</th>
              </tr>
            </thead>
            <tbody>
              {trades.map(t => (
                <tr key={t.id} className="border-b border-border/40 last:border-0">
                  <td className="px-5 py-2.5 text-sm font-medium text-foreground">{t.tradingsymbol}</td>
                  <td className={cn('px-3 py-2.5 text-right text-sm font-mono tabular-nums',
                    t.realized_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
                    {formatCurrencyWithSign(t.realized_pnl)}
                  </td>
                  <td className="px-3 py-2.5 text-right text-sm text-muted-foreground font-mono">
                    {fmtDur(t.duration_minutes)}
                  </td>
                  <td className="px-5 py-2.5 text-right text-sm text-muted-foreground">
                    {fmtDate(t.exit_time)} {fmtTime(t.exit_time)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ─── Main ─────────────────────────────────────────────────────────────────────

export default function PatternsTab({ days }: PatternsTabProps) {
  const [critical, setCritical]   = useState<CriticalData | null>(null);
  const [cond, setCond]           = useState<ConditionalData | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    Promise.all([
      api.get('/api/analytics/critical-trades',         { params: { days } }),
      api.get('/api/analytics/conditional-performance', { params: { days } }),
    ]).then(([cr, cd]) => {
      if (cancelled) return;
      setCritical(cr.data);
      setCond(cd.data);
    }).catch(() => {}).finally(() => {
      if (!cancelled) setIsLoading(false);
    });
    return () => { cancelled = true; };
  }, [days]);

  if (isLoading) return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <Skeleton className="h-28 rounded-xl" />
        <Skeleton className="h-28 rounded-xl" />
      </div>
      <Skeleton className="h-48 rounded-xl" />
      <Skeleton className="h-32 rounded-xl" />
    </div>
  );

  const flagged = critical?.trades ?? [];
  const clean   = flagged.filter(t => t.flag_reasons.length === 0);
  const dirty   = flagged.filter(t => t.flag_reasons.length > 0);

  const cleanPnl  = clean.reduce((s, t) => s + t.realized_pnl, 0);
  const dirtyPnl  = dirty.reduce((s, t) => s + t.realized_pnl, 0);
  const cleanWR   = clean.length ? Math.round(clean.filter(t => t.realized_pnl > 0).length / clean.length * 100) : 0;
  const dirtyWR   = dirty.length ? Math.round(dirty.filter(t => t.realized_pnl > 0).length / dirty.length * 100) : 0;
  const cleanAvg  = clean.length ? Math.round(cleanPnl / clean.length) : 0;
  const dirtyAvg  = dirty.length ? Math.round(dirtyPnl / dirty.length) : 0;

  // Group flagged trades by primary reason type
  const byReason: Record<string, FlaggedTrade[]> = {};
  for (const t of dirty) {
    for (const r of t.flag_reasons) {
      if (!byReason[r.type]) byReason[r.type] = [];
      byReason[r.type].push(t);
    }
  }

  const conditions = cond?.conditions ?? [];

  const hasAnyData = flagged.length > 0 || conditions.length > 0;

  if (!hasAnyData) {
    return (
      <div className="tm-card flex flex-col items-center justify-center py-16">
        <CheckCircle2 className="h-8 w-8 text-tm-profit mb-3" />
        <p className="font-medium text-foreground">No patterns detected in this period</p>
        <p className="text-sm text-muted-foreground mt-1">Keep trading to see behavioral analysis</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">

      {/* Recovery Pattern (11.15) */}
      <RecoveryCard days={days} />

      {/* Clean vs Flagged comparison */}
      {(clean.length > 0 || dirty.length > 0) && (
        <div className="grid grid-cols-2 gap-3">
          {/* Clean trades */}
          <div className="tm-card overflow-hidden">
            <div className="px-5 py-3 border-b border-border flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-tm-profit shrink-0" />
              <p className="tm-label">Clean Trades</p>
            </div>
            <div className="px-5 py-4">
              <p className={cn('text-2xl font-bold font-mono tabular-nums',
                cleanPnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
                {formatCurrencyWithSign(cleanPnl)}
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                {clean.length} trades · {cleanWR}% WR
              </p>
              <p className={cn('text-xs font-mono tabular-nums mt-0.5',
                cleanAvg >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
                {formatCurrencyWithSign(cleanAvg)}/trade avg
              </p>
            </div>
          </div>

          {/* Flagged trades */}
          <div className="tm-card overflow-hidden">
            <div className="px-5 py-3 border-b border-border flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-tm-obs shrink-0" />
              <p className="tm-label">Flagged Trades</p>
            </div>
            <div className="px-5 py-4">
              <p className={cn('text-2xl font-bold font-mono tabular-nums',
                dirtyPnl >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
                {dirty.length > 0 ? formatCurrencyWithSign(dirtyPnl) : '—'}
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                {dirty.length > 0 ? `${dirty.length} trades · ${dirtyWR}% WR` : 'No flagged trades'}
              </p>
              {dirty.length > 0 && (
                <p className={cn('text-xs font-mono tabular-nums mt-0.5',
                  dirtyAvg >= 0 ? 'text-tm-profit' : 'text-tm-loss')}>
                  {formatCurrencyWithSign(dirtyAvg)}/trade avg
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Flagged trades grouped by reason — expandable */}
      {Object.keys(byReason).length > 0 && (
        <div className="tm-card overflow-hidden">
          <div className="px-5 py-3 border-b border-border">
            <p className="tm-label">Flagged Trade Breakdown</p>
            <p className="text-xs text-muted-foreground">Click any row to see the trades</p>
          </div>
          <div>
            {Object.entries(byReason).map(([type, trades]) => (
              <PatternGroup
                key={type}
                type={type}
                label={FLAG_LABEL[type] ?? type}
                trades={trades}
              />
            ))}
          </div>
        </div>
      )}

      {/* Conditional performance */}
      {conditions.length > 0 && (
        <div className="tm-card overflow-hidden">
          <div className="px-5 py-3 border-b border-border">
            <p className="tm-label">Performance Under Conditions</p>
            <p className="text-xs text-muted-foreground">
              Baseline: {cond?.baseline_win_rate}% WR · {formatCurrencyWithSign(cond?.baseline_avg_pnl ?? 0)}/trade avg
            </p>
          </div>
          <div className="divide-y divide-border">
            {conditions.map(c => {
              const delta = c.delta_vs_baseline;
              const worse = delta < -3;
              const better = delta > 3;
              return (
                <div key={c.key} className="px-5 py-4">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-foreground">{c.label}</p>
                      <p className="text-xs text-muted-foreground mt-0.5 leading-relaxed">{c.narrative}</p>
                    </div>
                    <div className="shrink-0 text-right">
                      <p className={cn('text-sm font-bold font-mono tabular-nums',
                        c.win_rate >= 50 ? 'text-tm-profit' : 'text-tm-loss')}>
                        {c.win_rate}% WR
                      </p>
                      <p className={cn('text-xs mt-0.5 font-mono tabular-nums',
                        better ? 'text-tm-profit' : worse ? 'text-tm-loss' : 'text-muted-foreground')}>
                        {delta > 0 ? '+' : ''}{delta}% vs baseline
                      </p>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

    </div>
  );
}
