import { useEffect, useState } from 'react';
import { Users, TrendingUp, Bell, Activity, RefreshCw, AlertTriangle, Wifi } from 'lucide-react';
import { adminApi } from '@/lib/adminApi';

const C = {
  text:   '#e2e8f0',
  muted:  'rgba(226,232,240,0.45)',
  dim:    'rgba(226,232,240,0.25)',
  border: 'rgba(255,255,255,0.07)',
  amber:  '#f59e0b',
  green:  '#10b981',
  red:    '#ef4444',
  dm:     "'DM Sans', sans-serif",
};

interface OverviewData {
  users:    { total: number; connected: number; new_today: number; active_7d: number; online_now: number };
  activity: { total_trades: number; total_alerts: number; alerts_today: number };
  health:   { db: string; redis: string };
  daily_signups: { date: string; count: number }[];
}

function StatCard({ icon: Icon, label, value, sub, color }: {
  icon: any; label: string; value: number | string; sub?: string; color?: string;
}) {
  return (
    <div style={{ background: 'rgba(255,255,255,0.03)', border: `1px solid ${C.border}`, borderRadius: 14, padding: '1.25rem 1.5rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <span style={{ fontSize: '0.78rem', color: C.muted }}>{label}</span>
        <div style={{ width: 32, height: 32, borderRadius: 9, background: `${color || C.amber}18`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Icon style={{ width: 15, height: 15, color: color || C.amber }} />
        </div>
      </div>
      <div style={{ fontSize: '1.8rem', fontWeight: 700, color: C.text, lineHeight: 1 }}>
        {typeof value === 'number' ? value.toLocaleString() : value}
      </div>
      {sub && <div style={{ fontSize: '0.72rem', color: C.muted, marginTop: 6 }}>{sub}</div>}
    </div>
  );
}

function Sparkline({ data }: { data: { date: string; count: number }[] }) {
  if (data.length < 2) return <p style={{ fontSize: '0.78rem', color: C.dim, padding: '1rem 0' }}>Not enough data yet</p>;
  const max = Math.max(...data.map(d => d.count), 1);
  const W = 600, H = 80, P = 6;
  const pts = data.map((d, i) => {
    const x = P + (i / (data.length - 1)) * (W - P * 2);
    const y = H - P - ((d.count / max) * (H - P * 2));
    return `${x},${y}`;
  });
  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: 80 }} preserveAspectRatio="none">
        <polygon points={`${P},${H} ${pts.join(' ')} ${W - P},${H}`} fill="rgba(245,158,11,0.07)" />
        <polyline points={pts.join(' ')} fill="none" stroke={C.amber} strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
        {data.map((d, i) => {
          const x = P + (i / (data.length - 1)) * (W - P * 2);
          const y = H - P - ((d.count / max) * (H - P * 2));
          return <circle key={i} cx={x} cy={y} r="2.5" fill={C.amber} />;
        })}
      </svg>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4 }}>
        <span style={{ fontSize: '0.67rem', color: C.dim }}>{data[0].date}</span>
        <span style={{ fontSize: '0.67rem', color: C.dim }}>{data[data.length - 1].date}</span>
      </div>
    </div>
  );
}

function StatusDot({ ok }: { ok: boolean }) {
  return <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: ok ? C.green : C.red, boxShadow: ok ? `0 0 6px ${C.green}` : `0 0 6px ${C.red}` }} />;
}

export default function AdminOverview() {
  const [data, setData]       = useState<OverviewData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState('');
  const [ts, setTs]           = useState('');

  const load = async () => {
    setLoading(true); setError('');
    try { const d = await adminApi.overview(); setData(d); setTs(new Date().toLocaleTimeString()); }
    catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  return (
    <div style={{ padding: '2rem', fontFamily: C.dm }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '2rem' }}>
        <div>
          <h1 style={{ fontSize: '1.3rem', fontWeight: 700, color: C.text, margin: 0 }}>Overview</h1>
          {ts && <p style={{ fontSize: '0.75rem', color: C.dim, marginTop: 4 }}>Updated {ts}</p>}
        </div>
        <button onClick={load} disabled={loading} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '0.5rem 1rem', borderRadius: 9, background: 'rgba(255,255,255,0.04)', border: `1px solid ${C.border}`, color: C.muted, fontSize: '0.78rem', cursor: loading ? 'not-allowed' : 'pointer', fontFamily: C.dm }}>
          <RefreshCw style={{ width: 13, height: 13, animation: loading ? 'spin 1s linear infinite' : 'none' }} />
          Refresh
        </button>
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>

      {error && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '0.75rem 1rem', borderRadius: 10, background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', marginBottom: '1.5rem' }}>
          <AlertTriangle style={{ width: 15, height: 15, color: C.red }} />
          <span style={{ fontSize: '0.82rem', color: C.red }}>{error}</span>
        </div>
      )}

      {data && (
        <>
          {/* Stat grid */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(190px, 1fr))', gap: '1rem', marginBottom: '2rem' }}>
            <StatCard icon={Users}      label="Total Users"   value={data.users.total} />
            <StatCard icon={Activity}   label="Connected"     value={data.users.connected}   sub="Zerodha linked"    color={C.green} />
            <StatCard icon={Wifi}       label="Online Now"    value={data.users.online_now}  sub="Active WebSocket"  color={C.green} />
            <StatCard icon={Users}      label="New Today"     value={data.users.new_today} />
            <StatCard icon={TrendingUp} label="Active (7d)"   value={data.users.active_7d} />
            <StatCard icon={TrendingUp} label="Total Trades"  value={data.activity.total_trades} />
            <StatCard icon={Bell}       label="Total Alerts"  value={data.activity.total_alerts} />
            <StatCard icon={Bell}       label="Alerts Today"  value={data.activity.alerts_today} color={data.activity.alerts_today > 50 ? C.red : undefined} />
          </div>

          {/* User growth chart */}
          <div style={{ background: 'rgba(255,255,255,0.03)', border: `1px solid ${C.border}`, borderRadius: 14, padding: '1.25rem 1.5rem', marginBottom: '1.5rem' }}>
            <h2 style={{ fontSize: '0.85rem', fontWeight: 600, color: C.text, marginBottom: '0.75rem' }}>New Signups — Last 14 Days</h2>
            <Sparkline data={data.daily_signups} />
          </div>

          {/* Infrastructure */}
          <div style={{ background: 'rgba(255,255,255,0.03)', border: `1px solid ${C.border}`, borderRadius: 14, padding: '1.25rem 1.5rem' }}>
            <h2 style={{ fontSize: '0.85rem', fontWeight: 600, color: C.text, marginBottom: '1rem' }}>Infrastructure</h2>
            <div style={{ display: 'flex', gap: '2rem' }}>
              {[
                { label: 'Database', ok: data.health.db === 'ok' },
                { label: 'Redis',    ok: data.health.redis === 'ok' },
              ].map(({ label, ok }) => (
                <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <StatusDot ok={ok} />
                  <span style={{ fontSize: '0.82rem', color: C.muted }}>{label}</span>
                  <span style={{ fontSize: '0.75rem', color: ok ? C.green : C.red }}>{ok ? 'healthy' : 'error'}</span>
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      {loading && !data && (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '3rem' }}>
          <div style={{ width: 28, height: 28, border: `2px solid ${C.amber}`, borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
        </div>
      )}
    </div>
  );
}
