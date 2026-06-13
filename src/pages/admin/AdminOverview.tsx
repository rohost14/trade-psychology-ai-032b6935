import { useEffect, useState } from 'react';
import { RefreshCw, AlertTriangle, Circle } from 'lucide-react';
import { adminApi } from '@/lib/adminApi';

// ─── Design tokens ───────────────────────────────────────────────────────────
const T = {
  bg:       '#09090b',
  surface:  '#111115',
  raised:   '#16161d',
  border:   '#1c1c28',
  border2:  '#252536',
  text:     '#f1f0f5',
  muted:    '#6b6a82',
  dim:      '#3a3a50',
  amber:    '#f59e0b',
  amberBg:  'rgba(245,158,11,0.1)',
  green:    '#22c55e',
  greenBg:  'rgba(34,197,94,0.08)',
  red:      '#ef4444',
  redBg:    'rgba(239,68,68,0.08)',
  blue:     '#3b82f6',
  blueBg:   'rgba(59,130,246,0.1)',
  purple:   '#8b5cf6',
  purpleBg: 'rgba(139,92,246,0.1)',
};

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

// ─── Lifecycle config ─────────────────────────────────────────────────────────
const LC_CFG: Record<string, { color: string; bg: string; label: string }> = {
  active:       { color: T.green,  bg: T.greenBg,  label: 'Active' },
  new:          { color: T.blue,   bg: T.blueBg,   label: 'New' },
  at_risk:      { color: T.amber,  bg: T.amberBg,  label: 'At Risk' },
  churned:      { color: T.red,    bg: T.redBg,    label: 'Churned' },
  inactive:     { color: T.muted,  bg: 'rgba(107,106,130,0.12)', label: 'Inactive' },
  suspended:    { color: T.red,    bg: T.redBg,    label: 'Suspended' },
  disconnected: { color: T.muted,  bg: 'rgba(107,106,130,0.12)', label: 'Disconnected' },
};

// ─── Utilities ────────────────────────────────────────────────────────────────
function pct(n: number, d: number, decimals = 1): string {
  if (!d) return '—';
  return (n / d * 100).toFixed(decimals) + '%';
}

function stepConversion(n: number, prev: number): string {
  if (!prev) return '—';
  return (n / prev * 100).toFixed(1) + '%';
}

// ─── Sub-components ──────────────────────────────────────────────────────────

function SectionHeader({ title, sub }: { title: string; sub?: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 18 }}>
      <span style={{ fontSize: 13, fontWeight: 600, color: T.text, letterSpacing: '-0.01em' }}>{title}</span>
      {sub && <span style={{ fontSize: 11, color: T.dim }}>{sub}</span>}
    </div>
  );
}

function KpiCard({ label, value, sub, accent, badge }: {
  label: string; value: number | string; sub?: string; accent?: string; badge?: string;
}) {
  const color = accent || T.text;
  return (
    <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 10, padding: '16px 20px' }}>
      <div style={{ fontSize: 11, fontWeight: 500, color: T.muted, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 10 }}>
        {label}
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 6 }}>
        <div style={{ fontSize: 28, fontWeight: 700, color, lineHeight: 1, fontVariantNumeric: 'tabular-nums', letterSpacing: '-0.02em' }}>
          {typeof value === 'number' ? value.toLocaleString('en-IN') : value}
        </div>
        {badge && (
          <span style={{ fontSize: 11, fontWeight: 600, color: T.muted, padding: '2px 7px', borderRadius: 20, background: T.raised, border: `1px solid ${T.border}` }}>
            {badge}
          </span>
        )}
      </div>
      {sub && <div style={{ fontSize: 12, color: T.muted }}>{sub}</div>}
    </div>
  );
}

