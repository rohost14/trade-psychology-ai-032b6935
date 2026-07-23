import { useEffect, useState } from 'react';
import { adminApi } from '@/lib/adminApi';
import {
  AdminPage, AdminCard, KpiCard, SectionHeader, StatusPill, MeterRow,
  AreaSparkline, LoadingBlock, ErrorBanner, EmptyState, RefreshButton,
  fmtNum, pct, type Accent,
} from './_ui';
import { cn } from '@/lib/utils';

// ─── Types ───────────────────────────────────────────────────────────────────
interface OverviewData {
  users:    { total: number; connected: number; new_today: number; online_now: number };
  engagement: { dau: number; wau: number; mau: number; dau_mau_ratio: number };
  activity: { total_trades: number; total_alerts: number; alerts_today: number };
  funnel:   { total: number; connected: number; has_trades: number; has_alerts: number; has_acknowledged: number };
  lifecycle_dist: { active: number; new: number; at_risk: number; churned: number; inactive: number; suspended: number; disconnected: number };
  adoption: { push_enabled: number; limits_configured: number; guardian_set: number; whatsapp_enabled: number; total: number };
  health:   { db: string; redis: string };
  daily_signups: { date: string; count: number }[];
}

// ─── Lifecycle config (accent tokens, not hex) ──────────────────────────────────
const LC_CFG: Record<string, { accent: Accent; label: string }> = {
  active:       { accent: 'profit',  label: 'Active' },
  new:          { accent: 'brand',   label: 'New' },
  at_risk:      { accent: 'warning', label: 'At Risk' },
  churned:      { accent: 'loss',    label: 'Churned' },
  inactive:     { accent: 'muted',   label: 'Inactive' },
  suspended:    { accent: 'loss',    label: 'Suspended' },
  disconnected: { accent: 'muted',   label: 'Disconnected' },
};
const ACCENT_RGB: Record<Accent, string> = {
  profit:  'rgb(var(--tm-profit))',
  loss:    'rgb(var(--tm-loss))',
  warning: 'rgb(var(--tm-obs))',
  brand:   'rgb(var(--tm-brand))',
  muted:   'rgb(var(--muted-foreground))',
};

// ─── Conversion funnel ─────────────────────────────────────────────────────────
function FunnelSection({ f }: { f: OverviewData['funnel'] }) {
  const steps = [
    { label: 'Signed Up',         value: f.total },
    { label: 'Connected Zerodha', value: f.connected },
    { label: 'First Trade',       value: f.has_trades },
    { label: 'Alert Received',    value: f.has_alerts },
    { label: 'Alert Acted On',    value: f.has_acknowledged },
  ];

  let maxDrop = 0, bottleneckIdx = -1;
  for (let i = 1; i < steps.length; i++) {
    const drop = steps[i - 1].value - steps[i].value;
    if (drop > maxDrop) { maxDrop = drop; bottleneckIdx = i; }
  }

  const cols = 'grid gap-3.5 items-center [grid-template-columns:160px_1fr_80px_110px]';

  return (
    <AdminCard
      className="mb-4"
      title="Conversion Funnel"
      subtitle="End-to-end: signup → Zerodha → trade → alert → action"
      right={bottleneckIdx > 0 ? (
        <span
          className="inline-flex items-center px-3 py-1.5 rounded-full text-[11px] border"
          style={{ background: 'color-mix(in srgb, rgb(var(--tm-loss)) 8%, transparent)', borderColor: 'color-mix(in srgb, rgb(var(--tm-loss)) 20%, transparent)', color: 'rgb(var(--tm-loss))' }}
        >
          Biggest drop:&nbsp;<strong>{steps[bottleneckIdx].label}</strong>&nbsp;(−{fmtNum(maxDrop)})
        </span>
      ) : undefined}
    >
      {/* Column headers */}
      <div className={cn(cols, 'pb-1.5 mb-0.5')}>
        <span className="table-header">Stage</span>
        <span />
        <span className="table-header text-right">Count</span>
        <span className="table-header text-right">% of total</span>
      </div>

      {steps.map((s, i) => {
        const isFirst = i === 0;
        const prev = isFirst ? s.value : steps[i - 1].value;
        const pctOfTotal = f.total > 0 ? s.value / f.total : 0;
        const dropoff = prev > 0 ? (1 - s.value / prev) * 100 : 0;
        const accent: Accent = isFirst ? 'brand' : pctOfTotal > 0.6 ? 'profit' : pctOfTotal > 0.3 ? 'warning' : 'loss';
        const rgb = ACCENT_RGB[accent];
        return (
          <div key={s.label} className={cn(cols, 'py-2.5 border-b border-border')}>
            <div className="text-[13px] font-medium text-foreground">{s.label}</div>
            <div className="h-2 rounded bg-muted overflow-hidden relative">
              <div className="absolute inset-y-0 left-0 rounded transition-[width] duration-700"
                   style={{ width: `${pctOfTotal * 100}%`, background: rgb, boxShadow: `0 0 8px color-mix(in srgb, ${rgb} 38%, transparent)` }} />
            </div>
            <div className="text-sm font-bold text-foreground tabular-nums text-right">{fmtNum(s.value)}</div>
            <div className="flex flex-col items-end gap-0.5">
              <span className="text-[13px] font-semibold tabular-nums" style={{ color: rgb }}>{(pctOfTotal * 100).toFixed(1)}%</span>
              {!isFirst && (
                <span className="text-[10px]" style={{ color: dropoff > 30 ? 'rgb(var(--tm-loss))' : 'rgb(var(--muted-foreground))' }}>
                  {dropoff > 0 ? `↓ ${dropoff.toFixed(1)}% drop` : '—'}
                </span>
              )}
            </div>
          </div>
        );
      })}

      {f.total > 0 && (
        <div className="flex justify-end mt-3 text-xs text-muted-foreground">
          Overall conversion:&nbsp;<strong className="text-foreground tabular-nums">{pct(f.has_acknowledged, f.total)} end-to-end</strong>
        </div>
      )}
    </AdminCard>
  );
}

