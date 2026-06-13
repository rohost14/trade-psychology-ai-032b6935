import { useEffect, useState } from 'react';
import { Users, TrendingUp, Bell, Activity, RefreshCw, AlertTriangle, Wifi, Circle } from 'lucide-react';
import { adminApi } from '@/lib/adminApi';

interface OverviewData {
  users:    { total: number; connected: number; new_today: number; active_7d: number; online_now: number };
  activity: { total_trades: number; total_alerts: number; alerts_today: number };
  health:   { db: string; redis: string };
  daily_signups: { date: string; count: number }[];
}

const T = {
  bg:      '#09090b',
  surface: '#111115',
  border:  '#1c1c28',
  text:    '#f1f0f5',
  muted:   '#6b6a82',
  dim:     '#3a3a50',
  amber:   '#f59e0b',
  green:   '#22c55e',
  red:     '#ef4444',
};

function KpiCard({ label, value, sub, trend, accent }: {
  label: string; value: number | string; sub?: string; trend?: string; accent?: string;
}) {
  const color = accent || T.text;
  return (
    <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 10, padding: '16px 20px' }}>
      <div style={{ fontSize: 11, fontWeight: 500, color: T.muted, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 10 }}>{label}</div>
      <div style={{ fontSize: 28, fontWeight: 700, color, lineHeight: 1, fontVariantNumeric: 'tabular-nums', letterSpacing: '-0.02em', marginBottom: 6 }}>
        {typeof value === 'number' ? value.toLocaleString() : value}
      </div>
      {sub && <div style={{ fontSize: 12, color: T.muted }}>{sub}</div>}
      {trend && <div style={{ fontSize: 11, color: T.green, marginTop: 2, fontWeight: 500 }}>{trend}</div>}
    </div>
  );
}

function Sparkline({ data }: { data: { date: string; count: number }[] }) {
  if (data.length < 2) return (
    <p style={{ fontSize: 12, color: T.dim, padding: '12px 0' }}>Not enough data yet</p>
  );
  const max = Math.max(...data.map(d => d.count), 1);
  const W = 600, H = 72, P = 4;
  const pts = data.map((d, i) => {
    const x = P + (i / (data.length - 1)) * (W - P * 2);
    const y = H - P - (d.count / max) * (H - P * 2);
    return `${x},${y}`;
  });
  const area = `${P},${H} ${pts.join(' ')} ${W - P},${H}`;
  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: 72, display: 'block' }} preserveAspectRatio="none">
        <defs>
          <linearGradient id="sg" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#f59e0b" stopOpacity="0.15" />
            <stop offset="100%" stopColor="#f59e0b" stopOpacity="0" />
          </linearGradient>
        </defs>
        <polygon points={area} fill="url(#sg)" />
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
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '5px 10px', borderRadius: 20, background: ok ? 'rgba(34,197,94,0.08)' : 'rgba(239,68,68,0.08)', border: `1px solid ${ok ? 'rgba(34,197,94,0.2)' : 'rgba(239,68,68,0.2)'}` }}>
      <Circle size={6} fill={ok ? T.green : T.red} style={{ color: ok ? T.green : T.red }} />
      <span style={{ fontSize: 12, color: ok ? T.green : T.red, fontWeight: 500 }}>{label}</span>
      <span style={{ fontSize: 11, color: T.muted }}>{ok ? 'healthy' : 'error'}</span>
    </div>
  );
}

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
    <div style={{ padding: '28px 32px', fontFamily: "'Inter', 'DM Sans', sans-serif", maxWidth: 1080 }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 28 }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 700, color: T.text, margin: 0, letterSpacing: '-0.02em' }}>Overview</h1>
          {ts && <p style={{ fontSize: 12, color: T.dim, marginTop: 4 }}>Last updated {ts} IST</p>}
        </div>
        <button
          onClick={load} disabled={loading}
          style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 12px', borderRadius: 7, background: T.surface, border: `1px solid ${T.border}`, color: T.muted, fontSize: 12, cursor: loading ? 'not-allowed' : 'pointer', fontFamily: 'inherit' }}
        >
          <RefreshCw size={12} style={{ animation: loading ? 'spin 1s linear infinite' : 'none' }} />
          Refresh
        </button>
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>

      {error && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px', borderRadius: 8, background: 'rgba(239,68,68,0.07)', border: '1px solid rgba(239,68,68,0.18)', marginBottom: 20 }}>
          <AlertTriangle size={13} style={{ color: T.red, flexShrink: 0 }} />
          <span style={{ fontSize: 12, color: T.red }}>{error}</span>
        </div>
      )}

      {loading && !data && (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '48px 0' }}>
          <div style={{ width: 24, height: 24, border: `2px solid ${T.amber}`, borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
        </div>
      )}

      {data && (
        <>
          {/* KPI row 1 — Users */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 12 }}>
            <KpiCard label="Total Users"   value={data.users.total}      sub={`${data.users.active_7d} active last 7d`} />
            <KpiCard label="Connected"     value={data.users.connected}   sub="Zerodha linked"     accent={T.green}   trend={data.users.connected > 0 ? `${Math.round(data.users.connected / data.users.total * 100)}% of total` : undefined} />
            <KpiCard label="Online Now"    value={data.users.online_now}  sub="Active WebSocket"   accent={T.green} />
            <KpiCard label="New Today"     value={data.users.new_today}   sub="Signups since midnight" />
          </div>

          {/* KPI row 2 — Activity */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 24 }}>
            <KpiCard label="Total Trades"  value={data.activity.total_trades}  sub="All time" />
            <KpiCard label="Total Alerts"  value={data.activity.total_alerts}  sub="All time" />
            <KpiCard label="Alerts Today"  value={data.activity.alerts_today}  accent={data.activity.alerts_today > 50 ? T.red : T.text} />
            <KpiCard label="Active (7d)"   value={data.users.active_7d}        sub="Unique users" />
          </div>

          {/* Bottom row: chart + status */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 280px', gap: 16 }}>

            {/* Signups chart */}
            <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 10, padding: '18px 22px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 16 }}>
                <span style={{ fontSize: 13, fontWeight: 600, color: T.text }}>New Signups</span>
                <span style={{ fontSize: 11, color: T.dim }}>Last 14 days</span>
              </div>
              <Sparkline data={data.daily_signups} />
            </div>

            {/* Status + quick stats */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 10, padding: '18px 20px' }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: T.muted, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 12 }}>Infrastructure</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  <StatusPill label="Database" ok={data.health.db === 'ok'} />
                  <StatusPill label="Redis"    ok={data.health.redis === 'ok'} />
                </div>
              </div>

              <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 10, padding: '18px 20px', flex: 1 }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: T.muted, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 14 }}>Engagement</div>
                {[
                  { label: 'Broker connect rate', value: data.users.total > 0 ? `${Math.round(data.users.connected / data.users.total * 100)}%` : '—' },
                  { label: '7d retention',         value: data.users.total > 0 ? `${Math.round(data.users.active_7d / data.users.total * 100)}%` : '—' },
                  { label: 'Alerts / user',        value: data.users.total > 0 ? (data.activity.total_alerts / data.users.total).toFixed(1) : '—' },
                ].map(row => (
                  <div key={row.label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '5px 0', borderBottom: `1px solid ${T.border}` }}>
                    <span style={{ fontSize: 12, color: T.muted }}>{row.label}</span>
                    <span style={{ fontSize: 13, fontWeight: 600, color: T.text, fontVariantNumeric: 'tabular-nums' }}>{row.value}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