function Sparkline({ data }: { data: { date: string; count: number }[] }) {
  if (data.length < 2) return (
    <p style={{ fontSize: 12, color: T.dim, padding: '12px 0' }}>Not enough data yet</p>
  );
  const max = Math.max(...data.map(d => d.count), 1);
  const W = 600, H = 80, P = 4;
  const pts = data.map((d, i) => {
    const x = P + (i / (data.length - 1)) * (W - P * 2);
    const y = H - P - (d.count / max) * (H - P * 2);
    return `${x},${y}`;
  });
  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: 80, display: 'block' }} preserveAspectRatio="none">
        <defs>
          <linearGradient id="sg" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#f59e0b" stopOpacity="0.18" />
            <stop offset="100%" stopColor="#f59e0b" stopOpacity="0" />
          </linearGradient>
        </defs>
        <polygon points={`${P},${H} ${pts.join(' ')} ${W - P},${H}`} fill="url(#sg)" />
        <polyline points={pts.join(' ')} fill="none" stroke="#f59e0b" strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
      </svg>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4 }}>
        <span style={{ fontSize: 11, color: T.dim }}>{data[0]?.date}</span>
        <span style={{ fontSize: 11, color: T.dim }}>{data[data.length - 1]?.date}</span>
      </div>
    </div>
  );
}

function StatusPill({ label, ok }: { label: string; ok: boolean }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 6,
      padding: '6px 12px', borderRadius: 20,
      background: ok ? T.greenBg : T.redBg,
      border: `1px solid ${ok ? 'rgba(34,197,94,0.2)' : 'rgba(239,68,68,0.2)'}`,
    }}>
      <Circle size={6} fill={ok ? T.green : T.red} style={{ color: ok ? T.green : T.red }} />
      <span style={{ fontSize: 12, color: ok ? T.green : T.red, fontWeight: 500 }}>{label}</span>
      <span style={{ fontSize: 11, color: T.muted }}>{ok ? 'healthy' : 'error'}</span>
    </div>
  );
}

// ─── Funnel ────────────────────────────────────────────────────────────────
interface FunnelStep { label: string; value: number; prevValue: number; total: number; }

function FunnelRow({ label, value, prevValue, total, isFirst }: FunnelStep & { isFirst: boolean }) {
  const pctOfTotal   = total > 0 ? value / total : 0;
  const stepConv     = prevValue > 0 ? value / prevValue : 1;
  const dropoff      = prevValue > 0 ? (1 - stepConv) * 100 : 0;
  const barColor     = isFirst ? T.amber : pctOfTotal > 0.6 ? T.green : pctOfTotal > 0.3 ? T.amber : T.red;

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '160px 1fr 80px 110px', gap: 14, alignItems: 'center', padding: '11px 0', borderBottom: `1px solid ${T.border}` }}>
      {/* Label */}
      <div style={{ fontSize: 13, color: T.text, fontWeight: 500 }}>{label}</div>

      {/* Bar */}
      <div style={{ height: 8, background: T.raised, borderRadius: 4, overflow: 'hidden', position: 'relative' }}>
        <div style={{
          position: 'absolute', left: 0, top: 0, bottom: 0,
          width: `${pctOfTotal * 100}%`,
          background: barColor,
          borderRadius: 4,
          transition: 'width 0.6s cubic-bezier(0.4,0,0.2,1)',
          boxShadow: `0 0 8px ${barColor}60`,
        }} />
      </div>

      {/* Count */}
      <div style={{ fontSize: 14, fontWeight: 700, color: T.text, fontVariantNumeric: 'tabular-nums', textAlign: 'right' }}>
        {value.toLocaleString('en-IN')}
      </div>

      {/* Pct + dropoff */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 1 }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: barColor, fontVariantNumeric: 'tabular-nums' }}>
          {(pctOfTotal * 100).toFixed(1)}%
        </span>
        {!isFirst && (
          <span style={{ fontSize: 10, color: dropoff > 30 ? T.red : T.muted }}>
            {dropoff > 0 ? `↓ ${dropoff.toFixed(1)}% drop` : '—'}
          </span>
        )}
      </div>
    </div>
  );
}