// ─── Lifecycle distribution ─────────────────────────────────────────────────────
function LifecycleDist({ dist }: { dist: OverviewData['lifecycle_dist'] }) {
  const total = Object.values(dist).reduce((a, b) => a + b, 0);
  const stages = (['active','new','at_risk','churned','inactive','suspended','disconnected'] as const)
    .map(key => ({ key, ...LC_CFG[key] }))
    .filter(s => (dist as Record<string, number>)[s.key] > 0);

  return (
    <AdminCard title="Lifecycle Distribution" subtitle={`${fmtNum(total)} total`}>
      {total > 0 && (
        <div className="flex h-2 rounded overflow-hidden mb-4 gap-px">
          {stages.map(s => {
            const n = (dist as Record<string, number>)[s.key];
            return n > 0 ? (
              <div key={s.key} className="min-w-[2px]" style={{ flex: n, background: ACCENT_RGB[s.accent] }} title={`${s.label}: ${n} (${pct(n, total)})`} />
            ) : null;
          })}
        </div>
      )}
      {stages.map(s => {
        const n = (dist as Record<string, number>)[s.key];
        return (
          <MeterRow key={s.key} label={s.label} value={n} total={total} accent={s.accent} />
        );
      })}
      {total === 0 && <EmptyState>No users yet</EmptyState>}
    </AdminCard>
  );
}

