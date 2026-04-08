import { useState, useEffect, useCallback } from 'react';
import {
  Radar, AlertTriangle, CheckCircle2, TrendingDown,
  TrendingUp, Minus, RefreshCw, Info,
} from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { useBroker } from '@/contexts/BrokerContext';
import { api } from '@/lib/api';

// ── Types ─────────────────────────────────────────────────────────────────

interface PositionMetric {
  position_id: string;
  tradingsymbol: string;
  exchange: string;
  instrument_type: string;
  quantity: number;
  lot_size: number;
  entry_price: number;
  current_ltp: number | null;
  underlying_name: string | null;
  underlying_ltp: number | null;
  strike: number | null;
  expiry: string | null;
  days_to_expiry: number | null;
  breakeven: number | null;
  breakeven_gap: number | null;
  premium_decay_pct: number | null;
  capital_at_risk: number | null;
  unrealized_pnl: number;
}

interface ConcentrationData {
  total_capital_at_risk: number;
  expiry_weeks: Record<string, { pct: number; capital: number }>;
  underlyings: Record<string, { pct: number; capital: number }>;
  long_pct: number;
  short_pct: number;
  margin_utilization: number | null;
  triggered: Array<{ type: string; key: string; value: number }>;
}

interface GttSummary {
  honored: number;
  overridden: number;
  active: number;
  active_gtts: Array<{
    gtt_id: number;
    tradingsymbol: string;
    exchange: string;
    trigger_price: number | null;
    quantity: number;
    created_at: string;
  }>;
}

// ── Helpers ───────────────────────────────────────────────────────────────

function fmt(n: number | null | undefined, decimals = 0): string {
  if (n == null) return '—';
  return n.toLocaleString('en-IN', { maximumFractionDigits: decimals });
}