function FunnelSection({ f }: { f: OverviewData['funnel'] }) {
  const steps: Array<{ label: string; value: number }> = [
    { label: 'Signed Up',         value: f.total },
    { label: 'Connected Zerodha', value: f.connected },
    { label: 'First Trade',       value: f.has_trades },
    { label: 'Alert Received',    value: f.has_alerts },
    { label: 'Alert Acted On',    value: f.has_acknowledged },
  ];

  // Bottleneck: the step with the biggest absolute drop
  let maxDrop = 0; let bottleneckIdx = -1;
  for (let i = 1; i < steps.length; i++) {
    const drop = steps[i - 1].value - steps[i].value;
    if (drop > maxDrop) { maxDrop = drop; bottleneckIdx = i; }
  }

  return (
    <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 10, padding: '20px 24px', marginBottom: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 6 }}>
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: T.text }}>Conversion Funnel</div>
          <div style={{ fontSize: 12, color: T.muted, marginTop: 3 }}>
            End-to-end: signup → Zerodha → trade → alert → action
          </div>
        </div>
        {bottleneckIdx > 0 && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 6,
            padding: '5px 12px', borderRadius: 20,
            background: T.redBg, border: '1px solid rgba(239,68,68,0.2)',
          }}>
            <span style={{ fontSize: 11, color: T.red }}>
              Biggest drop: <strong>{steps[bottleneckIdx].label}</strong> (−{maxDrop.toLocaleString('en-IN')})
            </span>
          </div>
        )}
      </div>

      {/* Column headers */}
      <div style={{ display: 'grid', gridTemplateColumns: '160px 1fr 80px 110px', gap: 14, padding: '6px 0', marginBottom: 2 }}>
        <span style={{ fontSize: 10, fontWeight: 600, color: T.dim, textTransform: 'uppercase', letterSpacing: '0.07em' }}>Stage</span>
        <span />
        <span style={{ fontSize: 10, fontWeight: 600, color: T.dim, textTransform: 'uppercase', letterSpacing: '0.07em', textAlign: 'right' }}>Count</span>
        <span style={{ fontSize: 10, fontWeight: 600, color: T.dim, textTransform: 'uppercase', letterSpacing: '0.07em', textAlign: 'right' }}>% of total</span>
      </div>

      {steps.map((s, i) => (
        <FunnelRow
          key={s.label}
          label={s.label}
          value={s.value}
          prevValue={i > 0 ? steps[i - 1].value : s.value}
          total={f.total}
          isFirst={i === 0}
        />
      ))}

      {/* Overall conversion */}
      {f.total > 0 && (
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 12 }}>
          <div style={{ fontSize: 12, color: T.muted }}>
            Overall conversion:&nbsp;
            <strong style={{ color: T.text, fontVariantNumeric: 'tabular-nums' }}>
              {pct(f.has_acknowledged, f.total)} end-to-end
            </strong>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Lifecycle distribution ───────────────────────────────────────────────────
function LifecycleDist({ dist }: { dist: OverviewData['lifecycle_dist'] }) {
  const total = Object.values(dist).reduce((a, b) => a + b, 0);
  const stages = [
    { key: 'active', ...LC_CFG.active },
    { key: 'new', ...LC_CFG.new },
    { key: 'at_risk', ...LC_CFG.at_risk },
    { key: 'churned', ...LC_CFG.churned },
    { key: 'inactive', ...LC_CFG.inactive },
    { key: 'suspended', ...LC_CFG.suspended },
    { key: 'disconnected', ...LC_CFG.disconnected },
  ].filter(s => (dist as any)[s.key] > 0);

  return (
    <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 10, padding: '20px 22px' }}>
      <SectionHeader title="Lifecycle Distribution" sub={`${total.toLocaleString('en-IN')} total`} />

      {/* Stacked bar */}
      {total > 0 && (
        <div style={{ display: 'flex', height: 8, borderRadius: 4, overflow: 'hidden', marginBottom: 18, gap: 1 }}>
          {stages.map(s => {
            const n = (dist as any)[s.key] as number;
            return n > 0 ? (
              <div
                key={s.key}
                style={{ flex: n, background: s.color, minWidth: 2 }}
                title={`${s.label}: ${n} (${pct(n, total)})`}
              />
            ) : null;
          })}
        </div>
      )}

      {/* Rows */}
      {stages.map(s => {
        const n = (dist as any)[s.key] as number;
        const p = total > 0 ? n / total : 0;
        return (
          <div key={s.key} style={{ display: 'grid', gridTemplateColumns: '90px 1fr 50px', gap: 10, alignItems: 'center', marginBottom: 10 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <Circle size={6} fill={s.color} style={{ color: s.color, flexShrink: 0 }} />
              <span style={{ fontSize: 12, color: T.muted }}>{s.label}</span>
            </div>
            <div style={{ height: 5, background: T.raised, borderRadius: 3, overflow: 'hidden' }}>
              <div style={{
                height: '100%', width: `${p * 100}%`, background: s.color,
                borderRadius: 3, transition: 'width 0.5s ease',
              }} />
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 12, fontWeight: 600, color: T.text, fontVariantNumeric: 'tabular-nums' }}>{n}</span>
            </div>
          </div>
        );
      })}

      {total === 0 && (
        <p style={{ fontSize: 12, color: T.muted, textAlign: 'center', padding: '16px 0' }}>No users yet</p>
      )}
    </div>
  );
}