// ─── Feature adoption ────────────────────────────────────────────────────────────
function FeatureAdoption({ a }: { a: OverviewData['adoption'] }) {
  const rows: Array<{ label: string; n: number; hint: string; accent: Accent }> = [
    { label: 'Push notifications', n: a.push_enabled,      hint: 'Browser push enabled',      accent: 'warning' },
    { label: 'Limits configured',  n: a.limits_configured, hint: 'Trade or loss limit set',   accent: 'brand' },
    { label: 'Guardian set',       n: a.guardian_set,      hint: 'Guardian phone on file',    accent: 'brand' },
    { label: 'WhatsApp alerts',    n: a.whatsapp_enabled,  hint: 'WhatsApp notifications on',  accent: 'profit' },
  ];
  return (
    <AdminCard title="Feature Adoption" subtitle={a.total ? `${fmtNum(a.total)} total users` : undefined}>
      {rows.map(r => <MeterRow key={r.label} label={r.label} hint={r.hint} value={r.n} total={a.total} accent={r.accent} />)}
    </AdminCard>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────────
export default function AdminOverview() {
  const [data, setData]       = useState<OverviewData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState('');
  const [ts, setTs]           = useState('');

  const load = async () => {
    setLoading(true); setError('');
    try {
      const d = await adminApi.overview();
      setData(d);
      setTs(new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }));
    } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  return (
    <AdminPage
      title="Overview"
      subtitle={ts ? `Last updated ${ts} IST` : undefined}
      actions={<RefreshButton onClick={load} loading={loading} />}
    >
      <ErrorBanner message={error} />
      {loading && !data && <LoadingBlock />}

      {data && (
        <>
          {/* KPI Row 1: User Base */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
            <KpiCard label="Total Users" value={data.users.total} sub={`${data.users.connected} Zerodha connected`} />
            <KpiCard label="Connected" value={data.users.connected} sub="Zerodha linked" accent="profit"
                     badge={data.users.total > 0 ? pct(data.users.connected, data.users.total, 0) : undefined} />
            <KpiCard label="Online Now" value={data.users.online_now} sub="Active WebSocket"
                     accent={data.users.online_now > 0 ? 'profit' : undefined} />
            <KpiCard label="New Today" value={data.users.new_today} sub="Signups since IST midnight" />
          </div>

          {/* KPI Row 2: Engagement */}
          {data.engagement && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
              <KpiCard label="DAU" value={data.engagement.dau} sub="Traders in last 24h" accent="brand" />
              <KpiCard label="WAU" value={data.engagement.wau} sub="Traders in last 7d" />
              <KpiCard label="MAU" value={data.engagement.mau} sub="Traders in last 30d" />
              <KpiCard label="DAU / MAU" value={`${data.engagement.dau_mau_ratio}%`} sub="Stickiness (>20% = healthy)"
                       accent={data.engagement.dau_mau_ratio >= 20 ? 'profit' : data.engagement.dau_mau_ratio >= 10 ? 'warning' : 'loss'} />
            </div>
          )}

          {/* Conversion Funnel */}
          {data.funnel && <FunnelSection f={data.funnel} />}

          {/* Bottom 3-col */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4">
            {/* Signups chart */}
            <AdminCard title="New Signups" subtitle="Last 14 days">
              <AreaSparkline data={data.daily_signups} />
              <div className="mt-4 flex border-t border-border pt-3.5">
                {[
                  { label: 'Trades', value: fmtNum(data.activity.total_trades) },
                  { label: 'Alerts', value: fmtNum(data.activity.total_alerts) },
                  { label: 'Today',  value: fmtNum(data.activity.alerts_today) + ' alerts' },
                ].map((row, i) => (
                  <div key={row.label} className={cn('flex-1 px-3', i > 0 && 'border-l border-border')}>
                    <div className="text-[11px] text-muted-foreground mb-0.5">{row.label}</div>
                    <div className="text-sm font-semibold text-foreground tabular-nums">{row.value}</div>
                  </div>
                ))}
              </div>
            </AdminCard>

            {data.lifecycle_dist
              ? <LifecycleDist dist={data.lifecycle_dist} />
              : <AdminCard title="Lifecycle Distribution"><EmptyState>Backend not updated yet</EmptyState></AdminCard>}

            {data.adoption
              ? <FeatureAdoption a={data.adoption} />
              : <AdminCard title="Feature Adoption"><EmptyState>Backend not updated yet</EmptyState></AdminCard>}
          </div>

          {/* Infrastructure slim row */}
          <AdminCard noPadding>
            <div className="flex items-center gap-4 flex-wrap px-5 py-3.5">
              <span className="tm-label shrink-0">Infrastructure</span>
              <StatusPill label="Database" ok={data.health.db === 'ok'} />
              <StatusPill label="Redis" ok={data.health.redis === 'ok'} />
              <div className="ml-auto flex gap-6">
                {[
                  { label: 'Connect rate',  value: data.users.total > 0 ? pct(data.users.connected, data.users.total, 0) : '—' },
                  { label: '30d retention', value: data.users.total > 0 && data.engagement ? pct(data.engagement.mau, data.users.total, 0) : '—' },
                  { label: 'Alerts / user', value: data.users.total > 0 ? (data.activity.total_alerts / data.users.total).toFixed(1) : '—' },
                ].map(({ label, value }) => (
                  <div key={label} className="text-right">
                    <div className="text-[11px] text-muted-foreground">{label}</div>
                    <div className="text-[13px] font-semibold text-foreground tabular-nums">{value}</div>
                  </div>
                ))}
              </div>
            </div>
          </AdminCard>
        </>
      )}
    </AdminPage>
  );
}