function fmtCurrency(n: number | null | undefined): string {
  if (n == null) return '—';
  return `₹${Math.abs(n).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;
}

function dteColor(dte: number | null): string {
  if (dte == null) return 'text-muted-foreground';
  if (dte <= 1) return 'text-tm-loss';
  if (dte <= 3) return 'text-tm-obs';
  return 'text-foreground';
}

function decayColor(pct: number | null): string {
  if (pct == null) return 'text-muted-foreground';
  if (pct >= 50) return 'text-tm-loss';
  if (pct >= 25) return 'text-tm-obs';
  return 'text-tm-profit';
}

function concentrationColor(pct: number, threshold: number): string {
  if (pct >= threshold) return 'text-tm-loss';
  if (pct >= threshold * 0.8) return 'text-tm-obs';
  return 'text-foreground';
}

// ── Sub-components ────────────────────────────────────────────────────────

function SectionCard({ title, children, className }: {
  title: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn('tm-card overflow-hidden', className)}>
      <div className="px-5 py-4 border-b border-border">
        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">{title}</p>
      </div>
      <div className="p-5">{children}</div>
    </div>
  );
}

function AlertBadge({ type }: { type: string }) {
  const labels: Record<string, string> = {
    expiry_concentration: 'Expiry',
    underlying_concentration: 'Concentration',
    directional_skew: 'Directional',
    margin_utilization: 'Margin',
  };
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 dark:bg-amber-900/30 px-2 py-0.5 text-xs font-medium text-amber-700 dark:text-amber-400">
      <AlertTriangle className="h-3 w-3" />
      {labels[type] ?? type}
    </span>
  );
}

// ── Position Clock Card ───────────────────────────────────────────────────

function PositionCard({ m }: { m: PositionMetric }) {
  const isOption = m.instrument_type === 'CE' || m.instrument_type === 'PE';
  const isLong = m.quantity > 0;
  const pnlColor = m.unrealized_pnl >= 0 ? 'text-tm-profit' : 'text-tm-loss';

  return (
    <div className="rounded-lg border border-border bg-card p-4 space-y-3 animate-fade-in-up">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <p className="font-semibold text-sm">{m.tradingsymbol}</p>
          <p className="text-xs text-muted-foreground">
            {m.instrument_type} · {isLong ? 'Long' : 'Short'} {Math.abs(m.quantity)} lots
          </p>
        </div>
        <div className="text-right">
          <p className={cn('text-sm font-medium', pnlColor)}>
            {m.unrealized_pnl >= 0 ? '+' : '-'}{fmtCurrency(m.unrealized_pnl)}
          </p>
          <p className="text-xs text-muted-foreground">Unrealised P&L</p>
        </div>
      </div>

      {/* Metrics grid */}
      <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
        <div>
          <p className="text-muted-foreground">Entry</p>
          <p className="font-medium">₹{fmt(m.entry_price, 2)}</p>
        </div>
        <div>
          <p className="text-muted-foreground">LTP</p>
          <p className="font-medium">{m.current_ltp != null ? `₹${fmt(m.current_ltp, 2)}` : '—'}</p>
        </div>

        {isOption && (
          <>
            <div>
              <p className="text-muted-foreground">Strike</p>
              <p className="font-medium">₹{fmt(m.strike, 0)}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Breakeven</p>
              <p className="font-medium">{m.breakeven != null ? `₹${fmt(m.breakeven, 0)}` : '—'}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Gap to BE</p>
              <p className={cn('font-medium', m.breakeven_gap != null && m.breakeven_gap < 0 ? 'text-tm-loss' : 'text-tm-profit')}>
                {m.breakeven_gap != null ? `${m.breakeven_gap >= 0 ? '+' : ''}${fmt(m.breakeven_gap, 0)}` : '—'}
              </p>
            </div>
            <div>
              <p className="text-muted-foreground">Premium decay</p>
              <p className={cn('font-medium', decayColor(m.premium_decay_pct))}>
                {m.premium_decay_pct != null ? `${fmt(m.premium_decay_pct, 1)}%` : '—'}
              </p>
            </div>
          </>
        )}

        <div>
          <p className="text-muted-foreground">Capital at risk</p>
          <p className="font-medium">{fmtCurrency(m.capital_at_risk)}</p>
        </div>
        <div>
          <p className="text-muted-foreground">Expiry</p>
          <p className={cn('font-medium', dteColor(m.days_to_expiry))}>
            {m.days_to_expiry != null ? `${m.days_to_expiry}d` : '—'}
            {m.expiry ? ` (${m.expiry})` : ''}
          </p>
        </div>
      </div>
    </div>
  );
}

// ── Concentration Panel ───────────────────────────────────────────────────

function ConcentrationPanel({ data }: { data: ConcentrationData }) {
  const hasAlerts = data.triggered.length > 0;

  return (
    <div className="space-y-4">
      {hasAlerts && (
        <div className="rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 p-3 space-y-1">
          <p className="text-xs font-semibold text-amber-700 dark:text-amber-400 mb-2 flex items-center gap-1">
            <AlertTriangle className="h-3.5 w-3.5" /> Active Alerts
          </p>
          {data.triggered.map((t, i) => (
            <div key={i} className="flex items-center justify-between">
              <AlertBadge type={t.type} />
              <span className="text-xs font-medium text-amber-700 dark:text-amber-400">{t.value.toFixed(0)}%</span>
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 text-xs">
        <div>
          <p className="text-muted-foreground mb-1">Total capital at risk</p>
          <p className="text-lg font-semibold">{fmtCurrency(data.total_capital_at_risk)}</p>
        </div>
        <div>
          <p className="text-muted-foreground mb-1">Direction</p>
          <div className="flex items-center gap-2">
            <TrendingUp className="h-3.5 w-3.5 text-tm-profit" />
            <span className={cn('font-medium', concentrationColor(data.long_pct, 100))}>
              {data.long_pct.toFixed(0)}%
            </span>
            <span className="text-muted-foreground">/</span>
            <TrendingDown className="h-3.5 w-3.5 text-tm-loss" />
            <span>{data.short_pct.toFixed(0)}%</span>
          </div>
        </div>
        {data.margin_utilization != null && (
          <div>
            <p className="text-muted-foreground mb-1">Margin used</p>
            <p className={cn('font-semibold', concentrationColor(data.margin_utilization, 80))}>
              {data.margin_utilization.toFixed(0)}%
            </p>
          </div>
        )}
      </div>

      {/* Expiry breakdown */}
      {Object.keys(data.expiry_weeks).length > 0 && (
        <div>
          <p className="text-xs text-muted-foreground mb-2">Expiry week distribution</p>
          <div className="space-y-1.5">
            {Object.entries(data.expiry_weeks)
              .sort((a, b) => b[1].pct - a[1].pct)
              .map(([week, info]) => (
                <div key={week} className="flex items-center gap-2">
                  <div className="w-20 shrink-0 text-xs text-muted-foreground">{week}</div>
                  <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
                    <div
                      className={cn(
                        'h-full rounded-full',
                        info.pct >= 60 ? 'bg-tm-loss' : info.pct >= 40 ? 'bg-tm-obs' : 'bg-tm-brand'
                      )}
                      style={{ width: `${info.pct}%` }}
                    />
                  </div>
                  <span className={cn('text-xs font-medium w-10 text-right', concentrationColor(info.pct, 60))}>
                    {info.pct.toFixed(0)}%
                  </span>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Underlying breakdown */}
      {Object.keys(data.underlyings).length > 0 && (
        <div>
          <p className="text-xs text-muted-foreground mb-2">Underlying concentration</p>
          <div className="space-y-1.5">
            {Object.entries(data.underlyings)
              .sort((a, b) => b[1].pct - a[1].pct)
              .map(([sym, info]) => (
                <div key={sym} className="flex items-center gap-2">
                  <div className="w-20 shrink-0 text-xs text-muted-foreground">{sym}</div>
                  <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
                    <div
                      className={cn(
                        'h-full rounded-full',
                        info.pct >= 70 ? 'bg-tm-loss' : info.pct >= 50 ? 'bg-tm-obs' : 'bg-tm-brand'
                      )}
                      style={{ width: `${info.pct}%` }}
                    />
                  </div>
                  <span className={cn('text-xs font-medium w-10 text-right', concentrationColor(info.pct, 70))}>
                    {info.pct.toFixed(0)}%
                  </span>
                </div>
              ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── GTT Panel ─────────────────────────────────────────────────────────────

function GttPanel({ data }: { data: GttSummary }) {
  const total = data.honored + data.overridden;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 sm:gap-3 text-center">
        <div className="rounded-lg bg-muted/50 p-3">
          <p className="text-2xl font-bold font-mono tabular-nums text-tm-profit">{data.honored}</p>
          <p className="text-xs text-muted-foreground mt-0.5">SL Honoured</p>
        </div>
        <div className="rounded-lg bg-muted/50 p-3">
          <p className="text-2xl font-bold font-mono tabular-nums text-tm-loss">{data.overridden}</p>
          <p className="text-xs text-muted-foreground mt-0.5">Overridden</p>
        </div>
        <div className="rounded-lg bg-muted/50 p-3">
          <p className="text-2xl font-bold">{data.active}</p>
          <p className="text-xs text-muted-foreground mt-0.5">Active GTTs</p>
        </div>
      </div>

      {total > 0 && (
        <div>
          <div className="flex justify-between text-xs mb-1">
            <span className="text-muted-foreground">SL discipline</span>
            <span className="font-medium">{Math.round(data.honored / total * 100)}%</span>
          </div>
          <div className="h-2 bg-muted rounded-full overflow-hidden">
            <div
              className="h-full rounded-full bg-tm-profit transition-all"
              style={{ width: `${(data.honored / total) * 100}%` }}
            />
          </div>
        </div>
      )}

      {data.active_gtts.length > 0 && (
        <div>
          <p className="text-xs text-muted-foreground mb-2">Active stop-losses</p>
          <div className="space-y-1.5">
            {data.active_gtts.map((gtt) => (
              <div key={gtt.gtt_id} className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="h-3.5 w-3.5 text-tm-profit shrink-0" />
                  <span className="font-medium">{gtt.tradingsymbol}</span>
                </div>
                <span className="text-muted-foreground">
                  {gtt.trigger_price != null ? `₹${fmt(gtt.trigger_price, 0)}` : '—'}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {data.active_gtts.length === 0 && data.active === 0 && (
        <p className="text-xs text-muted-foreground text-center py-2">
          No active GTT stop-losses found. Consider setting GTTs on open positions.
        </p>
      )}
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────

export default function PortfolioRadar() {
  const { account } = useBroker();
  const [metrics, setMetrics] = useState<PositionMetric[]>([]);
  const [concentration, setConcentration] = useState<ConcentrationData | null>(null);
  const [gtt, setGtt] = useState<GttSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);

  const fetchAll = useCallback(async () => {
    if (!account?.id) return;
    setLoading(true);
    setError(null);
    try {
      const [metricsRes, concentrationRes, gttRes] = await Promise.all([
        api.get('/api/portfolio-radar/metrics', { params: { broker_account_id: account.id } }),
        api.get('/api/portfolio-radar/concentration', { params: { broker_account_id: account.id } }),
        api.get('/api/portfolio-radar/gtt-discipline', { params: { broker_account_id: account.id } }),
      ]);
      setMetrics(metricsRes.data.metrics ?? []);
      setConcentration(concentrationRes.data);
      setGtt(gttRes.data);
      setLastRefresh(new Date());
    } catch {
      setError('Failed to load portfolio data');
    } finally {
      setLoading(false);
    }
  }, [account?.id]);

  const syncGtts = useCallback(async () => {
    if (!account?.id || syncing) return;
    setSyncing(true);
    try {
      await api.post('/api/portfolio-radar/sync-gtts', null, { params: { broker_account_id: account.id } });
      // Re-fetch GTT data after sync
      const res = await api.get('/api/portfolio-radar/gtt-discipline', { params: { broker_account_id: account.id } });
      setGtt(res.data);
    } finally {
      setSyncing(false);
    }
  }, [account?.id, syncing]);

  useEffect(() => {
    fetchAll();
    // Also sync GTTs on mount so the list is fresh
    if (account?.id) {
      api.post('/api/portfolio-radar/sync-gtts', null, { params: { broker_account_id: account.id } }).catch(() => {});
    }
  }, [account?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!account) {
    return (
      <div className="flex items-center justify-center h-64 text-muted-foreground text-sm">
        Connect your Zerodha account to view Portfolio Radar.
      </div>
    );
  }

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto px-4 sm:px-6 py-6 space-y-5">
        <div className="flex items-center justify-between">
          <Skeleton className="h-6 w-40" />
          <Skeleton className="h-8 w-20" />
        </div>
        <div className="grid md:grid-cols-2 gap-5">
          <Skeleton className="h-64 rounded-xl" />
          <Skeleton className="h-64 rounded-xl" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64 text-tm-loss text-sm">{error}</div>
    );
  }

  const noPositions = metrics.length === 0;

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 py-6 space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <Radar className="h-5 w-5 text-tm-brand" />
          <div>
            <h1 className="text-lg font-semibold tracking-tight">Portfolio Radar</h1>
            <p className="text-xs text-muted-foreground">
              {lastRefresh ? `Updated ${lastRefresh.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}` : 'Live position intelligence'}
            </p>
          </div>
        </div>
        <button
          onClick={fetchAll}
          className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium bg-muted hover:bg-muted/80 transition-colors"
        >
          <RefreshCw className={cn('h-3.5 w-3.5', loading && 'animate-spin')} />
          Refresh
        </button>
      </div>

      {noPositions ? (
        <div className="tm-card overflow-hidden p-10 text-center">
          <Minus className="h-8 w-8 text-muted-foreground/40 mx-auto mb-3" />
          <p className="text-sm font-medium">No open F&O positions</p>
          <p className="text-xs text-muted-foreground mt-1">Portfolio Radar activates when you have open positions.</p>
        </div>
      ) : (
        <div className="grid md:grid-cols-2 gap-5">
          {/* Left column */}
          <div className="space-y-5">
            {/* Concentration */}
            {concentration && (
              <SectionCard title="Portfolio Concentration">
                <ConcentrationPanel data={concentration} />
              </SectionCard>
            )}

            {/* GTT Discipline */}
            <SectionCard title="Stop-Loss Discipline">
              {gtt ? (
                <div className="space-y-4">
                  <GttPanel data={gtt} />
                  <button
                    onClick={syncGtts}
                    disabled={syncing}
                    className="w-full text-xs text-muted-foreground hover:text-foreground flex items-center justify-center gap-1 py-1 transition-colors"
                  >
                    <RefreshCw className={cn('h-3 w-3', syncing && 'animate-spin')} />
                    {syncing ? 'Syncing GTTs…' : 'Sync GTTs from Kite'}
                  </button>
                </div>
              ) : (
                <p className="text-xs text-muted-foreground">Loading…</p>
              )}
            </SectionCard>
          </div>

          {/* Right column — Position clock cards */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
                Position Clock
              </p>
              <span className="text-xs text-muted-foreground">{metrics.length} open</span>
            </div>
            {metrics.map((m) => (
              <PositionCard key={m.position_id} m={m} />
            ))}
            <div className="flex items-start gap-2 rounded-lg bg-muted/40 p-3 text-xs text-muted-foreground">
              <Info className="h-3.5 w-3.5 mt-0.5 shrink-0" />
              <span>Metrics use live prices from KiteTicker. Breakeven gap shows distance to profit zone for option buyers.</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