// ─── Feature adoption ──────────────────────────────────────────────────────────
function FeatureAdoption({ a }: { a: OverviewData['adoption'] }) {
  const rows: Array<{ label: string; n: number; hint: string; color: string }> = [
    { label: 'Push notifications', n: a.push_enabled,      hint: 'Browser push enabled',       color: T.amber },
    { label: 'Limits configured',  n: a.limits_configured, hint: 'Trade or loss limit set',    color: T.blue },
    { label: 'Guardian set',       n: a.guardian_set,      hint: 'Guardian phone on file',     color: T.purple },
    { label: 'WhatsApp alerts',    n: a.whatsapp_enabled,  hint: 'WhatsApp notifications on',  color: T.green },
  ];

  return (
    <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 10, padding: '20px 22px' }}>
      <SectionHeader title="Feature Adoption" sub={a.total ? `${a.total.toLocaleString('en-IN')} total users` : undefined} />

      {rows.map(({ label, n, hint, color }) => {
        const p = a.total > 0 ? n / a.total : 0;
        const pStr = a.total > 0 ? (p * 100).toFixed(0) + '%' : '—';
        return (
          <div key={label} style={{ marginBottom: 14 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 5 }}>
              <div>
                <span style={{ fontSize: 13, color: T.text, fontWeight: 500 }}>{label}</span>
                <span style={{ fontSize: 11, color: T.dim, marginLeft: 8 }}>{hint}</span>
              </div>
              <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                <span style={{ fontSize: 12, color: T.muted, fontVariantNumeric: 'tabular-nums' }}>
                  {n.toLocaleString('en-IN')} / {a.total.toLocaleString('en-IN')}
                </span>
                <span style={{ fontSize: 13, fontWeight: 700, color, fontVariantNumeric: 'tabular-nums', minWidth: 38, textAlign: 'right' }}>
                  {pStr}
                </span>
              </div>
            </div>
            <div style={{ height: 6, background: T.raised, borderRadius: 3, overflow: 'hidden' }}>
              <div style={{
                height: '100%', width: `${p * 100}%`, background: color,
                borderRadius: 3, transition: 'width 0.5s ease',
                boxShadow: `0 0 6px ${color}50`,
              }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────
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
    } catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  return (
    <div style={{ padding: '28px 32px', fontFamily: "'Inter', 'DM Sans', sans-serif", maxWidth: 1100 }}>

      {/* ── Header ─────────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 28 }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 700, color: T.text, margin: 0, letterSpacing: '-0.02em' }}>Overview</h1>
          {ts && <p style={{ fontSize: 12, color: T.dim, marginTop: 4 }}>Last updated {ts} IST</p>}
        </div>
        <button
          onClick={load} disabled={loading}
          style={{
            display: 'flex', alignItems: 'center', gap: 6, padding: '6px 12px',
            borderRadius: 7, background: T.surface, border: `1px solid ${T.border}`,
            color: T.muted, fontSize: 12, cursor: loading ? 'not-allowed' : 'pointer', fontFamily: 'inherit',
          }}
        >
          <RefreshCw size={12} style={{ animation: loading ? 'spin 1s linear infinite' : 'none' }} />
          Refresh
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </button>
      </div>

      {/* ── Error banner ───────────────────────────────────────────────── */}
      {error && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px',
          borderRadius: 8, background: T.redBg,
          border: '1px solid rgba(239,68,68,0.18)', marginBottom: 20,
        }}>
          <AlertTriangle size={13} style={{ color: T.red, flexShrink: 0 }} />
          <span style={{ fontSize: 12, color: T.red }}>{error}</span>
        </div>
      )}

      {/* ── Loading ────────────────────────────────────────────────────── */}
      {loading && !data && (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '56px 0' }}>
          <div style={{ width: 24, height: 24, border: `2px solid ${T.amber}`, borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
        </div>
      )}

      {data && (
        <>
          {/* ── KPI Row 1: User Base ────────────────────────────────────── */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 12 }}>
            <KpiCard
              label="Total Users"
              value={data.users.total}
              sub={`${data.users.connected} Zerodha connected`}
            />
            <KpiCard
              label="Connected"
              value={data.users.connected}
              sub="Zerodha linked"
              accent={T.green}
              badge={data.users.total > 0 ? pct(data.users.connected, data.users.total, 0) : undefined}
            />
            <KpiCard
              label="Online Now"
              value={data.users.online_now}
              sub="Active WebSocket"
              accent={data.users.online_now > 0 ? T.green : undefined}
            />
            <KpiCard
              label="New Today"
              value={data.users.new_today}
              sub="Signups since IST midnight"
            />
          </div>

          {/* ── KPI Row 2: Engagement ──────────────────────────────────── */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 24 }}>
            <KpiCard
              label="DAU"
              value={data.engagement.dau}
              sub="Traders in last 24h"
              accent={T.blue}
            />
            <KpiCard
              label="WAU"
              value={data.engagement.wau}
              sub="Traders in last 7d"
            />
            <KpiCard
              label="MAU"
              value={data.engagement.mau}
              sub="Traders in last 30d"
            />
            <KpiCard
              label="DAU / MAU"
              value={`${data.engagement.dau_mau_ratio}%`}
              sub="Stickiness (>20% = healthy)"
              accent={
                data.engagement.dau_mau_ratio >= 20 ? T.green :
                data.engagement.dau_mau_ratio >= 10 ? T.amber : T.red
              }
            />
          </div>

          {/* ── Conversion Funnel ───────────────────────────────────────── */}
          <FunnelSection f={data.funnel} />

          {/* ── Bottom 3-col ────────────────────────────────────────────── */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16, marginBottom: 16 }}>

            {/* Signups chart */}
            <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 10, padding: '20px 22px' }}>
              <SectionHeader title="New Signups" sub="Last 14 days" />
              <Sparkline data={data.daily_signups} />

              {/* Activity counts below chart */}
              <div style={{ marginTop: 16, display: 'flex', gap: 0, borderTop: `1px solid ${T.border}`, paddingTop: 14 }}>
                {[
                  { label: 'Trades', value: data.activity.total_trades.toLocaleString('en-IN') },
                  { label: 'Alerts', value: data.activity.total_alerts.toLocaleString('en-IN') },
                  { label: 'Today',  value: data.activity.alerts_today.toLocaleString('en-IN') + ' alerts' },
                ].map((row, i) => (
                  <div key={row.label} style={{
                    flex: 1, padding: '0 12px',
                    borderLeft: i > 0 ? `1px solid ${T.border}` : 'none',
                  }}>
                    <div style={{ fontSize: 11, color: T.dim, marginBottom: 3 }}>{row.label}</div>
                    <div style={{ fontSize: 14, fontWeight: 600, color: T.text, fontVariantNumeric: 'tabular-nums' }}>{row.value}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Lifecycle distribution */}
            <LifecycleDist dist={data.lifecycle_dist} />

            {/* Feature adoption */}
            <FeatureAdoption a={data.adoption} />
          </div>

          {/* ── Infrastructure (slim row) ────────────────────────────── */}
          <div style={{
            background: T.surface, border: `1px solid ${T.border}`, borderRadius: 10,
            padding: '14px 22px',
            display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap',
          }}>
            <span style={{ fontSize: 11, fontWeight: 600, color: T.muted, textTransform: 'uppercase', letterSpacing: '0.07em', flexShrink: 0 }}>Infrastructure</span>
            <StatusPill label="Database" ok={data.health.db === 'ok'} />
            <StatusPill label="Redis"    ok={data.health.redis === 'ok'} />
            <div style={{ marginLeft: 'auto', display: 'flex', gap: 24 }}>
              {[
                { label: 'Connect rate',  value: data.users.total > 0 ? pct(data.users.connected, data.users.total, 0) : '—' },
                { label: '30d retention', value: data.users.total > 0 ? pct(data.engagement.mau, data.users.total, 0) : '—' },
                { label: 'Alerts / user', value: data.users.total > 0 ? (data.activity.total_alerts / data.users.total).toFixed(1) : '—' },
              ].map(({ label, value }) => (
                <div key={label} style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: 11, color: T.dim }}>{label}</div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: T.text, fontVariantNumeric: 'tabular-nums' }}>{value}</div>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
